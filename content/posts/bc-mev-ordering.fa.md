+++
date = '2026-11-27T18:00:00+03:30'
draft = false
title = 'MEV و ترتیب تراکنش‌ها'
description = 'MEV روی anvil محلی: یک searcher با Go یک swap در انتظار را sandwich می‌کند، بعد minAmountOut واقعی و deadline جلویش را می‌گیرند؛ و ترتیب anvil.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "mev", "defi", "go-ethereum"]
cover = { image = "/images/covers/bc-mev-ordering.fa.png", alt = "MEV و ترتیب تراکنش‌ها", hiddenInSingle = true }
+++

[بهینه‌سازی gas و قرارداد قابل ارتقا با proxy](/fa/posts/bc-gas-optimization-proxies/) درباره‌ی هزینه‌ی تراکنش بود؛ این پست درباره‌ی زمان اجرای آن است. سازنده‌ی بلاک ترتیب را انتخاب می‌کند و ترتیب نتیجه را عوض می‌کند: در [AMM و فرمول constant product](/fa/posts/bc-amm-constant-product/) همان swap ده‌هزار USDXی، بسته به این‌که چه چیزی زودتر اجرا شود، 90.66 یا 63.95 DEMO داد. ارزشی که با انتخاب، اضافه کردن یا کنار گذاشتن تراکنش‌ها می‌شود برداشت، {{< term "mev" "MEV" >}} (maximal extractable value) نام دارد.

در [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/) ماینر خودم بر اساس نرخ کارمزد مرتب می‌کرد. این‌جا {{< term "mempool" "استخر تراکنش‌های در انتظار" >}} یک نود واقعی را از Go می‌خوانم، با کد کلاینت [کار با اتریوم از Go با go-ethereum](/fa/posts/bc-go-ethereum-client/). همه چیز روی قراردادهای خودم در anvil محلی اجرا می‌شود.

> اجرا با Go 1.27، go-ethereum v1.17.10 (binding با abigen v2) و Foundry 1.8.7 روی macOS (arm64). `SimplePool` و `DemoToken` بدون تغییر از پست AMM کپی شده‌اند، به‌علاوه‌ی یک اسکریپت deploy: ۱٬۰۰۰ DEMO و ۱۰۰٬۰۰۰ USDX در استخر و ۲۰٬۰۰۰ USDX برای حساب ۲. کلیدها کلیدهای تست عمومی anvil‌اند (حساب ۱ قربانی است). anvil فقط روی 127.0.0.1 گوش می‌دهد؛ پایین `--rpc-url` را حذف کرده‌ام.

## تراکنش‌هایی که منتظر می‌مانند

بعد از deploy، automine را خاموش می‌کنم تا تراکنش‌ها منتظر بمانند:

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/mev victim
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 0.00, deadline +300s
victim: sent 0xf158a547
```

قربانی 90.66 DEMO قیمت گرفته ولی هر چیزی را قبول می‌کند. تراکنش در انتظار عمومی است: anvil آن را با `txpool_content` نشان می‌دهد و در شبکه‌ی واقعی بین نودها gossip می‌شود.

## یک searcher با Go

{{< term "searcher" "searcher" >}} تراکنش‌های در انتظار را دنبال سود می‌گردد. مال من calldata را با ABI decode می‌کند و با همان `getAmountOut` خود استخر از راه `eth_call` شبیه‌سازی می‌کند، پس حسابش دقیقاً حساب قرارداد است (ساده‌شده؛ دمو با `*big.Int` کار می‌کند):

```go
var content struct {
	Pending map[common.Address]map[string]*types.Transaction `json:"pending"`
}
rc.CallContext(ctx, &content, "txpool_content")
args, _ := swapM.Inputs.Unpack(tx.Data()[4:]) // tokenIn, amountIn, minAmountOut, to, deadline

for s := step; s <= budget; s += step { // 1,000 USDX steps
	got := amountOut(s, rU, rD)                // 1) our buy
	v := amountOut(vIn, rU+s, rD-got)          // 2) the victim's buy
	if v < vMin { continue }                   // the victim would revert
	back := amountOut(got, rD-got-v, rU+s+vIn) // 3) our sell
	profit := back - s
}
```

بعد یک خرید {{< term "front-running" "front-run" >}} می‌فرستد که بیشتر از قربانی کارمزد می‌دهد و یک فروش back-run (با nonce بعدی) که کمتر می‌دهد؛ هر کدام با `minAmountOut` خودش.

```
$ go run ./cmd/mev searcher
searcher: pending swap from victim: 10000.00 USDX in, minAmountOut 0.00, tip 2 gwei
searcher: victim alone would get 90.66 DEMO
searcher: best front-run 20000.00 USDX, victim would get 63.95 DEMO, expected profit 3032.19 USDX
searcher: sent front-run 0x4e0a3314 (tip 3, cap 53 gwei), back-run 0x0e111db4 (tip 1, cap 51 gwei)
$ cast rpc anvil_mine
$ go run ./cmd/mev block
block 13, base fee 208805657 wei, 3 txs
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 1  10000.00 USDX -> 63.95 DEMO
2  searcher nonce 3 tip 1 cap 51 gwei status 1  166.24 DEMO -> 23032.19 USDX
victim DEMO balance:   63.95
searcher USDX change: 3032.19, DEMO held: 0.00
```

این یک {{< term "sandwich-attack" "sandwich" >}} است: قربانی 26.70 DEMO کمتر گرفت و searcher مبلغ 3,032.19 USDX برداشت. با `minAmountOut = 0` فقط بودجه سود را محدود می‌کرد.

## ببینید نود چطور مرتب می‌کند

اجرای اولم برعکس درآمد: اول قربانی، و هر دو تراکنش searcher روی حداقل خروجی خودشان revert شدند. سقف کارمزد هر سه 100 gwei بود. سه انتقال ساده:

| tip | fee cap | جایگاه |
|---|---|---|
| 1 gwei | 50 gwei | 0 |
| 3 gwei | 30 gwei | 1 |
| 5 gwei | 10 gwei | 2 |

anvil 1.8.7 با `--order fees` (پیش‌فرض) بر اساس `maxFeePerGas` مرتب کرد، نه tip؛ برای همین دمو سقف را 50 gwei به‌علاوه‌ی tip می‌گذارد. تا جایی که من می‌دانم geth بر اساس tip مؤثر مرتب می‌کند. سیاست ترتیب دست سازنده‌ی بلاک است.

## محافظت: یک minAmountOut واقعی

```
$ go run ./cmd/mev victim -min-bps 50
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 90.20, deadline +300s
$ go run ./cmd/mev searcher
(trimmed)
searcher: no profitable front-run keeps the victim above minAmountOut, skip
```

با تحمل {{< term "slippage" "slippage" >}} نیم‌درصدی، هیچ front-run در گام‌های ۱٬۰۰۰ USDXی هم قربانی را بالای حداقلش نگه نداشت و هم دو کارمزد ۰٫۳ درصد را درآورد. searcher بی‌دقت (`-ignore-min`) این بلاک را می‌گیرد:

```
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 0
2  searcher nonce 3 tip 1 cap 51 gwei status 0
searcher USDX change: -20000.00, DEMO held: 166.24
(trimmed)
$ cast run <victim tx hash>
    └─ ← [Revert] SlippageExceeded(63956986828671189740 [6.395e19], 90207783941074838592 [9.02e19])
```

قربانی فقط gas داد و USDXش ماند. فروش DEMOی searcher حالا 19,900.05 USDX برمی‌گرداند.

## محافظت: deadline

swapی که منتظر می‌ماند ممکن است دیرتر و در لحظه‌ی بدتری اجرا شود. یکی با `-deadline 60` فرستادم، ساعت anvil را با `evm_increaseTime 600` جلو بردم و بلاک ساختم:

```
0  victim   nonce 2 tip 2 cap 52 gwei status 0
    └─ ← [Revert] Expired()
(trimmed)
```

## محافظت‌های دیگر (این‌جا اجرا نکردم)

- ارسال خصوصی: تراکنش را به یک سازنده‌ی بلاک بفرستید، نه به استخر عمومی. به گیرنده اعتماد می‌کنید.
- حراج دسته‌ای (batch auction): سفارش‌های یک بازه با یک قیمت تسویه می‌شوند و ترتیب داخل دسته بی‌اثر است.
- {{< term "commit-reveal" "Commit-reveal" >}}: اول hash را منتشر کنید، محتوا را بعد.
- تا جایی که من می‌دانم در اتریوم بسیاری از بلاک‌ها را builderها می‌سازند و proposer با حراج انتخاب می‌کند ({{< term "proposer-builder-separation" "proposer-builder separation" >}}، اغلب با MEV-Boost). این قدرت ترتیب را جابه‌جا می‌کند، نه حذف.

## همه‌ی MEV مضر نیست

back-run قیمت را برگرداند. {{< term "arbitrage" "Arbitrage" >}} بین دو استخر همین کار را می‌کند و قیمت DEXها را هم‌راستا نگه می‌دارد. {{< term "liquidation" "liquidation" >}}های پست [وام‌دهی، وثیقه و liquidation](/fa/posts/bc-lending-liquidation/) هم MEV هستند: پاداش به اولین نفر می‌رسد و بدون آن‌ها bad debt بزرگ می‌شود.

## چند نکته‌ی مهم

- swap با `minAmountOut = 0` امضا نکنید؛ آن را از quote تازه حساب کنید.
- deadline را چند دقیقه بگذارید.
- ترتیب، سیاست سازنده‌ی بلاک است. تستش کنید، فرض نکنید.

## تمرین

1. یک استخر دوم با قیمت دیگر اضافه کنید و arbitrageی بنویسید که دو قیمت را به هم برساند.
2. بزرگ‌ترین front-run را پیدا کنید که قربانی را بالای تحمل ۱، ۰٫۵ و ۰٫۱ درصد نگه دارد. کی سود می‌دهد؟
3. anvil را با `--order fifo` دوباره اجرا کنید و sandwich را تکرار کنید.

## قدم بعدی

پست بعد: **Proof of Stake، BFT و finality**.
