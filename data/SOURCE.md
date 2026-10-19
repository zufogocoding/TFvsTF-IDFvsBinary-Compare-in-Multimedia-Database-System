# Nguồn và quy ước Cranfield

- Nguồn lưu trữ Đại học Glasgow: https://ir.dcs.gla.ac.uk/resources/test_collections/cran/cran.tar.gz
- Tài liệu chuẩn hóa: https://ir-datasets.com/cranfield.html
- Bộ nạp tham chiếu: https://github.com/allenai/ir_datasets/blob/master/ir_datasets/datasets/cranfield.py
- SHA-256 của archive: `8c48a8412e4a7e6e0dd5af99c959f8d75fdf88135602adc1a56aa22770652d64`

Archive gốc được giữ tại `raw/cran.tar.gz`. Các thành phần `cran.all.1400`, `cran.qry`, `cranqrel`, `cranqrel.readme` được giữ nguyên byte. JSONL/TSV chuẩn hóa chỉ gộp khoảng trắng, bảo toàn văn bản, mã tài liệu và nhãn gốc. `source_query_id` bảo toàn thẻ `.I`; `query_id` là thứ tự bản ghi 1–225 để khớp qrels. Không ánh xạ qrels trực tiếp theo mã `.I` có khoảng trống.

Quy ước đánh giá dùng `raw_grade > 0` là liên quan; -1 và cặp không có qrel đóng góp 0. Các mã 1–4 được lưu nguyên, **không tự gán tên mức cao/thấp** trong giao diện. README gốc liệt kê thứ tự ngữ nghĩa khác với trang mô tả của ir_datasets; vì vậy nDCG được tính với gain nhị phân. MAP, Precision, Recall và nDCG nhị phân không phụ thuộc vào việc đảo thứ tự các mức dương.

Hai bản ghi không tạo được token vẫn được giữ trong 1.400 hàng và mẫu số N của IDF. Các checksum tệp chuẩn hóa nằm trong `manifest.json`. Nguồn dữ liệu và ghi chú gốc được giữ để truy vết; không tuyên bố một giấy phép mới cho dataset.
