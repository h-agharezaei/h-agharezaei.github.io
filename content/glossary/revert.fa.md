+++
title = "Revert"
fa_title = "revert"
summary = "متوقف کردن یک فراخوانی EVM و برگرداندن همه‌ی تغییرات state آن، همراه داده‌ی خطای اختیاری."
category = "Blockchain"
related = ["gas", "evm", "solidity"]
posts = ["bc-solidity-first-contract"]
+++

در Solidity دستور `revert CustomError(args)` یا یک `require` ناموفق revert می‌کند. تراکنش revertشده باز هم در بلاک می‌آید و فرستنده هزینه‌ی [gas](/fa/glossary/gas/) مصرفی را می‌دهد؛ فقط تغییرات state حذف می‌شوند.
