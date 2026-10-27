+++
title = "PyO3"
summary = "یک کتابخانه‌ی Rust برای نوشتن ماژول‌های توسعه‌ی Python (و صدا زدن Python از Rust)."
category = "Python"
fa_title = "PyO3"
related = ["ffi", "gil", "wheel"]
posts = ["py-ffi-pyo3-ctypes"]
+++

با PyO3 توابع و structهای Rust را با `#[pyfunction]`، `#[pyclass]` و `#[pymodule]` علامت می‌زنید و ابزار build مثل maturin کرِیت را به یک ماژول قابل import در Python تبدیل می‌کند. تبدیل آرگومان‌ها و نگاشت خطا به exception خودکار تولید می‌شود.
