+++
date = '2026-11-17T10:00:00+03:30'
draft = false
title = 'workflowهای تیمی و درون packfile'
description = 'workflowهای Git و packfile: مقایسه‌ی trunk-based، GitHub flow و Gitflow، سپس git gc، verify-pack و clone کم‌عمق، جزئی و sparse با اجرای واقعی.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "workflows", "packfiles"]
cover = { image = "/images/covers/git-workflows-packfiles.fa.png", alt = "workflowهای تیمی و درون packfile", hiddenInSingle = true }
+++

این آخرین مقاله از سری Git است. در [مقاله‌ی قبل](/fa/posts/git-submodule-subtree-worktree/) با submodule، subtree و worktree آشنا شدیم. اینجا می‌بینیم تیم‌ها چطور branchها را سازمان می‌دهند و Git چه می‌کند تا repository کوچک بماند.

> دموها با Git نسخه‌ی 2.39.2 روی macOS و در پوشه‌های موقت اجرا شده‌اند و عددها از همان اجراها کپی شده‌اند. سرویس hosting اجرا نکردم، پس branch protection فقط در حد مفهوم آمده است.

## workflowهای تیمی، خیلی کوتاه

workflow یعنی توافق درباره‌ی اینکه کار کجا انجام می‌شود و چه چیزی اجازه دارد به `main` برسد. جدول زیر نظر خودم است، نه استاندارد:

| Workflow | ایده | مناسب برای | هزینه |
|---|---|---|---|
| {{< term "trunk-based-development" "Trunk-based" >}} | تغییرهای ریز و روزانه به `main`، کار نیمه‌تمام پشت flag | CI قوی، deploy مکرر | نیاز به انضباط |
| GitHub flow | branch کوتاه، pull request، review، merge، deploy | بیشتر تیم‌های backend | branchهای طولانی آزارنده‌اند |
| Gitflow | branchهای `main`، `develop`، feature، release، hotfix | محصول‌های نسخه‌دار | branch زیاد |
| Release branch | ساخت `release/1.4` و فقط رفع باگ روی آن | اپ موبایل، کتابخانه | backport دستی |

پیش‌فرض من GitHub flow است و release branch را فقط برای patch کردن نسخه‌ی قدیمی می‌گیرم. **Branch protection** قانونی سمت سرور است: `main` فقط از راه pull request با review و checkهای سبز تغییر می‌کند. همین وبلاگ این‌طور کار می‌کند:

```bash
git log --oneline --merges -5
```

```text
53c9acd Merge pull request #6 from h-agharezaei/add-glossary
fdb74d6 Merge pull request #5 from h-agharezaei/add-glossary
c848814 Merge pull request #4 from h-agharezaei/update-cover-domain
51d90ac Merge pull request #3 from h-agharezaei/add-go-cve-2026-111943-post
9e6f4d7 Merge pull request #2 from h-agharezaei/add-go-cve-2026-111943-post
```

## Objectهای loose و packfile

هر object اول به‌شکل یک فایل جدا («loose») ذخیره می‌شود. repositoryای ساختم با یک فایل ۲۰۰۰ خطی و ۴۰ ویرایش کوچک، هرکدام یک commit:

```bash
git count-objects -v
du -sk .git
```

```text
count: 123
size: 3280
in-pack: 0
packs: 0
...
3384	.git
```

۱۲۳ object loose و حدود ۳.۳ مگابایت، چون هر نسخه‌ی فایل کامل ذخیره شده است. حالا garbage collection:

```bash
git gc -q
git count-objects -v
du -sk .git
ls .git/objects/pack
```

```text
count: 0
in-pack: 123
packs: 1
size-pack: 148
268	.git
pack-8ba0db77...idx
pack-8ba0db77...pack
```

از ۳۳۸۴ کیلوبایت به ۲۶۸ کیلوبایت. **{{< term "packfile" "Packfile" >}}** چند object را در یک فایل نگه می‌دارد و فایل `.idx` فهرست آن است. کوچک‌تر بودن pack بیشتر از **{{< term "delta-compression" "delta compression" >}}** می‌آید: object به‌صورت diff کوچکی نسبت به یک object مشابه ذخیره می‌شود. `git verify-pack -v` آن را نشان می‌دهد:

```text
8dc7cd65... blob 143281 69145 5386
48db3cc6... blob     43    48 144494 1 8dc7cd65...
36070a34... blob     43    45 144661 5 80839e73...
non delta: 84 objects
chain length = 1: 5 objects
chain length = 5: 4 objects
chain length = 12: 1 object
```

ستون‌ها: id، نوع، اندازه، اندازه در pack، offset، و برای deltaها عمق زنجیره و base. یک blob با ۱۴۳ کیلوبایت کامل ذخیره شده، ولی نسخه‌ای دیگر فقط ۴۳ بایت دستور روی base خودش است. ۳۹ از ۴۱ blob، delta بودند و عمق زنجیره‌ها تا ۱۲ می‌رسید. `git repack -a -d` همه‌چیز را در یک pack بازنویسی می‌کند؛ اینجا چیزی عوض نشد چون `gc` کار را کرده بود.

## repositoryهای بزرگ: shallow، partial، sparse

یک repository سرور کوچک ساختم با ۷ commit، ۵ سند و یک فایل کد (۷۰ object) و `uploadpack.allowFilter` را روشن کردم. تعداد objectها در هر clone:

| Clone | دستور | Object |
|---|---|---|
| کامل | `git clone file://...` | ۷۰ |
| **{{< term "shallow-clone" "Shallow" >}}** | `--depth 1` | ۱۰ (۱ commit، ۳ tree، ۶ blob) |
| **{{< term "partial-clone" "Partial" >}}** | `--filter=blob:none` | ۳۴ (۷ commit، ۲۱ tree، ۶ blob) |

clone کم‌عمق فقط یک commit دارد و `git log` یک خط نشان می‌دهد؛ `git fetch --unshallow` بعداً هر ۷ commit و ۴۲ blob را برگرداند. clone جزئی تاریخچه‌ی کامل را دارد ولی محتوای فایل‌ها را در صورت نیاز می‌گیرد: `git show HEAD~3:docs/doc1.txt` یک blob گم‌شده را گرفت (بعدش ۷ blob). Git به remote می‌گوید «promisor remote»، یعنی بعداً به شبکه نیاز دارید.

**{{< term "sparse-checkout" "Sparse checkout" >}}** فقط بعضی پوشه‌ها را در working tree می‌گذارد:

```bash
git clone --filter=blob:none --sparse file://... sp
git sparse-checkout set app
ls
```

```text
app
```

clone با `--sparse` با ۰ blob شروع شد؛ بعد از `set app` یک blob دانلود شد و فقط `app/` روی دیسک بود. partial clone به‌علاوه‌ی sparse checkout ترکیب معمول برای monorepoهای بزرگ است.

`git maintenance` می‌تواند کارهای نگهداری شبیه `gc` را در پس‌زمینه انجام دهد؛ آن را اجرا نکردم.

## چند نکته‌ی مهم

- clone کم‌عمق تاریخچه ندارد، پس `git log` و `git blame` چیز کمی می‌بینند.
- clone جزئی بعداً به remote نیاز دارد؛ آفلاین، نبودنِ blob خطاست.
- `gc` بعد از یک مهلت، objectهای unreachable را پاک می‌کند، پس commitهای بدون ارجاع backup نیستند.
- Branch protection جایش روی سرور است؛ hookهای محلی را می‌شود رد کرد.

## جمع‌بندی سری

گیت object‌های تغییرناپذیر نگه می‌دارد، نام branch اشاره‌گر به آن‌هاست و بیشتر دستورها یا object اضافه می‌کنند یا اشاره‌گر را جابه‌جا. نُه مقاله‌ی قبلی به ترتیب:

- [گیت چطور فکر می‌کند: object و hash](/fa/posts/git-how-git-thinks/)
- [index و staging: سه ناحیه‌ی گیت](/fa/posts/git-index-staging/)
- [branch، HEAD و ref: فقط اشاره‌گر](/fa/posts/git-branches-head-refs/)
- [merge یا rebase؟ دو تاریخچه‌ی واقعی](/fa/posts/git-merge-vs-rebase/)
- [حل conflict و rerere](/fa/posts/git-resolve-conflicts/)
- [برگرداندن کار: reflog، revert و cherry-pick](/fa/posts/git-undo-reflog-revert/)
- [پیدا کردن باگ با git bisect](/fa/posts/git-bisect/)
- [hookها و commit message تمیز](/fa/posts/git-hooks-commit-hygiene/)
- [submodule، subtree و worktree](/fa/posts/git-submodule-subtree-worktree/)

## تمرین

repositoryای با یک فایل ۱۰۰۰ خطی و ۲۰ commit بسازید که هرکدام یک خط را عوض می‌کند. `count-objects -v` و `du -sk .git` را ثبت کنید، `git gc` بزنید و مقایسه کنید. طولانی‌ترین زنجیره‌ی delta را با `verify-pack -v` پیدا کنید. بعد با `--depth 1` clone کنید و objectها را با `git cat-file --batch-all-objects --batch-check` بشمارید.

## قدم بعدی

این آخرین مقاله‌ی Git بود. مقاله‌ی بعدی تقویم، سری Databases را شروع می‌کند: مدل رابطه‌ای و SQL ضروری.
