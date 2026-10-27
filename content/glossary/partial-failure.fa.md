+++
title = "Partial failure"
summary = "وقتی یک بخش سیستم خراب می‌شود و بقیه کار می‌کنند، فراخواننده نمی‌داند چه شده."
category = "Distributed"
fa_title = "خرابی جزئی"
related = ["failure-detector", "gray-failure", "idempotency"]
posts = ["ds-why-distributed-is-hard"]
+++

در سیستم توزیع‌شده یک فراخوانی ممکن است در درخواست، در سرور یا در پاسخ شکست بخورد. timeout در هر سه حالت یکسان دیده می‌شود، پس فراخواننده نمی‌داند عملیات اعمال شده یا نه.
