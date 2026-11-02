+++
date = '2027-07-02T10:00:00+03:30'
draft = false
title = 'کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust'
description = 'کیف‌پول HD با Rust: از کلمه‌های BIP-39 تا seed، BIP-32 سنجیده با test vector، آدرس اتریوم با BIP-44، سرور واریز با xpub و خطر لو رفتن xpub.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "hd-wallet", "bip32", "bip39", "ethereum"]
cover = { image = "/images/covers/bc-hd-wallets-rust.fa.png", alt = "کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust", hiddenInSingle = true }
+++

پست قبلی، [Event و ساخت indexer با Go و Postgres](/fa/posts/bc-event-indexer-go/)، واریز به آدرس‌های شناخته‌شده را زیر نظر داشت. آدرس‌ها از کجا می‌آیند؟ در [کلید، امضای ECDSA و آدرس روی secp256k1](/fa/posts/bc-keys-ecdsa-addresses/) هر کلید تصادفی یک آدرس می‌داد. صرافی برای هر کاربر آدرس می‌خواهد؛ با یک کلید تصادفی برای هر آدرس، پشتیبان با هر ثبت‌نام بزرگ‌تر و سرور پر از کلید خصوصی می‌شود.

{{< term "hd-wallet" "کیف‌پول HD" >}} هر دو را حل می‌کند: یک seed، درختی از کلیدهای محاسبه‌شده، و نیمه‌ای عمومی که بدون کلید خصوصی آدرس می‌سازد؛ و با تفکیک hot/cold در [پست هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) جور است.

> همه‌ی mnemonicها، seedها و آدرس‌های این صفحه از **test vectorهای عمومی** آمده‌اند و کلیدشان را هر کسی می‌تواند حساب کند: هرگز به آن‌ها پول نفرستید. Rust 1.90، `bip32` نسخه‌ی 0.5.3 (iqlusion)، `k256` 0.13.4، `pbkdf2` 0.12.2، `hmac` 0.12.1، `sha2` 0.10.9، `sha3` 0.10.9 و `hex` 0.4.3 روی macOS (arm64). دمو یک پروژه‌ی محلی Cargo است.

## BIP-39: از کلمه تا seed

{{< term "bip-39" "BIP-39" >}} به entropy تصادفی (اینجا ۲۵۶ بیت) بایت اول SHA-256 آن را به‌عنوان checksum اضافه می‌کند و ۲۶۴ بیت را به ۲۴ تکه‌ی ۱۱ بیتی می‌بُرد؛ هر تکه شماره‌ی کلمه‌ای در فهرست ۲۰۴۸تایی است. vector با entropy تمام‌صفر را از فایل تست crate برداشتم (کپی‌شده از `vectors.json` ترزور):

```rust
let m = Mnemonic::from_entropy([0u8; 32], Language::English);
let cs = Sha256::digest([0u8; 32])[0];
let typo = m.phrase().replace(" art", " abandon");
println!("last word changed: {:?}", Mnemonic::new(typo, Language::English).err());
```

```
words: 24, first: abandon, last: art
checksum byte: 0x66 -> last word index 102
last word changed: Some(Bip39)
```

کلمه‌ی آخر ۳ بیت صفر از entropy و checksum یعنی `0x66` = 102 = "art" را نگه می‌دارد، پس غلط تایپی معمولاً گیر می‌افتد. این crate یک خطای کلی `Bip39` می‌دهد و فقط ۲۴ کلمه را پشتیبانی می‌کند.

طبق BIP-39، seed حاصل {{< term "pbkdf2" "PBKDF2" >}}-HMAC-SHA512 است: کلمه‌ها به‌عنوان رمز، `"mnemonic" + passphrase` به‌عنوان salt و ۲۰۴۸ دور. دستی هم حسابش کردم:

```rust
let seed = m.to_seed("TREZOR");
let mut manual = [0u8; 64];
pbkdf2::pbkdf2_hmac::<Sha512>(m.phrase().as_bytes(), b"mnemonicTREZOR", 2048, &mut manual);
```

```
seed: bda85446c6841370...
seed matches vector: true
manual PBKDF2 == seed: true
seed with empty passphrase: 408b285c12383600...
root xprv matches vector: true
```

passphrase دیگر یعنی کیف‌پول دیگر؛ خطای «passphrase اشتباه» وجود ندارد. مثل [ذخیره‌ی امن رمز عبور](/fa/posts/sec-password-hashing/)، دورها فقط حدس را کند می‌کنند؛ محافظ اصلی entropy است.

## BIP-32: کلید master، chain code و فرزندها

{{< term "bip-32" "BIP-32" >}} روی seed یک {{< term "hmac" "HMAC" >}}-SHA512 می‌گیرد: نیمه‌ی چپ کلید خصوصی master است و نیمه‌ی راست **chain code**. هر فرزند هم HMAC-SHA512 با کلید chain code والد است و نیمه‌ی چپش به کلید والد (پیمانه‌ی n) اضافه می‌شود. کلید و chain code با هم کلید توسعه‌یافته‌اند: `xprv`، یا {{< term "xpub" "xpub" >}} در سمت عمومی. test vector شماره‌ی ۱ از BIP-32 (seed `000102...0f`؛ مقدارهای مورد انتظار از spec و تست‌های crate):

```
chain code: 873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508
m xprv matches: true
m/0'/1 from xpub only matches: true
xpub -> hardened child: Some(ChildNumber)
```

`m/0'/1` فقط از xpub کلید `m/0'` ساخته شد. این برای شماره‌های **معمولی** کار می‌کند که ورودی HMAC کلید عمومی والد است. برای شماره‌های {{< term "hardened-derivation" "hardened" >}} (`2'`، یعنی 2^31 به بالا) ورودی کلید خصوصی والد است و xpub خطا می‌دهد.

## چرا hardened مهم است

در مشتق‌گیری معمولی `k_child = IL + k_parent mod n` است و `IL` فقط xpub والد را می‌خواهد. پس با xpub و کلید خصوصی یک فرزند معمولیِ لو رفته: `k_parent = k_child - IL`:

```rust
let mut mac = Hmac::<Sha512>::new_from_slice(&parent.attrs().chain_code).unwrap();
mac.update(&parent.to_bytes()); // 33-byte compressed public key
mac.update(&index.to_be_bytes());
let i = mac.finalize().into_bytes();
let il = <Scalar as Reduce<U256>>::reduce_bytes(i[..32].into());
let kc = <Scalar as Reduce<U256>>::reduce_bytes(child_priv.into());
(kc - il).to_bytes().into()
```

کلید `m/44'/60'/0'/0/3` را «لو دادم» و دو پله بالا رفتم:

```
recovered m/44'/60'/0' private key == real: true
```

یک کلید لو رفته کل account را خرج‌پذیر می‌کند. بالا رفتن در `0'` (hardened) می‌ایستد: `IL` آنجا همان کلید مجهول را لازم دارد.

## BIP-44 و آدرس اتریوم

{{< term "bip-44" "BIP-44" >}} چیدمان را ثابت می‌کند: `m / 44' / coin' / account' / change / index` و برای Ether عدد 60. قاعده‌ی آدرس همان BC4 است (Keccak-256 کلید فشرده‌نشده، ۲۰ بایت آخر، {{< term "eip-55" "EIP-55" >}}) و برای کلید خصوصی 1 همان `0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf` را می‌دهد. watch-only در برابر مشتق‌گیری کامل:

```
account xpub: xpub6DGfjznv...EajsXn
m/44'/60'/0'/0/0  0x2b5D7A0E9d3EC34D629D07c6bDE5c41fb613c655  same as xprv: true
m/44'/60'/0'/0/1  0xAbc76C2f6D144fA6Fe17bb6CA0e6D81a38Daa353  same as xprv: true
m/44'/60'/0'/0/2  0x7375C7Ea6F22Dd15A36DAC44E906a83991a75701  same as xprv: true
```

این سه آدرس را با کیف‌پول دیگری مقایسه نکردم.

## سرور واریز watch-only

شکلی که برای واریز صرافی انتخاب می‌کنم:

- ماشینی آفلاین seed را می‌سازد و فقط xpub مربوط به account را بیرون می‌دهد.
- سرویس واریز `(user_id, index, address)` را با `address = xpub/0/index` ذخیره می‌کند. بدون کلید خصوصی.
- indexer پست قبلی همین آدرس‌ها را زیر نظر دارد.
- امضاکننده‌ای جدا پول را جابه‌جا می‌کند: {{< term "hot-wallet" "کیف‌پول داغ" >}} کوچک آنلاین، بقیه سرد.

xpubی را که با فرزندهای معمولی‌اش آنلاین امضا هم می‌شود بیرون ندهید؛ این دو را با accountهای hardened جدا کنید.

## چند نکته‌ی مهم

- mnemonic یعنی همه‌ی کلیدها با هم: نه لاگ، نه اسکرین‌شات، نه یادداشت ابری.
- xpub همه‌ی آدرس‌ها را لو می‌دهد و با یک کلید فرزند لو رفته، کلید والد را.
- passphrase گم‌شده یعنی پول گم‌شده.
- سطح‌های hardened را مرز بین accountها و سرویس‌ها قرار دهید.
- با vectorهای رسمی تست کنید، نه با عبارتی که پول دارد.

## تمرین

1. بیست آدرس واریز از xpub بسازید و در `HashMap<String, u32>` برای indexer نگه دارید.
2. `assert!` را از `recover_parent` بردارید و نشان دهید برای فرزند hardened کلید اشتباه برمی‌گرداند.
3. شماره‌ی ۲۴ کلمه را دستی از entropy حساب و با `phrase()` مقایسه کنید.

## قدم بعدی

پست بعد: **AMM و فرمول constant product**.
