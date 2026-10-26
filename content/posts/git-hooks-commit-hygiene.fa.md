+++
date = '2026-11-13T10:00:00+03:30'
draft = false
title = 'hookها و commit message تمیز'
description = 'Git hook در عمل: اسکریپت‌های pre-commit، commit-msg و pre-push، اشتراک‌گذاری با core.hooksPath و نوشتن commit message تمیز با fixup.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "hooks", "commit-messages", "beginner"]
cover = { image = "/images/covers/git-hooks-commit-hygiene.fa.png", alt = "hookها و commit message تمیز", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/git-bisect/) با `git bisect` یک باگ را در تاریخچه پیدا کردیم. این کار فقط وقتی خوب جواب می‌دهد که تاریخچه خوانا باشد: کامیت‌های کوچک با پیامی که می‌گوید «چرا». این مقاله درباره‌ی این است که با **{{< term "git-hook" "hook" >}}** این وضعیت را خودکار نگه داریم، به‌علاوه چند عادت برای خود پیام‌ها.

> همه‌ی مثال‌ها در یک repo محلی با Git نسخه‌ی 2.39 و Python 3 اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## hook فقط یک اسکریپت است

Git دنبال فایل‌های اجرایی می‌گردد که اسمشان همان رویداد است. اگر اسکریپت با کد غیرصفر خارج شود، Git متوقف می‌شود. به‌صورت پیش‌فرض این فایل‌ها در `.git/hooks` هستند که version نمی‌شود. یک hook از نوع `pre-commit` که جلوی نشانه‌ای را می‌گیرد که خودم برای «قبل از commit باید پاک شود» می‌گذارم:

```sh
#!/bin/sh
if git diff --cached -U0 | grep -q 'TODO-REMOVE'; then
  echo "pre-commit: found TODO-REMOVE in staged changes" >&2
  exit 1
fi
```

```text
$ git commit -m "add debug"
pre-commit: found TODO-REMOVE in staged changes
$ echo $?
1
```

commit انجام نشد و تغییر همچنان staged ماند. بعد از پاک کردن آن خط، commit رد شد.

## اشتراک‌گذاری با core.hooksPath

چون `.git/hooks` version نمی‌شود، هم‌تیمی‌ها hookهای شما را نمی‌گیرند. آن‌ها را در یک پوشه‌ی ردیابی‌شده بگذارید و Git را به آن پوشه راهنمایی کنید:

```text
$ git config core.hooksPath .githooks
```

هر نفر این را یک بار برای هر clone اجرا می‌کند (یک اسکریپت setup یا README می‌تواند یادآوری کند). حالا `pre-commit` فایل‌های پایتونِ staged را کامپایل می‌کند:

```sh
#!/bin/sh
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
[ -z "$files" ] && exit 0
for f in $files; do
  python3 -m py_compile "$f" || { echo "pre-commit: $f does not compile" >&2; exit 1; }
done
```

```text
  File "bad.py", line 1
    print(
         ^
SyntaxError: '(' was never closed
pre-commit: bad.py does not compile
```

برای Go به همین شکل از `gofmt -l` استفاده می‌شود؛ من اینجا فقط نسخه‌ی Python را اجرا کردم.

## کنترل سبک پیام با commit-msg

Git مسیر فایل پیام را به‌عنوان `$1` می‌دهد. این hook یک پیشوند به سبک **{{< term "conventional-commits" "Conventional Commits" >}}** را اجباری می‌کند:

```sh
#!/bin/sh
subject=$(head -n 1 "$1")
if ! echo "$subject" | grep -Eq '^((fixup! |squash! )?)(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?: .+'; then
  echo "commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)" >&2
  echo "got: $subject" >&2
  exit 1
fi
```

```text
$ git commit -m "added hooks"
commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)
got: added hooks
$ git commit -m "chore: add shared hooks"
[main 785e41e] chore: add shared hooks
```

به بخش `fixup! |squash! ` توجه کنید. نسخه‌ی اولِ regex من آن را نداشت و `fixup! feat: add greet` را رد کرد، و این جریان بخش آخر را خراب کرد. hook گاهی جلوی خودتان هم می‌ایستد.

## pre-push و اجرای تست‌ها

```sh
#!/bin/sh
python3 -m unittest discover -s tests -q || { echo "pre-push: tests failed, push blocked" >&2; exit 1; }
```

با یک تست عمداً غلط (`assertEqual(1 + 1, 3)`):

```text
AssertionError: 2 != 3
FAILED (failures=1)
pre-push: tests failed, push blocked
error: failed to push some refs to '../remote.git'
```

بعد از درست کردن تست، push موفق شد. این hook را سریع نگه دارید، وگرنه آدم‌ها دورش می‌زنند.

## hook حفاظ است، نه امنیت

```text
$ git commit --no-verify -m "whatever"
[main d172ea1] whatever
```

`--no-verify` هر دو hook یعنی `pre-commit` و `commit-msg` را رد می‌کند و commit من با پیام نامناسب ثبت شد. علاوه بر این، hook فقط وقتی وجود دارد که آن شخص نصبش کرده باشد. هر چیزی که واقعاً به آن تکیه دارید باید دوباره در **{{< term "ci" "CI" >}}** اجرا شود. ابزارهایی مثل Husky یا pre-commit نصب hook را مدیریت می‌کنند؛ فقط اسمشان را می‌آورم و اینجا امتحانشان نکردم.

## یک commit message خوب

یک قرارداد رایج (نه قانون Git): خط عنوان حدود ۵۰ کاراکتر، یک خط خالی، و بدنه‌ای با عرض حدود ۷۲ کاراکتر که توضیح می‌دهد «چرا».

```text
feat: add retry

Retry up to 3 times because the upstream
returns 503 during deploys.
```

دستور `git commit -v` تفاوت staged را در ویرایشگر نشان می‌دهد تا بتوانید دقیقاً همان چیزی را که تغییر داده‌اید توصیف کنید. دستور `git config commit.template <file>` ویرایشگر را از قبل پر می‌کند؛ با یک template که خط‌های comment داشت، `git commit` ویرایشگر را با همان خط‌ها باز کرد و خط‌هایی که با `#` شروع می‌شوند از پیام نهایی حذف می‌شوند.

## اصلاح یک commit قدیمی با fixup

در یک commit قدیمی غلط تایپی پیدا کردید؟ اصلاح را stage کنید و هدف را نام ببرید:

```text
$ git commit --fixup 2f84e0a
$ git log --oneline -4
5cc2712 fixup! feat: add greet
7e55bd8 fix: let fixup commits through
e9528aa feat: add bye
2f84e0a feat: add greet
```

بعد یک rebase با **{{< term "fixup-commit" "fixup" >}}** آن را داخل commit هدف ادغام می‌کند. مقدار `GIT_SEQUENCE_EDITOR=true` لیست آماده را بدون باز کردن ویرایشگر می‌پذیرد:

```text
$ GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash HEAD~4
Successfully rebased and updated refs/heads/main.
b10a5cf fix: let fixup commits through
82e5be5 feat: add bye
be3de2d feat: add greet
```

خط fixup ناپدید شد و اصلاح داخل `feat: add greet` نشست. پیش از آن باید working tree تمیز باشد؛ اولین تلاش من با پیام «Your index contains uncommitted changes» شکست خورد. بازنویسی تاریخچه فقط برای commitهایی امن است که هنوز با کسی به اشتراک نگذاشته‌اید.

## چند نکته‌ی مهم

- hookهای `.git/hooks` محلی‌اند؛ برای اشتراک‌گذاری از `core.hooksPath` با یک پوشه‌ی ردیابی‌شده استفاده کنید.
- اسکریپت را اجرایی کنید (`chmod +x`)، وگرنه Git نادیده‌اش می‌گیرد.
- `pre-commit` را سریع نگه دارید و فقط فایل‌های staged را بررسی کنید.
- hook را امنیت فرض نکنید: `--no-verify` وجود دارد، پس بررسی‌ها را در CI تکرار کنید.
- commitهایی را که push و به اشتراک گذاشته‌اید autosquash نکنید.

## تمرین

در یک repo آزمایشی، در `.githooks/` یک hook از نوع `commit-msg` بنویسید که subjectهای بلندتر از ۷۲ کاراکتر را رد کند. `core.hooksPath` را تنظیم کنید و بررسی کنید پیام بلند رد و پیام کوتاه پذیرفته می‌شود. بعد دو commit بسازید، برای اولی یک fixup اضافه کنید و با autosquash ادغامش کنید.

## قدم بعدی

مقاله‌ی بعدی «submodule، subtree و worktree» است.
