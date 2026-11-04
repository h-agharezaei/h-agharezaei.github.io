+++
date = '2026-12-02T18:00:00+03:30'
draft = false
title = 'مهندسی صرافی: واریز، برداشت، confirmation و reorg'
description = 'واریز و برداشت صرافی با Go و Postgres: ماشین حالت واریز، دفتر دوطرفه، یک reorg واقعی روی anvil، کلید idempotency و جایگزینی تراکنش گیرکرده.'
contentType = 'engineering'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "exchange"]
cover = { image = "/images/covers/bc-exchange-deposits-withdrawals.fa.png", alt = "مهندسی صرافی: واریز، برداشت، confirmation و reorg", hiddenInSingle = true }
+++

فرض کنید کاربری ۱۰۰ توکن به صرافی شما می‌فرستد. تراکنش در یک بلاک می‌آید. اگر همان لحظه ۱۰۰ توکن به حسابش اضافه کنید و کمی بعد آن بلاک با یک {{< term "chain-reorganization" "reorg" >}} از زنجیره کنار برود، کاربر هم توکن‌های خودش را دارد و هم ۱۰۰ توکن اعتبار از شما. برداشت هم مشکل‌های خودش را دارد: یک درخواست می‌تواند با دوبار کلیک هم‌زمان دو بار برسد، و تراکنش امضاشده می‌تواند با کارمزد کم گیر کند و هیچ‌وقت وارد بلاک نشود.

بعد از رمزنگاری [مبانی zero-knowledge proof با Rust](/fa/posts/bc-zero-knowledge-rust/)، این مقاله کار معمولی بک‌اند است: رویدادهای زنجیره را به موجودی تبدیل کنیم، و موجودی را به تراکنش. جواب سؤال‌ها همان چیزهایی است که در بقیه‌ی مهندسی نرم‌افزار هم می‌شناسیم: state machine، تراکنش دیتابیس و idempotency.

ماژول [Event و ساخت indexer با Go و Postgres](/fa/posts/bc-event-indexer-go/) را کپی کردم، indexerش را به اسکنر واریز تبدیل کردم و دفتر حساب و برداشت را اضافه کردم. آدرس‌ها از [کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust](/fa/posts/bc-hd-wallets-rust/) می‌آیند و امضا و nonce از [کار با اتریوم از Go با go-ethereum](/fa/posts/bc-go-ethereum-client/). این یک طراحی آموزشی است، نه یک صرافی کامل، و چیزی درباره‌ی ساختار داخلی هیچ صرافی واقعی نمی‌گوید.

> اجرا با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10، pgx v5.11.0 و PostgreSQL 18.3 از `embedded-postgres`. یک anvil تازه روی `127.0.0.1:8547` با اسکریپت deploy مقاله‌ی توکن‌ها. همه‌ی کلیدها و آدرس‌ها **حساب‌های تست عمومی** anvil هستند. مسیرهای موقت `<tmp>` نوشته شده‌اند. در همه‌ی نمونه‌های پایین `X` یعنی برنامه‌ی `exchange` (ساخته‌شده از `./cmd/exchange`) با گزینه‌ی `-pgdir <tmp>/pg`. کلید کیف‌پول داغ همان حساب شماره‌ی ۹ anvil است. پیش از شروع، حساب شماره‌ی ۰ هزار DEMO به آن فرستاده تا برای برداشت توکن داشته باشد (این تراکنش بلاک ۴ است).

## آدرس واریز

اول باید بدانیم هر واریز مال کیست. راهش این است که هر کاربر آدرس مخصوص خودش را داشته باشد؛ هر توکنی که به آن آدرس برسد مال همان کاربر است. به این آدرس {{< term "deposit-address" "آدرس واریز" >}} می‌گویند. در محیط واقعی من آن را به شکل `xpub/0/index` از یک {{< term "xpub" "xpub" >}} مشتق می‌کنم، همان‌طور که در مقاله‌ی کیف‌پول HD دیدیم، تا سرویس واریز هیچ کلید خصوصی‌ای نداشته باشد. در این دمو حساب‌های ۱ و ۲ anvil جای alice و bob هستند.

اسکنر فقط انتقال‌هایی را می‌خواهد که **به** این آدرس‌ها رفته باشند. فیلتر روی لاگ‌های توکن همین است:

```go
Topics: [][]common.Hash{{transferTopic}, nil, topicTo}, // Transfer(any, ours)
```

سه جایگاه به ترتیب یعنی: رویداد `Transfer`، فرستنده‌ی دلخواه (`nil`)، و گیرنده‌ای از میان آدرس‌های ما.

## وضعیت‌های یک واریز و دفتر حساب

هر واریز را مثل یک {{< term "state-machine" "ماشین حالت" >}} کوچک ببینید. وقتی لاگ برای اولین بار دیده شود `seen` است. تا وقتی کمتر از N {{< term "confirmation" "تأیید" >}} (یعنی N بلاک روی بلاک واریز) دارد `pending` است. وقتی به N برسد `credited` می‌شود و پول به حساب می‌رود. و اگر پیش از آن reorg بلاکش را حذف کند `orphaned` می‌شود. کد این گذارها را صریح نوشته است:

```go
var allowed = map[string][]string{
	"seen":     {"pending", "credited", "orphaned"},
	"pending":  {"pending", "credited", "orphaned"},
	"orphaned": {"seen"}, // the same log came back in another block
	"credited": {},       // final; a reorg past N needs a human
}
// move(): UPDATE deposits SET status = $to WHERE tx_hash = .. AND log_index = .. AND status = $from
```

هر گذاری که در این جدول نیست خطای برنامه است. `orphaned` فقط می‌تواند به `seen` برگردد، برای وقتی که همان تراکنش در بلاک دیگری دوباره بیاید. `credited` پایانی است: اگر reorg حتی بعد از N هم بلاکی را بردارد، باید آدمی بررسی کند، نه کد. همچنین `move` فقط وقتی وضعیت را عوض می‌کند که هنوز در وضعیت قبلی باشد (`AND status = $from`)، پس دو پروسه‌ی هم‌زمان نمی‌توانند یک واریز را دوبار جلو ببرند.

ردیف واریز با `(tx_hash, log_index)` شناسایی می‌شود، مثل مقاله‌ی indexer: هر لاگ فقط یک بار ثبت می‌شود.

پول را در یک {{< term "double-entry-bookkeeping" "دفتر حساب دوطرفه" >}} نگه می‌داریم. اصل ساده است: هر رویداد مالی یک «سند» (journal) است و جمع مبلغ‌های همه‌ی سطرهای سند صفر است. وقتی کاربر ۱۰۰ توکن واریز می‌کند، سند دو سطر دارد: حساب `external` (یعنی دنیای بیرون) منفی ۱۰۰ و حساب کاربر مثبت ۱۰۰. پول نه از هیچ ساخته می‌شود و نه گم می‌شود. هر سند یک `ref` یکتا دارد (برای واریز `deposit:<tx>:<log index>`)، پس یک واریز را نمی‌شود دوبار به حساب گذاشت:

```go
posted, err := post(ctx, tx, fmt.Sprintf("deposit:%s:%d", d.hash, d.idx),
	line{"external", neg(amt)},
	line{"user:" + d.user, amt})
// then move(..., "credited") in the same DB transaction
```

بعد از `post`، تغییر وضعیت به `credited` در همان تراکنش دیتابیس انجام می‌شود. یا هر دو اتفاق می‌افتند یا هیچ‌کدام.

## reorg پیش از N، و بعد رسیدن به N

حالا ببینیم این‌ها در عمل چه می‌کنند. می‌خواهم یک reorg واقعی را روی anvil بسازم. anvil یک snapshot می‌گیرد و بعد با revert زنجیره را به آن لحظه برمی‌گرداند، یعنی بلاک‌هایی که بعد از snapshot آمده‌اند ناپدید می‌شوند. در دستورها `$T` توکن است، `$A0` فرستنده، `$ALICE` آدرس واریز alice و N برابر ۳ است (تعداد تأیید = `head − شماره‌ی بلاک + 1`).

سناریو: snapshot می‌گیریم، ۱۰۰ DEMO به alice می‌فرستیم، اسکن می‌کنیم، یک بلاک می‌سازیم و دوباره اسکن می‌کنیم. بعد revert می‌کنیم و سه بلاک جدید می‌سازیم، یعنی زنجیره‌ی دیگری که آن تراکنش در آن نیست. اسکن آخر باید این را بفهمد.

```
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $ALICE 100ether --unlocked --from $A0   # block 5
$ X scan -confirmations 3
head 5, cursor -1, N 3
deposit alice 100 DEMO tx 0x1ee92a01 block 5: seen
deposit alice 100 DEMO: seen -> pending (1/3)
$ cast rpc anvil_mine 1
$ X scan -confirmations 3
head 6, cursor 5, N 3
deposit alice 100 DEMO: pending -> pending (2/3)
$ cast rpc evm_revert 0x0
true
$ cast rpc anvil_mine 3
$ X scan -confirmations 3
reorg: fork point 4, dropping blocks 5-6
deposit alice 100 DEMO tx 0x1ee92a01: pending -> orphaned
head 7, cursor 4, N 3
$ X balances
external             0 DEMO
user:alice           0 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast output trimmed)
```

خط‌به‌خط:

- **اسکن اول:** `cursor -1` یعنی هنوز هیچ بلاکی را نخوانده‌ایم و از ابتدا می‌خوانیم. تراکنش در بلاک ۵ است و head هم ۵، پس فقط یک تأیید دارد: `1/3`. وضعیت `seen` و بلافاصله `pending`.
- **اسکن دوم:** یک بلاک اضافه شده و head برابر ۶ است. حالا `2/3`. هنوز به N نرسیده، پس پولی داده نمی‌شود.
- **revert:** زنجیره به زمان snapshot برمی‌گردد و بلاک‌های ۵ و ۶ حذف می‌شوند. سه بلاک جدید می‌سازیم (۵ تا ۷) که تراکنش در آن‌ها نیست.
- **اسکن آخر:** اسکنر برای هر بلاکی که در دیتابیس دارد، hash را با hash فعلی زنجیره مقایسه می‌کند و از بالا به پایین می‌گردد تا به بلاکی برسد که هنوز یکی است. این `fork point` است، اینجا بلاک ۴. همه‌ی بلاک‌های بالاتر کنار می‌روند (۵ تا ۶)، و واریز آن‌ها `orphaned` می‌شود. حذف نمی‌شود، چون ممکن است در بلاک دیگری برگردد.
- **balances:** هیچ پولی جابه‌جا نشده. جمع همه‌ی حساب‌ها صفر است.

واریز هیچ‌وقت به حساب نرفت، و این همان هدف بود. این‌جا تراکنش کاملاً ناپدید شد. در یک reorg واقعی ممکن است در بلاک دیگری برگردد، که همان گذار `orphaned -> seen` است.

حالا واریز دوم: ۱۲۰ DEMO در بلاک ۸ می‌آید. اسکن اول آن را `pending (1/3)` می‌کند (اسکن و خروجی `cast send` را حذف کرده‌ام). دو بلاک می‌سازیم و دوباره اسکن می‌کنیم. بعد با `-rewind 4` نشانگر اسکنر را عمداً به بلاک ۴ برمی‌گردانیم، تا شبیه‌سازی کنیم که برنامه وسط کار crash کرده و باید دوباره بلاک‌های قبلی را بخواند:

```
$ cast rpc anvil_mine 2
$ X scan -confirmations 3
head 10, cursor 8, N 3
deposit alice 120 DEMO: pending -> credited (3/3), journal posted: true
$ X scan -confirmations 3 -rewind 4
head 10, cursor 4, N 3
$ X balances
external             -120 DEMO
user:alice           120 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast send and the first scan, 1/3, trimmed)
```

- **اسکن اول:** واریز در بلاک ۸ است و head برابر ۱۰، پس سه تأیید دارد (`3/3`). `credited` شد و سند حساب ثبت شد (`journal posted: true`).
- **اسکن با rewind:** اسکنر بلاک‌های ۵ تا ۱۰ را دوباره خواند، لاگ بلاک ۸ را دوباره دید و **هیچ کاری نکرد**. کلید `(tx_hash, log_index)` و `ref` یکتای سند جلوی ثبت دوباره را گرفتند.
- **balances:** `external` منفی ۱۲۰ است (۱۲۰ از بیرون آمده) و alice مثبت ۱۲۰ (صرافی این‌قدر به او بدهکار است). جمع صفر.

## برداشت

برداشت سه خطر دارد: درخواست تکراری، خرج‌کردن یک موجودی دو بار، و کرش وسط امضا و ارسال. برای هر کدام یک راه داریم.

برای درخواست تکراری، هر درخواست یک {{< term "idempotency-key" "کلید idempotency" >}} دارد که برای هر کاربر یکتاست؛ مثلاً کلاینت برای هر کلیک کاربر یک کلید می‌سازد. اگر همان کلید دوباره برسد، درخواست جدیدی ساخته نمی‌شود و همان درخواست قبلی برگردانده می‌شود. درج درخواست، بررسی ریسک (این‌جا سقف ۱۰۰ DEMO برای هر درخواست)، قفل ردیف حساب کاربر، بررسی موجودی و انتقال مبلغ به `withdrawals:pending` همه در یک تراکنش دیتابیس‌اند، مثل [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/). قفل ردیف باعث می‌شود دو درخواست مختلف نتوانند هم‌زمان یک موجودی را خرج کنند. خلاصه‌شده:

```
INSERT INTO withdrawals (...) ... ON CONFLICT (user_id, idem_key) DO NOTHING RETURNING id
// no row: return the existing request (error if amount or address differ)
SELECT 1 FROM accounts WHERE name = $1 FOR UPDATE
post(ctx, tx, fmt.Sprintf("withdrawal:%d:reserve", id),
	line{acct, neg(amt)}, line{"withdrawals:pending", amt})
```

مبلغ برداشت اول از حساب کاربر به `withdrawals:pending` می‌رود. یعنی «رزرو» می‌شود، پیش از اینکه چیزی به زنجیره برود.

برای امضا و ارسال، دستور `send` {{< term "nonce" "nonce" >}} بعدی را از یک ردیف قفل‌شده به اسم `hot_wallet` می‌گیرد. این ردیف همان مدیر nonce مقاله‌ی go-ethereum است و بین همه‌ی workerها مشترک است. تراکنش را با {{< term "hot-wallet" "کیف‌پول داغ" >}} (کیف‌پولی که کلیدش آنلاین است) امضا می‌کند و بایت‌های امضاشده را **پیش از ارسال** ذخیره می‌کند. پس اگر وسط کار crash شود، فقط همان بایت‌ها دوباره فرستاده می‌شوند و hash همان است، نه یک تراکنش دوم. `track` بعد از N تأیید برداشت را نهایی می‌کند، یا اگر رسید تراکنش شکست را نشان بدهد رزرو را آزاد می‌کند (این شاخه در کد هست ولی در این اجرا اتفاق نیفتاد).

اول یک درخواست یکسان را دو بار هم‌زمان می‌فرستیم (`-parallel 2`، مثل دوبار کلیک). `$A3` مقصد است:

```
$ X withdraw -user alice -to $A3 -amount 30 -key w-1 -parallel 2
withdrawal #1 already exists: reserved
withdrawal #1 created: reserved
$ X send
withdrawal #1 signed: nonce 0, tx 0xc295cb2f
withdrawal #1 sent: 0xc295cb2f
$ X send
nothing to send
$ cast rpc anvil_mine 2
$ X track
withdrawal #1: confirmed via 0xc295cb2f (3/3)
$ cast nonce $HOT
1
$ X withdraw -user alice -to $A3 -amount 30 -key w-1
withdrawal #1 already exists: confirmed
$ X withdraw -user alice -to $A3 -amount 150 -key w-2
withdrawal #4 created: rejected (over the per-withdrawal limit)
$ X withdraw -user alice -to $A3 -amount 95 -key w-3
withdrawal #5 created: rejected (insufficient balance 90)
$ X withdraw -user alice -to $A3 -amount 31 -key w-1
error: idempotency key "w-1" reused with a different request
$ X withdraw -user alice -to $A3 -amount 10 -key w-4
withdrawal #7 created: reserved
```

خط‌به‌خط:

- **دو درخواست هم‌زمان:** یکی `created` شد و دیگری فهمید قبلاً وجود دارد. کدام یکی «created» را می‌گوید ممکن است در هر اجرا فرق کند؛ مهم این است که فقط یک برداشت ساخته شد.
- **اولین `send`:** برداشت با nonce صفر امضا و فرستاده شد. hash تراکنش ممکن است در اجرای شما فرق کند، چون به کارمزد آن لحظه بستگی دارد. **دومین `send`** چیزی برای فرستادن نداشت.
- **`track`:** بعد از دو بلاک اضافه، تراکنش سه تأیید دارد و برداشت `confirmed` می‌شود. `cast nonce $HOT` برابر ۱ است: روی زنجیره فقط یک تراکنش رفت.
- **درخواست تکراری با همان کلید و همان مبلغ:** همان برداشت قبلی را با وضعیتش (`confirmed`) پس می‌دهد.
- **۱۵۰ DEMO:** از سقف ۱۰۰ بیشتر است، رد شد.
- **۹۵ DEMO:** alice بعد از رزرو ۳۰ تا فقط ۹۰ دارد، رد شد.
- **کلید `w-1` با مبلغ ۳۱:** همان کلید با درخواست دیگر، خطا. کلید باید به یک درخواست مشخص بسته باشد.
- **آخرین:** ۱۰ DEMO با کلید جدید رزرو شد.

شماره‌ی برداشت‌ها پرش دارند (#1، بعد #4، #5، #7). دلیل: درج متعارض هم یک مقدار از sequence دیتابیس مصرف می‌کند، حتی اگر ردیفی ساخته نشود. مقایسه کنید با [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/).

## برداشت گیرکرده

برداشت شماره‌ی ۷ را ببینیم. اگر تراکنشی با کارمزد کم فرستاده شود و هیچ‌وقت در بلاک نیاید، نباید کاربر را معطل بگذاریم و نباید nonce را هم دور بریزیم، چون nonceهای بعدی پشت آن می‌مانند. راه درست این است که همان تراکنش را با **همان nonce** و کارمزد بیشتر دوباره بفرستیم. این همان {{< term "replace-by-fee" "replace-by-fee" >}} است که در [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/) دیدیم. هر کدام از دو نسخه که در بلاک بیفتد، nonce فقط یک بار مصرف می‌شود.

anvil سقف کارمزد کمتر از base fee را رد کرد، پس گیرکردن را با خاموش‌کردن automine شبیه‌سازی کردم، یعنی تراکنش‌ها تا وقتی خودم بلاک نسازم در صف می‌مانند. دستور `bump` همان فراخوانی را با کارمزد دوبرابر دوباره امضا می‌کند:

```
$ cast rpc evm_setAutomine false
$ X send
withdrawal #7 signed: nonce 1, tx 0x45267a5e
withdrawal #7 sent: 0x45267a5e
$ X track
withdrawal #7: no receipt for 1 attempt(s) at nonce 1
$ X bump -id 7
withdrawal #7: replaced 0x45267a5e with 0x27b7e080, nonce 1, tip 1 -> 2 gwei
$ cast rpc txpool_status
{"pending":"0x1","queued":"0x0"}
$ cast rpc anvil_mine 1
$ cast rpc evm_setAutomine true
$ cast rpc anvil_mine 2
$ X track
withdrawal #7: confirmed via 0x27b7e080 (3/3)
$ cast nonce $HOT
2
```

- **`send`:** برداشت ۷ با nonce ۱ امضا و ارسال شد، ولی automine خاموش است، پس در بلاک نمی‌آید.
- **`track`:** هیچ رسیدی نیست. برداشت گیر کرده.
- **`bump`:** همان تراکنش با همان nonce و با tip برابر ۲ gwei (به‌جای ۱) فرستاده شد و جای قبلی را گرفت.
- **`txpool_status`:** در صف فقط یک تراکنش هست (`pending: 1`)، یعنی نسخه‌ی جدید جایگزین نسخه‌ی قدیمی شد و دو تا نیستند.
- **آخر:** بلاک ساخته شد، سه تأیید رسید و `track` برداشت را `confirmed` کرد. nonce کیف‌پول داغ حالا ۲ است: دو تراکنش، نه سه.

`track` رسید **همه‌ی** تلاش‌های ذخیره‌شده را می‌گردد، چون هر کدام ممکن است همان باشد که در بلاک افتاده.

## کیف‌پول داغ، سرد و sweep

این بخش کد ندارد. {{< term "sweeping" "Sweep" >}} یعنی جمع‌کردن واریزها از آدرس‌های زیاد کاربران به کیف‌پول‌های خود صرافی. برای توکن ERC-20 هر آدرس واریز اول باید ETH برای gas داشته باشد تا بتواند توکن را بفرستد. کیف‌پول داغ فقط به اندازه‌ی برداشت‌های نزدیک پول دارد. بقیه در {{< term "cold-wallet" "کیف‌پول سرد" >}} می‌ماند و با انتقال‌هایی که آدم‌ها دستی تأیید می‌کنند کیف‌پول داغ را دوباره پر می‌کند. [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) نشان می‌دهد چرا هر چیزی که می‌تواند از کیف‌پول داغ امضا بخواهد به اندازه‌ی خود کلید مهم است.

## قاعده‌هایی که دفتر را درست نگه می‌دارند

- فقط در N تأیید پول را به حساب بگذارید، و برای reorg عمیق‌تر از N هم هشدار داشته باشید. پولی را که به حساب رفته خودکار برنگردانید.
- nonceهای یک کیف‌پول داغ مال یک پروسه است. یک `cast send` دستی با همان کلید شمارنده را خراب می‌کند.
- تراکنش امضاشده را پیش از ارسال ذخیره کنید. تلاش دوباره باید همان را بفرستد، نه امضای تازه بسازد.
- جمع کل دفتر باید صفر باشد. با موجودی واقعی روی زنجیره هم تطبیقش دهید (reconciliation): یعنی موجودی کیف‌پول‌ها روی زنجیره را با آنچه دفتر می‌گوید صرافی بدهکار است مقایسه کنید و هر اختلاف را بررسی کنید. این مقایسه را در دمو ننوشتم.

## قدم بعدی

**پروژه‌ی پایانی بلاکچین با Go و Rust**: کلید امضای این بک‌اند را به یک signer جدا می‌برد.
