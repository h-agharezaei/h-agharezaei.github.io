+++
date = '2027-01-29T10:00:00+03:30'
draft = false
title = 'KV و Object Store در NATS'
description = 'KV و Object Store در NATS JetStream با Go: revision، compare-and-swap، watch، TTL، یک قفل ساده و ذخیره‌ی object‌های بزرگ، همراه با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "kv", "object-store", "messaging"]
cover = { image = "/images/covers/nats-kv-object-store.fa.png", alt = "KV و Object Store در NATS", hiddenInSingle = true }
+++

فرض کنید چند سرویس دارید که همه باید یک تکه‌ی کوچک کانفیگ مشترک را بخوانند، مثلاً یک feature flag که checkout جدید را روشن می‌کند. سه چیز می‌خواهید. سرویس بتواند flag را بخواند. وقتی کسی آن را عوض کرد فوراً خبردار شود، بدون polling. و دو نفری که همزمان flag را عوض می‌کنند بی‌صدا روی کار هم ننویسند. یک روز دیگر یکی از سرویس‌ها باید یک فایل گزارش ۵ مگابایتی را با سرویس دیگر به اشتراک بگذارد. می‌توانید برای هرکدام یک دیتابیس یا فایل‌سرور جدا راه بیندازید، یا متوجه شوید چیزی دارید که هر دو را بلد است.

اگر سرویس‌هایتان از قبل JetStream دارند، می‌تواند: JetStream به‌عنوان **ذخیره‌ی key-value** (KV) و **ذخیره‌ی blob** (Object Store) هم کار می‌کند. هر دو روی streamها ساخته شده‌اند، پس چیز اضافه‌ای برای راه‌اندازی نیست. سرور تعبیه‌شده‌ی [مقاله‌ی قبل](/fa/posts/nats-jetstream-testing/) برای امتحانشان کافی است. کاربردهای معمول: feature flag، قفل‌های کوتاه‌عمر، [کلیدهای dedup](/fa/posts/nats-jetstream-idempotency/) یا فایلی که چند سرویس لازم دارند.

> همه‌چیز را با Go 1.27، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 اجرا کردم و از پکیج جدیدتر `jetstream` استفاده کردم (KV و Object Store در آن است). دمو یک برنامه‌ی محلی با یک سرور تعبیه‌شده است. کد یک مثال محلی است، نه یک repo منتشرشده. ماشین مشغول بود، پس فقط زمان‌های تقریبی می‌آورم، و شناسه‌های تصادفی در خروجی (مثل `nuid`) در هر اجرا فرق می‌کنند.

## ساختن bucket، put و get

یک KV یک **bucket** (سطل) از کلیدها و مقدارهاست. مقداری را زیر یک کلید می‌گذارید و دوباره می‌خوانید. نکته این است که هر نوشتن یک **revision** می‌گیرد، عددی که می‌گوید این کدام نوشتن بود. همین عدد کوچک است که watch و به‌روزرسانی امن را در ادامه‌ی مقاله ممکن می‌کند.

در دموی اول یک bucket به نام `Config` می‌سازم، یک کلید را دو بار می‌نویسم و می‌خوانمش:

```go
kv, _ := js.CreateKeyValue(ctx, jetstream.KeyValueConfig{
	Bucket: "Config", History: 5, Storage: jetstream.FileStorage,
})
r1, _ := kv.Put(ctx, "feature.checkout", []byte("off"))
r2, _ := kv.Put(ctx, "feature.checkout", []byte("on"))
e, _ := kv.Get(ctx, "feature.checkout")
hist, _ := kv.History(ctx, "feature.checkout")
```

```text
put revisions: 1 2
get: key=feature.checkout value=on revision=2 op=KeyValuePutOp
get missing: nats: key not found true
history: rev=1 value=off
history: rev=2 value=on
```

خط‌به‌خط:

- `put revisions: 1 2`: دو نوشتن revision شماره‌ی ۱ و ۲ گرفتند.
- `get`: خواندن کلید آخرین مقدار، یعنی `on` را با revision شماره‌ی ۲ برمی‌گرداند. `op=KeyValuePutOp` می‌گوید این مدخل با put ساخته شده (انواع دیگرش delete و purge است، پایین‌تر).
- `get missing`: خواندن کلیدی که وجود ندارد خطا برمی‌گرداند. در Go با `errors.Is(err, jetstream.ErrKeyNotFound)` آزمونش می‌کنید و `true` آخر خط همان بررسی است.
- `history`: هر دو مقدار هنوز هستند، قدیمی‌ترین اول، چون bucket تاریخچه نگه می‌دارد.

`History` تعداد مقدارهای قدیمی هر کلید است که bucket نگه می‌دارد (پیش‌فرض ۱ و حداکثر ۶۴). revision همان شماره‌ی ترتیب stream برای آن نوشتن است، پس در کل bucket یکتاست، نه برای هر کلید جدا. فیلدهای مفید دیگر `TTL` (انقضا، بعداً می‌آید) و `Storage` (فایل یا حافظه) هستند.

## این فقط یک stream است

اگر KV «روی stream ساخته شده» می‌توانیم زیر کاپوت را ببینیم. دمو اطلاعات stream و پیام خام را می‌خواند:

```text
stream=KV_Config subjects=[$KV.Config.>] max_msgs_per_subject=5 storage=File msgs=2
raw message: subject=$KV.Config.feature.checkout seq=2 data=on
```

bucket به نام `Config` یک stream به نام `KV_Config` است. هر کلید یک subject است، یعنی `$KV.Config.<key>`، و `History: 5` شده `max_msgs_per_subject=5` که یعنی «برای هر subject حداکثر ۵ پیام نگه دار». `msgs=2` همان دو نوشتن ماست. `Get` فقط آخرین پیام آن subject را می‌خواند و شماره‌ی ترتیب آن پیام (`seq=2`) همان revision است. پس هرچه درباره‌ی streamها می‌دانید (replica، storage، `nats stream info`) برای bucket هم صادق است.

## Create و Update: compare-and-swap

حالا مشکل دو نفری که یک flag را عوض می‌کنند. فرض کنید دو سرویس هر دو شمارنده‌ای با مقدار ۵ را می‌خوانند و هر دو ۶ می‌نویسند. یک افزایش گم می‌شود و هیچ‌کس خطایی نمی‌گیرد. راه‌حل رایج **compare-and-swap** است: «این مقدار جدید را فقط اگر کلید هنوز روی همان revisionی است که من خواندم بنویس». اگر کسی در این فاصله آن را عوض کرده باشد، نوشتن رد می‌شود و دوباره می‌خوانید. این همان ایده‌ی {{< term "optimistic-concurrency" "همزمانی خوش‌بینانه" >}} است: قفل نیست، فقط یک بررسی موقع نوشتن.

KV برای این دو فراخوانی دارد. `Create` فقط وقتی موفق می‌شود که کلید وجود نداشته باشد. `Update` فقط وقتی موفق می‌شود که revision فعلی کلید را بدهید. دمو هر دو را امتحان می‌کند، با حالت‌های شکست:

```text
create: 3 <nil>
create again: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 3: key exists | is ErrKeyExists: true
update with current rev: 4 <nil>
update stale: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 4: nats: key revision mismatch
api error code: 10071 | wrong last sequence: 4
is ErrKeyRevisionMismatch: true
```

- اولین `create` کلید `limit` را با revision شماره‌ی ۳ ساخت (revisionهای ۱ و ۲ نوشتن‌های قبلی بودند).
- `create` دوم همین کلید شکست خورد. `wrong last sequence: 3` می‌گوید آخرین revision کلید ۳ است، پس «ساختن» مجاز نیست.
- `update with current rev` با revision شماره‌ی ۳ موفق شد و revision جدید ۴ است.
- `update stale` با revision شماره‌ی ۱ آمد که کهنه است. سرور جواب داد `wrong last sequence: 4`، یعنی «کلید روی ۴ است، نه ۱»، و کتابخانه آن را revision mismatch گزارش می‌کند.

هر دو شکست در اصل همان بررسی `wrong last sequence` سرور هستند (کد خطا ۱۰۰۷۱). در Go از `errors.Is` با `jetstream.ErrKeyExists` و `jetstream.ErrKeyRevisionMismatch` استفاده کنید. حلقه‌ی معمول این است: `Get`، محاسبه‌ی مقدار جدید، `Update` با revisionی که خواندید و در صورت mismatch دوباره `Get` و تلاش مجدد. قفل لازم نیست.

## Delete در برابر Purge و تاریخچه

برای پاک کردن یک کلید دو راه هست و در سرنوشت تاریخچه فرق دارند. در دمو کلیدهای `a` و `b` را هرکدام دو بار نوشتم و بعد `Delete(a)` و `Purge(b)` را صدا زدم:

```text
get a after delete: nats: key not found
history a (3 entries): [rev=5 op=KeyValuePutOp] [rev=6 op=KeyValuePutOp] [rev=9 op=KeyValueDeleteOp]
history b (1 entries): [rev=10 op=KeyValuePurgeOp]
keys: [feature.checkout limit]
```

`Delete` یک نشانگر حذف اضافه می‌کند و مقدارهای قدیمی را در تاریخچه نگه می‌دارد: `a` دو put خود را دارد (revisionهای ۵ و ۶) و نشانگر (revision شماره‌ی ۹). revisionهای ۷ و ۸ مال `b` هستند، که دوباره نشان می‌دهد revisionها در کل bucket شمرده می‌شوند. `Purge` هم نشانگر می‌نویسد (revision شماره‌ی ۱۰) ولی مقدارهای قدیمی‌تر را پاک می‌کند، برای همین `b` یک مدخل دارد. هر دو باعث می‌شوند `Get` خطای `ErrKeyNotFound` بدهد و `Keys` دیگر فهرستشان نکند: فقط `feature.checkout` و `limit` مانده‌اند.

## Watch

حالا چیز دوم از ابتدای مقاله: خبردار شدن وقتی مقداری عوض می‌شود. **watch** یک subscription روی bucket است. کد از کانال `Updates()` ناظر می‌خواند:

```go
w, _ := kv.WatchAll(ctx)
for e := range w.Updates() {
	if e == nil { fmt.Println("nil (initial values done)"); continue }
	fmt.Println(e.Key(), string(e.Value()), e.Revision(), e.Operation())
}
```

در دمو bucket از قبل دو کلید دارد. بعد از شروع watch، یک goroutine دیگر دو put و یک delete انجام می‌دهد:

```text
watch: dark=off rev=1 op=KeyValuePutOp
watch: beta=off rev=2 op=KeyValuePutOp
watch: nil (initial values done)
watch: dark=on rev=3 op=KeyValuePutOp
watch: gamma=on rev=4 op=KeyValuePutOp
watch: beta= rev=5 op=KeyValueDeleteOp
```

دو خط اول مقدار فعلی هر کلید است. بعد یک مدخل `nil` می‌آید که یعنی «به زمان حال رسیدی». بعد از آن تغییرهای زنده می‌آیند: `dark` روشن شد، کلید تازه‌ی `gamma` آمد و `beta` حذف شد (مقدارش خالی است). سرویس می‌تواند از این برای نگه داشتن یک cache محلی از کانفیگ استفاده کند: cache را از بخش اول پر می‌کند و تغییرها را با رسیدنشان اعمال می‌کند، بدون polling. `Watch` یک الگوی کلید می‌گیرد و گزینه‌هایی مثل `UpdatesOnly()` و `IgnoreDeletes()` هم هست.

## TTL و یک قفل کوچک

bucket می‌تواند مدخل‌ها را منقضی هم بکند. bucket با `TTL: time.Second` مدخل‌ها را یک ثانیه بعد از نوشتن حذف می‌کند. دمو یک کلید session می‌نویسد و به‌جای sleep با یک مهلت poll می‌کند:

```text
get right after put: <nil>
gone after ~1.3s: nats: key not found
```

خط اول یعنی خواندن موفق بود (`<nil>` یعنی «بدون خطا»). خط دوم یعنی کلید بعد از حدود ۱٫۳ ثانیه خودش ناپدید شد. انقضا لحظه‌ای نیست: با TTL یک‌ثانیه‌ای روی یک ماشین مشغول حدود ۱٫۳ ثانیه دیدم، پس هرگز به زمان دقیق تکیه نکنید.

`Create` و TTL را کنار هم بگذارید تا قفلی داشته باشید که اگر صاحبش بمیرد خودش آزاد می‌شود. `Create` گرفتن قفل است چون فقط یک نفر می‌تواند کلید را بسازد و TTL تور ایمنی است. در دمو `worker-a` قفل `nightly-report` را می‌گیرد و با آزاد نکردنش «crash» می‌کند. بعد `worker-b` و `worker-c` در یک حلقه `Create` را دوباره امتحان می‌کنند. هرکس ببرد ۱۰۰ میلی‌ثانیه قفل را نگه می‌دارد و با `Delete` آزادش می‌کند:

```text
+0.0s worker-a: create lock: err=<nil>
+1.3s worker-c: got the lock
+1.5s worker-b: got the lock
+1.6s done
```

تا ۱٫۳ ثانیه‌ی اول هیچ‌کس نتوانست قفل را بگیرد، تا مدخل worker-a منقضی شد. بعد `worker-c` برد و `worker-b` فقط بعد از آزاد کردن `worker-c` آن را گرفت، پس هر لحظه فقط یک نفر آن را داشت. برنده در هر اجرا می‌تواند فرق کند، و در اجرای قبلی‌ام برای `worker-b` عدد `+1.4s` و برای `done` عدد `+1.5s` چاپ شد.

توجه کنید این یک lease ساده است، نه mutex امن. اگر صاحب قفل فقط کند باشد و TTL بگذرد، یک نفر دیگر هم قفل را می‌گیرد. کار را idempotent نگه دارید. همین `Create` برای بررسی dedup هم عالی است، و برای خاموش کردن تمیز Workerها [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) را ببینید.

## Object Store

مقدارهای KV کوچک‌اند، چون هرکدام یک پیام NATS است. برای چیزهای بزرگ Object Store هست. یک blob بزرگ را به chunk (تکه) تقسیم می‌کند، هر تکه را یک پیام ذخیره می‌کند و موقع `Get` دوباره سر هم می‌کند. دمو ۵ مگابایت + ۱۲۳ بایت داده‌ی شبه‌تصادفی می‌سازد و رفت‌وبرگشت را با SHA-256 بررسی می‌کند:

```text
generated 5243003 bytes sha256=814fa28020cf3b71
put: name=report.bin size=5243003 chunks=41 digest=SHA-256=gU-igCDPO3F_4IIRwRPdwils9n-F89Us246F7Q2bgTo= nuid=OBH4NbUJ2ckiDHP87U2H7F
get: 5243003 bytes sha256=814fa28020cf3b71 equal=true
list: report.bin size=5243003 chunks=41
list: small.txt size=5 chunks=1
stream=OBJ_Files subjects=[$O.Files.C.> $O.Files.M.>] msgs=44 bytes=5246313
```

- خط اول ۸ بایت اول SHA-256 داده‌ای را که ساختیم چاپ می‌کند. `get` همان مقدار را برای داده‌ی برگشتی چاپ می‌کند و `equal=true` یعنی یکی هستند.
- `put` نشان می‌دهد شیء در ۴۱ تکه ذخیره شد، با یک digest از نوع SHA-256 برای محتوا.
- اندازه‌ی پیش‌فرض هر تکه ۱۲۸ کیلوبایت است، پس blob شد ۴۱ پیام: ۴۰ تکه‌ی کامل و یک تکه‌ی آخر ۱۲۳ بایتی.
- subjectهای `.C.` تکه‌ها و subjectهای `.M.` متادیتا را نگه می‌دارند، پس ۴۴ پیام = ۴۱ تکه + ۱ تکه‌ی `small.txt` + ۲ پیام متادیتا (یکی برای هر شیء).

بعد دمو شیء بزرگ را حذف می‌کند:

```text
info after delete: nats: object not found
after delete: msgs=3 bytes=671
status: bucket=Files size=671 sealed=false storage=File replicas=1
```

حذف تکه‌ها را پاک می‌کند و یک نشانگر متادیتا می‌گذارد: ۳ پیام می‌ماند (تکه و متادیتای `small.txt` و نشانگر `report.bin`). `replicas=1` اشاره‌ای به مقاله‌ی بعد است: این bucket فقط روی یک سرور است.

## KV و Object Store کجا کم می‌آورند

- این یک دیتابیس نیست: نه query دارد، نه تراکنش روی چند کلید، فقط revision برای هر کلید. آن را حالت مشترک کوچک بدانید.
- در این دمو TTL تنظیم bucket است، پس برای هر طول عمر یک bucket بگیرید (قفل‌ها، sessionها، کانفیگ).
- مقدارها به‌صورت پیام معمولی NATS می‌روند، پس حداکثر payload سرور (طبق مستندات NATS به‌طور پیش‌فرض ۱ مگابایت) مقدار KV را محدود می‌کند. بیشتر از آن از Object Store استفاده کنید.
- Object Store موقع `Get` digest را بررسی می‌کند، ولی باز هم تکه‌هایی در یک stream است: حد ذخیره‌سازی و replicaها را در نظر بگیرید.
- ناظرها باید مدخل `nil` و نشانگرهای حذف را مدیریت کنند، مثل خروجی بالا.

## قدم بعدی

همه‌ی این‌ها روی یک سرور تعبیه‌شده اجرا شد. مقاله‌ی بعد، [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/)، می‌گوید با سه سرور و یک محیط واقعی چه چیزهایی عوض می‌شود.
