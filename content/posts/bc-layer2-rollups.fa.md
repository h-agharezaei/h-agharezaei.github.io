+++
date = '2026-11-29T18:00:00+03:30'
draft = false
title = 'Layer 2 و rollupها: optimistic و ZK'
description = 'rollup با Go و Solidity: یک optimistic rollup کوچک با state root از نوع Merkle، fraud proof برای جریمه‌ی sequencer دروغگو و gas اندازه‌گیری‌شده.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "solidity", "layer-2", "rollup", "foundry"]
cover = { image = "/images/covers/bc-layer2-rollups.fa.png", alt = "Layer 2 و rollupها: optimistic و ZK", hiddenInSingle = true }
+++

هر نود همه‌ی تراکنش‌ها را دوباره اجرا می‌کند و بلاک سقف gas دارد، پس ظرفیت L1 ای مثل اتریوم محدود است. [Proof of Stake، BFT و finality](/fa/posts/bc-proof-of-stake-bft/) بلاک‌ها را قطعی کرد، نه بزرگ‌تر.

{{< term "layer-2" "Layer 2" >}} اجرا را به جای دیگری می‌برد و L1 را داور نگه می‌دارد. طرح رایجش {{< term "rollup" "rollup" >}} است: اجرای تراکنش‌ها بیرون از زنجیره، و ثبت داده‌ی آن‌ها و تعهد به state حاصل در قراردادی روی L1. یک نمونه‌ی کوچک با تکه‌های قبلی ساختم: درخت از [Merkle tree و اثبات عضویت](/fa/posts/bc-merkle-trees-proofs/)، توکن از [توکن‌ها: ERC-20 و ERC-721](/fa/posts/bc-erc20-erc721/) و خواندن لاگ مثل [Event و ساخت indexer](/fa/posts/bc-event-indexer-go/).

> Go 1.27 با go-ethereum v1.17.10، Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64)، anvil روی `127.0.0.1:8550` با hardfork پیش‌فرضش. کد مثال محلی. کلیدها کلیدهای تست عمومی anvil هستند. کد Merkle بدون تغییر از دموی BC3 کپی شده. این یک **مدل آموزشی** است، نه rollup واقعی.

## rollup کوچک ما

state لایه‌ی دوم: ۸ حساب با موجودی `uint64`. هر تراکنش ۱۰ بایت است: `from`، `to` و مبلغ ۸ بایتی. تراکنش نامعتبر رد می‌شود و کل دسته revert نمی‌شود. {{< term "state-root" "state root" >}} همان Merkle root پست BC3 روی ۸ برگ `index || balance` است.

{{< term "sequencer" "sequencer" >}}، یک برنامه‌ی Go، دسته را اجرا می‌کند و در `RollupInbox` روی L1 می‌فرستد. دسته به‌صورت {{< term "calldata" "calldata" >}} می‌رود و قرارداد فقط hash آن و root ادعاشده را نگه می‌دارد:

```solidity
function appendBatch(bytes calldata txs, bytes32 stateRoot) external {
    if (msg.sender != sequencer) revert NotSequencer();
    if (slashed) revert SequencerSlashed();
    if (txs.length == 0 || txs.length % TX_SIZE != 0) revert BadLength();
    bytes32 dataHash = keccak256(txs);
    batches.push(Batch(dataHash, stateRoot, uint64(block.timestamp)));
    emit BatchAppended(batches.length - 1, stateRoot, dataHash);
}
```

اینجا root چک نمی‌شود: {{< term "optimistic-rollup" "optimistic rollup" >}} آن را درست فرض می‌کند، مگر کسی در پنجره‌ی اعتراض (اینجا یک ساعت) خلافش را ثابت کند.

## گیر انداختن sequencer دروغگو

ساده‌ترین شکل {{< term "fraud-proof" "fraud proof" >}}: معترض بایت‌های دسته و کل state قبلی را می‌فرستد؛ قرارداد هر دو را با داده‌ی ذخیره‌شده می‌سنجد، کل دسته را دوباره اجرا می‌کند و نتیجه را مقایسه می‌کند:

```solidity
if (keccak256(txs) != b.dataHash) revert WrongData();
uint64[ACCOUNTS] memory bal = pre;
if (stateRoot(bal) != prevRoot) revert WrongPreState();
execute(bal, txs);
bytes32 correct = stateRoot(bal);
if (correct == b.stateRoot) revert RootIsCorrect();
while (batches.length > i) batches.pop(); // roll back
slashed = true;
// half the bond is sent to the challenger (trimmed)
```

sequencer یک ETH وثیقه گذاشته. verifier (با Go) فقط state اولیه و L1 را می‌شناسد: لاگ‌های `BatchAppended` را می‌خواند، هر تراکنش را می‌گیرد، calldata را decode و دوباره اجرا می‌کند. `go run ./cmd/rollup run`، که در آن دسته‌ی دوم یک میلیون سکه به حساب ۷ می‌دهد:

```
RollupInbox 0x5FbDB2315678afecb367f032d93F642f64180aa3, genesis root 4c5dbac8, bond 1 ETH
sequencer: batch of 4 txs (3 valid), 40 bytes, root fb844e73, block 2, gas 116627
sequencer: next batch lies: account 7 gets 1000000 out of thin air
sequencer: batch of 2 txs (2 valid), 20 bytes, root 090abc11, block 3, gas 99330
verifier: batch 0 claimed fb844e73, re-executed fb844e73 ok
verifier: batch 1 claimed 090abc11, re-executed 0ff4589b MISMATCH -> challenge
verifier: challenge accepted, block 4, gas 134540
batchCount=1 slashed=true bond=0 
sequencer posts again: SequencerSlashed()
after +0s: batch 0 final = false
after +3600s: batch 0 final = true
```

Go و Solidity روی درخت توافق دارند، وگرنه `WrongPreState` می‌گرفتیم. در تست‌های forge اعتراض به دسته‌ی درست، اعتراض دیرهنگام و state قبلی جعلی شکست می‌خورند.

این فقط به خاطر {{< term "data-availability" "data availability" >}} کار می‌کند: اگر فقط root روی L1 بود، کسی نمی‌توانست دوباره اجرا کند.

**fraud proof واقعی فرق دارد**، تا جایی که طرح‌های منتشرشده را فهمیده‌ام (هیچ‌کدام را اجرا نکردم): کل دسته و state روی L1 مقیاس‌پذیر نیست. Arbitrum و OP Stack اجرای مورد اختلاف را تعاملی نصف می‌کنند تا اختلاف به یک دستور برسد؛ L1 فقط همان قدم را با Merkle proof برای state درگیر اجرا می‌کند.

## gas: تعداد N انتقال روی L1 در برابر یک دسته

`go run ./cmd/rollup gas` تعداد N انتقال `DemoToken` روی L1 می‌فرستد (گیرنده‌ها از قبل DEMO دارند)، بعد یک دسته با N انتقال L2. `gasUsed` از receiptها:

```
    N L1 transfers gas     per tx one batch post gas     per tx
    1            35223      35223              99306      99306
   10           352206      35220             100101      10010
  100          3522108      35221             107803       1078
  500         17610612      35221             142140        284
```

برای یک انتقال، دسته گران‌تر است چون ذخیره‌اش هزینه‌ی ثابت دارد. هر انتقال اضافه حدود ۸۶ gas می‌افزاید، بیشترش قیمت calldata (طبق مستندات اتریوم، ۱۶ gas برای هر بایت غیرصفر و ۴ برای بایت صفر). ملاحظه‌ها: تراکنش‌های L2 من امضا ندارند (هر کدام ۶۵ بایت بیشتر می‌شد)، اجرای بیرون از زنجیره حساب نشده، و تا جایی که می‌دانم rollupهای واقعی بیشتر داده‌ی فشرده را در blobهای EIP-4844 می‌فرستند؛ من calldata ساده فرستادم.

## ZK rollup

{{< term "zk-rollup" "ZK rollup" >}} با هر دسته یک {{< term "validity-proof" "validity proof" >}} می‌فرستد: اثبات اینکه root جدید واقعاً از root قبلی به دست می‌آید. L1 پیش از پذیرفتن root آن را بررسی می‌کند: پنجره‌ی اعتراض لازم نیست، ولی ساختن اثبات پرهزینه است. [مبانی zero-knowledge proof با Rust](/fa/posts/bc-zero-knowledge-rust/) یک اثبات کوچک دستی می‌سازد؛ اینجا کد ZK rollup ننوشتم.

## برداشت

خروج از rollup یعنی اثبات موجودی L2 روی L1 در برابر یک root. در optimistic rollup آن root اول باید از پنجره‌ی اعتراض عبور کند؛ تا جایی که می‌دانم، rollupهای بزرگ حدود هفت روز در نظر می‌گیرند. در ZK rollup باید منتظر اثبات بررسی‌شده‌ی بعدی بمانید.

## کجا این مدل آموزشی می‌شکند

- تراکنش‌های من امضا ندارند، پس اجرای دوباره جلوی sequencerی را که انتقال جعل کند نمی‌گیرد. rollupهای واقعی امضای کاربر را هنگام اجرا بررسی می‌کنند.
- امنیت optimistic به دست‌کم یک verifier صادق و آنلاین در هر پنجره نیاز دارد.
- یک sequencer تنها هنوز می‌تواند سانسور کند یا ترتیب را بچیند.

## تمرین

1. روی L1 تابع `deposit()` اضافه کنید و برداشتی بسازید که فقط در برابر root قطعی و با Merkle proof موجودی پرداخت کند.
2. sequencer را طوری کنید که calldata را پنهان کند (فقط root بفرستد). verifier هنوز چه کاری می‌تواند بکند؟

## قدم بعدی

**Bridge و ارتباط بین زنجیره‌ها**: L1 می‌تواند rollup را داوری کند چون داده را دارد؛ دو زنجیره‌ی مستقل نمی‌توانند.
