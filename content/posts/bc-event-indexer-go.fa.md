+++
date = '2026-11-20T18:00:00+03:30'
draft = false
title = 'Event و ساخت indexer با Go و Postgres'
description = 'ساخت indexer رویداد با Go و Postgres: topic و data، bloom در header، eth_getLogs دسته‌ای، درج idempotent، تعداد confirmation و یک reorg واقعی روی anvil.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "indexer"]
cover = { image = "/images/covers/bc-event-indexer-go.fa.png", alt = "Event و ساخت indexer با Go و Postgres", hiddenInSingle = true }
+++

فرض کنید یک صرافی دارید و باید بدانید یک آدرس مشخص در تاریخچه‌اش چه انتقال‌هایی از توکن DEMO داشته است. نود اتریوم به «در بلاک ۵ چه اتفاقی افتاد» خوب جواب می‌دهد، ولی به «همه‌ی انتقال‌های DEMO این آدرس از اول تا حالا» بد. باید بلاک‌ها را یکی‌یکی بگردید. صرافی چیز دومی را لازم دارد، سریع و از دیتابیس خودش.

برنامه‌ای که این کار را می‌کند {{< term "indexer" "indexer" >}} نام دارد: رویدادهای زنجیره را می‌خواند و در دیتابیس خودمان کپی می‌کند، تا بعداً با یک SQL ساده بشود به هر سؤالی جواب داد. کار اول ساده به نظر می‌رسد، اما سه مشکل دارد که این مقاله حول آن‌ها می‌چرخد:

۱. چطور فقط بلاک‌هایی را بخوانیم که به کارمان می‌آیند؟
۲. اگر برنامه وسط کار بمیرد، چطور نه چیزی گم شود نه دوبار ثبت شود؟
۳. اگر زنجیره چند بلاک آخرش را عوض کند، چه کنیم؟

بعد از [مقاله‌ی alloy](/fa/posts/bc-rust-alloy-client/) دوباره به Go برگشتم، ماژول [مقاله‌ی go-ethereum](/fa/posts/bc-go-ethereum-client/) را همراه کد abigen کپی کردم و indexer را روی آن ساختم. تکه‌ها از مقاله‌های قبل می‌آیند: Postgres از [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/)، bloom از [Bloom filter و consistent hashing](/fa/posts/algo-bloom-filter-consistent-hashing/) و reorg از [Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر](/fa/posts/bc-forks-reorgs/).

> اجرا با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10، pgx v5.11.0 و PostgreSQL 18.3 از ماژول `embedded-postgres` روی یک پورت آزاد loopback. یک anvil تازه روی `127.0.0.1:8545` با اسکریپت deploy مقاله‌ی توکن‌ها؛ آدرس‌ها حساب‌های آزمایشی عمومی anvil هستند. مسیرهای موقت `<tmp>` نوشته شده‌اند.

## یک رویداد از چه تکه‌هایی ساخته شده

اول ببینیم چه چیزی را می‌خواهیم بخوانیم. وقتی قرارداد یک {{< term "event-log" "رویداد" >}} را emit می‌کند، نتیجه یک log در رسید تراکنش است. هر log دو نوع جا برای نگه‌داشتن اطلاعات دارد:

- **topic:** حداکثر چهار مقدار ۳۲ بایتی.
- **data:** بقیه‌ی اطلاعات، بدون محدودیت چهارتایی.

برای رویداد `Transfer(address indexed from, address indexed to, uint256 value)` چیدمان این‌طور است. topic شماره‌ی صفر، hash امضای رویداد است (همان `0xddf252ad...`) و نشان می‌دهد این log از کدام نوع رویداد است. topic‌های ۱ و ۲ همان `from` و `to` هستند که تا ۳۲ بایت صفر پشتشان گذاشته‌اند (padding). `value` که indexed نیست در data می‌نشیند.

این تفاوت عملاً مهم است: نود می‌تواند روی پارامترهای indexed فیلتر کند («فقط انتقال‌هایی که گیرنده‌شان فلان آدرس است»)، ولی روی data نه.

## چطور از بلاک‌های بی‌ربط رد شویم: bloom

هر header بلاک یک فیلد `logsBloom` دارد، به اندازه‌ی ۲۰۴۸ بیت. این یک {{< term "bloom-filter" "Bloom filter" >}} است: خلاصه‌ی فشرده‌ای از آدرس‌ها و topicهای همه‌ی logهای آن بلاک. یک Bloom filter فقط دو جواب می‌دهد: «قطعاً این‌جا نیست» یا «شاید هست». «شاید» یعنی مثبت کاذب هم ممکن است، ولی «نیست» همیشه درست است. پس اگر bloom بگوید نیست، می‌شود بدون خواندن receiptهای بلاک از رویش رد شد.

برای دیدن این حرف، برنامه‌ی کوچکی نوشتم که برای هر بلاک می‌پرسد: آدرس توکن ما در bloom هست؟ topic مربوط به `Transfer` هست؟ (خروجی را در انتهای ماجرا، بعد از همه‌ی آزمایش‌های این مقاله گرفتم، پس هفت بلاک دارد.)

```
$ go run ./cmd/bloom
block 1: token in bloom true  Transfer in bloom true
block 2: token in bloom false Transfer in bloom false
block 3: token in bloom false Transfer in bloom true
block 4: token in bloom true  Transfer in bloom true
block 5: token in bloom true  Transfer in bloom true
block 6: token in bloom false Transfer in bloom false
block 7: token in bloom false Transfer in bloom false
```

- **بلاک ۱:** deploy توکن، که ۱٬۰۰۰٬۰۰۰ DEMO را به حساب ۰ mint کرد. هر دو `true` هستند.
- **بلاک ۲:** deploy قرارداد NFT. نه توکن ما، نه `Transfer`.
- **بلاک ۳:** mint کردن یک NFT. این بلاک topic `Transfer` را دارد، چون NFT هم رویدادی با همین امضا emit می‌کند، ولی آدرس آن توکن ما نیست. فیلتری که هر دو را بخواهد از روی این بلاک رد می‌شود.
- **بلاک‌های ۴ و ۵:** انتقال‌های DEMO.
- **بلاک‌های ۶ و ۷:** هیچ log ی ندارند (بعداً می‌بینیم چرا: بلاک‌هایی که برای آزمایش reorg ساختم).

یادتان باشد `true` هنوز می‌تواند مثبت کاذب باشد؛ فقط `false` قطعی است.

## جدول‌ها

حالا که می‌دانیم چه می‌خواهیم، جایی برای نگه‌داشتنش لازم است. سه جدول داریم:

```sql
CREATE TABLE blocks (number bigint PRIMARY KEY, hash text NOT NULL, parent_hash text NOT NULL);
CREATE TABLE transfers (
    block_number bigint NOT NULL, block_hash text NOT NULL,
    tx_hash text NOT NULL, log_index integer NOT NULL,
    from_addr text NOT NULL, to_addr text NOT NULL,
    value numeric(78, 0) NOT NULL, -- uint256 fits in 78 digits
    PRIMARY KEY (tx_hash, log_index)
);
CREATE TABLE cursor (id integer PRIMARY KEY CHECK (id = 1), last_block bigint NOT NULL);
-- IF NOT EXISTS and the cursor's first row (1, -1) trimmed
```

- **`blocks`:** hash هر بلاکی که پردازش کرده‌ایم. بعداً از روی آن می‌فهمیم زنجیره عوض شده یا نه.
- **`transfers`:** خود انتقال‌ها، با بلاکی که در آن بوده‌اند.
- **`cursor`:** یک ردیف فقط، مثل نشانه‌ی کتاب: آخرین بلاکی که کامل پردازش شده. مقدار اولیه‌اش `-1` است، یعنی هنوز هیچ بلاکی نه.

دو انتخاب در `transfers` دلیل دارد. `value` از نوع `NUMERIC` است، چون `bigint` حدود ۹٫۲ DEMO را سرریز می‌کند (توکن ۱۸ رقم اعشار دارد و عددها به واحد کوچک ذخیره می‌شوند). و کلید اصلی `(tx_hash, log_index)` است، چون این دو با هم یک log را در کل زنجیره یکتا مشخص می‌کنند. نتیجه‌اش این است که درج با `ON CONFLICT DO NOTHING` می‌شود، و اگر یک بازه را دوبار پردازش کنیم، دفعه‌ی دوم چیزی اضافه نمی‌شود. به چنین عملی که تکرارش بی‌ضرر است {{< term "idempotency" "idempotent" >}} می‌گویند، و جواب مشکل دوم ماست.

## پردازش یک دسته

indexer اول حساب می‌کند تا کدام بلاک امن است. می‌گوید `head - N`، که N تعداد {{< term "confirmation" "confirmation" >}} است: یعنی فقط بلاک‌هایی را بخوان که دست‌کم N بلاک روی آن‌ها ساخته شده، چون هرچه بلاک قدیمی‌تر باشد احتمال عوض شدنش کمتر است. بعد از cursor شروع می‌کند و در دسته‌های دوبلاکی جلو می‌رود. (اندازه‌ی دسته با فلگ `-batch` تعیین می‌شود و پیش‌فرضش ۲ است.)

```go
logs, err := ix.eth.FilterLogs(ctx, ethereum.FilterQuery{
	FromBlock: new(big.Int).SetUint64(from),
	ToBlock:   new(big.Int).SetUint64(to),
	Addresses: []common.Address{tokenAddr},
	Topics:    [][]common.Hash{{transferTopic}},
})
// in one DB transaction: the blocks' hashes, the transfers, the cursor
for _, l := range logs {
	if l.BlockHash != headers[l.BlockNumber].Hash() {
		return fmt.Errorf("block %d changed during the pass, rerun", l.BlockNumber)
	}
	ev, err := demo.UnpackTransferEvent(&l)
	// INSERT ... ON CONFLICT (tx_hash, log_index) DO NOTHING
}
```

`FilterLogs` از نود می‌خواهد فقط logهای این توکن را با topic `Transfer` در این بازه بدهد. بعد هر log را با header همان بلاک مقایسه می‌کنیم: اگر hash بلاک عوض شده باشد، یعنی وسط کار زنجیره تغییر کرده و همان‌جا خطا می‌دهیم. در آخر هر log را decode می‌کنیم و درج می‌کنیم.

نکته‌ی مهم این است که hash بلاک‌ها، ردیف‌های `transfers` و cursor همه در **یک تراکنش دیتابیس** commit می‌شوند. پس اگر برنامه وسط کار بمیرد، یا همه‌ی اینها ثبت شده یا هیچ‌کدام، و cursor هیچ‌وقت از داده‌اش جلوتر نمی‌رود. هر بازه‌ی جدید هم باید به بلاکی وصل باشد که آخر بار ذخیره کرده‌ایم: parent hash اولین بلاک بازه باید با hash ذخیره‌شده‌ی بلاک قبلی یکی باشد. این بررسی در اجراهای من فعال نشد.

## یک اجرا، اجرای دوباره، یک reorg

حالا هر سه مشکل را عملاً ببینیم. `$T` توکن است و `$A0` تا `$A4` حساب‌های آزمایشی ۰ تا ۴ anvil. حساب ۰ به حساب ۱ مقدار ۲۵۰ DEMO می‌فرستد (بلاک ۴). بعد یک snapshot از anvil می‌گیرم، یعنی وضعیت فعلی را ذخیره می‌کنم تا بعداً بتوانم برگردم. بعد دو انتقال دیگر (۱ به ۲ و ۲ به ۳) در بلاک‌های ۵ و ۶ می‌نشینند. اینجا هنوز از reorg خبری نیست؛ اول اجرای ساده:

```
$ cast send $T "transfer(address,uint256)" $A1 250ether --unlocked --from $A0   # block 4
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $A2 40ether --unlocked --from $A1  # block 5
$ cast send $T "transfer(address,uint256)" $A3 5ether --unlocked --from $A2   # block 6
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2
head 6, confirmations 2, safe 4, cursor -1
blocks 0-1: 1 logs, 1 new rows
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 1 new rows
```

خط اول: نوک زنجیره بلاک ۶ است و با دو confirmation فقط تا بلاک ۴ امن است. cursor هنوز `-1` است. سه خط بعد سه دسته‌اند: بلاک‌های ۰ تا ۱ یک log دارند (mint اولیه)، بلاک‌های ۲ و ۳ هیچ log ی از توکن ما ندارند، و بلاک ۴ یک log دارد (انتقال ۲۵۰ DEMO). بلاک‌های ۵ و ۶ هنوز دست نخورده‌اند، چون confirmation کافی ندارند.

حالا مشکل دوم: برنامه وسط کار می‌میرد. `-rewind 1` cursor را به بلاک ۱ برمی‌گرداند، انگار پروسه بعد از commit بلاک ۱ مرده است، و دوباره اجرا می‌کند:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2 -rewind 1
head 6, confirmations 2, safe 4, cursor 1
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 0 new rows
```

بلاک ۴ دوباره خوانده می‌شود، log پیدا می‌شود، ولی **۰ ردیف جدید** درج می‌شود: همان `ON CONFLICT DO NOTHING` کارش را کرد. بازه‌ی تکراری ضرری نزد.

حالا مشکل سوم، reorg. اول با `-confirmations 0` نوک زنجیره را دنبال می‌کنم تا بلاک‌های ۵ و ۶ هم در دیتابیس بنشینند. بعد anvil را به snapshot برمی‌گردانم (`evm_revert`)، که یعنی بلاک‌های ۵ و ۶ از بین می‌روند. یک انتقال متفاوت (۱ به ۴، مقدار ۷ DEMO) می‌فرستم، که بلاک ۵ جدید و متفاوتی می‌سازد، و دو بلاک خالی هم اضافه می‌کنم:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
head 6, confirmations 0, safe 6, cursor 4
blocks 5-6: 2 logs, 2 new rows
$ cast rpc evm_revert 0x0
true
$ cast send $T "transfer(address,uint256)" $A4 7ether --unlocked --from $A1   # new block 5
$ cast rpc anvil_mine 2
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
reorg: block 6 stored 0xa6ef000b, chain 0xc63678e1
reorg: block 5 stored 0x68dd3f4a, chain 0x60f21742
reorg: fork point 4, deleted 2 transfers above it
head 7, confirmations 0, safe 7, cursor 4
blocks 5-6: 1 logs, 1 new rows
blocks 7-7: 0 logs, 0 new rows
```

(خروجی `cast send` و `anvil_mine` را حذف کرده‌ام. hashهای بلاک در هر اجرا فرق می‌کنند، پس عددهای شما چیز دیگری خواهند بود.)

anvil خودش fork نمی‌شود. snapshot و revert فقط راهی محلی است تا زنجیره دو بلاک را عوض کند. روشی که indexer استفاده می‌کند ساده است: در شروع، hash ذخیره‌شده‌ی بلاک cursor را با hash همان بلاک در زنجیره مقایسه می‌کند. اگر فرق داشت، یک بلاک عقب می‌رود و دوباره مقایسه می‌کند، تا بلاکی برسد که هر دو بر سرش توافق دارند. این **نقطه‌ی fork** است. بعد همه‌چیز بالای آن را در یک تراکنش پاک می‌کند و از آن‌جا دوباره index می‌کند. در خروجی بالا:

- دو خط `reorg: block ...`: بلاک‌های ۶ و ۵ در دیتابیس با زنجیره فرق دارند.
- `fork point 4, deleted 2 transfers`: بلاک ۴ هنوز یکی است. دو انتقال قدیمی (۴۰ و ۵ DEMO) که روی شاخه‌ی کنارگذاشته بودند پاک شدند.
- بعد دوباره index می‌کند: بلاک‌های ۵ و ۶ یک log دارند (انتقال ۷ DEMO) و بلاک ۷ هیچ.

این همان قطع و وصل [مقاله‌ی forkها](/fa/posts/bc-forks-reorgs/) است. با `-confirmations 2` اجرای اول در بلاک ۴ ایستاده بود، پس این reorg دوبلاکی اصلاً به داده‌ی ذخیره‌شده دست نمی‌زد. confirmation دقیقاً برای همین است.

## مقایسه‌ی SQL با خود قرارداد

آیا واقعاً درست کار کرده؟ راه امتحانش این است که موجودی هر آدرس را از دو راه حساب کنیم: یکی با SQL از روی انتقال‌هایی که ذخیره کرده‌ایم، و یکی با پرسیدن `balanceOf` از خود قرارداد. SQL هر انتقال را یک بار برای گیرنده با علامت مثبت و یک بار برای فرستنده با علامت منفی می‌شمارد:

```sql
WITH moves AS (
    SELECT to_addr AS addr, value FROM transfers
    UNION ALL
    SELECT from_addr, -value FROM transfers
)
SELECT addr, sum(value)::text FROM moves
WHERE addr <> '0x0000000000000000000000000000000000000000'
GROUP BY addr ORDER BY addr;
```

(آدرس صفر را کنار گذاشته‌ایم، چون mint از آن‌جا می‌آید و موجودی واقعی ندارد.)

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -balances
0x15d34AAf… sql 7000000000000000000       balanceOf 7000000000000000000       match
0x70997970… sql 243000000000000000000     balanceOf 243000000000000000000     match
0xf39Fd6e5… sql 999750000000000000000000  balanceOf 999750000000000000000000  match
```

هر سه آدرس دقیقاً یکی‌اند. حساب ۴ هفت DEMO دارد، حساب ۱ برابر ۲۵۰ − ۷ = ۲۴۳ و حساب ۰ برابر ۱٬۰۰۰٬۰۰۰ − ۲۵۰ = ۹۹۹٬۷۵۰. حساب‌های ۲ و ۳ در هیچ‌کدام از دو طرف نیستند: DEMOشان فقط روی شاخه‌ی کنارگذاشته وجود داشت، و reorg آن را هم از دیتابیس پاک کرد و هم از زنجیره.

## جاهایی که indexer خطا می‌کند

- **`eth_getLogs` با شماره‌ی بلاک ممکن است با reorg مسابقه بدهد.** بین اینکه header را می‌گیرید و logها را، زنجیره می‌تواند عوض شود. hash بلاک هر log را با headerی که ذخیره کرده‌اید مقایسه کنید، همان کاری که در کد بالا کردیم.
- **تا جایی که می‌دانم سرویس‌دهنده‌های RPC بازه‌ی بلاک یا تعداد نتیجه‌ی `eth_getLogs` را محدود می‌کنند، هر کدام به شکلی.** دسته‌ای بخوانید و با دیدن خطا دسته را کوچک کنید.
- **confirmation کار reorg را کم می‌کند، حذفش نمی‌کند.** مسیر rollback را نگه دارید و تستش کنید.
- **مقدار را `NUMERIC` یا متن ذخیره کنید، هرگز `float`.** عددهای ۲۵۶ بیتی در `float64` جا نمی‌شوند.

## تمرین

۱. یک جدول `approvals` برای رویداد `Approval` اضافه کنید و هر دو رویداد را با یک فراخوانی `FilterLogs` index کنید.
۲. سه بلاک reorg کنید و با `-confirmations 2` اجرا کنید. چه چیزی عوض می‌شود؟
۳. پروسه را بین `FilterLogs` و `COMMIT` بکشید. اجرای بعدی از چه وضعیتی شروع می‌کند؟

## قدم بعدی

مقاله‌ی بعد «کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust» است: این indexer آدرس‌ها را می‌پاید، و آن مقاله نشان می‌دهد خود آدرس‌ها از کجا می‌آیند.
