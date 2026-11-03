+++
date = '2026-11-06T18:00:00+03:30'
draft = false
title = 'تراکنش و مدل UTXO'
description = 'تراکنش UTXO در Go: ورودی، خروجی، sighash، txid، coinbase و کارمزد، همراه با رد شدن double spend، امضای جعلی و خرج بیش از موجودی.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "utxo", "transactions", "bitcoin"]
cover = { image = "/images/covers/bc-transactions-utxo.fa.png", alt = "تراکنش و مدل UTXO", hiddenInSingle = true }
+++

بلاک‌های [Merkle tree و اثبات عضویت](/fa/posts/bc-merkle-trees-proofs/) هنوز بایت خام مثل `"alice -> bob: 10"` دارند که هر کسی می‌تواند بنویسد. پکیج `wallet` [پست قبلی](/fa/posts/bc-keys-ecdsa-addresses/) یک hash سی‌ودو بایتی را امضا می‌کند، پس این پست آن رشته‌ها را با تراکنش واقعی عوض می‌کند: سکه مال کیست، چه کسی اجازه‌ی خرجش را دارد و نود چه چیزی را چک می‌کند. این مدل بیت‌کوین است، مدل {{< term "utxo" "UTXO" >}}. تراکنش دیتابیس در [تراکنش و ACID](/fa/posts/db-transactions-acid/) چیز دیگری است که فقط اسمش یکی است.

ماژول `toychain` پست Merkle را کپی کردم و پکیج `wallet` را هم داخلش به‌عنوان `wallet/` کپی کردم تا همه یک ماژول باشد. یک helper هم به `wallet` اضافه کردم: `AddressBytes` که آدرس خام ۲۰ بایتی را می‌دهد.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است. کلیدها از کلمه‌هایی مثل "alice" ساخته شده‌اند؛ عمومی‌اند، هرگز پولی نگرفته‌اند و فقط برای این دمو هستند.

## ورودی و خروجی

موجودی وجود ندارد، فقط خروجی هست: «۵۰ سکه، متعلق به این آدرس». هر تراکنش خروجی‌های قبلی را مصرف می‌کند و خروجی تازه می‌سازد:

```go
type OutPoint struct {
	TxID  Hash
	Index uint32
}

type TxIn struct {
	Prev   OutPoint
	PubKey []byte // must hash to the owner of Prev
	Sig    []byte // 64 bytes, r || s
}

type TxOut struct {
	Value uint64
	Owner Address // 20 bytes
}

type Tx struct {
	Inputs  []TxIn
	Outputs []TxOut
}
```

خروجی کامل خرج می‌شود. برای پرداخت ۳۰ از یک خروجی ۵۰ سکه‌ای، Alice دو خروجی می‌سازد: ۳۰ برای Bob و ۱۵ به‌عنوان باقی‌مانده (change) برای خودش. آن ۵ سکه‌ی گم‌شده کارمزد است: `fee = sum(inputs) - sum(outputs)`.

## چه چیزی امضا می‌شود، شناسه چیست

encoding یکتاست، مثل header در [هش، بلاک و زنجیره](/fa/posts/bc-hashes-blocks-chain/): تعدادها و فیلدهای طول‌ثابت به ترتیب، با پیشوند طول برای کلید و امضا. دو hash از آن درمی‌آید:

```go
func (tx Tx) ID() Hash { return Sum(tx.Encode()) }

func (tx Tx) SigHash() Hash {
	return Sum(append([]byte{0x02}, tx.encode(false)...))
}
```

{{< term "sighash" "sighash" >}} همه‌ی ورودی‌ها و خروجی‌ها را پوشش می‌دهد ولی امضاها را خالی می‌نویسد، چون امضا نمی‌تواند خودش را امضا کند. txid همه چیز را پوشش می‌دهد، امضا هم. این فقط به این دلیل امن است که `wallet.Verify` امضای high-S را رد می‌کند؛ وگرنه {{< term "signature-malleability" "malleability" >}} به هر کسی اجازه می‌داد شناسه را عوض کند. پیشوند `0x02` هم sighash را از برگ (`0x00`) و گره‌ی (`0x01`) Merkle جدا نگه می‌دارد.

## Coinbase و مجموعه‌ی UTXO

سکه‌ی تازه از {{< term "coinbase-transaction" "تراکنش coinbase" >}} می‌آید، اولین تراکنش هر بلاک. یک ورودی ساختگی دارد با TxID صفر و ارتفاع بلاک به‌عنوان index، تا دو coinbase که به یک نفر پرداخت می‌کنند باز هم شناسه‌ی متفاوت بگیرند. حداکثر می‌تواند `BlockReward` (۵۰) به‌علاوه‌ی کارمزدهای بلاک را بپردازد.

state یک map است:

```go
type UTXOSet map[OutPoint]TxOut
```

`ApplyBlock` روی یک کپی کار می‌کند. برای هر تراکنش چک می‌کند: هر ورودی در مجموعه هست؛ هیچ خروجی‌ای در بلاک دو بار خرج نشده؛ کلید عمومی به مالک خروجی hash می‌شود؛ {{< term "digital-signature" "امضا" >}} روی sighash درست است؛ `sum(in) >= sum(out)` بدون overflow. بعد خروجی‌های خرج‌شده را حذف و خروجی‌های تازه را اضافه می‌کند. هر خطا کپی را دور می‌ریزد.

## پرداخت با باقی‌مانده

`go run ./cmd/toychain pay`: genesis به Alice پنجاه سکه می‌دهد، بعد او ۳۰ به Bob می‌دهد با ۱۵ باقی‌مانده:

```
after genesis:
  197a84d5374b:0   50  alice
tx ef4d0ece5dfd: 233 bytes, sighash 74a059145008, fee 5, err <nil>
block 1: 2 txs, err <nil>
after block 1:
  569759b941f7:0   55  miner
  ef4d0ece5dfd:0   30  bob
  ef4d0ece5dfd:1   15  alice
balances: alice 15, bob 30, miner 55
validate: <nil>
```

خروجی genesis رفته و miner پنجاه به‌علاوه‌ی ۵ برداشته.

## Double spend

{{< term "double-spend" "double spend" >}} یعنی دو امضای معتبر روی یک سکه. `go run ./cmd/toychain double`:

```
both valid alone: <nil> <nil>
same block: block 1: tx 2: input 0: output spent twice in one block
block 1 with one of them: <nil>
the other in block 2: block 2: tx 1: input 0: input is unknown or already spent
replay toBob in block 2: block 2: tx 1: input 0: input is unknown or already spent
chain length: 2
```

هر پرداخت به‌تنهایی معتبر است؛ با هم، بلاک رد می‌شود. فرستادن دوباره‌ی تراکنش تأییدشده هم شکست می‌خورد: ورودی‌اش دیگر نیست. این‌که کدام پرداخت برنده شود سؤال consensus است و بعداً می‌آید.

## امضای جعلی

`go run ./cmd/toychain forge`، Mallory در برابر سکه‌ی Alice:

```
alice's key, mallory's signature: input 0: bad signature
mallory's key on alice's coin:   input 0: public key does not match the output owner
output rewritten after signing:  input 0: bad signature
change lowered after signing:    input 0: bad signature
```

خط آخر مهم است: کارمزد فیلد نیست، باقی‌مانده‌ی ورودی‌هاست. کم کردن change کارمزد را بالا می‌برد، و چون خروجی‌ها امضا شده‌اند، گیر می‌افتد.

## خرج بیش از موجودی و کارمزد

`go run ./cmd/toychain overspend`:

```
50 in, 60 out: outputs exceed inputs: in 50, out 60
50 in, 50 out: fee 0, err <nil>
50 in, 1 out:  fee 49, err <nil> (forgot the change)
coinbase takes 51 with 0 fees: block 1: tx 0: coinbase pays more than reward + fees or has the wrong height
```

خط سوم معتبر است: خروجی باقی‌مانده را فراموش کنید و miner آن را می‌برد.

تست‌ها خرج کردن خروجی‌ای که در همان بلاک ساخته شده و ویرایش تراکنش تأییدشده را هم پوشش می‌دهند. ضمناً شکاف پست Merkle را هم بستم: {{< term "block-header" "header" >}} حالا به `TxCount` متعهد است و `VerifyInclusion` تعداد را از header می‌گیرد، نه از prover.

```
ok  	toychain/chain	0.413s
?   	toychain/cmd/toychain	[no test files]
ok  	toychain/wallet	(cached)
```

## دام‌های اعتبارسنجی

- هر چیزی را که مهم است امضا کنید. هر چه بیرون sighash باشد را هر کسی می‌تواند عوض کند.
- کارمزد را ورودی منهای خروجی حساب کنید و overflow را چک کنید.
- کل بلاک را روی کپی state اعتبارسنجی کنید، هرگز درجا.
- بیت‌کوین واقعی فرق دارد: تا جایی که می‌دانم خروجی‌ها را با script قفل می‌کند و برای هر ورودی hash جداگانه امضا می‌کند. هیچ‌کدام را پیاده نکردم.

## تمرین

۱. اجازه دهید coinbase چند خروجی داشته باشد و تستی بنویسید که جمعشان هنوز سقف دارد.
۲. فیلد `Locktime` اضافه کنید: تراکنش قبل از آن ارتفاع نامعتبر است. مطمئن شوید امضا می‌شود.
۳. تابع `Select(utxo, owner, amount)` بنویسید که خروجی‌ها را انتخاب کند و خروجی باقی‌مانده را بسازد.

## قدم بعدی

پست بعد: **مدل حساب، nonce و جلوگیری از replay**. اتریوم به‌جای خروجی موجودی نگه می‌دارد و این دفاع دیگری در برابر replay لازم دارد.
