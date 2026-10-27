+++
date = '2027-05-31T10:00:00+03:30'
draft = false
title = 'لاگ، audit و واکنش به حادثه'
description = 'لاگ امنیتی در Go: فیلدهای audit، تست redaction، log injection، لاگ زنجیره‌ی hash، قاعده‌های تشخیص با precision و recall و یک runbook.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "logging", "audit", "incident-response", "go"]
cover = { image = "/images/covers/sec-logging-audit-incident-response.fa.png", alt = "لاگ، audit و واکنش به حادثه", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [fuzzing برای پیدا کردن باگ امنیتی](/fa/posts/sec-fuzzing/)، پیش از مهاجم دنبال باگ می‌گشت. بعضی باز هم رد می‌شوند و آن‌وقت باید بتوانید بفهمید چه شد. برای سازوکار لاگ [لاگ‌ها و journalctl](/fa/posts/linux-logs-journalctl/) را ببینید.

> فقط دفاعی. کد Go 1.26 خودم، رویدادهای تولیدشده، نشانی‌های بازه‌ی مستندات و کاربران ساختگی. مثال محلی.

## سه نوع لاگ

لاگ برنامه برای توسعه‌دهنده است؛ لاگ امنیتی رویدادهایی مثل ورود ناموفق را ثبت می‌کند. {{< term "audit-log" "audit log" >}} جواب می‌دهد چه کسی، چه کاری، روی چه چیزی، کی، از کجا و با چه نتیجه‌ای. فیلدها: actor، action، resource، outcome، شناسه‌ی درخواست، IP مبدأ و زمان UTC. با `log/slog` ([پیکربندی، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/)):

```
{"time":"2027-05-30T09:15:00Z","level":"INFO","msg":"audit","actor":"alice","action":"order.cancel","resource":"order/1042","outcome":"denied","request_id":"req-7f3a","source_ip":"198.51.100.23"}
```

## چه چیزی را لاگ نکنیم

گذرواژه، توکن، شناسه‌ی نشست ([نشست یا JWT؟](/fa/posts/sec-sessions-vs-jwt/))، شماره‌ی کامل کارت و داده‌ی شخصی اضافه. پاک‌سازی بر اساس نام کلید کافی نیست، پس تستی داریم که با لو رفتن راز شکست می‌خورد. فیلد بی‌دقت `note` یک توکن و یک شماره‌ی کارت داشت:

```
--- FAIL: TestNoSecretsLeak (0.00s)
    secrets leaked into the log: [tok_9f8e7d6c5b4a3921 4111111111111111]
    {"level":"INFO","msg":"login","password":"[REDACTED]","token":"[REDACTED]"}
    {"level":"INFO","msg":"debug","note":"retry with tok_9f8e7d6c5b4a3921 card 4111111111111111"}
```

redaction کلیدی کار کرد، متن آزاد نه. گشتن در مقدار رشته‌ها برای الگوی توکن و کارت درستش کرد. الگو تور ایمنی است: راه‌حل واقعی دور نگه داشتن رازها از logger است، [مدیریت رازها و کلیدها](/fa/posts/sec-secrets-management/).

## log injection

logger متنی که به ورودی اعتماد کند اجازه می‌دهد کاربر ردیف جعلی بسازد ([تزریق و XSS](/fa/posts/sec-injection-xss/)، [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/)). نام کاربر `bob result=fail` و یک خط جدید و ردیفی جعلی بود:

```
-- naive text logger
2027-05-30T09:15:00Z INFO login user=bob result=fail
2027-05-30T09:15:01Z INFO login user=admin result=ok result=fail
-- slog JSON
{"time":"...","msg":"audit","actor":"bob result=fail\n2027-05-30T09:15:01Z INFO login user=admin result=ok", ...}
```

logger ساده ردیف باورپذیر «admin وارد شد» چاپ کرد. JSON {{< term "structured-logging" "ساختاریافته" >}} خط جدید را escape می‌کند و هر رویداد یک خط می‌ماند.

## تشخیص دست‌کاری

هر رکورد SHA-256 از hash قبلی به‌اضافه‌ی محتوای خودش را نگه می‌دارد، یک {{< term "hash-chain" "زنجیره‌ی hash" >}}. verifier اولین خط بد را گزارش می‌کند. دوازده رکورد و هر ۵ رکورد یک checkpoint با {{< term "hmac" "HMAC" >}} امضاشده:

```
edit line 4         chain: line 4: content does not match its hash (edited)
delete line 6       chain: line 6: expected seq 6, found 7 (deleted or reordered)
swap lines 8 and 9  chain: line 8: expected seq 8, found 9 (deleted or reordered)
truncate to 7       chain: ok   checkpoint 10: log ends at line 7 (tail truncated)
truncate to 11      chain: ok   checkpoints: ok
full rewrite        chain: ok   checkpoint 5: hash differs from the log
```

محدودیت‌ها همین‌جا پیداست: بریدن انتها زنجیره‌ی معتبر می‌گذارد، فقط checkpoint فهمید، و از دست رفتن رکوردهای بعد از آخرین checkpoint (خط ۱۱) نامشخص ماند. بازنویسی کامل زنجیره را دوباره حساب می‌کند اما بدون کلید checkpointها نمی‌خوانند. کلید را از نویسنده‌ی لاگ دور نگه دارید و لاگ را بیرون از میزبان بفرستید. در لینوکس `chattr +a` فایل را فقط‌افزودنی می‌کند (فقط از مستندات؛ اجرا نکردم).

## تشخیص حمله

مولدی با seed ثابت ۱۰٬۰۳۰ رویداد در سه روز ساخت: ۶۱۲ ورود ناموفق و ۷ حمله‌ی تزریق‌شده (چهار انفجار {{< term "credential-stuffing" "credential stuffing" >}}، یک spray آهسته، یک ورود «سفر غیرممکن»، یک تغییر نقش ساعت ۰۳:۰۰) و یک تله: NAT دفتری با ۴۰ شکست هم‌زمان. قاعده: اگر یک IP برای N کاربر متمایز در یک پنجره شکست بخورد هشدار بده.

| قاعده | هشدار | درست | کاذب | precision | recall |
|---|---|---|---|---|---|
| 24h, 20 users | 4 | 3 | 1 | 0.75 | 0.60 |
| 10 min, 8 users + 24h | 6 | 5 | 1 | 0.83 | 1.00 |
| 10 min, 30 users + 24h | 4 | 3 | 1 | 0.75 | 0.60 |
| 10 min, 41 users + 24h | 4 | 3 | 1 | 0.75 | 0.60 |
| travel (1 h) | 1 | 1 | 0 | 1.00 | 1.00 |
| role change off-hours | 3 | 1 | 2 | 0.33 | 1.00 |

چهار ردیف اول ۵ حمله‌ی مبتنی بر IP را می‌سنجند؛ دو ردیف آخر جدا. آستانه‌ی پایین حمله‌های کوچک را می‌گیرد اما روی NAT هم هشدار می‌دهد؛ آستانه‌ی بالا ساکت است و حمله را از دست می‌دهد. دو تغییر مشروع on-call عدد ۰٫۳۳ را توضیح می‌دهد. هشدار کاذب {{< term "alert-fatigue" "خستگی از هشدار" >}} می‌سازد؛ با موارد شناخته‌شده تنظیم کنید.

## واکنش به حادثه

{{< term "incident-response" "واکنش به حادثه" >}} از چرخه‌ی NIST SP 800-61 پیروی می‌کند: آمادگی، شناسایی و تحلیل، مهار، ریشه‌کنی و بازیابی، فعالیت پس از حادثه (از حافظه؛ سند را ببینید). اسکلتی برای {{< term "runbook" "runbook" >}} شما:

```
# Incident <id>   severity: SEV1-3   lead: <name>   comms: <name>
- [ ] Record time, who noticed what
- [ ] Preserve: copy logs and disk snapshot BEFORE cleaning
- [ ] Contain: disable account/key, isolate host (do not wipe)
- [ ] Rotate secrets: outermost first, then dependents
- [ ] Notify: legal/compliance for deadlines (varies by law)
- [ ] Postmortem within a week
```

شدت: SEV1 داده‌ی مشتری یا قطعی کامل، SEV2 اثر جزئی، SEV3 مهارشده. ثبت کنید چه کسی و کی با شواهد کار کرد. بسیاری از مقررات مهلت اطلاع‌رسانی دارند؛ مشاوره‌ی حقوقی نیست، از تیم حقوقی بپرسید. بعد از پایان، [postmortem بدون سرزنش](/fa/posts/eng-postmortems-blameless/) بنویسید.

تمرین میزی (ساختگی): ساعت ۰۳:۰۰ حسابی که صاحبش خواب است نقشش عوض می‌شود. چک‌لیست را بلند مرور کنید و اولین گام ناشناخته را یادداشت کنید.

## چند نکته‌ی مهم

- actor و تصمیم را لاگ کنید، هرگز راز را.
- ورودی کاربر را ساختاریافته کنید.
- قاعده‌های هشدار را با حمله‌ها و هشدارهای کاذب شناخته‌شده بیازمایید.
- runbook را پیش از نیاز تمرین کنید.

## تمرین

قاعده‌ای برای پنج `order.cancel` ردشده از یک actor در یک دقیقه بنویسید، آن را در مولد تزریق کنید و precision و recall را گزارش دهید.

## قدم بعدی

این آخرین مقاله‌ی مجموعه‌ی امنیت بود. مجموعه‌های بعدی سیستم‌های توزیع‌شده و مهندسی نرم‌افزار هستند.
