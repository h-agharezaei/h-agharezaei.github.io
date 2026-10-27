+++
title = "Read repair"
summary = "هنگامی که خواندن متوجه replicaی با نسخه‌ی قدیمی می‌شود، نسخه‌ی جدید را همان لحظه روی آن می‌نویسد."
category = "Distributed"
fa_title = "read repair"
related = ["anti-entropy", "quorum"]
posts = ["ds-replication-quorum"]
+++

روشی ارزان برای ترمیم replicaها با ترافیکی که از قبل هست. کلیدهایی که هرگز خوانده نشوند قدیمی می‌مانند، پس کنار آن به [anti-entropy](/fa/glossary/anti-entropy/) نیاز است.
