# So sánh Binary, TF và TF-IDF trong truy xuất văn bản

Hệ thống truy vấn cục bộ bằng Python, giao diện HTML/CSS/JavaScript tiếng Việt. Dataset là **Cranfield tiếng Anh**, có 1.400 bản ghi văn bản, 225 truy vấn và 1.837 nhãn liên quan. Mã nguồn, dataset đã kiểm tra checksum, SQLite, chỉ mục và kết quả thực nghiệm được cung cấp cùng dự án.

## Chạy nhanh trên Windows

Khuyến nghị **Python 3.12 bản 64-bit**. Giải nén toàn bộ dự án; mở PowerShell tại thư mục chứa `app.py`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --open-browser
```

Truy cập **http://127.0.0.1:8000**. Nhấn Ctrl+C trong cửa sổ Python để dừng. Nếu cổng đang được dùng:

```powershell
.\.venv\Scripts\python.exe app.py --port 8001 --open-browser
```

Cũng có thể mở `RUN_WINDOWS.bat`. Không cần kích hoạt venv, nên không cần đổi chính sách chạy script của PowerShell.

Trên Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --open-browser
```

Sau khi cài thư viện, tìm kiếm chạy offline; giao diện không dùng CDN, dịch vụ AI hoặc khóa API. Dataset đã nằm trong gói, không cần tải lại để demo. Dự án không đụng đến các môi trường TensorFlow/IoT khác trên máy.

## Demo truy vấn

1. Mở tab **Truy vấn & so sánh**.
2. Chọn truy vấn mẫu có nhãn, chẳng hạn Q3 về `heat conduction in composite slabs`, hoặc tự nhập `boundary layer pressure`.
3. Chọn Top 5/10/20 và bấm **So sánh kết quả**.
4. Đối chiếu ba danh sách; nhấp tiêu đề để xem toàn văn. Mở phần trọng số thuật ngữ để xem Binary, TF, IDF và TF-IDF trước chuẩn hóa.
5. Với truy vấn mẫu, AP và P@10 được tính từ **toàn bộ** danh sách được truy xuất, độc lập với số kết quả hiển thị. Truy vấn tự nhập không có nhãn sẽ không được gán chỉ số chất lượng giả.

Kho văn bản là tiếng Anh. Giao diện không tự dịch truy vấn tiếng Việt. Điểm cosine chỉ dùng xếp hạng trong từng phương pháp; không so chất lượng bằng cách lấy phương pháp có điểm cosine lớn nhất.

## Chạy thực nghiệm

Trong giao diện, mở tab **Thực nghiệm**; chọn TEST và 30 lượt đo rồi bấm chạy. Có thể chọn DEV với 1 hoặc 3 lượt để kiểm tra nhanh. Khi đang đo, API tìm kiếm tạm từ chối truy vấn mới để hạn chế làm nhiễu thời gian.

Để đo trong tiến trình riêng, dừng máy chủ và chạy:

```powershell
.\.venv\Scripts\python.exe evaluate.py --split TEST --repeats 30 --bootstrap 10000
```

Mỗi lần chạy có ID mới, không ghi đè kết quả cũ. Khởi động lại ứng dụng để xem kết quả hoặc chọn lần chạy trong danh sách lịch sử. Thời gian phụ thuộc máy; không sao chép số mili giây của máy kiểm chứng để nhận là số đo trên máy cá nhân.

Các tệp trong `results/<experiment_id>/`:

| Tệp | Nội dung |
| --- | --- |
| `summary.csv`, `summary.json` | Chỉ số trung bình, độ trễ và thống kê chỉ mục |
| `per_query_metrics.csv` | Chỉ số từng cặp truy vấn–phương pháp |
| `rankings.tsv` | Toàn bộ văn bản có điểm dương, thứ hạng và điểm chưa làm tròn |
| `timing_samples.csv` | Từng mẫu thời gian; tách tạo vector, chấm điểm và sắp xếp |
| `paired_comparisons.json` | Chênh lệch AP ghép cặp và bootstrap 95% |
| `config.json` | Cấu hình, ID truy vấn, công thức, seed và số lượt đo |
| `environment.json` | Python, thư viện, CPU, RAM và chính sách luồng |
| `manifest.json` | Nguồn dataset, checksum và dấu vết tệp chỉ mục |

## Quy trình khoa học được triển khai

- Dùng chung tiền xử lý NFKC, chữ thường, token `[a-z]+`, unigram; giữ từ dừng và không stemming.
- Tạo **một** ma trận đếm và **một** từ vựng từ toàn kho. Không fit trên truy vấn hoặc nhãn.
- Binary: `1 nếu count > 0`; TF: `count`; TF-IDF: `count * ln(N/df)`.
- Chuẩn hóa L2 cho cả văn bản và truy vấn của ba phương pháp, dùng cùng cosine.
- Trọng số TF-IDF được tính trực tiếp theo công thức sách. Không dùng mặc định `TfidfTransformer`, vì công thức IDF mặc định có cộng 1/làm trơn.
- Chia **truy vấn** thành 45 DEV và 180 TEST bằng `random.Random(42).shuffle`; toàn bộ 1.400 bản ghi vẫn là kho có thể truy xuất.
- Giữ 2 bản ghi không tạo được token. Chúng có vector 0, không được trả về; N trong IDF vẫn là 1.400. Đây là một quy ước được khai báo rõ để bảo toàn mã và qrels.
- Truy xuất mọi văn bản có cosine > 0, không cắt sớm trước khi tính AP. Phá hòa bằng `doc_id` tăng dần theo chuỗi, không làm tròn điểm trước khi xếp hạng.
- Nhãn liên quan là `raw_grade > 0`; cặp không có qrel được xem là không liên quan theo quy ước đánh giá. nDCG@10 dùng **gain nhị phân**, không dùng độ lớn các mức dương.
- MAP là chỉ số chính; bổ sung P@5, P@10, R@10, R@20 và nDCG nhị phân@10. Trung bình theo truy vấn.
- Chạy khởi động 3 lần/phương pháp; đo 30 lần/truy vấn/phương pháp, hoán vị thứ tự phương pháp với seed 42. Loại HTTP, giao diện và ghi SQLite khỏi khoảng thời gian đo.
- Ba ma trận dùng float64. Bộ nhớ CSR là tổng byte của `data`, `indices`, `indptr`; vì vậy Binary không mặc nhiên chiếm ít bộ nhớ hơn TF trong triển khai này.
- Bootstrap ghép cặp lấy lại mẫu ở mức **truy vấn**, không coi 30 lượt đo thời gian là 30 truy vấn độc lập. Các khoảng là phân tích thăm dò, không tuyên bố đã hiệu chỉnh đồng thời nhiều phép so sánh.

## Dataset và vấn đề cần đọc trước khi làm báo cáo

Nguồn gốc: <https://ir.dcs.gla.ac.uk/resources/test_collections/cran/cran.tar.gz>

Tài liệu bộ nạp chuẩn: <https://ir-datasets.com/cranfield.html>

`cran.qry` có mã `.I` không liên tiếp. **Qrels sử dụng thứ tự bản ghi 1–225**, không phải mã `.I` nguyên gốc. Bộ chuyển đổi lưu cả `query_id` chuẩn và `source_query_id`; Q3 tương ứng mã nguồn `004`. Đây cũng là cách bộ nạp `ir_datasets` ánh xạ truy vấn.

Tệp README nhãn gốc và trang mô tả bộ nạp có khác biệt về cách mô tả thứ tự các mức dương. Do đó các chỉ số chính ở đây dùng **nhãn nhị phân** và nDCG nhị phân. Không tự đảo mức hoặc tuyên bố đã xác minh ngữ nghĩa thứ bậc. Xem `data/SOURCE.md` và `data/raw/cranqrel.readme`.

Để tải/chuyển đổi lại chính phiên bản dataset đã kiểm chứng:

```powershell
.\.venv\Scripts\python.exe prepare_data.py
```

Hoặc `prepare_data.py --archive duong_dan/cran.tar.gz`. Tệp tải phải khớp SHA-256 cố định; tệp đã chuyển đổi cũng có checksum. Nếu chỉnh dữ liệu, phải tạo phiên bản dataset mới và cơ sở dữ liệu riêng thay vì sửa tệp rồi bỏ qua kiểm tra hash.

## Cấu trúc mã nguồn và Chương III

| Thành phần | Vai trò |
| --- | --- |
| `app.py`, `ir_system/server.py` | Máy chủ HTTP cục bộ, API và giao diện |
| `web/index.html`, `web/app.js`, `web/style.css` | Giao diện truy vấn, thực nghiệm và dữ liệu |
| `prepare_data.py`, `ir_system/dataset.py` | Tải, kiểm tra và chuẩn hóa dataset |
| `ir_system/engine.py` | Từ vựng chung, ba biểu diễn, cosine và xếp hạng |
| `ir_system/metrics.py` | AP, P@k, R@k và nDCG nhị phân |
| `ir_system/experiment.py`, `evaluate.py` | Thực nghiệm theo lô, đo thời gian, bootstrap và xuất tệp |
| `ir_system/storage.py`, `schema.sql` | SQLite và chín bảng có khóa ngoại |
| `ir_system/config.py` | Cấu hình cố định, hash dữ liệu/mã nguồn |
| `tests/` | Kiểm thử tính tay, dữ liệu, cơ sở dữ liệu và API |
| `docs/` | Chương III tương ứng với hệ thống đã triển khai |
| `VERIFICATION.md` | Môi trường và kết quả kiểm chứng của bản bàn giao |

Năm mục báo cáo giữ đúng thứ tự: **3.1 Khảo sát**, **3.2 Phân tích**, **3.3 Thiết kế tổng thể**, **3.4 Cơ sở dữ liệu**, **3.5 Chức năng**. Chương III mô tả phương pháp và cấu hình thực thi; kết luận phương pháp nào tốt hơn cần dựa vào các kết quả thật trong `results/` và giới hạn trong phạm vi Cranfield.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử bao gồm công thức tính tay, vector 0, từ ngoài từ vựng, phá hòa, nhãn sai mã, checksum bị thay đổi, AP có văn bản liên quan không được trả về, nDCG nhị phân và API. Chúng không thay thế đánh giá trên TEST.

## Cơ sở dữ liệu

`runtime/ir_compare.sqlite3` gồm `datasets`, `documents`, `queries`, `qrels`, `experiments`, `query_runs`, `ranked_results`, `query_metrics`, `timing_samples`. Dùng DB Browser for SQLite hoặc công cụ tương đương để mở khi ứng dụng đã dừng. Tệp `schema.sql` là DDL thực tế của hệ thống.

## Giới hạn

Đây là ứng dụng nghiên cứu cục bộ, lắng nghe trên 127.0.0.1; không có tài khoản người dùng, phân quyền hay triển khai máy chủ công cộng. Dataset nhỏ, một miền chuyên ngành và tiếng Anh. Kết quả không chứng minh phương pháp tốt nhất cho mọi ngôn ngữ hoặc hệ thống tìm kiếm khác.
