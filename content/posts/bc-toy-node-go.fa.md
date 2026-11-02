+++
date = '2026-11-13T18:00:00+03:30'
draft = false
title = 'جمع‌بندی بخش اول: یک نود کامل کوچک با Go'
description = 'یک full node کوچک با Go: پروسه‌های جدا روی loopback، بلاک روی دیسک با اعتبارسنجی دوباره، API از نوع JSON-RPC، کیف‌پول خط فرمان و خاموشی تمیز.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "full-node", "json-rpc", "bitcoin"]
cover = { image = "/images/covers/bc-toy-node-go.fa.png", alt = "جمع‌بندی بخش اول: یک نود کامل کوچک با Go", hiddenInSingle = true }
+++

پست قبلی، [Bitcoin Script: یک مفسر stack کوچک با Rust](/fa/posts/bc-bitcoin-script-rust/)، یک گریز کوتاه بود. کد Go از [Mempool، کارمزد و انتخاب تراکنش](/fa/posts/bc-mempool-fees/) ادامه دارد، جایی که همه‌ی نودها در یک پروسه بودند و با بسته شدنش همه‌چیز را فراموش می‌کردند.

این پست بخش اول را می‌بندد: یک {{< term "full-node" "full node" >}} به اسم `toynode`، بلاک روی دیسک، API و کیف‌پول خط فرمان. تکه‌ها از [ساخت ابزار خط فرمان با Go](/fa/posts/go-cli-tool/)، [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) و [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) می‌آیند.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است و فقط روی loopback. کلیدها از کلمه‌هایی مثل "miner" ساخته شده‌اند: عمومی‌اند و فقط برای دمو. مسیرهای موقت `<tmp>` نوشته شده‌اند.

## هر نود یک پروسه

```
$ toynode -h
Usage of <tmp>/bin/toynode:
  -data string
    	directory for blocks.dat (required)
  -interval duration
    	time between mined blocks (default 2s)
  -listen string
    	P2P address (default "127.0.0.1:19001")
  -mine
    	mine blocks
  -miner string
    	demo key name that receives block rewards (default "miner")
  -name string
    	name used in logs and the handshake (default "node")
  -peers string
    	comma-separated P2P addresses to keep connected to
  -rpc string
    	JSON-RPC address (loopback only) (default "127.0.0.1:18001")
```

یک goroutine هر ثانیه peerهای قطع را دوباره dial می‌کند، پس peer ری‌استارت‌شده دوباره پیدا می‌شود.

## بلاک روی دیسک

هر بلاکی که به درخت اضافه می‌شود، شاخه‌ی فرعی هم، در `blocks.dat` نوشته می‌شود: طول ۴ بایتی، بلاک به‌صورت JSON، بعد `fsync`. والد همیشه قبل از فرزند می‌آید. موقع شروع، رکورد نیمه‌کاره‌ی آخر که از crash مانده بریده می‌شود و هر بلاک دوباره از `AddBlock` رد می‌شود: header و proof of work برای همه، تراکنش و امضا برای زنجیره‌ی فعال، و fork choice با chainwork:

```go
for _, b := range blocks {
	if b.Header.Height == 0 {
		continue // genesis is built in
	}
	if _, err := n.chain.AddBlock(b); err != nil {
		return err
	}
}
```

اعتبارسنجی دوباره برای زنجیره‌ی بزرگ کند است، ولی به دیسک اعتماد نمی‌کنیم. یک تست ۵ بایت از ته فایل می‌بُرد و بار شدن بلاک‌های قبلی را چک می‌کند. mempool ذخیره نمی‌شود؛ تا جایی که می‌دانم Bitcoin Core موقع خاموش شدن mempool را روی دیسک می‌نویسد.

## API از نوع JSON-RPC روی loopback

API همان {{< term "json-rpc" "JSON-RPC" >}} 2.0 روی HTTP است: `getblockcount`، `getblock`، `getbalance`، `listunspent`، `sendtx` و `getmempoolinfo`. احراز هویت ندارد، پس نود هر آدرسی جز loopback را رد می‌کند:

```
$ toynode -data <tmp>/x -rpc 0.0.0.0:18109
rpc address 0.0.0.0:18109 is not a loopback IP
```

تا جایی که می‌دانم bitcoind از RPC با فایل cookie یا اعتبارنامه‌ی تنظیم‌شده محافظت می‌کند.

کلید دست `toywallet` است. `send` خروجی‌های تأییدشده را از نود می‌گیرد، از بزرگ‌ترین برمی‌دارد تا مبلغ و کارمزد پوشش داده شود، change می‌گذارد، امضا می‌کند و `sendtx` را صدا می‌زند. نود هیچ‌وقت کلید خصوصی را نمی‌بیند.

## سه نود و یک ری‌استارت

`demo.sh` سه پروسه راه می‌اندازد: n1 هر ۲ ثانیه ماین می‌کند، n2 به n1 وصل می‌شود و n3 به هر دو. بعد یک پرداخت، یک `SIGTERM` به n2 و ری‌استارت:

```
== heights
{"jsonrpc":"2.0","id":1,"result":3}
{"jsonrpc":"2.0","id":1,"result":3}
{"jsonrpc":"2.0","id":1,"result":3}
== wallet
miner 0xb7885750: 150
sent a1ee6a59dee4: 1 inputs, 20 to 0xd94f176c, fee 1, 233 bytes
bob 0xd94f176c: 20
bob 0xd94f176c: 20
{"jsonrpc":"2.0","id":2,"result":{"height":4,"hash":"0000359c9480ba929389cca89523c1967ec04f8a1ac2e78190ad31f398cefd25","prev":"0003f6b32dc59ccac63d9416036d5b5de9c241b3d48b71f8b1f6cb946ea2ef07","time":1793564462,"bits":12,"txids":["3f4cb1ba34d5822b628abfb47aad11a6b376e22600327143c0d1b1ed43d2b2bf","a1ee6a59dee410ccacc13ce9482db04bf2d46a2276b85fd227564a89e95df997"]}}
== stop n2 (SIGTERM)
== heights while n2 is down
{"jsonrpc":"2.0","id":1,"result":7}
{"jsonrpc":"2.0","id":1,"result":7}
== restart n2
== heights
{"jsonrpc":"2.0","id":1,"result":9}
{"jsonrpc":"2.0","id":1,"result":9}
{"jsonrpc":"2.0","id":1,"result":9}
bob 0xd94f176c: 20
```

کیف‌پول از n3 فرستاد، n1 ماین کرد و n2 جواب داد. لاگ n2:

```
[n2] block 4 0000359c9480 from n1: extended, 2 txs, relayed to 1
[n2] signal received, shutting down
[n2] block 5 000a8de373da from n1: extended, 1 txs, relayed to 1
[n2] stopped at height 5
[n2] loaded 5 blocks from disk, re-validated, tip 5 000a8de373da
[n2] p2p 127.0.0.1:19102, rpc 127.0.0.1:18102, mining false
[n2] connected to n1 (its height 7 work 32768, mine 5 work 24576)
[n2] block 6 00015ccd8617 from n1: extended, 1 txs, relayed to 0
[n2] block 7 00087e9fdc04 from n1: extended, 1 txs, relayed to 0
```

بلاک ۵ بعد از سیگنال رسید و باز ذخیره شد، چون {{< term "graceful-shutdown" "خاموشی تمیز" >}} ترتیب دارد: توقف سرور HTTP (درخواست‌های جاری تمام می‌شوند)، توقف ماینر و dialer، بستن نود و صبر برای goroutineها، و آخر sync و بستن فایل. ری‌استارت یک {{< term "initial-block-download" "initial block download" >}} کوچک است: در handshake کار n1 بیشتر است، پس n2 locator می‌فرستد و بلاک‌های ۶ و ۷ را می‌گیرد.

## بخش اول در یک جدول

| پست | چیزی که نود گرفت |
|---|---|
| [BC2](/fa/posts/bc-hashes-blocks-chain/) | SHA-256، header با encoding یکتا، زنجیر کردن بلاک‌ها |
| [BC3](/fa/posts/bc-merkle-trees-proofs/) | Merkle root، اثبات عضویت |
| [BC4](/fa/posts/bc-keys-ecdsa-addresses/) | کلید secp256k1، امضای low-S |
| [BC5](/fa/posts/bc-transactions-utxo/) | تراکنش UTXO، کارمزد، coinbase |
| [BC6](/fa/posts/bc-account-model-nonce/) | مقایسه با مدل حساب |
| [BC7](/fa/posts/bc-proof-of-work-mining/) | proof of work، retarget، chainwork |
| [BC8](/fa/posts/bc-p2p-gossip/) | framing روی TCP، gossip، همگام‌سازی |
| [BC9](/fa/posts/bc-forks-reorgs/) | درخت بلاک، reorg، داده‌ی undo |
| [BC10](/fa/posts/bc-mempool-fees/) | mempool، نرخ کارمزد، RBF |
| [BC11](/fa/posts/bc-bitcoin-script-rust/) | مفسر Script (با Rust، جدا) |
| BC12 | پروسه، دیسک، API، کیف‌پول |

## چیزهایی که نود واقعی دارد و این ندارد

فهرست کامل نیست:

- همگام‌سازی headers-first و موازی از چند peer؛ مال من بلاک کامل را از یک peer می‌گیرد.
- محافظت در برابر {{< term "denial-of-service" "denial of service" >}}: سقف اتصال، قطع peer بدرفتار، سقف حافظه‌ی هر peer.
- Script: این‌جا خروجی یک آدرس دارد؛ مفسر BC11 وصل نشده.
- relay فشرده‌ی بلاک (BIP-152) که از تراکنش‌های موجود نزد peer استفاده می‌کند.
- قاعده‌ی بلوغ coinbase، median-time-past و سقف timestamp آینده.
- دیتابیس واقعی برای UTXO، pruning، peer discovery، تخمین کارمزد.

## چند نکته‌ی مهم

- هر چه بار می‌کنید دوباره اعتبارسنجی کنید؛ دیسک هم ورودی است.
- قبل از اعلام ذخیره `fsync` کنید و رکورد نیمه‌کاره را موقع شروع ببرید.
- RPC بدون احراز هویت فقط روی loopback.
- به ترتیب خاموش کنید: اول ورودی‌ها، آخر ذخیره‌سازی.

## تمرین

۱. mempool را موقع خاموش شدن ذخیره و موقع شروع دوباره اضافه کنید.
۲. یک فایل `-rpccookie` با توکن تصادفی اضافه کنید و در هر درخواست چکش کنید.
۳. ماینر را در یک حلقه با `SIGKILL` بکشید و چک کنید هر ری‌استارت زنجیره‌ی معتبر بار می‌کند.

## قدم بعدی

بخش دوم شروع می‌شود. پست بعد: **EVM از درون: stack، memory، storage و gas با یک مفسر کوچک Rust**.
