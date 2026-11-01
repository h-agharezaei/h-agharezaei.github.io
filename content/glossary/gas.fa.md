+++
title = "Gas"
summary = "واحدی که EVM با آن کار را اندازه می‌گیرد: هر opcode هزینه‌ی gas دارد و فراخوانی‌ای که gas کم بیاورد متوقف و تغییراتش برگردانده می‌شود."
category = "Blockchain"
fa_title = "Gas"
related = ["evm", "opcode", "halting-problem"]
posts = ["bc-evm-internals-rust", "bc-solidity-first-contract"]
+++

فرستنده یک سقف gas تعیین می‌کند و بابت gas مصرف‌شده پول می‌دهد. چون هر قدم هزینه دارد، برنامه‌ی حلقه‌دار همیشه تمام می‌شود: یا کارش تمام می‌شود یا gas تمام می‌شود.
