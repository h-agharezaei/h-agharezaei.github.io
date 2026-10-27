+++
date = '2027-04-29T10:00:00+03:30'
draft = false
title = 'ساعت منطقی: Lamport و vector clock'
description = 'ساعت منطقی با Go: Lamport و vector clock در برابر ترتیب واقعی happens-before روی ۵۰۰۰ اجرای شبیه‌سازی‌شده، و تشخیص تعارض در نوشتن.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "logical-clocks", "lamport", "vector-clock", "go"]
cover = { image = "/images/covers/ds-logical-clocks.fa.png", alt = "ساعت منطقی: Lamport و vector clock", hiddenInSingle = true }
+++

مقاله‌ی قبل، [مدل‌های consistency](/fa/posts/ds-consistency-models/)، یک وعده را باز گذاشت: causal consistency راهی می‌خواهد که بدون اعتماد به ساعت بگوید «این قبل از آن رخ داد». این مقاله آن ابزار را می‌سازد. به بحث skew در [چرا سیستم توزیع‌شده سخت است](/fa/posts/ds-why-distributed-is-hard/) و هشدار last-write-wins در [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/) تکیه دارد.

> صادقانه: همه‌چیز Go 1.26 در یک process است. «processها» و تأخیر پیام‌ها **شبیه‌سازی** هستند، با تصادف seed‌دار (پیام‌ها تصادفی از میان پیام‌های در راه انتخاب می‌شوند، پس جابه‌جا می‌شوند). شبکه نیست. عددها تعدادند، نه زمان. تست‌ها با `go test -race` اجرا شده‌اند.

## چرا ساعت دیواری شکست می‌خورد

به هر process شبیه‌سازی‌شده یک ساعت دیواری با offset ثابت بدهید (۰، ۴- و ۳+ tick؛ اعداد ساخته‌ی خودم برای مدل کردن {{< term "clock-skew" "clock skew" >}}) و روی هر رویداد مهر بزنید. در ۵۰۰۰ اجرا، **۳۵۳۷** اجرا پیامی داشت که timestamp دریافتش دیرتر از ارسال خودش نبود، یعنی معلول قبل از علتش مهر خورده بود. offsetها ساخته‌ی من‌اند، ولی نکته می‌ماند: ترتیب timestampها ترتیب علت‌ها نیست.

## happens-before دقیقاً

{{< term "happens-before" "Happens-before" >}} (a → b) با سه قاعده تعریف می‌شود: رویدادهای یک process به ترتیب برنامه‌اند؛ send قبل از receive خودش است؛ و رابطه متعدی است. اگر نه a → b باشد نه b → a، رویدادها **هم‌زمان**‌اند (concurrent). ground truth من فقط از log ثبت‌شده و با بستن همین یال‌ها محاسبه می‌شود، بدون نگاه به هیچ ساعتی.

## ساعت Lamport

{{< term "lamport-clock" "ساعت Lamport" >}} یک عدد برای هر process است: با هر رویداد یکی زیاد کن، و هنگام receive بیشینه‌ی مقدار خودت و مقدار پیام را بگیر و یکی اضافه کن. در شبیه‌ساز:

```go
lam[p]++                              // local or send
lam[p] = max(lam[p], m.lam) + 1       // receive
```

یک trace واقعی (seed 2، ۱۰ رویداد؛ `from` همان sendی است که `R` دریافت کرده):

```
id proc kind  lamport  vector   from
 0  P0   L       1    [1 0 0]  -1
 1  P1   S       1    [0 1 0]  -1
 2  P1   S       2    [0 2 0]  -1
 3  P1   L       3    [0 3 0]  -1
 4  P1   S       4    [0 4 0]  -1
 5  P2   R       5    [0 4 1]  4
 6  P0   L       2    [2 0 0]  -1
 7  P0   R       3    [3 1 0]  1
 8  P0   R       4    [4 2 0]  2
 9  P0   L       5    [5 2 0]  -1
```

نتیجه روی ۵۰۰۰ اجرای تصادفی (۲٬۷۶۰٬۰۰۰ جفت مرتب از رویدادها):

```
happens-before pairs: 685631, concurrent pairs: 1388738
lamport: a->b but L(a)>=L(b): 0
lamport: concurrent but L(a)<L(b): 608758, L equal: 171222
```

پس a → b یعنی L(a) < L(b)، با صفر نقض. عکسش غلط است: ۶۰۸٬۷۵۸ جفت هم‌زمان باز هم L(a) < L(b) دارند. در trace، رویدادهای ۰ و ۲ هم‌زمان‌اند، ولی L آن‌ها ۱ و ۲ است. timestamp Lamport نمی‌تواند هم‌زمانی را تشخیص دهد. شکستن تساوی با شناسه‌ی process (مقایسه‌ی `(L, pid)`) یک ترتیب **کلی** سازگار با علّیت می‌دهد، مثلاً برای صف lock مفید است، ولی بین رویدادهای هم‌زمان ترتیبی می‌سازد که وجود ندارد.

## vector clock

{{< term "vector-clock" "vector clock" >}} برای هر process یک شمارنده نگه می‌دارد. خانه‌ی خودت را با هر رویداد زیاد کن؛ هنگام receive بیشینه‌ی عنصر به عنصر بگیر و خانه‌ی خودت را زیاد کن. مقایسه‌ی دو vector:

```go
case less && greater: return Concurrent
case less:            return Before
case greater:         return After
```

(`less` یعنی یک خانه کوچک‌تر است و `greater` یعنی یک خانه بزرگ‌تر.) در trace، رویداد ۰ با `[1 0 0]` و رویداد ۲ با `[0 2 0]`: هم‌زمان. برای هر ۲٬۷۶۰٬۰۰۰ جفت assert کردم که `Compare` دقیقاً با ground truth برابر است: **صفر اختلاف**. هزینه‌اش یک vector با N شمارنده در هر پیام است. dotted version vector و interval tree clock این رشد را کم می‌کنند؛ فقط نامشان را می‌آورم و پیاده نکردم.

## تشخیص writeهای متعارض

دو replica از یک key، ۱۰ گام تصادفی (put روی یک replica یا pull یکی از دیگری)، روی همان ۱۰۰۰ workload با seed ثابت (۹۹۸ تا write داشتند). هر put یک vector حمل می‌کند و مقدار pullشده فقط نسخه‌هایی را کنار می‌گذارد که بر آن‌ها غلبه دارد؛ این یک {{< term "version-vector" "version vector" >}} برای هر مقدار است. {{< term "last-write-wins" "Last write wins" >}} بزرگ‌ترین timestamp دیواری را نگه می‌دارد (ساعت replica شماره‌ی ۱ پنج tick عقب است، باز هم ساختگی). یک اجرا:

```
write a v=[1 0] wall=4
write b v=[2 0] wall=5
write c v=[2 1] wall=2
write d v=[3 0] wall=8
version vectors keep: d[3 0] c[2 1]
last-write-wins keeps: d
```

c و d هم‌زمان‌اند. روی کل workloadها:

```
with a conflict 499, writes LWW dropped silently 499,
LWW winner was not a latest write 92, version vectors lost 0
```

version vectorها هیچ writeی را از دست ندادند (یک تست آن را assert می‌کند) و هر دو sibling را برای ادغام به برنامه می‌دهند. LWW بی‌صدا ۴۹۹ write را دور ریخت، و در ۹۲ اجرا برنده writeی بود که writeی جدیدتر قبلاً جایش را گرفته بود.

## hybrid logical clock

{{< term "hybrid-logical-clock" "Hybrid logical clockها" >}} زمان فیزیکی را با یک شمارنده‌ی منطقی ترکیب می‌کنند، تا timestamp نزدیک به زمان واقعی بماند و علّیت را هم رعایت کند. یکی را اجرا نکردم؛ بر اساس آنچه از طراحی منتشرشده می‌دانم، سازشی است که بعضی دیتابیس‌ها به کار می‌برند.

## چند نکته‌ی مهم

- ترتیب Lamport با علّیت سازگار است، نه برابر آن.
- اندازه‌ی vector با تعداد شرکت‌کننده‌ها بزرگ می‌شود؛ در storeهای با clientهای زیاد معمولاً به ازای replica ردیابی می‌کنند.
- تشخیص تعارض آن را حل نمی‌کند؛ کسی باید ادغام کند.
- به تجربه‌ی من LWW با ساعت دیواری برای cache خوب است و برای هر چیزی که نباید گم شود غلط.

## تمرین

یک process چهارم اضافه کنید و ببینید نتیجه‌ی صفر اختلاف حفظ می‌شود. بعد `Put` را طوری عوض کنید که siblingها را ادغام نکند و ببینید چند sibling روی هم جمع می‌شود.

## قدم بعدی

مقاله‌ی بعد «timeout، retry و backoff با jitter» است.
