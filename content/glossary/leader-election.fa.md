+++
title = "Leader election"
summary = "انتخاب یک node برای هماهنگی در یک بازه؛ در Raft یک candidate در یک term تازه به رأی اکثریت نیاز دارد."
category = "Distributed"
fa_title = "leader election (انتخاب رهبر)"
related = ["raft", "quorum"]
posts = ["ds-consensus-raft"]
+++

followerهایی که heartbeat نمی‌شنوند در لحظه‌های تصادفی timeout می‌شوند، پس معمولاً یک candidate زودتر شروع می‌کند و برنده می‌شود.
