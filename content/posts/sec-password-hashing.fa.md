+++
date = '2027-03-22T10:00:00+03:30'
draft = false
title = 'ذخیره‌ی امن پسورد: argon2 و bcrypt'
description = 'هش کردن پسورد در Go با bcrypt و argon2id: salt، cost، محدودیت ۷۲ بایت، قالب PHC، مقایسه‌ی زمان‌ثابت و rehash هنگام login، با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "passwords", "argon2", "bcrypt", "hashing", "go"]
cover = { image = "/images/covers/sec-password-hashing.fa.png", alt = "ذخیره‌ی امن پسورد: argon2 و bcrypt", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [تزریق و XSS](/fa/posts/sec-injection-xss/)، درباره‌ی نفوذ از راه ورودی بود. این مقاله بدترین حالتِ بعد از آن را فرض می‌کند: کسی جدول `users` شما را خوانده است. اگر پسوردها ساده ذخیره شده باشند، همه‌ی حساب‌ها از دست رفته‌اند و چون مردم پسورد را تکرار می‌کنند، حساب‌های سایت‌های دیگر هم. هدف {{< term "password-hashing" "هش کردن پسورد" >}} (**password hashing**) این است که جدول نشت‌کرده هنوز استفاده‌اش گران باشد. زمینه، login همان API سفارش‌هاست از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/)؛ خطاها و لاگ‌ها مطابق [پیکربندی، لاگ ساخت‌یافته و خطا در Go](/fa/posts/go-config-logging-errors/) هستند.

> فقط دفاعی. این یک برنامه‌ی کوچک Go 1.26 با `golang.org/x/crypto` نسخه‌ی v0.31.0 است که محلی اجرا شد. چیزی را crack نکردم و از هیچ داده‌ی نشت‌کرده‌ی واقعی استفاده نکردم. دمویی جداست و ادامه‌ی دموی قبلی نیست.

## چرا SHA-256 ابزار اشتباهی است

SHA-256 برای سرعت طراحی شده. برای بررسی فایل خوب است؛ برای پسورد بد است، چون مهاجمی که جدول را دزدیده هم سریع می‌خواهد باشد. علاوه بر این قطعی (deterministic) است:

```
sha256 #1 4104d36f8da2c254
sha256 #2 4104d36f8da2c254
```

پسورد برابر، هش برابر می‌دهد؛ پس یک جدول از پیش محاسبه‌شده همه‌ی کاربران را پوشش می‌دهد و هر کسی می‌بیند چه کسانی پسورد مشترک دارند. تعداد SHA-256 در ثانیه را روی این ماشین اندازه نگرفتم: برنامه‌های دیگر آن را پرکرده‌اند و هر عددی گمراه‌کننده می‌شد. به‌طور کلی هش سریع به مهاجم اجازه‌ی حدس‌های بسیار زیاد در ثانیه می‌دهد و هش پسورد بسیار کم؛ این دانش عمومی است، نه اندازه‌گیری من.

{{< term "salt" "salt" >}} مشکل اشتراک را حل می‌کند و تابع عمداً کند مشکل سرعت را. bcrypt و argon2 هر دو را دارند.

## bcrypt

```go
h, _ := bcrypt.GenerateFromPassword([]byte(pw), 10)
err := bcrypt.CompareHashAndPassword(h, []byte(pw))
```

خروجی واقعی برای یک پسورد:

```
bcrypt #1  $2a$10$jv.fkgkg6LQqdoQUxi8XFOPK9TtcOqPqXMfP14OjXZjWjz2756q3S
bcrypt #2  $2a$10$q32SQpWrZBP4b0hDELouMuoRaag8edDnQW.gNPUnganwEl256uk1C
bcrypt c12 $2a$12$mdeSknpMc5r1cNGfd.jCa.xu7piNjrFuqmCXdoS6UBnml0K0akEFy
Cost(h3) = 12
compare ok: <nil>
compare bad: crypto/bcrypt: hashedPassword is not the hash of the given password
```

دو هش از یک پسورد فرق دارند چون {{< term "bcrypt" "bcrypt" >}} یک salt تصادفی می‌سازد و داخل رشته می‌گذارد. قالب `$version$cost$salt+hash` است؛ cost هم داخل رشته است، پس `Compare` فقط به رشته‌ی ذخیره‌شده نیاز دارد. هر پله از cost کار را دو برابر می‌کند.

**محدودیت ۷۲ بایت.** bcrypt فقط ۷۲ بایت اول پسورد را به‌کار می‌برد. این نسخه برای ورودی بلندتر هش نمی‌سازد:

```
73 bytes: bcrypt: password length exceeds 72 bytes
72 bytes: <nil>
72 a's vs 73 a's compare: <nil>
```

خط آخر مرا غافلگیر کرد: هشِ ساخته‌شده از ۷۲ حرف `a`، ۷۳ حرف `a` را در `CompareHashAndPassword` می‌پذیرد، یعنی بررسی بی‌صدا انتها را نادیده می‌گیرد. یا پسورد بلند را هنگام ثبت‌نام رد کنید یا از قبل هش کنید؛ pre-hash را اینجا آزمایش نکردم و مشکلات خودش را دارد (مثلاً بایت NUL در digest خام)، پس کورکورانه کپی نکنید.

## argon2id

{{< term "argon2" "argon2" >}}id سه پارامتر دارد: زمان (تعداد دور)، حافظه (KiB) و threads. هزینه‌ی حافظه حمله با GPU را سخت‌تر می‌کند. هش‌ها را با قالب رایج رشته‌ی PHC ذخیره کردم:

```
argon2id #1 $argon2id$v=19$m=19456,t=1,p=1$R/oNzVeBFwd1WsDpJjMLJg$X58e/1beHxPCFb0hEJ2Rnn/6lZMQjmv0jLjf4I4PrGY
argon2id #2 $argon2id$v=19$m=19456,t=1,p=1$ZhQgiCn7TIbCwgmlenuTsQ$H6BmcgnWq1iaJYGaTRNavg8rHsO8v6NwywoIkOjfayI
```

الگوریتم، نسخه، پارامترها، salt و هش همه در یک رشته‌اند. اعداد من (۱۹ MiB و یک دور) فقط برای دمو هستند؛ راهنمای فعلی OWASP را ببینید و برای سرور خودتان تنظیم کنید. بسته‌ی `argon2` فقط خودِ تابع را می‌دهد، پس کد encode/parse را خودم نوشتم (حدود ۴۰ خط در دمو).

## مقایسه در زمان ثابت

```go
got := argon2.IDKey([]byte(password), salt, p.Time, p.MemKiB, p.Threads, p.KeyLen)
ok := subtle.ConstantTimeCompare(got, want) == 1
```

{{< term "constant-time-comparison" "مقایسه‌ی زمان‌ثابت" >}} از نشت زمانی جلوگیری می‌کند که `==` با توقف در اولین بایت متفاوت ایجاد می‌کند. `CompareHashAndPassword` در bcrypt این کار را خودش می‌کند. نشت زمانی را اندازه نگرفتم.

## Rehash هنگام login

پارامترها کهنه می‌شوند. وقتی آن‌ها را بالا می‌برید، هش‌های قدیمی معتبر می‌مانند؛ پس در تنها لحظه‌ای که پسورد ساده را دارید، یعنی login موفق، ارتقایشان دهید:

```go
func Login(password, stored string, want Params) (ok, rehash bool, err error) {
	ok, have, err := VerifyArgon2id(password, stored)
	if err != nil || !ok { return false, false, err }
	return true, have != want, nil
}
```

فراخواننده با پارامتر جدید دوباره هش می‌کند و ذخیره می‌کند. تست‌ها پارامتر خیلی کوچک (۸ KiB و یک دور) دارند و sleep ندارند:

```
--- PASS: TestSaltMakesHashesDiffer
--- PASS: TestVerify
--- PASS: TestRehashOnLogin
```

بررسی می‌کنند که پسورد اشتباه هرگز rehash را فعال نمی‌کند.

## چند نکته‌ی مهم

- {{< term "pepper" "pepper" >}} (کلید محرمانه بیرون از پایگاه داده که با HMAC وارد می‌شود) وقتی فقط پایگاه داده نشت کند کمک می‌کند. مدیریت کلید اضافه می‌کند؛ آن را توضیح دادم و نساختم.
- هرگز پسورد یا body درخواست login را لاگ نکنید؛ logger و پیام خطاهایتان را بررسی کنید.
- پسوردهای ضعیف با هر الگوریتمی با حدس می‌افتند: فهرستی مثل `123456`، `password` و `qwerty` اول امتحان می‌شود. طول و بررسی پسوردهای افشاشده هنگام ثبت‌نام بیشتر از قواعد ترکیب کمک می‌کند. cracker اجرا نکردم؛ این استدلال است.
- توکن reset: تصادفی، بلند، یک‌بارمصرف، با انقضای کوتاه، و فقط هشش ذخیره شود، مثل پسورد.
- هش کند را می‌شود برای مصرف CPU سوءاستفاده کرد؛ با [rate limiting](/fa/posts/go-rate-limiting-caching/) ترکیبش کنید.

## تمرین

مهاجرت bcrypt به argon2id اضافه کنید: هنگام login اگر هش ذخیره‌شده با `$2` شروع می‌شود، با bcrypt بررسی کنید و بعد هش argon2id ذخیره کنید. تست را با cost برابر ۴ بنویسید تا سریع بماند.

## قدم بعدی

مقاله‌ی بعدی «session یا JWT؟» است.
