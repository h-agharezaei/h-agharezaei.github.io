+++
date = '2026-11-17T10:00:00+03:30'
draft = false
title = 'workflowهای تیمی و درون packfile'
description = 'workflowهای Git و packfile: مقایسه‌ی trunk-based، GitHub flow و Gitflow، سپس git gc، verify-pack و clone کم‌عمق، جزئی و sparse با اجرای واقعی.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "workflows", "packfiles"]
cover = { image = "/images/covers/git-workflows-packfiles.fa.png", alt = "workflowهای تیمی و درون packfile", hiddenInSingle = true }
+++

یک فایل ۲۰۰۰ خطی که ۴۰ بار با تغییرهای کوچک ویرایش شده، در حالت عادی ۳۳۸۴ کیلوبایت جا می‌گیرد. بعد از یک `git gc` همان repository ۲۶۸ کیلوبایت است. این فاصله‌ی حدود ۱۲ برابری از کجا می‌آید؟ جواب این سؤال توضیح می‌دهد چرا Git برای repositoryهای بزرگ گزینه‌هایی مثل clone کم‌عمق و جزئی دارد.

این آخرین مقاله‌ی سری است و دو بخش دارد. اول، کمی درباره‌ی اینکه تیم‌ها چطور با branchها کار می‌کنند (workflow). بعد، نگاهی به داخل `.git` برای دیدن اینکه objectها دقیقاً چطور روی دیسک ذخیره می‌شوند. از [مقاله‌ی اول](/fa/posts/git-how-git-thinks/) می‌دانید که Git همه‌چیز را در قالب objectهای تغییرناپذیر نگه می‌دارد؛ حالا می‌خواهیم ببینیم این objectها چطور جمع‌وجور می‌شوند. مقاله‌ی قبلی هم درباره‌ی [submodule، subtree و worktree](/fa/posts/git-submodule-subtree-worktree/) بود.

> دموها با Git نسخه‌ی 2.39.2 روی macOS و در پوشه‌های موقت اجرا شده‌اند و عددها از همان اجراها کپی شده‌اند. شناسه‌ها و اندازه‌ی pack در هر اجرا چند کیلوبایت یا چند کاراکتر فرق می‌کند. سرویس hosting اجرا نکردم، پس branch protection فقط در حد مفهوم آمده است.

## workflowهای تیمی، خیلی کوتاه

وقتی چند نفر روی یک repository کار می‌کنند، باید درباره‌ی چند چیز توافق کنند: کار جدید روی کدام branch انجام می‌شود؟ چه چیزی اجازه دارد به `main` برسد؟ کی و چطور deploy می‌شود؟ این توافق را workflow می‌گویند. چند الگوی رایج هست. جدول زیر نظر خودم است، نه استاندارد:

| Workflow | ایده | مناسب برای | هزینه |
|---|---|---|---|
| {{< term "trunk-based-development" "Trunk-based" >}} | تغییرهای ریز و روزانه به `main`، کار نیمه‌تمام پشت {{< term "feature-flag" "flag" >}} | CI قوی، deploy مکرر | نیاز به انضباط |
| GitHub flow | branch کوتاه، pull request، review، merge، deploy | بیشتر تیم‌های backend | branchهای طولانی آزارنده‌اند |
| Gitflow | branchهای `main`، `develop`، feature، release، hotfix | محصول‌های نسخه‌دار | branch زیاد |
| Release branch | ساخت `release/1.4` و فقط رفع باگ روی آن | اپ موبایل، کتابخانه | backport دستی |

چند توضیح برای ستون «ایده». در trunk-based همه مستقیم (یا با branchهای یک‌روزه) روی `main` کار می‌کنند، و کاری که هنوز تمام نشده با یک flag خاموش می‌ماند، یعنی کد هست ولی کاربر نمی‌بیندش. در GitHub flow برای هر کار یک branch کوتاه می‌سازید، pull request می‌دهید، یک نفر review می‌کند و بعد merge و deploy می‌شود. Gitflow برای محصولی است که نسخه‌های مشخص دارد و طبق برنامه release می‌دهد. Release branch یعنی وقتی نسخه‌ی ۱.۴ بیرون رفت، یک branch برایش نگه می‌دارید تا فقط باگ‌های آن نسخه را رفع کنید و آن اصلاح‌ها را (با cherry-pick) به `main` هم برسانید.

پیش‌فرض من GitHub flow است و release branch را فقط برای patch کردن نسخه‌ی قدیمی می‌گیرم. در همه‌ی این الگوها یک ابزار کمک می‌کند: {{< term "branch-protection" "branch protection" >}}، یک قانون سمت سرور که می‌گوید `main` فقط از راه pull request با review و checkهای سبز تغییر کند. همین وبلاگ این‌طور کار می‌کند. پنج merge آخر آن، هنگام نوشتن این مقاله:

```bash
git log --oneline --merges -5
```

```text
3d46fe0 Merge pull request #14 from h-agharezaei/post-binance-hack
e199ee2 Merge pull request #13 from h-agharezaei/switch-domain-justroham
3235020 Merge pull request #12 from h-agharezaei/switch-domain-justroham
677819c Merge pull request #11 from h-agharezaei/switch-domain-justroham
5831598 Merge pull request #10 from h-agharezaei/switch-domain-justroham
```

هر خط یک merge commit است که pull request را به `main` آورده. (روی سیستم شما، در repository دیگری، چیز دیگری می‌بینید؛ و برای این وبلاگ هم با هر pull request تازه، فهرست جلو می‌رود.)

## Objectهای loose و packfile

حالا به داخل `.git` برویم. هر object (commit، tree، blob) وقتی ساخته می‌شود، اول به‌شکل یک فایل جدا روی دیسک می‌نشیند. به این حالت «loose» (آزاد) می‌گویند. این ساده و سریع است، ولی وقتی یک فایل بزرگ بارها عوض می‌شود، هر نسخه‌ی آن یک فایل کامل می‌شود، حتی اگر فقط یک خطش فرق کند.

برای دیدن اثرش یک repository ساختم با یک فایل ۲۰۰۰ خطی و ۴۰ ویرایش کوچک، هرکدام یک commit. بعد تعداد objectها و اندازه‌ی `.git` را گرفتم:

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

`count` تعداد objectهای loose است و `size` حجم آن‌ها به کیلوبایت. `in-pack: 0` و `packs: 0` یعنی هنوز هیچ objectای فشرده نشده. (نقطه‌چین جای چند خط دیگر است که اینجا مهم نیستند.) پس ۱۲۳ object loose داریم و `.git` حدود ۳.۳ مگابایت است، چون هر نسخه‌ی فایل کامل ذخیره شده است. حالا garbage collection:

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

این بار `count: 0`: دیگر object loose نداریم. هر ۱۲۳ object توی یک pack هستند (`in-pack: 123`، `packs: 1`) و اندازه‌ی `.git` از ۳۳۸۴ به ۲۶۸ کیلوبایت رسیده. {{< term "packfile" "Packfile" >}} یعنی یک فایل که چند object را کنار هم نگه می‌دارد، و فایل `.idx` کنارش فهرستی است که می‌گوید هر object کجای pack است.

بیشتر کوچک‌شدن از {{< term "delta-compression" "delta compression" >}} می‌آید. ایده ساده است: وقتی نسخه‌ی ۲۰ و ۲۱ یک فایل تقریباً یکی‌اند، لازم نیست هر دو را کامل نگه داشت. یکی را کامل ذخیره می‌کنیم و دیگری را فقط به‌صورت یک diff کوچک نسبت به آن (یک delta). `git verify-pack -v` همین را نشان می‌دهد. خروجی کامل طولانی است؛ این قسمت‌هایش را می‌بینید (offsetها در هر اجرا فرق می‌کنند)، به‌همراه جمع‌بندی آخر:

```text
8dc7cd65... blob 143281 69145 5295
48db3cc6... blob     43    48 74531 1 8dc7cd65...
36070a34... blob     43    45 74698 5 80839e73...
non delta: 84 objects
chain length = 1: 5 objects
chain length = 2: 3 objects
chain length = 3: 4 objects
chain length = 4: 2 objects
chain length = 5: 4 objects
chain length = 6: 4 objects
chain length = 7: 3 objects
chain length = 8: 2 objects
chain length = 9: 5 objects
chain length = 10: 3 objects
chain length = 11: 3 objects
chain length = 12: 1 object
```

ستون‌های هر خط به ترتیب: شناسه، نوع، اندازه‌ی اصلی، اندازه‌ی داخل pack، محل در فایل (offset)، و برای deltaها عمق زنجیره و شناسه‌ی base. خط اول یک blob ۱۴۳ کیلوبایتی است که کامل نگه داشته شده (و با فشرده‌سازی معمولی در pack ۶۹ کیلوبایت جا گرفته). خط دوم نسخه‌ای دیگر است که فقط ۴۳ بایت است: یک دستور نسبت به همان blob اول، با عمق ۱. خط سوم عمق ۵ دارد، یعنی برای ساختنش باید پنج delta را پشت سر هم روی base اعمال کرد.

خط‌های `chain length` در پایین می‌گویند چند object در هر عمق قرار دارند، و `non delta: 84 objects` یعنی ۸۴ object (commit، tree و blobهای پایه) کامل ذخیره شده‌اند. از ۴۱ blob این repository ۳۹ تا delta بودند و عمق زنجیره‌ها تا ۱۲ می‌رسید. دستور `git repack -a -d` همه‌چیز را از نو در یک pack بازنویسی می‌کند؛ اینجا چیزی عوض نشد چون `gc` همین کار را کرده بود.

## repositoryهای بزرگ: shallow، partial، sparse

حالا یک سؤال عملی. repositoryی با تاریخچه‌ی ده ساله و هزاران فایل دارید و می‌خواهید فقط یک تغییر کوچک بدهید. چرا باید همه‌چیز را دانلود کنید؟ سه گزینه هست که بخشی را نمی‌گیرند.

برای مقایسه یک repository سرور کوچک ساختم: ۷ commit، ۵ سند و یک فایل کد، که در هر commit همه‌ی شش فایل عوض می‌شوند (جمعاً ۷۰ object)، و روی آن `uploadpack.allowFilter` را روشن کردم تا سرور فیلتر را قبول کند. تعداد objectهای هر نوع clone:

| Clone | دستور | Object |
|---|---|---|
| کامل | `git clone file://...` | ۷۰ |
| {{< term "shallow-clone" "Shallow" >}} (کم‌عمق) | `--depth 1` | ۱۰ (۱ commit، ۳ tree، ۶ blob) |
| {{< term "partial-clone" "Partial" >}} (جزئی) | `--filter=blob:none` | ۳۴ (۷ commit، ۲۱ tree، ۶ blob) |

clone کم‌عمق فقط آخرین commit را می‌گیرد، پس `git log` یک خط نشان می‌دهد. `git fetch --unshallow` بعداً هر ۷ commit و ۴۲ blob را برگرداند. clone جزئی تاریخچه‌ی کامل را دارد ولی blobها، یعنی محتوای فایل‌ها را، فقط در صورت نیاز می‌گیرد: مثلاً `git show HEAD~3:docs/doc1.txt` یک blob گم‌شده را از سرور گرفت (بعدش ۷ blob داشتم). Git به آن سرور می‌گوید «promisor remote»، چون قول داده objectهای کم را بعداً بدهد؛ یعنی بعداً به شبکه نیاز دارید.

سومی، {{< term "sparse-checkout" "sparse checkout" >}}، به تعداد objectها کاری ندارد و کنترل می‌کند کدام پوشه‌ها روی دیسک (در working tree) ظاهر شوند. با partial clone که ترکیب شود، فقط blobهای همان پوشه‌ها دانلود می‌شوند:

```bash
git clone --filter=blob:none --sparse file://... sp
git sparse-checkout set app
ls
```

```text
app
```

clone با `--sparse` با ۰ blob شروع شد و روی دیسک هیچ پوشه‌ای نبود. بعد از `set app` یک blob دانلود شد (فایل کد) و فقط `app/` روی دیسک ظاهر شد. partial clone به‌علاوه‌ی sparse checkout ترکیب معمول برای monorepoهای بزرگ است.

`git maintenance` می‌تواند کارهای نگهداری شبیه `gc` را در پس‌زمینه انجام دهد؛ آن را اجرا نکردم.

## بهای میان‌برها

- **clone کم‌عمق تاریخچه ندارد.** پس `git log` و `git blame` چیز کمی می‌بینند.
- **clone جزئی بعداً به remote نیاز دارد.** آفلاین، نبودنِ blob خطاست.
- **`gc` بعد از یک مهلت، objectهای unreachable را پاک می‌کند.** طبق مستندات Git این مهلت به‌طور پیش‌فرض حدود دو هفته است (`gc.pruneExpire`؛ این را خودم امتحان نکردم). پس commitهای بدون ارجاع backup نیستند.
- **Branch protection جایش روی سرور است.** hookهای محلی را می‌شود رد کرد، همان‌طور که در مقاله‌ی hookها دیدیم.

## جمع‌بندی سری

گیت objectهای تغییرناپذیر نگه می‌دارد، نام branch اشاره‌گر به آن‌هاست و بیشتر دستورها یا object اضافه می‌کنند یا اشاره‌گر را جابه‌جا. نُه مقاله‌ی قبلی به ترتیب:

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

مطلب بعدی تقویم «مدل رابطه‌ای و SQL ضروری»، شروع سری Databases است.
