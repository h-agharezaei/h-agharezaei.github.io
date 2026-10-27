+++
title = "PITR"
summary = "بازیابی به لحظه‌ی دلخواه: یک base backup را restore می‌کنید و WAL آرشیوشده را تا لحظه‌ی مورد نظر replay می‌کنید."
category = "Databases"
fa_title = "PITR"
related = ["wal", "logical-backup"]
posts = ["db-backup-restore-pitr"]
+++

یک base backup و همه‌ی segmentهای WAL بعد از آن لازم است. target می‌تواند زمان، یک restore point نام‌دار (با `pg_create_restore_point`)، یک LSN یا شناسه‌ی تراکنش باشد. این ابزار برای برگرداندن یک `DELETE` اشتباه است، کاری که replica نمی‌تواند.
