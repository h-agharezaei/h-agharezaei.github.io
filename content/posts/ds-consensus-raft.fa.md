+++
date = '2027-05-18T10:00:00+03:30'
draft = false
title = 'consensus و Raft'
description = 'consensus و Raft با شبیه‌سازی ۵ node در Go با seed ثابت: انتخابات، partition، ترمیم log و safety checker که نسخه‌ی خراب را پیدا می‌کند.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consensus", "raft", "go", "simulation"]
cover = { image = "/images/covers/ds-consensus-raft.fa.png", alt = "consensus و Raft", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-sharding-consistent-hashing/) داده را بین nodeها پخش کرد. کپی‌ها سؤال سخت‌تری دارند: چند node چطور روی یک ترتیب برای نوشتن‌ها توافق کنند، وقتی بعضی crash می‌کنند و شبکه دروغ می‌گوید؟ این همان {{< term "consensus" "consensus" >}} است. یک {{< term "raft" "Raft" >}} حداقلی (مقاله‌ی Ongaro و Ousterhout) می‌سازم و خرابش می‌کنم. ببینید: [replication و quorum](/fa/posts/ds-replication-quorum/)، [مدل‌های consistency](/fa/posts/ds-consistency-models/)، [CAP](/fa/posts/ds-cap-pacelc/) و [timeoutها](/fa/posts/ds-timeouts-retries-backoff/).

> صادقانه: **شبیه‌سازی** در Go 1.26 روی یک ماشین. یک حلقه‌ی تک‌نخی ۵ node را جلو می‌برد؛ شبکه (تأخیر، گم شدن، تکرار، جابه‌جایی ترتیب، partition) و ساعت شبیه‌سازی‌شده و با seed ثابت‌اند، پس خروجی‌ها تکرارپذیرند. فقط شمارش. پیاده نشده: تغییر عضویت، snapshot، دیسک واقعی، read-index. خوشه‌ی واقعی Raft اجرا نشد.

## سه بخش

**انتخابات.** زمان به termها تقسیم می‌شود. followerی که ۱۲ تا ۲۳ tick (تصادفی) چیزی نشنود candidate می‌شود، term را زیاد می‌کند و رأی می‌خواهد. هر node در هر term یک بار رأی می‌دهد، فقط به candidateی که log‌اش دست‌کم به‌روز مثل log خودش باشد. اکثریت برنده است ({{< term "leader-election" "leader election" >}}). term و رأی بعد از crash می‌مانند؛ بقیه از بین می‌روند.

**تکثیر.** فقط leader به {{< term "replicated-log" "replicated log" >}} اضافه می‌کند و `AppendEntries(prevIndex, prevTerm, entries)` می‌فرستد. follower اگر آن entry قبلی را نداشته باشد رد می‌کند؛ leader عقب می‌رود تا logها یکی شوند، بعد ته‌ی متفاوت را بازنویسی می‌کند.

**commit.** entry وقتی committed است که اکثریت آن را داشته باشد، اما leader فقط برای entryهای term خودش replica می‌شمارد. entryهای قدیمی غیرمستقیم commit می‌شوند، برای همین leader تازه اول یک no-op اضافه می‌کند.

```go
if cnt >= c.maj() && (n.Log[N-1].Term == n.Term || c.cfg.BugOldTerm) { // commit N }
```

## انتخابات و بعد crash شدن leader

```
t= 12  n2 election timeout -> candidate, term 1
t= 13  n0 votes for n2 in term 1
t= 13  n1 votes for n2 in term 1
t= 13  n3 votes for n2 in term 1
t= 15  n4 votes for n2 in term 1
t= 15  n2 wins term 1 with a majority -> LEADER
-- leader n2 log [1:noop 1:x=1 1:y=2 1:x=3] commit=4
t= 30  n2 CRASH (term 1, log 4, commit 4)
t= 47  n1 election timeout -> candidate, term 2
t= 49  n3 votes for n1 in term 2
t= 50  n0 votes for n1 in term 2
t= 52  n1 wins term 2 with a majority -> LEADER
t= 53  n4 election timeout -> candidate, term 2
-- new leader n1 term 2 log [1:noop 1:x=1 1:y=2 1:x=3 2:noop] commit=5 kv=map[x:3 y:2]
```

n2 اول timeout شد و برنده شد. بعد از مرگش entryهای committed روی leader تازه ماندند. n4 دیر و در همان term 2 timeout شد، باخت و follower n1 شد.

## یک partition

leader قدیمی n2 و n3 از n0 و n1 و n4 جدا می‌شوند. کلاینت در سمت کوچک روی n2 می‌نویسد:

```
t=108  n0 wins term 5 with a majority -> LEADER
  n2 term=1 role=leader log=7 commit=3
  n3 term=1 role=follower log=7 commit=3
  n0 term=5 role=leader log=6 commit=6
  n1 term=5 role=follower log=6 commit=6
  n4 term=5 role=follower log=6 commit=6
old leader n2 log during partition [1:noop 1:x=1 1:y=2 1:a=1 1:b=2 1:c=3 1:z=9]
t=148  HEAL
old leader n2 log after heal      [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8] role=follower commit=6
```

leader اقلیت چهار نوشتن پذیرفت ولی commit روی ۳ ماند: دو node اکثریت نیستند. سمت دیگر leader انتخاب کرد و تا ۶ commit کرد. بعد از heal، n2 term 5 را دید، کنار رفت و entryهای commit‌نشده‌اش پاک شد؛ به کسی نگفته بودند committed‌اند. هر دو {{< term "quorum" "quorum" >}} یک node مشترک دارند، پس دو سمت {{< term "network-partition" "network partition" >}} هرگز هر دو commit نمی‌کنند؛ بدون این به {{< term "split-brain" "split-brain" >}} می‌رسید.

## safety checker

هر اجرا برای چهار ویژگی چک می‌شود:

- **Election Safety:** در هر term حداکثر یک leader.
- **Log Matching:** اگر دو log در یک index روی term یک entry هم‌نظر باشند، روی همه‌ی قبلی‌ها هم هم‌نظرند.
- **Leader Completeness:** leader تازه همه‌ی entryهای committed را دارد.
- **State Machine Safety:** هیچ دو nodeای در یک index دو فرمان متفاوت اعمال نمی‌کنند.

هر اجرا ۵ node، ۱۰۰۰ tick، ۱۰٪ گم شدن، ۵٪ تکرار، تأخیر ۱ تا ۶، crash و restart و partition تصادفی و crash اضافه‌ی leader. ۳۰۰۰ seed، کد درست:

```
correct Raft                       runs=3000 violations=0
  crashes=91790 partitions=21155 msgs sent=4263233 dropped=810305 duplicated=173709
  leaders elected=52685 entries committed=176166
  checks: election-safety=52685 leader-completeness=52685 log-matching=3030000 state-machine=1795219
```

صفر نقض. checkerی که فعال نشود شاید کور باشد؛ پس کد را خراب می‌کنم.

## خراب کردن عمدی

نسخه‌ی ۱ باگ Figure 8 مقاله است: entry مربوط به term قدیمی را به‌محض داشتن اکثریت commit کن. نسخه‌ی ۲ هنگام رأی دادن چک «به‌روز بودن log» را حذف می‌کند.

```
BROKEN: old-term entries by count  runs=3000 violations=2
  first failing seed 373: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    t=879  n0 wins term 45 with a majority -> LEADER
  same seed 373 with the correct code: violation=""
BROKEN: no up-to-date vote check   runs=3000 violations=2963
  first failing seed 1: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  same seed 1 with the correct code: violation=""
```

باگ اول نادر است (۲ از ۳۰۰۰): لازم است leader در لحظه‌ی بد بمیرد و node کهنه برنده شود. دومی تقریباً همه‌ی اجراها را می‌شکند. هر دو entry committed را گم می‌کنند؛ همان seedها با قوانین درست پاس می‌شوند و تست آن‌ها را ثابت می‌کند.

## چند node؟

k تا از n node را از ابتدا crash کردم (هر کدام ۲۰ seed) و پرسیدم ۵ فرمان commit می‌شود یا نه:

```
3      2         yes yes no no  => tolerates 1 (formula (n-1)/2 = 1)
4      3         yes yes no no no  => tolerates 1 (formula (n-1)/2 = 1)
5      3         yes yes yes no no no  => tolerates 2 (formula (n-1)/2 = 2)
6      4         yes yes yes no no no no  => tolerates 2 (formula (n-1)/2 = 2)
```

تحمل f خرابی به 2f+1 node نیاز دارد؛ node چهارم هزینه می‌آورد، نه تحمل. جدول ۱ تا ۷ یک تست است.

## چند نکته‌ی مهم

- هر نوشتن از leader می‌گذرد. leader برکنارشده شاید خبر نداشته باشد و خواندنش کهنه باشد؛ خواندن {{< term "linearizability" "linearizable" >}} به read-index یا lease نیاز دارد (نام برده شد، ساخته نشد).
- node برگشته می‌تواند termها را بالا ببرد و leader سالم را مختل کند؛ pre-vote این را حل می‌کند (ساخته نشد).
- Raft و Paxos یک مسئله را حل می‌کنند. etcd و Consul از Raft استفاده می‌کنند. NATS تکثیر JetStream را مبتنی بر Raft مستند کرده؛ دوباره نخواندم. ببینید [JetStream در production](/fa/posts/nats-jetstream-production/).
- در تجربه‌ی من persistence جای باگ است: sync نکردن term یا رأی قبل از پاسخ، Election Safety را می‌شکند. شبیه‌سازی من آن‌ها را در حافظه نگه می‌دارد و این را نشان نمی‌دهد.
- نیافتن نقض در ۳۰۰۰ اجرا شاهد است، نه اثبات.

## تمرین

no-op leader را حذف کنید (قانون commit را نگه دارید) و ۳۰۰۰ seed را دوباره اجرا کنید. safety می‌شکند؟ چه چیزی کندتر می‌شود و چرا؟

## قدم بعدی

«saga یا 2PC؟»: consistency بین چند سرویس بدون یک log مشترک.
