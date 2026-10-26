+++
title = "Durable consumer"
summary = "یک consumer نام‌دار در JetStream که جایگاهش بعد از restart و اتصال مجدد حفظ می‌شود."
category = "Messaging"
fa_title = "کانسیومر ماندگار"
related = ["jetstream", "idempotency"]
posts = ["nats-jetstream-go", "nats-jetstream-scaling-lag"]
+++

چون سرور به خاطر دارد کدام پیام‌ها ack شده‌اند، durable consumer دقیقاً از جایی که ایستاده ادامه می‌دهد. چند instance می‌توانند یک نام durable مشترک داشته باشند و کار را بینشان تقسیم کنند؛ راه مقیاس‌پذیری افقی همین است.
