# Báo cáo Day 09 — <Họ và tên>, 2A202603227

> Các mục 1, 2, 3, 4(a), 5 được điền từ số liệu thật trong `submission/reports/`, `submission/calibration/`, `submission/results/`. Mục 4(b) và mục 6 là phần học viên tự điền.

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Vào 224 ảnh, cửa vào loại 22 (8 trùng byte, 5 rò rỉ test, 4 trùng gần đúng, 3 quá nhỏ, 2 hỏng) nên còn **202 ảnh**; bản xuất `export/clean_v1` chỉ là **bản nháp**, chưa được phát hành.
Lý do: không còn lỗi bắt buộc nào (0), nhưng sau 80 ảnh được người duyệt vẫn còn **38/202 ảnh (18,8%)** có cảnh báo chưa duyệt, vượt ngưỡng 10% (`07_error_list_v3`, `08_summary.json`).

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1` (lô raw 224 ảnh; mẫu số mỗi dòng là số ảnh bị ảnh hưởng / số dòng cờ).

| Mã lỗi | Số ảnh / dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE | 2 / 2 | máy (loại ảnh) | cú pháp, bắt chắc chắn |
| BAD_SIZE | 3 / 3 | máy (loại ảnh) | cạnh ngắn < 250 px |
| DUP_IMAGE_EXACT | 8 / 8 | máy (loại ảnh) | trùng md5 |
| DUP_IMAGE_NEAR | 4 / 4 | máy (loại ảnh) | phash ≤ 12; đã mở xem các cặp mới, đều là trùng thật |
| LEAK_TEST | 5 / 5 | máy (loại ảnh) | trùng ảnh test/val, phải loại để đo công bằng |
| BAD_FORMAT | 3 / 3 | máy (xoá dòng) | dòng thiếu cột/nan |
| BAD_CLASS_ID | 6 / 6 | máy (xoá dòng) | id lớp ngoài 0..3 |
| BOX_ZERO | 4 / 4 | máy (xoá dòng) | w hoặc h ≤ 0 |
| DUP_BOX | 7 / 7 | máy (xoá dòng) | cùng lớp, IoU > 0,9 |
| BOX_OUT_OF_IMAGE | 8 / 8 | máy (cắt box) | box tràn ảnh, cắt về [0,1] |
| BAD_CLASS_NAME | 1 / 2 | máy (ghi lại `data.yaml`) | tên lớp viết sai |
| MISSING_LABEL_FILE | 6 / 6 | **người** | máy không được bịa nhãn; chuyển người gán |
| POSSIBLE_MISSING | 52 / 53 | **người** | model thấy vật mà nhãn không có box |
| POSSIBLE_WRONG_CLASS | 18 / 18 | **người** | nghi gán nhầm lớp (car/truck/bus) |
| POSSIBLE_LOOSE_BOX | 24 / 28 | **người** | box lệch/lỏng so với model |
| POSSIBLE_FALSE_POS | 27 / 29 | **người** | box nhãn không khớp vật nào model thấy |
| EMPTY_LABEL, BOX_TINY, BOX_HUGE, CLASS_RARE | 12, 4, 3, 1 ảnh | **người** | cảnh báo, ý nghĩa cần người xét |

Autofix ghi 35 thay đổi vào `03_fixes.csv`: 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`.

**Hàng đợi duyệt.** `05_review_queue.csv` có 125 ảnh, xếp theo điểm ưu tiên cộng các trọng số trong `configs/pipeline.yaml`. Ảnh thiếu file nhãn (`NEEDS_LABEL`, trọng số 10) đứng đầu vì chưa có nhãn nào; tiếp theo là ảnh có nghi gán nhầm lớp (trọng số 3), thiếu box hoặc box thừa (2), box lỏng (1,5), cảnh báo cỡ box (0,3 đến 0,5). Ngân sách 80 ảnh được dùng hết (`06_review_log.csv`: 80 ảnh được thay bằng nhãn người), nên **45 ảnh trong hàng đợi không ai xem**. Sau duyệt còn 21 cờ `POSSIBLE_FALSE_POS`, 20 `POSSIBLE_LOOSE_BOX`, 13 `POSSIBLE_MISSING`, 3 `POSSIBLE_WRONG_CLASS` (`07_error_list_v3`).

## 3. Calibration (2 ngưỡng)
Số liệu từ `submission/calibration/calibration_report.md` (calib 39 ảnh), mỗi ô là precision / recall.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_IMAGE_NEAR: 1,00 / 0,50 → 1,00 / 0,67 | Xoá ảnh là hành động phá huỷ nên ưu tiên precision. 12 giữ precision 1,00 và tăng recall; trên raw số cờ không đổi từ 10 đến 14 nên 12 nằm giữa vùng ổn định. |
| `second_opinion.conf` | 0.25 | **0.6** | MISSING: 0,50 / 1,00 → 0,57 / 1,00; WRONG_CLASS: 0,56 / 0,83 → 0,62 / 0,83; LOOSE_BOX: 0,29 / 0,40 → 0,20 / 0,20; FALSE_POS: 0,31 / 1,00 (không đổi) | Cảnh báo chỉ chuyển người xem nên chấp nhận precision thấp, nhưng chọn mức cao nhất vẫn giữ recall 1,00 cho MISSING và 0,83 cho WRONG_CLASS. Nâng lên 0,7 thì recall MISSING giảm còn 0,88. Đổi lại LOOSE_BOX tệ hơn (recall 0,20, chỉ 5 lỗi chèn nên rất nhiễu). |

Hiệu quả trên raw: tỉ lệ ảnh còn cảnh báo sau duyệt giảm từ 29,3% (60/205) xuống 18,8% (38/202), vẫn trên ngưỡng 10% nên kết luận là Hold.

**Một chỗ calibration đánh lừa.** Trên calib, `phash_dist = 16` trông tốt nhất (recall DUP_IMAGE_NEAR 0,83, precision vẫn 1,00). Nhưng trên raw, số ảnh bị gắn LEAK_TEST nhảy từ 5 (ở 14) lên 11 (ở 16), và lên 105 ảnh (cùng 25 DUP_IMAGE_NEAR) ở 20. Tôi mở xem 4 cặp ảnh bị gắn thêm ở 16 (img_0013, img_0017, img_0021, img_0033 so với ảnh test_087, test_071, test_048, test_070): cả 4 là ảnh hoàn toàn khác nhau (bàn laptop với sân bóng chày, người đứng với ngựa nhảy rào...). Chọn 16 sẽ xoá nhầm ảnh tốt. Nguyên nhân: ảnh calib dựng từ biến đổi có kiểm soát, còn raw có cảnh tự nhiên nên khoảng cách phash của ảnh khác nhau thấp hơn nhiều.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt): vẫn còn **6 lỗi bắt buộc** (6 ảnh thiếu file nhãn nên `MISSING_LABEL_FILE`), kết luận **Rework**, mã thoát **20**, log ghi "KHÔNG xuất: còn lỗi bắt buộc" và thư mục `work/exp_nb` không được tạo, tức không xuất dataset. Khi có người duyệt (80 ảnh, `reviewed`), lỗi bắt buộc về 0 và gate chuyển sang Hold.

TODO(học viên): (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh, ca không có trong calib như đã nêu ở `docs/CALIBRATION.md`…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Model `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1, cùng val (`gold_val` 40 ảnh) và cùng test (100 ảnh), GPU RTX 4060 (`submission/results/comparison.md`).

| biến thể | #ảnh train | số seed | mAP50 | mAP50-95 | precision | recall |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0,725 ± 0,004 | 0,526 ± 0,010 | 0,747 ± 0,068 | 0,628 ± 0,016 |
| clean | 202 | 2 | 0,740 ± 0,008 | 0,512 ± 0,002 | 0,770 ± 0,040 | 0,650 ± 0,032 |

Từng seed (mAP50): raw 0,728 / 0,723; clean 0,735 / 0,745. Chênh mAP50 (clean − raw) = **+0,015**, tức khoảng 2 đến 4 lần độ lệch chuẩn giữa các seed (0,004 và 0,008), nhưng chỉ có 2 seed nên ước lượng nhiễu kém tin cậy. Mặt khác mAP50-95 của clean **thấp hơn** 0,014 và precision có độ lệch lớn. **Kết luận trung thực: chưa đủ bằng chứng để nói clean tốt hơn raw**; chênh nhỏ, tín hiệu lẫn lộn giữa hai chỉ số, test chỉ 100 ảnh.

Giả thuyết giải thích và cách kiểm (chưa kiểm):
1. Rò rỉ test trong raw (5 ảnh trùng test) có thể làm raw đo cao hơn thực tế, che khoảng cách thật. Kiểm: loại riêng 5 ảnh đó khỏi raw, train lại rồi so.
2. Clean vẫn còn nhãn máy: 38 ảnh còn cảnh báo, và lỗi ngữ nghĩa (thiếu box, box lỏng) phần lớn chưa được sửa, nên cải thiện bị giới hạn. Kiểm: so thêm biến thể `oracle` (nhãn người) bằng `train_compare.py --variants oracle`.
3. Số ảnh mỗi lớp ít, nhất là `truck` và `bus`, làm AP theo lớp dao động mạnh giữa các seed. Kiểm: xem `ap50_per_class` trong các file `*_seed*.json` và chạy thêm seed (ví dụ 5 seed).

Bước tiếp theo: tăng số seed lên ít nhất 5 và thêm biến thể `oracle` trước khi kết luận.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
