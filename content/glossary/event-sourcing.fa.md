+++
title = "Event sourcing"
fa_title = "رویدادمحوری ذخیره‌سازی (event sourcing)"
summary = "وضعیت ذخیره نمی‌شود؛ فهرست append-only رویدادهایی که به آن رسیده‌اند ذخیره می‌شود و وضعیت فعلی fold آن‌هاست."
category = "Distributed"
related = ["cqrs", "event-snapshot", "upcasting"]
posts = ["ds-cqrs-event-sourcing"]
+++

حساب یک سطر با موجودی نیست، بلکه رویدادهای Opened و Deposited و Withdrawn است. command قواعد را روی وضعیت fold‌شده بررسی و رویداد جدید صادر می‌کند؛ چیزی درجا ویرایش نمی‌شود.
