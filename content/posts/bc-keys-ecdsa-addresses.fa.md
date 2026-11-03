+++
date = '2026-11-05T18:00:00+03:30'
draft = false
title = 'کلید، امضای ECDSA و آدرس روی secp256k1'
description = 'کلید secp256k1 در Go: امضا و راستی‌آزمایی ECDSA، nonce با RFC 6979، لو رفتن کلید با تکرار nonce، low-S و آدرس EIP-55 اتریوم، با خروجی واقعی.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ecdsa", "secp256k1", "ethereum", "cryptography"]
cover = { image = "/images/covers/bc-keys-ecdsa-addresses.fa.png", alt = "کلید، امضای ECDSA و آدرس روی secp256k1", hiddenInSingle = true }
+++

چه کسی اجازه‌ی خرج کردن دارد؟ زنجیره سرور لاگینی ندارد که از آن بپرسد؛ با کلید خصوصی امضا می‌کنید و هر نود امضا را با کلید عمومی شما چک می‌کند. [Merkle tree و اثبات عضویت](/fa/posts/bc-merkle-trees-proofs/) بودن داده در بلاک را ثابت کرد؛ این پست یک پکیج کوچک Go برای امضا می‌سازد تا پست بعد از آن استفاده کند. در [اشتباه‌های رایج رمزنگاری](/fa/posts/sec-crypto-mistakes/) فقط از مستندات نقل کردم که تکرار nonce در ECDSA کلید خصوصی را لو می‌دهد؛ این بار بازتولیدش می‌کنم.

> همه‌ی کلیدها یا دورریختنی و تازه‌اند و هرگز پولی نگرفته‌اند، یا کلید خصوصی `1` که یک کلید تست عمومی و معروف است. به هیچ آدرسی در این صفحه پول نفرستید. Go 1.27.3، `github.com/decred/dcrd/dcrec/secp256k1/v4` نسخه‌ی v4.4.1 و `golang.org/x/crypto` نسخه‌ی v0.58.0 روی macOS (arm64). دمو یک ماژول محلی است: پکیج `wallet` با تست و برنامه‌ی `cmd/demo`.

## چرا کتاب‌خانه

بیت‌کوین و اتریوم با {{< term "ecdsa" "ECDSA" >}} روی منحنی {{< term "secp256k1" "secp256k1" >}} امضا می‌کنند. پکیج `crypto/ecdsa` در Go منحنی‌های NIST (مثل P-256) را دارد ولی secp256k1 را نه، پس کتاب‌خانه لازم داریم. پکیج `crypto` در go-ethereum هم هست ولی ماژول بزرگی است؛ پکیج Decred کوچک و متمرکز است.

کلید خصوصی یک عدد تصادفی `d` در بازه‌ی [1, n-1] است، حدود ۲۵۶ بیت. کلید عمومی نقطه‌ی `d·G` روی منحنی است که `G` یک نقطه‌ی ثابت است. رفتن از `d` به نقطه ارزان است؛ برگشتن عملاً ممکن نیست.

## پکیج `wallet`

API عمداً کوچک است:

```go
func Generate() (*Key, error)
func (k *Key) PublicKey() []byte        // 65 bytes: 0x04 || X || Y
func (k *Key) Sign(hash [32]byte) []byte // 64 bytes: r || s
func (k *Key) Address() string
func Verify(pub []byte, hash [32]byte, sig []byte) bool
```

`Sign` یک hash سی‌ودو بایتی می‌گیرد نه خود پیام؛ این‌که کدام hash، انتخاب زنجیره است.

```go
func (k *Key) Sign(hash [32]byte) []byte {
	sig := ecdsa.Sign(k.priv, hash[:])
	r, s := sig.R(), sig.S()
	out := make([]byte, 64)
	r.PutBytesUnchecked(out[:32])
	s.PutBytesUnchecked(out[32:])
	return out
}
```

## امضا، راستی‌آزمایی، تغییر یک بایت

```go
h := sha256.Sum256(msg) // "pay 10 coins to bob"
sig1, sig2 := k.Sign(h), k.Sign(h)
...
msg[4] = '9' // "pay 90 coins to bob"
fmt.Println("verify after one byte:", wallet.Verify(k.PublicKey(), sha256.Sum256(msg), sig1))
```

```
sig: 155740b11dbd144a... 64 bytes
same sig twice: true
verify: true
verify after one byte: false
verify with other key: false
```

{{< term "digital-signature" "امضای دیجیتال" >}} همین hash را به همین کلید گره می‌زند. مبلغ یا کلید را عوض کنید، راستی‌آزمایی شکست می‌خورد.

به `same sig twice: true` دقت کنید. ECDSA برای هر امضا یک {{< term "nonce" "nonce" >}} مخفی به اسم `k` می‌خواهد. کتاب‌خانه آن را با {{< term "rfc-6979" "RFC 6979" >}} می‌سازد: یک HMAC از کلید خصوصی و hash، به‌جای عدد تصادفی. کلید و hash یکسان یعنی امضای یکسان، و موقع امضا به مولد تصادفی نیازی نیست.

## چرا تکرار nonce کلید را لو می‌دهد

امضا یعنی `r = (k·G).x` و `s = k⁻¹(z + r·d) mod n` که `z` همان hash است. اگر یک کلید دو hash را با یک `k` امضا کند، `r` هر دو یکی است و دو معادله با دو مجهول کافی است:

```
k = (z1 - z2) / (s1 - s2)
d = (s1·k - z1) / r
```

برای امتحان، امضاکننده‌ای نوشتم که `k` را پارامتر می‌گیرد (هرگز این کار را نکنید)، با یک کلید دورریختنی و یک `k` تکراری دو پیام را امضا کردم و معادله‌ها را با محاسبات scalar خود کتاب‌خانه حل کردم:

```
sig1 valid: true
sig2 valid: true
same r: true
recovered k == k: true
recovered d == private key: true
```

هر دو امضا معتبرند و ریاضی به‌تنهایی کلید را لو می‌دهد.

## Low-S و malleability

اگر `(r, s)` معتبر باشد، `(r, n - s)` هم معتبر است. این {{< term "signature-malleability" "malleability امضا" >}} است: هر کسی می‌تواند امضای معتبر دومی بسازد، و اگر شناسه‌ی تراکنش شامل امضا باشد، شناسه عوض می‌شود. کتاب‌خانه همیشه `s` کوچک‌تر را می‌دهد و `Verify` من بزرگ‌تر را رد می‌کند:

```
high-S, raw ECDSA verify: true
high-S, wallet.Verify:   false
```

طبق مستندات، تراکنش اتریوم (EIP-2) S کوچک را الزامی می‌کند و policy رله‌ی Bitcoin Core هم همین‌طور.

## آدرس به سبک اتریوم

آدرس اتریوم ۲۰ بایت آخر {{< term "keccak-256" "Keccak-256" >}} روی ۶۴ بایت `X || Y` است. Keccak-256 همان SHA3-256 استاندارد NIST نیست (padding فرق دارد)، پس در Go از `sha3.NewLegacyKeccak256` استفاده کنید. بعد {{< term "eip-55" "EIP-55" >}} هر حرف hex را که nibble متناظرش در Keccak آدرسِ حروف‌کوچک ۸ یا بیشتر باشد بزرگ می‌کند:

```go
func Address(pub []byte) string {
	h := Keccak256(pub[1:]) // drop the 0x04 prefix
	return checksum(hex.EncodeToString(h[12:]))
}
```

```
pubkey: 65 bytes, prefix 04
address: 0x2E0B564f4791229D3e027B595be21Da9f9fbbaF2
checksum ok: true
test key 1: 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf
```

تست‌ها آدرس کلید `1` (با Keccak در pycryptodome هم چک شد)، مثال مستند EIP-55 و Keccak-256 ورودی خالی را ثابت نگه می‌دارند. همه پاس شدند:

```
ok  	example.com/bckeys/wallet	0.344s
```

آدرس بیت‌کوین فرق دارد و اینجا پیاده‌اش نکردم: تا جایی که می‌دانم کلید عمومی (معمولاً فشرده) را با SHA-256 و بعد RIPEMD-160 hash می‌کند و بسته به نوع آدرس با Base58Check یا Bech32 نمایش می‌دهد.

## دام‌های کلید و امضا

- کلید خصوصی خودِ حساب است. هرگز لاگ، چاپ یا commit نشود.
- nonce را خودتان نسازید؛ از کتاب‌خانه‌ای استفاده کنید که RFC 6979 را پیاده کرده.
- اگر جایی داده را با بایت‌های امضا شناسایی می‌کند، low-S را در راستی‌آزمایی اجباری کنید.
- آدرس یک hash است: از روی آن نمی‌شود کلید عمومی را برگرداند.

## تمرین

۱. متد `Compressed()` بنویسید که کلید عمومی ۳۳ بایتی را برگرداند و چک کنید `secp256k1.ParsePubKey` هر دو شکل را قبول می‌کند.
۲. تستی بنویسید که یک بایت تصادفی از امضا را عوض کند و مطمئن شود `Verify` شکست می‌خورد.
۳. کاری کنید `ValidChecksum` آدرس تمام حروف‌کوچک را هم قبول کند (تا جایی که می‌دانم ابزارها آن را بدون checksum در نظر می‌گیرند) و برایش تست بنویسید.

## قدم بعدی

پست بعد: **تراکنش و مدل UTXO**. تراکنش‌ها را با همین پکیج `wallet` امضا می‌کنیم.
