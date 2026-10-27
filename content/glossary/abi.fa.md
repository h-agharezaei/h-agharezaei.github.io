+++
title = "ABI"
summary = "Application Binary Interface: قرارداد در سطح باینری (calling convention، چیدمان نوع‌ها، نام نمادها) بین کدهای کامپایل‌شده."
category = "Python"
fa_title = "ABI"
related = ["ffi", "pyo3", "wheel"]
posts = ["py-ffi-pyo3-ctypes"]
+++

دو تکه‌ی کامپایل‌شده فقط وقتی می‌توانند همدیگر را صدا بزنند که روی ABI توافق داشته باشند. Rust ABI پایدار خودش را ندارد، پس FFI از C ABI (`extern "C"`) می‌گذرد. CPython هم یک ABI محدود و پایدار (`abi3`) دارد که اجازه می‌دهد یک افزونه‌ی کامپایل‌شده روی چند نسخه‌ی Python کار کند.
