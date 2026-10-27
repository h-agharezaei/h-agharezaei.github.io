+++
title = "AckWait"
summary = "مدتی که JetStream منتظر ack می‌ماند، قبل از اینکه پیام را دوباره بفرستد."
category = "Messaging"
fa_title = "AckWait"
related = ["jetstream", "durable-consumer"]
posts = ["node-nats-jetstream"]
+++

اگر consumer در مدت AckWait چیزی ack، nak یا term نکند، سرور پیام را دوباره می‌فرستد، تا سقف `max_deliver`. فهرست `backoff` می‌تواند این یک مقدار را با تأخیرهای افزایشی جایگزین کند.
