"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    c = cfg["label_format"]
    n_classes = len(ds.classes)
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)               # None nếu không có ảnh / ảnh hỏng -> bỏ qua BOX_TINY
        kept = []                                # các box hợp lệ ở dòng trước, để dò DUP_BOX
        for ln_no, text in ds.read_label_lines(stem) or []:
            try:
                box = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"dòng sai định dạng: {e}", line=ln_no))
                continue
            cls, cx, cy, w, h = box
            if not 0 <= cls < n_classes:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_classes - 1}", line=ln_no, extra={"id": cls}))
                continue
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"box rỗng (w={w}, h={h})", line=ln_no))
                continue
            overflow = max(w / 2 - cx, cx + w / 2 - 1, h / 2 - cy, cy + h / 2 - 1)   # mức tràn lớn nhất trong 4 mép
            if overflow > c["overflow_tol"]:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f}", line=ln_no, extra={"overflow": round(overflow, 4)}))
            if any(k[0] == cls and iou_xywh(k[1:], box[1:]) > c["dup_box_iou"] for k in kept):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box lặp với một dòng trước (cùng lớp)", line=ln_no))
            kept.append(box)
            if size and min(w * size[0], h * size[1]) < c["min_box_px"]:
                issues.append(Issue("label_format", WARN, "BOX_TINY", stem, f"cạnh ngắn {min(w * size[0], h * size[1]):.1f}px < {c['min_box_px']}px", line=ln_no))
            if w * h > c["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh", line=ln_no))
    return issues
