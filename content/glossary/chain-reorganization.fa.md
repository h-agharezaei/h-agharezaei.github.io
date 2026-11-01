+++
title = "Chain reorganization (reorg)"
summary = "عوض کردن زنجیره‌ی فعال با شاخه‌ی سنگین‌تر: جدا کردن بلاک‌ها تا جد مشترک و وصل کردن بلاک‌های تازه."
category = "Blockchain"
fa_title = "reorg (بازآرایی زنجیره)"
related = ["fork-choice-rule", "stale-block", "probabilistic-finality"]
posts = ["bc-forks-reorgs"]
+++

جدا کردن بلاک برای برگرداندن state به داده‌ی undo (یا replay) نیاز دارد. تراکنش‌های بلاک‌های جداشده که در شاخه‌ی تازه نیستند دوباره تأییدنشده می‌شوند؛ بعضی شاید حالا نامعتبر باشند چون شاخه‌ی تازه همان خروجی‌ها را خرج کرده.
