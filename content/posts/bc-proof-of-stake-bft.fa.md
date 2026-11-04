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

در [Proof of Work، difficulty و mining](/fa/posts/bc-proof-of-work-mining/) هر رأی برق خرج داشت، و [Fork، reorg و قاعده‌ی زنجیره‌ی سنگین‌تر](/fa/posts/bc-forks-reorgs/) هزینه‌ی دیگرش را نشان داد: هیچ بلاکی قطعی نیست. هر وقت زنجیره‌ی سنگین‌تری برسد، بلاک‌های قبلی کنار می‌روند. پس دو سؤال می‌ماند: چه کسی بلاک را می‌سازد، و بلاک کی قطعی می‌شود؟ [MEV و ترتیب تراکنش‌ها](/fa/posts/bc-mev-ordering/) فقط می‌پرسید چه کسی تراکنش‌های داخل بلاک را مرتب می‌کند.

{{< term "proof-of-stake" "Proof of Stake" >}} به‌جای انرژی سوزانده‌شده، پول قفل‌شده می‌گذارد. مثل جلسه‌ای است که هر کس برای حق رأی گرفتن مقداری پول گرو می‌گذارد. هر {{< term "validator" "validator" >}} مقداری را به‌عنوان stake می‌سپارد. وزن رأی‌اش به همان اندازه است، و اگر تقلبش ثابت شود، بخشی از آن گرو سوزانده می‌شود.

این رأی‌گیری باید در برابر {{< term "byzantine-fault" "خطای بیزانسی" >}} مقاوم باشد. در [consensus و Raft](/fa/posts/ds-consensus-raft/) نودها ممکن بود crash کنند، ولی دروغ نمی‌گفتند. نود بیزانسی فرق دارد: ممکن است به هر نفر چیز متفاوتی بگوید. این‌جا بعضی از شرکت‌کننده‌ها عمداً دروغ می‌گویند.

> Go 1.27 روی macOS (arm64)، کد مثال محلی. پکیج `wallet` (secp256k1) بدون تغییر از دموی [نود کامل کوچک](/fa/posts/bc-toy-node-go/) کپی شده؛ کلیدها از اسم‌هایی مثل "alice" می‌آیند: عمومی و فقط برای دمو. این یک **مدل آموزشی** از یک round شبیه Tendermint است: بدون timeout، تعویض round و locking، با تحویل هم‌زمان. پروتکل production نیست.

## چه کسی پیشنهاد می‌دهد

اول باید معلوم شود نوبت کیست. پنج validator داریم: alice با stake برابر 30، bob با 25، carol با 20، dave با 15 و erin با 10. جمع stake برابر 100 است. هر کس باید شانسی متناسب با stake خودش داشته باشد: alice سی درصد نوبت‌ها را، erin ده درصد.

مشکل این است که همه‌ی نودها باید روی یک proposer توافق کنند، بدون اینکه کسی به آن‌ها بگوید. پس انتخاب باید یک تابع از چیزهایی باشد که همه می‌دانند: یک seed مشترک، ارتفاع بلاک و شماره‌ی round. همه همین تابع را حساب می‌کنند و به یک جواب می‌رسند (کوتاه‌شده):

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

تابع یک عدد `r` بین 0 و 99 از hash می‌سازد. بعد validatorها را به ترتیب مثل بازه‌های پشت سر هم می‌بیند: alice بازه‌ی 0 تا 29، bob 30 تا 54 و همین‌طور تا آخر. `r` در بازه‌ی هر کس بیفتد او proposer است. برای اینکه ببینیم شانس‌ها واقعاً متناسب با stake است، 10٬۰۰۰ ارتفاع را شمردم:

```
proposer counts over 10000 heights: alice(30)=2986 bob(25)=2538 carol(20)=1947 dave(15)=1535 erin(10)=994
```

تقریباً ۳۰، ۲۵، ۲۰، ۱۵ و ۱۰ درصد. نقطه‌ی ضعف این روش seed است. اگر seed مثلاً hash بلاک قبلی بود، proposer می‌توانست نسخه‌های زیادی از بلاکش بسازد و نسخه‌ای را منتشر کند که دوباره خودش proposer شود. به این کار grinding می‌گویند. تا جایی که می‌دانم اتریوم مقدار فاش‌شده‌ی هر proposer را در seed مخلوط می‌کند (RANDAO)، پس آخرین proposer فقط می‌تواند مقدارش را فاش کند یا نوبتش را رد کند.

## دو رأی و quorum دو سوم

حالا proposer انتخاب شده. بلاک چطور تأیید می‌شود؟ در سه مرحله:

۱. proposer بلاک را می‌فرستد و همه برای آن prevote امضا می‌کنند. prevote یعنی «من این پیشنهاد را دیدم».
۲. هر کس بیش از دو سوم stake را دید که برای یک بلاک prevote کرده، برای آن precommit امضا می‌کند (وگرنه برای nil، یعنی هیچ‌چیز). precommit یعنی «من دیدم که دو سوم همه همان پیشنهاد را دیده‌اند».
۳. اگر بیش از دو سوم stake برای یک بلاک precommit کرده باشد، بلاک commit می‌شود.

دو رأی لازم است، چون رأی اول فقط می‌گوید «من دیدم». رأی دوم می‌گوید «می‌دانم که بقیه هم دیده‌اند». commit فقط وقتی امن است که کسی نتواند بعداً بلاک دیگری را قطعی کند.

شرط دو سوم در یک خط است:

```go
func (s *Set) Quorum(stake uint64) bool { return 3*stake > 2*s.Total() }
```

چرا دو سوم و نه اکثریت ساده؟ اول یک مثال کوچک. چهار validator داریم و یکی‌شان بیزانسی است. {{< term "quorum" "quorum" >}} را سه نفر می‌گیریم. دو گروه سه‌نفره از چهار نفر، دست‌کم دو نفر مشترک دارند. چون فقط یک نفر بیزانسی است، دست‌کم یکی از آن دو نفر مشترک صادق است. و صادق هیچ‌وقت برای دو بلاک متفاوت رأی نمی‌دهد. پس دو quorum برای دو بلاک متفاوت ممکن نیست.

حالا کلی: n validator داریم که f تا بیزانسی‌اند. بیزانسی‌ها ممکن است ساکت بمانند، پس quorum باید فقط از n−f نفر شکل بگیرد تا پروتکل گیر نکند. دو quorum دست‌کم 2(n−f)−n = n−2f عضو مشترک دارند، و در آن‌ها باید یک صادق باشد. یعنی n−2f ≥ f+1، پس n ≥ 3f+1. عددی مثل 2f+1 در {{< term "raft" "Raft" >}} فقط چون نودها دروغ نمی‌گویند کافی است. این‌جا به‌جای نودها، stake را می‌شماریم.

## سه اجرا

برنامه را با `go run ./cmd/posbft` اجرا می‌کنیم. اول وقتی همه صادق‌اند:

```
== all honest (seed-0)
proposer alice (byzantine=false), A=ce20c9 B=a1237f
after precommit: alice=ce20c9 bob=ce20c9 carol=ce20c9 dave=ce20c9 erin=ce20c9
```

خط دوم نام proposer را نشان می‌دهد، و دو hash کوتاه: `A` بلاکی است که proposer صادق به همه می‌دهد و `B` بلاک دیگری که فقط در سناریوهای بیزانسی استفاده می‌شود. خط آخر می‌گوید هر نود بعد از precommit کدام بلاک را commit کرده: همه A.

بلاک همان لحظه‌ی commit قطعی است. این {{< term "deterministic-finality" "finality قطعی" >}} است، برخلاف {{< term "probabilistic-finality" "finality احتمالی" >}} در proof of work. لازم نیست صبر کنید تا چند بلاک روی آن بیاید، و reorg فقط وقتی ممکن است که یک سوم stake رأی متناقض امضا کند.

سناریوی دوم: dave و erin (روی هم 25 درصد stake) بیزانسی‌اند. seedها را امتحان کردم تا یکی‌شان proposer شد (seed-5). erin بلاک A را به alice و bob می‌دهد و B را به carol. هر دو بیزانسی هم همین کار را با رأی‌ها می‌کنند: به alice و bob رأی A و به carol رأی B می‌دهند. سه نفر صادق هم هر کدام برای بلاکی که دیده‌اند رأی می‌دهند:

```
proposer erin (byzantine=true), A=4444c9 B=7bc6a3
after precommit: alice=4444c9 bob=4444c9 carol=- dave=byz erin=byz
after gossip: alice=4444c9 bob=4444c9 carol=4444c9 dave=byz erin=byz
conflicting commits: false
evidence from carol: dave prevote 7bc6a3 vs 4444c9, check=<nil>
slash dave: stake 15 -> 8
evidence from carol: erin prevote 7bc6a3 vs 4444c9, check=<nil>
slash erin: stake 10 -> 5
evidence from carol: erin precommit 7bc6a3 vs 4444c9, check=<nil>
evidence from carol: dave precommit 7bc6a3 vs 4444c9, check=<nil>
```

(دو خط آخر ترتیب ثابتی ندارند و در اجراهای مختلف جابه‌جا می‌شوند. برنامه خط‌های دیگری هم چاپ می‌کند که برای کوتاهی نیاورده‌ام.)

خط‌به‌خط:

- **`after precommit`:** alice و bob بلاک A را commit کرده‌اند، چون A از alice (30) + bob (25) + دو بیزانسی (25) جمعاً 80 stake رأی دیده و 80 بیشتر از دو سوم است. carol هنوز commit نکرده (`-`)، چون برای خودش فقط 45 stake برای B و 55 برای A دیده و هیچ‌کدام از دو سوم نیست.
- **`after gossip`:** نودهای صادق آنچه دیده‌اند را به هم می‌فرستند (gossip). حالا carol هم رأی‌های A را می‌بیند و A را commit می‌کند. هر سه صادق یک بلاک دارند.
- **`conflicting commits: false`:** دو نود صادق بلاک متفاوت commit نکرده‌اند. safety حفظ شد.
- **`evidence`:** carol حالا از dave دو prevote امضاشده دارد، یکی برای B (که خودش به carol داده بود) و یکی برای A (که از alice و bob رسیده). همین برای erin و برای precommitها هم هست.
- **`slash`:** stake dave از 15 به 8 رسید و stake erin از 10 به 5.

دلیل اینکه B نتوانست commit شود، حساب ساده‌ای است: سهم B حداکثر 20+25 = 45 است، یعنی کمتر از دو سوم.

آن دو رأی امضاشده‌ی متناقض از یک نفر، یعنی {{< term "equivocation" "equivocation" >}}، خودشان اثبات کامل تقلب‌اند. کد بررسی‌شان این است (کوتاه‌شده):

```go
case a.Block == b.Block:
	return errors.New("same block: not conflicting")
case !s.VerifyVote(a) || !s.VerifyVote(b):
	return errors.New("bad signature")
```

دو رأی باید از یک validator و هم‌نوع باشند، با ارتفاع و round یکسان، و بلاکشان فرق کند، و هر دو امضای معتبر داشته باشند. verifier فقط کلید عمومی دارد، پس هر کسی می‌تواند مدرک را چک کند. برنامه این را هم نشان می‌دهد که دو رأی یکسان مدرک نیستند (`same vote twice: same block: not conflicting`)، و تست‌های پکیج چک می‌کنند که مدرک دست‌کاری‌شده رد شود.

{{< term "slashing" "Slashing" >}} در این مدل نصف stake را می‌سوزاند. این انتخاب من است؛ زنجیره‌های واقعی جریمه‌ی خودشان را دارند.

سناریوی سوم: alice و erin (40 درصد stake) آفلاین‌اند.

```
proposer carol (byzantine=false), A=098419 B=fb4012
after precommit: alice=off bob=- carol=- dave=- erin=off
conflicting commits: false
```

آنلاین‌ها 60 stake دارند، و 60 بیشتر از دو سوم 100 نیست. پس هیچ‌کس commit نمی‌کند (`-`). پروتکل گیر کرده ولی غلط هم نکرده: liveness (پیشرفت) رفته، safety (توافق روی یک بلاک) نه. به زبان [CAP و PACELC درست](/fa/posts/ds-cap-pacelc/)، consistency بر availability مقدم شده. پروتکل واقعی پس از timeout دوباره می‌کوشد.

## شکستن مرز

اگر از یک سوم بیشتر شود چه؟ با alice و dave بیزانسی (45 درصد) همان حمله می‌شود `bob=a1237f carol=ce20c9 erin=ce20c9` و `conflicting commits: true`: bob بلاک B را commit کرد و دو نفر دیگر A را. safety شکست. با این حال carol علیه هر دو مدرک دارد، پس تقلب‌شان قابل اثبات است ولی خرابی انجام شده. یک تست همه‌ی زیرمجموعه‌های بیزانسی و تقسیم‌ها را روی 4 seed اجرا می‌کند:

```
runs=972 conflicting(byz<1/3)=0 conflicting(byz>=1/3)=68 commits with >=1/3 offline=0
```

یعنی در ۹۷۲ اجرا، وقتی stake بیزانسی زیر یک سوم بود هیچ‌بار دو بلاک متناقض commit نشد. وقتی یک سوم یا بیشتر بود، ۶۸ اجرا شکست خورد. و وقتی یک سوم یا بیشتر آفلاین بود، هیچ commitی انجام نشد.

## اتریوم، کوتاه

طبق مستندات اتریوم، تا جایی که فهمیده‌ام، هر دو ایده ترکیب شده‌اند: یک {{< term "fork-choice-rule" "قاعده‌ی fork choice" >}} (LMD-GHOST) سر زنجیره را انتخاب می‌کند و Casper FFG وقتی دو سوم stake به checkpointهای epoch رأی بدهد آن‌ها را finalize می‌کند. کلاینت اتریوم اجرا نکردم.

## safety روی چه فرض‌هایی ایستاده

- **quorum یعنی بیش از دو سوم stake، نه دو سوم نودها.**
- **safety فرض می‌کند stake بیزانسی زیر یک سوم است.** بالاتر از آن، مدرک فقط بعد از اتفاق، متقلب‌ها را نشان می‌دهد.
- **proposalهای مدل من امضا ندارند.** proposal دوگانه هم مدرک است.
- **slashing باید پیش از برداشت stake برسد.** تا جایی که می‌دانم برای همین برداشت در proof of stake تأخیر دارد.

## تمرین

round دوم با locking بسازید: کسی که A را precommit کرده بعداً فقط A را prevote کند، مگر prevote دو سوم تازه‌تری برای چیز دیگر ببیند.

## قدم بعدی

**Layer 2 و rollupها: optimistic و ZK**: بلاک قطعی، بلاک بزرگ‌تر نیست.
