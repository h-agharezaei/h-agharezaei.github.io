+++
date = '2027-07-12T10:00:00+03:30'
draft = false
title = 'مبانی zero-knowledge proof با Rust'
description = 'zero-knowledge proof با Rust: اثبات Schnorr روی secp256k1، اثبات‌کننده‌ی متقلب، Fiat-Shamir و باگ جعل آن، و لو رفتن راز با تکرار nonce.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "zero-knowledge", "schnorr", "cryptography", "secp256k1"]
cover = { image = "/images/covers/bc-zero-knowledge-rust.fa.png", alt = "مبانی zero-knowledge proof با Rust", hiddenInSingle = true }
+++

پست قبلی، [Bridge و ارتباط بین زنجیره‌ها](/fa/posts/bc-bridges-cross-chain/)، درباره‌ی اعتماد به ادعای زنجیره‌ی دیگر بود. zero-knowledge proof جلوتر می‌رود: قانع کردن دیگری به درستی یک گزاره، بدون نشان دادن دلیلش. در [Merkle tree و اثبات عضویت](/fa/posts/bc-merkle-trees-proofs/) اثبات، برگ را نشان می‌داد و در [کلید، امضای ECDSA و آدرس روی secp256k1](/fa/posts/bc-keys-ecdsa-addresses/) تکرار nonce کلید خصوصی را لو داد. هر دو اینجا برمی‌گردند.

> کد آموزشی است، نه برای production. رازها scalar تصادفی تازه‌اند و چاپ نمی‌شوند. Rust 1.90، `k256` 0.13.4 (فقط feature `arithmetic`)، `sha2` 0.10.9 و `rand_core` 0.6.4 روی macOS (arm64). دمو یک پروژه‌ی محلی Cargo است.

## یک اثبات چه قولی می‌دهد

{{< term "zero-knowledge-proof" "zero-knowledge proof" >}} بین **prover** و **verifier** اجرا می‌شود و سه قول می‌دهد:

- **Completeness**: prover صادقِ دارای راز همیشه قانع می‌کند.
- **Soundness**: prover بدون راز شکست می‌خورد، جز با احتمالی ناچیز.
- **Zero-knowledge**: verifier فقط «درست است» را می‌فهمد؛ هر چه دیده را خودش هم می‌توانست بسازد.

گزاره‌ی ما روی secp256k1: «`x` را می‌دانم که `X = x·G`». یافتن `x` از `X` مسئله‌ی {{< term "discrete-logarithm" "لگاریتم گسسته" >}} است و روی این منحنی ناممکن فرض می‌شود.

## پروتکل تعاملی Schnorr

در {{< term "schnorr" "پروتکل Schnorr" >}} prover با `r` تصادفی تعهد `R = r·G` را می‌فرستد، verifier یک challenge تصادفی `c` می‌دهد و prover جواب `s = r + c·x` را:

```rust
fn commit() -> (Scalar, Point) {
    let r = Scalar::random(&mut OsRng);
    (r, G * r)
}
fn respond(x: Scalar, r: Scalar, c: Scalar) -> Scalar {
    r + c * x
}
fn verify(pub_x: Point, big_r: Point, c: Scalar, s: Scalar) -> bool {
    G * s == big_r + pub_x * c
}
```

`r` یک {{< term "nonce" "nonce" >}} است که `x` را داخل `s` پنهان می‌کند. Completeness:

```
== interactive, honest prover ==
accepted 1000/1000
```

## Soundness: متقلب و extractor

متقلب بدون `x` می‌تواند `c` را حدس بزند، `s` دلخواهی بردارد و `R = s·G - c_guess·X` بسازد. فقط اگر verifier دقیقاً `c_guess` را بفرستد قبول می‌شود: احتمال 1/q برای گروه با مرتبه‌ی q. روی secp256k1 این حدود 2^-256 است، پس گروهی اسباب‌بازی هم گرفتم: 4 به پیمانه‌ی 23 با مرتبه‌ی 11:

```
== cheating prover (does not know x) ==
toy group q=11: 8837/100000 = 0.0884 (1/q = 0.0909)
secp256k1:      0/10000
```

سه اجرای دیگر: 0.0905، 0.0920 و 0.0895.

چرا راه بهتری نیست؟ جواب دادن به دو challenge برای یک `R` مقدار `x = (s1 - s2) / (c1 - c2)` را لو می‌دهد؛ پس جواب مطمئن یعنی دانستن `x`:

```
== extractor: same R, two challenges ==
both transcripts valid: true, extracted x == x: true
```

## Zero-knowledge: یک simulator

اول `c` و `s` را بردارید، بعد `R = s·G - c·X`، بدون `x`:

```
== simulator: valid transcript without x ==
simulated (R, c, s) verifies: true
```

transcript شبیه‌سازی‌شده با واقعی فرقی ندارد، پس چیزی درباره‌ی `x` یاد نمی‌دهد. فرض این استدلال تصادفی بودن `c` است (honest-verifier zero-knowledge).

## Fiat-Shamir: بدون verifier

{{< term "fiat-shamir" "تبدیل Fiat-Shamir" >}} به‌جای verifier از hash روی transcript استفاده می‌کند تا هر کسی بعداً اثبات را چک کند، مثل {{< term "digital-signature" "امضای دیجیتال" >}}:

```rust
fn challenge(pub_x: Point, big_r: Point, msg: &[u8]) -> Scalar {
    hash_to_scalar(&[b"bc30/schnorr/v1", &enc(G), &enc(pub_x), &enc(big_r), msg])
}
```

```
== Fiat-Shamir ==
proof: R=02010fea30003cab.. s=5be1affab357361e..
check: true
check other msg: false
check other key: false
```

باگ کلاسیک جا انداختن چیزی از hash است. `challenge_no_r` باگ‌دار `R` را نمی‌گیرد، پس مهاجم `c` را پیش از انتخاب `R` می‌داند؛ ترفند simulator:

```rust
let c = challenge_no_r(pub_x, msg);
let s = Scalar::random(&mut OsRng);
let forged = Proof { big_r: G * s - pub_x * c, s };
```

```
== bug: R not hashed -> forgery ==
forged, buggy verifier: true
forged, correct verifier: false
```

اثبات معتبر برای کلیدی که مهاجم رازش را ندارد. طبق منابع، جا انداختن کلید عمومی هم مشابه است؛ آن را اجرا نکردم.

## تکرار nonce راز را لو می‌دهد

extractor یک حمله هم هست. دو اثبات با یک `r` challengeهای متفاوت دارند:

```
== nonce reuse leaks x ==
both valid: true, same R: true
recovered x == x: true
```

همان جبر لو رفتن کلید {{< term "ecdsa" "ECDSA" >}} در BC4. طبق BIP-340، امضای Schnorr بیت‌کوین همین ساختار روی secp256k1 است، با tagged hash و روشی پیشنهادی برای ساخت nonce.

## نگاه کلی (بدون کد)

Schnorr یک گزاره‌ی ثابت را اثبات می‌کند. سیستم‌های عمومی اثبات می‌کنند «این برنامه روی ورودی‌های مخفی درست اجرا شد»:

- **Circuit**: محاسبه به قیدهای حسابی روی یک میدان متناهی تبدیل می‌شود (arithmetization) و prover نشان می‌دهد جوابی برای همه‌ی قیدها دارد.
- {{< term "zk-snark" "zk-SNARK" >}} اثبات خیلی کوچک (Groth16: سه عضو گروه، طبق مقاله‌اش) و بررسی سریع دارد. خیلی از SNARKها {{< term "trusted-setup" "trusted setup" >}} می‌خواهند؛ نگه‌دارنده‌ی راز تصادفی آن می‌تواند اثبات جعل کند.
- {{< term "zk-stark" "zk-STARK" >}} شفاف است (فقط تابع hash، بدون setup)؛ تا جایی که می‌دانم اثبات‌هایش خیلی بزرگ‌ترند، ده‌ها کیلوبایت یا بیشتر.
- **ZK-rollup** دسته‌ای از تراکنش‌ها را با یک validity proof می‌فرستد و قراردادی روی L1 پیش از پذیرفتن state root جدید آن را بررسی می‌کند ([Layer 2 و rollupها: optimistic و ZK](/fa/posts/bc-layer2-rollups/)).
- **حریم خصوصی**: اثبات عضویت در Merkle tree بدون فاش کردن برگ. تراکنش‌های shielded در Zcash با zk-SNARK کار می‌کنند.

سیستم‌های واقعی از کتاب‌خانه‌هایی مثل arkworks، halo2 یا RISC Zero استفاده می‌کنند؛ من سراغشان نرفتم.

## چند نکته‌ی مهم

- همه چیز را hash کنید: برچسب دامنه، generator، کلید عمومی، تعهد و پیام.
- nonce را تکرار نکنید و اریب نسازید؛ یک تکرار راز را لو می‌دهد.
- کتاب‌خانه‌ی audit‌شده به کار ببرید؛ این کد نه constant-time است نه بازبینی‌شده.
- بپرسید trusted setup به چه کسی اعتماد دارد و رازهایش را چه کسی نابود کرده.

## تمرین

۱. `pub_x` را از `challenge` حذف کنید و جعل کنید: اول `R`، بعد hash، بعد کلید.
۲. با q = 5 (4 به پیمانه‌ی 11 مرتبه‌ی 5 دارد) نرخ موفقیت متقلب را ببینید.
۳. `prove` را با nonceهایی به سبک BIP-340 به یک امضا تبدیل کنید.

## قدم بعدی

پست بعد: **مهندسی صرافی: واریز، برداشت، confirmation و reorg**.
