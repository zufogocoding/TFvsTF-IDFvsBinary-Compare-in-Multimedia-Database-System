# Kiểm chứng bản bàn giao

- Thực nghiệm chính: `20261018T083500_336f4644`.
- SHA-256 mã nguồn: `1019443839d879dfa762358967e55c87aaeceb9699c28944b5cc620c0d20112f`.
- Dataset: 1.400 bản ghi, 225 truy vấn, 1.837 qrels; 45 DEV và 180 TEST.
- 7.044 thuật ngữ; 2 bản ghi không tạo token được giữ trong kho.
- 28 kiểm thử tự động thành công; log đầy đủ tại `docs/test_log.txt`.
- Đã kiểm tra trình duyệt: ba danh sách, ánh xạ Q3, mở văn bản, trọng số, từ ngoài từ vựng, chín bảng dữ liệu, chạy DEV, tải CSV và màn hình 390 px; không có lỗi JavaScript chưa xử lý.
- Đã kiểm tra đủ 540 query_runs, 3.240 query_metrics và 16.200 timing_samples trên TEST.
- SQLite integrity_check = ok; foreign_key_check không có lỗi; journal_mode = DELETE.
- Gói bàn giao giữ snapshot của lần TEST hoàn tất này. Các lần chạy mới tạo ID riêng.

## Kết quả đo thật

| Biểu diễn | MAP | nDCG nhị phân@10 | P@10 | R@20 | p50 ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BINARY | 0.155637 | 0.205305 | 0.129444 | 0.294237 | 1.917 | 3.190 |
| TF | 0.164519 | 0.221479 | 0.130000 | 0.277438 | 1.905 | 3.181 |
| TFIDF | 0.275406 | 0.354078 | 0.230556 | 0.480381 | 2.141 | 3.553 |

## Môi trường

```json
{
  "python": "3.12.14",
  "platform": "Linux-6.18.55-x86_64-with-glibc2.39",
  "processor": "x86_64",
  "machine": "x86_64",
  "cpu_model": "INTEL(R) XEON(R) PLATINUM 8573C",
  "logical_cpus": 9,
  "ram_total_bytes": 10451435520,
  "numpy": "2.3.5",
  "scipy": "1.17.0",
  "scikit_learn": "1.8.0",
  "threadpools": [
    {
      "internal_api": "openblas",
      "num_threads": 1,
      "version": "0.3.30",
      "architecture": "SkylakeX"
    },
    {
      "internal_api": "openblas",
      "num_threads": 1,
      "version": "0.3.30",
      "architecture": "SkylakeX"
    },
    {
      "internal_api": "openmp",
      "num_threads": 1,
      "version": null,
      "architecture": null
    }
  ],
  "timing_clock": "time.perf_counter_ns",
  "timing_unit": "ms"
}
```

Ứng dụng được chạy và kiểm chứng trên Linux với Python 3.12.14. Hướng dẫn và tập lệnh Windows đi kèm; chưa khẳng định đã chạy kiểm thử trên một máy Windows thực tế.

Độ trễ là số đo của môi trường được ghi trong tệp, không phải số đo của máy cá nhân người sử dụng. Không suy rộng thứ tự chất lượng ngoài bộ dữ liệu và cấu hình này.
