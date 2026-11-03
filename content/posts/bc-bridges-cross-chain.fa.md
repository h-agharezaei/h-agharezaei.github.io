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

زنجیره‌ی B از اتفاق‌های A خبر ندارد مگر کسی بگوید، و {{< term "bridge" "bridge" >}} بیشتر از هر چیز همین سؤال است: B حرف چه کسی را باور کند؟ در [Layer 2 و rollupها: optimistic و ZK](/fa/posts/bc-layer2-rollups/) قرارداد L1 خودش می‌توانست rollup را بررسی کند، چون داده روی L1 بود. دو زنجیره‌ی مستقل این امکان را ندارند.

ساده‌ترین طرح رایج، {{< term "lock-and-mint" "lock-and-mint" >}}، را بین دو زنجیره‌ی محلی ساختم. جلوگیری از replay از [مدل حساب، nonce و جلوگیری از replay](/fa/posts/bc-account-model-nonce/)، امضا از [کلید، امضای ECDSA و آدرس روی secp256k1](/fa/posts/bc-keys-ecdsa-addresses/) و confirmation از [Event و ساخت indexer](/fa/posts/bc-event-indexer-go/) می‌آید.

> Go 1.27 با go-ethereum v1.17.10، Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). دو anvil: زنجیره‌ی A روی `127.0.0.1:8550` (chain id 31337) و B روی `127.0.0.1:8551` (chain id 31338). ماژول Go کپی ماژول پست قبل است و helper کوچک go-ethereum آن را نگه داشته. کلیدها کلیدهای تست عمومی anvil هستند، به‌علاوه‌ی کلیدهای اسباب‌بازی مثل `0xA1` در تست‌ها. کد آموزشی است و audit نشده.

## اینجا قفل، آنجا ضرب

`BridgeLock` روی A توکن DemoToken (از پست توکن‌ها) را می‌گیرد و `Deposit(nonce, from, recipient, amount)` منتشر می‌کند. `BridgeMint` روی B برای آن واریز `wDEMO` می‌سازد، ولی فقط با امضای ۲ از ۳ {{< term "relayer" "relayer" >}}؛ یعنی یک {{< term "multisig" "multisig" >}} که قرارداد اجرایش می‌کند. سوزاندن `wDEMO` روی B رویداد `Withdrawal` می‌دهد و همان گروه آزادسازی روی A را امضا می‌کنند.

هر relayer digestی را امضا می‌کند که هر دو سر مسیر را نام می‌برد:

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

قرارداد امضاکننده‌ی هر امضا را با {{< term "ecrecover" "ecrecover" >}} پیدا می‌کند (بدنه‌ی حلقه، کوتاه‌شده):

```solidity
if (uint256(s) > HALF_N) revert BadSignature(); // reject the malleable twin
address signer = ecrecover(d, v, r, s);
if (signer == address(0) || signer <= last) revert BadSignature(); // sorted: no double counting
last = signer;
if (isRelayer[signer]) valid++;
// after the loop:
if (valid < threshold) revert NotEnoughSignatures(valid, threshold);
```

`mint` همچنین chain id و قرارداد مبدأ و مقصد را با مقدارهای خودش مقایسه می‌کند و nonce واریز را مصرف‌شده علامت می‌زند.

## relayer

relayer (با Go) لاگ‌های `Deposit` را poll می‌کند و فقط وقتی کاری می‌کند که دو بلاک عمق گرفته باشند. digest را خودش حساب می‌کند؛ relayerی که از قرارداد مقصد بپرسد چه چیزی امضا کند، هر چه آن قرارداد بگوید امضا می‌کند:

```go
safe := head - w.Confirmations
q.FromBlock, q.ToBlock = new(big.Int).SetUint64(w.next), new(big.Int).SetUint64(safe)
confirmed, err = w.Chain.FilterLogs(ctx, q)
w.next = safe + 1
```

یک پروسه نقش هر سه relayer را بازی می‌کند (حساب‌های ۵ تا ۷ anvil)؛ r7 هنگام واریز «آفلاین» است. `go run ./cmd/bridge`:

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

به آدرس‌ها نگاه کنید: DemoToken روی A و BridgeMint روی B هر دو `0x5FbDB231...` هستند، چون یک deployer روی هر دو زنجیره با nonce صفر deploy کرده. آدرس قرارداد زنجیره را مشخص نمی‌کند و برای همین {{< term "chain-id" "chain id" >}} داخل پیام امضاشده است. تکرار همان پیام روی B به خاطر nonce رد می‌شود و فرستادنش به A به خاطر مسیر. این همان محافظت در برابر {{< term "replay-attack" "replay" >}} از پست nonce است، این بار بین زنجیره‌ها.

invariant در خط آخر است: توکن قفل‌شده روی A برابر `wDEMO` روی B است.

## وقتی کلید relayerها دزدیده شود

امضاها خود bridge هستند. یک تست Foundry کلیدهای relayer شماره‌ی ۱ و ۲ را به مهاجم می‌دهد و او واریزی را امضا می‌کند که هرگز رخ نداده:

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

۹۰۰ `wDEMO` بدون هیچ پشتوانه‌ای. همه‌ی چک‌ها رد شدند، چون از دید قرارداد پیام معتبر است. تا جایی که می‌دانم، چند مورد از بزرگ‌ترین سرقت‌های کریپتو bridgeهایی بوده‌اند که کلید validatorها یا relayerهایشان لو رفته بود. [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) همین درس را از زاویه‌ی دیگری دارد: آنجا کلیدی لو نرفت، ولی سیستم امضا هر چه مهاجم خواست امضا کرد.

## محدود کردن خسارت

همان تست با راه‌های کاهش خسارتی که ساختم ادامه می‌یابد:

- **سقف در هر دوره**: `BridgeMint` در هر روز حداکثر ۱۰۰۰ می‌سازد ({{< term "rate-limiting" "rate limiting" >}}). ۲۰۰ جعلی بعدی با `RateLimited(1100e18, 1000e18)` revert می‌شود.
- **توقف**: یک guardian می‌تواند ضرب را متوقف کند و پیام جعلی با `Paused()` رد می‌شود. کلید guardian خودش هدف است.
- **آستانه‌ی بالاتر**: با ۳ از ۵، دو کلید دزدیده‌شده `NotEnoughSignatures(2, 3)` می‌گیرند. این فقط وقتی کمک می‌کند که کلیدها دست اپراتورها و ماشین‌های مستقل باشند.

مدل قوی‌تر امضاکننده‌ی مورد اعتماد را حذف می‌کند: B یک {{< term "light-client" "light client" >}} از A اجرا می‌کند و consensus زنجیره‌ی A و Merkle proof واریز را بررسی می‌کند، یا یک اثبات ZK از همین را. هیچ‌کدام را نساختم؛ تا جایی که فهمیده‌ام هزینه‌اش gas و پیچیدگی است و امنیتش به finality زنجیره‌ی مبدأ بند است.

## دام‌های رایج bridge

- روی chain id و قرارداد مبدأ و مقصد و یک nonce امضا کنید. آدرس قرارداد به‌تنهایی بین زنجیره‌ها یکتا نیست.
- پیش از امضا منتظر confirmation بمانید؛ واریزی که reorg شود یعنی توکن ضرب‌شده بدون قفل.
- امضاکننده‌ها را مرتب و یکتا بخواهید و امضای با `s` بالا را رد کنید.
- برابری قفل‌شده و ضرب‌شده را چک کنید و اگر برابر نبود هشدار بدهید.

## تمرین

1. در `BridgeLock.release` هم سقف هر انتقال بگذارید.
2. زنجیره‌ی A را بعد از امضای یک واریز با صفر confirmation دچار reorg کنید. invariant چه می‌گوید؟

## قدم بعدی

**مبانی zero-knowledge proof با Rust**: طرح‌های قوی‌تر با اثبات، امضاکننده‌ی مورد اعتماد را حذف می‌کنند.
