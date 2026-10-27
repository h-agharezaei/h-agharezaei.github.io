+++
title = "Rolling update"
summary = "استقراری که instanceها را یکی‌یکی عوض می‌کند."
category = "Distributed"
fa_title = "روش rolling"
related = ["blue-green-deployment", "canary-release", "health-check"]
posts = ["ds-deployment-strategies"]
+++

در rolling update نسخه‌ی قدیمی instance به instance عوض می‌شود و معمولاً پیش از ادامه منتظر readiness check می‌ماند. در طول اجرا نسخه‌ی قدیم و جدید هم‌زمان ترافیک می‌گیرند.
