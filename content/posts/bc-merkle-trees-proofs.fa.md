+++
date = '2026-11-04T18:00:00+03:30'
draft = false
title = 'Merkle tree و اثبات عضویت'
description = 'Merkle tree با Go: root درخت در header بلاک، تعداد فرد برگ‌ها، پیشوند برگ و گره در برابر second preimage، و اثبات عضویت با اندازه‌ی واقعی.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "merkle-tree", "hashing", "data-structures"]
cover = { image = "/images/covers/bc-merkle-trees-proofs.fa.png", alt = "Merkle tree و اثبات عضویت", hiddenInSingle = true }
+++

وقتی header مثل [مقاله‌ی قبل](/fa/posts/bc-hashes-blocks-chain/) با یک `DataHash` تکی به payload متعهد است، برای فهمیدن اینکه پرداختی در بلاک هست کل بلاک را لازم دارید. {{< term "merkle-tree" "Merkle tree" >}} این را حل می‌کند: header هنوز ۳۲ بایت نگه می‌دارد، ولی هر کسی با چند hash می‌تواند ثابت کند یک تراکنش در بلاک هست. در [replication و quorum](/fa/posts/ds-replication-quorum/) از آن برای مقایسه‌ی replicaها استفاده کردیم؛ درخت‌ها به‌طور کلی در [درخت جست‌وجو و B-tree](/fa/posts/algo-trees-bst-btree/) آمده‌اند.

ماژول `toychain` مقاله‌ی قبل را کپی کردم و گسترش دادم: `Header.DataHash` شد `MerkleRoot` و `Block.Data` شد `Txs [][]byte`. تراکنش‌ها هنوز payload خام بایتی‌اند؛ تراکنش امضاشده در دو مقاله‌ی بعد می‌آید.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است.

## ساختن درخت

هر تراکنش hash می‌شود و یک برگ می‌سازد. هر والد hash دو فرزندش است. بالای درخت {{< term "merkle-root" "Merkle root" >}} است که در {{< term "block-header" "header" >}} می‌نشیند:

```go
const (
	leafPrefix = 0x00
	nodePrefix = 0x01
)

// LeafHash is SHA-256(0x00 || tx).
func LeafHash(tx []byte) Hash {
	return Sum(append([]byte{leafPrefix}, tx...))
}

// NodeHash is SHA-256(0x01 || left || right).
func NodeHash(left, right Hash) Hash { /* ... */ }

func nextLevel(level []Hash) []Hash {
	next := make([]Hash, 0, (len(level)+1)/2)
	for i := 0; i < len(level); i += 2 {
		if i+1 == len(level) {
			next = append(next, level[i]) // lone node: promoted as is
			break
		}
		next = append(next, NodeHash(level[i], level[i+1]))
	}
	return next
}
```

تعداد فرد یک قاعده می‌خواهد. من گره‌ی تنهای آخر را بدون تغییر بالا می‌برم. بیت‌کوین در عوض آن را تکرار می‌کند. با بالا بردن، شکل درخت همان است که RFC 6962 (Certificate Transparency) تعریف کرده؛ یک تست root من را با پیاده‌سازی مستقیم تعریف بازگشتی RFC برای ۰ تا ۳۰۰ تراکنش مقایسه می‌کند و همه یکی‌اند.

## چرا پیشوند 0x00 و 0x01

بدون آن‌ها برگ و گره‌ی داخلی هر دو «SHA-256 چند بایت»اند، و گره‌ی داخلی hash دقیقاً ۶۴ بایت است. پس یک «تراکنش» ۶۴ بایتی که از چسباندن دو hash فرزند ساخته شده، همان hash آن گره‌ی داخلی را می‌دهد. این یک حمله‌ی {{< term "second-preimage-attack" "second preimage" >}} روی درخت است، نه روی SHA-256. `go run ./cmd/toychain naive` یک درخت بدون پیشوند روی ۴ تراکنش واقعی می‌سازد، بعد روی ۲ تراکنش جعلی که از همان hashهای چسبیده ساخته شده‌اند:

```
naive root, 4 real txs:  472c9838ed30
naive root, 2 fake txs:  472c9838ed30
prefixed root, real:     8e904c88352a
prefixed root, fake:     e0b533a65e8d
```

دو لیست تراکنش متفاوت، یک root. پیشوند 0x00 برای برگ و 0x01 برای گره‌ی داخلی، که به آن {{< term "domain-separation" "domain separation" >}} می‌گویند، این دو نوع hash را در دو فضای جدا می‌گذارد و rootها دوباره متفاوت می‌شوند. RFC 6962 هم همین پیشوندها را دارد.

## تکرار گره‌ی آخر

قاعده‌ی بیت‌کوین یک تله‌ی شناخته‌شده دارد. `go run ./cmd/toychain dup` نسخه‌ی ساده‌شده‌ای از آن را اجرا می‌کند (یک بار SHA-256، بدون پیشوند):

```
duplicate-last [a b c]:   d31a37ef6ac1
duplicate-last [a b c c]: d31a37ef6ac1
promote-last   [a b c]:   36642e73c254
promote-last   [a b c c]: e9636069c740
```

`[a b c]` و `[a b c c]` یک root دارند، پس یک header با دو لیست تراکنش جور درمی‌آید. تا جایی که می‌دانم این مشکل در بیت‌کوین با شناسه‌ی CVE-2012-2459 گزارش شد: می‌شد نود را فریب داد که یک بلاک معتبر را نامعتبر علامت بزند. من چیزی را روی خود بیت‌کوین بازتولید نکردم.

## اثبات عضویت

{{< term "inclusion-proof" "اثبات عضویت" >}} لیست hashهای هم‌سطح (sibling) روی مسیر یک برگ تا root است:

```go
type Proof struct {
	Index    int    // position of the transaction
	TxCount  int    // number of transactions in the tree
	Siblings []Hash // bottom to top; promoted levels have no sibling
}
```

`VerifyProof(root, tx, p)` از `LeafHash(tx)` شروع می‌کند و آن را با هر sibling ترکیب می‌کند. اینکه sibling سمت چپ است یا راست از `Index` و `TxCount` درمی‌آید، نه از حرف اثبات‌کننده، و همه‌ی siblingها باید مصرف شوند. خروجی `go run ./cmd/toychain merkle` با ۵ تراکنش:

```
root of 5 txs: d9f7ce89020c
proof for tx 2 of 5: 3 siblings, 96 bytes
  sibling 0: 5850eb6c9ec8
  sibling 1: 408cc2b42814
  sibling 2: b0bdb971b6f9
verify real tx:    true
verify edited tx:  false
proof for tx 4 (promoted twice): 1 siblings
verify: true
```

تراکنش ۴ در دو سطح گره‌ی تنهاست، پس اثباتش یک hash است. تست‌ها همه‌ی indexها را برای ۱ تا ۷۰ تراکنش چک می‌کنند، به‌علاوه‌ی تراکنش جعلی و index اشتباه.

## اثبات چقدر بزرگ است؟

خروجی `go run ./cmd/toychain sizes`، اثبات برای تراکنش ۰:

```
      txs siblings  proof bytes all leaf hashes
        1        0            0             32
        2        1           32             64
        3        2           64             96
        4        2           64            128
        5        3           96            160
        8        3           96            256
      100        7          224           3200
     1000       10          320          32000
     4096       12          384         131072
  1000000       20          640       32000000
```

اندازه‌ی اثبات با log2 تعداد رشد می‌کند: یک میلیون تراکنش ۲۰ hash می‌خواهد، یعنی ۶۴۰ بایت. whitepaper بیت‌کوین این را {{< term "spv" "simplified payment verification" >}} می‌نامد: کلاینت سبک فقط headerها را نگه می‌دارد و اثبات می‌خواهد.

## برگشت به زنجیره

`ValidateBlocks` حالا root را از `Txs` دوباره حساب می‌کند. تغییر یک تراکنش در بلاک ۱:

```
  #0 prev=-            root=7b5eabeb1bbd hash=759fc6cff9c0 txs=1
  #1 prev=759fc6cff9c0 root=63a5466f1041 hash=cedaf9a6150d txs=3
  #2 prev=cedaf9a6150d root=5850eb6c9ec8 hash=a07354280ad9 txs=1
validate: <nil>
edit one tx: block 1: merkle root does not match transactions
```

root بلاک ۲ با sibling 0 بالا برابر است: root درخت تک‌تراکنشی همان hash برگ آن تراکنش است.

## حدود یک اثبات

- اثبات فقط به اندازه‌ی root معتبر است. root را از headerی بگیرید که خودتان اعتبارسنجی کرده‌اید، نه از اثبات‌کننده.
- قاعده‌ی تعداد فرد را مستند کنید؛ بالا بردن و تکرار root متفاوت می‌دهند.
- hash برگ و گره را جدا کنید. بدون آن درخت می‌شکند، نه SHA-256.
- header ما به تعداد تراکنش‌ها متعهد نیست. امتحان کردم: اثبات تراکنش ۰ از ۵ با ادعای ۶، ۷ یا ۸ تراکنش هم تأیید می‌شود. عضویت درست است، تعداد ثابت نشده.
- عضویت یعنی «این تراکنش در این بلاک هست»، نه اینکه معتبر یا خرج‌نشده است.

## تمرین

۱. تستی بنویسید که نشان دهد `[a b c]` و `[a b c c]` با `MerkleRoot` root متفاوت دارند.
۲. `TxCount` را به header اضافه کنید و کاری کنید verifier تعداد را از آنجا بگیرد.
۳. اثباتی برای دو تراکنش هم‌زمان بنویسید که siblingهای مشترکشان را یک بار بفرستد.

## قدم بعدی

مقاله‌ی بعد «کلید، امضای ECDSA و آدرس روی secp256k1» است: تراکنش‌ها دیگر بایت خام نیستند و امضا می‌شوند.
