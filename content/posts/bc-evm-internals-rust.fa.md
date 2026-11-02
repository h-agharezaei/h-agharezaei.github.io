+++
date = '2027-06-25T10:00:00+03:30'
draft = false
title = 'EVM از درون: stack، memory، storage و gas با یک مفسر کوچک Rust'
seoTitle = 'EVM از درون با یک مفسر کوچک Rust'
description = 'EVM از درون با Rust: یک مفسر کوچک با stack ۲۵۶ بیتی، memory، storage، calldata، چک JUMPDEST، REVERT و gas که جلوی حلقه‌ی بی‌پایان را می‌گیرد.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "ethereum", "evm", "interpreter"]
cover = { image = "/images/covers/bc-evm-internals-rust.fa.png", alt = "EVM از درون: stack، memory، storage و gas با یک مفسر کوچک Rust", hiddenInSingle = true }
+++

پست قبلی، [جمع‌بندی بخش اول: یک نود کامل کوچک با Go](/fa/posts/bc-toy-node-go/)، بخش اول را بست. بخش دوم، اتریوم، از زیر Solidity شروع می‌شود: ماشینی که قراردادها را اجرا می‌کند.

در [مدل حساب، nonce و جلوگیری از replay](/fa/posts/bc-account-model-nonce/) هر {{< term "account-model" "حساب" >}} یک موجودی و یک nonce بود. اتریوم {{< term "smart-contract" "smart contract" >}} را اضافه می‌کند: حسابی که کد و storage هم دارد. تراکنش به آن، کدش را روی {{< term "evm" "EVM" >}} اجرا می‌کند.

در [Bitcoin Script: یک مفسر stack کوچک با Rust](/fa/posts/bc-bitcoin-script-rust/) یک ماشین stack بدون حلقه ساختیم. این یکی حلقه دارد، پس به gas نیاز دارد.

> اجرا با Rust 1.90 روی macOS (arm64)، بدون وابستگی. کد مثال محلی است. این یک **زیرمجموعه‌ی آموزشی است، نه یک EVM سازگار با مشخصات**: ۱۹ opcode به‌علاوه‌ی `PUSH1`..`PUSH32`، gas ساده‌شده، بدون call، log و ساخت قرارداد.

## ماشین

طبق مستندات اتریوم، EVM یک ماشین {{< term "stack" "stack" >}} با کلمه‌های ۲۵۶ بیتی است و عمق stack حداکثر 1024 است. هر فراخوانی می‌بیند:

- **stack**: حداکثر 1024 کلمه، موقت؛
- **memory**: بایت‌هایی موقت که با پرداخت gas در کلمه‌های ۳۲ بایتی بزرگ می‌شوند؛
- **storage**: map دائمی قرارداد، کلید ۲۵۶ بیتی به مقدار ۲۵۶ بیتی؛
- **calldata**: ورودی فقط‌خواندنی؛ `RETURN` بایت‌هایی از memory را برمی‌گرداند.

کد {{< term "bytecode" "bytecode" >}} است: هر {{< term "opcode" "opcode" >}} یک بایت است. همه‌ی مقدارها را با جدول opcode در سورس go-ethereum چک کردم، مثلاً `ADD`=0x01، `SSTORE`=0x55، `JUMPDEST`=0x5b، `PUSH1`..`PUSH32`=0x60..0x7f و `REVERT`=0xfd.

## حلقه‌ی مفسر

Rust نوع `u256` ندارد، پس یکی کوچک نوشتم: چهار limb از `u64` با حساب wrap‌شونده، تست‌شده با `u128` و حالت‌های wrap. در کد واقعی crate تست‌شده بهتر است.

هر قدم اول gas می‌گیرد و بعد کار می‌کند. عملگرهای دوتایی بالای stack را عملوند چپ می‌گیرند:

```rust
self.charge(pc, opname, base_gas(op))?;
match op {
    0x01 | 0x02 | 0x03 | 0x10 | 0x14 => {
        let a = self.pop(pc, opname)?; // top of stack
        let b = self.pop(pc, opname)?;
        // ADD, MUL, SUB, LT, EQ on a and b, push result
    }
    0x55 => {
        let key = self.pop(pc, opname)?;
        let val = self.pop(pc, opname)?;
        self.storage.insert(key, val);
    }
    // ...
}
```

`Vm` روی یک کپی از storage کار می‌کند که فقط بعد از `STOP` یا `RETURN` ثبت می‌شود.

هزینه‌های {{< term "gas" "gas" >}} **ساده‌شده‌اند، نه مقدارهای mainnet**: opهای ارزان 3، `JUMP`=8، `JUMPI`=10، هر کلمه‌ی جدید memory 3، و `SLOAD`=100 و `SSTORE`=5000 ثابت که خودم انتخاب کردم. قیمت واقعی storage به دسترسی warm یا cold (EIP-2929) و به مقدار قبلی و جدید بستگی دارد؛ هزینه‌ی واقعی memory یک جمله‌ی درجه‌دو هم دارد.

## یک شمارنده

`PUSH1 1, PUSH1 0, SLOAD, ADD, PUSH1 0, SSTORE, STOP` خانه‌ی 0 را یکی زیاد می‌کند. trace، stack پیش از هر opcode و gas باقی‌مانده پس از کسر هزینه را نشان می‌دهد:

```
== counter, call 1 (gas limit 10000)
  pc=00 PUSH1        gas_left=9997   stack=[]
  pc=02 PUSH1        gas_left=9994   stack=[1]
  pc=04 SLOAD        gas_left=9894   stack=[1, 0]
  pc=05 ADD          gas_left=9891   stack=[1, 0]
  pc=06 PUSH1        gas_left=9888   stack=[1]
  pc=08 SSTORE       gas_left=4888   stack=[1, 0]
  pc=09 STOP         gas_left=4888   stack=[]
  success, gas used 5112
  storage after: [(0, 1)]
== counter, call 2 (gas limit 10000)
  success, gas used 5112
  storage after: [(0, 2)]
== counter, gas too low (gas limit 1000)
  halted: OutOfGas { pc: 8, op: "SSTORE" }, all gas consumed, storage changes discarded
  storage after: [(0, 2)]
```

storage بین فراخوانی‌ها می‌ماند، stack نه. با gas کم چیزی نوشته نمی‌شود.

## calldata، memory و return

`PUSH1 0, CALLDATALOAD, PUSH1 1, ADD, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN` ورودی به‌علاوه‌ی یک را برمی‌گرداند؛ `2^256-1` بی‌صدا به 0 wrap می‌شود. یک `MSTORE` دور هزینه‌ی memory را نشان می‌دهد:

```
== add one, calldata 41 (gas limit 1000)
  success, gas used 27, output 42
== add one, calldata 2^256-1 (gas limit 1000)
  success, gas used 27, output 0
== mstore at offset 1000 (gas limit 1000)
  success, gas used 108
```

(خط‌های `storage after: []` حذف شده‌اند.) نوشتن در بایت 1000 memory را ۳۳ کلمه می‌کند: 99 از 108 gas.

## حلقه، و چرا gas وجود دارد

یک شمارش معکوس، `while n != 0 { n = n - 1 }`، با `JUMPI` و `JUMP`:

```
== countdown n=2 (gas limit 1000)
  pc=00 PUSH1        gas_left=997    stack=[]
  pc=02 CALLDATALOAD gas_left=994    stack=[0]
  pc=03 JUMPDEST     gas_left=993    stack=[2]
  ... (24 lines trimmed)
  pc=10 JUMPDEST     gas_left=893    stack=[0]
  pc=11 STOP         gas_left=893    stack=[0]
  success, gas used 107
== countdown n=1000000 (gas limit 1000)
  halted: OutOfGas { pc: 15, op: "JUMP" }, all gas consumed, storage changes discarded
== stack grows forever (gas limit 100000)
  halted: StackOverflow { pc: 3 }, all gas consumed, storage changes discarded
```

EVM تا جایی که gas اجازه دهد {{< term "turing-complete" "Turing-complete" >}} است، و طبق {{< term "halting-problem" "halting problem" >}} هیچ نودی نمی‌تواند از قبل بفهمد کد دلخواه تمام می‌شود یا نه. بدون شمارنده، یک `while true` همه‌ی نودها را گیر می‌انداخت: {{< term "denial-of-service" "منع سرویس" >}}. Bitcoin Script حلقه ندارد؛ EVM حلقه دارد و هزینه‌ی هر قدم را از فرستنده می‌گیرد.

## مقصد پرش

پرش فقط روی دستور واقعی `JUMPDEST` مجاز است. VM قبل از اجرا کد را اسکن می‌کند و داده‌ی `PUSH` را رد می‌کند:

```
== jumpdest map for [60, 04, 56, 60, 5b, 00]: [false, false, false, false, false, false]
== jump into push data (gas limit 1000)
  halted: InvalidJump { pc: 2, dest: 4 }, all gas consumed, storage changes discarded
```

بایت 4 برابر `0x5b` است، اما آرگومان `PUSH1` است.

## REVERT

این کد ورودی را در خانه‌ی 0 می‌نویسد و اگر زیر 10 باشد revert می‌کند:

```
== guarded store x=42 (gas limit 20000)
  success, gas used 5034
  storage after: [(0, 42)]
== guarded store x=7 (gas limit 20000)
  REVERT, gas used 5041, storage changes discarded
  storage after: [(0, 42)]
```

`SSTORE` عدد 7 اجرا شد و بعد ناپدید شد. طبق مستندات، `REVERT` واقعی gas مصرف‌نشده را پس می‌دهد؛ خطایی مثل پرش نامعتبر همه را می‌سوزاند. هر ۷ تست `cargo test` پاس می‌شوند.

## چند نکته‌ی مهم

- ترتیب عملوندها: `SUB` بالای stack منهای دومی است؛ در نوشتن دستی راحت اشتباه می‌شود.
- حساب در 2^256 بی‌صدا wrap می‌شود؛ Solidity از نسخه‌ی 0.8 به بعد چک overflow را رویش اضافه می‌کند.
- بایت‌های بعد از `PUSH` داده‌اند؛ مقصد پرش را قبل از اجرا تحلیل کنید.
- برای کار واقعی از پیاده‌سازی سازگار استفاده کنید؛ revm یک EVM پرکاربرد Rust است (Foundry و Reth رویش ساخته شده‌اند)؛ این‌جا اجرایش نکردم.

## تمرین

۱. `POP` (0x50) و `GT` (0x11) را با تست اضافه کنید.
۲. فرمول واقعی memory را با بخش درجه‌دو پیاده کنید.
۳. قیمت `SLOAD` را با خانه‌های warm و cold هر فراخوانی تعیین کنید.

## قدم بعدی

پست بعد: **اولین قرارداد با Solidity و Foundry**.
