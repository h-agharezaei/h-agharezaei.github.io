+++
title = "Consensus"
summary = "رسیدن گروهی از node‌ها به توافق روی یک مقدار (یا یک log مرتب) با وجود crash برخی node‌ها یا گم شدن پیام‌ها."
category = "Distributed"
fa_title = "اجماع (consensus)"
related = ["quorum", "raft"]
posts = ["ds-consensus-raft"]
+++

Raft و Paxos الگوریتم‌های consensus هستند. به زنده بودن اکثریت node‌ها نیاز دارند و برای همین خوشه‌ی 2f+1 تایی f خرابی را تحمل می‌کند.
