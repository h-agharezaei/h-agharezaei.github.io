+++
date = '2026-11-20T18:00:00+03:30'
draft = false
title = 'Event و ساخت indexer با Go و Postgres'
description = 'ساخت indexer رویداد با Go و Postgres: topic و data، bloom در header، eth_getLogs دسته‌ای، درج idempotent، تعداد confirmation و یک reorg واقعی روی anvil.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "indexer"]
cover = { image = "/images/covers/bc-event-indexer-go.fa.png", alt = "Event و ساخت indexer با Go و Postgres", hiddenInSingle = true }
+++

در [کار با اتریوم از Rust با alloy](/fa/posts/bc-rust-alloy-client/) کلاینت Rust بود. این پست به Go برمی‌گردد: ماژول [کار با اتریوم از Go با go-ethereum](/fa/posts/bc-go-ethereum-client/) را همراه کد ساخته‌شده با abigen کپی کردم و یک {{< term "indexer" "indexer" >}} ساختم.

نود به «در بلاک ۵ چه هست» خوب جواب می‌دهد و به «همه‌ی انتقال‌های DEMO این آدرس» بد؛ صرافی دومی را لازم دارد، سریع و از دیتابیس خودش. تکه‌ها از پست‌های قبل می‌آیند: Postgres از [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/)، bloom از [Bloom filter و consistent hashing](/fa/posts/algo-bloom-filter-consistent-hashing/) و reorg از [Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر](/fa/posts/bc-forks-reorgs/).

> اجرا با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10، pgx v5.11.0 و PostgreSQL 18.3 از ماژول `embedded-postgres` روی یک پورت آزاد loopback. یک anvil تازه روی `127.0.0.1:8545` با اسکریپت دیپلوی پست توکن‌ها؛ آدرس‌ها حساب‌های تست عمومی anvil هستند. مسیرهای موقت `<tmp>` نوشته شده‌اند.

## topic و data

هر {{< term "event-log" "log رویداد" >}} حداکثر چهار topic و یک data دارد. برای `Transfer(address indexed from, address indexed to, uint256 value)` topic صفر hash امضا یعنی `0xddf252ad...` است، topicهای ۱ و ۲ همان `from` و `to` با padding تا ۳۲ بایت، و `value` در data می‌نشیند. نود روی پارامترهای indexed می‌تواند فیلتر کند، روی data نه.

هر header بلاک هم یک `logsBloom` دوهزار و چهل و هشت بیتی دارد، یک {{< term "bloom-filter" "Bloom filter" >}} از آدرس‌ها و topicهای logهایش. یک برنامه‌ی کوچک از آن درباره‌ی هر بلاک می‌پرسد (اجراشده در انتهای همین پست):

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

بلاک ۳ همان mint کردن NFT است: topic `Transfer` را دارد، ولی نه از توکن ما. فیلتری که هر دو را می‌خواهد می‌تواند بدون خواندن receiptها از رویش رد شود. «true» هنوز می‌تواند مثبت کاذب باشد.

## schema

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

`value` از نوع `NUMERIC` است: `bigint` حدود ۹.۲ DEMO سرریز می‌کند. `(tx_hash, log_index)` یک log را مشخص می‌کند، پس درج با `ON CONFLICT DO NOTHING` است و اجرای دوباره‌ی یک بازه {{< term "idempotency" "idempotent" >}} است.

## یک دسته

indexer اول `head - N` را حساب می‌کند (N تعداد {{< term "confirmation" "confirmation" >}}) و بعد از cursor در دسته‌های دوبلاکی جلو می‌رود:

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

بلاک‌ها، ردیف‌ها و cursor با هم commit می‌شوند، پس crash هیچ‌وقت cursor را جلوتر از داده‌اش جا نمی‌گذارد. هر بازه‌ی جدید هم باید از بلاکی شروع شود که parent hash آن با hash ذخیره‌شده‌ی بلاک قبلی یکی است؛ این بررسی در اجراهای من فعال نشد.

## یک اجرا، اجرای دوباره، یک reorg

`$T` و `$A0` تا `$A4` توکن و حساب‌های تست ۰ تا ۴ anvil هستند. حساب ۰ به حساب ۱ مقدار ۲۵۰ DEMO می‌فرستد (بلاک ۴)، یک snapshot می‌گیرم، بعد انتقال ۱ به ۲ و ۲ به ۳ در بلاک‌های ۵ و ۶ می‌نشینند:

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
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2 -rewind 1
head 6, confirmations 2, safe 4, cursor 1
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 0 new rows
(cast send output trimmed)
```

`-rewind` طوری cursor را عقب می‌برد که انگار پروسه بعد از commit مرده. log دوباره خوانده می‌شود و صفر بار درج می‌شود. برای دیدن یک {{< term "chain-reorganization" "reorg" >}}، با `-confirmations 0` نوک زنجیره را دنبال می‌کنم، بعد anvil را به snapshot برمی‌گردانم و یک بلاک ۵ متفاوت می‌سازم:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
head 6, confirmations 0, safe 6, cursor 4
blocks 5-6: 2 logs, 2 new rows
$ cast rpc evm_revert 0x0
true
$ cast send $T "transfer(address,uint256)" $A4 7ether --unlocked --from $A1   # new block 5
$ cast rpc anvil_mine 2
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
reorg: block 6 stored 0x2b083812, chain 0x2eeeb0c3
reorg: block 5 stored 0xfb574c72, chain 0x92e64fc2
reorg: fork point 4, deleted 2 transfers above it
head 7, confirmations 0, safe 7, cursor 4
blocks 5-6: 1 logs, 1 new rows
blocks 7-7: 0 logs, 0 new rows
(cast output trimmed)
```

anvil خودش fork نمی‌شود؛ snapshot و revert راهی محلی است که زنجیره دو بلاک را عوض کند. indexer در شروع hash ذخیره‌شده‌ی بلاک cursor را با hash زنجیره مقایسه می‌کند، تا جایی که یکی شوند عقب می‌رود، همه‌چیزِ بالای آن بلاک را در یک تراکنش پاک می‌کند و دوباره index می‌کند؛ همان قطع و وصل پست forkها. با `-confirmations 2` اجرای اول در بلاک ۴ ایستاده بود، پس این reorg دوبلاکی به داده دست نمی‌زد.

## SQL در برابر قرارداد

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

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -balances
0x15d34AAf… sql 7000000000000000000       balanceOf 7000000000000000000       match
0x70997970… sql 243000000000000000000     balanceOf 243000000000000000000     match
0xf39Fd6e5… sql 999750000000000000000000  balanceOf 999750000000000000000000  match
```

حساب‌های ۲ و ۳ از هر دو طرف حذف شده‌اند: DEMOشان فقط روی شاخه‌ی کنارگذاشته وجود داشت.

## چند نکته‌ی مهم

- `eth_getLogs` با شماره‌ی بلاک ممکن است با reorg مسابقه بدهد؛ hash بلاک هر log را با headerی که ذخیره کرده‌اید مقایسه کنید.
- تا جایی که می‌دانم سرویس‌دهنده‌های RPC بازه‌ی بلاک یا تعداد نتیجه‌ی `eth_getLogs` را محدود می‌کنند، هر کدام به شکلی؛ دسته‌ای بخوانید و با خطا دسته را کوچک کنید.
- confirmation کار reorg را کم می‌کند، حذفش نمی‌کند. مسیر rollback را نگه دارید و تستش کنید.
- مقدار را `NUMERIC` یا متن ذخیره کنید، هرگز `float`.

## تمرین

۱. یک جدول `approvals` برای رویداد `Approval` اضافه کنید و هر دو رویداد را با یک فراخوانی `FilterLogs` index کنید.
۲. سه بلاک reorg کنید و با `-confirmations 2` اجرا کنید. چه چیزی عوض می‌شود؟
۳. پروسه را بین `FilterLogs` و `COMMIT` بکشید. اجرای بعدی از چه وضعیتی شروع می‌کند؟

## قدم بعدی

پست بعد: **کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust**.
