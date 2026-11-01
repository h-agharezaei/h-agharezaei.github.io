+++
date = '2027-07-14T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی بلاکچین با Go و Rust'
description = 'پروژه‌ی پایانی بلاکچین با Go و Rust: یک signer با Rust که seed کیف‌پول HD و سیاست امضا را نگه می‌دارد و بک‌اند Go صرافی که هیچ کلیدی نمی‌بیند.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "rust", "ethereum", "exchange", "security"]
cover = { image = "/images/covers/bc-capstone.fa.png", alt = "پروژه‌ی پایانی بلاکچین با Go و Rust", hiddenInSingle = true }
+++

در پست قبلی، [مهندسی صرافی: واریز، برداشت، confirmation و reorg](/fa/posts/bc-exchange-deposits-withdrawals/)، بک‌اند Go برداشت‌ها را با کلیدی امضا می‌کرد که داخل باینری بود. هر کس آن‌جا کد اجرا می‌کرد، هر چیزی را می‌توانست امضا کند.

این پست آخر {{< term "key-custody" "نگهداری کلید" >}} را به یک پروسه‌ی جدا می‌برد. یک **signer** کوچک با Rust همان seed پست [کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust](/fa/posts/bc-hd-wallets-rust/) را نگه می‌دارد؛ بک‌اند BC31 آدرس و امضا را از آن می‌خواهد و هیچ کلید خصوصی ندارد. این توصیه‌ی [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) است، به‌شکل کد.

> اجرا با Go 1.27 و go-ethereum v1.17.10، Rust 1.90 با `bip32` 0.5.3، `k256` 0.13.4، `sha3` و `serde_json`، Foundry 1.8.7 روی macOS (arm64). یک anvil تازه روی `127.0.0.1:8552` با توکن BC16. seed همان **test vector عمومی BIP-39** پست BC20 است و بقیه‌ی کلیدها **حساب‌های تست عمومی** anvil: هرگز به آن‌ها پول نفرستید. پروژه‌ها محلی‌اند و `demo.sh` همه‌ی اجراهای زیر را انجام می‌دهد.

## جداسازی

signer روی `127.0.0.1:9552` در هر خط یک شیء JSON می‌گیرد. gRPC پست [ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) را برای کم ماندن وابستگی‌ها کنار گذاشتم. فقط سه عمل:

```rust
#[derive(Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Address { index: u32 },     // m/44'/60'/0'/0/index, from the xpub
    HotAddress,                 // m/44'/60'/1'/0/0, a separate hardened account
    SignWithdrawal(Withdrawal), // chain id, nonce, fees, token, to, amount
}
```

آدرس‌های واریز از {{< term "xpub" "xpub" >}} حساب ساخته می‌شوند؛ {{< term "hot-wallet" "کیف‌پول داغ" >}} زیر یک حساب hardened دیگر است، همان‌طور که BC20 توصیه کرد. بی احراز هویت، signer فقط loopback را می‌پذیرد.

## سیاست کنار کلید است

`sign_withdrawal` به‌جای تراکنش *فیلدهای* برداشت را می‌گیرد، بررسی می‌کند و تراکنش {{< term "eip-1559" "EIP-1559" >}} و calldata تابع `transfer` را خودش می‌سازد (RLP دست‌نویس با k256، نه alloy پست BC18). خلاصه‌شده:

```rust
if w.chain_id != p.chain_id { return Err(format!("chain id {} is not {}", ..)); }
if parse_addr(&w.token)? != p.token { return Err(format!("token {} is not the allowed contract", ..)); }
if amount == 0 || amount > p.per_tx { return Err(..); }
// daily total: amounts signed today, rebuilt from the audit log at start;
// a fee bump with the same request id, nonce, destination and amount is not counted twice
Ok(tx::Eip1559 { to: p.token, data: tx::transfer_calldata(&to, amount), .. })
```

هر تصمیم پیش از پاسخ در یک {{< term "audit-log" "audit log" >}} نوشته و sync می‌شود. در Go، `send` هنوز nonce را از Postgres برمی‌دارد و جواب signer را بررسی می‌کند (فرستنده، nonce، قرارداد، calldata). رد شدن یعنی nonce برمی‌گردد و مبلغ رزروشده آزاد می‌شود:

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

`X` یعنی `exchange -pgdir <tmp>/pg`. signer بالا می‌آید و حساب ۰ anvil به کیف‌پول داغش ۱ ETH و ۵۰۰ DEMO می‌دهد:

```
[signer] listening on 127.0.0.1:9552, hot wallet 0x7aBb15A014B82491c56E7fA27C88314Fc303B471, chain 31337, token 0x5FbDB2315678afecb367f032d93F642f64180aa3, per tx 100 DEMO, per day 100 DEMO, 0 signed request(s) in the audit log
$ X user -name alice
user alice created: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
$ X user -name bob
user bob created: index 1, deposit address 0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353
$ X user -name alice
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
```

هر {{< term "deposit-address" "آدرس واریز" >}} همان `m/44'/60'/0'/0/0` یا `/1` پست BC20 است و تکرار درخواست چیزی را عوض نمی‌کند. بعد ۱۵۰ DEMO به alice و سه confirmation:

```
deposit alice 150 DEMO tx 0x5577c442 block 6: seen
deposit alice 150 DEMO: seen -> pending (1/3)
deposit alice 150 DEMO: pending -> credited (3/3), journal posted: true
(scan headers trimmed)
```

برداشت ۶۰ DEMO، امضا با Rust، پذیرفته در anvil:

```
withdrawal #1 created: reserved
withdrawal #1 signed by the signer: nonce 0, tx 0x0cfadb0b
withdrawal #1 sent: 0x0cfadb0b
withdrawal #1: confirmed via 0x0cfadb0b (3/3)
A3 DEMO: 60000000000000000000 [6e19]
```

## رد شدن‌ها

سقف بک‌اند ۱۰۰ DEMO برای هر درخواست است، پس ۵۰ دیگر را رزرو می‌کند. سقف روزانه‌ی signer رد می‌کند:

```
withdrawal #2 created: reserved
withdrawal #2 refused by the signer: daily limit: 60 + 50 DEMO > 100
user:alice           90 DEMO
withdrawals:pending  0 DEMO
(other balance lines trimmed)
```

فرض کنید بک‌اند نفوذشده است: `probe` درخواست دست‌ساز را مستقیم به socket می‌فرستد:

```
signer refused: chain id 1 is not 31337
signer refused: token 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512 is not the allowed contract
signer refused: amount 500 DEMO over the per-tx limit 100
{"error":"bad request: unknown variant `export_seed`, expected one of `address`, `hot_address`, `sign_withdrawal` at line 1 column 19"}
```

هیچ عملی کلید برنمی‌گرداند یا hash خام امضا نمی‌کند. نکته‌ی {{< term "blast-radius" "blast radius" >}} همین است: بک‌اند دزدیده‌شده در محدوده‌ی سیاست برداشت می‌کند، ولی کیف‌پول را خالی نمی‌کند. در [Bridge و ارتباط بین زنجیره‌ها](/fa/posts/bc-bridges-cross-chain/) دو کلید relayer دزدیده‌شده توکن بی‌پشتوانه mint کردند و [امنیت قرارداد](/fa/posts/bc-contract-security/) لو رفتن کلید را دسته‌ی جدایی از حادثه‌ها می‌داند؛ یک {{< term "signing-service" "سرویس امضای" >}} باریک جلوی هیچ‌کدام را نمی‌گیرد، ولی اثر یک نفوذ را محدود می‌کند.

## ری‌استارت هر دو

signer را ری‌استارت و قدم‌های بک‌اند را تکرار کردم:

```
[signer] ... per day 100 DEMO, 1 signed request(s) in the audit log
user alice exists: index 0, deposit address 0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655
head 11, cursor 0, N 3
withdrawal #1 already exists: confirmed
nothing to send
withdrawal #4 signed by the signer: nonce 1, tx 0xd86af807
withdrawal #5 refused by the signer: daily limit: 100 + 10 DEMO > 100
withdrawal #4: confirmed via 0xd86af807 (3/3)
user:alice           50 DEMO
sum of all accounts: 0
hot wallet nonce: 2
(signer line shortened, other lines trimmed)
```

اسکن دوباره چیزی را دو بار به حساب نگذاشت، {{< term "idempotency-key" "کلید idempotency" >}} برداشت قبلی را برگرداند و سقف روزانه ماند. با `--seed random` seed فقط در حافظه است و دو اجرا برای index 0 دو آدرس متفاوت دادند؛ کار واقعی seed ذخیره‌شده می‌خواهد.

## نسخه‌ی واقعی چه دارد

تا جایی که می‌دانم، بدون اشاره به محصولی: کلید در {{< term "hsm" "HSM" >}} یا تقسیم‌شده با {{< term "mpc" "MPC" >}}، نه در حافظه‌ی پروسه؛ ارتباط احراز هویت‌شده؛ تأیید انسانی بالای یک سقف، بررسی‌شده توسط signer؛ audit log بیرون از همان ماشین؛ فهرست مقصدهای مجاز و تأخیر.

## چند نکته‌ی مهم

- سقف مهم سقف signer است؛ بررسی‌های بک‌اند برای کاربرند، نه مهاجم.
- عمل «این بایت‌ها را امضا کن» نگذارید؛ تراکنش را signer می‌سازد.
- وضعیت سیاست باید بعد از ری‌استارت بماند.
- فراخواننده هم جواب را بررسی می‌کند.

## تمرین

۱. عمل `sign_sweep(index)` را اضافه کنید که فقط به کیف‌پول داغ بفرستد.
۲. بگذارید Go آدرس‌های واریز را از یک xpub صادرشده بسازد و با signer مقایسه کند.
۳. برای بالای ۵۰ DEMO امضای یک تأییدکننده را لازم کنید.

## کل دوره در یک جدول

| بخش | پست‌ها | چه ساختیم |
|---|---|---|
| [مبانی](/fa/posts/bc-blockchain-for-programmers/) | BC1-BC12 | یک full node شبیه بیت‌کوین با Go و مفسر Script با Rust |
| [اتریوم](/fa/posts/bc-evm-internals-rust/) | BC13-BC20 | مفسر EVM، قرارداد با Foundry، کلاینت Go و Rust، indexer، کیف‌پول HD |
| [DeFi و امنیت](/fa/posts/bc-amm-constant-product/) | BC21-BC26 | AMM، وام‌دهی، oracle، حمله و رفع، proxy، MEV |
| [پیشرفته](/fa/posts/bc-proof-of-stake-bft/) | BC27-BC32 | BFT، rollup، bridge، ZK، بک‌اند صرافی و همین signer |

## از این‌جا به بعد

منابع رسمی: [مستندات توسعه‌دهنده‌ی ethereum.org](https://ethereum.org/en/developers/docs/)، [مستندات توسعه‌دهنده‌ی بیت‌کوین](https://developer.bitcoin.org/)، [مستندات Solidity](https://docs.soliditylang.org/) و [کتاب Foundry](https://book.getfoundry.sh/).

سری همین‌جا تمام می‌شود. ممنون که خواندید؛ من هم در نوشتنش خیلی یاد گرفتم.
