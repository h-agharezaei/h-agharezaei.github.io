+++
title = "Monotonic clock"
summary = "ساعتی که فقط جلو می‌رود و برای اندازه‌گیری مدت‌زمان است، نه گفتن تاریخ."
category = "Distributed"
fa_title = "ساعت یکنوا"
related = ["clock-skew"]
posts = ["ds-why-distributed-is-hard"]
+++

ساعت دیواری هنگام تصحیح می‌تواند بپرد و تفریق دو زمان دیواری حتی منفی شود. در Go مقدار `time.Now()` یک قرائت یکنوا هم دارد و `Sub` در صورت وجود آن را به کار می‌برد.
