+++
date = '2026-11-12T18:00:00+03:30'
draft = false
title = 'Bitcoin Script: یک مفسر stack کوچک با Rust'
description = 'Bitcoin Script با Rust: یک مفسر stack کوچک که قفل P2PKH را با HASH160 و OP_CHECKSIG باز می‌کند، همراه با کلید اشتباه، امضای دست‌کاری‌شده و OP_RETURN.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "bitcoin", "bitcoin-script", "interpreter"]
cover = { image = "/images/covers/bc-bitcoin-script-rust.fa.png", alt = "Bitcoin Script: یک مفسر stack کوچک با Rust", hiddenInSingle = true }
+++

«متعلق به Alice» برای یک خروجی یعنی چه؟ پست قبلی، [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/)، درباره‌ی ورود تراکنش‌ها به بلاک بود؛ این یکی درباره‌ی حق خرج یک سکه است.

در [تراکنش و مدل UTXO](/fa/posts/bc-transactions-utxo/) زنجیره‌ی آزمایشی ما با یک قاعده‌ی ثابت در کد جواب داد: هر {{< term "utxo" "UTXO" >}} یک آدرس نگه می‌دارد و نود چک می‌کند که کلید عمومی ورودی به آن hash شود و امضا درست باشد. در بیت‌کوین هر خروجی یک برنامه‌ی کوچک دارد، یعنی اسکریپت قفل (`scriptPubKey`)، و خرج‌کننده اسکریپت باز کردن را می‌دهد (`scriptSig`، یا witness در خروجی‌های SegWit). اگر اجرای هر دو به true برسد، سکه جابه‌جا می‌شود. اسم این زبان {{< term "bitcoin-script" "Bitcoin Script" >}} است.

این زبان یک ماشین {{< term "stack" "stack" >}} است، مثل [stack، queue و deque](/fa/posts/algo-stacks-queues-deques/)، و طبق ویکی بیت‌کوین عمداً {{< term "turing-complete" "Turing-complete" >}} نیست: نه حلقه دارد، نه پرش به عقب. هر opcode حداکثر یک بار اجرا می‌شود، پس هزینه‌ی چک کردن اسکریپت به طولش محدود است.

پایین‌تر یک مفسر کوچک با Rust می‌سازیم. این یک **زیرمجموعه‌ی آموزشی است و با consensus سازگار نیست**: حدود ده opcode، فرمت متنی خودم و یک چک امضای ساده‌شده.

> اجرا با Rust 1.90 روی macOS (arm64)، `k256` نسخه‌ی 0.13.4 برای {{< term "ecdsa" "ECDSA" >}} روی {{< term "secp256k1" "secp256k1" >}}، `sha2` نسخه‌ی 0.10.9 و `ripemd` نسخه‌ی 0.1.3. کلیدها در هر اجرا تازه و دورریختنی‌اند و هرگز پولی نگرفته‌اند. کد مثال محلی است.

## opcodeها به‌شکل enum

enum همراه با داده، مثل [Struct، Enum و Pattern Matching در Rust](/fa/posts/rust-structs-enums-pattern-matching/)، برای opcodeها مناسب است:

```rust
pub enum Op {
    Push(Vec<u8>),
    Dup, Hash160, Equal, EqualVerify, CheckSig,
    Add, If, Else, EndIf, Return,
}
```

parser متنی مثل `OP_DUP <89ab..> 5` را می‌خواند: اسم‌های `OP_` به variantها نگاشت می‌شوند، `<hex>` بایت push می‌کند، عدد دهدهی یک عدد encodeشده push می‌کند و هر چیز دیگری خطاست.

stack از نوع `Vec<Vec<u8>>` است، یعنی رشته‌های بایت. خطاها یک enum هستند و هر قدم `Result` برمی‌گرداند، مثل [مدیریت خطا با Result و Option در Rust](/fa/posts/rust-error-handling-result/):

```rust
Op::Dup => {
    let top = self.stack.last().ok_or(ScriptError::StackUnderflow("OP_DUP"))?;
    self.stack.push(top.clone());
}
Op::Hash160 => {
    let x = self.pop("OP_HASH160")?;
    self.stack.push(hash160(&x).to_vec()); // RIPEMD-160(SHA-256(x))
}
Op::EqualVerify => {
    let (a, b) = (self.pop("OP_EQUALVERIFY")?, self.pop("OP_EQUALVERIFY")?);
    if a != b { return Err(ScriptError::EqualVerifyFailed); }
}
Op::CheckSig => {
    let pubkey = self.pop("OP_CHECKSIG")?;
    let sig = self.pop("OP_CHECKSIG")?;
    let ok = check_sig(&pubkey, &sig, self.sighash);
    self.stack.push(if ok { vec![1] } else { vec![] });
}
Op::Return => return Err(ScriptError::OpReturn),
```

`HASH160` از crateهای واقعی `sha2` و `ripemd` استفاده می‌کند؛ یک تست hash ورودی خالی را ثابت نگه می‌دارد که با `openssl` هم چکش کردم. `OP_CHECKSIG` با امضای بد خطا نمی‌دهد؛ false (بایت خالی) push می‌کند و اسکریپت در انتها شکست می‌خورد.

`verify` اول اسکریپت باز کردن و بعد اسکریپت قفل را روی همان stack اجرا می‌کند و فقط با true در بالای stack موفق است. اسکریپت باز کردن فقط اجازه‌ی push داده دارد.

## چک امضا ساده شده است

`check_sig` من یک کلید فشرده‌ی ۳۳ بایتی و امضای ۶۴ بایتی `r || s` می‌گیرد و آن را روی یک {{< term "sighash" "sighash" >}} سی‌ودو بایتی که به ماشین داده شده چک می‌کند. طبق ویکی بیت‌کوین، `OP_CHECKSIG` واقعی امضای DER با یک بایت نوع sighash در انتها می‌گیرد و hash را بر اساس همان نوع از تراکنش خرج‌کننده حساب می‌کند. این‌جا sighash فقط SHA-256 یک رشته است.

## خرج کردن P2PKH

{{< term "p2pkh" "P2PKH" >}} (پرداخت به hash کلید عمومی) قفل کلاسیک بیت‌کوین است:

```
lock:   OP_DUP OP_HASH160 <pubkey hash> OP_EQUALVERIFY OP_CHECKSIG
unlock: <sig> <pubkey>
```

اسکریپت باز کردن امضا و کلید را push می‌کند. `OP_DUP` از کلید کپی می‌گیرد، `OP_HASH160` کپی را hash می‌کند، قفل hash مورد انتظار را push می‌کند، `OP_EQUALVERIFY` آن دو را مقایسه و حذف می‌کند و `OP_CHECKSIG` امضا را با کلید باقی‌مانده چک می‌کند. این همان قاعده‌ی ثابت زنجیره‌ی آزمایشی ماست، این بار به‌شکل داده.

`cargo run`:

```
lock:   OP_DUP OP_HASH160 <9405bb1b..> OP_EQUALVERIFY OP_CHECKSIG
unlock: <sig 64 bytes> <pubkey 33 bytes>

alice spends           ok (7 steps)
mallory's key          error: OP_EQUALVERIFY failed
mallory sig, alice key error: script ended with false on top
tampered sig           error: script ended with false on top
tx changed after sign  error: script ended with false on top
OP_RETURN output       error: OP_RETURN: output is unspendable
unlock with OP_DUP     error: unlock script must only push data
```

کلید خود Mallory در چک hash رد می‌شود. کلید Alice با {{< term "digital-signature" "امضای" >}} Mallory، یک بیت عوض‌شده در امضا، یا sighash متفاوت، همه به `OP_CHECKSIG` می‌رسند و false باقی می‌گذارند. خروجی‌ای که با `OP_RETURN` قفل شده را هیچ‌کس نمی‌تواند خرج کند؛ طبق مستندات بیت‌کوین، داده را این‌طور در خروجی‌هایی جا می‌دهند که نودها می‌توانند فراموششان کنند.

## عدد و شاخه

```
2 + 3 == 5             ok (5 steps)
if/else, true branch   ok (4 steps)
if/else, false branch  error: script ended with false on top
parse OP_LOOP          error: unknown token "OP_LOOP"
```

هر دو خط شاخه قفل `OP_IF 10 OP_ELSE 20 OP_ENDIF 10 OP_EQUAL` را دارند. با `1` شاخه‌ی اول اجرا می‌شود؛ با `0` عدد ۲۰ push می‌شود که ۱۰ نیست. opcodeهای ردشده شمرده نمی‌شوند.

عددها طبق توضیح ویکی‌اند: little-endian، علامت در بالاترین بیت بایت آخر و ورودی‌های حسابی حداکثر ۴ بایت. پس `0x80` یعنی «صفر منفی» و باید false حساب شود؛ یک تست این را چک می‌کند:

```
test errors ... ok
test numbers_round_trip ... ok
test hash160_known_vector ... ok
test p2pkh_spends_and_rejects_other_sighash ... ok
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

## ظرافت‌های Script

- امضای بد یک مقدار است (false)، نه خطا. stack نهایی را چک کنید، نه فقط «خطا نداشت».
- نبودن حلقه یعنی نود قبل از اجرای اسکریپت بدترین هزینه را می‌داند.
- این فقط یک زیرمجموعه است. بیت‌کوین واقعی قاعده‌های خیلی بیشتری دارد (encoding امضا، نوع‌های sighash، محدودیت اندازه، opcodeهای غیرفعال) که پیاده نشده‌اند.

## تمرین

۱. `OP_SUB` و `OP_VERIFY` را اضافه کنید، با تست برای underflow.
۲. `OP_SWAP` را اضافه کنید، بعد یک قفل ۲-از-۲ با دو `OP_CHECKSIG` و `OP_ADD` بنویسید و نشان دهید یک امضا کافی نیست.
۳. یک سقف تعداد قدم به `Machine` اضافه کنید و تست کنید که فعال می‌شود.

## قدم بعدی

پست بعد: **جمع‌بندی بخش اول: یک نود کامل کوچک با Go**. نودها را از پروسه‌ی دمو به دیسک می‌برد.
