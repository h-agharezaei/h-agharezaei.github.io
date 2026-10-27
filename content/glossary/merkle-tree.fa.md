+++
title = "Merkle tree"
summary = "درختی از hashها که هر والد hash فرزندانش است؛ پس root برابر یعنی داده برابر."
category = "Distributed"
fa_title = "Merkle tree"
related = ["anti-entropy"]
posts = ["ds-replication-quorum"]
+++

برای یافتن تفاوت، rootها را مقایسه می‌کنید و فقط در زیردرخت‌هایی که hash‌شان فرق دارد پایین می‌روید. اگر تفاوت کم باشد چند گره را مقایسه می‌کنید نه همه‌ی کلیدها را.
