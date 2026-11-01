+++
title = "Inclusion proof"
summary = "hashهای هم‌سطح روی مسیر یک برگ تا root که ثابت می‌کند آن برگ در Merkle tree هست."
category = "Blockchain"
fa_title = "اثبات عضویت"
related = ["merkle-tree", "merkle-root", "spv"]
posts = ["bc-merkle-trees-proofs"]
+++

verifier از برگ به بالا دوباره hash می‌کند و نتیجه را با rootی که از قبل به آن اعتماد دارد مقایسه می‌کند. اثبات حدود log2(n) hash دارد: ۲۰ تا برای یک میلیون برگ.
