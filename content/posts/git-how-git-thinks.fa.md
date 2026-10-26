+++
date = '2026-10-28T10:00:00+03:30'
draft = false
title = 'گیت چطور فکر می‌کند: object و hash'
description = 'نحوه‌ی ذخیره‌ی داده در گیت: blob، tree و commit، هش محتوا، فایل‌های loose فشرده با zlib و ساخت دستی یک commit با دستورهای plumbing.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "objects", "internals"]
cover = { image = "/images/covers/git-how-git-thinks.fa.png", alt = "گیت چطور فکر می‌کند: object و hash", hiddenInSingle = true }
+++

بیشتر ما گیت را مثل فهرستی از دستورها یاد می‌گیریم و اولین باری که یک rebase خراب می‌شود می‌ترسیم. این اولین مقاله از یک سری ده‌تایی درباره‌ی گیت است و از پایین‌ترین لایه شروع می‌کند: گیت چیزها را چطور ذخیره می‌کند. وقتی این را بدانید، `commit` و `branch` و `rebase` دیگر جادو نیستند. این وبلاگ سری‌های دیگری هم دارد (Go، Rust و NATS JetStream)، اما این سری درباره‌ی ابزاری است که همه هر روز با آن کار می‌کنیم.

> همه‌ی دستورهای زیر با git نسخه‌ی 2.39.2 در یک repository موقت اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند. نام نویسنده و تاریخ با متغیرهای محیطی ثابت شده تا هش‌ها تکرارپذیر باشند.

## ذخیره‌سازی بر اساس محتوا

گیت در هسته‌اش یک key-value store است. value یک محتواست و key هش آن محتوا (به‌طور پیش‌فرض {{< term "sha-1" "SHA-1" >}}). محتوای یکسان کلید یکسان می‌دهد و محتوای متفاوت کلید متفاوت:

```bash
echo 'hello'  | git hash-object --stdin
echo 'hello'  | git hash-object --stdin
echo 'hello!' | git hash-object --stdin
```

```text
ce013625030ba8dba906f756967f9e9ca394464a
ce013625030ba8dba906f756967f9e9ca394464a
4effa19f4f75f846c3229b9dbdbad14eff362f32
```

با `-w` گیت محتوا را در `.git/objects` می‌نویسد و بعد می‌شود پرسید این چیست:

```bash
H=$(echo 'hello' | git hash-object -w --stdin)
git cat-file -t $H   # نوع
git cat-file -s $H   # اندازه
git cat-file -p $H   # نمایش محتوا
```

```text
blob
6
hello
```

## یک loose object فقط یک فایل فشرده است

این object در فایلی ذخیره شده که اسمش همان هش است و بعد از دو کاراکتر اول به پوشه و فایل شکسته شده:

```text
.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a
```

فایل با zlib فشرده شده. اگر با یک قطعه کد کوچک پایتون بازش کنیم، قالب واقعی دیده می‌شود: نوع، یک فاصله، اندازه، یک بایت NUL و بعد محتوا.

```bash
python3 -c "import zlib;print(repr(zlib.decompress(open('.git/objects/ce/013625030ba8dba906f756967f9e9ca394464a','rb').read())))"
```

```text
b'blob 6\x00hello\n'
```

هش روی کل همین رشته، با header، حساب می‌شود. ببینید چه چیزی نیست: نه اسم فایل، نه تاریخ. فقط محتوا کلید را تعیین می‌کند.

## سه نوع object

هر {{< term "git-object" "Git object" >}} از چند نوع است که الان سه‌تایش مهم‌اند:

- **{{< term "blob" "blob" >}}** فقط محتوای یک فایل است.
- **{{< term "git-tree" "tree" >}}** یک پوشه است: فهرستی از نام، mode و هش که به blobها یا treeهای دیگر اشاره می‌کند.
- **{{< term "commit" "commit" >}}** به یک tree (همان snapshot) اشاره می‌کند، به‌علاوه‌ی parentها، author، committer و پیام.

## ساختن دستی یک commit

دستورهای روزمره (`add` و `commit`) از دستورهای سطح پایین‌تر **{{< term "plumbing" "plumbing" >}}** ساخته شده‌اند. ما فقط از همین‌ها استفاده می‌کنیم. بعد از گذاشتن `hello.txt` و `src/main.go` در index:

```bash
git update-index --add hello.txt src/main.go
T=$(git write-tree)
git cat-file -p $T
```

```text
100644 blob ce013625030ba8dba906f756967f9e9ca394464a	hello.txt
040000 tree b9270df7070cc6a5e7dbdec610a7ce4f54c47b20	src
```

شناسه‌ی این tree برابر `337d9a8` شد. حالا یک commit و یک branch که به آن اشاره کند:

```bash
C1=$(echo 'first commit' | git commit-tree $T)
git update-ref refs/heads/main $C1
git cat-file -p $C1
git log --oneline
```

```text
tree 337d9a8168ca5a97d9d3d9e24a6fe18e4a5cf75c
author Roham <roham@example.com> 1793169000 +0330
committer Roham <roham@example.com> 1793169000 +0330

first commit
c6c5da0 first commit
```

branch فقط یک فایل است که هش یک commit را نگه می‌دارد؛ برای همین ساختنش آنی است. index و `update-index` موضوع مقاله‌ی بعد است.

## تاریخچه یک گراف است

یک commit دوم روی `main` ساختم که با `-p $C1` والدش را مشخص کرده بود، و یک commit سوم روی branch به اسم `side` از همان والد:

```text
* 66ddd7b second commit
| * 8798212 side work
|/  
* c6c5da0 first commit
```

هر commit به والدهایش اشاره می‌کند، نه برعکس. دنبال کردن این اشاره‌ها یک **{{< term "dag" "DAG" >}}** می‌سازد: گراف جهت‌دار بدون دور. commit مرج هم فقط commitی است که دو والد دارد.

## چرا تاریخچه تغییرناپذیر است

هر commit هش والدش را در خودش دارد، پس تغییر هر چیز بالادستی همه‌ی پایین‌دستی‌ها را عوض می‌کند. برای commit دوم دو بار با همان tree و همان پیام commit ساختم، و بار دوم commit اول را با پیام دیگری دوباره ساختم:

```text
original:  A=5dbfa36  B=dc8cab0
rewritten: A=2cfd71a  B=23bdee6
```

`B` در هر دو بار محتوا و پیام یکسان دارد، اما چون والدش عوض شده هشش هم عوض شد. پس «بازنویسی تاریخچه» هیچ چیزی را ویرایش نمی‌کند؛ commitهای جدید می‌سازد و branch را به آن‌ها منتقل می‌کند و commitهای قدیمی تا garbage collection در پایگاه object می‌مانند. به همین دلیل rebase هش همه‌ی commitهای بعد از نقطه‌ی ویرایش را عوض می‌کند.

## SHA-1 و SHA-256

گیت به‌طور پیش‌فرض از SHA-1 (۴۰ کاراکتر hex) استفاده می‌کند. git من `git init --object-format=sha256` را پشتیبانی می‌کند و همان blob با محتوای `hello\n` آنجا شناسه‌ی ۶۴ کاراکتری می‌گیرد:

```text
2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4
```

طبق مستندات گیت، repositoryهای SHA-256 با SHA-1 سازگار نیستند، پس فعلاً برای کار عادی به آن‌ها تکیه نمی‌کنم. push یا میزبانی این repositoryها را امتحان نکرده‌ام.

## چند نکته‌ی مهم

- هش، header و محتوا را پوشش می‌دهد؛ پس بایت‌های یکسان روی هر ماشین یک object یکسان‌اند.
- commit یک snapshot (یک tree) را نگه می‌دارد، نه یک diff. diff در لحظه‌ی درخواست محاسبه می‌شود.
- نام فایل در tree است نه در blob، پس دو فایل با محتوای یکسان یک blob مشترک دارند.
- branch و tag فقط اشاره‌گر به commit هستند و برای همین ارزان‌اند.
- خارج از یک repository آزمایشی، `.git/objects` را دستی ویرایش نکنید.

## تمرین

در یک پوشه‌ی موقت `git init` بزنید، با `git hash-object -w` یک blob، با `git mktree` یا index یک tree و با `git commit-tree` یک commit بسازید. با `git update-ref` یک branch به آن اشاره دهید و `git log` را ببینید. بعد یکی از objectها را با پایتون باز کنید و header آن را پیدا کنید.

## قدم بعدی

مقاله‌ی بعد «index و staging: سه ناحیه‌ی گیت» است؛ آنجا می‌بینیم `git add` واقعاً چه کار می‌کند.
