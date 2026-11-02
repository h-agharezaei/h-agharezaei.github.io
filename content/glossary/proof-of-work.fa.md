+++
title = "Proof of work"
summary = "بلاک فقط وقتی معتبر است که hash header آن از یک target کمتر باشد؛ ساختنش هش‌های زیاد می‌خواهد و چک کردنش یک hash."
category = "Blockchain"
fa_title = "proof of work"
related = ["mining", "difficulty-target", "chainwork", "sybil-attack", "consensus"]
posts = ["bc-proof-of-work-mining", "bc-p2p-gossip"]
+++

proof of work تولید بلاک را به قرعه‌کشی‌ای تبدیل می‌کند که وزنش محاسبه است. ماینرها nonce را عوض می‌کنند تا hash header به [target سختی](/fa/glossary/difficulty-target/) برسد؛ هر نود نتیجه را با یک hash چک می‌کند. بازنویسی تاریخچه یعنی انجام دوباره‌ی همه‌ی کار از آن نقطه به بعد.
