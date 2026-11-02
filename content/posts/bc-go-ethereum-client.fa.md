+++
date = '2027-06-29T10:00:00+03:30'
draft = false
title = 'کار با اتریوم از Go با go-ethereum'
description = 'go-ethereum در Go: chain ID، موجودی به wei، تراکنش امضاشده‌ی EIP-1559، فراخوانی توکن با abigen، decode خطای سفارشی و مدیریت nonce در ارسال هم‌زمان.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "go-ethereum", "erc20"]
cover = { image = "/images/covers/bc-go-ethereum-client.fa.png", alt = "کار با اتریوم از Go با go-ethereum", hiddenInSingle = true }
+++

در [توکن‌ها: ERC-20 و ERC-721](/fa/posts/bc-erc20-erc721/) قرارداد `DemoToken` را روی anvil دیپلوی کردیم و با `cast` جابه‌جایش کردیم. یک backend همین کار را از داخل کد می‌کند: سرویسی که واریزها را می‌پاید، worker پرداخت، یا یک صرافی. این پست همین کار را از Go با {{< term "go-ethereum" "go-ethereum" >}} انجام می‌دهد، همان کتاب‌خانه‌ای که کلاینت geth رویش ساخته شده.

زیر کار، هر فراخوانی یک درخواست {{< term "json-rpc" "JSON-RPC" >}} روی HTTP است، مثل API نود کوچک [جمع‌بندی بخش اول: یک نود کامل کوچک با Go](/fa/posts/bc-toy-node-go/). nonce هم از [مدل حساب، nonce و جلوگیری از replay](/fa/posts/bc-account-model-nonce/) برمی‌گردد، این بار با یک نود واقعی.

> اجرا با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10 و Foundry 1.8.7. یک anvil تازه روی `127.0.0.1:8545` با همان اسکریپت دیپلوی پست قبل، پس توکن همان آدرس را دارد. کلیدهای خصوصی داخل کد کلیدهای تست عمومی anvil هستند: هیچ‌جای واقعی از آن‌ها استفاده نکنید.

## اتصال، chain ID و موجودی

```
$ curl -s -X POST -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x7a69"}
```

`ethclient` همین فراخوانی‌ها را در متدهایی با نوع مشخص می‌پیچد:

```go
client, err := ethclient.DialContext(ctx, "http://127.0.0.1:8545")
chainID, err := client.ChainID(ctx)
head, err := client.BlockNumber(ctx)
bal, err := client.BalanceAt(ctx, addr0, nil) // nil = latest block
fmt.Println("balance ETH: ", formatUnits(bal, 18))
```

موجودی عدد صحیح به {{< term "wei" "wei" >}} است، 10^18 تا برای هر ether، پس خیلی زود در `uint64` جا نمی‌شود. go-ethereum از `*big.Int` استفاده می‌کند و من هم با تقسیم صحیح نمایشش می‌دهم، هرگز با `float64`:

```go
func formatUnits(v *big.Int, decimals int) string {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(decimals)), nil)
	q, r := new(big.Int).QuoRem(v, unit, new(big.Int))
	return fmt.Sprintf("%s.%0*s", q, decimals, r.String())
}
```

```
$ go run ./cmd/ethdemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

`0x7a69` همان 31337 است، {{< term "chain-id" "chain ID" >}} پیش‌فرض anvil. حساب ۰ کارمزد سه تراکنش دیپلوی را داده، برای همین کمی زیر ۱۰٬۰۰۰ است.

## یک تراکنش EIP-1559 با دست

از {{< term "eip-1559" "EIP-1559" >}} به بعد هر بلاک یک base fee دارد که پروتکل تعیینش می‌کند و سوزانده می‌شود؛ تراکنش یک tip برای تولیدکننده‌ی بلاک و یک سقف برای کل کارمزد اضافه می‌کند. تا جایی که من می‌فهمم base fee در هر بلاک حداکثر ۱۲.۵ درصد بالا می‌رود، پس «دو برابر base fee فعلی به‌اضافه‌ی tip» برای چند بلاک پر جا می‌گذارد. این یک قاعده‌ی سرانگشتی رایج است، نه قانون.

```go
nonce, err := c.PendingNonceAt(ctx, from)
head, err := c.HeaderByNumber(ctx, nil)
tip, err := c.SuggestGasTipCap(ctx)
feeCap := new(big.Int).Add(new(big.Int).Mul(head.BaseFee, big.NewInt(2)), tip)

tx := types.NewTx(&types.DynamicFeeTx{
	ChainID: chainID, Nonce: nonce, GasTipCap: tip, GasFeeCap: feeCap,
	Gas: 21000, To: &acct1, Value: value, // 1.5 ETH in wei
})
signed, err := types.SignTx(tx, types.LatestSignerForChainID(chainID), key)
err = c.SendTransaction(ctx, signed)
rcpt, err := bind.WaitMined(ctx, c, signed.Hash())
```

```
$ go run ./cmd/ethdemo send
nonce: 3 base fee: 783421165 tip: 1000000000 fee cap: 2566842330
tx type: 2 hash: 0xecb131b439f7991150b056891e303b98c8539a0ce8c5e687564fe175c9c0cd4b
status: 1 block: 4 gas used: 21000 effective gas price: 1685976107
account 1 gained: 1.500000000000000000 ETH
```

سقف فقط سقف است. base fee بلاک ۴ برابر 685976107 بود (`cast block 4 --field baseFeePerGas`)، پس تراکنش برای هر واحد gas همان مقدار به‌اضافه‌ی ۱ gwei tip پرداخت. chain ID هم مثل پست nonce داخل داده‌ی امضاشده است.

## فراخوانی توکن با abigen

{{< term "contract-abi" "ABI" >}} رابط JSON قرارداد است. پروژه‌ی Foundry پست قبل را کپی کردم، `forge build` را اجرا کردم، ABI را از `out/` برداشتم و با {{< term "abigen" "abigen" >}} کد Go ساختم:

```
$ go run github.com/ethereum/go-ethereum/cmd/abigen@v1.17.10 --v2 \
    --abi abi/DemoToken.abi --pkg token --type DemoToken --out token/token.go
```

`--v2` را انتخاب کردم چون در v1.17.10 پکیج قدیمی `bind` به نفع `bind/v2` منسوخ (deprecated) اعلام شده. کد v2 فقط pack و unpack می‌کند و فراخوانی از `bind` می‌گذرد:

```go
demo := token.NewDemoToken()
inst := demo.Instance(c, tokenAddr)
dec, err := bind.Call(inst, call, demo.PackDecimals(), demo.UnpackDecimals)
opts := bind.NewKeyedTransactor(key, chainID)
tx, err := bind.Transact(inst, opts, demo.PackTransfer(acct1, amount))
rcpt, err := bind.WaitMined(ctx, c, tx.Hash())
ev, err := demo.UnpackTransferEvent(rcpt.Logs[0])
```

```
$ go run ./cmd/ethdemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO | account 1: 0.000000000000000000 DEMO
transfer tx type: 2 status: 1 gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 0: 999900.000000000000000000 DEMO | account 1: 100.000000000000000000 DEMO
```

`bind.Transact` خودش nonce، سقف gas و کارمزد را پر کرد و باز هم تراکنش نوع ۲ ساخت. gas مصرفی 52383 است، همان عدد `cast send` در پست قبل.

## decode کردن خطای سفارشی

حساب ۲ هیچ DEMO ندارد. وقتی می‌خواهد ۱ DEMO بفرستد، `bind.Transact` اول از نود تخمین gas می‌خواهد، فراخوانی شبیه‌سازی‌شده {{< term "revert" "revert" >}} می‌شود و چیزی ارسال نمی‌شود. خطا داده‌ی revert را با خودش دارد:

```go
var de rpc.DataError
if errors.As(err, &de) {
	data, _ := hexutil.Decode(fmt.Sprint(de.ErrorData()))
	decoded, err := demo.UnpackError(data)
	if e, ok := decoded.(*token.DemoTokenInsufficientBalance); ok { /* ... */ }
}
```

```
$ go run ./cmd/ethdemo revert
raw error: execution reverted: custom error 0xdb42144d: 0000000000000000000000003c44cdddb6a900fa2b585dd299e03d12fa4293bc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000de0b6b3a7640000
revert data: db42144d... (100 bytes)
InsufficientBalance: from 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC balance 0 needed 1000000000000000000
```

۴ بایت اول selector خطاست که مثل {{< term "function-selector" "function selector" >}} ساخته می‌شود؛ بعد سه کلمه‌ی ۳۲ بایتی می‌آید. nonce حساب ۲ صفر ماند.

## nonce با چند فرستنده‌ی هم‌زمان

پنج goroutine هم‌زمان از حساب ۰ تراکنش می‌فرستند. در دور اول هر کدام `PendingNonceAt` را می‌پرسد؛ در دور دوم یک شمارنده‌ی محافظت‌شده با mutex {{< term "nonce" "nonce" >}} را پخش می‌کند. برای اینکه race هر بار دیده شود، همه‌ی goroutineها قبل از ارسال nonce خودشان را می‌گیرند:

```go
type nonceManager struct {
	mu   sync.Mutex
	next uint64
}

func (m *nonceManager) Next() uint64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	n := m.next
	m.next++
	return n
}
```

```
$ go run ./cmd/ethdemo nonces
PendingNonceAt in every goroutine:
   nonce 5: replacement transaction underpriced
   nonce 5: <nil>
   nonce 5: replacement transaction underpriced
   nonce 5: replacement transaction underpriced
   nonce 5: replacement transaction underpriced
local nonce manager:
   nonce 7: <nil>
   nonce 8: <nil>
   nonce 9: <nil>
   nonce 10: <nil>
   nonce 6: <nil>
mined: 6 txs; account 0 nonce now: 11
```

nonce یکسان با مقدار متفاوت: نود چهار تلاش برای جایگزینی یک تراکنش بدون کارمزد بالاتر می‌بیند. با شمارنده، nonce شماره‌ی ۶ آخر از همه رسید و نود باز هم هر پنج را به ترتیب استخراج کرد. این شمارنده فقط وقتی جواب می‌دهد که تنها فرستنده‌ی آن کلید باشد؛ چند پروسه به یک جای واحد برای پخش nonce نیاز دارند.

## چند نکته‌ی مهم

- مقدارها را از RPC تا دیتابیس `*big.Int` نگه دارید. موجودی حساب ۰ در بالا به شکل `float64` می‌شود 9999997683290179895296.
- `PendingNonceAt` عکسی از دید نود است، نه رزرو.
- تراکنشی که هرگز استخراج نشود همه‌ی nonceهای بالاتر را نگه می‌دارد. برای جایگزینی‌اش با کارمزد بالاتر برنامه داشته باشید.
- داده‌ی revert را فقط وقتی می‌شود decode کرد که ABI همراه آن خطا را داشته باشید.

## تمرین

۱. `feeCap` را کمتر از base fee بگذارید و بفرستید. anvil چه جوابی می‌دهد؟
۲. anvil را با `--no-mining` اجرا کنید و برنامه را بین دو دور شمارنده ری‌استارت کنید. `next` باید از کجا شروع شود؟
۳. با صدا زدن `mint` از حساب ۱ خطای `NotMinter` را decode کنید.

## قدم بعدی

پست بعد: **کار با اتریوم از Rust با alloy**.
