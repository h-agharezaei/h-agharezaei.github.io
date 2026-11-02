+++
date = '2026-11-08T18:00:00+03:30'
draft = false
title = 'Proof of Work، difficulty و mining'
description = 'Proof of Work در Go: فیلد nonce و bits در header، ماین کردن و اعتبارسنجی، دو برابر شدن hash با هر بیت، retarget محدودشده و chainwork.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-work", "mining", "bitcoin"]
cover = { image = "/images/covers/bc-proof-of-work-mining.fa.png", alt = "Proof of Work، difficulty و mining", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/bc-account-model-nonce/) مدل حساب را دیدیم. تا اینجا هر کسی می‌توانست در چند میکروثانیه یک بلاک معتبر بسازد. در [بلاکچین از دید برنامه‌نویس](/fa/posts/bc-blockchain-for-programmers/) گفتم زنجیره‌ی hash فقط دستکاری را آشکار می‌کند و گران کردن بازنویسی بعداً می‌آید. این همان پست است.

در [consensus و Raft](/fa/posts/ds-consensus-raft/) توافق بین فهرست مشخصی از سرورها بود که هر کدام یک رأی داشتند. شبکه‌ی باز فهرست ندارد: هر کسی می‌تواند هزار نود بالا بیاورد. {{< term "proof-of-work" "Proof of Work" >}} به‌جای «هر نود یک رأی» می‌گوید «هر واحد محاسبه یک رأی».

ماژول `toychain` پست قبل را کپی و پکیج `chain` را گسترش دادم؛ بلاک‌ها هنوز UTXO دارند.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است. load average ماشین حدود ۳ بود، پس به‌جای زمان، تعداد hash را نشان می‌دهم.

## دو فیلد تازه در header

```go
type Header struct {
	Height     uint64
	Timestamp  int64
	PrevHash   Hash
	MerkleRoot Hash
	TxCount    uint32
	Bits       uint32 // the hash must start with this many zero bits
	Nonce      uint64 // changed by the miner until it does
}
```

{{< term "block-header" "header" >}} حالا ۹۶ بایت است. بلاک فقط وقتی معتبر است که `SHA-256(header)` دست‌کم `Bits` بیت صفر در ابتدا داشته باشد؛ یعنی hash به‌عنوان عدد از `2^(256-Bits)` کوچک‌تر باشد. میان‌بری وجود ندارد: {{< term "mining" "mining" >}} یعنی امتحان کردن مقدارهای {{< term "nonce" "nonce" >}} یکی‌یکی:

```go
func Mine(h Header, maxTries uint64) (Header, uint64, bool) {
	for tries := uint64(1); tries <= maxTries; tries++ {
		if h.MeetsTarget() {
			return h, tries, true
		}
		if tries == maxTries || h.Nonce == math.MaxUint64 {
			return h, tries, false
		}
		h.Nonce++
	}
	return h, 0, false
}
```

چرا بیت صفر و نه target بیت‌کوین؟ طبق مستندات بیت‌کوین، header آن یک {{< term "difficulty-target" "target" >}} کامل ۲۵۶ بیتی را به شکل فشرده نگه می‌دارد، پس سختی با هر ضریبی جابه‌جا می‌شود. بیت صفر خواناتر است، ولی سختی فقط دو برابر یا نصف می‌شود؛ هزینه‌اش را در جدول retarget می‌بینیم.

`go run ./cmd/toychain mine` یک بلاک genesis را با سه سختی ماین می‌کند:

```
bits  8: nonce      28,      29 hashes, hash 002acbe8e52ec14be233...
bits 16: nonce   49014,   49015 hashes, hash 0000af50878911463738...
bits 20: nonce 1908273, 1908274 hashes, hash 0000084c8f5cc05e63b2...
timestamp +1 after mining: 3c89edab33b4024d79b0..., meets target: false
```

ماین کردن تا ۱.۹ میلیون hash طول کشید؛ چک کردن یک hash است. با تغییر هر فیلد، کار از دست می‌رود.

## هر بیت کار را دو برابر می‌کند

یک بلاک شانس است؛ `go run ./cmd/toychain tries` برای هر سختی روی ۲۵۶ header میانگین می‌گیرد:

```
bits   avg hashes     2^bits    vs prev
   8          245        256          -
   9          506        512      2.07x
  10         1178       1024      2.33x
  11         2044       2048      1.73x
  12         4071       4096      1.99x
  13         8113       8192      1.99x
  14        17520      16384      2.16x
  15        29389      32768      1.68x
  16        66541      65536      2.26x
  17       145265     131072      2.18x
  18       290333     262144      2.00x
```

امید ریاضی `2^Bits` است و هر بیت اضافه تقریباً دو برابرش می‌کند؛ تک‌قدم‌ها نویز دارند، از 1.68x تا 2.33x.

## اعتبارسنجی

`AddBlock` حالا چک می‌کند: اتصال، timestamp بعد از والد، برابری `Bits` با قواعد، proof of work، و بعد Merkle root و تراکنش‌ها. `go run ./cmd/toychain powcheck`:

```
required bits: 8
unmined block:         block 1: hash does not meet the difficulty target
own bits 2 (21 hashes): block 1: wrong difficulty bits
mined, then tx edited: block 1: merkle root does not match transactions
mined (87 hashes):    <nil>
chainwork: genesis 256, tip 512
```

ماینر نمی‌تواند سختی آسان برای خودش انتخاب کند.

## Retarget

توان hash عوض می‌شود؛ نرخ بلاک نباید عوض شود. هر `RetargetInterval` بلاک، `NextBits` مدت دوره‌ی قبل را با مدت مطلوب مقایسه می‌کند و `Bits` را به نزدیک‌ترین توان دو می‌برد، حداکثر ۲ بیت (۴ برابر) در هر جهت. فقط حساب صحیح، تا همه‌ی نودها دقیقاً یک جواب بگیرند:

```go
w2, a2 := want*want, actual*actual
switch {
case w2 >= 8*a2: // at least 2^1.5 times too fast
	delta = 2
case w2 >= 2*a2:
	delta = 1
case a2 >= 8*w2:
	delta = -2
case a2 >= 2*w2:
	delta = -1
}
```

تا جایی که می‌دانم بیت‌کوین این کار را هر ۲۰۱۶ بلاک با همان سقف ۴ برابر می‌کند. پیش‌فرض من ۸ بلاک است تا دموهای بعدی کوتاه بمانند. `go run ./cmd/toychain retarget` یک ماینر را شبیه‌سازی می‌کند: در هر ثانیه‌ی فرضی `hashrate` nonce امتحان می‌کند و بعد timestamp را جلو می‌برد. hashها واقعی‌اند؛ فقط ساعت فرضی است. با دوره‌ی ۸ بلاکی نویز سیگنال را می‌پوشاند، پس این دمو ۳۲ بلاک می‌گیرد:

```
retarget every 32 blocks, target 10s per block, genesis bits 12
  heights   hashrate  bits  avg spacing     hashes    chainwork
   1-31        400/s    12        10.8s     127388       131072
  32-63        400/s    12        10.4s     127554       262144
  64-95       1600/s    12         3.6s     156288       393216
  96-127      1600/s    13         6.2s     295686       655360
 128-159      1600/s    14         9.8s     476788      1179648
 160-191       200/s    14        67.3s     427326      1703936
 192-223       200/s    12        24.3s     152411      1835008
 224-255       200/s    11         9.9s      60120      1900544
validate: <nil>
```

در ارتفاع ۶۴ توان hash چهار برابر شد: بلاک هر ۳.۶ ثانیه به‌جای ۱۰. دوره کمتر از 2^1.5 برابر سریع بود، پس {{< term "difficulty-adjustment" "retarget" >}} یک بیت اضافه کرد و دوره‌ی بعد یکی دیگر. با افت هشت‌برابری توان hash، سقف فقط −۲ بیت اجازه داد و برگشتن دو دوره طول کشید.

## Chainwork

ستون آخر {{< term "chainwork" "chainwork" >}} است: جمع `2^Bits` روی همه‌ی بلاک‌ها، یعنی امید ریاضی تعداد hashهای پشت tip. دو پست بعد، نودها زنجیره‌ای را انتخاب می‌کنند که بیشترین کار را دارد، نه بیشترین بلاک را.

## چرا جلوی Sybil را می‌گیرد

در {{< term "sybil-attack" "حمله‌ی Sybil" >}} یک نفر خودش را جای چند نفر جا می‌زند؛ با یک رأی برای هر نود، هزار نود جعلی برنده می‌شوند. با proof of work هویت جعلی هزینه‌ای ندارد و چیزی هم اضافه نمی‌کند؛ فقط hash حساب می‌شود و hash برق و سخت‌افزار می‌خواهد. بازنویسی یک بلاک یعنی انجام دوباره‌ی کار آن و همه‌ی کار بعدش، سریع‌تر از بقیه‌ی شبکه.

## چند نکته‌ی مهم

- proof of work را قبل از چک‌های گران بررسی کنید و `Bits` را با قاعده‌ی خودتان مقایسه کنید، نه با ادعای بلاک.
- در کد consensus عدد صحیح به کار ببرید؛ ممیز شناور ممکن است متفاوت گرد شود.
- timestamp ورودی retarget است. من فقط صعودی بودنش را می‌خواهم؛ تا جایی که می‌دانم بیت‌کوین می‌خواهد بعد از میانه‌ی ۱۱ بلاک قبلی باشد و زیاد در آینده نباشد.

## تمرین

۱. `Bits` را با یک target ۲۵۶ بیتی (`math/big`) عوض کنید و retarget را با نسبت دقیق انجام دهید، باز هم با سقف ۴ برابر.
۲. قاعده‌ی «حداکثر دو ساعت در آینده» را با یک تست اضافه کنید.
۳. شبیه‌سازی retarget را با دوره‌های ۸، ۳۲ و ۱۲۸ اجرا کنید و پراکندگی فاصله‌ی بلاک‌ها را مقایسه کنید.

## قدم بعدی

پست بعد: **شبکه‌ی P2P و gossip بین نودها**. چند نود تراکنش و بلاک را روی TCP با هم رد و بدل می‌کنند.
