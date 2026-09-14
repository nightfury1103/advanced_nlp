# Phiếu cập nhật số liệu báo cáo giữa kỳ: 12 tập

Tài liệu này dùng để cập nhật báo cáo giữa kỳ từ phạm vi **10 tập / 3.706 trang** sang **12 tập / 4.432 trang**. Agreement voting, tách câu và NER đã hoàn tất cho cả 12 tập; các số dưới đây được tổng hợp trực tiếp từ artefact của hai run 1–10 và 11–12.

## 1. Số liệu tổng quan cần thay ngay

| Chỉ tiêu | Số cũ | Số đúng cho phạm vi 12 tập | Ghi chú |
|---|---:|---:|---|
| Số tập sách | 10 | **12** | Bổ sung tập 11 và tập 12. |
| Tổng số trang đầu vào | 3.706 | **4.432** | 3.706 + 357 + 369. |
| Số trang tập 11 | Không nêu | **357** | Đã có trong manifest OCR. |
| Số trang tập 12 | Không nêu | **369** | Đã có trong manifest OCR. |
| Churro OCR | 10 tập / 3.706 trang | **12 tập / 4.432 trang** | Đủ toàn bộ corpus. |
| Qwen3.5 OCR | 10 tập / 3.706 trang | **12 tập / 4.432 trang** | Đủ toàn bộ corpus. |
| Surya OCR | Không nêu hoặc không thống nhất | **4.154 trang / 12 tập** | Thiếu 278 trang so với 4.432; riêng tập 7 có 130/408 trang. |

## 2. Phân bố số trang theo từng tập

| Tập | Số trang |
|---:|---:|
| 1 | 418 |
| 2 | 384 |
| 3 | 319 |
| 4 | 368 |
| 5 | 369 |
| 6 | 403 |
| 7 | 408 |
| 8 | 349 |
| 9 | 328 |
| 10 | 360 |
| 11 | 357 |
| 12 | 369 |
| **Tổng** | **4.432** |

## 3. Các vị trí cần sửa trong báo cáo

### Tóm tắt

Thay câu cũ có nội dung “10 tập sách, gồm 3.706 trang” bằng:

> Kết quả hiện có cho thấy bộ dữ liệu gồm **12 tập sách với 4.432 trang ảnh quét**. Churro và Qwen3.5 đã tạo đầu ra OCR cho toàn bộ corpus; các đầu ra này là nguồn cho bước hợp nhất kết quả OCR.

Các số NER tổng hợp cho 12 tập là **12.564 thực thể sau vote**, **10.054 thực thể release candidate** và **28.039 câu bất đồng**.

### Mục 2.1 – Mô tả dữ liệu đầu vào

Thay:

> Toàn bộ tập dữ liệu gồm 10 tập sách, 3.706 trang.

Bằng:

> Toàn bộ tập dữ liệu gồm **12 tập sách với 4.432 trang ảnh quét**. Số trang của từng tập được trình bày tại Bảng [x].

Thêm Bảng phân bố số trang theo 12 tập ở Mục 2 của tài liệu này.

### Mục 3.2 – Bước OCR

Thay cách viết chỉ nêu xử lý “toàn tập” nhưng không nêu phạm vi bằng:

> Ở giai đoạn OCR toàn tập, Churro và Qwen3.5 đã xử lý đầy đủ **12 tập, tương ứng 4.432 trang**. Surya OCR tạo đầu ra cho 4.154 trang; KanDianGuJi có phạm vi chạy khác với các mô hình còn lại. Các đầu ra tương thích được chuẩn hóa và đưa vào agreement voting theo từng trang.

### Mục 4.1 – Khối lượng dữ liệu xử lý

Thay hai dòng đầu bằng các giá trị sau:

| Chỉ số | Giá trị để báo cáo |
|---|---:|
| Corpus đầu vào | **12 tập / 4.432 trang** |
| Churro OCR | **4.432 trang** |
| Qwen3.5 OCR | **4.432 trang** |
| Surya OCR | **4.154 trang** |

Agreement voting, tách câu và NER đã hoàn tất cho 12 tập. Điền **12.564 thực thể sau vote**, **10.054 thực thể release candidate** và **28.039 câu bất đồng**.

### Mục 4.2 – Sản phẩm đầu ra

Sửa “văn bản OCR đã hợp nhất” thành:

> Văn bản OCR đã hợp nhất của **12 tập / 4.432 trang**; trong đó **4.393 trang có văn bản** và **39 trang trống**.

### Mục 4.3 – Ví dụ minh họa

Chọn một trang thuộc tập 11 hoặc tập 12 làm ví dụ minh họa. Điều này chứng minh trực tiếp rằng phạm vi 12 tập đã được mở rộng, thay vì chỉ thay số trong bảng.

### Mục 6 – Kết luận

Thay mọi cụm “toàn bộ 10 tập” hoặc “3.706 trang” bằng:

> Corpus đầu vào của đề tài gồm **12 tập với 4.432 trang**. OCR agreement voting và tách câu đã tạo ra **36.387 câu** làm đầu vào NER. NER agreement voting thu được **12.564 thực thể**; sau bước lọc bảo thủ, bộ release candidate còn **10.054 thực thể**. Có **28.039 câu** chứa bất đồng được lưu riêng để kiểm tra.

## 4. Những số giữ nguyên

Các số dưới đây thuộc benchmark năm trang mẫu nên **không đổi** khi mở rộng corpus từ 10 lên 12 tập:

| Chỉ tiêu benchmark | Giá trị |
|---|---:|
| Số trang benchmark | 5 trang: 044, 080, 160, 240, 320 |
| KanDianGuJi Aligned CER | 0,2527 |
| olmOCR L4 FP8 Aligned CER | 0,3031 trên 4/5 trang |
| GJ.cool Aligned CER | 0,3582 |
| Umi/RapidOCR CPU Aligned CER | 0,8445 |
| Qwen3.5-397B Aligned CER | 0,1282 |
| Qwen3-VL-8B Aligned CER | 0,1409 |
| Churro-3B Aligned CER | 0,1909 |

## 5. Số liệu downstream đã được kiểm chứng

Các số liệu dưới đây được cộng từ summary thực tế của run 1–10 và run 11–12:

| Chỉ tiêu downstream | Giá trị hiện có cho 10 tập | Giá trị phải báo cáo cho 12 tập |
|---|---:|---|
| Trang sau agreement voting | 3.706 | **4.432** |
| Trang `ok` / `blank` | 3.674 / 32 | **4.393 / 39** |
| Tổng số câu theo Jiayan | 117.171 | **142.538** |
| Câu sau sentence vote / đầu vào NER | 29.474 | **36.387** |
| Thực thể sau vote | 9.998 | **12.564** |
| Thực thể release candidate | 7.907 | **10.054** |
| Câu bất đồng NER | 22.761 | **28.039** |

Phân bố 10.054 thực thể trong release candidate: **LOCATION 5.507**, **PERSON 3.310**, **DATE 1.026**, **ORGANIZATION 189** và **TIME 22**.

## 6. Quy tắc viết để tránh sai số

1. Chỉ dùng cụm **“12 tập / 4.432 trang”** cho phạm vi đầu vào và output OCR đã xác minh.
2. Có thể viết agreement voting, tách câu và NER đã hoàn thành cho toàn bộ 12 tập.
3. Các số thực thể 12 tập phải lấy từ summary NER thực tế, không suy ra theo tỉ lệ.
4. Trong bảng coverage OCR, luôn ghi phạm vi của từng model; không mặc định mọi model đều có 4.432 trang.

## 7. Căn cứ kiểm chứng

- `outputs/ocr_runs/churro/churro-full-001/manifest.jsonl`: 12 tập, 4.432 trang.
- `outputs/ocr_runs/qwen35/qwen35-full-001/manifest.jsonl`: 12 tập, 4.432 trang.
- `outputs/ocr_runs/surya_ocr-full-001/manifest.jsonl`: 12 tập, 4.154 trang.
- `outputs/ocr_agreement/agreement-vote-books-011-012-final-v001-gap-vote-kdg-priority/manifest.jsonl`: 726 trang, 719 ok và 7 blank.
- `outputs/sentence_separation/*-books-011-012-v001/manifest.jsonl`: kết quả tách câu tập 11–12.
- `outputs/ner/ner-agreement-vote-books-001-010-v001/summary.json`: 29.474 câu, 9.998 thực thể sau vote và 22.761 câu bất đồng.
- `outputs/ner/ner-agreement-vote-books-011-012-v001/summary.json`: 6.913 câu, 2.566 thực thể sau vote và 5.278 câu bất đồng.
- `outputs/ner/ner-release-candidate-books-001-010-v001/summary.json`: 7.907 thực thể release candidate.
- `outputs/ner/ner-release-candidate-books-011-012-v001/summary.json`: 2.147 thực thể release candidate.
