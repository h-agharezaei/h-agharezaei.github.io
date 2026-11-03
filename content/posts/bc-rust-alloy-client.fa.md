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

اگر از Go و از Rust به یک anvil ether بفرستید، tipها فرق می‌کنند: go-ethereum ۱ gwei پیشنهاد داد و {{< term "alloy" "alloy" >}} ۱ {{< term "wei" "wei" >}} انتخاب کرد. این پست همان قدم‌های [پست Go](/fa/posts/bc-go-ethereum-client/) را با Rust برمی‌دارد.

قرارداد از [پست توکن‌ها](/fa/posts/bc-erc20-erc721/) است، کد async روی tokio اجرا می‌شود، مثل [پست Tokio](/fa/posts/rust-async-tokio/)، و `sol!` یک procedural macro مثل [ماکروهای Rust](/fa/posts/rust-macros/) است.

> اجرا با Rust 1.90 روی macOS (arm64)، `alloy` 1.6.3 (featureهای پیش‌فرض خاموش؛ `std`، `reqwest`، `provider-http`، `signer-local`، `contract`، `rpc-types`)، `tokio` 1.54.1، `futures-util` 0.3 و Foundry 1.8.7. نسخه‌ی 1.6.3 را انتخاب کردم چون نسخه‌های جدیدتر alloy به Rust جدیدتر از 1.90 نیاز دارند. یک anvil تازه روی `127.0.0.1:8545` با اسکریپت دیپلوی پست توکن‌ها. کلیدهای داخل کد کلیدهای تست عمومی anvil هستند: هیچ‌جای واقعی از آن‌ها استفاده نکنید.

## Provider، chain ID و موجودی

یک `Provider` روی API از نوع {{< term "json-rpc" "JSON-RPC" >}} نود سوار می‌شود، مثل `ethclient`:

```rust
let provider = ProviderBuilder::new().connect_http(RPC.parse()?);
let addr0 = KEY0.parse::<PrivateKeySigner>()?.address();
let bal = provider.get_balance(addr0).await?; // U256, in wei
println!("chain id:     {}", provider.get_chain_id().await?);
println!("balance ETH:  {}", format_units(bal, "ether")?);
```

```
$ ./target/debug/alloydemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

همان عددهای اجرای Go، از همان دیپلوی. موجودی به wei از نوع `U256` است، یک عدد صحیح ۲۵۶ بیتی با اندازه‌ی ثابت؛ Go از `*big.Int` استفاده می‌کرد.

## کیف‌پول و ارسال EIP-1559

با وصل کردن یک امضاکننده به builder، provider می‌تواند تراکنش بفرستد:

```rust
let signer: PrivateKeySigner = KEY0.parse()?;
let provider = ProviderBuilder::new().wallet(signer).connect_http(RPC.parse()?);
let value = U256::from(1_500_000_000_000_000_000u128); // 1.5 ETH
let tx = TransactionRequest::default().with_to(ACCT1).with_value(value);
let rcpt = provider.send_transaction(tx).await?.get_receipt().await?;
```

```
$ ./target/debug/alloydemo send
tx type: 2 hash: 0xa0306b3e8c9b5ef2886dc4d96111769d11e473ff92a28ac0d09d701e9cb3c58b
status: true block: 4 gas used: 21000 effective gas price: 685976108
account 1 gained: 1.500000000000000000 ETH
```

nonce، gas و کارمزد را خودم تعیین نکردم: «filler»های پیش‌فرض builder پرشان کردند و یک تراکنش {{< term "eip-1559" "EIP-1559" >}} (نوع ۲) ساختند. `cast tx` نشان می‌دهد چه انتخاب کردند: `maxFeePerGas` برابر 1566842331، یعنی دو برابر base fee بلاک ۳ (783421165) به‌اضافه‌ی tip برابر **۱ wei**. در Go، `SuggestGasTipCap` از `eth_maxPriorityFeePerGas` پرسید و ۱ gwei گرفت. estimator نسخه‌ی 1.6.3 در alloy (کدش را خواندم) به‌جایش میانه‌ی tip را از `eth_feeHistory` در ۱۰ بلاک آخر برمی‌دارد و تراکنش‌های دیپلوی ۱ wei tip داده بودند.

## ماکروی sol! به‌جای abigen

در Go، {{< term "contract-abi" "ABI" >}} را بیرون کشیدم و abigen را اجرا کردم که یک `token.go` با ۶۴۸ خط در مخزن نوشت. در Rust {{< term "sol-macro" "ماکروی sol!" >}} اعلان‌های Solidity را موقع کامپایل می‌خواند:

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

فایل تولیدشده‌ای در مخزن نمی‌ماند و آرگومان‌ها نوع دارند. فراخوانی عمداً غلط در `examples/wrong_type.rs` کامپایل نمی‌شود:

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

روی دیگر سکه: این رابط دست‌نویس است. `sol!` می‌تواند JSON مربوط به ABI را از `out/` هم بخواند؛ امتحانش نکردم.

## فراخوانی و ارسال

```rust
let token = DemoToken::new(TOKEN, &provider);
let dec = token.decimals().call().await?;   // u8
let b0 = token.balanceOf(me).call().await?; // U256
let rcpt = token.transfer(ACCT1, amount).send().await?.get_receipt().await?;
let ev = rcpt.decoded_log::<DemoToken::Transfer>().ok_or("no Transfer log")?;
```

```
$ ./target/debug/alloydemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO
transfer tx type: 2 status: true gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 1: 100.000000000000000000 DEMO
```

gas مصرفی 52383 است، مثل `cast send` و Go. `decimals()` یک `u8` ساده برمی‌گرداند.

## خطای سفارشی به شکل enum

حساب ۲ هیچ DEMO ندارد. موقع تخمین gas فراخوانی {{< term "revert" "revert" >}} می‌شود و چیزی ارسال نمی‌شود. `sol!` یک enum به اسم `DemoTokenErrors` با یک variant برای هر خطا ساخته، پس می‌شود رویش `match` کرد:

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

`0xdb42144d` همان {{< term "function-selector" "selector" >}} خطاست. در Go خروجی را به `any` باز کردم و type assertion زدم؛ اینجا `match` باید همه‌ی حالت‌ها را پوشش دهد، پس خطای تازه در `sol!` قاعدتاً همین‌جا خطای کامپایل می‌دهد (امتحانش نکردم).

## دنبال کردن رویداد Transfer

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

روی HTTP چیزی push نمی‌شود. طبق کد نسخه‌ی 1.6.3، `watch` با `eth_newFilter` یک filter نصب می‌کند و `eth_getFilterChanges` را poll می‌کند، برای نود محلی هر ۲۵۰ میلی‌ثانیه و در غیر این صورت هر ۷ ثانیه. هر آیتم یک {{< term "event-log" "log" >}} decodeشده به‌همراه metadata است. filterها روی نود زندگی می‌کنند و با ری‌استارت نود از بین می‌روند.

## Go و Rust، از چیزی که دیدم

- نوع‌دار کردن ABI: abigen کدی می‌نویسد که باید دوباره بسازید؛ `sol!` موقع کامپایل باز می‌شود و نوع غلط آرگومان خطای کامپایل است.
- خطاها: Go یک `rpc.DataError` و یک type assertion داد؛ alloy یک `Option` از enum تولیدشده می‌دهد.
- پیش‌فرض‌ها: alloy خودش nonce، gas و کارمزد را پر کرد؛ در Go با دست یا `bind.Transact`.
- وزن: `Cargo.lock` ۳۹۷ پکیج دارد و build نوع dev بدون debug info، ۵۰۶ مگابایت `target/` ساخت.

## پیش‌فرض‌های غافلگیرکننده

- fillerها کارمزد را از تاریخچه‌ی کارمزد برمی‌دارند. روی شبکه‌ی واقعی tip را چک کنید.
- در 1.6.3 filler پیش‌فرض nonce برای هر آدرس cache می‌کند و محلی می‌شمارد، مثل شمارنده‌ی nonce در پست Go. دو پروسه با یک کلید باز هم با هم برخورد می‌کنند.
- رابط دست‌نویس `sol!` ممکن است از قرارداد دیپلوی‌شده عقب بماند. اگر قرارداد زیاد عوض می‌شود، آن را از ABI بسازید.

## تمرین

۱. race مربوط به nonce در پست Go را با پنج task در tokio که یک provider مشترک دارند تکرار کنید، بعد با پنج provider جدا.
۲. خطای صدا زدن `mint` از حساب ۱ را به همان `match` بدهید (اول `mint` را به `sol!` اضافه کنید).
۳. `watch` را با `get_logs` روی بلاک ۰ تا آخرین بلاک عوض کنید. چند Transfer می‌گیرید و چرا اولی از آدرس صفر می‌آید؟

## قدم بعدی

پست بعد: **Event و ساخت indexer با Go و Postgres**؛ رویدادهایی که بعد از ری‌استارت نود هم می‌مانند.
