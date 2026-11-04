+++
date = '2026-12-03T18:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی بلاکچین با Go و Rust'
description = 'پروژه‌ی پایانی بلاکچین با Go و Rust: یک signer با Rust که seed کیف‌پول HD و سیاست امضا را نگه می‌دارد و بک‌اند Go صرافی که هیچ کلیدی نمی‌بیند.'
contentType = 'engineering'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "rust", "ethereum", "exchange", "security"]
cover = { image = "/images/covers/bc-capstone.fa.png", alt = "پروژه‌ی پایانی بلاکچین با Go و Rust", hiddenInSingle = true }
+++

بک‌اند Go در [مهندسی صرافی: واریز، برداشت، confirmation و reorg](/fa/posts/bc-exchange-deposits-withdrawals/) واریزها را اسکن می‌کند، دفتر حساب را نگه می‌دارد و برداشت‌ها را هم خودش امضا می‌کند، با کلیدی که داخل باینری است. یعنی هر کس بتواند داخل همین برنامه کد اجرا کند، هر چیزی را می‌تواند امضا کند: یک باگ، یک وابستگی آلوده، یک سرور نفوذشده. کلید و منطق برنامه در یک پروسه‌اند، پس هر که برنامه را در دست بگیرد کلید را هم گرفته.

فکرش را بکنید یک صندوق‌دار هم کلید گاوصندوق را دارد و هم دفتر حساب را. هر کس صندوق‌دار را گول بزند، گاوصندوق را خالی می‌کند. راه حل قدیمی این است که کلید را به آدم دیگری بدهیم، کسی که فقط یک کار بلد است: درخواست را با قواعد خودش مقایسه کند و فقط اگر مجاز بود امضا بزند. صندوق‌دار می‌تواند درخواست بدهد، ولی کلید را هرگز نمی‌بیند.

این مقاله‌ی آخر همین کار را می‌کند: {{< term "key-custody" "نگهداری کلید" >}} را به یک پروسه‌ی جدا می‌برد. یک **signer** کوچک با Rust همان seed مقاله‌ی [کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust](/fa/posts/bc-hd-wallets-rust/) را نگه می‌دارد. بک‌اندِ مقاله‌ی قبل از signer آدرس و امضا می‌خواهد و خودش هیچ کلید خصوصی ندارد. این توصیه‌ی [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) است، به‌شکل کد.

> اجرا با Go 1.27 و go-ethereum v1.17.10، Rust 1.90 با `bip32` 0.5.3، `k256` 0.13.4، `sha3` و `serde_json`، Foundry 1.8.7 روی macOS (arm64). یک anvil تازه روی `127.0.0.1:8552` با توکن مقاله‌ی توکن‌ها. seed همان **test vector عمومی BIP-39** مقاله‌ی کیف‌پول HD است و بقیه‌ی کلیدها **حساب‌های تست عمومی** anvil: هرگز به آن‌ها پول نفرستید. پروژه‌ها محلی‌اند و یک اسکریپت `demo.sh` همه‌ی اجراهای زیر را یک‌جا انجام می‌دهد.

## جداسازی

signer با بک‌اند روی `127.0.0.1:9552` حرف می‌زند. هر پیام یک خط است که یک شیء JSON دارد. gRPC مقاله‌ی [ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) را برای کم ماندن وابستگی‌ها کنار گذاشتم. signer فقط سه کار بلد است و هیچ کار دیگری ندارد:

```rust
#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Address { index: u32 },     // m/44'/60'/0'/0/index, from the xpub
    HotAddress,                 // m/44'/60'/1'/0/0, a separate hardened account
    SignWithdrawal(Withdrawal), // chain id, nonce, fees, token, to, amount
}
```

سه عمل: آدرس واریز برای یک شماره‌ی کاربر، آدرس کیف‌پول داغ، و امضای یک برداشت. هیچ عملی «کلید را بده» یا «این بایت‌ها را امضا کن» نیست. آدرس‌های واریز از {{< term "xpub" "xpub" >}} حساب ساخته می‌شوند (کلید عمومی گسترش‌یافته، که فقط آدرس می‌سازد و امضا نمی‌کند). {{< term "hot-wallet" "کیف‌پول داغ" >}} زیر یک حساب hardened دیگر است (از xpub حساب واریز نمی‌شود آن را ساخت)، همان‌طور که مقاله‌ی کیف‌پول HD توصیه کرد. چون هیچ احراز هویتی در کار نیست، signer فقط روی loopback گوش می‌دهد و آدرس دیگری را قبول نمی‌کند.

## سیاست کنار کلید است

نکته‌ی اصلی این طراحی در `sign_withdrawal` است. این عمل به‌جای یک تراکنش آماده، فقط *فیلدهای* برداشت را می‌گیرد: chain id، nonce، کارمزدها، توکن، مقصد و مبلغ. signer فیلدها را بررسی می‌کند و بعد تراکنش {{< term "eip-1559" "EIP-1559" >}} و calldata تابع `transfer` را خودش می‌سازد (RLP را با k256 دستی نوشتم، نه با alloy مقاله‌ی کلاینت Rust). بنابراین بک‌اندِ نفوذشده نمی‌تواند تراکنش دلخواه بدهد، چون تراکنش را signer می‌سازد. خلاصه‌شده:

```rust
if w.chain_id != p.chain_id { return Err(format!("chain id {} is not {}", ..)); }
if parse_addr(&w.token)? != p.token { return Err(format!("token {} is not the allowed contract", ..)); }
if amount == 0 || amount > p.per_tx { return Err(..); }
// daily total: amounts signed today, rebuilt from the audit log at start;
// a fee bump with the same request id, nonce, destination and amount is not counted twice
Ok(tx::Eip1559 { to: p.token, data: tx::transfer_calldata(&to, amount), .. })
```

سه شرط اول: زنجیره درست باشد، توکن همان قرارداد مجاز باشد، و مبلغ از صفر بیشتر و از سقف هر تراکنش کمتر باشد. بعد سقف روزانه هم هست. مجموع مبلغ‌های امضاشده‌ی امروز از روی audit log هنگام شروع بازسازی می‌شود، و اگر کارمزد یک تراکنش بالا برود (با همان شناسه‌ی درخواست، nonce، مقصد و مبلغ) دوبار حساب نمی‌شود. «امروز» یعنی روز بر پایه‌ی زمان یونیکس (UTC).

هر تصمیم، چه امضا چه رد، پیش از پاسخ در یک {{< term "audit-log" "audit log" >}} نوشته و روی دیسک sync می‌شود. در Go هم دو چیز عوض می‌شود. `send` هنوز nonce را از Postgres برمی‌دارد و جواب signer را بررسی می‌کند (فرستنده، nonce، قرارداد و calldata را). و اگر signer رد کند، nonce برمی‌گردد و مبلغ رزروشده آزاد می‌شود:

```go
var refused errRefused
if errors.As(err, &refused) {
	tx.Rollback(ctx) // the nonce was not used
	if err := ex.release(ctx, id, refused.reason); err != nil {
		return err
	}
	fmt.Printf("withdrawal #%d refused by the signer: %s\n", id, refused.reason)
	continue
}
```

## از اول تا آخر

حالا همه را با هم اجرا می‌کنیم. `X` یعنی `exchange -pgdir <tmp>/pg`. اول signer بالا می‌آید، و حساب شماره‌ی ۰ anvil به کیف‌پول داغ آن ۱ ETH (برای gas) و ۵۰۰ DEMO می‌دهد:

```
[signer] listening on 127.0.0.1:9552, hot wallet 0x7aBb15A014B82491c56E7fA27C88314Fc303B471, chain 31337, token 0x5FbDB2315678afecb367f032d93F642f64180aa3, per tx 100 DEMO, per day 100 DEMO, 0 signed request(s) in the audit log
$ X user -name alice
user alice created: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
$ X user -name bob
user bob created: index 1, deposit address 0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353
$ X user -name alice
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
```

خط اول را signer چاپ می‌کند. می‌گوید روی کدام آدرس گوش می‌دهد، آدرس کیف‌پول داغ چیست، روی کدام زنجیره و با کدام توکن کار می‌کند، و سقف‌ها: ۱۰۰ DEMO برای هر تراکنش و ۱۰۰ DEMO در روز. `0 signed request(s)` یعنی audit log هنوز خالی است.

سه خط بعد کاربران را می‌سازند. هر کاربر شماره‌ی بعدی را می‌گیرد و آدرس واریزش را از signer می‌پرسد. alice شماره‌ی ۰ است و bob شماره‌ی ۱. هر {{< term "deposit-address" "آدرس واریز" >}} همان `m/44'/60'/0'/0/0` یا `/1` مقاله‌ی کیف‌پول HD است. درخواست دوباره‌ی alice چیزی را عوض نمی‌کند: همان کاربر با همان آدرس.

بعد ۱۵۰ DEMO به alice واریز می‌شود و بک‌اند سه تأیید صبر می‌کند. (بلاک ۶ است چون بلاک‌های ۱ تا ۳ مال deploy و بلاک‌های ۴ و ۵ مال فرستادن ETH و DEMO به کیف‌پول داغ بودند.)

```
head 6, cursor -1, N 3
deposit alice 150 DEMO tx 0x5577c442 block 6: seen
deposit alice 150 DEMO: seen -> pending (1/3)
head 8, cursor 6, N 3
deposit alice 150 DEMO: pending -> credited (3/3), journal posted: true
```

اسکن اول واریز را می‌بیند و `pending (1/3)` می‌کند. دو بلاک می‌سازیم. اسکن دوم `3/3` می‌بیند و واریز را به حساب می‌گذارد. همان ماشین حالتی است که در مقاله‌ی قبل دیدیم.

حالا برداشت ۶۰ DEMO. بک‌اند رزرو می‌کند، signer امضا می‌کند، anvil می‌پذیرد:

```
withdrawal #1 created: reserved
withdrawal #1 signed by the signer: nonce 0, tx 0x0cfadb0b
withdrawal #1 sent: 0x0cfadb0b
withdrawal #1: confirmed via 0x0cfadb0b (3/3)
A3 DEMO: 60000000000000000000 [6e19]
```

خط آخر موجودی توکن حساب مقصد (`A3`) را روی خود زنجیره می‌خواند: ۶۰ DEMO، که با ۱۸ رقم اعشار به شکل `6e19` نوشته می‌شود. یعنی برداشت واقعاً انجام شد.

## رد شدن‌ها

حالا برداشت ۵۰ DEMO دیگر. سقف بک‌اند ۱۰۰ DEMO برای هر درخواست است، پس آن را رزرو می‌کند. ولی signer امروز ۶۰ امضا کرده و ۶۰ + ۵۰ از سقف روزانه‌ی ۱۰۰ بیشتر است:

```
withdrawal #2 created: reserved
withdrawal #2 refused by the signer: daily limit: 60 + 50 DEMO > 100
nothing to send
external             -90 DEMO
user:alice           90 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
```

signer رد کرد، nonce برگشت و مبلغ رزروشده آزاد شد: `withdrawals:pending` دوباره صفر است و alice ۹۰ دارد (۱۵۰ منهای ۶۰). `nothing to send` یعنی چیزی برای ارسال نمانده. جمع دفتر هنوز صفر است.

حالا فرض کنید بک‌اند نفوذ شده است و مهاجم به‌جای بک‌اند، مستقیم با signer حرف می‌زند. دستور `probe` درخواست‌های دست‌ساز را مستقیم به socket می‌فرستد:

```
signer refused: chain id 1 is not 31337
signer refused: token 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512 is not the allowed contract
signer refused: amount 500 DEMO over the per-tx limit 100
{"error":"bad request: unknown variant `export_seed`, expected one of `address`, `hot_address`, `sign_withdrawal` at line 1 column 19"}
```

سه خط اول سه درخواست جعلی‌اند: زنجیره‌ی دیگر (chain id 1)، قرارداد دیگر (آدرس NFT به‌جای توکن) و مبلغ ۵۰۰ که از سقف ۱۰۰ بیشتر است. هر سه رد شدند. خط آخر پیامی است که با `nc` فرستادم: `{"op":"export_seed"}`، یعنی «seed را بده». عمل ناشناخته است و نتیجه یک خطای ساده است، چون چنین عملی در `Request` وجود ندارد.

هیچ عملی کلید برنمی‌گرداند یا hash خام را امضا نمی‌کند. نکته‌ی {{< term "blast-radius" "blast radius" >}} (شعاع انفجار) همین است: بک‌اندِ دزدیده‌شده هنوز می‌تواند در محدوده‌ی سیاست برداشت کند، ولی نمی‌تواند کیف‌پول را خالی کند. در [Bridge و ارتباط بین زنجیره‌ها](/fa/posts/bc-bridges-cross-chain/) دو کلید relayer دزدیده‌شده توکن بی‌پشتوانه mint کردند، و [امنیت قرارداد](/fa/posts/bc-contract-security/) لو رفتن کلید را دسته‌ی جدایی از حادثه‌ها می‌داند. یک {{< term "signing-service" "سرویس امضای" >}} باریک جلوی هیچ‌کدام را نمی‌گیرد، ولی اثر یک نفوذ را محدود می‌کند.

## ری‌استارت هر دو

یک سؤال مهم مانده: اگر پروسه‌ها خاموش و روشن شوند چه؟ وضعیت سیاست، مثل مجموع امروز، باید بماند. signer را ری‌استارت کردم و قدم‌های بک‌اند را تکرار کردم. (بک‌اند را هم با `-rewind 0` از بلاک صفر دوباره اسکن کردم.)

```
[signer] ... per day 100 DEMO, 1 signed request(s) in the audit log
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
head 11, cursor 0, N 3
withdrawal #1 already exists: confirmed
nothing to send
withdrawal #4 created: reserved
withdrawal #5 created: reserved
withdrawal #4 signed by the signer: nonce 1, tx 0xd86af807
withdrawal #5 refused by the signer: daily limit: 100 + 10 DEMO > 100
withdrawal #4 sent: 0xd86af807
withdrawal #4: confirmed via 0xd86af807 (3/3)
external             -50 DEMO
user:alice           50 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
hot wallet nonce: 2
(signer line shortened)
```

خط‌به‌خط:

- **خط اول:** signer بالا آمد و در audit log یک درخواست امضاشده یافت (همان ۶۰ DEMO). مجموع امروز را از روی آن بازسازی کرد.
- **آدرس alice:** همان آدرس قبلی است، چون seed ثابت است.
- **`head 11, cursor 0`:** اسکن از بلاک صفر شروع شد. واریز ۱۵۰ DEMO دوباره دیده شد ولی هیچ خط واریزی چاپ نشد و چیزی دوباره به حساب نرفت.
- **`#1 already exists: confirmed`:** همان درخواست `w-1` با همان کلید idempotency، برداشت قبلی را برگرداند، نه برداشت تازه. `nothing to send` هم یعنی چیزی نمانده.
- **`#4` و `#5`:** دو برداشت تازه، ۴۰ و ۱۰ DEMO. هر دو رزرو شدند.
- **`#4 signed`:** ۶۰ (از پیش) + ۴۰ می‌شود ۱۰۰ و از سقف روزانه نمی‌گذرد. امضا شد، با nonce ۱. این nonce هنوز مصرف نشده بود، چون برداشت #2 رد شد و nonceش برگشت.
- **`#5 refused`:** ۱۰۰ + ۱۰ بیشتر از سقف می‌شود. رد شد و رزروش آزاد شد. سقف روزانه بعد از ری‌استارت هم ماند.
- **خطوط آخر:** alice ۵۰ دارد (۱۵۰ منهای ۶۰ منهای ۴۰)، جمع دفتر صفر است و nonce کیف‌پول داغ ۲ است: دو تراکنش واقعاً رفته.

نتیجه: اسکن دوباره (`-rewind 0`) چیزی را دو بار به حساب نگذاشت، {{< term "idempotency-key" "کلید idempotency" >}} برداشت قبلی را برگرداند، و سقف روزانه بعد از ری‌استارت ماند.

با `--seed random` ماجرا فرق دارد: seed فقط در حافظه‌ی پروسه است، پس هر بار که signer بالا بیاید seed و آدرس‌ها عوض می‌شوند. دو بار با `--seed random` بالا آوردم و کیف‌پول داغ دو آدرس متفاوت گرفت. کار واقعی seed ذخیره‌شده می‌خواهد.

audit log هم بعد از کل اجرا هفت تصمیم دارد: دو امضا (برداشت‌های ۱ و ۴) و پنج رد (برداشت ۲، سه درخواست `probe` و برداشت ۵). رد شدن‌ها هم ثبت می‌شوند.

## نسخه‌ی واقعی چه دارد

تا جایی که می‌دانم، بدون اشاره به محصولی خاص: کلید در {{< term "hsm" "HSM" >}} یا تقسیم‌شده با {{< term "mpc" "MPC" >}}، نه در حافظه‌ی پروسه؛ ارتباط احراز هویت‌شده؛ تأیید انسانی بالای یک سقف که خود signer بررسی کند؛ audit log بیرون از همان ماشین؛ فهرست مقصدهای مجاز و تأخیر.

## قاعده‌های طراحی signer

- سقفی که مهم است سقف signer است. بررسی‌های بک‌اند برای کاربرند، نه برای مهاجم.
- عمل «این بایت‌ها را امضا کن» نگذارید. تراکنش را signer می‌سازد.
- وضعیت سیاست باید بعد از ری‌استارت بماند.
- فراخواننده هم جواب signer را بررسی می‌کند.

## کل دوره در یک جدول

اگر از ابتدا مقاله‌ها را دنبال کرده‌اید، این جدول خلاصه‌ی راه است. هر ردیف یک بخش است، با شماره‌ی مقاله‌ها و چیزی که در آن ساختیم:

| بخش | مقاله‌ها | چه ساختیم |
|---|---|---|
| [مبانی](/fa/posts/bc-blockchain-for-programmers/) | ۱ تا ۱۲ | یک full node شبیه بیت‌کوین با Go و مفسر Script با Rust |
| [اتریوم](/fa/posts/bc-evm-internals-rust/) | ۱۳ تا ۲۰ | مفسر EVM، قرارداد با Foundry، کلاینت Go و Rust، indexer، کیف‌پول HD |
| [DeFi و امنیت](/fa/posts/bc-amm-constant-product/) | ۲۱ تا ۲۶ | AMM، وام‌دهی، oracle، حمله و رفع، proxy، MEV |
| [پیشرفته](/fa/posts/bc-proof-of-stake-bft/) | ۲۷ تا ۳۲ | BFT، rollup، bridge، ZK، بک‌اند صرافی و همین signer |

چند چیز از مقاله‌های قبل در همین signer دوباره آمدند: کلیدها و امضای ECDSA، آدرس‌های HD، تراکنش‌های EIP-1559 و nonce، دفتر حساب و تأییدها از مقاله‌ی صرافی، و درس کلید دزدیده‌شده از bridge.

## از این‌جا به بعد

منابع رسمی: [مستندات توسعه‌دهنده‌ی ethereum.org](https://ethereum.org/en/developers/docs/)، [مستندات توسعه‌دهنده‌ی بیت‌کوین](https://developer.bitcoin.org/)، [مستندات Solidity](https://docs.soliditylang.org/) و [کتاب Foundry](https://book.getfoundry.sh/).

سری همین‌جا تمام می‌شود. ممنون که خواندید؛ من هم در نوشتنش خیلی یاد گرفتم.
