+++
date = '2027-04-27T10:00:00+03:30'
draft = false
title = 'feature flag و trunk-based development'
description = 'feature flag در Go: rollout درصدی پایدار، کلید اضطراری، reload اتمی، هزینه‌ی پرچم‌ها و نقش آن‌ها در trunk-based development.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["feature-flags", "trunk-based-development", "software-engineering", "go", "release"]
cover = { image = "/images/covers/eng-feature-flags-trunk-based.fa.png", alt = "feature flag و trunk-based development", hiddenInSingle = true }
+++

پست قبل، [ADR و مستندسازی تصمیم‌ها](/fa/posts/eng-adr-documentation/)، ثبت می‌کرد که چرا چیزی را انتخاب می‌کنیم. این پست درباره‌ی انتخابی است که شیوه‌ی انتشار را عوض می‌کند: جدا کردن deploy از release. {{< term "feature-flag" "feature flag" >}} اجازه می‌دهد کد نیمه‌تمام در `main` باشد و کاربر آن را نبیند، و همین {{< term "trunk-based-development" "trunk-based development" >}} را شدنی می‌کند. پرچم‌ها {{< term "technical-debt" "بدهی" >}} هم می‌سازند ([بدهی فنی](/fa/posts/eng-technical-debt/))، پس هزینه‌اش را هم می‌شمارم. مرتبط: [تست در Go](/fa/posts/go-testing-basics/) و [refactor امن](/fa/posts/eng-refactoring-safely/). نظرها مشخص شده‌اند؛ بقیه اجرا شده است.

> Go 1.26 و `go test -race`. دمو نمونه‌ی محلی است: بسته‌ی پرچمی حدود ۸۰ خط، بدون SDK بیرونی.

## ارزیاب

هر پرچم یک قاعده دارد: `kill` از نوع bool، `percent` و `overrides` برای هر کاربر. ترتیب ثابت است: پرچم ناشناخته خاموش است، بعد کلید اضطراری، بعد override، بعد درصد.

```go
func Bucket(name, user string) int {
	h := fnv.New32a()
	h.Write([]byte(name + user))
	return int(h.Sum32() % 100)
}
```

کاربر و پرچم یکسان همیشه در همان bucket می‌افتند، پس چیزی برای ذخیره نیست. {{< term "kill-switch" "کلید اضطراری" >}} حتی از override قوی‌تر است و پرچم ناشناخته false برمی‌گرداند (fail-safe: غلط املایی ویژگی را پنهان می‌کند، نه افشا). پیکربندی یک فایل JSON است؛ `Reload` اول آن را parse می‌کند و بعد با `atomic.Pointer` جایگزین می‌کند، پس فایل خراب پیکربندی قبلی را نگه می‌دارد.

## آیا بالا بردن درصد کسی را جابه‌جا می‌کند؟

{{< term "canary-release" "rollout درصدی" >}} وقتی درست است که بالا بردن درصد کاربرِ قبلاً واردشده را بیرون نیندازد. تست روی ۱۰٬۰۰۰ شناسه‌ی ساختگی درصد را ۱۰ و ۲۵ و ۵۰ می‌کند و با هر جابه‌جایی شکست می‌خورد:

```text
percent=10 users_in=1017 of 10000
percent=25 users_in=2513 of 10000
percent=50 users_in=5020 of 10000
```

تست می‌گذرد. دلیلش قاعده‌ی `bucket < percent` است: بالا بردن `percent` فقط bucket اضافه می‌کند. توزیع bucketها تقریباً یکنواخت است؛ تعداد کاربر در هر بلوک ده‌تایی:

```text
[1017 990 1005 1003 1005 982 1006 1013 988 991]
```

اضافه کردن نام پرچم به hash مهم است: وگرنه همان ۱۰٪ کاربران همه‌ی پرچم‌ها را آزمایش می‌کردند.

## reload زنده

برنامه‌ی کوچکی فایل را می‌خواند، منتظر می‌ماند، من فایل را عوض می‌کنم و دوباره می‌خواند. خروجی واقعی (بدون زمان):

```text
-- before first load
level=INFO msg=flag name=new-pricing user=alice on=false why=unknown
-- after load
level=INFO msg=flag name=new-pricing user=alice on=false why=override
-- after reload
level=INFO msg=flag name=new-pricing user=alice on=true why=percent
```

همان process، رفتار تازه. یک تست هنگام ارزیابی هشت goroutine زیر `-race` reload می‌کند و می‌گذرد.

## هر دو شاخه و branch by abstraction

هر پرچم مسیر کد را دو برابر می‌کند و هر دو نیمه تست می‌خواهند. در بسته‌ی `shop` قیمت‌گذاری قدیم و جدید پشت interface به نام `Pricer` است ({{< term "branch-by-abstraction" "branch by abstraction" >}}) و پرچم `new-pricing` بینشان سوییچ می‌کند. یک تست همان انتظارها را با پرچم ۰ و ۱۰۰ درصد اجرا می‌کند. یک {{< term "characterization-test" "characterization test" >}} قدیم و جدید را روی ۸۸۶۶ ورودی مقایسه می‌کند و برابری می‌خواهد. کد تازه را خاموش merge کنید و بعد درصد را بالا ببرید.

## هزینه

n پرچم bool مستقل ۲ به توان n پیکربندی می‌دهد. تست این را چاپ کرد:

```text
3 boolean flags -> 8 configurations
10 boolean flags -> 1024 configurations
20 boolean flags -> 1048576 configurations
```

همه را نمی‌توانید تست کنید. **به تجربه‌ی من** بیشتر پرچم‌ها روی هم اثر ندارند، اما آن‌هایی که دارند در production خراب می‌شوند. پرچم‌ها را مستقل و کم نگه دارید.

پرچم قدیمی بدهی است. در repo آزمایشی با سه commit (نویسنده‌ی جعلی و تاریخ ثابت؛ تاریخچه ساختگی است، نه پروژه‌ی واقعی) یک اسکریپت پرچم‌های `flag/flags.go`، ارجاع‌هایشان و اولین commit را با `git log -S` فهرست می‌کند:

```text
old-banner     refs=0 first_added=2026-01-10
fast-checkout  refs=1 first_added=2026-03-02
new-pricing    refs=2 first_added=2026-04-20
```

`old-banner` ارجاعی ندارد و قدیمی‌ترین است؛ کاندیدای حذف. چک‌لیست حذف من: به ۱۰۰ برسان و صبر کن؛ شاخه‌ی بازنده و شرط پرچم را حذف کن؛ تست‌هایش را حذف کن؛ ورودی پیکربندی را حذف کن؛ ثابت را حذف کن.

## trunk-based در عمل

شاخه‌های کوتاه‌عمر، merge به `main` دست‌کم روزانه، و کار نیمه‌تمام پشت پرچم. توصیه‌ها درباره‌ی عمر شاخه فرق می‌کند؛ من یکی دو روز را هدف می‌گیرم. deploy کد را روی سرور می‌گذارد و release روشن کردن آن است. dark launch کدی را deploy می‌کند که اجرا می‌شود ولی نتیجه‌اش به کاربر نمی‌رسد؛ canary درصد کمی را در معرض می‌گذارد.

| | GitFlow | Trunk-based |
|---|---|---|
| شاخه‌ها | develop و release بلندمدت | کوتاه‌عمر، یک `main` |
| کار نیمه‌تمام | روی شاخه می‌ماند | پشت پرچم merge می‌شود |
| نیاز دارد | انضباط merge | CI سریع، تست، پرچم |

**به نظر من** trunk-based به سرویسی می‌خورد که زیاد deploy می‌شود؛ GitFlow برای نرم‌افزار با نسخه‌های مشخص مناسب‌تر است. rollback یعنی برگرداندن پرچم و بعد با فرصت revert کردن. pipeline‌ای که با هر merge اجرا می‌شود موضوع پست بعدی است.

## چند نکته‌ی مهم

- پرچم کنترل دسترسی نیست: authorization را با آن تصمیم نگیرید.
- مسیر پرچم‌خاموش را هم تست کنید، چون rollback شماست.
- هر پرچم صاحب و تاریخ حذف می‌خواهد.
- OpenFeature را اجرا نکردم. تا جایی که می‌دانم یک API استاندارد و مستقل از فروشنده برای ارزیابی پرچم است؛ پیش از تکیه بر آن مستنداتش را ببینید.

## تمرین

به تابعی که مال شماست یک پرچم اضافه کنید، خاموش merge کنید، هر دو تست را بنویسید، در یک تست درصد را بالا ببرید و بعد با چک‌لیست حذفش کنید.

## قدم بعدی

پست بعدی «طراحی pipeline برای CI/CD» است.
