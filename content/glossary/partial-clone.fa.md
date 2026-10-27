+++
title = "Partial clone"
summary = "clone بدون بعضی objectها که در صورت نیاز گرفته می‌شوند."
category = "Git"
fa_title = "clone جزئی"
related = ["sparse-checkout", "shallow-clone"]
posts = ["git-workflows-packfiles", "eng-monorepo-vs-polyrepo"]
+++

با `--filter=blob:none` تاریخچه‌ی کامل commitها می‌ماند ولی محتوای فایل‌ها فقط در صورت نیاز از یک promisor remote که filter را اجازه می‌دهد گرفته می‌شود. آفلاین، نبودنِ blob خطاست. معمولاً با [sparse checkout](/fa/glossary/sparse-checkout/) ترکیب می‌شود.
