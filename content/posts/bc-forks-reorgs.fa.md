+++
date = '2027-06-21T10:00:00+03:30'
draft = false
title = 'Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر'
description = 'fork و reorg در Go: درخت بلاک، انتخاب زنجیره با chainwork، برگرداندن UTXO با داده‌ی undo و یک double spend بعد از partition شبکه روی loopback.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "reorg", "fork-choice", "bitcoin"]
cover = { image = "/images/covers/bc-forks-reorgs.fa.png", alt = "Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/bc-p2p-gossip/) نودها بلاک gossip می‌کردند، ولی بلاک رقیب tip فقط لاگ می‌شد. دو ماینر ممکن است در یک ارتفاع بلاک پیدا کنند، و یک {{< term "network-partition" "partition شبکه" >}} می‌تواند بگذارد دو گروه مدتی تاریخچه‌ی جدا بسازند. به زبان [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/)، proof of work دسترس‌پذیری را انتخاب می‌کند: هر دو طرف بلاک می‌سازند و تاریخچه‌ی طرف بازنده بعداً برگردانده می‌شود.

در [Proof of Work، difficulty و mining](/fa/posts/bc-proof-of-work-mining/) هر بلاک فیلد `Bits` گرفت و زنجیره جمع کار را نگه داشت؛ حالا همین جمع شاخه‌ی برنده را تعیین می‌کند.

ماژول پست قبل را کپی کردم؛ `Chain` حالا یک درخت است.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است و فقط روی loopback. کلیدها از کلمه‌هایی مثل "alice" ساخته شده‌اند: عمومی‌اند و فقط برای دمو.

## درخت، نه فهرست

```go
type node struct {
	block   Block
	parent  *node
	work    *big.Int // chainwork: sum of Work(bits) from genesis to here
	undo    Undo     // set while the block is on the active chain
	invalid bool     // failed full validation when we tried to connect it
}

type Chain struct {
	params Params
	index  map[Hash]*node
	active []*node // active[h] is the active block at height h
	utxo   UTXOSet
}
```

`AddBlock` header هر بلاک را با والد خودش چک می‌کند: اتصال، timestamp، `Bits` همان شاخه، proof of work و Merkle root. بعد {{< term "chainwork" "chainwork" >}} را مقایسه می‌کند. کمتر یا مساوی: بلاک در شاخه‌ی فرعی ذخیره می‌شود و تراکنش‌هایش فعلاً چک نمی‌شوند؛ در تساوی، اولین بلاک دیده‌شده می‌ماند. بیشتر: شاخه فعال می‌شود.

این همان {{< term "fork-choice-rule" "قاعده‌ی fork choice" >}} است: بیشترین کار، نه بیشترین بلاک.

## بلندتر یعنی سنگین‌تر نیست

`go run ./cmd/toychain forkchoice` هر دو شاخه را در یک پروسه می‌سازد. چهار بلاک مشترک، بعد شاخه‌ی b با timestampهای کند و شاخه‌ی a با timestampهای تند. در ارتفاع ۸، retarget سختی b را پایین و سختی a را بالا می‌برد:

```
common    4 bits 10: extended    tip  4, tip work  5120
branch b  5 bits 10: extended    tip  5, tip work  6144
...
branch b  7 bits 10: extended    tip  7, tip work  8192
branch b  8 bits  8: extended    tip  8, tip work  8448
...
branch b 13 bits  8: extended    tip 13, tip work  9728
branch a  5 bits 10: side branch tip 13, tip work  9728
branch a  6 bits 10: side branch tip 13, tip work  9728
branch a  7 bits 10: side branch tip 13, tip work  9728
branch a  8 bits 12: reorg       tip  8, tip work 12288, disconnected 9, connected 4
branch a  9 bits 12: extended    tip  9, tip work 16384
b: height 13, work 9728; a: height 9, work 16384
known blocks: 19 active: 10 validate: <nil>
```

بلاک ۸ شاخه‌ی a ۴۰۹۶ کار دارد، برابر ۱۶ بلاک b، و tip از ارتفاع ۱۳ به ۸ رفت. اگر بلاک‌ها را می‌شمردیم، بلاک‌های ارزان با timestamp جعلی برنده می‌شدند.

## Reorg

یک {{< term "chain-reorganization" "reorg" >}} سه مرحله دارد: پیدا کردن جد مشترک، جدا کردن بلاک‌های قدیمی از tip به پایین، و وصل کردن بلاک‌های تازه به بالا.

جدا کردن به state قبلی UTXO نیاز دارد. replay از genesis ساده است ولی هر بار کل زنجیره خرج دارد، پس هر بلاک وصل‌شده داده‌ی undo نگه می‌دارد: خروجی‌هایی که خرج کرده.

```go
func (u UTXOSet) DisconnectBlock(txs []Tx, undo Undo) UTXOSet {
	prev := maps.Clone(u)
	for _, tx := range txs {
		id := tx.ID()
		for i := range tx.Outputs {
			delete(prev, OutPoint{TxID: id, Index: uint32(i)})
		}
	}
	for _, s := range undo {
		prev[s.OutPoint] = s.Out
	}
	return prev
}
```

تا جایی که می‌دانم Bitcoin Core هم داده‌ی undo را کنار فایل‌های بلاک نگه می‌دارد. اگر تراکنش‌های یک بلاک از شاخه‌ی تازه رد شوند، آن بلاک و فرزندانش نامعتبر علامت می‌خورند، شاخه‌ی قدیمی برمی‌گردد و نود peer فرستنده را قطع می‌کند. یک تست چک می‌کند که مجموعه‌ی UTXO بعد از دو reorg با replay از genesis برابر است.

تراکنش‌های غیر coinbase بلاک‌های جداشده که در شاخه‌ی تازه نیستند در `Result.Unconfirmed` برمی‌گردند. نود آن‌هایی را که هنوز معتبرند دوباره به pending اضافه می‌کند.

## یک partition روی loopback

`go run ./cmd/toychain partition`: چهار نود در یک خط بلاک ۱ را با هم دارند، بعد به {A,B} و {C,D} تقسیم می‌شوند. Alice در یک طرف ۳۰ سکه به Bob می‌دهد و در طرف دیگر همان سکه را به Mallory، یعنی یک {{< term "double-spend" "double spend" >}}. ماینر هم در طرف A/B ده سکه به Bob می‌دهد. A یک بلاک ماین می‌کند و D دو بلاک:

```
toBob ef4d0ece5dfd, minerToBob ae9aaa78f115, toMallory 2864f55b62ad
[A] mined block 2 0000b06c35d8 (bits 12, 6607 hashes, 3 txs), sent to 1 peers
[D] mined block 2 00039be25c01 (bits 12, 5012 hashes, 2 txs), sent to 1 peers
[D] mined block 3 000f3bde1876 (bits 12, 858 hashes, 1 txs), sent to 1 peers
B sees bob 40, pending 0
== heal: B connects to C
[B] connected to C (its height 3 work 16384, mine 2 work 12288)
[C] getblocks by B: fork point 1, sent 2 blocks
[B] block 2 00039be25c01 from C: side branch (work 12288, mine 12288)
[B] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
[B]   tx ae9aaa78f115 from the old branch back to pending
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B] block 3 000f3bde1876 from C: reorg, 1 txs, relayed to 1
[A] block 3 000f3bde1876 from B: parent unknown, sending locator
[B] getblocks by A: fork point 1, sent 2 blocks
[A] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
...
A: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
B: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
C: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
D: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
```

قبل از اتصال دوباره، Bob با یک confirmation چهل سکه داشت. بعدش پرداخت ماینر دوباره pending است و پرداخت Alice برای همیشه رفته، چون سکه‌اش به Mallory رسید. برای پیدا کردن نقطه‌ی fork، نود یک block locator می‌فرستد: ۱۰ hash آخر و بعد hashهایی با فاصله‌ی دو برابرشونده. بلاک ۲ نود A حالا یک {{< term "stale-block" "stale block" >}} است و coinbase آن هم از بین رفت. تا جایی که می‌دانم به همین دلیل بیت‌کوین خروجی coinbase را تا ۱۰۰ بلاک قابل خرج نمی‌داند.

## چرا صرافی‌ها صبر می‌کنند

در proof of work هیچ بلاکی قطعی نیست؛ فقط با انباشته شدن کار روی آن، جایگزین کردنش سخت‌تر می‌شود. این {{< term "probabilistic-finality" "finality احتمالی" >}} است. whitepaper بیت‌کوین نشان می‌دهد مهاجمی با کمتر از نصف توان hash به‌طور نمایی عقب می‌افتد، پس هر {{< term "confirmation" "confirmation" >}} ریسک را کم می‌کند. شش confirmation یک قرارداد رایج برای بیت‌کوین است؛ صرافی‌ها عدد خودشان را برای هر زنجیره و مبلغ تعیین می‌کنند. Bob دید چرا یکی کافی نیست.

## چند نکته‌ی مهم

- با chainwork انتخاب کنید، هرگز با ارتفاع.
- header شاخه‌ی فرعی را فوراً چک کنید و تراکنش‌هایش را هنگام فعال شدن؛ شکست‌ها را علامت بزنید تا فرزندانشان رد شوند.
- بدون داده‌ی undo هر reorg یک replay کامل است.
- تراکنش‌هایی را که reorg برمی‌گرداند دوباره چک کنید: بعضی double spend شده‌اند.

## تمرین

۱. تراکنش‌های برگشته به pending را دوباره broadcast کنید تا C و D هم پرداخت ماینر را ببینند.
۲. یک متد `Confirmations(txid)` و یک قاعده‌ی کیف‌پول اضافه کنید که منتظر ۳ تا بماند.
۳. شاخه‌های فرعی‌ای را که بیش از ۱۰۰ بلاک پایین‌تر از tip هستند حذف کنید.

## قدم بعدی

پست بعد: **Mempool، کارمزد و انتخاب تراکنش**. مجموعه‌ی pending ما یک mempool واقعی می‌شود.
