+++
title = "Bitcoin Script"
summary = "زبان کوچک و stack-محور بیت‌کوین: هر خروجی یک اسکریپت قفل دارد و خرج‌کننده داده‌ی باز کردنش را می‌دهد."
category = "Blockchain"
fa_title = "Bitcoin Script"
related = ["utxo", "p2pkh", "stack", "turing-complete"]
posts = ["bc-bitcoin-script-rust"]
+++

نود داده‌ی باز کردن و بعد اسکریپت قفل (`scriptPubKey`) را روی یک [stack](/fa/glossary/stack/) اجرا می‌کند؛ خروجی فقط وقتی خرج می‌شود که نتیجه true باشد. طبق ویکی بیت‌کوین حلقه ندارد، پس [Turing-complete](/fa/glossary/turing-complete/) نیست. قفل کلاسیک آن [P2PKH](/fa/glossary/p2pkh/) است.
