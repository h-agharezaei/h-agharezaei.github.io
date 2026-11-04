+++
date = '2027-03-07T10:00:00+03:30'
draft = false
title = 'تزریق و XSS'
description = 'تزریق SQL، تزریق دستور، path traversal و XSS در یک دموی کوچک Go روی localhost: کد آسیب‌پذیر، رفتار واقعی و راه‌حل هرکدام.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "injection", "xss", "sql-injection", "appsec", "go"]
cover = { image = "/images/covers/sec-injection-xss.fa.png", alt = "تزریق و XSS", hiddenInSingle = true }
+++

یک فرم ورود یا یک کادر جست‌وجوی محصول را تصور کنید. پشت آن، سرور یک کوئری SQL را با چسباندن چیزی که شما تایپ کرده‌اید به یک رشته می‌سازد. `book` بنویسید، کتاب را می‌گیرید. `' OR '1'='1` بنویسید، همه‌ی ردیف‌های جدول را می‌گیرید. برنامه خراب نشده؛ دقیقاً همان کاری را کرده که رشته گفته، و رشته را بخشی غریبه نوشته بود.

کل ایده‌ی پشت این دسته از باگ‌ها، که اسمش تزریق (injection) است، همین است. برنامه متنی را برای یک مفسر می‌فرستد (دیتابیس، shell، فایل‌سیستم یا مرورگر) و بخشی از این متن از منبع غیرقابل‌اعتماد آمده است. اگر مفسر نتواند تشخیص دهد دستورهای خود برنامه کجا تمام می‌شود و داده‌ی کاربر کجا شروع، داده‌ی کاربر تبدیل به دستور می‌شود. ورودی از یک {{< term "trust-boundary" "مرز اعتماد" >}} گذشته و مثل کد با آن رفتار می‌شود. [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/) فقط اسم این خانواده را آورد (A05 در جدولش). این‌جا برای هر عضوش یک دمو دارم، روی یک API شبیه سفارش مثل [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) و با [Postgres از طریق pgx](/fa/posts/go-postgres-pgx-sqlc/) پشتش.

> فقط دفاعی. همه‌ی مثال‌های زیر یک برنامه‌ی کوچک Go از خودم روی `127.0.0.1` است، روی PostgreSQL 18.3 واقعی با دو جدول دورانداختنی (`items` و `secrets`، با داده‌ی ساختگی). هیچ هدف شخص ثالثی در کار نیست. این برنامه ادامه‌ی دموی مقاله‌ی قبل نیست؛ جداست. چیزی را در مرورگر امتحان نکردم. همه‌ی خروجی‌های زیر را دوباره با Go 1.27 اجرا کردم (اجرای اول با Go 1.26 بود)، با سرور روی یک پورت تصادفی آزاد به‌جای پورت ثابت برنامه؛ برای همین دستورهای زیر فقط مسیرها و پارامترها را نشان می‌دهند.

هر endpoint دو بار وجود دارد. `/v1/...` نسخه‌ی آسیب‌پذیر است و `/v2/...` نسخه‌ی اصلاح‌شده، تا بتوانید یک درخواست را به هر دو بفرستید و مقایسه کنید.

## SQL injection

handler آسیب‌پذیر SQL را با قالب‌بندی رشته می‌سازد:

```go
q := fmt.Sprintf("SELECT id, name, price FROM items WHERE name = '%s'", name)
```

`name` کاربر بین دو کوتیشن گذاشته می‌شود. تا وقتی `name` کوتیشن نداشته باشد همه‌چیز خوب است. اول یک درخواست عادی و بعد payload کلاسیک (`curl --data-urlencode` کدگذاری URL را انجام می‌دهد):

```
$ name=book
[{"id":1,"name":"book","price":1500}]
$ name=' OR '1'='1
[{"id":1,"name":"book","price":1500},{"id":2,"name":"pen","price":200},{"id":3,"name":"lamp","price":4500}]
```

درخواست دوم همه‌ی ردیف‌ها را برگرداند. لاگ سرور دلیلش را نشان می‌دهد. بعد از پر شدن رشته، کوئری این شکل را داشت:

```
SELECT id, name, price FROM items WHERE name = '' OR '1'='1'
```

کوتیشن داخل payload رشته را زودتر بست، `OR '1'='1'` بخشی از SQL شد و `'1'='1'` همیشه درست است. دیتابیس راهی نداشت بفهمد نیمی از این متن قرار بود فقط یک مقدار ساده باشد.

payload دوم جلوتر می‌رود و جدول دیگری را می‌خواند. همان اصل است: `UNION SELECT` ردیف‌های یک جدول دیگر را به نتیجه می‌چسباند و `--` بقیه‌ی کوئری اصلی را به کامنت تبدیل می‌کند. این فقط روی داده‌ی ساختگی خودم است:

```
$ name=x' UNION SELECT id, token, 0 FROM secrets --
[{"id":2,"name":"demo-token-BBBB","price":0},{"id":1,"name":"demo-token-AAAA","price":0}]
```

این‌ها توکن‌های ساختگی جدول `secrets` هستند که به‌جای نام محصول آمده‌اند. یک کادر جست‌وجو جدولی را لو داد که قرار نبود به آن دست بزند.

راه‌حل {{< term "parameterized-query" "کوئری پارامتری" >}} (parameterized query) است. متن SQL و مقدار جداگانه به دیتابیس می‌رسند، پس دیتابیس از همان اول می‌داند `$1` یک مقدار است و هرگز کد نیست:

```go
pool.Query(ctx, "SELECT id, name, price FROM items WHERE name = $1", name)
```

حالا `book` هنوز کتاب را برمی‌گرداند. هر دو payload `[]` برمی‌گردانند، چون دیگر SQL نیستند؛ فقط یک نام محصول عجیب‌اند که با هیچ‌چیز نمی‌خواند.

**شناسه‌ها را نمی‌شود پارامتر کرد.** پارامتر می‌تواند جای یک مقدار بنشیند، نه جای نام یک ستون. `ORDER BY` نام ستون می‌گیرد، پس `/v1/sort` آسیب‌پذیر ناچار آن را الحاق می‌کند:

```go
q := "SELECT id, name, price FROM items ORDER BY " + by
```

یک زیرکوئری هم به‌عنوان کلید مرتب‌سازی پذیرفته می‌شود: `by=(select 1)` اجرا می‌شود و ردیف‌ها را به ترتیب جدول برمی‌گرداند، که ثابت می‌کند ورودی به‌عنوان SQL خوانده می‌شود. (payload کلاسیک `by=price; DROP TABLE items` این‌جا کار نکرد، ولی نه چون کد امن است: pgx هر بار یک دستور می‌فرستد و Postgres جواب داد `cannot insert multiple commands into a prepared statement`، پس handler `query failed` برگرداند. به جزئیات driver برای محافظت از یک جدول تکیه نمی‌کنم.)

راه‌حل ستون مرتب‌سازی یک allow-list است که انتخاب کاربر را به یک رشته‌ی ثابت نگاشت می‌کند، پس ورودی هرگز به کوئری نمی‌رسد:

```go
var sortable = map[string]string{"name": "name", "price": "price"}
```

`by=price` بر اساس قیمت مرتب می‌کند؛ `by=price; DROP TABLE items` جواب `400 bad sort column` می‌گیرد.

stored procedure و ORM جادو نیستند. اگر داخلشان SQL را با رشته بسازند، همین باگ آن‌جا هم هست. مدخل واژه‌نامه‌ی {{< term "sql-injection" "SQL injection" >}} خلاصه‌اش را دارد.

## Command injection

گاهی یک برنامه باید برنامه‌ی دیگری را اجرا کند. handler آسیب‌پذیر یک رشته را به shell می‌دهد که آن را parse می‌کند. من از یک `echo` بی‌ضرر استفاده کردم، نه ابزار شبکه:

```go
exec.Command("sh", "-c", "echo pinging "+host)
```

```
$ host=x; echo INJECTED
pinging x
INJECTED
```

`;` جداکننده‌ی دستورها در shell است، پس `host` یک دستور دوم هم داد و shell اجرایش کرد. این {{< term "command-injection" "command injection" >}} است: خط دوم خروجی یک دستور کامل اضافه است که کاربر انتخاب کرده. راه‌حل این است که اصلاً shell نباشد و آرگومان‌ها به‌صورت فهرست داده شوند. آن‌وقت ورودی همیشه یک آرگومان است، هر نویسه‌ای که داشته باشد:

```go
exec.Command("echo", "pinging", host)
```

```
$ host=x; echo INJECTED
pinging x; echo INJECTED
```

همان ورودی، این بار به‌صورت متن ساده در یک خط چاپ شد و `;` فقط یک نویسه است.

## Path traversal

سومین مفسر فایل‌سیستم است. handler آسیب‌پذیر فایل، `name` کاربر را به پوشه‌ی `public/` می‌چسباند. کنار آن پوشه، بیرونش، فایلی به اسم `secret.txt` هست:

```
$ name=hello.txt
hello from public
$ name=../secret.txt
TOP-SECRET-FILE
```

`..` یعنی «پوشه‌ی والد» و `filepath.Join` مسیر را تمیز می‌کند، پس `public/../secret.txt` می‌شود `secret.txt` و handler با آرامش از `public/` بیرون می‌رود. این {{< term "path-traversal" "path traversal" >}} است.

راه‌حل ۱ مسیر را مطلق می‌کند و بررسی می‌کند هنوز با پوشه‌ی `public` شروع می‌شود. حالا `../secret.txt` جواب `403` می‌گیرد. اما من یک symlink هم در پوشه گذاشتم، `public/link.txt` که به `../secret.txt` اشاره می‌کند. راه‌حل ۱ باز هم آن را سرو می‌کند، چون بررسی‌اش به رشته نگاه می‌کند، نه به جایی که symlink به آن می‌رود.

راه‌حل ۲ از `os.OpenRoot` استفاده می‌کند که یک پوشه را به‌عنوان ریشه‌ای باز می‌کند که برنامه نمی‌تواند از آن بیرون برود (از Go 1.24 اضافه شده):

```go
root, _ := os.OpenRoot("public")
f, err := root.Open(name)
```

```
$ name=hello.txt     -> hello from public
$ name=../secret.txt -> 404, log: path escapes from parent
$ name=link.txt      -> 404, log: path escapes from parent
```

هر دو تلاش برای فرار شکست می‌خورد، از جمله symlink. کلاینت یک 404 ساده می‌گیرد و دلیلش در لاگ سرور می‌ماند.

## XSS

آخرین مفسر مرورگر است. صفحه‌ای که با `fmt.Fprintf` ساخته شود ورودی را خام برمی‌گرداند:

```
$ name=<script>alert(1)</script>
<h1>Hello, <script>alert(1)</script></h1>
```

این {{< term "xss" "XSS" >}} (cross-site scripting) از نوع reflected است: تگ `<script>` حالا بخشی از صفحه است، پس مرورگر اجرایش می‌کند. اگر صفحه از طریق یک لینک به قربانی نشان داده شود، اسکریپت با اختیارهای همان سایت اجرا می‌شود. من فقط متن پاسخ را نگاه کردم؛ در مرورگر بازش نکردم. با `html/template`:

```
<h1>Hello, &lt;script&gt;alert(1)&lt;/script&gt;</h1>
```

`<` و `>` شدند `&lt;` و `&gt;` که مرورگر به‌جای تگ، به‌صورت متن نشان می‌دهد. template این escape را بر اساس زمینه (context) انجام می‌دهد ({{< term "output-encoding" "output encoding" >}})، و زمینه مهم است چون یک متن در جاهای مختلف escape متفاوتی می‌خواهد. یک template با چهار زمینه و ورودی `"><script>alert(1)</script>`:

```
body:  <p>&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</p>
attr:  <a title="&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">x</a>
js:    <script>var n = "\"><script>alert(1)</script>";</script>
url:   <a href="/s?q=%22%3e%3cscript%3ealert%281%29%3c%2fscript%3e">x</a>
```

چهار زمینه، چهار escape متفاوت. در body و attribute نویسه‌ها به HTML entity تبدیل می‌شوند؛ داخل اسکریپت رشته به روش JavaScript escape می‌شود (شکل‌های `<`)؛ و در URL درصد‌کدگذاری می‌شوند. (روی Go 1.27 خط script همان‌طور که بالا آمده escape می‌شود؛ در اجرای اول این مقاله `<` و `>` آن‌جا escape نشده بودند. دلیلش را پیدا نکردم و خروجی اجرای دوباره را نشان می‌دهم.)

Stored XSS همین باگ است با یک دیتابیس در میانه: payload ذخیره می‌شود، مثلاً در یک نظر، و برای هر کسی که صفحه را ببیند اجرا می‌شود.

دو هدر پاسخ وقتی escape جایی شکست بخورد خسارت را محدود می‌کنند. با `curl -i` نشان داده شده‌اند (رفتار مرورگر را بررسی نکردم؛ دمو `X-Content-Type-Options: nosniff` هم می‌گذارد که درباره‌اش حرفی نمی‌زنم):

```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'
Set-Cookie: session=demo; Path=/; HttpOnly; Secure; SameSite=Lax
```

{{< term "content-security-policy" "Content Security Policy" >}} به مرورگر می‌گوید به کدام منبع‌های اسکریپت اعتماد کند و {{< term "httponly" "HttpOnly" >}} کوکی را از JavaScript صفحه پنهان می‌کند. هیچ‌کدام جای escape را نمی‌گیرند. این‌ها خط دفاعی دوم‌اند.

سمت Node چیزی اجرا نکردم. template literalها (`` `<h1>${name}</h1>` ``) هیچ escapeی نمی‌کنند، پس مثل `Fprintf` رفتار می‌کنند. از template engineی استفاده کنید که پیش‌فرض escape می‌کند، و در `pg` از پارامتر (`$1`) استفاده کنید، مثل [Postgres از Node.js با pg](/fa/posts/node-postgres-pg/) و [سرور HTTP با node:http](/fa/posts/node-http-server/).

## تله‌های دفاع

- **blocklist شکست می‌خورد.** «کوتیشن را حذف کن» یا «کلمه‌ی DROP را رد کن» همیشه یک حالت را از دست می‌دهد. به‌جای تمیز کردن داده، داده را از کد جدا کنید.
- **ورودی کاربر را هرگز در `sh -c` نگذارید.** آرگومان‌ها را به‌صورت فهرست بدهید و وقتی یک کتابخانه کار را انجام می‌دهد، به‌جای اجرای یک برنامه از آن استفاده کنید.
- **خطایی که SQL را برمی‌گرداند به مهاجم کمک می‌کند.** لاگش کنید و پیام عمومی برگردانید، مثل [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/).
- **هنگام خروجی، و برای همان زمینه، escape کنید.** «ورودی را sanitize کرده‌ایم» وقتی همان مقدار جای دیگری نشان داده شود کمکی نمی‌کند.
- **rate limit تزریق را درست نمی‌کند.** سرعت یک نفر را کم می‌کند، نه معنای کوئری را عوض. ببینید [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/) به چه دردی می‌خورد.

## تمرین

یک endpoint به اسم `/v1/search` اضافه کنید که از `LIKE '%` + input + `%'` استفاده کند. بشکنیدش و بعد با پارامتر درستش کنید (`$1` با `"%" + input + "%"`). کدام نویسه‌ها هنوز wildcard هستند، و آیا این مشکل امنیتی است؟

## قدم بعدی

مقاله‌ی بعد «ذخیره‌ی امن پسورد: argon2 و bcrypt» است. از جایی شروع می‌کند که تزریقی کار کرده و کسی جدول `users` شما را خوانده است: آن جدول چه چیزی باید داشته باشد تا پسوردها امن بمانند؟
