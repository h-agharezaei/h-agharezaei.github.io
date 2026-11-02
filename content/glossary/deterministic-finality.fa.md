+++
title = "Deterministic finality"
summary = "بلاک به محض اینکه validatorهایی با بیش از دو سوم stake commit آن را امضا کنند قطعی است و بدون امضای متناقض یک سوم stake برنمی‌گردد."
category = "Blockchain"
fa_title = "finality قطعی"
related = ["probabilistic-finality", "quorum", "equivocation"]
posts = ["bc-proof-of-stake-bft"]
+++

نقطه‌ی مقابل [finality احتمالی](/fa/glossary/probabilistic-finality/) در proof of work است که در آن confirmation بیشتر فقط ریسک را کم می‌کند. اگر شبکه دوپاره شود، پروتکل‌های BFT به‌جای ساختن دو تاریخچه commit را متوقف می‌کنند.
