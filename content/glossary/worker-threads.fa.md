+++
title = "Worker threads"
summary = "threads داخل یک process در Node، با event loop و heap جدا، برای کار CPU-bound."
category = "Node.js"
fa_title = "رشته‌ی کارگر"
related = ["event-loop", "worker-pool", "shared-array-buffer"]
posts = ["node-worker-threads-cluster"]
+++

ماژول `worker_threads` در Node چند thread اضافه در همان process می‌سازد. هر کدام event loop و حافظه‌ی خودش را دارد؛ داده با کپی از راه `postMessage`، با انتقال یا با [SharedArrayBuffer](/fa/glossary/shared-array-buffer/) جابه‌جا می‌شود.
