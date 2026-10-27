+++
date = '2027-04-20T10:00:00+03:30'
draft = false
title = 'CAP و PACELC درست'
description = 'CAP و PACELC با شبیه‌سازی‌های Go با seed ثابت: CP رد می‌کند، AP جدا می‌شود و merge می‌شود، و replication همگام و ناهمگام تأخیر را با تازگی عوض می‌کند.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cap-theorem", "pacelc", "consistency", "go"]
cover = { image = "/images/covers/ds-cap-pacelc.fa.png", alt = "CAP و PACELC درست", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/ds-why-distributed-is-hard/) timeout یعنی «نامعلوم». CAP همان لحظه‌ای است که این نامعلوم آن‌قدر طول می‌کشد که باید تصمیم بگیرید چه کنید. «از سه تا دو تا را انتخاب کن» شعاری است که همه یادشان مانده و به نظر من بیشتر گمراه می‌کند تا یاد بدهد. اول دقیق بگویمش. پیش‌زمینه: [replication](/fa/posts/db-replication-streaming/) و [JetStream](/fa/posts/nats-jetstream-production/).

> صادقانه: همه‌ی این‌ها **شبیه‌سازی** هستند، در یک برنامه‌ی Go 1.26 (با seed ثابت و قطعی). زمان با «tick» ساختگی شمرده می‌شود و «شبکه» یک boolean و یک تأخیر است. شبکه‌ی واقعی نیست و زمانی گزارش نمی‌کنم.

## بیان دقیق

دو replica به نام A و B از یک register. یک {{< term "network-partition" "network partition" >}} (افتادن شبکه) در tickهای ۳۰ تا ۶۹ از ۱۰۰ ارتباطشان را قطع می‌کند. کلاینت‌ها روی A می‌نویسند و از B می‌خوانند.

در نتیجه‌ی صوری (گیلبرت و لینچ) حرف‌ها این‌اند:

- **C**: {{< term "linearizability" "linearizability" >}}، یعنی از دید کلاینت یک نسخه‌ی به‌روز.
- **A**: هر گره‌ی سالم به هر درخواست پاسخ می‌دهد.
- **P**: سیستم وقتی شبکه پیام‌های بین گره‌ها را گم می‌کند کار می‌کند.

شبکه‌ی واقعی partition می‌شود، پس P انتخاب نیست. بیان صادقانه: **هنگام partition باید از C یا A بگذری**، برای عملیاتی که کامل نمی‌شود. این همان {{< term "cap-theorem" "قضیه‌ی CAP" >}} است.

## ۱. CP: رد کردن

نوشتن به هر دو replica نیاز دارد ({{< term "quorum" "quorum" >}} برابر ۲ از ۲؛ سیستم‌های واقعی ۳ تا دارند تا یکی بتواند خراب شود). خواندن از B وقتی B نتواند به‌روز بودنش را تأیید کند رد می‌شود.

```
CP : writes=50 rejected=20 | reads=100 rejected=40 stale=0 | diverged=false final A=99 B=99
```

۲۰ نوشتن از ۵۰ و ۴۰ خواندن از ۱۰۰ رد شدند، ولی هیچ مقدار کهنه‌ای برنگشت و replicaها برابر ماندند.

## ۲. AP: پذیرفتن در هر دو سمت

حالا هر دو سمت می‌پذیرند. یک کلاینت هم روی B می‌نویسد (۴ نوشتن اضافه در طول partition). بیرون از partition، A با تأخیر ۲ tick به‌صورت ناهمگام به B می‌رساند.

```
AP : writes accepted=49 (rejected=0, concurrent on B=4)
     stale reads at B: in partition 26/40, outside 0/60
     before heal: A=69 B=1065 | after heal with LWW: A=89 B=89
```

چیزی رد نشد، ولی ۲۶ از ۴۰ خواندن در B کهنه بود و موقع heal دو replica مخالف بودند (۶۹ در برابر ۱۰۶۵). «کهنه» یعنی قدیمی‌تر از تازه‌ترین نوشتن تأییدشده، فراتر از تأخیر عادی ۲ tick. {{< term "last-write-wins" "Last write wins" >}} با stamp حل کرد و بی‌صدا نوشتن‌های B را دور ریخت.

سبد خرید lost update را بهتر نشان می‌دهد. دو سمت با `tea` شروع می‌کنند؛ A مقدار `book` و B مقدار `pen` اضافه می‌کند:

```
cart LWW  : [pen tea] (book was added and acknowledged, now gone)
cart union: [book pen tea]
```

union مجموعه‌ها یک {{< term "crdt" "CRDT" >}} کوچک است: merge به هر ترتیب و هر چند بار همان جواب را می‌دهد. برای عدد، G-counter برای هر گره یک خانه نگه می‌دارد، با بیشینه‌ی هر خانه merge می‌کند و مقدارش جمع خانه‌هاست. با seed برابر ۴۲، از ۱۰۰ شروع شد و A به‌اندازه‌ی ۸ و B به‌اندازه‌ی ۱۶ افزایش داد:

```
counter: +8 on A, +16 on B, expected 124 | LWW register 116 (lost 8) | G-counter 124
```

هزینه: G-counter فقط بالا می‌رود و union حذف ندارد؛ CRDT همگرایی را با محدود کردن بیان می‌خرد.

## CAP چه چیزی نمی‌گوید

| ادعای رایج | واقعیت |
|---|---|
| «هر دو تا را انتخاب کن» | P اجباری است؛ انتخاب بین C و A است و فقط هنگام partition |
| «سیستم CA وجود دارد» | یک گره توزیع‌شده نیست؛ سیستم شبکه‌ای نمی‌تواند از partition کنار بکشد |
| «AP یعنی همیشه ناسازگار» | بدون partition سیستم AP می‌تواند سازگار رفتار کند |
| «CAP درباره‌ی latency است» | نه؛ کند بودن partition نیست (PACELC را ببینید) |
| «سیستم یک بار برای همیشه CP یا AP است» | می‌تواند برای هر عملیات فرق کند |

## PACELC: ۹۹٪ بقیه‌ی زمان

{{< term "pacelc" "PACELC" >}} از دانیل آبادی حالت بدون partition را اضافه می‌کند: **اگر Partition، بین A و C؛ وگرنه بین Latency و Consistency.** همان دو replica، ولی لینک سالم با تأخیر یک‌طرفه‌ی seed‌دار بین ۲ تا ۴ tick. replication همگام (مثل {{< term "synchronous-commit" "synchronous commit" >}}) وقتی follower خودش ack بدهد ack می‌دهد؛ ناهمگام فوراً. ۴۵ نوشتن و ۱۰۰ خواندن از follower:

```
sync : writes=45 ack ticks mean=5.8 max=8 | follower reads=100 stale=0 max lag=0 writes
async: writes=45 ack ticks mean=0.0 max=0 | follower reads=100 stale=69 max lag=2 writes
```

tickها شبیه‌سازی‌اند. حالت sync برای هر نوشتن حدود ۶ tick داد و هیچ‌وقت خواندنی قدیمی‌تر از نوشتن تأییدشده برنگرداند. async فوراً ack داد، ولی ۶۹ خواندن از follower عقب‌تر از آخرین نوشتن تأییدشده بود. این معامله‌ی «وگرنه» است و در حالت سالم هم هست.

طبق مقاله‌ی قبلی خودم، streaming replication در PostgreSQL به‌طور پیش‌فرض ناهمگام است و می‌شود همگامش کرد. طبق مستندات، streamهای replicate شده‌ی JetStream مبتنی بر quorum هستند؛ این را توضیح دادم و اینجا cluster اجرا نکردم.

## چند نکته‌ی مهم

- بگویید «هنگام partition، C یا A»، هرگز «CA».
- قاعده‌ی merge را پیش از راه‌اندازی تعیین کنید.
- LWW راهی برای بی‌صدا از دست دادن داده است.

## تمرین

`PartFrom`/`PartTo` و تأخیر replication را عوض کنید. کدام شمارنده‌ها با partition رشد می‌کنند و کدام با تأخیر؟ بعد به سبد خرید حذف اضافه کنید و ببینید union با آن چه می‌کند.

## قدم بعدی

مقاله‌ی بعدی «مدل‌های consistency» است.
