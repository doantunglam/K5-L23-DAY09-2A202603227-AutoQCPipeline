"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fx(image, line, action, before, after):
    return {"image": image, "line": "" if line is None else line, "action": action, "before": before, "after": after}


def _clip(text):
    """Cắt box về trong [0,1]; trả về dòng mới, hoặc None nếu box không còn diện tích."""
    cls, cx, cy, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]          # cảnh báo là việc của người, không đụng
    fixes = []

    # 1) Xoá ảnh (+ nhãn): làm trước để các issue khác của ảnh đó được bỏ qua êm.
    removed = set()
    for i in errors:
        if i.code in REMOVE_CODES and i.image not in removed:
            img, lab = ds.image_path(i.image), ds.label_path(i.image)
            if img is None and not lab.exists():
                continue                                          # đã xoá từ trước
            fixes.append(_fx(i.image, None, "remove_image", f"{img.name if img else '(không có ảnh)'}", f"(đã xoá: {i.code})"))
            if img is not None:
                img.unlink()
            if lab.exists():
                lab.unlink()
            ds._size_cache.pop(i.image, None)
            removed.add(i.image)

    # 2) Lỗi theo dòng: gom theo file, dùng số dòng GỐC, ghi lại một lần.
    drops, clips = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.image in removed or i.line is None:
            continue
        if i.code in DROP_CODES:
            drops[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clips[i.image].add(i.line)
    for stem in sorted(set(drops) | set(clips)):
        rows = ds.read_label_lines(stem)
        if rows is None:
            continue
        out, changed = [], False
        for ln_no, text in rows:
            if ln_no in drops[stem]:
                fixes.append(_fx(stem, ln_no, "drop_line", text, "(đã xoá dòng)"))
                changed = True
                continue
            if ln_no in clips[stem]:
                try:
                    new = _clip(text)
                except ValueError:
                    new = None
                if new is None:
                    fixes.append(_fx(stem, ln_no, "drop_line", text, "(đã xoá dòng: box nằm ngoài ảnh)"))
                else:
                    fixes.append(_fx(stem, ln_no, "clip_box", text, new))
                    out.append(new)
                changed = True
                continue
            out.append(text)
        if changed:
            ds.label_path(stem).write_text("".join(t + "\n" for t in out), encoding="utf-8")

    # 3) Ảnh thiếu nhãn: không bịa nhãn, chuyển cho người.
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append(_fx(i.image, None, "needs_label", "(không có file)", "chuyển người gán"))

    # 4) Tên lớp trong data.yaml.
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        d = (yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else None) or {}
        before = d.get("names")
        d["names"] = {k: n for k, n in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(_fx("data.yaml", None, "rename_classes", str(before), str(d["names"])))
    return fixes
