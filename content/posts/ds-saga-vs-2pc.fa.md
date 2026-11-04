+++
date = '2027-05-23T10:00:00+03:30'
draft = false
title = 'saga یا 2PC؟'
description = 'saga یا commit دو فازی: شبیه‌سازی 2PC که block می‌شود، PREPARE TRANSACTION واقعی در Postgres و sagaهای سفارش با جبران که کامل بررسی شده‌اند.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "saga", "two-phase-commit", "transactions", "go", "postgres"]
cover = { image = "/images/covers/ds-saga-vs-2pc.fa.png", alt = "saga یا 2PC؟", hiddenInSingle = true }
+++

مشتری یک سفارش ثبت می‌کند. سه سرویس جدا باید کاری بکنند: موجودی باید رزرو شود، کارت باید شارژ شود و یک مرسوله باید ساخته شود. هر سرویس پایگاه‌داده‌ی خودش را دارد. دو مرحله‌ی اول موفق می‌شوند و سومی شکست می‌خورد، چون برای آن آدرس پیکی نیست. حالا از مشتری پول گرفته شده برای چیزی که هیچ‌وقت ارسال نمی‌شود، و یک قلم موجودی برای هیچ‌کس رزرو مانده.

داخل یک پایگاه‌داده این آسان است: سه مرحله را در یک تراکنش بگذارید و بگذارید rollback شود. اینجا یک پایگاه‌داده‌ی واحد نیست. log Raft در [مقاله‌ی قبل](/fa/posts/ds-consensus-raft/) روی ترتیب نوشتن‌ها برای یک گروه از node‌ها توافق می‌کند، ولی سه سرویس مستقل را پوشش نمی‌دهد. چیزی که می‌خواهیم هنوز **atomicity** است: یا هر سه مرحله انجام شود یا هیچ‌کدام. و می‌خواهیم بدانیم هر روش چه هزینه‌ای دارد.

دو جواب کلاسیک هست:

- {{< term "two-phase-commit" "commit دو فازی" >}} (2PC) atomicity را نگه می‌دارد. یک coordinator از هر سرویس می‌پرسد آماده است یا نه، و فقط اگر همه بگویند بله به همه می‌گوید commit کنید. بهایش این است که سرویس‌ها تا منتظرند lock نگه می‌دارند.
- {{< term "saga" "saga" >}} ایزولاسیون را کنار می‌گذارد. هر سرویس مرحله‌ی خودش را همان لحظه commit می‌کند. اگر مرحله‌ای بعدی شکست بخورد، مرحله‌های قبلی با کارهای تازه‌ای که آن‌ها را برعکس می‌کنند، به نام {{< term "compensating-transaction" "جبران" >}} (compensation)، مثل بازپرداخت، خنثی می‌شوند. بهایش این است که بقیه می‌توانند حالت‌های میانی را ببینند.

این مقاله هر دو را در شبیه‌سازی اجرا می‌کند، آجر اصلی 2PC را در PostgreSQL واقعی نشان می‌دهد، و بعد یک saga را در برابر crash بررسی می‌کند. برای پیش‌زمینه‌ی یک پایگاه‌داده‌ی واحد، [ACID](/fa/posts/db-transactions-acid/)؛ برای الگوهای مرتبط، [outbox](/fa/posts/go-outbox-pattern-nats/)، [idempotency](/fa/posts/nats-jetstream-idempotency/) و [retryها](/fa/posts/ds-timeouts-retries-backoff/).

> بخش‌های 2PC و saga **شبیه‌سازی** در Go روی یک ماشین‌اند: ساعت شبیه‌سازی‌شده، شبکه‌ی شبیه‌سازی‌شده (تأخیر ۱ تا ۳ tick با seed ثابت) و سرویس‌های داخل یک process. شمارش و tick نشان می‌دهم، نه زمان. همه را با Go 1.27 دوباره اجرا کردم، به‌همراه `go test -race` (اجرای اصلی با Go 1.26 بود) و خروجی‌ها همان است. بخش Postgres یک PostgreSQL 18.3 واقعی روی loopback با `psql` است؛ آن را هم دوباره اجرا کردم.

## commit دو فازی در شبیه‌سازی

ساختار یک coordinator و سه participant است: موجودی (inventory)، پرداخت (payment) و ارسال (shipping). هرکدام یک row برای سفارش را lock می‌کند. پروتکل دو فاز دارد:

1. **آماده‌سازی (prepare).** coordinator `PREPARE` می‌فرستد. هر participant کارش را انجام می‌دهد، آن را durable می‌کند، **lock را نگه می‌دارد** و رأی YES می‌دهد. participantی که نتواند سهمش را انجام دهد NO می‌دهد و rollback می‌کند.
2. **تصمیم.** coordinator تصمیمش را در log خودش می‌نویسد و بعد `COMMIT` (اگر همه YES داده‌اند) یا `ABORT` (اگر کسی NO داده) می‌فرستد. participantها با شنیدن آن lockهایشان را آزاد می‌کنند.

مسیر خوشحال با خروجی خود دمو این است. زمان‌ها tick شبیه‌سازی‌اند و هر پیام ۱ تا ۳ tick طول می‌کشد:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping PREPARED (row locked, durable), votes YES
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping YES
t=  6  coord <- inventory YES
t=  6  coord LOG "COMMIT"
t=  8  inventory COMMIT, lock released after 5 ticks
t=  8  payment COMMIT, lock released after 7 ticks
t=  8  shipping COMMIT, lock released after 7 ticks
t=  9  coord <- inventory ACK
t= 10  coord <- shipping ACK
t= 11  coord <- payment ACK
t= 11  coord LOG "END"
decision: COMMIT lock ticks: map[inventory:5 payment:7 shipping:7]
```

coordinator در `t=6`، لحظه‌ای که آخرین YES می‌رسد، `COMMIT` را log می‌کند. lock هر participant از خط `PREPARED` خودش تا رسیدن تصمیم نگه داشته شد: ۵ تا ۷ tick. این هزینه‌ی 2PC است، حتی وقتی هیچ چیز خراب نمی‌شود: در این بازه هیچ‌کس دیگر نمی‌تواند به آن rowها دست بزند.

حالا همان اجرا وقتی shipping رأی NO می‌دهد:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping votes NO (rolls back, no lock kept)
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping NO
t=  4  coord LOG "ABORT"
t=  6  coord <- inventory YES
t=  6  inventory ABORT, lock released after 3 ticks
t=  6  payment ABORT, lock released after 5 ticks
t=  7  coord <- inventory ACK
t=  9  coord <- payment ACK
decision: ABORT lock ticks: map[inventory:3 payment:5 shipping:0]
```

NO ارسال در `t=4` به coordinator می‌رسد و او فوراً `ABORT` را log می‌کند، بی‌آن‌که منتظر رأی inventory بماند. shipping هیچ‌وقت lock نگه نداشت (`shipping:0`). inventory و payment، که YES داده بودند، با رسیدن `ABORT` lockهایشان را آزاد می‌کنند. هر سه در یک وضعیت تمام می‌کنند: هیچ اتفاقی نیفتاد. این همان atomicity است.

### عیب معروف: coordinator که می‌میرد

لحظه‌ی خطرناک بعد از این است که participantی YES داده و پیش از این‌که تصمیم را بشنود. در این نقطه participant خودش نمی‌تواند تصمیم بگیرد. اگر commit کند، ممکن است coordinator ABORT تصمیم گرفته باشد. اگر abort کند، ممکن است coordinator COMMIT تصمیم گرفته باشد. پس باید صبر کند و lock را نگه دارد. در اجرای بعدی coordinator بعد از YES دادن هر سه، ولی پیش از نوشتن تصمیم، crash می‌کند و در `t=60` برمی‌گردد:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping PREPARED (row locked, durable), votes YES
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping YES
t=  6  coord <- inventory YES
t=  6  coord CRASH: all voted yes, no decision written yet
t= 60  coord RESTART, reads its log [BEGIN]
t= 60  coord found BEGIN without a decision -> presumed ABORT
t= 60  coord LOG "ABORT"
t= 61  inventory ABORT, lock released after 58 ticks
t= 61  payment ABORT, lock released after 60 ticks
t= 63  shipping ABORT, lock released after 62 ticks
t= 63  coord <- inventory ACK
t= 64  coord <- payment ACK
t= 65  coord <- shipping ACK
t= 65  coord LOG "END"
(32 INQUIRE lines and their lost replies left out)
decision: ABORT lock ticks: map[inventory:58 payment:60 shipping:62] competing writes refused: 12 of 13
```

آن را مثل یک خط زمانی بخوانید. بین `t=6` و `t=60` هیچ اتفاقی نمی‌افتد، چون coordinator خاموش است. در این ۵۴ tick هر سه participant با lockهایی که نگه داشته‌اند منتظر نشسته‌اند. بیکار نیستند: هر ۱۰ tick هرکدام از coordinator می‌پرسد «چه تصمیمی گرفته شد؟» (دمو خطوط `INQUIRE` را از چاپ حذف می‌کند و خودش هم می‌گوید: ۳۲ خط درباره‌ی این پرسش‌ها و پاسخ‌های گم‌شده، چون coordinator خاموش است). به این انتظار **blocking** می‌گویند. در `t=60` coordinator دوباره راه می‌افتد، log را می‌خواند، `BEGIN` را بدون تصمیم می‌بیند و انتخاب امن را می‌کند، یعنی abort. lockها ۵۸ و ۶۰ و ۶۲ tick نگه داشته شدند، به‌جای ۳ تا ۷. عدد آخر به نویسنده‌ی رقیبی مربوط است که هر ۵ tick row موجودی را می‌خواهد: ۱۲ تا از ۱۳ تلاشش به‌خاطر lock رد شد.

اگر coordinator پیش از crash `COMMIT` را در log نوشته بود، ریکاوری برعکس می‌شد. اجرای دمو برای آن حالت (trace کاملش را هم چاپ می‌کند که اینجا نیاوردم) با این خط‌ها تمام می‌شود: `coord RESTART, reads its log [BEGIN COMMIT]` و `coord found COMMIT without END -> resend COMMIT`. تصمیم `COMMIT` است، با همان زمان‌های lock یعنی ۵۸ و ۶۰ و ۶۲ tick: log است که «نامعلوم» را به یک تصمیم تبدیل می‌کند.

مدت نگه داشتن lock به مدت خاموشی coordinator بستگی دارد. حالت crash پیش از تصمیم را با چهار زمان ریکاوری اجرا کردم:

```
recover at t=10    decision=ABORT  lock ticks inventory=9    payment=11   shipping=11   refused=2/4
recover at t=60    decision=ABORT  lock ticks inventory=58   payment=60   shipping=62   refused=12/13
recover at t=200   decision=ABORT  lock ticks inventory=198  payment=202  shipping=202  refused=40/42
recover at t=1000  decision=ABORT  lock ticks inventory=1000 payment=1000 shipping=1000 refused=200/202
```

زمان lock تقریباً tick به tick دنبال زمان خاموشی است و نویسنده‌ی رقیب تقریباً هر بار رد می‌شود (۲۰۰ از ۲۰۲ در انتها). خاموشی coordinator تبدیل می‌شود به خاموشی همه‌ی rowهایی که یک تراکنش prepare‌شده lock کرده.

## آجر واقعی در Postgres

پایگاه‌داده‌های واقعی سمت participant در 2PC را در اختیار می‌گذارند. در Postgres اسمش {{< term "prepared-transaction" "prepared transaction" >}} است: `PREPARE TRANSACTION` دخالت session شما را تمام می‌کند ولی تراکنش را، با lockهایش، روی دیسک نگه می‌دارد. `max_prepared_transactions` باید بیشتر از ۰ باشد؛ instanceای که من راه انداختم ۵ داشت. اینجا یک پایگاه‌داده جای دو resource manager جدا نشسته، با یک جدول `account` و یک جدول `stock`.

```sql
begin; update account set balance = balance - 30 where id = 1;
       update stock set qty = qty - 1 where sku = 'A';
prepare transaction 'order-42';
```

بعد از پایان session، داده هنوز مقدارهای قدیمی را نشان می‌داد (balance برابر ۱۰۰ و qty برابر ۵)، ولی تراکنش وجود داشت، و lockهایش هم. خروجی واقعی:

```
   gid    | has_ts | owner | database 
----------+--------+-------+----------
 order-42 | t      | app   | orders

 locktype |   rel   |       mode       | granted | no_session 
----------+---------+------------------+---------+------------
 relation | account | RowExclusiveLock | t       | t
 relation | stock   | RowExclusiveLock | t       | t
```

جدول اول `pg_prepared_xacts` است: تراکنشی به اسم `order-42` که به هیچ session تعلق ندارد (`has_ts` فقط می‌گوید زمان prepare ثبت شده). جدول دوم `pg_locks` است: هر دو جدول lock شده‌اند و `no_session = t` یعنی هیچ session زنده‌ای صاحب این lockها نیست؛ مال تراکنش prepare‌شده‌اند. یک session دوم با `lock_timeout = '500ms'` که همان row را به‌روز می‌کند:

```
ERROR:  canceling statement due to lock timeout
CONTEXT:  while updating tuple (0,1) in relation "account"
```

این blocking است، با یک پایگاه‌داده‌ی واقعی. بعد Postgres را روی همان data directory دوباره راه انداختم: `order-42` هنوز در فهرست بود. یک session کاملاً جدید `COMMIT PREPARED 'order-42'` را اجرا کرد و مقدارها ۷۰ و ۴ شدند و هیچ تراکنش prepare‌شده‌ای نماند. مسیر دیگر را هم امتحان کردم: `ROLLBACK PREPARED` داده را بدون تغییر می‌گذارد.

پس قولِ فاز prepare واقعی است: بعد از `PREPARE` participant دیگر نمی‌تواند نه بگوید، حتی با crash. و هزینه‌اش هم واقعی است. طبق مستندات Postgres، `PREPARE TRANSACTION` «برای استفاده در برنامه‌ها در نظر گرفته نشده» (is not intended for use in applications)؛ برای یک transaction manager بیرونی است، و تراکنش prepare‌شده‌ی فراموش‌شده lockهایش را نگه می‌دارد و می‌تواند VACUUM را عقب بیندازد. XA رابط استاندارد چنین managerهاست؛ هیچ‌کدام را اجرا نکردم.

## saga: برگرداندن با یک کار تازه

saga با نگه نداشتن lock بین سرویس‌ها از همه‌ی این‌ها فرار می‌کند. سفارش را به مرحله‌های محلی تقسیم می‌کند که هرکدام یک جبران دارد:

| مرحله | جبران (برگرداندن) |
|---|---|
| رزرو موجودی | آزاد کردن موجودی |
| شارژ کارت | بازپرداخت |
| ساخت مرسوله | (آخرین مرحله، بعدش چیزی نیست) |

هر مرحله بلافاصله در سرویس خودش commit می‌شود. اگر مرحله‌ای شکست بخورد، saga جبران مرحله‌های قبلی را به ترتیب معکوس اجرا می‌کند. هر دو سبک رایج را نوشتم:

- {{< term "orchestration" "Orchestration" >}}: یک coordinator، یک state machine با log پایدار (`begin` و `done` و `failed` و `comp`)، مرحله‌ها را به ترتیب صدا می‌زند و هنگام شکست جبران‌ها را. شبیه coordinator در 2PC است، ولی فقط فراخوانی‌ها را هدایت می‌کند و lock نگه نمی‌دارد.
- {{< term "choreography" "Choreography" >}}: بدون coordinator. سرویس‌ها به رویدادهای یک صف پایدار که دست‌کم یک بار تحویل می‌دهد واکنش نشان می‌دهند. `ShippingFailed` باعث می‌شود payment بازپرداخت کند؛ `PaymentRefunded` باعث می‌شود موجودی آزاد شود.

دمو این ویژگی را در پایان هر اجرا بررسی می‌کند: **پول گرفته شده است اگر و فقط اگر سفارش ارسال شده، و موجودی رزرو شده است اگر و فقط اگر ارسال شده.** یعنی هیچ سفارش نیمه‌کاره‌ای باقی نمی‌ماند. حالت‌ها همه‌ی ترکیب‌های این‌ها را می‌پوشانند: هر مرحله شکست بخورد (یا هیچ‌کدام)، هر فراخوانی دو بار یا یک بار تحویل شود، اولین فراخوانی undo هر سرویس یک بار شکست بخورد یا نه، یک crash پیش از هر نوشتن log و هر فراخوانی سرویس، و یک crash دوم در حین ریکاوری:

```
orchestration (persisted log) cases=3468 violations=0
choreography (events)     cases=2508 violations=0
```

هر حالت در وضعیت سازگار تمام می‌شود. checker می‌تواند هشدار بدهد: یک تست بازپرداختی می‌سازد که کاری نمی‌کند و ناوردا آن را علامت می‌زند. این به خاطر سه قاعده در کد برقرار است. فراخوانی‌ها **idempotent** هستند: هر سرویس نتیجه را به‌ازای هر شناسه‌ی saga نگه می‌دارد، پس فراخوانی تکراری چیزی را عوض نمی‌کند. جبران یک نشانه به جا می‌گذارد که باعث می‌شود سرویس فراخوانی رو به جلوی دیررسیده برای همان saga را رد کند. و جبران تا موفق شدن دوباره امتحان می‌شود. به این توجه کنید که چه چیزی بررسی می‌شود: وضعیت نهایی. در طول اجرا اجازه داریم ناوردا شکسته باشد، و همین ما را به هزینه‌اش می‌رساند.

## saga چه چیزی را قابل دیدن می‌کند

با 2PC بقیه حالت میانی را نمی‌بینند چون rowها lock هستند. saga چنین محافظتی ندارد: بعد از مرحله‌ی شارژ، پول واقعاً گرفته شده، حتی اگر مرحله‌ی بعد دارد شکست می‌خورد و بازپرداخت می‌کند. دمو این را با خواننده‌ای نشان می‌دهد که بعد از هر کار پایدار سفارش را نگاه می‌کند، وقتی shipping شکست می‌خورد:

```
reads=20  naive view saw 'charged'=7, final charged=false
PENDING view (status exposed only when the saga ends): reads that showed 'charged'=0
```

هفت خواندن از بیست خواندن پولی را دیدند که بعداً برگردانده شد. راه‌های مقابله در سطح برنامه‌اند: نشان دادن حالت `PENDING` به مشتری تا وقتی saga تمام شود (خط دوم: نمای pending هیچ‌وقت «charged» نشان نداد)، استفاده از **semantic lock** که پرچمی روی سفارش است و باعث می‌شود عملیات دیگر در حین اجرای saga صبر کنند یا شکست بخورند، و ترجیح دادن به‌روزرسانی‌هایی که جابه‌جایی‌پذیرند (commutative). من فقط نمای pending را پیاده کردم.

## مقایسه

| | 2PC | Saga |
|---|---|---|
| Atomicity | همه یا هیچ | نهایی، با جبران |
| ایزولاسیون | lockها در حین prepare نگه داشته می‌شوند | ندارد، حالت‌های میانی دیده می‌شوند |
| دسترس‌پذیری | روی coordinator بلاک می‌شود | ادامه می‌دهد، بعداً ترمیم می‌کند |
| تأخیر | دو round trip با lock | بدون lock بین سرویس‌ها |
| پیچیدگی | در پروتکل | در جبران‌های شما |
| وابستگی | منابعی لازم است که 2PC بفهمند | هر سرویسی با یک API |

به تجربه‌ی من saga به سرویس‌های جدا می‌خورد و 2PC به چند database تحت کنترل خودتان. طبق مقاله‌اش، Spanner از 2PC بین گروه‌هایی از replicaها استفاده می‌کند که خودشان با Paxos replicate شده‌اند، پس coordinator و participantها مثل یک ماشین تنها نمی‌میرند؛ فقط نامش را می‌برم. TCC (try-confirm-cancel) شیوه‌ای برای ساختن saga است که در آن مرحله‌ی «try» یک رزرو است که بعداً تأیید یا لغو می‌شود.

## جایی که saga خراب می‌شود

- **نیت را پیش از فراخوانی و نتیجه را بعد از آن log کنید.** crashها در فاصله‌ی بین این دو زندگی می‌کنند و saga برای دانستن این‌که از کجا ادامه بدهد به log نیاز دارد.
- **جبران همان rollback نیست.** بازپرداخت یک واقعیت تازه است که در صورت‌حساب مشتری دیده می‌شود، و ایمیلی که فرستاده شده برگشت‌پذیر نیست.
- **مرحله‌ای را که نمی‌تواند شکست بخورد یا برگردد آخر بگذارید.** آن‌وقت بعد از آن چیزی به جبران نیاز ندارد.
- **رویدادهای saga را از طریق outbox منتشر کنید**، وگرنه ممکن است بین نوشتن در پایگاه‌داده و ارسال پیام گم شوند.
- **شبیه‌سازی شبیه‌سازی است.** partition شبکه ندارد، دیسک واقعی ندارد و سرویس‌هایش اشیای داخل یک process هستند.

## قدم بعدی

بعد، «CQRS و event sourcing» می‌آید. saga به log اتفاق‌ها تکیه دارد. قدم بعد این است که آن log را منبع حقیقتِ خودِ داده کنیم و از viewهای جدای ساخته‌شده از آن بخوانیم.
