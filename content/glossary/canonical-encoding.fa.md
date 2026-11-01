+++
title = "Canonical encoding"
summary = "قاعده‌ی serialize که برای هر مقدار دقیقاً یک دنباله‌ی بایت می‌دهد، تا همه همان بایت‌ها را hash کنند."
category = "Blockchain"
fa_title = "encoding یکتا"
related = ["block-header", "sha-256"]
posts = ["bc-hashes-blocks-chain"]
+++

خروجی پیش‌فرض JSON یکتا نیست: ترتیب کلید، فاصله، escape و فرمت عدد بین کتاب‌خانه‌ها فرق می‌کند. فیلدهای با طول ثابت و ترتیب ثابت، یا پیشوند طول برای فیلدهای متغیر، این مشکل را ندارند.
