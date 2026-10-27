+++
title = "Monotonic reads"
summary = "readهای پشت‌سرهم یک client هرگز به مقدار قدیمی‌تر برنمی‌گردند."
category = "Distributed"
fa_title = "monotonic reads"
related = ["read-your-writes","eventual-consistency"]
posts = ["ds-consistency-models"]
+++

وقتی readهای متوالی به replicaهایی با lag متفاوت بخورند می‌تواند نقض شود. وصل‌کردن client به یک replica یا session token جلوی آن را می‌گیرد.
