+++
title = "TOCTOU"
summary = "Time-of-check to time-of-use: وضعیت بین بررسی و عملی که به آن تکیه دارد عوض می‌شود."
category = "Security"
fa_title = "TOCTOU"
related = ["race-condition", "dns-rebinding"]
posts = ["sec-ssrf-deserialization"]
+++

شرطی را بررسی می‌کنید و بعداً عمل می‌کنید، اما چیز دیگری می‌تواند وسط راه آن را عوض کند. راه‌حل این است که بررسی و استفاده یک گام اتمیک باشند یا روی همان چیزی که بررسی کردید عمل کنید. نگاه کنید به [race condition](/fa/glossary/race-condition/).
