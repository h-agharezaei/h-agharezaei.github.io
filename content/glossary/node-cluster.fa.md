+++
title = "Node cluster"
summary = "ماژول `cluster`: چند process از Node که یک port را به اشتراک می‌گذارند."
category = "Node.js"
fa_title = "cluster در Node"
related = ["worker-threads", "event-loop"]
posts = ["node-worker-threads-cluster"]
+++

ماژول `cluster` به process اصلی اجازه می‌دهد workerهایی fork کند که همه روی یک port اتصال می‌پذیرند. حافظه مشترک ندارند. primary تصمیم می‌گیرد اتصال‌ها چطور پخش شوند و با مرگ یک worker چه شود.
