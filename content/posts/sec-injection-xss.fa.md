+++
date = '2027-03-07T10:00:00+03:30'
draft = false
title = 'تزریق و XSS'
description = 'تزریق SQL، تزریق دستور، path traversal و XSS در یک دموی کوچک Go روی localhost: کد آسیب‌پذیر، رفتار واقعی و راه‌حل هرکدام.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "injection", "xss", "sql-injection", "appsec", "go"]
cover = { image = "/images/covers/sec-injection-xss.fa.png", alt = "تزریق و XSS", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/)، دسته‌ها را فهرست کرد. این مقاله به خانواده‌ای می‌پردازد که پشت بیشترشان است: ورودی غیرقابل‌اعتماد که با چیزی مخلوط می‌شود که یک مفسر (interpreter) آن را می‌خواند. مفسر می‌تواند Postgres، یک shell، فایل‌سیستم یا مرورگر باشد و باگ همیشه یکی است: داده از یک {{< term "trust-boundary" "مرز اعتماد" >}} (**trust boundary**) رد می‌شود و مثل کد با آن رفتار می‌شود. موضوع باز هم همان API سفارش‌هاست از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/)، این بار با [pgx](/fa/posts/go-postgres-pgx-sqlc/) پشتش.

> فقط دفاعی. هرچه می‌بینید یک برنامه‌ی کوچک Go از خودم روی `127.0.0.1` است، روی یک PostgreSQL 18.3 واقعی با دو جدول موقت (`items` و `secrets`) و با Go 1.26. هیچ هدف شخص ثالثی در کار نیست. این برنامه ادامه‌ی دموی مقاله‌ی قبل نیست و جداست. چیزی را در مرورگر آزمایش نکردم.

هر endpoint دو بار وجود دارد: `/v1/...` آسیب‌پذیر و `/v2/...` اصلاح‌شده.

## تزریق SQL

handler آسیب‌پذیر SQL را با فرمت‌کردن رشته می‌سازد:

```go
q := fmt.Sprintf("SELECT id, name, price FROM items WHERE name = '%s'", name)
```

یک درخواست عادی و بعد payload کلاسیک (با `curl --data-urlencode` و URL-encoded فرستاده شده):

```
$ name=book
[{"id":1,"name":"book","price":1500}]
$ name=' OR '1'='1
[{"id":1,"name":"book","price":1500},{"id":2,"name":"pen","price":200},{"id":3,"name":"lamp","price":4500}]
```

لاگ سرور دلیلش را نشان می‌دهد: کوتیشن رشته را بست و query شد `WHERE name = '' OR '1'='1'`. payload دوم جدول دیگری را می‌خواند، فقط روی داده‌ی دموی خودم:

```
$ name=x' UNION SELECT id, token, 0 FROM secrets --
[{"id":2,"name":"demo-token-BBBB","price":0},{"id":1,"name":"demo-token-AAAA","price":0}]
```

راه‌حل {{< term "parameterized-query" "query پارامتری" >}} (**parameterized query**) است که مقدار جدا از متن SQL می‌رود:

```go
pool.Query(ctx, "SELECT id, name, price FROM items WHERE name = $1", name)
```

`book` هنوز کتاب را برمی‌گرداند و هر دو payload می‌شوند `[]`، چون حالا فقط یک اسم محصول عجیب‌اند که با هیچ ردیفی نمی‌خواند.

**شناسه‌ها پارامتر نمی‌شوند.** `ORDER BY` نام ستون می‌گیرد، نه مقدار. `/v1/sort` آسیب‌پذیر آن را به هم می‌چسباند و یک subquery به‌عنوان کلید مرتب‌سازی پذیرفته شد (query اجرا شد و ردیف‌ها به ترتیب جدول برگشتند). راه‌حل یک allow-list است که انتخاب کاربر را به رشته‌های ثابت نگاشت می‌کند:

```go
var sortable = map[string]string{"name": "name", "price": "price"}
```

`by=price` کار می‌کند و `by=price; DROP TABLE items` جواب `400 bad sort column` می‌گیرد. stored procedure و ORM جادو نیستند: اگر داخلشان SQL را از رشته می‌سازند، همان باگ آنجا هم هست. {{< term "sql-injection" "تزریق SQL" >}} را در واژه‌نامه ببینید.

## تزریق دستور

handler آسیب‌پذیر یک رشته را به shell می‌دهد. از `echo` بی‌خطر استفاده کردم و هیچ ابزار شبکه‌ای نه:

```go
exec.Command("sh", "-c", "echo pinging "+host)
```

```
$ host=x; echo INJECTED
pinging x
INJECTED
```

`;` دستور دومی را شروع کرد. این {{< term "command-injection" "تزریق دستور" >}} (**command injection**) است. راه‌حل بدون shell و با لیست آرگومان است تا ورودی فقط یک آرگومان بماند:

```go
exec.Command("echo", "pinging", host)
```

```
$ host=x; echo INJECTED
pinging x; echo INJECTED
```

## Path traversal

handler فایل آسیب‌پذیر ورودی را به پوشه‌ی `public/` می‌چسباند. فایل `secret.txt` کنار آن و بیرونش است:

```
$ name=hello.txt
hello from public
$ name=../secret.txt
TOP-SECRET-FILE
```

`filepath.Join` مسیر را پاک‌سازی می‌کند و `..` از پوشه بالا می‌رود: این {{< term "path-traversal" "path traversal" >}} است. راه‌حل اول مسیر را absolute می‌کند و پیشوند را چک می‌کند؛ `../secret.txt` می‌شود `403`. اما یک symlink به نام `public/link.txt` هم گذاشتم که به `../secret.txt` اشاره می‌کند و راه‌حل اول آن را تحویل می‌دهد، چون چک روی رشته است، نه روی مقصد symlink. راه‌حل دوم `os.OpenRoot` است (در Go 1.26 وجود دارد):

```go
root, _ := os.OpenRoot("public")
f, err := root.Open(name)
```

```
$ name=hello.txt    -> hello from public
$ name=../secret.txt -> 404, log: path escapes from parent
$ name=link.txt     -> 404, log: path escapes from parent
```

## XSS

صفحه‌ای که با `fmt.Fprintf` ساخته شده ورودی را خام برمی‌گرداند:

```
$ name=<script>alert(1)</script>
<h1>Hello, <script>alert(1)</script></h1>
```

این {{< term "xss" "XSS" >}} (از نوع reflected) است: تگ script داخل بدنه است و مرورگر اجرایش می‌کند. من فقط متن پاسخ را دیدم. با `html/template`:

```
<h1>Hello, &lt;script&gt;alert(1)&lt;/script&gt;</h1>
```

قالب بر اساس زمینه escape می‌کند ({{< term "output-encoding" "output encoding" >}}). یک قالب، ورودی `"><script>alert(1)</script>`:

```
body:  <p>&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</p>
attr:  <a title="&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">x</a>
js:    <script>var n = "\"><script>alert(1)</script>";</script>
url:   <a href="/s?q=%22%3e%3cscript%3ealert%281%29%3c%2fscript%3e">x</a>
```

چهار زمینه، چهار escape متفاوت. stored XSS همین باگ است با یک دیتابیس در میانه: payload ذخیره می‌شود و برای هرکس که صفحه را ببیند اجرا می‌شود.

دو هدر دامنه‌ی خسارت را کم می‌کنند، با `curl -i` (رفتار مرورگر را بررسی نکردم):

```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'
Set-Cookie: session=demo; Path=/; HttpOnly; Secure; SameSite=Lax
```

{{< term "content-security-policy" "Content Security Policy" >}} منبع اسکریپت را محدود می‌کند و {{< term "httponly" "HttpOnly" >}} کوکی را از JavaScript صفحه پنهان می‌کند. هیچ‌کدام جای escape را نمی‌گیرند.

درباره‌ی Node چیزی اجرا نکردم. template literal (`` `<h1>${name}</h1>` ``) اصلاً escape نمی‌کند و مثل `Fprintf` رفتار می‌کند. از موتور قالبی استفاده کنید که پیش‌فرض escape می‌کند و در `pg` از پارامتر (`$1`) استفاده کنید، مثل [Postgres از Node.js با pg](/fa/posts/node-postgres-pg/) و [سرور HTTP با node:http](/fa/posts/node-http-server/).

## چند نکته‌ی مهم

- blocklist ("کوتیشن را حذف کن") شکست می‌خورد؛ به‌جای تمیزکردن، داده را از کد جدا کنید.
- ورودی کاربر را هرگز در `sh -c` نگذارید؛ به‌جای اجرای برنامه از یک کتابخانه استفاده کنید.
- خطایی که SQL را برمی‌گرداند به مهاجم کمک می‌کند؛ لاگ کنید و پیام کلی بدهید، مثل [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/).
- موقع خروجی و برای همان زمینه escape کنید؛ به "روی ورودی تمیز شده" اعتماد نکنید.
- rate limit تزریق را حل نمی‌کند، [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/) را ببینید.

## تمرین

یک endpoint به نام `/v1/search` اضافه کنید که از `LIKE '%` + ورودی + `%'` استفاده کند. آن را بشکنید، بعد با پارامتر درستش کنید (`$1` با `"%" + input + "%"`). کدام کاراکترها هنوز wildcard هستند و آیا این مشکل امنیتی است؟

## قدم بعدی

مقاله‌ی بعدی ذخیره‌ی امن پسورد: argon2 و bcrypt است.
