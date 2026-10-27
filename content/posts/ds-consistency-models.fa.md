+++
date = '2027-04-25T10:00:00+03:30'
draft = false
title = 'مدل‌های consistency'
description = 'مدل‌های consistency با یک history checker به Go: linearizable، sequential، read-your-writes و monotonic reads، روی ۱۰۰۰ history شبیه‌سازی‌شده.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consistency", "linearizability", "go", "replication"]
cover = { image = "/images/covers/ds-consistency-models.fa.png", alt = "مدل‌های consistency", hiddenInSingle = true }
+++

«consistent» کلمه‌ای است که در design reviewها از همه بیشتر غلط به کار برده‌ام. مقاله‌ی قبل، [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/)، نشان داد C در CAP یک معنی مشخص دارد. این مقاله درباره‌ی کل پلکان وعده‌هایی است که یک store می‌تواند بدهد، و درباره‌ی این‌که به‌جای بحث، یک وعده را **بررسی** کنیم. روی [چرا سیستم توزیع‌شده سخت است](/fa/posts/ds-why-distributed-is-hard/) و [replication lag در Postgres](/fa/posts/db-replication-streaming/) بنا شده است.

> صادقانه: همه‌چیز کد Go 1.26 در یک process است. leader و followerها **شبیه‌سازی** هستند، با تصادف seed‌دار و tickهای گسسته، نه شبکه. عددها تعداد history هستند، نه زمان. خود checker واقعی است و با `go test -race` تست شده.

## history و یک register

history فهرستی از عملیات روی یک register است (مقدار اولیه ۰): client، read یا write، مقدار، و زمان شروع و برگشت. مقدار writeها به ترتیب اعمال در leader زیاد می‌شود، پس مقدار بزرگ‌تر یعنی نسخه‌ی جدیدتر.

بررسی {{< term "linearizability" "linearizability" >}} یک جست‌وجوی brute-force به سبک Wing و Gong است: عملیاتی را انتخاب کن که هیچ عملیات باقی‌مانده‌ای قبل از شروعش تمام نشده، آن را روی register اعمال کن (read باید مقدار فعلی را برگرداند) و ادامه بده. نمایی است و برای حدود ده عملیات کافی. بررسی {{< term "sequential-consistency" "sequential consistency" >}} دنبال هر ترتیبی می‌گردد که ترتیب هر client را حفظ کند و زمان واقعی را نادیده بگیرد. {{< term "read-your-writes" "read-your-writes" >}} و {{< term "monotonic-reads" "monotonic reads" >}} فقط پیمایش ساده‌ی هر client هستند.

## شش history نام‌دار

زمان به راست می‌رود؛ `[` و `]` شروع و برگشت‌اند.

```
B  C1 W1 [------]
   C2   W2 [------]
   C3              R=1 [-]
   C4                      R=2 [-]

C  C1 W1 [--]
   C2          R=0 [-]          (starts after W1 returned)

E  C1 W1 [-]
   C3      W2 [-]
   C2            R=2 [-]  R=1 [-]
```

حکم checker من (تست‌ها دقیقاً همین جدول را assert می‌کنند):

```
history                                linearizable sequential   RYW   MR
A concurrent writes, reads agree       yes          yes          yes   yes
B concurrent writes, reads disagree    NO           yes          yes   yes
C stale read after write returned      NO           yes          yes   yes
D own write not visible                NO           NO           NO    yes
E value goes backwards                 NO           yes          yes   NO
F plain write then read                yes          yes          yes   yes
```

B: هر دو write قبل از readها تمام شده‌اند، پس دو reader نباید روی آخرین مقدار اختلاف داشته باشند؛ ولی اگر زمان واقعی نادیده گرفته شود، W1، R1، W2، R2 ترتیب معتبری است. C همان stale read کلاسیک است. D حتی sequential consistency را می‌شکند، چون یک client با خودش تناقض دارد. E از نظر sequential معتبر است (readهای C2 بین دو write قرار می‌گیرند) ولی readهایش به عقب برمی‌گردند.

## پلکان قدرت

| مدل | یک خط |
|---|---|
| Linearizable | مثل یک نسخه رفتار می‌کند و زمان واقعی را رعایت می‌کند |
| Sequential | یک ترتیب سراسری، ترتیب هر client حفظ می‌شود، زمان واقعی نادیده است |
| {{< term "causal-consistency" "Causal" >}} | علت قبل از معلول دیده می‌شود، writeهای نامرتبط ممکن است فرق کنند |
| {{< term "eventual-consistency" "Eventual" >}} | اگر writeها متوقف شوند replicaها همگرا می‌شوند |

read-your-writes و monotonic reads تضمین‌های سطح session کنار این پلکان‌اند. causal به راهی برای ردیابی «happened before» نیاز دارد که مقاله‌ی بعد (آخر متن) می‌سازد. checker علّی پیاده نکردم.

## leader و follower عقب‌مانده

شبیه‌سازی: یک leader و دو follower. write به leader می‌رسد و leader آن را با lag تصادفی ۱ تا ۵ tick برای هر follower می‌فرستد و به ترتیب اعمال می‌شود. سه client هر کدام سه عملیات انجام می‌دهند (۴۰٪ write)، readها به یک follower تصادفی می‌روند و همان ۱۰۰۰ workload با seed ثابت در هر حالت اجرا می‌شود:

```
mode               not-linear      not-seq    RYW     MR   (violations out of 1000)
follower reads            388          148    221      3
own-write token           276            5      0      6
session token             271            0      0      0
```

readهای ساده از follower همه‌چیز را می‌شکنند. راه‌حل اول session token است: client نسخه‌ی آخرین write خودش را نگه می‌دارد و followerی که کمتر از آن اعمال کرده کنار گذاشته می‌شود، یعنی read به leader می‌رود. read-your-writes از ۲۲۱ به ۰ می‌رسد. monotonic reads (۳ به ۶) و نقض‌های sequential (۵) کامل از بین نمی‌روند، چون token چیزی را که client **خوانده** نمی‌بیند. اگر token بالاترین نسخه‌ی دیده‌شده باشد، چه خوانده چه نوشته، هر سه به ۰ می‌رسند.

ولی ۲۷۱ history هنوز linearizable نیستند. تضمین‌های session درباره‌ی writeهای **client‌های دیگر** چیزی نمی‌گویند و readهای follower برای آن‌ها می‌تواند کهنه باشد. خواندن فقط از leader در این مدل آن را حل می‌کند، به قیمت بار روی leader؛ و leader واقعی هم می‌تواند partition شود.

## سیستم‌های واقعی چه می‌کنند

اجرایشان نکردم، ولی checkerهای واقعی وجود دارند: Jepsen با Knossos، و Porcupine به Go، که history دیتابیس‌های واقعی را زیر خطا ثبت می‌کنند. به تجربه‌ی من بهترین عادت این است که برای هر مسیر read بپرسیم کدام ویژگی‌ها را قول می‌دهد و اگر به replica بخورد چه می‌شود. streamهای replicated در JetStream در [JetStream در production](/fa/posts/nats-jetstream-production/) آمده‌اند.

## چند نکته‌ی مهم

- eventual consistency درباره‌ی میزان کهنگی چیزی نمی‌گوید؛ lag را اندازه بگیرید.
- session token وقتی هیچ replicaی به‌اندازه‌ی کافی تازه نیست به fallback (leader) نیاز دارد.
- checker فقط درباره‌ی historyهایی که ثبت کرده‌اید چیزی ثابت می‌کند.
- «strongly consistent» در مستندات ممکن است linearizable باشد یا ضعیف‌تر؛ بپرسید کدام.

## تمرین

یک ویژگی سوم به checker اضافه کنید: «writes follow reads» (writeی بعد از یک read بعد از نسخه‌ی خوانده‌شده مرتب شود). بعد بازه‌ی lag را در `makePlans` عوض کنید و ببینید کدام عددها تکان می‌خورند.

## قدم بعدی

مقاله‌ی بعد «ساعت منطقی: Lamport و vector clock» است.
