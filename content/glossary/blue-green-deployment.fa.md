+++
title = "استقرار blue/green"
summary = "دو نسخه‌ی یکسان کنار هم؛ ترافیک فقط وقتی نسخه‌ی جدید سالم بود از نسخه‌ی زنده به آن منتقل می‌شود."
category = "Engineering"
fa_title = "استقرار blue/green"
related = ["rollback", "health-check", "canary-release"]
posts = ["eng-ci-cd-pipeline-design", "ds-deployment-strategies"]
+++

سوییچ یک گام ارزان است (یک symlink یا هدف load balancer)، پس برگشت همان گام در جهت عکس است. هزینه‌اش اجرای دو نسخه و پایگاه داده‌ای است که هر دو نسخه بتوانند با آن کار کنند.
