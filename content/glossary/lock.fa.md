+++
title = "Lock"
summary = "سازوکاری که یک session را وادار می‌کند پیش از دست زدن به داده‌ای که session دیگری استفاده می‌کند صبر کند؛ PostgreSQL قفل سطح جدول و سطح ردیف دارد."
category = "Databases"
fa_title = "قفل"
related = ["deadlock", "skip-locked", "advisory-lock"]
posts = ["db-locks-deadlocks"]
+++

بعضی عملیات نباید هم‌زمان اجرا شوند. قفل باعث می‌شود session دوم صبر کند (یا زود خطا بگیرد) تا اولی commit یا rollback کند. در PostgreSQL قفل‌ها تا پایان [تراکنش](/fa/glossary/transaction/) نگه داشته می‌شوند و چرخه‌ای از انتظارها به [deadlock](/fa/glossary/deadlock/) می‌رسد.
