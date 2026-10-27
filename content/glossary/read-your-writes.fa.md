+++
title = "Read-your-writes"
summary = "بعد از این‌که client مقداری می‌نویسد، readهای بعدی خودش همان مقدار یا جدیدتر را می‌بینند."
category = "Distributed"
fa_title = "read-your-writes"
related = ["monotonic-reads","linearizability"]
posts = ["ds-consistency-models"]
+++

یک تضمین در سطح session. راه‌حل رایج یک session token است که نسخه‌ی آخرین write را نگه می‌دارد؛ replicaی که عقب‌تر است کنار گذاشته می‌شود و read به leader می‌رود.
