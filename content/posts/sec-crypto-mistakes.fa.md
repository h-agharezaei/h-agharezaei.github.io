+++
date = '2027-05-17T10:00:00+03:30'
draft = false
title = 'اشتباه‌های رایج رمزنگاری'
description = 'اشتباه‌های رایج رمزنگاری در Go: ECB، تکرار nonce، نبود احراز، math/rand، هش، IV ثابت، رمز XOR و کلید ضعیف، همه با خروجی واقعی.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "cryptography", "encryption", "go", "hmac"]
cover = { image = "/images/covers/sec-crypto-mistakes.fa.png", alt = "اشتباه‌های رایج رمزنگاری", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [SSRF و deserialization ناامن](/fa/posts/sec-ssrf-deserialization/)، درباره‌ی اعتماد بیش‌ازحد به ورودی بود. رمزنگاری هم همین‌طور خراب می‌شود: کد کار می‌کند، تست‌ها سبزند و طراحی باز هم شکسته است. [مدیریت راز و کلید](/fa/posts/sec-secrets-management/) AES-GCM، nonce و رمزنگاری پاکتی را پوشش داد و تکرارشان نمی‌کنم. این مقاله فهرست «چه چیزی خراب می‌شود» است. ذخیره‌ی رمز عبور در [ذخیره‌ی امن رمز عبور](/fa/posts/sec-password-hashing/) و گواهی‌ها در [TLS و گواهی x509 در عمل](/fa/posts/sec-tls-x509-certificates/) آمده است.

> فقط دفاعی. همه‌ی کلیدها و جمله‌ها آشکارا جعلی‌اند و همه‌چیز محلی با Go 1.26 و `golang.org/x/crypto` نسخه‌ی v0.31.0 اجرا شد. سراغ پیدا کردن collision در هش یا حمله به چیز واقعی نرفتم. دمو یک `main.go` کوچک و یک تست است که با `go test -race` اجرا شد و موفق بود.

## ۱. ECB الگو را لو می‌دهد

Go کمکی برای ECB ندارد، پس بلوک به بلوک با `cipher.Block` رمز می‌کنم. متن: ۶۴ بایت `A`.

```
block 0 9716d7a815f1ccfe34e0a747bd079f4c
block 1 9716d7a815f1ccfe34e0a747bd079f4c
block 2 9716d7a815f1ccfe34e0a747bd079f4c
block 3 9716d7a815f1ccfe34e0a747bd079f4c
ECB: 4 blocks, 3 duplicates
CBC: 4 blocks, 0 duplicates
GCM: 5 blocks (incl. tag), 0 duplicates
```

{{< term "ecb-mode" "ECB" >}} بلوک‌های برابر را به بلوک‌های برابر رمز می‌کند و ساختار داده دیده می‌شود. CBC با IV تصادفی و GCM این‌طور نیستند. راه‌حل: حالت {{< term "aead" "AEAD" >}}.

## ۲. تکرار nonce

دو جمله‌ی جعلی با یک کلید و یک بلوک شمارنده‌ی صفر (CTR همان چیزی است که GCM در درونش دارد):

```
c1^c2 == p1^p2: true
knowing p1, p2 = "transfer 900 to bobby"
```

کلید حذف می‌شود. با دانستن یک پیام، پیام دیگر هم به دست می‌آید. برای هر پیام یک {{< term "nonce" "nonce" >}} تازه‌ی تصادفی با {{< term "aes-gcm" "AES-GCM" >}} بگیرید.

## ۳. رمزنگاری بدون احراز

یک بیت از متن رمزشده را برعکس کردم:

```
CTR tampered: "transfer 000 to alice" (no error)
GCM tampered: cipher: message authentication failed
```

CTR بی‌صدا `100` را `000` کرد. GCM رد کرد. رمزنگاری محتوا را پنهان می‌کند؛ فقط احراز، تغییر را تشخیص می‌دهد.

## ۴. `math/rand` برای توکن

از Go 1.20 توابع سطح بالای `math/rand` به‌صورت تصادفی seed می‌شوند، اما seed صریح هنوز قطعی است. دو process اجرا کردم:

```
run 1: seeded math/rand: afbf64b1967f8c53   unseeded: f08b0fe9b34522d4
run 2: seeded math/rand: afbf64b1967f8c53   unseeded: 9da761b5e88de565
```

مقدار seed‌شده تکرار شد. حتی نوع خودکار هم برای مخفی ماندن طراحی نشده و `math/rand/v2` همان دسته از مولدهاست. توکن و کلید را از `crypto/rand` بگیرید.

## ۵. سوءاستفاده از هش

- برای MD5 و SHA-1 حمله‌های collision شناخته‌شده‌ی عمومی وجود دارد؛ جایی که مهاجم ورودی را انتخاب می‌کند استفاده نکنید.
- هش ساده برای رمز عبور بسیار سریع است؛ مقاله‌ی رمز عبور را ببینید.
- `sha256(secret || msg)` به‌عنوان MAC در برابر {{< term "length-extension-attack" "حمله‌ی length extension" >}} آسیب‌پذیر است (توضیح، نه نمایش). از {{< term "hmac" "HMAC" >}} استفاده کنید:

```
HMAC-SHA256: 504c1fb4aec45d534910476e45d37c2feb925e4978ae10d99635a698cd14d93b
hmac.Equal(valid, forged): false
```

برچسب‌ها را با `hmac.Equal` ({{< term "constant-time-comparison" "مقایسه‌ی زمان‌ثابت" >}}) مقایسه کنید، نه `==`.

## ۶. IV ثابت و کلید در کد

```
fixed IV, equal ciphertexts: true
random IV, equal ciphertexts: false
```

IV ثابت CBC را قطعی می‌کند و ناظر پیام‌های تکراری را می‌بیند. کلید داخل سورس یعنی کلید لو رفته.

## ۷. ساختن رمز شخصی

«رمز» XOR با کلید تکرارشونده‌ی سه‌بایتی با حدس کلمه‌ی اول پیام می‌شکند:

```
recovered key: "K3y"
decrypted: "Meet me at the old bridge at noon, bring the fake documents, tell nobody at all."
```

## ۸. رمز عبور به‌جای کلید

```
password as key: 7 bytes: crypto/aes: invalid key size 7
zero-padded password is a valid key: true
```

صفر اضافه کردن آن را «کار می‌اندازد» و ضعیف می‌کند. کلید را با {{< term "key-derivation-function" "تابع اشتقاق کلید" >}} و {{< term "salt" "salt" >}} تصادفی بسازید: `scrypt.Key(pw, salt, 1<<15, 8, 1, 32)` سی‌ودو بایت داد.

## ۹ و ۱۰. TLS و امضا

`InsecureSkipVerify` بررسی گواهی را خاموش می‌کند و هر کس روی مسیر می‌تواند سرور را جعل کند؛ اینجا اجرایش نکردم. ECDSA برای هر امضا nonce مخفی یکتا می‌خواهد؛ طبق مستندات تکرارش کلید خصوصی را لو می‌دهد (ماجرای PS3 روایت معمول است که از حافظه می‌گویم و بازتولید نکردم). Ed25519 این را در طراحی دارد:

```
sig bytes: 64 verify: true
tampered message verify: false
```

## چه چیزی استفاده کنیم

| نیاز | انتخاب |
|---|---|
| رمز کردن داده | AES-GCM یا ChaCha20-Poly1305 |
| احراز پیام | HMAC-SHA256 |
| رمز عبور | Argon2id |
| تصادفی بودن | `crypto/rand` |
| امضا | {{< term "digital-signature" "Ed25519" >}} |
| انتقال | TLS |

این نظر من است که مستندات پشتوانه‌اش‌اند. بهتر از آن، کتابخانه‌ی سطح بالا (age، `secretbox` در NaCl، Tink؛ فقط نام می‌برم) بگیرید و بازبینی بخواهید.

## چند نکته‌ی مهم

- از اجزای پایه‌ای طرح شخصی نسازید.
- هر چه رمز می‌کنید احراز هم بکنید.
- هر nonce یا IV از `crypto/rand` بیاید.
- کلید از KDF یا مدیر راز بیاید، نه از یک رشته.

## تمرین

تستی بنویسید که ۱۰۰۰ پیام را با GCM رمز کند و تکراری نبودن nonceها را بررسی کند؛ بعد کد را به شمارنده تغییر دهید و فکر کنید کی خراب می‌شود.

## قدم بعدی

مقاله‌ی بعدی: امنیت حافظه: C در برابر Rust.
