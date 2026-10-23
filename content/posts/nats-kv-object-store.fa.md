+++
date = '2027-01-29T10:00:00+03:30'
draft = false
title = 'KV و Object Store در NATS'
description = 'KV و Object Store در NATS JetStream با Go: revision، compare-and-swap، watch، TTL، یک قفل ساده و ذخیره‌ی object‌های بزرگ، همراه با خروجی واقعی.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "kv", "object-store", "messaging"]
cover = { image = "/images/covers/nats-kv-object-store.fa.png", alt = "KV و Object Store در NATS", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/nats-jetstream-testing/) سرویس‌های JetStream را با یک سرور توکار تست کردیم. این مقاله از همان ترفند برای چیز تازه‌ای استفاده می‌کند: JetStream می‌تواند **key-value store** (KV) و **blob store** (Object Store) هم باشد. هر دو روی streamها ساخته شده‌اند و چیز اضافه‌ای برای اجرا لازم نیست. برای وضعیت کوچکِ مشترک عالی‌اند: feature flag، قفل‌های کوتاه‌مدت، [کلیدهای dedup](/fa/posts/nats-jetstream-idempotency/) یا فایلی که چند سرویس لازم دارند.

> Go 1.26، `nats-server` نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0، با پکیج جدیدتر `jetstream` (KV و Object Store را دارد). برنامه‌ی نمونه یک سرور توکار دارد. ماشین شلوغ بود، پس فقط زمان‌های تقریبی را می‌آورم.

## ساخت bucket، Put و Get

```go
kv, _ := js.CreateKeyValue(ctx, jetstream.KeyValueConfig{
	Bucket: "Config", History: 5, Storage: jetstream.FileStorage,
})
r1, _ := kv.Put(ctx, "feature.checkout", []byte("off"))
r2, _ := kv.Put(ctx, "feature.checkout", []byte("on"))
e, _ := kv.Get(ctx, "feature.checkout")
hist, _ := kv.History(ctx, "feature.checkout")
```
```
put revisions: 1 2
get: key=feature.checkout value=on revision=2 op=KeyValuePutOp
get missing: nats: key not found true
history: rev=1 value=off
history: rev=2 value=on
```

`History` تعداد مقدارهای قدیمیِ نگه‌داشته‌شده برای هر کلید است (پیش‌فرض ۱، حداکثر ۶۴). **Revision** همان شماره‌ی sequence پیام در stream است، پس در کل bucket یکتاست، نه فقط برای هر کلید. از فیلدهای مفید دیگر `TTL` (انقضا) و `Storage` (فایل یا حافظه) است.

## فقط یک stream است

```
stream=KV_Config subjects=[$KV.Config.>] max_msgs_per_subject=5 storage=File msgs=2
raw message: subject=$KV.Config.feature.checkout seq=2 data=on
```

Bucket به نام `Config` یک stream با نام `KV_Config` است. هر کلید یک subject است: `$KV.Config.<key>`، و `History` به `max_msgs_per_subject` تبدیل می‌شود. `Get` آخرین پیام آن subject را می‌خواند. پس هر چه درباره‌ی streamها می‌دانید (replica، storage، `nats stream info`) اینجا هم صدق می‌کند.

## Create و Update: compare-and-swap

`Create` فقط وقتی موفق می‌شود که کلید وجود نداشته باشد. `Update` فقط وقتی موفق می‌شود که revision فعلی کلید را بدهید.

```
create: 3 <nil>
create again: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 3: key exists | is ErrKeyExists: true
update with current rev: 4 <nil>
update stale: nats: nats: API error: code=400 err_code=10071 description=wrong last sequence: 4: nats: key revision mismatch
is ErrKeyRevisionMismatch: true
```

هر دو در اصل همان بررسی `wrong last sequence` سرور هستند (کد خطای 10071). در Go با `errors.Is` و `jetstream.ErrKeyExists` یا `jetstream.ErrKeyRevisionMismatch` تشخیص بدهید. الگوی معمول: `Get`، محاسبه، `Update` با همان revision، و اگر mismatch بود دوباره `Get` و تلاش مجدد. به قفل نیازی نیست.

## Delete در برابر Purge و تاریخچه

کلیدهای `a` و `b` را دو بار نوشتم، بعد `Delete(a)` و `Purge(b)`:

```
get a after delete: nats: key not found
history a (3 entries): [rev=5 op=KeyValuePutOp] [rev=6 op=KeyValuePutOp] [rev=9 op=KeyValueDeleteOp]
history b (1 entries): [rev=10 op=KeyValuePurgeOp]
keys: [feature.checkout limit]
```

`Delete` یک نشانگر حذف اضافه می‌کند و مقدارهای قدیمی در history می‌مانند. `Purge` هم نشانگر می‌نویسد ولی مقدارهای قبلی را پاک می‌کند. در هر دو حالت `Get` خطای `ErrKeyNotFound` می‌دهد.

## Watch

```go
w, _ := kv.WatchAll(ctx)
for e := range w.Updates() {
	if e == nil { fmt.Println("nil (initial values done)"); continue }
	fmt.Println(e.Key(), string(e.Value()), e.Revision(), e.Operation())
}
```

با دو کلیدِ موجود، بعد دو put و یک delete از goroutine دیگر:

```
watch: dark=off rev=1 op=KeyValuePutOp
watch: beta=off rev=2 op=KeyValuePutOp
watch: nil (initial values done)
watch: dark=on rev=3 op=KeyValuePutOp
watch: gamma=on rev=4 op=KeyValuePutOp
watch: beta= rev=5 op=KeyValueDeleteOp
```

اول مقدار فعلیِ همه‌ی کلیدها می‌آید، بعد یک مقدار `nil` به معنی «به‌روز شدی»، بعد تغییرهای زنده، از جمله delete. یک سرویس با این می‌تواند cache محلیِ config خودش را نگه دارد. `Watch` الگوی کلید می‌گیرد و گزینه‌هایی مثل `UpdatesOnly()` و `IgnoreDeletes()` هست.

## TTL و یک قفل کوچک

Bucket با `TTL: time.Second` ورودی‌ها را بعد از یک ثانیه حذف می‌کند. به‌جای sleep، تا یک deadline poll کردم:

```
get right after put: <nil>
gone after ~1.3s: nats: key not found
```

(انقضا لحظه‌ای نیست: با TTL یک‌ثانیه‌ای روی ماشین شلوغ حدود ۱.۳ ثانیه دیدم، پس هرگز به زمان دقیق تکیه نکنید.) `Create` و TTL را کنار هم بگذارید تا قفلی داشته باشید که اگر صاحبش بمیرد خودش آزاد می‌شود. در نمونه، `worker-a` قفل `nightly-report` را می‌گیرد و «crash» می‌کند، بعد `worker-b` و `worker-c` در حلقه `Create` را تکرار می‌کنند و برنده با `Delete` آزادش می‌کند:

```
+0.0s worker-a: create lock: err=<nil>
+1.3s worker-c: got the lock
+1.4s worker-b: got the lock
+1.5s done
```

هر لحظه فقط یکی قفل را داشت. این یک lease ساده است، نه mutex امن: اگر صاحب قفل فقط کند باشد و TTL بگذرد، دیگری هم قفل را می‌گیرد. کار را idempotent نگه دارید. همین `Create` برای بررسی dedup هم خوب است، و برای متوقف کردن تمیز workerها [graceful shutdown](/fa/posts/go-graceful-shutdown-workers/) را ببینید.

## Object Store

مقدارهای KV کوچک‌اند. برای چیزهای بزرگ Object Store هست. ۵ مگابایت + ۱۲۳ بایت داده‌ی تصادفی ساختم و رفت‌وبرگشت را با SHA-256 بررسی کردم:

```
generated 5243003 bytes sha256=814fa28020cf3b71
put: name=report.bin size=5243003 chunks=41 digest=SHA-256=gU-igCDPO3F_4IIRwRPdwils9n-F89Us246F7Q2bgTo= nuid=...
get: 5243003 bytes sha256=814fa28020cf3b71 equal=true
list: report.bin size=5243003 chunks=41
list: small.txt size=5 chunks=1
stream=OBJ_Files subjects=[$O.Files.C.> $O.Files.M.>] msgs=44 bytes=5246313
```

اندازه‌ی پیش‌فرض هر chunk برابر ۱۲۸ کیلوبایت است، پس blob به ۴۱ پیام تبدیل شد (۴۰ chunk کامل و ۱۲۳ بایت). subjectهای `.C.` chunkها و `.M.` متادیتا را نگه می‌دارند، پس ۴۴ پیام = ۴۱ + ۱ chunk فایل `small.txt` + ۲ متادیتا. بعد از `Delete("report.bin")`:

```
info after delete: nats: object not found
after delete: msgs=3 bytes=671
status: bucket=Files size=671 sealed=false storage=File replicas=1
```

Delete، chunkها را پاک می‌کند و یک نشانگر در متادیتا می‌گذارد.

## چند نکته‌ی مهم

- این پایگاه‌داده نیست: query ندارد، تراکنش بین چند کلید ندارد، فقط revision برای هر کلید. آن را وضعیت کوچکِ مشترک بدانید.
- TTL اینجا تنظیم کل bucket است، پس برای هر طول عمر یک bucket بسازید (قفل‌ها، sessionها، config).
- مقدارها پیام عادی NATS هستند، پس حداکثر payload سرور (پیش‌فرض ۱ مگابایت) مقدار KV را محدود می‌کند؛ بزرگ‌تر از آن Object Store.
- Object Store هنگام `Get` digest را بررسی می‌کند، ولی باز هم chunk در یک stream است: به محدودیت‌های storage و replica دقت کنید.
- Watcher باید ورودی `nil` و نشانگرهای delete را مدیریت کند.

## قدم بعدی

مقاله‌ی بعد: JetStream در production، شامل clustering، retention و امنیت.
