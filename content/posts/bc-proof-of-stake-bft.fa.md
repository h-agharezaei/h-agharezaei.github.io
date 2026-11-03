+++
date = '2026-11-28T18:00:00+03:30'
draft = false
title = 'Proof of Stake، BFT و finality'
description = 'proof of stake و finality از نوع BFT با Go: انتخاب proposer با وزن stake، رأی امضاشده‌ی prevote و precommit، quorum دو سوم و slashing برای امضای دوگانه.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-stake", "bft", "finality"]
cover = { image = "/images/covers/bc-proof-of-stake-bft.fa.png", alt = "Proof of Stake، BFT و finality", hiddenInSingle = true }
+++

در [Proof of Work، difficulty و mining](/fa/posts/bc-proof-of-work-mining/) هر رأی برق خرج داشت و [Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر](/fa/posts/bc-forks-reorgs/) هزینه‌اش را نشان داد: هیچ بلاکی قطعی نیست. پس چه کسی بلاک را می‌سازد و کی قطعی می‌شود؟ [MEV و ترتیب تراکنش‌ها](/fa/posts/bc-mev-ordering/) فقط می‌پرسید چه کسی تراکنش‌های داخل بلاک را مرتب می‌کند.

{{< term "proof-of-stake" "Proof of Stake" >}} به‌جای انرژی سوزانده‌شده پول قفل‌شده می‌گذارد. هر {{< term "validator" "validator" >}} stake می‌سپارد، وزن رأی‌اش همان stake است و تقلب اثبات‌شده بخشی از آن را می‌سوزاند.

رأی‌گیری consensus مقاوم در برابر {{< term "byzantine-fault" "خطای بیزانسی" >}} است. در [consensus و Raft](/fa/posts/ds-consensus-raft/) نودها crash می‌کردند ولی دروغ نمی‌گفتند؛ اینجا بعضی دروغ می‌گویند.

> Go 1.27 روی macOS (arm64)، کد مثال محلی. پکیج `wallet` (secp256k1) بدون تغییر از دموی [نود کامل کوچک](/fa/posts/bc-toy-node-go/) کپی شده؛ کلیدها از اسم‌هایی مثل "alice" می‌آیند: عمومی و فقط برای دمو. این یک **مدل آموزشی** از یک round شبیه Tendermint است: بدون timeout، تعویض round و locking، با تحویل هم‌زمان. پروتکل production نیست.

## چه کسی پیشنهاد می‌دهد

validatorها: alice با 30، bob با 25، carol با 20، dave با 15 و erin با 10. همه باید به یک proposer برسند، پس انتخاب تابع seed مشترک، ارتفاع و round است (کوتاه‌شده):

```go
func (s *Set) Proposer(seed Hash, height uint64, round uint32) *Validator {
	// h = sha256(seed || height || round)
	r := binary.BigEndian.Uint64(h[:8]) % s.Total()
	for _, v := range s.Vals {
		if r < v.Stake {
			return v
		}
		r -= v.Stake
	}
	panic("unreachable")
}
```

```
proposer counts over 10000 heights: alice(30)=2986 bob(25)=2538 carol(20)=1947 dave(15)=1535 erin(10)=994
```

متناسب با stake. نقطه‌ی ضعف seed است: اگر hash بلاک قبلی بود، proposer می‌توانست نسخه‌های زیادی از بلاکش بسازد و نسخه‌ای را منتشر کند که دوباره خودش proposer شود (grinding). تا جایی که می‌دانم اتریوم مقدار فاش‌شده‌ی هر proposer را در seed مخلوط می‌کند (RANDAO)، پس آخرین proposer فقط می‌تواند فاش کند یا نوبت را رد کند.

## دو رأی و quorum دو سوم

proposer بلاک را می‌فرستد؛ همه prevote امضا می‌کنند؛ هر کس از بیش از دو سوم stake برای یک بلاک prevote ببیند برایش precommit امضا می‌کند (وگرنه برای nil)؛ بیش از دو سوم precommit یعنی commit.

```go
func (s *Set) Quorum(stake uint64) bool { return 3*stake > 2*s.Total() }
```

چرا دو سوم و نه اکثریت؟ n validator داریم که f تا بیزانسی‌اند. آن‌ها ممکن است ساکت بمانند، پس {{< term "quorum" "quorum" >}} باید از n−f تا شکل بگیرد. دو quorum دست‌کم 2(n−f)−n = n−2f عضو مشترک دارند و یکی‌شان باید صادق باشد، چون صادق دو رأی متفاوت نمی‌دهد: n−2f ≥ f+1، یعنی n ≥ 3f+1. عدد 2f+1 در {{< term "raft" "Raft" >}} فقط چون نودها دروغ نمی‌گویند کافی است. اینجا به‌جای نود stake را می‌شماریم.

## سه اجرا

`go run ./cmd/posbft`، همه صادق:

```
== all honest (seed-0)
proposer alice (byzantine=false), A=ce20c9 B=a1237f
after precommit: alice=ce20c9 bob=ce20c9 carol=ce20c9 dave=ce20c9 erin=ce20c9
```

بلاک همان لحظه‌ی commit قطعی است. این {{< term "deterministic-finality" "finality قطعی" >}} است، برخلاف {{< term "probabilistic-finality" "finality احتمالی" >}} در proof of work: confirmation لازم نیست و reorg فقط وقتی ممکن است که یک سوم stake رأی متناقض امضا کند.

حالا dave و erin (25 درصد) بیزانسی‌اند. seedها را امتحان کردم تا یکی‌شان proposer شد (seed-5). erin بلاک A را به alice و bob و B را به carol می‌دهد و هر دو به alice و bob رأی A و به carol رأی B می‌دهند:

```
proposer erin (byzantine=true), A=4444c9 B=7bc6a3
after precommit: alice=4444c9 bob=4444c9 carol=- dave=byz erin=byz
after gossip: alice=4444c9 bob=4444c9 carol=4444c9 dave=byz erin=byz
conflicting commits: false
evidence from carol: dave prevote 7bc6a3 vs 4444c9, check=<nil>
slash dave: stake 15 -> 8
evidence from carol: erin prevote 7bc6a3 vs 4444c9, check=<nil>
slash erin: stake 10 -> 5
evidence from carol: dave precommit 7bc6a3 vs 4444c9, check=<nil>
evidence from carol: erin precommit 7bc6a3 vs 4444c9, check=<nil>
```

سهم B حداکثر 20+25 = 45 است. بعد از gossip، carol بلاک A را commit می‌کند و دو رأی امضاشده از dave دارد با ارتفاع، round و نوع یکسان و بلاک متفاوت. این {{< term "equivocation" "equivocation" >}} است و همین دو رأی اثبات کامل‌اند:

```go
case a.Block == b.Block:
	return errors.New("same block: not conflicting")
case !s.VerifyVote(a) || !s.VerifyVote(b):
	return errors.New("bad signature")
```

verifier فقط کلید عمومی دارد، پس هر کسی می‌تواند چک کند. {{< term "slashing" "Slashing" >}} اینجا نصف stake را می‌سوزاند، که انتخاب من است؛ زنجیره‌های واقعی جریمه‌ی خودشان را دارند.

در آخر alice و erin (40 درصد) آفلاین‌اند:

```
proposer carol (byzantine=false), A=098419 B=fb4012
after precommit: alice=off bob=- carol=- dave=- erin=off
conflicting commits: false
```

60 بیشتر از دو سوم 100 نیست: چیزی commit نمی‌شود. liveness رفته، safety نه؛ به زبان [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/)، consistency بر availability مقدم شده. پروتکل واقعی پس از timeout دوباره می‌کوشد.

## شکستن مرز

با alice و dave بیزانسی (45 درصد) همان حمله `bob=a1237f carol=ce20c9 erin=ce20c9` و `conflicting commits: true` می‌دهد، هرچند carol علیه هر دو مدرک دارد. یک تست همه‌ی زیرمجموعه‌های بیزانسی و تقسیم‌ها را روی 4 seed اجرا می‌کند:

```
runs=972 conflicting(byz<1/3)=0 conflicting(byz>=1/3)=68 commits with >=1/3 offline=0
```

## اتریوم، کوتاه

طبق مستندات اتریوم، تا جایی که فهمیده‌ام، هر دو ترکیب شده‌اند: یک {{< term "fork-choice-rule" "قاعده‌ی fork choice" >}} (LMD-GHOST) سر زنجیره را انتخاب می‌کند و Casper FFG وقتی دو سوم stake به checkpointهای epoch رأی بدهد آن‌ها را finalize می‌کند. کلاینت اتریوم اجرا نکردم.

## safety روی چه فرض‌هایی ایستاده

- quorum یعنی بیش از دو سوم stake، نه نودها.
- safety فرض می‌کند stake بیزانسی زیر یک سوم است؛ بالاتر از آن مدرک فقط بعد از اتفاق متقلب‌ها را نشان می‌دهد.
- proposalهای مدل من امضا ندارند؛ proposal دوگانه هم مدرک است.
- slashing باید پیش از برداشت stake برسد؛ تا جایی که می‌دانم برای همین برداشت در proof of stake تأخیر دارد.

## تمرین

round دوم با locking بسازید: کسی که A را precommit کرده بعداً فقط A را prevote کند، مگر prevote دو سوم تازه‌تری برای چیز دیگر ببیند.

## قدم بعدی

**Layer 2 و rollupها: optimistic و ZK**: بلاک قطعی، بلاک بزرگ‌تر نیست.
