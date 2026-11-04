+++
date = '2026-11-27T18:00:00+03:30'
draft = false
title = 'MEV و ترتیب تراکنش‌ها'
description = 'MEV روی anvil محلی: یک searcher با Go یک swap در انتظار را sandwich می‌کند، بعد minAmountOut واقعی و deadline جلویش را می‌گیرند؛ و ترتیب anvil.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "mev", "defi", "go-ethereum"]
cover = { image = "/images/covers/bc-mev-ordering.fa.png", alt = "MEV و ترتیب تراکنش‌ها", hiddenInSingle = true }
+++

فرض کنید در یک حراجی هستید و می‌خواهید چیزی بخرید. منشی سفارش‌ها را روی میز می‌گذارد و هر سفارش را به ترتیبی که خودش می‌خواهد بازمی‌کند. اگر کسی بتواند پیش از سفارش شما، سفارش خودش را روی میز بگذارد و بعد از شما هم یک سفارش دیگر، می‌تواند از وجود شما سود ببرد، بی‌آنکه چیزی بداند که شما نمی‌دانید.

در بلاکچین منشی، سازنده‌ی بلاک است. در [AMM و فرمول constant product](/fa/posts/bc-amm-constant-product/) دیدیم همان swap ده‌هزار USDXی، بسته به این‌که چه چیزی زودتر اجرا شود، 90.66 یا 63.95 DEMO می‌دهد. این ترتیب را سازنده‌ی بلاک انتخاب می‌کند. ارزشی که با انتخاب، اضافه کردن یا کنار گذاشتن تراکنش‌ها می‌شود برداشت، {{< term "mev" "MEV" >}} نام دارد (maximal extractable value، بیشینه‌ی ارزش قابل برداشت). [بهینه‌سازی gas و قرارداد قابل ارتقا با proxy](/fa/posts/bc-gas-optimization-proxies/) درباره‌ی هزینه‌ی تراکنش بود؛ این پست درباره‌ی زمان اجرای آن است.

در [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/) ماینر خودم بر اساس نرخ کارمزد مرتب می‌کرد. این‌جا {{< term "mempool" "استخر تراکنش‌های در انتظار" >}} یک نود واقعی را از Go می‌خوانم، با کد کلاینت [کار با اتریوم از Go با go-ethereum](/fa/posts/bc-go-ethereum-client/). همه‌چیز روی قراردادهای خودم در anvil محلی اجرا می‌شود، تا ببینیم محافظت‌ها چرا وجود دارند.

> اجرا با Go 1.27، go-ethereum v1.17.10 (binding با abigen v2) و Foundry 1.8.7 روی macOS (arm64). `SimplePool` و `DemoToken` بدون تغییر از پست AMM کپی شده‌اند، به‌علاوه‌ی یک اسکریپت deploy: ۱٬۰۰۰ DEMO و ۱۰۰٬۰۰۰ USDX در استخر و ۲۰٬۰۰۰ USDX برای حساب ۲. کلیدها کلیدهای تست عمومی anvil‌اند (حساب ۱ قربانی است). anvil فقط روی 127.0.0.1 گوش می‌دهد؛ پایین `--rpc-url` را حذف کرده‌ام. هش تراکنش‌ها در هر اجرا فرق می‌کند، ولی بقیه‌ی خروجی‌ها قطعی‌اند.

## تراکنش‌هایی که منتظر می‌مانند

تراکنشی که می‌فرستید فوراً در بلاک نمی‌رود. اول در استخر تراکنش‌های در انتظار (mempool) می‌ماند، و هر کسی که به نود وصل باشد می‌تواند آن را ببیند. سازنده‌ی بلاک بعداً از میان آن‌ها انتخاب می‌کند. این فاصله است که MEV را ممکن می‌کند.

برای دیدن این فاصله، بعد از deploy اتوماین anvil را خاموش می‌کنم تا تراکنش‌ها منتظر بمانند تا خودم بلاک بسازم. بعد قربانی را اجرا می‌کنم:

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/mev victim
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 0.00, deadline +300s
victim: sent 0xf158a547
```

قربانی می‌خواهد ۱۰٬۰۰۰ USDX را با DEMO عوض کند. قبل از ارسال، از استخر پرسیده «اگر الان بخرم چند DEMO می‌گیرم؟» (quote) و جواب 90.66 بوده. ولی دو پارامتر swap را بی‌دقت تنظیم کرده:

- **`minAmountOut`:** حداقل DEMOیی که قربانی قبول می‌کند. اینجا صفر است، یعنی «هر چقدر شد، قبول».
- **`deadline`:** تا چه زمانی swap معتبر است. اینجا ۳۰۰ ثانیه بعد از آخرین بلاک.

تراکنش در انتظار عمومی است: anvil آن را با `txpool_content` نشان می‌دهد و در شبکه‌ی واقعی بین نودها gossip می‌شود.

## یک searcher با Go

{{< term "searcher" "searcher" >}} برنامه‌ای است که تراکنش‌های در انتظار را دنبال سود می‌گردد. مال من اول تراکنش‌های در انتظار را می‌خواند. calldata هر تراکنش (۴ بایت اول شناسه‌ی تابع و بقیه آرگومان‌ها) را با ABI decode می‌کند و اگر یک `swap` روی استخر من باشد، شبیه‌سازی می‌کند. شبیه‌سازی با همان `getAmountOut` خود استخر و از راه `eth_call` انجام می‌شود، پس حسابش دقیقاً حساب قرارداد است. (کد ساده‌شده است؛ دمو با `*big.Int` کار می‌کند.)

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

ایده‌ی حلقه این است. searcher ۲۰٬۰۰۰ USDX دارد. برای هر مبلغ آزمایشی `s` (از ۱٬۰۰۰ تا ۲۰٬۰۰۰) سه قدم را روی موجودی‌های شبیه‌سازی‌شده‌ی استخر پیش می‌برد: ۱) خودش با `s` DEMO می‌خرد و قیمت بالا می‌رود. ۲) swap قربانی اجرا می‌شود و چون قیمت بالاتر است DEMO کمتری می‌گیرد، و خودش هم قیمت را باز بالاتر می‌برد. ۳) searcher DEMOیی که خریده را می‌فروشد، به قیمتی که حالا بالاتر است. اگر در قدم ۲ قربانی کمتر از `minAmountOut` خودش بگیرد، تراکنشش revert می‌شود و sandwich بی‌فایده است، پس رد می‌شود. از میان مبلغ‌های باقی‌مانده، بیشترین سود انتخاب می‌شود.

بعد searcher دو تراکنش می‌فرستد. اولی یک خرید {{< term "front-running" "front-run" >}} است که tip بیشتری از قربانی می‌دهد تا جلوتر در بلاک بنشیند. دومی فروش back-run است (با nonce بعدی) که tip کمتری می‌دهد تا بعد از قربانی بنشیند. هر کدام `minAmountOut` خودش را دارد.

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

خروجی searcher:

- **خط اول و دوم:** تراکنش قربانی پیدا شد و به‌تنهایی 90.66 DEMO می‌گرفت.
- **خط سوم:** بهترین مبلغ، کل بودجه‌ی searcher یعنی ۲۰٬۰۰۰ USDX است. با آن، قربانی فقط 63.95 DEMO می‌گیرد و سود مورد انتظار 3032.19 USDX است.
- **خط چهارم:** دو تراکنش فرستاده شد. `tip` پاداشی است که به سازنده‌ی بلاک می‌رسد و `cap` سقف کل کارمزد هر واحد gas است.

بعد بلاک ساخته شد و `block` آن را به ترتیب نشان می‌دهد. ترتیب همان ساندویچ است: خرید searcher، swap قربانی، فروش searcher. searcher با ۲۰٬۰۰۰ USDX شروع کرد، 166.24 DEMO خرید و بعد آن را به 23٬032.19 USDX فروخت. قربانی هم 63.95 DEMO گرفت.

به این کار {{< term "sandwich-attack" "sandwich" >}} می‌گویند: تراکنش قربانی بین دو تراکنش searcher مثل پرِ ساندویچ قرار گرفت. قربانی حدود 26.7 DEMO کمتر از quote خودش گرفت و searcher 3,032.19 USDX برداشت. چون `minAmountOut` صفر بود، فقط بودجه‌ی searcher سودش را محدود می‌کرد.

## ببینید نود چطور مرتب می‌کند

اجرای اولم برعکس درآمد: اول قربانی، و هر دو تراکنش searcher روی حداقل خروجی خودشان revert شدند. دلیل را از ترتیب نود فهمیدم. سقف کارمزد هر سه تراکنش 100 gwei بود. برای آزمایش مستقیم، سه انتقال ساده از سه حساب فرستادم:

| tip | fee cap | جایگاه |
|---|---|---|
| 1 gwei | 50 gwei | 0 |
| 3 gwei | 30 gwei | 1 |
| 5 gwei | 10 gwei | 2 |

anvil 1.8.7 با `--order fees` (پیش‌فرض) بر اساس `maxFeePerGas` (همان cap) مرتب کرد، نه tip. یعنی تراکنشی که tip بیشتری می‌دهد ولی سقف پایین‌تری گذاشته، عقب‌تر نشست. برای همین دمو سقف را 50 gwei به‌علاوه‌ی tip می‌گذارد. تا جایی که من می‌دانم geth بر اساس tip مؤثر مرتب می‌کند. نکته این است که سیاست ترتیب دست سازنده‌ی بلاک است و جایی تضمین نشده؛ تستش کنید، فرض نکنید.

## محافظت: یک minAmountOut واقعی

حالا همان قربانی را با یک حداقل واقعی می‌فرستیم. `-min-bps 50` یعنی تحمل نیم درصد (۵۰ basis point) کمتر از quote:

```
$ go run ./cmd/mev victim -min-bps 50
victim: swap 10000 USDX -> DEMO, quote 90.66, minAmountOut 90.20, deadline +300s
$ go run ./cmd/mev searcher
(trimmed)
searcher: no profitable front-run keeps the victim above minAmountOut, skip
```

این تحمل، {{< term "slippage" "slippage" >}} نیم‌درصدی است. هیچ front-run در گام‌های ۱٬۰۰۰ USDXی هم قربانی را بالای حداقلش نگه نداشت و هم دو کارمزد ۰٫۳ درصدی استخر (برای خرید و فروش) را درآورد. searcher از حمله صرف‌نظر کرد.

اگر searcher بی‌دقت باشد (`-ignore-min`، که حداقل قربانی را نادیده می‌گیرد) و بلاک را بگیرد، این می‌شود:

```
0  searcher nonce 2 tip 3 cap 53 gwei status 1  20000.00 USDX -> 166.24 DEMO
1  victim   nonce 2 tip 2 cap 52 gwei status 0
2  searcher nonce 3 tip 1 cap 51 gwei status 0
searcher USDX change: -20000.00, DEMO held: 166.24
(trimmed)
$ cast run <victim tx hash>
    └─ ← [Revert] SlippageExceeded(63956986828671189740 [6.395e19], 90207783941074838592 [9.02e19])
```

`status 0` یعنی تراکنش revert شد. swap قربانی revert کرد، چون حداقل 90.20 DEMO می‌خواست ولی استخر فقط حدود 63.96 می‌داد (`SlippageExceeded(گرفتنی, حداقل)`). back-run هم revert شد: searcher می‌خواست DEMOهایش را دست‌کم به ۲۰٬۰۰۰ USDX بفروشد، ولی چون swap قربانی اجرا نشده بود و قیمت را بالاتر نبرده بود، استخر فقط 19,900.05 USDX می‌داد (این عدد را با فرمول استخر حساب کردم). نتیجه: searcher ۲۰٬۰۰۰ USDX داد و 166.24 DEMO دارد که به ۲۰٬۰۰۰ فروش نمی‌رود. قربانی فقط gas داد و USDXش ماند.

## محافظت: deadline

swapی که منتظر می‌ماند ممکن است خیلی دیرتر، در لحظه‌ای بدتر اجرا شود. `deadline` جلوی این را می‌گیرد: اگر زمان بلاک از آن گذشته باشد، swap revert می‌شود. یکی با `-deadline 60` فرستادم، ساعت anvil را با `evm_increaseTime 600` ده دقیقه جلو بردم و بلاک ساختم:

```
0  victim   nonce 2 tip 2 cap 52 gwei status 0
    └─ ← [Revert] Expired()
(trimmed)
```

## محافظت‌های دیگر (این‌جا اجرا نکردم)

- **ارسال خصوصی:** تراکنش را مستقیم به یک سازنده‌ی بلاک بفرستید، نه به استخر عمومی. به گیرنده اعتماد می‌کنید.
- **حراج دسته‌ای (batch auction):** سفارش‌های یک بازه با یک قیمت تسویه می‌شوند و ترتیب داخل دسته بی‌اثر است.
- **{{< term "commit-reveal" "Commit-reveal" >}}:** اول hash سفارش را منتشر کنید و محتوا را بعد، تا کسی در زمان انتظار چیزی نبیند.
- **جداسازی سازنده و پیشنهاددهنده:** تا جایی که من می‌دانم در اتریوم بسیاری از بلاک‌ها را builderها می‌سازند و proposer با حراج انتخاب می‌کند ({{< term "proposer-builder-separation" "proposer-builder separation" >}}، اغلب با MEV-Boost). این قدرت ترتیب را جابه‌جا می‌کند، نه حذف.

## همه‌ی MEV مضر نیست

اگر از sandwich فقط بدی دیدید، تصویر ناقص است. back-run در مثال بالا قیمت استخر را برگرداند. {{< term "arbitrage" "Arbitrage" >}} بین دو استخر همین کار را می‌کند: اگر یک توکن در یکی گران‌تر باشد، معامله‌گر از ارزان می‌خرد و در گران می‌فروشد، و قیمت DEXها را هم‌راستا نگه می‌دارد. {{< term "liquidation" "liquidation" >}}های پست [وام‌دهی، وثیقه و liquidation](/fa/posts/bc-lending-liquidation/) هم MEV هستند: پاداش به اولین نفر می‌رسد و بدون آن‌ها bad debt بزرگ می‌شود.

## پیش از امضای یک swap

- **swap با `minAmountOut = 0` امضا نکنید.** آن را از quote تازه حساب کنید.
- **deadline را چند دقیقه بگذارید.**
- **ترتیب، سیاست سازنده‌ی بلاک است.** تستش کنید، فرض نکنید.

## تمرین

1. یک استخر دوم با قیمت دیگر اضافه کنید و arbitrageی بنویسید که دو قیمت را به هم برساند.
2. بزرگ‌ترین front-run را پیدا کنید که قربانی را بالای تحمل ۱، ۰٫۵ و ۰٫۱ درصد نگه دارد. کی سود می‌دهد؟
3. anvil را با `--order fifo` دوباره اجرا کنید و sandwich را تکرار کنید.

## قدم بعدی

**Proof of Stake، BFT و finality**: بعد از ترتیب داخل بلاک، این‌که چه کسی بلاک را می‌سازد و کی قطعی می‌شود.
