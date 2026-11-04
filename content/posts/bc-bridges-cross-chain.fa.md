+++
date = '2026-11-30T18:00:00+03:30'
draft = false
title = 'Bridge و ارتباط بین زنجیره‌ها'
description = 'bridge بین زنجیره‌ها با Go و Solidity: lock-and-mint بین دو anvil، امضای ۲ از ۳ با ecrecover، رد replay، کلیدهای دزدیده‌شده و سقف ضرب.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "bridge", "foundry", "security"]
cover = { image = "/images/covers/bc-bridges-cross-chain.fa.png", alt = "Bridge و ارتباط بین زنجیره‌ها", hiddenInSingle = true }
+++

فرض کنید در یک کازینو با پول نقد می‌روید و صندوق‌دار هزار تومان‌تان را می‌گیرد و در گاوصندوق می‌گذارد. در عوض به شما یک ژتون هزارتومانی می‌دهد که فقط توی همین کازینو خرج می‌شود. هر وقت ژتون را برگردانید، صندوق‌دار آن را پاره می‌کند و پول واقعی را پس می‌دهد. تا وقتی گاوصندوق به اندازه‌ی ژتون‌های موجود پول داشته باشد، همه‌چیز درست است.

{{< term "bridge" "Bridge" >}} (پل بین زنجیره‌ها) دقیقاً همین کار را بین دو بلاکچین می‌کند. ولی یک مشکل جدی دارد. زنجیره‌ی B از آنچه روی A اتفاق افتاده خبر ندارد، مگر کسی بیاید و بگوید. پس سؤال اصلی هر bridge این است: B حرف چه کسی را باور کند؟ در [Layer 2 و rollupها: optimistic و ZK](/fa/posts/bc-layer2-rollups/) قرارداد L1 خودش می‌توانست rollup را بررسی کند، چون داده‌اش روی L1 بود. دو زنجیره‌ی مستقل این امکان را ندارند.

ساده‌ترین و رایج‌ترین طرح اسمش {{< term "lock-and-mint" "lock-and-mint" >}} است (قفل کن، ضرب کن)، همان کازینوی بالا. من آن را بین دو زنجیره‌ی محلی ساختم. تکه‌هایش از مقاله‌های قبلی می‌آیند: جلوگیری از replay از [مدل حساب، nonce و جلوگیری از replay](/fa/posts/bc-account-model-nonce/)، امضا از [کلید، امضای ECDSA و آدرس روی secp256k1](/fa/posts/bc-keys-ecdsa-addresses/) و confirmation از [Event و ساخت indexer](/fa/posts/bc-event-indexer-go/).

> Go 1.27 با go-ethereum v1.17.10، Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). دو anvil: زنجیره‌ی A روی `127.0.0.1:8550` (chain id 31337) و B روی `127.0.0.1:8551` (chain id 31338). ماژول Go کپی ماژول مقاله‌ی قبل است و helper کوچک go-ethereum آن را نگه داشته. کلیدها کلیدهای تست عمومی anvil هستند، به‌علاوه‌ی کلیدهای اسباب‌بازی مثل `0xA1` در تست‌ها. کد آموزشی است و audit نشده.

## اینجا قفل، آنجا ضرب

روی زنجیره‌ی A قراردادی داریم به اسم `BridgeLock` (گاوصندوق). کسی توکن DemoToken را (همان توکن مقاله‌ی توکن‌ها) به آن می‌دهد و قرارداد رویداد `Deposit(nonce, from, recipient, amount)` را منتشر می‌کند، یعنی «این‌قدر واریز شد».

روی زنجیره‌ی B قراردادی داریم به اسم `BridgeMint` (چاپخانه‌ی ژتون). این قرارداد برای هر واریز توکن `wDEMO` می‌سازد، ولی فقط وقتی مدرک بیاورند که واریز واقعاً روی A اتفاق افتاده. مدرک چیست؟ امضای ۲ نفر از ۳ نفر که به آن‌ها {{< term "relayer" "relayer" >}} می‌گوییم. relayer برنامه‌ای است که واریزهای A را می‌پاید و پیامش را برای B امضا می‌کند. این قاعده‌ی «۲ از ۳» یک {{< term "multisig" "multisig" >}} است که خود قرارداد اجرایش می‌کند.

برگشت هم همین‌طور است. اگر کسی `wDEMO` را روی B بسوزاند، رویداد `Withdrawal` منتشر می‌شود و همان گروه relayerها آزادسازی توکن اصلی را روی A امضا می‌کنند.

هر relayer یک digest (خلاصه‌ی ۳۲ بایتی پیام) را امضا می‌کند. این digest هر دو سر مسیر را نام می‌برد، تا یک امضا فقط برای یک مسیر معتبر باشد:

```solidity
struct Message {
    uint256 srcChainId; address srcContract;
    uint256 dstChainId; address dstContract;
    uint256 nonce; address recipient; uint256 amount;
}

function digest(Message calldata m) public pure returns (bytes32) {
    return keccak256(abi.encode(keccak256("BC29_BRIDGE_V1"), m));
}
```

پیام می‌گوید: از کدام زنجیره و کدام قرارداد، به کدام زنجیره و کدام قرارداد، با چه شماره‌ی یکتایی (`nonce`)، چه مقدار و برای چه کسی.

قرارداد امضاکننده‌ی هر امضا را با {{< term "ecrecover" "ecrecover" >}} پیدا می‌کند. ecrecover از روی digest و امضا، آدرس امضاکننده را بیرون می‌کشد. این بدنه‌ی حلقه است (کوتاه‌شده):

```solidity
if (uint256(s) > HALF_N) revert BadSignature(); // reject the malleable twin
address signer = ecrecover(d, v, r, s);
if (signer == address(0) || signer <= last) revert BadSignature(); // sorted: no double counting
last = signer;
if (isRelayer[signer]) valid++;
// after the loop:
if (valid < threshold) revert NotEnoughSignatures(valid, threshold);
```

خط‌به‌خط:

- **خط اول:** برای هر امضای ECDSA یک «دوقلو» با مقدار `s` متفاوت هم وجود دارد که همان پیام را تأیید می‌کند. قرارداد فقط نسخه‌ی با `s` کوچک را می‌پذیرد تا یک امضا به دو شکل در نیاید.
- **خط دوم و سوم:** امضاکننده پیدا می‌شود. امضاها باید به ترتیب آدرس مرتب باشند (`signer <= last` رد می‌شود). این کار جلوی شمردن یک relayer دو بار را می‌گیرد.
- **خط چهارم:** فقط امضای relayerهای شناخته‌شده شمرده می‌شود.
- **بعد از حلقه:** اگر کمتر از حد نصاب (اینجا ۲) امضای معتبر باشد، تراکنش رد می‌شود.

`mint` علاوه بر این، chain id و قرارداد مبدأ و مقصد پیام را با مقدار خودش مقایسه می‌کند و nonce واریز را «استفاده‌شده» علامت می‌زند.

## relayer

relayer ما یک برنامه‌ی Go است. واریزها را (`Deposit`) در لاگ‌های A می‌خواند، ولی فقط وقتی دست‌کم ۲ بلاک روی بلاک واریز آمده باشد عمل می‌کند. دلیلش این است که بلاک‌های تازه ممکن است با یک reorg کنار بروند ([Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر](/fa/posts/bc-forks-reorgs/))، و اگر relayer واریزی را امضا کند که بعد حذف شود، `wDEMO` ساخته شده و چیزی قفل نشده است.

نکته‌ی دیگر: relayer digest را خودش حساب می‌کند. اگر از قرارداد مقصد می‌پرسید چه چیزی را امضا کند، هر چه آن قرارداد می‌گفت امضا می‌کرد:

```go
safe := head - w.Confirmations
q.FromBlock, q.ToBlock = new(big.Int).SetUint64(w.next), new(big.Int).SetUint64(safe)
confirmed, err = w.Chain.FilterLogs(ctx, q)
w.next = safe + 1
```

کد هر بار فقط تا بلاک `head - 2` را می‌خواند و جایی که ایستاده را به یاد می‌سپارد (`w.next`).

برای ساده‌ماندن، یک پردازش نقش هر سه relayer را بازی می‌کند (حساب‌های ۵ تا ۷ anvil، با نام r5 و r6 و r7). در واریز، r7 «آفلاین» است. با `go run ./cmd/bridge` اجرا می‌کنیم. برنامه ابتدا قراردادها را روی دو زنجیره می‌سازد. بعد کاربر ۲۵۰ DEMO روی A قفل می‌کند، relayerها آن را می‌پایند و ۲۵۰ `wDEMO` روی B ساخته می‌شود. بعد همان پیام را دوباره می‌فرستد تا ببینیم رد می‌شود. در آخر کاربر ۱۰۰ `wDEMO` می‌سوزاند و توکن اصلی روی A آزاد می‌شود.

```
chain A id 31337, chain B id 31338
A: DemoToken 0x5FbDB231 BridgeLock 0xe7f1725E
B: BridgeMint 0x5FbDB231 wDEMO 0xa16E02E8
user locks 250 DEMO on A in block 6
relayer poll A: head 6, confirmed 0, waiting 1
(two more blocks on A)
relayer poll A: head 8, confirmed 1, waiting 0
  deposit 31337 -> 31338 nonce 1 amount 250e18 (block 6), digest matches contract: true
  r5+r6 signed, mint on B in block 2, gas 147740
user wDEMO on B: 250
replay on B: AlreadyProcessed()
same message on A: WrongRoute()
user burns 100 wDEMO on B in block 3
relayer poll B (head 5): withdrawal 31338 -> 31337 nonce 1 amount 100e18, r6+r7 signed, release on A in block 9
user DEMO on A: 850, locked on A: 150, wDEMO supply on B: 150, backed: true
```

خط‌به‌خط:

- **سه خط اول:** شناسه‌ی دو زنجیره و آدرس کوتاه‌شده‌ی قراردادها.
- **`user locks 250 DEMO on A in block 6`:** کاربر ۲۵۰ توکن را قفل کرد. شماره‌ی بلاک فقط نشان می‌دهد چند تراکنش پیش از این روی A بوده.
- **اولین `relayer poll A`:** واریز در تازه‌ترین بلاک است (`head 6`)، یعنی هنوز هیچ بلاکی رویش نیامده. `confirmed 0, waiting 1` یعنی هیچ واریز تأییدشده‌ای نیست و یکی منتظر است. relayer صبر می‌کند.
- **`(two more blocks on A)`:** برنامه دو بلاک خالی روی A می‌سازد. حالا head به ۸ رسیده و واریز دو بلاک عمق دارد.
- **دومین poll:** `confirmed 1`. relayer واریز را برمی‌دارد. `digest matches contract: true` یعنی digest که خودش حساب کرد با آنچه تابع `digest` قرارداد روی B می‌دهد یکی است.
- **`r5+r6 signed, mint on B`:** دو نفر امضا کردند و mint روی B انجام شد (`147740` gas).
- **`user wDEMO on B: 250`:** ژتون‌ها به دست کاربر رسید.
- **`replay on B: AlreadyProcessed()`:** همان پیام و همان امضاها را دوباره به B دادیم. قرارداد می‌بیند nonce قبلاً استفاده شده و رد می‌کند.
- **`same message on A: WrongRoute()`:** همان پیام را به قرارداد A فرستادیم. این پیام برای مسیر A به B ساخته شده بود و قرارداد A انتظار پیامی از B به A دارد، پس رد می‌شود.
- **بقیه:** کاربر ۱۰۰ `wDEMO` را روی B می‌سوزاند. relayerها (این بار r6 و r7، یعنی هر دو نفری کافی‌اند) سوختن را بعد از دو بلاک می‌بینند و آزادسازی روی A را امضا می‌کنند.
- **خط آخر:** کاربر ۸۵۰ DEMO روی A دارد (۱۰۰۰ منهای ۲۵۰ به‌علاوه‌ی ۱۰۰)، ۱۵۰ توکن هنوز قفل است و ۱۵۰ `wDEMO` روی B وجود دارد. `backed: true` یعنی این دو عدد برابرند.

به آدرس‌ها نگاه کنید: DemoToken روی A و BridgeMint روی B هر دو `0x5FbDB231...` هستند، چون همان deployer روی هر دو زنجیره با nonce صفر قرارداد ساخته. پس آدرس قرارداد یک زنجیره را مشخص نمی‌کند. برای همین {{< term "chain-id" "chain id" >}} داخل پیام امضاشده است. تکرار همان پیام روی B با nonce رد شد و فرستادنش به A با مسیر. این همان محافظت در برابر {{< term "replay-attack" "replay" >}} مقاله‌ی nonce است، ولی بین زنجیره‌ها.

مهم‌ترین قاعده (invariant) همان خط آخر است: توکن قفل‌شده روی A باید همیشه برابر `wDEMO` روی B باشد.

## وقتی کلید relayerها دزدیده شود

حالا بد بودن ماجرا را ببینیم. تمام امنیت این bridge در امضاهاست. اگر کسی دو کلید از سه کلید را بدزدد چه؟ یک تست Foundry همین را بازی می‌کند: مهاجم کلیدهای relayer شماره‌ی ۱ و ۲ را دارد و واریزی را امضا می‌کند که هرگز اتفاق نیفتاده:

```
$ forge test -vv
[PASS] test_BurnAndRelease() (gas: 547423)
[PASS] test_CompromisedThresholdMintsUnbacked() (gas: 428178)
Logs:
  wDEMO supply: 900.000000000000000000
  DEMO locked : 0.000000000000000000
[PASS] test_HigherThresholdStopsTwoKeys() (gas: 253767)
[PASS] test_MintWithTwoOfThree() (gas: 344897)
[PASS] test_OneSignatureOrDuplicateNotEnough() (gas: 270604)
[PASS] test_ReplayRejected() (gas: 365543)
[PASS] test_WrongChainRejected() (gas: 278001)
(trimmed)
```

نتیجه در بخش `Logs` است: ۹۰۰ `wDEMO` وجود دارد و هیچ DEMO‌ای پشتش قفل نیست. همه‌ی بررسی‌های قرارداد قبول شدند، چون از دید قرارداد پیام معتبر است: دو امضای درست از دو relayer شناخته‌شده. تا جایی که می‌دانم، چند مورد از بزرگ‌ترین دزدی‌های دنیای کریپتو bridgeهایی بودند که کلید validator یا relayerشان لو رفت. [تحلیل فنی هک Binance](/fa/posts/binance-hack-hot-wallet-2026/) درس مشابهی را از زاویه‌ی دیگر دارد: در آنجا هم نشانه‌ای از افشای کلید نبود، ولی سیستم امضا هر چه مهاجم خواست امضا کرد.

## محدودکردن خسارت

همان تست ادامه پیدا می‌کند و راه‌هایی را نشان می‌دهد که خودم در قرارداد گذاشته‌ام:

- **سقف در هر دوره:** `BridgeMint` در هر روز حداکثر ۱۰۰۰ واحد می‌سازد ({{< term "rate-limiting" "rate limiting" >}}). مهاجم ۹۰۰ ساخته بود؛ ۲۰۰ جعلیِ بعدی با خطای `RateLimited(1100e18, 1000e18)` رد می‌شود، چون جمع ۱۱۰۰ از سقف ۱۰۰۰ می‌گذرد.
- **توقف اضطراری (pause):** یک نگهبان (guardian) می‌تواند ساخت را متوقف کند. پیام جعلی بعدی با `Paused()` برمی‌گردد. البته کلید خود نگهبان هم هدف است.
- **حد نصاب بالاتر:** با ۳ از ۵ امضا، دو کلید دزدیده‌شده به `NotEnoughSignatures(2, 3)` می‌خورند. این فقط وقتی کمک می‌کند که کلیدها دست اپراتورهای مستقل و روی ماشین‌های جدا باشند.

مدل قوی‌تر خود امضاکننده‌های مورد اعتماد را حذف می‌کند. در آن مدل B یک {{< term "light-client" "light client" >}} از A را اجرا می‌کند (برنامه‌ای که هدر بلاک‌های A را دنبال و بررسی می‌کند) و با یک Merkle proof تأیید می‌کند واریز واقعاً در بلاکی از A هست؛ یا به‌جای آن یک اثبات ZK از همین موضوع. هیچ‌کدام را نساخته‌ام. تا جایی که می‌فهمم، بهایش gas و پیچیدگی بیشتر است، و امنیتش به قطعیت زنجیره‌ی مبدأ بستگی دارد.

## تله‌های رایج bridge

- روی chain id و قرارداد مبدأ و مقصد، و یک nonce امضا کنید. آدرس قرارداد به‌تنهایی بین زنجیره‌ها یکتا نیست.
- پیش از امضا confirmation صبر کنید. واریزی که reorg شود یعنی توکن ساخته‌شده بدون چیزی که قفل شده باشد.
- امضاکننده‌های مرتب و متمایز بخواهید و امضای با `s` بزرگ را رد کنید.
- بررسی کنید قفل‌شده برابر ساخته‌شده است، و اگر نبود هشدار بدهید.

## تمرین

1. در `BridgeLock.release` هم یک سقف برای هر انتقال بگذارید.
2. زنجیره‌ی A را بعد از امضای واریزی با صفر confirmation reorg کنید. invariant چه می‌گوید؟

## قدم بعدی

**مبانی zero-knowledge proof با Rust**: اثبات‌ها همان راهی هستند که طرح‌های قوی‌تر با آن امضاکننده‌های مورد اعتماد را حذف می‌کنند.
