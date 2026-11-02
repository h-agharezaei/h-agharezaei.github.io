+++
date = '2027-06-14T10:00:00+03:30'
draft = false
title = 'هش، بلاک و زنجیره: اولین بلاکچین با Go'
description = 'اولین بلاکچین با Go: ویژگی‌های SHA-256، header بلاک با encoding یکتا، genesis، اضافه‌کردن بلاک، اعتبارسنجی و کشف دستکاری با خروجی واقعی.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "sha-256", "hashing", "serialization"]
cover = { image = "/images/covers/bc-hashes-blocks-chain.fa.png", alt = "هش، بلاک و زنجیره: اولین بلاکچین با Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/bc-blockchain-for-programmers/) ایده را دیدیم: رکوردهایی که با hash به هم وصل‌اند، پس تغییر یکی همه‌ی پیوندهای بعدی را می‌شکند. حالا آن را به کد تبدیل می‌کنیم. این مقاله یک ماژول کوچک Go را شروع می‌کند که بقیه‌ی بخش اول دوره همین را گسترش می‌دهد. امروز: {{< term "sha-256" "SHA-256" >}} چه قولی می‌دهد، بلاک چیست، چرا بایت‌های hash‌شده باید دقیق تعریف شوند و زنجیره چطور خودش را چک می‌کند. proof of work بعداً می‌آید.

همین ترفند پیوند در [لاگ، audit و واکنش به حادثه](/fa/posts/sec-logging-audit-incident-response/) هم آمد، و گیت هم objectهایش را با hash نام‌گذاری می‌کند ([گیت چطور فکر می‌کند: object و hash](/fa/posts/git-how-git-thinks/)).

> همه‌ی مثال‌ها را با Go 1.27 روی macOS (arm64) اجرا کرده‌ام. کد یک مثال محلی است، نه repo منتشرشده.

## ساختار ماژول

```
toychain/
  go.mod                 module toychain
  chain/hash.go          Hash, Sum
  chain/block.go         Header, Block, Genesis
  chain/chain.go         Chain, Append, ValidateBlocks
  chain/chain_test.go
  cmd/toychain/main.go   demos: go run ./cmd/toychain <name>
```

مقاله‌های بعدی به `chain` اضافه می‌کنند، بازنویسی‌اش نمی‌کنند.

## SHA-256 چه می‌دهد

یک تابع hash رمزنگاری هر ورودی را به یک digest با اندازه‌ی ثابت می‌برد؛ برای SHA-256 سی‌ودو بایت. امروز دو ویژگی مهم است: قطعی است، و تغییر کوچک در ورودی حدود نصف بیت‌های خروجی را عوض می‌کند، یعنی {{< term "avalanche-effect" "اثر بهمنی" >}}. به این هم تکیه می‌کنیم که کسی نتواند دو ورودی با digest یکسان پیدا کند؛ این به سال‌ها تحلیل عمومی رمزنگاری متکی است، نه به چیزی که بشود تستش کرد.

```go
type Hash [32]byte

func Sum(b []byte) Hash { return sha256.Sum256(b) }
```

دستور `go run ./cmd/toychain sha` یک پیام را دو بار hash می‌کند، بیت آخرش را برمی‌گرداند (`0` می‌شود `1`)، بعد همین کار را روی ۱۰٬۰۰۰ ورودی تصادفی ۶۴ بایتی تکرار می‌کند:

```
same input twice:
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
one bit flipped: "alice -> bob: 11"
  e15286f848d3de8b06620811c49d4e31160f86ce4992e11f8833f77851a375ac
differing bits: 120 of 256
10000 trials: min 98, avg 128.1, max 161 differing bits
```

یک بیت تغییر در ورودی، ۱۲۰ بیت در خروجی؛ میانگین ۱۲۸٫۱، یعنی نصف ۲۵۶، همان انتظار از یک تابع شبه‌تصادفی.

## بلاک و header آن

هر بلاک یک {{< term "block-header" "header" >}} کوچک و یک payload دارد. فقط header hash می‌شود؛ payload از طریق hash خودش وارد header می‌شود، جایی که مقاله‌ی بعد بهترش می‌کند.

```go
type Header struct {
	Height    uint64 // 0 for genesis
	Timestamp int64  // unix seconds
	PrevHash  Hash   // hash of the previous block header, zero for genesis
	DataHash  Hash   // SHA-256 of the block data
}

type Block struct {
	Header Header
	Hash   Hash
	Data   []byte
}
```

`PrevHash` همان پیوند است. هر header به همه‌ی تاریخچه‌ی قبل از خودش متعهد است و زنجیره را یک {{< term "hash-chain" "زنجیره‌ی hash" >}} می‌کند.

## بایت‌هایی که hash می‌کنید باید دقیق تعریف شوند

hash روی بایت‌ها حساب می‌شود، نه روی «همان object». اگر دو نود یک header را متفاوت serialize کنند، دو id متفاوت می‌گیرند و سر زنجیره توافق نمی‌کنند. خروجی `go run ./cmd/toychain encoding`:

```
json.Marshal:        {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  9ad464a5d059
Encoder, no escape:  {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  1e65ec03e3fb
map via json.Marshal: {"amount":10,"from":"alice","to":"bob"}
"ab"+"c" vs "a"+"bc" same hash: true
header bytes (80): 0000000000000001000000006553f13c...
```

یک پرداخت، دو hash: `json.Marshal` به‌طور پیش‌فرض `<` و `>` را برای HTML escape می‌کند، ولی `Encoder` با `SetEscapeHTML(false)` نه. Go کلیدهای map را sort می‌کند، پس خط map در Go پایدار است، اما زبان‌های دیگر انتخاب دیگری دارند (`JSON.stringify` در JavaScript ترتیب درج کلیدهای معمولی را نگه می‌دارد)، و فاصله‌ها، فرمت عدد و escape یونیکد هم فرق می‌کنند. خط چهارم نشان می‌دهد که چسباندن ساده مبهم است: مرز فیلدها گم می‌شود.

پس header یک {{< term "canonical-encoding" "encoding یکتا" >}} می‌گیرد: فیلدهای با طول ثابت، big-endian و با ترتیب ثابت. طول هر فیلد معلوم است، پس نتیجه همیشه ۸۰ بایت بی‌ابهام است.

```go
func (h Header) Encode() []byte {
	buf := make([]byte, 0, HeaderSize)
	buf = binary.BigEndian.AppendUint64(buf, h.Height)
	buf = binary.BigEndian.AppendUint64(buf, uint64(h.Timestamp))
	buf = append(buf, h.PrevHash[:]...)
	buf = append(buf, h.DataHash[:]...)
	return buf
}

func (h Header) Hash() Hash { return Sum(h.Encode()) }
```

## genesis، اضافه‌کردن، اعتبارسنجی

{{< term "genesis-block" "بلاک genesis" >}} تنها بلاکی است که والد ندارد: ارتفاع ۰ و `PrevHash` تمام‌صفر. `Append` روی نوک زنجیره می‌سازد:

```go
func (c *Chain) Append(ts int64, data []byte) Block {
	tip := c.Tip()
	b := NewBlock(tip.Header.Height+1, tip.Hash, ts, data)
	c.blocks = append(c.blocks, b)
	return b
}
```

`ValidateBlocks` به هیچ مقدار ذخیره‌شده‌ای اعتماد نمی‌کند. برای هر بلاک ارتفاع را چک می‌کند، hash داده و hash header را دوباره حساب می‌کند و `PrevHash` را با hash بلاک قبلی مقایسه می‌کند. اولین مشکل را به شکل یک sentinel error پیچیده‌شده برمی‌گرداند.

## دستکاری، واقعی

`go run ./cmd/toychain chain` چهار بلاک با timestamp ثابت می‌سازد و بعد یک کپی را در سه قدم دستکاری می‌کند:

```
  #0 prev=-            hash=4d7f75130edb data="genesis"
  #1 prev=4d7f75130edb hash=056ffcc052ff data="alice -> bob: 10"
  #2 prev=056ffcc052ff hash=75a7ae117b39 data="bob -> carol: 4"
  #3 prev=75a7ae117b39 hash=5be1abf7508b data="carol -> dave: 1"
validate: <nil>
edit data:       block 1: data hash does not match data
rehash block 1:  block 2: previous hash does not match
rebuild rest:    <nil>
tip before: 5be1abf7508b tip after: a571aac4dcd0
```

تغییر داده در بلاک ۱ گیر می‌افتد. درست‌کردن hashهای بلاک ۱ شکستگی را به بلاک ۲ می‌برد. بازسازی همه‌ی بلاک‌های بعدی کپی را دوباره معتبر می‌کند، ولی با hash نوک متفاوت. اعتبارسنجی به‌تنهایی دو تاریخچه را تشخیص نمی‌دهد؛ نسخه‌ی واقعی را این حفظ می‌کند که دیگران hash نوکش را دارند و، بعدتر، بازسازی هزینه دارد. `go test ./...` همین حالت‌ها را به شکل table test تکرار می‌کند.

## چند نکته‌ی مهم

- یک encoding یکتا که خودتان کنترلش می‌کنید را hash کنید، نه `fmt.Sprintf("%v")` یا خروجی پیش‌فرض یک کتاب‌خانه‌ی JSON.
- به هر فیلد با طول متغیر یک پیشوند طول یا طول ثابت بدهید؛ چسباندن ساده مبهم است.
- hash را برای راحتی ذخیره کنید، ولی موقع اعتبارسنجی همیشه دوباره حسابش کنید.
- hash تغییر را نشان می‌دهد، نه اینکه چه کسی آن را انجام داده. امضا بعداً می‌آید.

## تمرین

۱. فیلد `Version uint32` را به header اضافه کنید و `Encode` و `HeaderSize` را به‌روز کنید. کدام تست به‌روز نکردن را می‌گیرد؟
۲. کاری کنید `ValidateBlocks` بلاکی را که timestamp آن از والدش قدیمی‌تر است رد کند.
۳. یک `Decode([]byte) (Header, error)` بنویسید و تستی که نشان دهد `Decode(h.Encode())` همان `h` را برمی‌گرداند.

## قدم بعدی

مقاله‌ی بعد «Merkle tree و اثبات عضویت» است. آن `DataHash` تکی به root یک لیست تراکنش تبدیل می‌شود و ثابت می‌کنیم یک تراکنش در بلاک هست، بدون فرستادن بقیه.
