+++
title = "Byzantine fault"
summary = "خطایی که در آن node فقط از کار نمی‌افتد، بلکه دلخواه رفتار می‌کند: دروغ می‌گوید، به هر peer جواب متفاوتی می‌دهد یا عمداً خرابکاری می‌کند."
category = "Blockchain"
fa_title = "Byzantine fault (خطای بیزانسی)"
related = ["consensus", "distributed-ledger"]
posts = ["bc-blockchain-for-programmers", "bc-proof-of-stake-bft"]
+++

پروتکل‌های crash-fault مثل Raft فرض می‌کنند nodeها صادق‌اند ولی ممکن است متوقف شوند. پروتکل‌های Byzantine fault tolerant (BFT) حتی وقتی بخشی از شرکت‌کننده‌ها نادرست‌اند کار می‌کنند؛ همان شرایطی که بلاکچین‌های عمومی برایش طراحی شده‌اند. هزینه‌اش پیام بیشتر است و در BFT کلاسیک بیش از دو سوم nodeها باید صادق باشند.
