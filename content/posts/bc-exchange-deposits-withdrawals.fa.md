+++
date = '2027-07-13T10:00:00+03:30'
draft = false
title = 'مهندسی صرافی: واریز، برداشت، confirmation و reorg'
description = 'واریز و برداشت صرافی با Go و Postgres: ماشین حالت واریز، دفتر دوطرفه، یک reorg واقعی روی anvil، کلید idempotency و جایگزینی تراکنش گیرکرده.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "exchange"]
cover = { image = "/images/covers/bc-exchange-deposits-withdrawals.fa.png", alt = "مهندسی صرافی: واریز، برداشت، confirmation و reorg", hiddenInSingle = true }
+++

پست قبلی، [مبانی zero-knowledge proof با Rust](/fa/posts/bc-zero-knowledge-rust/)، رمزنگاری بود. این یکی کار بک‌اند است: تبدیل رویداد زنجیره به موجودی و موجودی به تراکنش.

ماژول [Event و ساخت indexer با Go و Postgres](/fa/posts/bc-event-indexer-go/) را کپی کردم، indexerش را اسکنر واریز کردم و دفتر حساب و برداشت افزودم. آدرس‌ها از [کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust](/fa/posts/bc-hd-wallets-rust/) می‌آیند و امضا و nonce از [کار با اتریوم از Go با go-ethereum](/fa/posts/bc-go-ethereum-client/). این یک طراحی آموزشی است، نه یک صرافی کامل، و چیزی درباره‌ی ساختار داخلی هیچ صرافی واقعی نمی‌گوید.

> اجرا با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10، pgx v5.11.0 و PostgreSQL 18.3 از `embedded-postgres`. یک anvil تازه روی `127.0.0.1:8547` با اسکریپت دیپلوی پست توکن‌ها. همه‌ی کلیدها و آدرس‌ها **حساب‌های تست عمومی** anvil هستند. مسیرهای موقت `<tmp>` نوشته شده‌اند.

## آدرس واریز

هر کاربر یک {{< term "deposit-address" "آدرس واریز" >}} می‌گیرد. در محیط واقعی آن را مثل BC20 به شکل `xpub/0/index` از یک {{< term "xpub" "xpub" >}} می‌سازم تا سرویس واریز کلید خصوصی نداشته باشد؛ این‌جا حساب‌های ۱ و ۲ anvil جای آدرس alice و bob را گرفته‌اند. اسکنر فقط انتقال‌های *به* این آدرس‌ها را می‌خواهد:

```go
Topics: [][]common.Hash{{transferTopic}, nil, topicTo}, // Transfer(any, ours)
```

## وضعیت واریز و دفتر حساب

هر واریز یک {{< term "state-machine" "ماشین حالت" >}} کوچک است: `seen` وقتی log اولین بار دیده می‌شود، `pending` تا وقتی کمتر از N {{< term "confirmation" "confirmation" >}} دارد، `credited` در N، و `orphaned` اگر یک {{< term "chain-reorganization" "reorg" >}} زودتر حذفش کند:

```go
var allowed = map[string][]string{
	"seen":     {"pending", "credited", "orphaned"},
	"pending":  {"pending", "credited", "orphaned"},
	"orphaned": {"seen"}, // the same log came back in another block
	"credited": {},       // final; a reorg past N needs a human
}
// move(): UPDATE deposits SET status = $to WHERE tx_hash = .. AND log_index = .. AND status = $from
```

کلید ردیف واریز مثل BC19 همان `(tx_hash, log_index)` است. پول در یک دفتر {{< term "double-entry-bookkeeping" "دوطرفه (double-entry)" >}} است: جمع ردیف‌های هر journal صفر است، `external` طرف دنیای بیرون است، و `ref` هر journal (`deposit:<tx>:<log index>`) یکتاست، پس دو بار واریز به حساب ممکن نیست:

```go
posted, err := post(ctx, tx, fmt.Sprintf("deposit:%s:%d", d.hash, d.idx),
	line{"external", neg(amt)},
	line{"user:" + d.user, amt})
// then move(..., "credited") in the same DB transaction
```

## یک reorg پیش از N، و بعد رسیدن به N

`$T` توکن است، `$A0` فرستنده، `$ALICE` آدرس alice و N = 3 (confirmation یعنی head − block + 1). reorg را مثل BC19 با snapshot و revert در anvil می‌سازم:

```
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $ALICE 100ether --unlocked --from $A0   # block 5
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 5, cursor -1, N 3
deposit alice 100 DEMO tx 0x1ee92a01 block 5: seen
deposit alice 100 DEMO: seen -> pending (1/3)
$ cast rpc anvil_mine 1
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 6, cursor 5, N 3
deposit alice 100 DEMO: pending -> pending (2/3)
$ cast rpc evm_revert 0x0
true
$ cast rpc anvil_mine 3
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
reorg: fork point 4, dropping blocks 5-6
deposit alice 100 DEMO tx 0x1ee92a01: pending -> orphaned
head 7, cursor 4, N 3
$ go run ./cmd/exchange -pgdir <tmp>/pg balances
external             0 DEMO
user:alice           0 DEMO
...
(cast output trimmed)
```

هیچ‌وقت به حساب نرفت. این‌جا تراکنش ناپدید شد؛ در reorg واقعی ممکن است در بلاک دیگری برگردد: مسیر `orphaned -> seen`. واریز دوم، ۱۲۰ DEMO، در بلاک ۸ می‌نشیند:

```
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 10, cursor 8, N 3
deposit alice 120 DEMO: pending -> credited (3/3), journal posted: true
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3 -rewind 4
head 10, cursor 4, N 3
$ go run ./cmd/exchange -pgdir <tmp>/pg balances
external             -120 DEMO
user:alice           120 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast send and the first scan, 1/3, trimmed)
```

اسکن با cursor عقب‌رفته بلاک ۸ را دوباره خواند و کاری نکرد.

## برداشت

هر درخواست یک {{< term "idempotency-key" "کلید idempotency" >}} دارد که برای هر کاربر یکتاست. درج، بررسی ریسک (این‌جا سقف ۱۰۰ DEMO)، قفل ردیف حساب کاربر، بررسی موجودی و انتقال مبلغ به `withdrawals:pending` همه در یک تراکنش دیتابیس‌اند، مثل [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/). خلاصه‌شده:

```
INSERT INTO withdrawals (...) ... ON CONFLICT (user_id, idem_key) DO NOTHING RETURNING id
// no row: return the existing request (error if amount or address differ)
SELECT 1 FROM accounts WHERE name = $1 FOR UPDATE
post(ctx, tx, fmt.Sprintf("withdrawal:%d:reserve", id),
	line{acct, neg(amt)}, line{"withdrawals:pending", amt})
```

`send` مقدار {{< term "nonce" "nonce" >}} بعدی را از یک ردیف قفل‌شده‌ی `hot_wallet` برمی‌دارد (nonce manager پست BC17، مشترک بین workerها)، با {{< term "hot-wallet" "کیف‌پول داغ" >}} امضا می‌کند و بایت‌های امضاشده را پیش از ارسال ذخیره می‌کند؛ پس crash یعنی ارسال دوباره‌ی همان hash. `track` بعد از N confirmation تسویه می‌کند، یا با receipt ناموفق مبلغ رزروشده را آزاد می‌کند (در کد هست، در این اجرا راهش نینداختم). یک درخواست، دو بار هم‌زمان:

```
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 30 -key w-1 -parallel 2
withdrawal #1 already exists: reserved
withdrawal #1 created: reserved
$ go run ./cmd/exchange -pgdir <tmp>/pg send
withdrawal #1 signed: nonce 0, tx 0x66fc1a20
withdrawal #1 sent: 0x66fc1a20
$ go run ./cmd/exchange -pgdir <tmp>/pg send
nothing to send
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #1: confirmed via 0x66fc1a20 (3/3)
$ cast nonce $HOT
1
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 95 -key w-3
withdrawal #5 created: rejected (insufficient balance 90)
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 31 -key w-1
error: idempotency key "w-1" reused with a different request
(other runs trimmed)
```

فقط یک تراکنش روی زنجیره. شماره‌ها پرش دارند چون درج‌های متعارض هم sequence مصرف می‌کنند. مقایسه کنید با [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/).

## برداشتِ گیرکرده

anvil سقف کارمزد کمتر از base fee را رد کرد، پس گیرکردن را با خاموش‌کردن automine شبیه‌سازی کردم. `bump` همان فراخوانی را با **همان nonce** و کارمزد دوبرابر دوباره امضا می‌کند، مثل {{< term "replace-by-fee" "replace-by-fee" >}} در [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/):

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/exchange -pgdir <tmp>/pg send
withdrawal #7 signed: nonce 1, tx 0x919ab50e
withdrawal #7 sent: 0x919ab50e
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #7: no receipt for 1 attempt(s) at nonce 1
$ go run ./cmd/exchange -pgdir <tmp>/pg bump -id 7
withdrawal #7: replaced 0x919ab50e with 0xd822743e, nonce 1, tip 1 -> 2 gwei
$ cast rpc txpool_status
{"pending":"0x1","queued":"0x0"}
$ cast rpc anvil_mine 1
$ cast rpc evm_setAutomine true
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #7: confirmed via 0xd822743e (3/3)
$ cast nonce $HOT
2
(withdraw command and one track call trimmed)
```

`track` همه‌ی تلاش‌های ذخیره‌شده را بررسی می‌کند؛ هر کدام ممکن است mine شود.

## داغ، سرد و sweep

این بخش کد ندارد. {{< term "sweeping" "sweep" >}} واریزها را از آدرس‌های زیاد به کیف‌پول‌های صرافی جمع می‌کند؛ برای ERC-20 هر آدرس واریز اول ETH برای gas لازم دارد. کیف‌پول داغ فقط پولِ برداشت‌های نزدیک را دارد؛ بقیه در {{< term "cold-wallet" "کیف‌پول سرد" >}} می‌ماند و با انتقال‌های تأییدشده‌ی دستی کیف‌پول داغ را شارژ می‌کند. [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) نشان می‌دهد چرا هر چیزی که از کیف‌پول داغ امضا می‌خواهد به اندازه‌ی کلیدش مهم است.

## چند نکته‌ی مهم

- فقط در N به حساب بگذارید و برای reorg عمیق‌تر از N هشدار داشته باشید؛ پولِ به حساب رفته را خودکار برنگردانید.
- nonceهای یک کیف‌پول داغ مال یک پروسه است. یک `cast send` دستی با همان کلید شمارنده را خراب می‌کند.
- تراکنش امضاشده را پیش از ارسال ذخیره کنید؛ تلاش دوباره همان را می‌فرستد، نه امضای تازه.
- جمع کل دفتر باید صفر باشد؛ با موجودی روی زنجیره هم تطبیقش دهید.

## تمرین

۱. یک فرمان تطبیق اضافه کنید: موجودی کیف‌پول داغ و آدرس‌های واریز روی زنجیره در برابر `user:*` به‌علاوه‌ی `withdrawals:pending`.
۲. مسیر شکست را اجرا کنید: برداشتی را روی زنجیره revert کنید و آزادشدن مبلغ رزروشده را نشان دهید.
۳. برای واریزهای بزرگ N بزرگ‌تری بگذارید.

## قدم بعدی

پست بعد: **پروژه‌ی پایانی بلاکچین با Go و Rust**.
