+++
date = '2026-11-07T18:00:00+03:30'
draft = false
title = 'مدل حساب، nonce و جلوگیری از replay'
description = 'مدل حساب در Go: موجودی و nonce برای هر آدرس، رد تراکنش تکراری و خارج از ترتیب، chain ID در برابر replay بین زنجیره‌ها و مقایسه با UTXO.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "nonce", "replay-protection"]
cover = { image = "/images/covers/bc-account-model-nonce.fa.png", alt = "مدل حساب، nonce و جلوگیری از replay", hiddenInSingle = true }
+++

در اتریوم یک «۳۰ سکه به Bob بده»ی امضاشده بعد از اجرا هم معتبر می‌ماند؛ بدون state اضافه، هر کسی می‌تواند تکرارش کند. این {{< term "replay-attack" "حمله‌ی replay" >}} است، همان مسئله‌ی پیام تکراری در [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/)، فقط با پول. مدل {{< term "utxo" "UTXO" >}} [پست قبلی](/fa/posts/bc-transactions-utxo/) خودبه‌خود در امان بود: هر پرداخت خروجی‌های کامل را مصرف می‌کرد، پس تراکنش تکراری دیگر ورودی نداشت. اتریوم به‌جایش موجودی هر آدرس را نگه می‌دارد.

ماژول `toychain` پست قبل را کپی کردم و پکیج `account` را اضافه کردم. بلاک‌ها هنوز تراکنش UTXO دارند و در پست‌های بعدی هم همین می‌ماند: مدل حساب یک state جدا برای مقایسه است که به بلاک‌ها وصلش نکردم.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است. کلیدها از کلمه‌هایی مثل "alice" ساخته شده‌اند: عمومی‌اند، هرگز پولی نگرفته‌اند و فقط برای دمو هستند.

## تراکنش حساب

در {{< term "account-model" "مدل حساب" >}} کل دفتر دو map است:

```go
type State struct {
	ChainID  uint64
	Balances map[chain.Address]uint64
	Nonces   map[chain.Address]uint64 // next expected nonce per sender
}

type Tx struct {
	ChainID uint64
	Nonce   uint64
	To      chain.Address
	Value   uint64
	Fee     uint64
	PubKey  []byte // the sender is derived from this
	Sig     []byte
}
```

فیلد `From` نداریم؛ فرستنده آدرس `PubKey` است و امضا باید با آن درست باشد. طبق مستندات اتریوم، تراکنش واقعی کلید عمومی را نمی‌فرستد و آن را از روی امضا بازیابی می‌کند؛ پکیج `wallet` من بازیابی ندارد، پس می‌فرستمش. sighash همه‌ی فیلدها جز امضا را پوشش می‌دهد، از جمله `ChainID` و `Nonce`.

## Nonce: نه replay، نه جابه‌جایی

هر فرستنده یک شمارنده دارد. تراکنش باید دقیقاً مقدار بعدی را داشته باشد و اجرایش آن را یکی بالا می‌برد:

```go
switch want := s.Nonces[from]; {
case tx.Nonce < want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceUsed, tx.Nonce, want)
case tx.Nonce > want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceGap, tx.Nonce, want)
}
```

اینجا {{< term "nonce" "nonce" >}} یک شماره‌ی ترتیب است، نه nonce تصادفی ECDSA از پست کلیدها. `go run ./cmd/toychain account`: Alice با ۱۰۰ شروع می‌کند و ۳۰ به Bob می‌دهد با کارمزد ۱:

```
tx nonce 0: 185 bytes, apply: <nil>
  alice 69 (nonce 1), bob 30, miner 1
replay the same tx: nonce already used: got 0, next is 1
nonce 2 before 1:   nonce too high: earlier nonce missing: got 2, next is 1
nonce 1:            <nil>
nonce 2 now:        <nil>
  alice 57 (nonce 3), bob 40, miner 3
```

replay شکست می‌خورد: nonce صفر مصرف شده. من شکاف را رد می‌کنم، نه این‌که در صف نگهش دارم: nonce دو تا رسیدن nonce یک رد می‌شود. تا جایی که می‌دانم کلاینت‌های اتریوم چنین تراکنشی را در mempool نگه می‌دارند تا شکاف پر شود؛ قواعد consensus باز هم آن‌ها را دقیقاً به ترتیب اجرا می‌کنند.

## Chain ID: نه replay روی زنجیره‌ی دیگر

nonce جلوی replay روی همان زنجیره را می‌گیرد. اگر زنجیره دو شاخه شود، یا شبکه‌ی تست با شبکه‌ی اصلی کلید مشترک داشته باشد، همان nonce روی هر دو معتبر است. طبق EIP-155، اتریوم یک {{< term "chain-id" "chain ID" >}} داخل داده‌ی امضاشده می‌گذارد. `go run ./cmd/toychain crosschain` دو state با تاریخچه‌ی یکسان و شناسه‌ی متفاوت اجرا می‌کند:

```
on chain 1: <nil>
same tx on chain 2: transaction is for another chain: tx 1, this chain 2
chain ID edited to 2: bad signature
  alice 100 (nonce 0), bob 0, miner 0
```

زنجیره‌ی ۲ آن را رد می‌کند و عوض کردن فیلد {{< term "digital-signature" "امضا" >}} را می‌شکند.

## همان پرداخت‌ها در هر دو مدل

`go run ./cmd/toychain compare` ده پرداخت یک‌سکه‌ای از Alice به Bob را در هر مدل، همه در یک بلاک، می‌فرستد:

```
utxo block: <nil>
utxo:    12 state entries, 2330 tx bytes
account block: <nil>
account: 2 balances + 1 nonces, 1850 tx bytes
```

UTXO ده خروجی Bob، باقی‌مانده‌ی Alice و coinbase ماینر را نگه می‌دارد؛ مدل حساب دو موجودی و یک nonce. تراکنش حساب ۱۸۵ بایت است و UTXO با یک ورودی و دو خروجی ۲۳۳ بایت؛ هر دو کلید عمومی ۶۵ بایتی دارند، پس این‌ها اندازه‌ی بیت‌کوین یا اتریوم نیستند.

## UTXO در برابر حساب

| | UTXO | حساب |
|---|---|---|
| state | خروجی‌های خرج‌نشده (اینجا ۱۲) | موجودی و nonce برای هر آدرس (اینجا ۳) |
| جلوگیری از replay | خروجی خرج‌شده دیگر نیست | nonce، و chain ID بین زنجیره‌ها |
| خواندن موجودی | جمع روی خروجی‌ها | یک خواندن از map |
| کار کیف‌پول | انتخاب خروجی، ساختن باقی‌مانده | هیچ |
| تداخل | فقط اگر دو تراکنش ورودی مشترک داشته باشند | تراکنش‌های یک فرستنده به ترتیب nonce |
| عادت حریم خصوصی | باقی‌مانده می‌تواند به آدرس تازه برود | یک آدرس تاریخچه‌اش را جمع می‌کند |

در UTXO هر {{< term "double-spend" "double spend" >}} از خود ورودی‌ها پیداست، پس تراکنش‌های مستقل جدا چک می‌شوند. در مدل حساب دو تراکنش روی یک موجودی باید به ترتیب اجرا شوند. مدل حساب برای کیف‌پول ساده‌تر است و قراردادهای اتریوم روی آن ساخته شده‌اند.

## دام‌های nonce

- chain ID و nonce را داخل بایت‌های امضاشده بگذارید؛ فیلدی که بیرون sighash باشد از چیزی محافظت نمی‌کند.
- شکاف nonce را رد کنید یا در صف بگذارید، ولی هرگز خارج از ترتیب اجرا نکنید.
- یک nonce گیرکرده همه‌ی تراکنش‌های بعدی آن فرستنده را نگه می‌دارد.
- بلاک را روی کپی state اجرا کنید، مثل مجموعه‌ی UTXO.

## تمرین

۱. یک `MaxNonceGap` اضافه کنید و تراکنش‌ها را تا آن حد در صف نگه دارید و وقتی شکاف بسته شد اجرا کنید.
۲. `PubKey` را با امضای ۶۵ بایتی قابل بازیابی (`ecdsa.SignCompact` در کتاب‌خانه) عوض کنید و فرستنده را از آن دربیاورید.
۳. تستی بنویسید که یک تراکنش امضاشده با chain ID صفر را هر دو زنجیره رد کنند.

## قدم بعدی

پست بعد: **Proof of Work، difficulty و mining**. ساختن بلاک گران می‌شود، و همین تعیین می‌کند کدام زنجیره برنده است.
