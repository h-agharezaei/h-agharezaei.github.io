+++
title = "xpub"
summary = "کلید عمومی توسعه‌یافته: کلید عمومی به‌همراه chain code، که برای ساختن همه‌ی کلیدهای عمومی فرزندِ غیر hardened کافی است."
category = "Blockchain"
fa_title = "xpub"
related = ["bip-32", "hardened-derivation", "hd-wallet"]
posts = ["bc-hd-wallets-rust", "bc-exchange-deposits-withdrawals", "bc-capstone"]
+++

یک سرور فقط‌نظارتی می‌تواند با xpub آدرس واریز تازه بسازد بی‌آن‌که کلید خصوصی داشته باشد. با این حال حساس است: همه‌ی آن آدرس‌ها را به هم وصل می‌کند و اگر کلید خصوصی یکی از فرزندهای غیر [hardened](/fa/glossary/hardened-derivation/) لو برود، کلید خصوصی والد را لو می‌دهد.
