+++
title = "Stream"
summary = "شیئی که داده را تکه‌تکه جابه‌جا می‌کند تا برنامه لازم نباشد همه‌ی آن را در حافظه نگه دارد."
category = "Node.js"
fa_title = "استریم"
related = ["backpressure", "high-water-mark", "event-loop"]
posts = ["node-streams-backpressure"]
+++

stream منبع یا مقصد داده‌ای است که تکه‌تکه پردازش می‌شود. Node.js چهار نوع دارد: Readable، Writable، Duplex و Transform. streamها با `pipeline` به هم وصل می‌شوند و مصرف‌کننده‌ی کند با [backpressure](/fa/glossary/backpressure/) محافظت می‌شود.
