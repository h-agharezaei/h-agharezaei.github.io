+++
date = '2026-11-19T18:00:00+03:30'
draft = false
title = 'کار با اتریوم از Rust با alloy'
description = 'alloy در Rust: provider و کیف‌پول، ارسال EIP-1559 با رسید، فراخوانی توکن با ماکروی sol!، decode خطای سفارشی به enum و دنبال کردن رویداد Transfer.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "ethereum", "alloy", "erc20"]
cover = { image = "/images/covers/bc-rust-alloy-client.fa.png", alt = "کار با اتریوم از Rust با alloy", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/bc-go-ethereum-client/) با Go به یک نود anvil وصل شدیم: موجودی خواندیم، ETH فرستادیم، توکن را صدا زدیم و یک خطای سفارشی را decode کردیم. حالا یک سؤال ساده دارم: اگر همین کارها را از Rust بکنم، چه چیزی فرق می‌کند؟ فقط سینتکس، یا خود کتابخانه هم جور دیگری فکر می‌کند؟

اولین نشانه‌ی تفاوت همان‌جا پیدا شد که تراکنش را فرستادم. از Go که ETH فرستادم، go-ethereum برای tip عدد ۱ gwei را پیشنهاد کرد. از Rust با {{< term "alloy" "alloy" >}} که فرستادم، tip شد فقط ۱ {{< term "wei" "wei" >}}. هر دو درست کار می‌کنند، ولی هر کتابخانه پیش‌فرض خودش را دارد. در این مقاله همان قدم‌های مقاله‌ی Go را با Rust برمی‌داریم و هر جا چیزی فرق کرد، می‌بینیم از کجا آمده.

قرارداد توکن همان است که در [مقاله‌ی توکن‌ها](/fa/posts/bc-erc20-erc721/) ساختیم. کد async است و روی tokio اجرا می‌شود، مثل [مقاله‌ی Tokio](/fa/posts/rust-async-tokio/). بخش جالب مقاله هم از یک procedural macro می‌آید، از همان جنس [ماکروهای Rust](/fa/posts/rust-macros/).

> اجرا با Rust 1.90 روی macOS (arm64)، `alloy` 1.6.3 (featureهای پیش‌فرض خاموش؛ `std`، `reqwest`، `provider-http`، `signer-local`، `contract`، `rpc-types`)، `tokio` 1.54.1، `futures-util` 0.3 و Foundry 1.8.7. نسخه‌ی 1.6.3 را انتخاب کردم چون نسخه‌های جدیدتر alloy به Rust جدیدتر از 1.90 نیاز دارند. یک anvil تازه روی `127.0.0.1:8545` با اسکریپت deploy مقاله‌ی توکن‌ها. کلیدهای داخل کد کلیدهای آزمایشی عمومی anvil هستند: هیچ‌جای واقعی از آن‌ها استفاده نکنید. کد یک پروژه‌ی Cargo محلی است.

## Provider، chain ID و موجودی

ساده‌ترین کار اول: وصل شدن به نود و خواندن موجودی. در alloy برای این کار یک `Provider` داریم. Provider چیزی است که API نود، یعنی همان {{< term "json-rpc" "JSON-RPC" >}} روی HTTP، را به متدهای Rust تبدیل می‌کند. جایش در برنامه همان جای `ethclient` در Go است.

```rust
let provider = ProviderBuilder::new().connect_http(RPC.parse()?);
let addr0 = KEY0.parse::<PrivateKeySigner>()?.address();
let bal = provider.get_balance(addr0).await?; // U256, in wei
println!("chain id:     {}", provider.get_chain_id().await?);
println!("balance ETH:  {}", format_units(bal, "ether")?);
```

`ProviderBuilder` را مثل سازنده‌ای قدم‌به‌قدم بخوانید: می‌گویید به کجا وصل شود (`connect_http`) و، همان‌طور که در بخش بعد می‌بینیم، می‌توانید چیزهای دیگری هم به آن اضافه کنید. خط دوم از روی کلید خصوصی، آدرس حساب ۰ را می‌سازد. بقیه فقط دو پرسش از نود است. خروجی `alloydemo info`:

```
$ ./target/debug/alloydemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

این‌ها همان عددهای اجرای Go هستند، چون هر دو به یک deploy وصل شده‌اند: شبکه‌ی ۳۱۳۳۷ (پیش‌فرض anvil)، سه بلاک که اسکریپت deploy ساخته، و موجودی کمی کمتر از ۱۰٬۰۰۰ ETH چون حساب ۰ برای آن سه تراکنش gas داده است.

یک تفاوت کوچک هست. موجودی به wei از نوع `U256` است، یعنی عدد صحیح ۲۵۶ بیتی با اندازه‌ی ثابت. در Go برای همین کار `*big.Int` داشتیم که اندازه‌اش دلخواه است. تابع `format_units` هم که wei را به ETH با ممیز تبدیل می‌کند همراه خود alloy می‌آید و لازم نیست مثل Go خودم بنویسمش.

## کیف‌پول و ارسال تراکنش EIP-1559

برای فرستادن تراکنش، provider باید بتواند امضا کند. در alloy این یعنی یک امضاکننده را به builder بدهید:

```rust
let signer: PrivateKeySigner = KEY0.parse()?;
let provider = ProviderBuilder::new().wallet(signer).connect_http(RPC.parse()?);
let value = U256::from(1_500_000_000_000_000_000u128); // 1.5 ETH
let tx = TransactionRequest::default().with_to(ACCT1).with_value(value);
let rcpt = provider.send_transaction(tx).await?.get_receipt().await?;
```

به آنچه ننوشته‌ام دقت کنید. فقط گیرنده و مقدار را گفته‌ام. نه nonce، نه سقف gas، نه کارمزد، نه chain ID. اینها را چند «filler» پیش‌فرض builder پر می‌کنند: هر کدام یک فیلد خالی تراکنش را قبل از امضا از نود می‌پرسد و پر می‌کند. `send_transaction` تراکنش را می‌فرستد و `get_receipt` صبر می‌کند تا در بلاک بنشیند و رسید را بدهد. خروجی `alloydemo send`:

```
$ ./target/debug/alloydemo send
tx type: 2 hash: 0xa0306b3e8c9b5ef2886dc4d96111769d11e473ff92a28ac0d09d701e9cb3c58b
status: true block: 4 gas used: 21000 effective gas price: 685976108
account 1 gained: 1.500000000000000000 ETH
```

- **`tx type: 2`:** تراکنش از نوع {{< term "eip-1559" "EIP-1559" >}} است. fillerها خودشان همین نوع را انتخاب کردند.
- **`status: true`، `block: 4`:** موفق بود و در بلاک ۴ نشست.
- **`gas used: 21000`:** هزینه‌ی ثابت یک انتقال ساده‌ی ETH، همان عدد Go.
- **`effective gas price`:** آنچه واقعاً به‌ازای هر gas پرداخت شد. برابر است با base fee بلاک ۴ (۶۸۵۹۷۶۱۰۷، همان که در مقاله‌ی Go با `cast` دیدیم) به‌علاوه‌ی tip برابر ۱ wei.
- **خط آخر:** حساب ۱ دقیقاً ۱٫۵ ETH گرفت.

حالا برگردیم به tip. با `cast tx` دیدم fillerها چه انتخاب کرده‌اند: `maxFeePerGas` برابر ۱۵۶۶۸۴۲۳۳۱ است، یعنی دو برابر base fee بلاک ۳ (۷۸۳۴۲۱۱۶۵) به‌علاوه‌ی tip برابر **۱ wei**. چرا ۱ wei و نه ۱ gwei؟ در Go، `SuggestGasTipCap` از نود پرسید (`eth_maxPriorityFeePerGas`) و جواب ۱ gwei بود. اما برآوردگر alloy در نسخه‌ی 1.6.3 (کدش را خواندم) از نود نمی‌پرسد؛ میانه‌ی tipها را در ۱۰ بلاک آخر از `eth_feeHistory` برمی‌دارد. تراکنش‌های deploy هم فقط ۱ wei tip داده بودند، پس همان شد. روی anvil فرقی نمی‌کند، ولی روی شبکه‌ی واقعی همین پیش‌فرض است که تعیین می‌کند تراکنشتان چقدر زود وارد بلاک شود.

## ماکروی sol! به‌جای abigen

برای صدا زدن قرارداد، برنامه باید توابع آن را بشناسد: اسم‌ها، نوع آرگومان‌ها و نوع خروجی‌ها. این توصیف همان {{< term "contract-abi" "ABI" >}} است. در Go، ABI را از خروجی Foundry برداشتم و abigen را اجرا کردم، و abigen یک فایل `token.go` با ۶۴۸ خط در مخزن نوشت که باید هر بار قرارداد عوض شد دوباره ساخته شود.

در Rust راه دیگری هست: {{< term "sol-macro" "ماکروی sol!" >}}. شما تعریف قرارداد را به همان زبان Solidity داخل خود کد Rust می‌نویسید و ماکرو موقع کامپایل از آن کد Rust می‌سازد. فایل تولیدشده‌ای در مخزن نمی‌ماند.

```rust
sol! {
    #[sol(rpc)]
    contract DemoToken {
        event Transfer(address indexed from, address indexed to, uint256 value);

        error InsufficientBalance(address from, uint256 balance, uint256 needed);
        error InsufficientAllowance(address spender, uint256 allowance, uint256 needed);
        error ZeroAddress();
        error NotMinter();

        function decimals() external view returns (uint8);
        function balanceOf(address owner) external view returns (uint256);
        function transfer(address to, uint256 value) external returns (bool);
    }
}
```

اینجا فقط همان چیزهایی را نوشته‌ام که در این مقاله لازم دارم: یک event، چهار خطای سفارشی و سه تابع. نشانه‌ی `#[sol(rpc)]` به ماکرو می‌گوید علاوه بر نوع‌ها، متدهایی هم بسازد که از طریق provider قرارداد را صدا بزنند.

فایده‌ی اصلی این است که آرگومان‌ها نوع دارند. برای دیدنش در `examples/wrong_type.rs` عمداً یک فراخوانی غلط نوشتم: آدرس را به‌صورت رشته داده‌ام و مقدار را به‌صورت عدد معمولی. کامپایلر قبول نمی‌کند:

```
$ cargo build -q --example wrong_type
error[E0308]: arguments to this method are incorrect
  --> examples/wrong_type.rs:14:23
   |
14 |     let _call = token.transfer("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", 100);
   |                       ^^^^^^^^ -------------------------------------------- expected `Address`, found `&str`
... (trimmed)
   = note: expected struct `alloy::alloy_primitives::Uint<256, 4>`
                found type `{integer}`
```

دو خطای نوع می‌بینید: به‌جای `Address` یک `&str` داده‌ام، و به‌جای `U256` یک عدد معمولی. این اشتباه قبل از اجرای برنامه گرفته می‌شود و کدش اصلاً کامپایل نمی‌شود. (خروجی کامپایلر را کوتاه کرده‌ام.)

روی دیگر سکه: این رابط را من با دست نوشتم و ممکن است با قرارداد deployشده فرق کند. `sol!` می‌تواند ABI را به‌صورت JSON از پوشه‌ی `out/` هم بخواند؛ امتحانش نکردم.

## فراخوانی و ارسال

با این رابط، صدا زدن قرارداد شبیه صدا زدن یک تابع معمولی است:

```rust
let token = DemoToken::new(TOKEN, &provider);
let dec = token.decimals().call().await?;   // u8
let b0 = token.balanceOf(me).call().await?; // U256
let rcpt = token.transfer(ACCT1, amount).send().await?.get_receipt().await?;
let ev = rcpt.decoded_log::<DemoToken::Transfer>().ok_or("no Transfer log")?;
```

`.call()` فقط می‌خواند و چیزی در شبکه تغییر نمی‌دهد (مثل `cast call`). `.send()` تراکنش واقعی می‌فرستد (مثل `cast send`). در آخر، `decoded_log` از رسید، logی را که قرارداد emit کرده بر اساس event تعریف‌شده باز می‌کند. خروجی `alloydemo token`:

```
$ ./target/debug/alloydemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO
transfer tx type: 2 status: true gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 1: 100.000000000000000000 DEMO
```

- **خط ۱:** `decimals()` یک `u8` ساده برمی‌گرداند (۱۸) و حساب ۰ همه‌ی ۱٬۰۰۰٬۰۰۰ DEMO را دارد.
- **خط ۲:** انتقال هم یک تراکنش نوع ۲ است و موفق شد. gas مصرفی ۵۲۳۸۳ است، همان عددی که با `cast send` و در Go دیدیم، و دقیقاً یک log داریم.
- **خط ۳:** event از نوع `Transfer`، از حساب ۰ به حساب ۱. مقدار ۱۰^۲۰ واحد است، چون ۱۰۰ DEMO فرستادم و هر DEMO برابر ۱۰^۱۸ واحد است.
- **خط ۴:** حساب ۱ حالا ۱۰۰ DEMO دارد.

## خطای سفارشی به شکل enum

حالا شکست. حساب ۲ هیچ DEMO ندارد و می‌خواهد ۱ DEMO بفرستد. موقع تخمین gas، شبیه‌سازی فراخوانی {{< term "revert" "revert" >}} می‌شود و چیزی ارسال نمی‌شود. چیزی که به دست ما می‌رسد یک خطاست که داده‌ی خام revert را داخلش دارد.

اینجا `sol!` دوباره کمک می‌کند: برای خطاهایی که تعریف کردیم یک enum به اسم `DemoTokenErrors` ساخته، با یک variant برای هر خطا. پس می‌شود رویش `match` کرد:

```rust
use DemoToken::DemoTokenErrors as E;
match err.as_decoded_interface_error::<E>() {
    Some(E::InsufficientBalance(e)) => {
        println!("InsufficientBalance: from {} balance {} needed {}", e.from, e.balance, e.needed)
    }
    Some(E::InsufficientAllowance(_)) => println!("InsufficientAllowance"),
    Some(E::ZeroAddress(_)) => println!("ZeroAddress"),
    Some(E::NotMinter(_)) => println!("NotMinter"),
    None => println!("not a DemoToken error"),
}
```

```
$ ./target/debug/alloydemo revert
raw error: server returned an error response: error code 3: execution reverted: custom error 0xdb42144d: 0000...3c44cdddb6a900fa2b585dd299e03d12fa4293bc...0de0b6b3a7640000, data: "0xdb42144d...0de0b6b3a7640000"   (trimmed)
InsufficientBalance: from 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC balance 0 needed 1000000000000000000
account 2 nonce: 0
```

- **`raw error`:** آنچه نود برگردانده، کوتاه‌شده (رشته‌ی هگز واقعی بلندتر است). `0xdb42144d` همان {{< term "function-selector" "selector" >}} خطاست: چهار بایت اول که مشخص می‌کند کدام خطا رخ داده. بعد از آن آرگومان‌های خطا می‌آیند.
- **خط دوم:** `match` آن بایت‌ها را به `InsufficientBalance` تبدیل کرده است: حساب ۲ (آدرس `0x3C44…`) موجودی ۰ دارد و ۱۰^۱۸ واحد، یعنی ۱ DEMO، لازم بود.
- **`account 2 nonce: 0`:** تراکنش اصلاً فرستاده نشد، پس nonce حساب تکان نخورد.

مقایسه با Go: آنجا خروجی را به `any` باز می‌کردم و یک type assertion می‌زدم. اینجا `match` باید همه‌ی حالت‌ها را پوشش دهد، پس اگر خطای تازه‌ای به `sol!` اضافه کنم، قاعدتاً همین‌جا خطای کامپایل می‌گیرم. این آخری را امتحان نکردم.

## دنبال کردن رویداد Transfer

آخرین قدم: گوش دادن به eventها. یک filter روی نود نصب می‌کنیم که بگوید «هر Transfer جدید را به من نشان بده»، بعد دو انتقال می‌فرستیم و دو eventی را که برمی‌گردد چاپ می‌کنیم:

```rust
let poller = token.Transfer_filter().watch().await?;
let mut stream = poller.into_stream().take(2);
for n in [1u64, 2] {
    token.transfer(ACCT1, U256::from(n)).send().await?.watch().await?;
}
while let Some(item) = stream.next().await {
    let (ev, log) = item?;
    println!("block {}: {} -> {} value {}", log.block_number.unwrap_or_default(), ev.from, ev.to, ev.value);
}
```

```
$ ./target/debug/alloydemo events
block 6: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 value 1
block 7: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 value 2
```

هر خط یک انتقال است: اولی ۱ واحد در بلاک ۶ و دومی ۲ واحد در بلاک ۷ (بلاک ۵ همان انتقال مثال قبل بود).

نکته‌ی مهم اینکه روی HTTP هیچ چیزی از نود «push» نمی‌شود. طبق کد نسخه‌ی 1.6.3، `watch` با `eth_newFilter` یک filter روی نود می‌سازد و بعد مرتب `eth_getFilterChanges` را صدا می‌زند، یعنی poll می‌کند: برای نود محلی هر ۲۵۰ میلی‌ثانیه و در غیر این صورت هر ۷ ثانیه. هر آیتم یک {{< term "event-log" "log" >}} است که decode شده و metadata‌اش (مثل شماره‌ی بلاک) هم کنارش آمده. چون filter روی خود نود زندگی می‌کند، اگر نود ری‌استارت شود از بین می‌رود. به همین دلیل بعداً برای نگه‌داشتن رویدادها راه دیگری لازم داریم.

## Go و Rust، از چیزی که دیدم

- **نوع‌دار کردن ABI:** abigen کدی می‌نویسد که باید دوباره بسازید؛ `sol!` موقع کامپایل باز می‌شود و نوع غلط آرگومان خطای کامپایل است.
- **خطاها:** Go یک `rpc.DataError` و یک type assertion داد؛ alloy یک `Option` از enum تولیدشده می‌دهد.
- **پیش‌فرض‌ها:** alloy خودش nonce، gas و کارمزد را پر کرد؛ در Go یا با دست می‌کردم یا با `bind.Transact`.
- **وزن:** `Cargo.lock` ۳۹۷ پکیج دارد و build نوع dev بدون debug info، ۵۰۶ مگابایت `target/` ساخت.

## پیش‌فرض‌های غافلگیرکننده

- **fillerها کارمزد را از تاریخچه‌ی کارمزد برمی‌دارند.** همان که دیدیم: tip برابر ۱ wei شد چون بلاک‌های قبلی همین‌قدر داده بودند. روی شبکه‌ی واقعی tip را چک کنید.
- **filler پیش‌فرض nonce در 1.6.3 برای هر آدرس cache می‌کند و محلی می‌شمارد،** مثل شمارنده‌ی nonce در مقاله‌ی Go. دو پروسه با یک کلید باز هم با هم برخورد می‌کنند.
- **رابط دست‌نویس `sol!` ممکن است از قرارداد deployشده عقب بماند.** اگر قرارداد زیاد عوض می‌شود، آن را از ABI بسازید.

## تمرین

۱. race مربوط به nonce در مقاله‌ی Go را با پنج task در tokio که یک provider مشترک دارند تکرار کنید، بعد با پنج provider جدا.
۲. خطای صدا زدن `mint` از حساب ۱ را به همان `match` بدهید (اول `mint` را به `sol!` اضافه کنید).
۳. `watch` را با `get_logs` روی بلاک ۰ تا آخرین بلاک عوض کنید. چند Transfer می‌گیرید و چرا اولی از آدرس صفر می‌آید؟

## قدم بعدی

مقاله‌ی بعد «Event و ساخت indexer با Go و Postgres» است: filter روی نود با ری‌استارت از بین می‌رود، پس رویدادها را باید جایی نگه داریم که بمانند.
