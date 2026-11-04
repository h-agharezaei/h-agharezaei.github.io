+++
title = "Publish-subscribe"
summary = "سبکی از پیام‌رسانی که در آن ناشر پیام را به یک subject نام‌دار می‌فرستد و هر مشترکِ آن subject نسخه‌ی خودش را می‌گیرد."
category = "Distributed"
fa_title = "publish-subscribe"
related = ["queue-group", "event-envelope"]
posts = ["ds-messaging-event-driven"]
+++

ناشر نمی‌داند چه کسی گوش می‌دهد و مشترک نمی‌داند چه کسی منتشر کرده است. اگر سه مشترک روی یک subject گوش بدهند، هرکدام همه‌ی پیام‌ها را می‌گیرد. این را با [queue group](/fa/glossary/queue-group/) مقایسه کنید که در آن اعضا پیام‌ها را بین خودشان تقسیم می‌کنند.
