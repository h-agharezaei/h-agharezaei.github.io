+++
date = '2027-04-30T10:00:00+03:30'
draft = false
title = 'مدیریت راز و کلید'
description = 'مدیریت راز در Go: نشت در تاریخچه‌ی git، لاگ، env و ps، اسکنر، بارگذاری fail-closed، تکرار nonce در AES-GCM و رمزنگاری پاکتی با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "secrets", "encryption", "key-management", "git", "go"]
cover = { image = "/images/covers/sec-secrets-management.fa.png", alt = "مدیریت راز و کلید", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [TLS و گواهی x509 در عمل](/fa/posts/sec-tls-x509-certificates/)، با «کلید را از مخزن دور نگه دارید» تمام شد. این مقاله درباره‌ی این است که رازها با این حال چطور فرار می‌کنند و چطور باید آن‌ها را بارگذاری و استفاده کرد. روی [پیکربندی، لاگ ساخت‌یافته و خطا در Go](/fa/posts/go-config-logging-errors/) بنا شده است؛ ذخیره‌ی رمز عبور مقاله‌ی جدا دارد، [ذخیره‌ی امن رمز عبور](/fa/posts/sec-password-hashing/)، و کلید امضا در [سشن یا JWT؟](/fa/posts/sec-sessions-vs-jwt/) آمده است.

> فقط دفاعی. همه‌ی رازهای زیر آشکارا جعلی‌اند و همه‌چیز محلی با Go 1.26 و git اجرا شد. gitleaks، trufflehog، `git filter-repo`، Vault و KMS ابری را اجرا نکردم و فقط توضیح داده شده‌اند. مسیرها به `<tmp>` کوتاه شده‌اند.

## git یادش می‌ماند

یک مخزن یک‌بارمصرف ساختم، یک `config.env` جعلی commit کردم و در commit بعدی پاکش کردم:

```
$ git log --all --oneline --name-only -S AKIAFAKEFAKEFAKE1234
69a28b5 remove secrets from the repo
config.env
fefecea add config
config.env
$ git show HEAD~1:config.env      (masked by me)
AWS_ACCESS_KEY_ID=AKIA****
DB_PASSWORD=hunt****
```

working tree تمیز است، تاریخچه نه. بعد از یک نشت واقعی: **اول بچرخانید**، چون راز همین حالا کپی شده؛ بعد تاریخچه را بازنویسی کنید (معمولاً با `git filter-repo`، که اینجا نصب نبود و اجرا نشد)؛ و بعد پیشگیری کنید.

`.gitignore` برای فایلی که قبلاً tracked شده کاری نمی‌کند (`new.env` با وجود `*.env` در `git ls-files` ماند). یک {{< term "git-hook" "هوک pre-commit" >}}، اسکریپت shell خودم که diff مرحله‌بندی‌شده را grep می‌کند، بقیه را می‌بندد:

```
pre-commit: staged changes look like they contain a secret; commit blocked
exit status: 1
```

`--no-verify` آن را رد می‌کند، پس حفاظ است نه دیوار.

## یک اسکنر کوچک

{{< term "secret-scanning" "اسکن راز" >}} همین ایده روی کل تاریخچه است. اسکنر من حدود ۵۰ خط است: دو regex به‌اضافه‌ی {{< term "shannon-entropy" "آنتروپی شانون" >}} بالای ۴٫۲ بیت در هر نویسه برای توکن‌های بلند. روی مخزن نشت‌دار (match ها پوشانده شده):

```
line 13  aws-access-key-id  AKIA****
line 14  assigned-secret    PASS****
line 28  aws-access-key-id  AKIA****
line 29  assigned-secret    PASS****
scanned 36 lines, 4 findings
```

روی یک مخزن تمیز با یک خط `go.sum`، یک hash از commit و یک جمله‌ی README درباره‌ی رمز عبور:

```
line 22  high-entropy       Zk3k**** (5.24 bits/char)
scanned 22 lines, 1 findings
```

checksum ماژول هشدار اشتباه است؛ hash ۴۰ رقمی hex زیر آستانه ماند. آستانه را پایین بیاورید غرق نویز می‌شوید، بالا ببرید کلید واقعی را از دست می‌دهید.

## لاگ، خطا، محیط، آرگومان

لاگر JSON هر چه بدهید چاپ می‌کند. چهار حالت:

```
{"token":"tok_FAKE_0123456789abcdef"}                  plain
{"token":"[REDACTED]"}                                 ReplaceAttr by key "token"
{"tok":"tok_FAKE_0123456789abcdef"}                    ReplaceAttr, key named "tok"
{"tok":"[REDACTED]"}                                   type Secret with LogValue
```

پنهان‌سازی بر اساس نام کلید نام‌های دیگر را از دست می‌دهد. نوع `Secret` با متد `LogValue` (و `String`) هر جا برود پنهان می‌کند، حتی در `fmt %v`. خطا هم همین‌طور نشت می‌کند: `connect failed: dsn=postgres://app:FAKE-db-pass-123@...` شد `connect failed: host=127.0.0.1:5432 user=app`.

یک {{< term "environment-variable" "متغیر محیطی" >}} به فرزندان ارث می‌رسد و آرگومان‌ها عمومی‌اند:

```
inherited: child sees FAKE_DEMO_SECRET = FAKE-env-value-123
explicit:  child sees FAKE_DEMO_SECRET =
ps args:    <tmp>/demo wait --api-key=FAKE-cli-key-456
ps eww:     FAKE_DEMO_SECRET=FAKE-env-value-123
```

برای فرزندان `cmd.Env` را صریح بدهید. `ps eww` در macOS محیط پروسه‌ی فرزند خودم را نشان داد؛ Linux را امتحان نکردم، معادلش `/proc/<pid>/environ` است.

## بارگذاری رازها

باگی که بیشتر می‌بینم یک مقدار پیش‌فرض است:

```
bad fallback:  key="dev-secret"
fail closed:   FAKE_SIGNING_KEY is not set
```

متغیر نبود و بی‌صدا کلید شناخته‌شده شد. به‌جایش هنگام شروع شکست بخورید. قرارداد `NAME_FILE` مقدار را از فایل می‌خواند و من mode آن را بررسی می‌کنم:

```
mode 0644:     db_password has mode 0644, want 0600 or stricter
mode 0600:     value="FAKE-file-secret" err=<nil>
```

مدیر رازها (Vault، KMS ابری) audit و چرخش اضافه می‌کنند؛ هیچ‌کدام را اجرا نکردم.

## رمزنگاری با کلید

{{< term "aes-gcm" "AES-256-GCM" >}} یک {{< term "nonce" "nonce" >}} یکتا می‌خواهد. یک nonce صفر را برای دو پیام جعلی بی‌ضرر دوباره به کار بردم:

```
same nonce: c1^c2 == p1^p2 ? true
knowing p1, p2 = "pay mallory 999 US"
```

دانستن یک plaintext دیگری را لو می‌دهد. هر بار از `crypto/rand` استفاده کنید.

در {{< term "envelope-encryption" "رمزنگاری پاکتی" >}} هر رکورد کلید داده‌ی تصادفی دارد که با کلید اصلی بسته‌بندی شده و شناسه‌ی کلید کنارش ذخیره می‌شود. {{< term "key-rotation" "چرخش" >}} فقط کلید کوچک بسته‌بندی‌شده را دوباره می‌بندد:

```
stored key id: kek-1  wrapped DEK bytes: 60  data bytes: 50
after rewrap:  kek-2  data unchanged: true
old record, kek-1 retired: unknown key id kek-1
rewrapped record: "card-last4=0000 (fake)" err=<nil>
wrong record id (AAD): cipher: message authentication failed
```

شناسه‌ی رکورد به‌عنوان داده‌ی اضافه از جابه‌جایی متن رمزشده بین ردیف‌ها جلوگیری می‌کند. رازها را با `subtle.ConstantTimeCompare` ({{< term "constant-time-comparison" "مقایسه‌ی زمان‌ثابت" >}}) مقایسه کنید. پاک کردن حافظه در Go قابل اتکا نیست (garbage collector ممکن است مقدارها را کپی کند)، پس قولش را نمی‌دهم.

## چند نکته‌ی مهم

- بعد از نشت اول بچرخانید؛ حذف commit کافی نیست.
- هرگز برای راز مقدار پیش‌فرض نگذارید؛ هنگام شروع شکست بخورید.
- بر اساس نوع پنهان کنید، نه نام کلید.
- فایل با 0600 را به متغیر و آرگومان ترجیح دهید.
- کنار هر متن رمزشده شناسه‌ی کلید نگه دارید.

## تمرین

به اسکنر گزینه‌ی `--history` اضافه کنید که commit هر یافته را چاپ کند، و یک allowlist برای هشدار اشتباه `go.sum`.

## قدم بعدی

مقاله‌ی بعدی «زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها» است.
