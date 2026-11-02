+++
date = '2026-11-09T18:00:00+03:30'
draft = false
title = 'شبکه‌ی P2P و gossip بین نودها'
description = 'gossip در P2P با Go: پروتکل TCP با پیشوند طول روی loopback، مجموعه‌ی seen در برابر حلقه، همگام‌سازی نود تازه و رد بلاک نامعتبر یک peer.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "p2p", "gossip", "tcp"]
cover = { image = "/images/covers/bc-p2p-gossip.fa.png", alt = "شبکه‌ی P2P و gossip بین نودها", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/bc-proof-of-work-mining/) ساختن بلاک گران شد، ولی فقط در یک پروسه. بلاکچین یعنی نودهای زیاد بدون سرور مرکزی که هر کدام هر چه می‌شنود خودش چک می‌کند. این پست نودهای `toychain` را روی TCP به هم وصل می‌کند.

بخش socket همان [سرور و کلاینت TCP از صفر](/fa/posts/net-sockets-tcp-from-scratch/) است. تفاوتش با [service discovery و load balancing](/fa/posts/ds-service-discovery-load-balancing/) اعتماد است: به هیچ peerی اعتماد نداریم و هر پیام قبل از رد شدن چک می‌شود.

ماژول پست قبل را کپی و پکیج `p2p` را اضافه کردم. همه‌ی نودها در یک پروسه روی `127.0.0.1` با پورت انتخابی سیستم‌عامل اجرا می‌شوند.

> اجرا با Go 1.27 روی macOS (arm64). کد مثال محلی است و فقط روی loopback. کلیدها از کلمه‌هایی مثل "alice" ساخته شده‌اند: عمومی‌اند و فقط برای دمو.

## فرمت پیام روی سیم

یک پروتکل {{< term "peer-to-peer" "peer-to-peer" >}} روی جریان بایت TCP به {{< term "message-framing" "framing" >}} نیاز دارد. هر frame یک طول ۴ بایتی big-endian است، بعد یک بایت نوع، بعد payload:

```go
const (
	MsgVersion   MsgType = 1 // handshake: who I am, which chain, how high
	MsgTx        MsgType = 2 // one transaction
	MsgBlock     MsgType = 3 // one block
	MsgGetBlocks MsgType = 4 // "send me your blocks from this height on"
)

const MaxFrame = 1 << 20
```

payload برای خوانایی JSON است؛ بیت‌کوین و اتریوم encoding دودویی خودشان را دارند. `ReadMsg` طول بیشتر از `MaxFrame` را قبل از گرفتن حافظه رد می‌کند، چون یک peer می‌تواند ادعای ۴ گیگابایت کند.

هر اتصال با `version` در هر دو جهت شروع می‌شود: نام، hash بلاک genesis و ارتفاع. peer با genesis دیگر قطع می‌شود. اگر peer بالاتر باشد، با `getblocks` بلاک‌های بعد از ارتفاع خودمان را می‌خواهیم. هر peer یک goroutine نویسنده با یک channel محدود دارد؛ اگر پر شود، peer قطع می‌شود.

## Gossip و مجموعه‌ی seen

{{< term "gossip-protocol" "Gossip" >}} ساده است: نودی که چیز تازه و معتبری بگیرد آن را برای همه‌ی peerها جز فرستنده می‌فرستد. در شبکه‌ی حلقه‌دار این کار تمام نمی‌شود، پس هر نود شناسه‌ی تراکنش‌ها و بلاک‌هایی را که دیده نگه می‌دارد:

```go
func (n *Node) handleTx(from *peer, tx chain.Tx) {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.stats.TxIn++
	id := tx.ID()
	if n.seen[id] {
		n.stats.Dups++
		return
	}
	n.seen[id] = true
	if _, err := n.checkTx(tx); err != nil {
		n.stats.Rejected++
		n.logf("tx %s from %s rejected: %v", id.Short(), from.label(), err)
		return
	}
	n.pending[id] = tx
	k := n.relay(from, MsgTx, tx)
	n.stats.Relayed += k
	n.logf("tx %s from %s: valid, relayed to %d", id.Short(), from.label(), k)
}
```

`checkTx` تراکنش را با مجموعه‌ی UTXO چک می‌کند و تراکنشی را که با یک تراکنش pending خروجی مشترک خرج کند رد می‌کند. بلاک‌ها هم همین مسیر را از `AddBlock` می‌روند، با یک تفاوت: peerی که بلاک نامعتبر بفرستد قطع می‌شود. تراکنش بد شاید race صادقانه باشد؛ بلاک بد با {{< term "proof-of-work" "proof of work" >}} معتبر اتفاقی نیست.

## یک اجرا

`go run ./cmd/toychain gossip`: A تنها دو بلاک ماین می‌کند، بعد B، C و A حلقه می‌سازند. Alice از طریق C به Bob پول می‌دهد، A بلاک ۳ را ماین می‌کند و D دیر می‌رسد و فقط به C وصل می‌شود (لاگ کمی کوتاه شده):

```
== ring A-B-C-A on loopback
[A] connected to B (its height 0, mine 2)
[B] connected to A (its height 2, mine 0)
[A] getblocks from 1 by B: sent 2 blocks
[B] block 1 0004060375af from A: valid, 1 txs, relayed to 0
[B] block 2 000d7c19dc57 from A: valid, 1 txs, relayed to 0
...
== alice pays bob 30 through C
[C] tx ef4d0ece5dfd submitted locally, sent to 2 peers
[B] tx ef4d0ece5dfd from C: valid, relayed to 1
[A] tx ef4d0ece5dfd from C: valid, relayed to 1
== A mines block 3
[A] mined block 3 0004a6f9de1f (bits 12, 37 hashes, 2 txs), sent to 2 peers
[B] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
[C] block 3 0004a6f9de1f from A: valid, 2 txs, relayed to 1
== D joins late, connects to C only
[D] connected to C (its height 3, mine 0)
[C] connected to D (its height 0, mine 3)
[C] getblocks from 1 by D: sent 3 blocks
[D] block 1 0004060375af from C: valid, 1 txs, relayed to 0
[D] block 2 000d7c19dc57 from C: valid, 1 txs, relayed to 0
[D] block 3 0004a6f9de1f from C: valid, 2 txs, relayed to 0
D: tip 0004a6f9de1f, bob 30, pending 0
```

A و B تراکنش را برای هم فرستادند؛ مجموعه‌ی seen نسخه‌ی دوم را دور ریخت (`duplicates 1` برای A در پایین). D هر سه بلاک را خودش چک کرد، از proof of work تا امضا، و بعد پذیرفت Bob سی سکه دارد.

## peerی که دروغ می‌گوید

بعد Mallory دستی با B حرف می‌زند: یک `version` و بعد یک بلاک؛ اول بلاکی ماین‌نشده، بعد بلاکی با proof of work معتبر و coinbase هزار سکه‌ای:

```
mallory: got version, sending unmined block
[B] REJECT block from mallory: block 4: hash does not meet the difficulty target
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
mallory: got version, sending mined (4258 hashes), coinbase 1000
[B] REJECT block from mallory: block 4: tx 0: coinbase pays more than reward + fees or has the wrong height
[B] disconnect mallory: sent an invalid block
mallory: connection: EOF
A: height 3, tx in 2, block in 0, duplicates 1, relayed 1, rejected 0
B: height 3, tx in 2, block in 6, duplicates 2, relayed 2, rejected 2
C: height 3, tx in 0, block in 4, duplicates 1, relayed 1, rejected 0
D: height 3, tx in 0, block in 3, duplicates 0, relayed 0, rejected 0
```

بلاک دوم hash واقعی خرج کرده بود و باز رد شد: proof of work بلاک را معتبر نمی‌کند، فقط گرانش می‌کند. تست‌ها قطع شدن peer با genesis دیگر را هم چک می‌کنند و `go test -race ./...` پاس می‌شود.

## شبکه‌های واقعی چه می‌کنند

discovery را پیاده نکردم: آدرس‌ها دستی داده می‌شوند. تا جایی که می‌دانم، نود تازه‌ی بیت‌کوین اولین peerها را از DNS seedها پیدا می‌کند، یعنی hostnameهایی که به آدرس نودهای فعال resolve می‌شوند، و بعد آدرس‌های بیشتر را از peerها یاد می‌گیرد. کلاینت‌های اتریوم یک پروتکل discovery شبیه Kademlia روی UDP دارند که در مشخصات devp2p آمده (discv4 و discv5). بیت‌کوین اول با `inv` فقط hash را اعلام می‌کند، داده را با `getdata` می‌فرستد و اول headerها را همگام می‌کند؛ نودهای من کل بلاک را می‌فرستند. {{< term "peer-discovery" "peer discovery" >}} جای حمله‌ی eclipse هم هست: نودی که همه‌ی peerهایش مهاجم باشند فقط زنجیره‌ی مهاجم را می‌بیند.

## چند نکته‌ی مهم

- هر طول ورودی از شبکه را قبل از گرفتن حافظه محدود کنید، و اندازه‌ی جواب هر درخواست را هم.
- قبل از relay چک کنید؛ وگرنه زباله‌ی مهاجم را پخش می‌کنید.
- یک peer کند نباید نود را نگه دارد: برای هر peer یک نویسنده با صف محدود.
- مجموعه‌ی seen من تا ابد بزرگ می‌شود؛ تا جایی که می‌دانم Bitcoin Core برای این کار از rolling Bloom filter استفاده می‌کند.

## تمرین

۱. فرستادن کل بلاک را با `inv`/`getdata` عوض کنید: فقط hash اعلام شود و بلاک با درخواست فرستاده شود.
۲. امتیاز ban اضافه کنید: peer بعد از سه تراکنش ردشده قطع شود و آدرسش یک دقیقه کنار گذاشته شود.
۳. `getblocks` را طوری کنید که اول headerها بیایند و proof of work آن‌ها قبل از درخواست بدنه چک شود.

## قدم بعدی

پست بعد: **Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر**. نودها فعلاً بلاک رقیب را نادیده می‌گیرند؛ بعد درخت بلاک نگه می‌داریم و زنجیره‌ی با بیشترین کار برنده می‌شود.
