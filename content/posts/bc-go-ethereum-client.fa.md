+++
date = '2026-11-18T18:00:00+03:30'
draft = false
title = 'کار با اتریوم از Go با go-ethereum'
description = 'go-ethereum در Go: chain ID، موجودی به wei، تراکنش امضاشده‌ی EIP-1559، فراخوانی توکن با abigen، decode خطای سفارشی و مدیریت nonce در ارسال هم‌زمان.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "go-ethereum", "erc20"]
cover = { image = "/images/covers/bc-go-ethereum-client.fa.png", alt = "کار با اتریوم از Go با go-ethereum", hiddenInSingle = true }
+++

در سه مقاله‌ی قبل همه‌چیز را دستی و در ترمینال با `cast` انجام دادم. برای یادگرفتن خوب است، ولی سیستم‌های واقعی این کارها را از داخل کد می‌کنند: یک برنامه‌ی دیده‌بان واریز که پرداخت‌های ورودی را می‌فهمد، یک worker پرداخت که آن‌ها را می‌فرستد، یا بک‌اند یک صرافی. و کد با دو مشکل روبه‌رو می‌شود که ترمینال قایمشان می‌کند. چند قسمت برنامه ممکن است هم‌زمان بفرستند، و عددها از چیزی که `float64` دقیق نگه می‌دارد بزرگ‌ترند.

این مقاله همان قدم‌ها را از Go با {{< term "go-ethereum" "go-ethereum" >}} انجام می‌دهد، کتابخانه‌ای که پشت کلاینت geth است (یکی از برنامه‌های اصلی که نود اتریوم را اجرا می‌کنند). موجودی می‌خوانیم، یک انتقال ETH امضاشده می‌فرستیم، قرارداد توکن [مقاله‌ی توکن‌ها](/fa/posts/bc-erc20-erc721/) را صدا می‌زنیم، یک شکست را decode می‌کنیم و تراکنش‌ها را هم‌زمان می‌فرستیم.

زیرش جادویی نیست. هر فراخوانی {{< term "json-rpc" "JSON-RPC" >}} روی HTTP است، همان جنس API [نود کوچک](/fa/posts/bc-toy-node-go/): یک درخواست JSON با اسم متد، و یک جواب JSON. nonceهایی که از [مقاله‌ی مدل حساب](/fa/posts/bc-account-model-nonce/) آمده‌اند حالا با یک نود واقعی روبه‌رو می‌شوند.

> همه‌ی مثال‌ها را با Go 1.27 روی macOS (arm64)، go-ethereum v1.17.10 و Foundry 1.8.7 اجرا کرده‌ام. از یک anvil تازه روی `127.0.0.1:8545` و اسکریپت deploy مقاله‌ی قبل استفاده کردم، پس توکن همان آدرس آن‌جا را دارد. کلیدهای خصوصی در کد کلیدهای آزمایشی عمومی anvil هستند: هرگز جای واقعی استفاده‌شان نکنید.

## اتصال، chain ID، موجودی

اول خود پروتکل، تا بدانیم کتابخانه چه چیزی را بسته‌بندی می‌کند. یک `curl` از نود chain ID را می‌پرسد:

```
$ curl -s -X POST -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x7a69"}
```

عددها در این API رشته‌های هگزادسیمال‌اند. `0x7a69` برابر ۳۱۳۳۷ است. بسته‌ی `ethclient` هر کدام از این فراخوانی‌ها را در یک متد تایپ‌دار Go می‌پیچد:

```go
client, err := ethclient.DialContext(ctx, "http://127.0.0.1:8545")
chainID, err := client.ChainID(ctx)
head, err := client.BlockNumber(ctx)
bal, err := client.BalanceAt(ctx, addr0, nil) // nil = latest block
fmt.Println("balance ETH: ", formatUnits(bal, 18))
```

موجودی‌ها عدد صحیح به {{< term "wei" "wei" >}} هستند، ۱۰^۱۸ در هر ether، پس خیلی زود از `uint64` بزرگ‌تر می‌شوند. go-ethereum از `*big.Int` استفاده می‌کند (عدد صحیح با اندازه‌ی دلخواه در Go). برای نمایش موجودی به ETH از تقسیم صحیح و باقی‌مانده استفاده می‌کنم، نه `float64`:

```go
func formatUnits(v *big.Int, decimals int) string {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(decimals)), nil)
	q, r := new(big.Int).QuoRem(v, unit, new(big.Int))
	return fmt.Sprintf("%s.%0*s", q, decimals, r.String())
}
```

`go run ./cmd/ethdemo info` کد اتصال، chain ID و موجودی را اجرا می‌کند:

```
$ go run ./cmd/ethdemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

- **`chain id: 31337`:** همان `0x7a69` در فراخوانی curl است، {{< term "chain-id" "chain ID" >}} پیش‌فرض anvil. chain ID عددی است که یک شبکه را مشخص می‌کند و در هر تراکنش امضاشده می‌رود تا تراکنشی که برای شبکه‌ی آزمایشی امضا شده روی شبکه‌ی دیگری replay نشود.
- **`block number: 3`:** سه تراکنش اسکریپت deploy (دو قرارداد و یک mint) بلاک‌های ۱ تا ۳ را ساخته‌اند.
- **موجودی:** حساب ۰ با ۱۰٬۰۰۰ ETH شروع کرد و برای آن سه تراکنش gas داد، پس کمی کمتر از آن است. خط `wei` و خط ETH یک عددند: یک بار صحیح و یک بار با ممیز.

## تراکنش EIP-1559 به‌صورت دستی

حالا فرستادن. هر تراکنش کارمزد دارد و از زمان {{< term "eip-1559" "EIP-1559" >}} کارمزد دو بخش دارد. هر بلاک یک **base fee** به‌ازای هر واحد gas دارد که پروتکل خودکار تعیین می‌کند و سوزانده می‌شود (به کسی نمی‌رسد). رویش یک **tip** برای تولیدکننده‌ی بلاک اضافه می‌کنید و یک **سقف** تعیین می‌کنید، بیشترین قیمت کل به‌ازای هر gas که قبول دارید. تا جایی که می‌دانم، base fee از یک بلاک تا بلاک بعد حداکثر ۱۲٫۵٪ بالا می‌رود، پس «دو برابر base fee فعلی به‌علاوه‌ی tip» برای چند بلاک پر جا باز می‌گذارد. این یک قاعده‌ی سرانگشتی رایج است، نه قانون.

این کد تراکنش را دستی می‌سازد، امضا می‌کند و می‌فرستد:

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

قدم‌به‌قدم: nonce شماره‌ی تراکنش بعدی حساب است (همان محافظت از replay در مقاله‌ی مدل حساب). نود base fee آخر و یک tip پیشنهادی را می‌گوید. `Gas: 21000` هزینه‌ی ثابت یک انتقال ساده‌ی ETH است. `DynamicFeeTx` نوع تراکنش EIP-1559 است (نوع ۲). کلید امضایش می‌کند، `SendTransaction` ارسالش می‌کند و `WaitMined` صبر می‌کند تا در بلاک بنشیند و رسید را برمی‌گرداند.

```
$ go run ./cmd/ethdemo send
nonce: 3 base fee: 783421165 tip: 1000000000 fee cap: 2566842330
tx type: 2 hash: 0xecb131b439f7991150b056891e303b98c8539a0ce8c5e687564fe175c9c0cd4b
status: 1 block: 4 gas used: 21000 effective gas price: 1685976107
account 1 gained: 1.500000000000000000 ETH
```

- **`nonce: 3`:** حساب ۰ قبلاً سه تراکنش فرستاده بود (deploy).
- **`base fee`، `tip`، `fee cap`:** همه به wei به‌ازای هر gas. سقف ۲۵۶۶۸۴۲۳۳۰ برابر ۲ × ۷۸۳۴۲۱۱۶۵ + ۱۰۰۰۰۰۰۰۰۰ است، همان قاعده‌ی سرانگشتی ما. tip برابر ۱ gwei است، یعنی ۱۰^۹ wei.
- **`effective gas price`:** چیزی که واقعاً به‌ازای هر gas پرداخت شد: ۱۶۸۵۹۷۶۱۰۷. سقف فقط یک حد بالاست. base fee خود بلاک ۴ برابر ۶۸۵۹۷۶۱۰۷ بود (با `cast block 4 --field baseFeePerGas` چک کردم)، یعنی از ۷۸۳۴۲۱۱۶۵ که در بلاک ۳ دیدیم پایین آمده، پس تراکنش همان به‌علاوه‌ی ۱ gwei tip پرداخت.
- **`gas used: 21000`، `status: 1`:** هزینه‌ی انتقال ساده، و موفقیت.
- **خط آخر:** موجودی حساب ۱ دقیقاً ۱٫۵ ETH بالا رفت. فرستنده ۱٫۵ ETH به‌علاوه‌ی gas می‌دهد و گیرنده دقیقاً ۱٫۵ می‌گیرد.

chain ID داخل داده‌ی امضاشده است، مثل مقاله‌ی nonce: امضایی که برای این زنجیره ساخته شده روی زنجیره‌ی دیگر بی‌ارزش است.

## فراخوانی توکن با abigen

برای صدا زدن یک قرارداد، برنامه‌ی Go باید تابع‌های آن را بداند: اسم‌ها، نوع آرگومان‌ها و نوع خروجی‌ها. این توصیف {{< term "contract-abi" "ABI قرارداد" >}} است، یک فایل JSON که کامپایلر می‌سازد. پروژه‌ی Foundry مقاله‌ی قبل را کپی کردم، `forge build` زدم، ABI را از `out/` برداشتم و با {{< term "abigen" "abigen" >}} از آن کد Go ساختم:

```
$ go run github.com/ethereum/go-ethereum/cmd/abigen@v1.17.10 --v2 \
    --abi abi/DemoToken.abi --pkg token --type DemoToken --out token/token.go
```

از `--v2` استفاده کردم چون در v1.17.10 بسته‌ی قدیمی `bind` به نفع `bind/v2` منسوخ (deprecated) علامت خورده، و سورس همین را می‌گوید. کد تولیدشده‌ی v2 فقط آرگومان‌ها را بسته‌بندی می‌کند و نتیجه‌ها را باز می‌کند؛ خود فراخوانی‌ها از بسته‌ی `bind` می‌گذرند:

```go
demo := token.NewDemoToken()
inst := demo.Instance(c, tokenAddr)
dec, err := bind.Call(inst, call, demo.PackDecimals(), demo.UnpackDecimals)
opts := bind.NewKeyedTransactor(key, chainID)
tx, err := bind.Transact(inst, opts, demo.PackTransfer(acct1, amount))
rcpt, err := bind.WaitMined(ctx, c, tx.Hash())
ev, err := demo.UnpackTransferEvent(rcpt.Logs[0])
```

`bind.Call` یک خواندن است، مثل `cast call`: آرگومان‌ها را بسته‌بندی کن، از نود بپرس، جواب را باز کن. `bind.Transact` تراکنش واقعی است، مثل `cast send`. `UnpackTransferEvent` log رسید را decode می‌کند: همان topicها و dataیی که در مقاله‌ی قبل دستی خواندیم.

```
$ go run ./cmd/ethdemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO | account 1: 0.000000000000000000 DEMO
transfer tx type: 2 status: 1 gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 0: 999900.000000000000000000 DEMO | account 1: 100.000000000000000000 DEMO
```

- **خط ۱:** اول `decimals` از قرارداد خوانده می‌شود (۱۸) و برای قالب موجودی‌ها به کار می‌رود. حساب ۰ کل عرضه‌ی اولیه یعنی ۱٬۰۰۰٬۰۰۰ DEMO را دارد.
- **خط ۲:** انتقال یک تراکنش نوع ۲ است (`bind.Transact` خودش nonce، سقف gas و کارمزدها را پر کرد و باز هم تراکنش EIP-1559 ساخت). gas مصرفی ۵۲۳۸۳ است، همان `cast send` مقاله‌ی قبل، و دقیقاً یک log emit شده.
- **خط ۳:** event از نوع `Transfer` decode‌شده: از حساب ۰ به حساب ۱، به مقدار ۱۰^۲۰ واحد.
- **خط ۴:** موجودی‌های جدید: ۹۹۹٬۹۰۰ و ۱۰۰. یعنی ۱۰۰ DEMO، چون `100 * 10^decimals` فرستادم.

## decode یک خطای سفارشی

شکست برای کد Go چه شکلی است؟ حساب ۲ هیچ DEMO ندارد و می‌خواهد ۱ DEMO بفرستد. `bind.Transact` اول از نود می‌خواهد gas را تخمین بزند، فراخوانی شبیه‌سازی‌شده {{< term "revert" "revert" >}} می‌شود و چیزی فرستاده نمی‌شود. خطای Go داده‌ی خام revert را حمل می‌کند که با ABI decode می‌کنیم:

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

- **خطای خام** یک رشته است، به درد آدم می‌خورد، نه برنامه.
- **داده‌ی revert** ۱۰۰ بایت است: ۴ بایت اول selector خطاست (`0xdb42144d`)، که مثل {{< term "function-selector" "function selector" >}} از `InsufficientBalance(address,uint256,uint256)` ساخته می‌شود، و بعد از آن سه کلمه‌ی ۳۲ بایتی، یعنی آرگومان‌ها.
- **خط decode‌شده:** `UnpackError` selector را با ABI تطبیق داد و یک مقدار تایپ‌دار Go برگرداند، پس برنامه می‌تواند به‌جای هگز بنویسد «از این آدرس، موجودی ۰، نیاز ۱۰^۱۸». nonce حساب ۲ صفر ماند، چون چیزی فرستاده نشد.

## nonce با ارسال‌کننده‌های هم‌زمان

مشکلی که اول مقاله گفتم. هر تراکنش یک حساب باید nonce بعدی را به ترتیب داشته باشد. اگر چند goroutine هم‌زمان بفرستند و هرکدام از نود nonce را بپرسد، همه یک عدد می‌گیرند. در دمو پنج goroutine از حساب ۰ می‌فرستند. در دور اول هرکدام `PendingNonceAt` را می‌پرسد؛ در دور دوم یک شمارنده‌ی محافظت‌شده با mutex {{< term "nonce" "nonceها" >}} را می‌دهد. برای اینکه race هر بار نشان داده شود، همه‌ی goroutineها nonceشان را می‌گیرند، قبل از اینکه هرکدام بفرستد:

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
   nonce 5: <nil>
   nonce 5: replacement transaction underpriced
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

- **دور اول:** هر پنج تا nonce ۵ را گرفتند. هرکدام مقدار متفاوتی دارد، پس هرکدام تراکنش متفاوتی با nonce یکسان است. یکی وارد شد؛ نود به چهار تای دیگر می‌گوید `replacement transaction underpriced`: تلاش برای جایگزینی تراکنش منتظر بدون پرداخت کارمزد بیشتر را می‌بیند. اینکه کدام یک از پنج تا برنده شود از اجرایی به اجرای دیگر فرق می‌کند.
- **دور دوم:** nonceهای ۶ تا ۱۰ بدون شکاف و تکرار پخش می‌شوند و هر پنج ارسال موفق است. ترتیب goroutineها تصادفی است (nonce ۶ این بار آخر رفت) و نود باز هم هر پنج را به ترتیب nonce در بلاک گذاشت.
- **خط آخر:** ۶ تراکنش در بلاک نشست (یکی از دور اول، پنج تا از دور دوم) و nonce حساب از ۵ به ۱۱ رسید.

این manager فقط وقتی راه‌حل است که **تنها** ارسال‌کننده برای آن کلید باشد. اگر چند پروسه از یک حساب بفرستند، به یک جای مشترک نیاز دارند که nonceها را پخش کند.

## اشتباه‌های رایج کلاینت

- **مقدارها را از RPC تا پایگاه داده به‌صورت `*big.Int` نگه دارید.** موجودی حساب ۰ در بالا به‌صورت `float64` می‌شود ۹۹۹۹۹۹۷۶۸۳۲۹۰۱۷۹۸۹۵۲۹۶: از رقم‌های آخر همین حالا غلط است.
- **`PendingNonceAt` یک عکس لحظه‌ای** از دید نود است، نه رزرو. دو فراخواننده می‌توانند یک عدد بگیرند.
- **تراکنشی که هیچ‌وقت در بلاک ننشیند همه‌ی nonceهای بالاتر آن حساب را می‌بندد.** از قبل برنامه داشته باشید که با همان nonce و کارمزد بیشتر جایگزینش کنید.
- **داده‌ی revert را فقط وقتی می‌شود decode کرد که ABI شامل آن خطا را داشته باشید.** وگرنه فقط هگز می‌بینید.

## تمرین

۱. `feeCap` را کمتر از base fee بگذارید و بفرستید. anvil چه جوابی می‌دهد؟
۲. anvil را با `--no-mining` اجرا کنید و برنامه را بین دو دور nonce manager ری‌استارت کنید. `next` باید از کجا شروع شود؟
۳. با فراخوانی `mint` از حساب ۱، خطای `NotMinter` را decode کنید.

## قدم بعدی

مقاله‌ی بعد «کار با اتریوم از Rust با alloy» است. همین قدم‌ها را با Rust انجام می‌دهد تا دو کتابخانه را کنار هم ببینید.
