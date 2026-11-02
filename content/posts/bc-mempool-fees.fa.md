+++
date = '2026-11-11T18:00:00+03:30'
draft = false
title = 'Mempool، کارمزد و انتخاب تراکنش'
description = 'mempool در Go: پذیرش تراکنش با نرخ کارمزد، ساخت block template با بسته‌ی اجداد، replace-by-fee، بیرون کردن تراکنش ارزان و broadcast دوباره بعد از reorg.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "mempool", "fees", "bitcoin"]
cover = { image = "/images/covers/bc-mempool-fees.fa.png", alt = "Mempool، کارمزد و انتخاب تراکنش", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/bc-forks-reorgs/) یک reorg تراکنشی را به `pending` برگرداند، ولی کسی آن را دوباره broadcast نکرد. به‌علاوه کارمزد صفر قبول می‌شد، بلاک همه‌چیز را برمی‌داشت، map سقف نداشت و خرج خروجی تأییدنشده رد می‌شد.

کارمزد همان ورودی منهای خروجی است، مثل [تراکنش و مدل UTXO](/fa/posts/bc-transactions-utxo/)، و ماینر آن را در coinbase برمی‌دارد ([Proof of Work، difficulty و mining](/fa/posts/bc-proof-of-work-mining/)). ماژول پست قبل را کپی کردم و map را با پکیج {{< term "mempool" "mempool" >}} عوض کردم.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است و فقط روی loopback. کلیدها از کلمه‌هایی مثل "alice" ساخته شده‌اند: عمومی‌اند و فقط برای دمو.

## کارمزد به ازای بایت، نه کارمزد

جای بلاک محدود است؛ مال من خیلی کوچک است (`MaxBlockBytes = 1000` با coinbase). ماینر بایت می‌فروشد، پس {{< term "fee-rate" "نرخ کارمزد" >}} را مقایسه می‌کند: کارمزد تقسیم بر اندازه. یک تراکنش با یک ورودی و یک خروجی این‌جا ۲۰۵ بایت است، پس کارمزد ۱ سکه یعنی ۴٫۹ سکه به ازای هر کیلوبایت.

```go
type Rate struct {
	Fee  uint64
	Size int
}

func (r Rate) Less(o Rate) bool { return r.Fee*uint64(o.Size) < o.Fee*uint64(r.Size) }
```

ضرب متقاطع float لازم ندارد. `Add` تراکنش را با UTXOهای نوک زنجیره و خروجی‌های بقیه‌ی mempool چک می‌کند و بعد سیاست را اعمال می‌کند: حداقل ۱ سکه در کیلوبایت، سقف بایت و قاعده‌های تداخل. این سیاست محلی است، نه consensus.

## والد، فرزند و بسته

فرزند می‌تواند خروجی یک والد تأییدنشده را خرج کند. می‌شد شرط گذاشت که اول والد انتخاب شود و هر تراکنش با نرخ خودش سنجیده شود، ولی آن‌وقت والد ارزان منتظر می‌ماند حتی با فرزند پرکارمزد. پس هر تراکنش را همراه اجداد انتخاب‌نشده‌اش می‌سنجم، و این یعنی {{< term "child-pays-for-parent" "child pays for parent" >}} کار می‌کند. هسته‌ی `Template`:

```go
for id, e := range p.txs {
	if chosen[id] {
		continue
	}
	set := map[chain.Hash]bool{}
	for a := range p.ancestorsOf(map[chain.Hash]bool{id: true}) {
		if !chosen[a] {
			set[a] = true
		}
	}
	var pkg Rate
	for a := range set {
		pkg.Fee += p.txs[a].Fee
		pkg.Size += p.txs[a].Size
	}
	if size+pkg.Size > maxBytes {
		continue
	}
	if best == nil || bestPkg.Less(pkg) || (!pkg.Less(bestPkg) && e.seq < best.seq) {
		best, bestPkg, bestSet = e, pkg, set
	}
}
```

بهترین مجموعه با والد اول اضافه می‌شود و حلقه تکرار می‌شود. بیشترین کارمزد زیر یک سقف اندازه یک مسئله‌ی {{< term "knapsack" "knapsack" >}} است؛ این همان تقریب {{< term "greedy-algorithm" "greedy" >}} از [greedy و backtracking](/fa/posts/algo-greedy-backtracking/) است. تا جایی که می‌دانم Bitcoin Core هم مدت‌هاست {{< term "block-template" "block template" >}} را با نرخ کارمزد بسته‌ی اجداد می‌سازد.

## یک اجرا

`go run ./cmd/toychain mempool`: genesis پنجاه سکه را بین هفت نفر پخش می‌کند که به یک فروشگاه پول می‌دهند؛ erin به کلید دومش پول می‌دهد (`parent`) و آن کلید به فروشگاه (`child`). سقف mempool ۱۳۰۰ بایت است:

```
== admission (min 1.0/kB, pool max 1300 B)
alice    fee 1, 205 B, 4.9/kB  ok
bob      fee 3, 205 B, 14.6/kB ok
carol    fee 2, 205 B, 9.8/kB  ok
dave-0   rejected: fee rate below the minimum: 0.0/kB < 1.0/kB
dave     fee 1, 205 B, 4.9/kB  ok
parent   fee 1, 205 B, 4.9/kB  ok
child    fee 4, 205 B, 19.5/kB ok
== template, max 1000 B incl. 76 B coinbase
1. bob     own 14.6/kB package 14.6/kB
2. parent  own 4.9/kB  package 12.2/kB
3. child   own 19.5/kB package 12.2/kB
4. carol   own 9.8/kB  package 9.8/kB
4 txs, 896 B, fees 10; left out: alice dave
```

`parent` به‌تنهایی آخر می‌ماند؛ با فرزندش از carol جلو می‌زند. یک تراکنش دیگر اندازه را به ۱۱۰۱ بایت می‌رساند.

## Replace-by-fee

دو تراکنش که یک خروجی را خرج کنند با هم تداخل دارند. با {{< term "replace-by-fee" "replace-by-fee" >}} تراکنش تازه می‌تواند جای قبلی را بگیرد. قاعده‌ی من: نرخ کارمزد بالاتر از هر تراکنشی که با آن تداخل دارد، و کارمزد مطلق بیشتر از همه‌ی چیزهایی که بیرون می‌روند، فرزندان هم حساب. وگرنه erin می‌توانست والد و فرزند (۵ سکه) را با تراکنشی ۲ سکه‌ای عوض کند:

```
== replace-by-fee
alice-2  fee 2, 205 B, 9.8/kB  ok, replaced alice
alice-2b rejected: replacement must pay a higher fee rate than each tx it conflicts with: 9.8/kB <= 9.8/kB
erin-2   rejected: replacement must pay more fee than everything it replaces: 2 <= 5
```

BIP-125 قاعده‌های بیشتری دارد: پرداخت هزینه‌ی relay خود جایگزین، نداشتن ورودی تأییدنشده‌ی تازه، حداکثر ۱۰۰ تراکنش حذف‌شده، و سیگنال opt-in که تا جایی که می‌دانم Bitcoin Core جدید دیگر لازمش ندارد. هیچ‌کدام را پیاده نکردم. پس پرداخت تأییدنشده فقط یک قول است: یک {{< term "double-spend" "double spend" >}} با کارمزد بیشتر برنده می‌شود.

## mempool پر

بدون سقف، هر کسی می‌تواند حافظه‌ی نود را با تراکنش ارزان پر کند، یعنی {{< term "denial-of-service" "denial of service" >}}. وقتی mempool پر است، تراکنش با کمترین امتیاز همراه فرزندانش بیرون می‌رود. امتیاز بیشینه‌ی نرخ خودش و نرخ همراه فرزندان است، تا والد ارزان با فرزند پرکارمزد در امان بماند. تازه‌وارد باید از چیزی که بیرون می‌کند بهتر باشد:

```
== full pool: 1230 B used
grace    fee 4, 205 B, 19.5/kB ok, evicted dave (4.9/kB)
heidi    rejected: mempool full: 4.9/kB does not beat the lowest score 9.8/kB
== mine a block from the template
block 1: 5 txs, fees 12; mempool: 4 removed, 0 dropped, left: carol alice-2
```

## بلاک، reorg و broadcast دوباره

بعد از هر بلاک، نود mempool را روی نوک تازه از نو می‌سازد: تراکنش‌های تأییدشده بیرون می‌روند، تراکنش‌های بلاک‌های جداشده اول امتحان می‌شوند و بعد بقیه به ترتیب ورود؛ هر چه حالا double spend شده یا والدش رفته حذف می‌شود. Bitcoin Core این کار را تدریجی می‌کند؛ از نو ساختن ساده‌تر است.

تراکنش‌های برگشته دوباره broadcast می‌شوند. همان partition پست قبل، با کارمزد ۱ سکه روی دو پرداخت (لاگ کوتاه شده):

```
[B] REORG: disconnect [2:000089], connect [2:0007d5 3:000b42]
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B]   tx 4eb5ab26deff from the old branch back to the mempool, re-broadcast to 2
...
[C] tx 4eb5ab26deff from B: valid, relayed to 1
...
[D] tx 4eb5ab26deff from C: valid, relayed to 0
...
C: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
D: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
```

دفعه‌ی قبل C و D با `pending 0` تمام کردند. `go test -race ./...` پاس می‌شود، از جمله تستی که reorg در آن فرزند را قبل از والدش برمی‌گرداند.

## چند نکته‌ی مهم

- با کارمزد به ازای بایت مرتب کنید و فرزند را همراه اجداد تأییدنشده‌اش بسنجید.
- جایگزین باید کارمزد هر چیزی را که حذف می‌کند بپردازد.
- mempool را محدود کنید و با امتیاز بسته بیرون کنید، نه نرخ خود تراکنش.
- قاعده‌های mempool سیاست محلی‌اند؛ consensus فقط بلاک معتبر را تعریف می‌کند.

## تمرین

۱. قاعده‌ی BIP-125 علیه ورودی تأییدنشده‌ی تازه در جایگزین را با یک تست اضافه کنید.
۲. بعد از بیرون کردن، حداقل نرخ را تا نرخ تراکنش بیرون‌رفته بالا ببرید و هر ۱۰ بلاک نصفش کنید.

## قدم بعدی

پست بعد: **Bitcoin Script: یک مفسر stack کوچک با Rust**.
