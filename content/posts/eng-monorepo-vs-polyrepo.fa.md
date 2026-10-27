+++
date = '2027-06-02T10:00:00+03:30'
draft = false
title = 'monorepo یا polyrepo؟'
description = 'monorepo یا polyrepo در Go: یک تغییر چندبخشی به دو روش، CI فقط برای ماژول‌های اثرپذیر، CODEOWNERS، clone جزئی و ماتریس تصمیم با نظر شخصی.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["monorepo", "polyrepo", "go-workspaces", "ci", "git", "software-engineering"]
cover = { image = "/images/covers/eng-monorepo-vs-polyrepo.fa.png", alt = "monorepo یا polyrepo؟", hiddenInSingle = true }
+++

پست قبلی، [مبانی DDD](/fa/posts/eng-ddd-basics/)، مرزها را درون یک سیستم کشید. سؤال بعدی این است که کدِ پشت این مرزها کجا زندگی کند. در {{< term "monorepo" "monorepo" >}} چند سرویس در یک مخزن‌اند و در {{< term "polyrepo" "polyrepo" >}} هر سرویس مخزن خودش را دارد. مرتبط: [پکیج‌ها و ماژول‌ها](/fa/posts/go-packages-modules/)، [طراحی pipeline برای CI/CD](/fa/posts/eng-ci-cd-pipeline-design/)، [feature flag و trunk-based development](/fa/posts/eng-feature-flags-trunk-based/)، [شاخه‌ها، HEAD و ref‌ها](/fa/posts/git-branches-head-refs/).

یک سیستم اسباب‌بازی (`orders`، `payments` و `shared` با تابع `Format`) را یک بار در یک مخزن و یک بار در سه مخزن ساختم؛ مخزن‌ها محلی و دورریختنی‌اند (Go 1.26، Git 2.39). **عددها شمارش و بایت‌اند، نه زمان.** نظرها برچسب دارند.

## ۱. یک تغییر، دو روش

`Format(cents)` را به `Format(cents, cur)` تغییر دادم. در monorepo سه ماژول با فایل {{< term "go-workspace" "go.work" >}} به هم وصل‌اند. وقتی فقط `shared` عوض شود، یک دستور همه‌ی فراخوانی‌های خراب را نشان می‌دهد:

```text
$ go build ./orders/... ./payments/... ./shared/...   # output trimmed
orders/orders.go:14:23: not enough arguments in call to shared.Format
payments/payments.go:9:67: not enough arguments in call to shared.Format
```

هر دو فراخوانی را درست کردم و یک commit زدم. `go test -race` در هر سه ماژول سبز شد و `git show --stat` شش فایل را در یک commit نشان داد.

در polyrepo، `orders` و `payments` با نسخه به `shared` وابسته‌اند. برای شبیه‌سازی release بدون شبکه، zip‌های tag‌دار را از یک module proxy محلی سرو کردم. نتیجه: سه pull request، یک tag، و این وضعیت بعد از دومی:

```text
orders:   example.com/poly/shared v0.2.0
orders total: 30.00 EUR
payments: example.com/poly/shared v0.1.0
payments: paid 12.50
```

همه‌چیز کامپایل می‌شود، ولی تا PR سوم دو سرویس پول را متفاوت فرمت می‌کنند.

| | monorepo | polyrepo |
|---|---|---|
| مخزن / commit / PR | ۱ / ۱ / ۱ | ۳ / ۳ / ۳ (+۱ tag) |
| حالت‌های نسخه‌ی ناهمگون | ۰ | ۱ |

**نظر من:** تغییر اتمی قوی‌ترین دلیل برای monorepo است؛ ولی pin کردن نسخه هم ویژگی است: payments مجبور به حرکت نشد.

## ۲. CI نباید همه‌چیز را اجرا کند

بدون CI انتخابی، monorepo کند می‌شود. اسکریپت من خروجی `git diff --name-only` را می‌خواند، هر `go.mod` را parse می‌کند و یال‌های وابستگی را می‌پیماید:

```text
diff 1: orders/orders.go    run tests for: ['orders']
diff 2: payments/payments.go    run tests for: ['payments']
diff 3: shared/money.go     run tests for: ['orders', 'payments', 'shared']
diff 4: docs/README.md      run tests for: (nothing)
```

ابزارهایی مثل Bazel، Nx، Turborepo، Pants و Buck2 برای این کار هستند؛ از آن‌ها استفاده نکردم و ادعایی ندارم.

## ۳. مالکیت و دسترسی

فایل {{< term "codeowners" "CODEOWNERS" >}} مسیرها را به تیم‌ها نگاشت می‌کند. matcher کوچک ۱۱ خطی من (آخرین الگوی منطبق برنده است) این را داد: `payments/payments.go -> @team-payments @team-security` و `orders/README.md -> @team-docs`. تا آنجا که می‌دانم GitHub دسترسی خواندن per-directory ندارد، پس «فقط تیم X بخواند» طبیعتاً per-repo است. آزمایشش نکردم؛ مستندات میزبانتان را ببینید.

## ۴. مقیاس

با `git fast-import` مخزنی ساختم: ۳٬۰۰۰ commit، ۳٬۰۰۰ فایل، هزار تا برای هر سرویس. `git count-objects -vH` حجم pack را 2.11 MiB نشان داد. وقتی مخزن بزرگ شود:

- `git log -- orders` برای هر پوشه ۱٬۰۰۰ commit شمرد: تاریخچه را می‌شود per-path پرسید.
- {{< term "sparse-checkout" "sparse checkout" >}} (حالت cone، فقط `orders`): ۱٬۰۰۰ فایل روی دیسک، ۳٬۰۰۰ فایل tracked.
- {{< term "partial-clone" "partial clone" >}} (با `--filter=blob:none` و `--no-checkout`): 1.22 MiB و ۳٬۰۰۰ blob غایب؛ با خواندن یک فایل همان یکی آمد و ۲٬۹۹۹ غایب ماند.

پیام‌های commit با scope (مثل `fix(shared): ...`، {{< term "conventional-commits" "Conventional Commits" >}}) لاگ را خوانا نگه می‌دارند.

## ۵. نسخه‌بندی و release

monorepo می‌تواند یک نسخه برای همه داشته باشد: ساده است، اما ارتقاها با هم حرکت می‌کنند. در polyrepo هر کتابخانه {{< term "semver" "نسخه‌ی معنایی" >}} خودش را دارد. monorepo با چند ماژول Go هم می‌تواند جدا tag بزند: طبق مرجع Go modules، زیرپوشه‌ی ماژول پیشوند tag نسخه هم هست (مثلاً `orders/v1.2.0`). resolve یک ماژول چندگانه‌ی tag‌دار را اجرا نکردم.

## ماتریس تصمیم من (نظر شخصی)

| عامل | تمایل به monorepo | تمایل به polyrepo |
|---|---|---|
| اندازه‌ی تیم | کوچک تا متوسط، on-call مشترک | تیم‌های مستقل زیاد |
| کد مشترک | زیاد تغییر می‌کند | API پایدار و نسخه‌دار |
| ریتم release | با هم | مستقل |
| ابزار build | CI انتخابی دارید یا می‌سازید | هر مخزن ساده است |
| کنترل دسترسی | داخل شرکت باز | سخت‌گیرانه per-project |
| onboarding | یک clone، یک جستجو | مخزن‌های کوچک و متمرکز |

راه میانه‌ی من: یک مخزن برای هر حوزه‌ی محصول و کتابخانه‌های واقعاً مشترک در مخزن‌های جدا و نسخه‌دار.

## چند نکته‌ی مهم

- `go.work` برای کار محلی است؛ release باید همچنان نسخه‌ی واقعی بگیرد.
- در ریشه‌ی workspace دستور `go test ./...` شکست می‌خورد («directory prefix . does not contain modules»)؛ پوشه‌ی ماژول‌ها را نام ببرید.
- پوشه‌ی «shared» که همه ویرایشش می‌کنند نقطه‌ی coupling می‌شود؛ مالک بگذارید.
- pin کردن drift را پنهان می‌کند؛ bump زمان‌بندی کنید.

## تمرین

ماژول چهارم `reports` را اضافه کنید که به `shared` وابسته است و `affected.py` را طوری گسترش دهید که تغییر در `shared` آن را هم انتخاب کند. بعد فقط `reports/` را عوض کنید و ببینید تنها خودش اجرا می‌شود.

## قدم بعدی

پست بعدی «برآورد و برنامه‌ریزی» است.
