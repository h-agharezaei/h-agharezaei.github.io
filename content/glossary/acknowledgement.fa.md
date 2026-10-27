+++
title = "Acknowledgement (ack)"
summary = "پاسخ consumer به JetStream: ack (تمام شد)، nak (دوباره بفرست)، term (دیگر نفرست)."
category = "Messaging"
fa_title = "تأیید دریافت (ack)"
related = ["jetstream", "durable-consumer"]
posts = ["node-nats-jetstream"]
+++

با ack صریح، سرور پیام را تا پاسخ consumer «در انتظار» نگه می‌دارد. `ack` یعنی کار تمام شد، `nak` درخواست ارسال دوباره است (اختیاراً با تأخیر) و `term` به سرور می‌گوید دیگر این پیام را نفرستد.
