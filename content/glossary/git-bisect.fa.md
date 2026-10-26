+++
title = "git bisect"
summary = "ابزار Git که با جست‌وجوی دودویی در تاریخچه، اولین commit خراب‌کننده را پیدا می‌کند."
category = "Git"
fa_title = "git bisect"
related = ["binary-search", "regression", "atomic-commit"]
posts = ["git-bisect"]
+++

`git bisect` یک commit سالم و یک commit خراب را می‌گیرد و commit وسط را checkout می‌کند و از شما (یا یک اسکریپت) می‌پرسد سالم است یا خراب. هر جواب بازه را نصف می‌کند، پس حدود log2(N) تست برای پیدا کردن مقصر کافی است. [binary search](/fa/glossary/binary-search/) و [regression](/fa/glossary/regression/) را ببینید.
