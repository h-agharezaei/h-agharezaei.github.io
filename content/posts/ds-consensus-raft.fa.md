+++
date = '2027-05-18T10:00:00+03:30'
draft = false
title = 'consensus و Raft'
description = 'consensus و Raft با شبیه‌سازی ۵ node در Go با seed ثابت: انتخابات، partition، ترمیم log و safety checker که نسخه‌ی خراب را پیدا می‌کند.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consensus", "raft", "go", "simulation"]
cover = { image = "/images/covers/ds-consensus-raft.fa.png", alt = "consensus و Raft", hiddenInSingle = true }
+++

دو ماشین هر دو فکر می‌کنند leader هستند. کلاینتی `balance=100` را به یکی می‌نویسد، کلاینت دیگری `balance=50` را به دیگری، و هر دو نوشتن پذیرفته می‌شود. وقتی شبکه درست می‌شود دو تاریخچه‌ی متفاوت وجود دارد و هیچ‌کس نمی‌تواند بگوید کدام درست است. این {{< term "split-brain" "split-brain" >}} است، و همان شکستی که [replication و quorum](/fa/posts/ds-replication-quorum/) باز گذاشت: آن مقاله تأییدها را می‌شمرد، ولی نگفت چه کسی حق دارد leader باشد و همه چطور روی ترتیب نوشتن‌ها توافق می‌کنند.

این‌که گروهی از ماشین‌ها روی یک چیز به توافق برسند، حتی وقتی بعضی‌شان crash می‌کنند و پیام‌ها گم می‌شوند، {{< term "consensus" "consensus" >}} (اجماع) نام دارد. «یک چیز» می‌تواند یک مقدار باشد («leader کیست؟») یا فهرستی مرتب از دستورها («log نوشتن‌ها»). پایه‌ی سرویس‌های هماهنگی و پایگاه‌داده‌های replicate‌شده است، و sharding ([مقاله‌ی قبل](/fa/posts/ds-sharding-consistent-hashing/)) آن را حذف نمی‌کند: هر shard هنوز به آن نیاز دارد. {{< term "raft" "Raft" >}} الگوریتم اجماعی است که برای قابل‌فهم بودن طراحی شده، از مقاله‌ای از Ongaro و Ousterhout. نسخه‌ی حداقلی‌اش را در Go می‌سازم و بعد سعی می‌کنم خرابش کنم.

این مقاله اول درباره‌ی ایده‌هاست، با یک مثال کوچک دست‌کشیده، و بعد درباره‌ی شبیه‌سازی‌ای که نشان می‌دهد این ایده‌ها کار می‌کنند و وقتی یک قاعده حذف شود چه می‌شود. به [مدل‌های consistency](/fa/posts/ds-consistency-models/)، [CAP و PACELC](/fa/posts/ds-cap-pacelc/) و [timeoutها](/fa/posts/ds-timeouts-retries-backoff/) تکیه دارد.

> این یک **شبیه‌سازی** در Go است که با Go 1.27 دوباره اجرا شد (اجرای اصلی با Go 1.26 بود؛ خروجی همان است). یک حلقه‌ی تک‌نخی ۵ node را جلو می‌برد. شبکه (تأخیر، گم شدن، تکرار، جابه‌جایی ترتیب، partition) و ساعت شبیه‌سازی‌شده و با seed ثابت‌اند، پس هر اجرا همان خروجی را می‌دهد. شمارش نشان می‌دهم، نه زمان. پیاده نشده: تغییر عضویت، snapshot، دیسک واقعی و read-index. خوشه‌ی واقعی Raft اجرا نکردم.

## ایده با زبان ساده

Raft روی یک قاعده بنا شده: **تا اکثریت چیزی را نداشته باشد، آن چیز حساب نمی‌شود.** با ۳ node اکثریت ۲ است، با ۵ node برابر ۳. هر دو اکثریت دست‌کم یک node مشترک دارند، همان هم‌پوشانی‌ای که در مقاله‌ی قبل R + W > N را کارآمد کرد. آن node مشترک راهی است که یک تصمیم تازه از تصمیم قدیمی خبردار می‌شود.

روی این قاعده Raft سه بخش دارد:

1. **انتخابات.** در هر زمان node‌ها روی حداکثر یک leader برای هر بازه‌ی زمانی توافق دارند. زمان به بازه‌های شماره‌دار تقسیم می‌شود که **term** نام دارند.
2. **تکثیر.** فقط leader نوشتن را می‌پذیرد. هر نوشتن را به log خودش اضافه می‌کند و برای followerها کپی می‌کند.
3. **commit.** وقتی اکثریتِ node‌ها نوشتن را ذخیره کردند، آن نوشتن تمام‌شده یا committed حساب می‌شود.

این هم یک trace دست‌کشیده با ۳ node به اسم S1 و S2 و S3 (تصویری که خودم ساختم، نه خروجی دمو). همه‌ی node‌ها به‌صورت follower در term ۰ با log خالی شروع می‌کنند. نشانه‌گذاری log این است: `term:command`.

```
S2's timer fires first.
  S2 becomes a candidate in term 1, votes for itself, asks S1 and S3 for a vote.
  S1 has not voted in term 1 yet -> votes yes. S2 now has 2 of 3 votes = majority.
  S2 is the leader of term 1.

A client sends x=1.
  S2 appends it:   S2 log [1:x=1]
  S2 sends AppendEntries(prevIndex=0, entries=[1:x=1]) to S1 and S3.
  S1 stores it:    S1 log [1:x=1]  -> replies OK.
  Now S2 and S1 hold it = 2 of 3 = majority  -> commit index = 1. S2 applies x=1.
  (S3 never got the message.)

S2 crashes.
  S1 and S3 stop hearing S2. S1's timer fires: S1 becomes a candidate in term 2.
  S3 votes for S1 (its log is empty, S1's is longer, so S1 is at least as up to date).
  S1 is the leader of term 2, and x=1 is still in its log.
```

چرا `x=1` که committed شده نمی‌تواند گم شود؟ چون روی یک اکثریت است، و candidate برای برنده شدن رأی یک اکثریت را لازم دارد. این دو گروه یک node مشترک دارند. و node فقط به candidateای رأی می‌دهد که log‌اش دست‌کم به‌اندازه‌ی log خودش به‌روز باشد. پس candidateای که `x=1` را ندارد، مثل S3، هیچ‌وقت رأی S1 را نمی‌گیرد. leader جدید همیشه همه‌ی چیزهای committed را دارد.

یک وضعیت دیگر: log یک follower می‌تواند ته‌ای داشته باشد که leader با آن موافق نیست، مثلاً بازمانده از leader قدیمی‌ای که crash کرد:

```
leader   [1:a 1:b 2:c]
follower [1:a 1:b 1:z]
```

leader پیام `AppendEntries(prevIndex=2, prevTerm=1, [2:c])` را می‌فرستد: «بعد از entry شماره‌ی ۲ تو که term آن ۱ است، `2:c` را بگذار». follower یک entry شماره‌ی ۲ منطبق دارد، پس می‌پذیرد. entry شماره‌ی ۳ او (`1:z`) در تضاد است، پس حذف می‌شود و `2:c` جایش می‌آید. اگر follower entry شماره‌ی ۲ منطبق *نداشت*، رد می‌کرد و leader یک entry عقب می‌رفت و دوباره امتحان می‌کرد، تا logها یکی شوند.

## قاعده‌ها، کمی دقیق‌تر

**انتخابات.** followerی که ۱۲ تا ۲۳ tick (تصادفی) از leader چیزی نشنود candidate می‌شود، term را یکی زیاد می‌کند و رأی می‌خواهد. تصادفی بودن باعث می‌شود بعید باشد دو node با هم timeout بزنند. هر node در هر term یک بار رأی می‌دهد، و فقط به candidateای که log‌اش دست‌کم به‌اندازه‌ی log خودش به‌روز باشد. اکثریت برنده است ({{< term "leader-election" "leader election" >}}). term و رأی و log هر node بعد از crash می‌مانند؛ بقیه‌چیز (commit index و state اعمال‌شده) از بین می‌رود و دوباره ساخته می‌شود.

**تکثیر.** فقط leader به {{< term "replicated-log" "replicated log" >}} اضافه می‌کند. `AppendEntries(prevIndex, prevTerm, entries)` می‌فرستد. follower اگر entry قبلی را نداشته باشد رد می‌کند. leader عقب می‌رود تا logها یکی شوند و ته‌ی متفاوت را بازنویسی می‌کند.

**commit.** entry وقتی committed است که اکثریت آن را داشته باشد، ولی یک نکته‌ی ظریف هست: leader فقط برای entryهای **term خودش** replica می‌شمارد. entryهای قدیمی‌تر غیرمستقیم committed می‌شوند، وقتی entry جدیدتری روی آن‌ها commit شود. برای همین leader تازه، به‌محض برنده شدن، یک entry خالی (no-op) در term خودش اضافه می‌کند. بررسی در کد دمو همین خط است، که `BugOldTerm` کلیدی است که بعداً برای خراب کردن عمدی‌اش به کار می‌برم:

```go
if cnt >= c.maj() && (n.Log[N-1].Term == n.Term || c.cfg.BugOldTerm) { // commit N }
```

`cnt` تعداد node‌هایی است که entry شماره‌ی `N` را دارند، `c.maj()` اکثریت است و شرط دوم همان قاعده‌ی «term خودش» است.

## انتخابات، و بعد crash leader

دموی اول (`go run . election`) ۵ node را با ۲٪ گم شدن پیام راه می‌اندازد. منتظر leader می‌ماند، سه دستور (`x=1` و `y=2` و `x=3`) می‌فرستد، leader را crash می‌دهد و منتظر leader جدید می‌ماند. خروجی واقعی:

```
== (a) first election, then (b) leader crash ==
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

از بالا بخوانیم:

- در `t=12` تایمر تصادفی n2 اول تمام شد، پس candidate در term ۱ شد. سه رأی در `t=13` همان node‌های دیگرند که به او رأی داده‌اند، و خط «wins» در `t=15` لحظه‌ای است که پاسخ‌های رأی کافی به n2 برگشت: رأی خودش به‌علاوه‌ی دو رأی دیگر می‌شود ۳ از ۵، یعنی اکثریت. پیام‌ها یک tick یا بیشتر طول می‌کشند، برای همین برنده شدن بعد از رأی‌ها می‌آید.
- اولین خط log نشان می‌دهد leader چه دارد: `noop`ی که هنگام برنده شدن اضافه کرد (شماره‌ی ۱) و بعد سه دستور. `commit=4` یعنی هر چهار entry committed است.
- n2 در `t=30` crash می‌کند. followerها دیگر heartbeat نمی‌شنوند و در `t=47` تایمر n1 اول تمام می‌شود: انتخابات جدید، term ۲. دو node به او رأی می‌دهند و در `t=52` برنده می‌شود.
- خط آخر نکته‌ی اصلی است. log leader جدید همان log قدیمی به‌علاوه‌ی یک `2:noop` جدید است، پس هر entry committed زنده ماند. `kv=map[x:3 y:2]` همان state machine (یک map ساده‌ی کلید و مقدار) است: `x` با `x=3` بعدی بازنویسی شد.
- تایمر n4 در `t=53` تمام شد، یک tick بعد از این‌که n1 برنده شده بود، پس انتخابات خودش را برای term ۲ شروع کرد. نمی‌تواند برنده شود: بقیه در term ۲ رأی داده‌اند. وقتی heartbeat بعدی n1 برسد، n4 دوباره follower می‌شود. دمو این مرحله‌ی آخر را چاپ نمی‌کند؛ از قاعده‌های بالا نتیجه می‌شود.

## یک partition

حالا حالتی که split-brain می‌سازد. پنج node، و شبکه دو نیم شده: leader قدیمی n2 و n3 یک طرف‌اند، و n0 و n1 و n4 طرف دیگر. کلاینت‌ها نوشتن را به n2، یعنی leader قدیمی در سمت کوچک، می‌فرستند. دمو وضعیت هر دو سمت را چاپ می‌کند و بعد شبکه را وصل می‌کند (`go run . partition`):

```
== (c) partition: minority cannot commit ==
before: old leader n2 term 1 commit=3 log [1:noop 1:x=1 1:y=2]
t=108  n0 wins term 5 with a majority -> LEADER
  n2 term=1 role=leader log=7 commit=3
  n3 term=1 role=follower log=7 commit=3
  --
  n0 term=5 role=leader log=6 commit=6
  n1 term=5 role=follower log=6 commit=6
  n4 term=5 role=follower log=6 commit=6
  --
old leader n2 log during partition [1:noop 1:x=1 1:y=2 1:a=1 1:b=2 1:c=3 1:z=9]
t=148  HEAL
old leader n2 log after heal      [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8] role=follower commit=6
new leader n0 log                 [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8]
safety violation: ""
```

- **سمت اقلیت** (بلوک اول). n2 هنوز فکر می‌کند leader term ۱ است و چهار نوشتن تازه (`a=1` و `b=2` و `c=3` و `z=9`) را پذیرفته، پس log‌اش ۷ entry دارد و n3 آن‌ها را کپی کرده. اما **`commit=3` تکان نخورده**: دو node از پنج تا اکثریت نیستند، پس هیچ‌کدام از آن چهار نوشتن commit نمی‌شود.
- **سمت اکثریت** (بلوک دوم). سه node در `t=108` n0 را انتخاب کردند. term برابر ۵ است، پس termهای ۲ و ۳ و ۴ بدون leader گذشتند؛ دمو اینجا فقط خط‌های LEADER را چاپ می‌کند، پس نمی‌توانم بگویم چرا (گم شدن پیام یا candidateهای رقیب دلیل‌های معمولی‌اند). leader جدید `p=7` و `q=8` را commit کرد و `commit=6` دارد.
- **بعد از وصل شدن** (`t=148`). n2 پیامی با term ۵ می‌گیرد، می‌بیند term ۱ خودش قدیمی است و follower می‌شود. چهار entry commit‌نشده‌اش با log leader بازنویسی می‌شوند. هیچ‌کس هیچ‌وقت نشنید آن چهار نوشتن committed شده‌اند، پس چیزی که به کلاینتی قول داده شده بود گم نشد.
- خط آخر، `safety violation: ""`، یعنی checker می‌گوید هیچ ویژگی‌ای نشکست.

دلیل این‌که دو سمت نمی‌توانستند هر دو commit کنند همان حساب ابتدایی است: هر دو اکثریت یک node مشترک دارند، پس دو سمت یک {{< term "network-partition" "network partition" >}} هیچ‌وقت نمی‌توانند هر دو اکثریت داشته باشند. بدون این قاعده همان split-brain ابتدای مقاله پیش می‌آید.

## checker ویژگی‌های safety

یک دمو و دو خروجی چیز زیادی ثابت نمی‌کند؛ راه بهتر برای اعتماد این است که یک checker هزاران اجرای تصادفی را تماشا کند. هر اجرا چهار ویژگی را از مقاله‌ی Raft بررسی می‌کند:

- **Election Safety:** حداکثر یک leader در هر term. (یک leader قدیمی از term قبلی ممکن است مدتی هنوز باشد، مثل partition بالا، ولی دو leader هیچ‌وقت در یک term نیستند.)
- **Log Matching:** اگر دو log یک entry با شماره و term یکسان دارند، logها تا آن شماره کاملاً یکی‌اند.
- **Leader Completeness:** log هر leader جدید همه‌ی entryهای committed تا آن لحظه را دارد. (ویژگی‌ای که در trace دست‌کشیده دیدیم.)
- **State Machine Safety:** هیچ دو node دستورهای متفاوتی را در یک شماره‌ی log اعمال نمی‌کنند.

هر اجرا ۵ node و ۱۰۰۰ tick دارد، با ۱۰٪ گم شدن پیام، ۵٪ تکرار، تأخیر ۱ تا ۶ tick (پس پیام‌ها می‌توانند نامرتب برسند)، crashهای تصادفی، restart، partition، و crashهای اضافه که leader فعلی را هدف می‌گیرند. کلاینت‌ها به هر که leader است می‌نویسند. ۳۰۰۰ seed را روی کد درست اجرا کردم (`go run . safety`):

```
correct Raft                       runs=3000 violations=0
  crashes=91790 partitions=21155 msgs sent=4263233 dropped=810305 duplicated=173709
  leaders elected=52685 entries committed=176166
  checks: election-safety=52685 leader-completeness=52685 log-matching=3030000 state-machine=1795219
```

خط اول جواب است: **صفر تخطی در ۳۰۰۰ اجرا**. خط‌های بعد نشان می‌دهند checker واقعاً چیزی برای دیدن داشت: بیش از ۹۱ هزار crash، ۲۱ هزار partition و ۵۲۶۸۵ انتخابات. خط `checks` می‌شمارد هر ویژگی چند بار آزمایش شد: election-safety و leader-completeness یک بار برای هر leader انتخاب‌شده، log-matching برای هر جفت node در هر ۱۰ tick، و state-machine برای هر entryای که یک node اعمال کرد.

checkerی که هیچ‌وقت چیزی نمی‌گیرد شاید فقط کور باشد. پس قدم بعدی این است که کد را عمداً غلط کنیم و ببینیم checker متوجه می‌شود.

## خراب کردن عمدی

دو باگ ساختم، هرکدام پشت یک کلید (`go run . broken`). **نسخه‌ی ۱** وضعیتی است که شکل ۸ مقاله‌ی Raft هشدارش را می‌دهد: leader entryای از term *قدیمی‌تر* را به‌محض این‌که اکثریت دارد commit می‌کند، به‌جای این‌که منتظر entry از term خودش بماند. **نسخه‌ی ۲** هنگام رأی دادن بررسی «log دست‌کم به‌روز» را رد می‌کند. هر دو تغییرهای کوچک و وسوسه‌انگیزی‌اند. خروجی واقعی:

```
BROKEN: old-term entries by count  runs=3000 violations=2
  crashes=91781 partitions=21155 msgs sent=4263085 dropped=810292 duplicated=173702
  leaders elected=52682 entries committed=177618
  checks: election-safety=52682 leader-completeness=52682 log-matching=3029850 state-machine=1815410
  first failing seed 373: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
  replay seed 373, last events before the violation:
    t=845  OLD-TERM: index 30 holds a term-9 entry, committed by counting replicas
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    ...
    t=853  n2 (leader, term 38) commits up to index 38
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    t=861  PARTITION groups=[1 1 1 1 1]
    t=876  n4 restart: term 38, voted 2, log 70 kept; commit/applied/kv lost
    t=879  n0 wins term 45 with a majority -> LEADER
  replay: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
  same seed 373 with the correct code: violation=""
BROKEN: no up-to-date vote check   runs=3000 violations=2963
  crashes=30043 partitions=6986 msgs sent=1312485 dropped=252070 duplicated=52991
  leaders elected=18840 entries committed=81165
  checks: election-safety=18840 leader-completeness=18840 log-matching=981960 state-machine=654398
  first failing seed 1: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  replay seed 1, last events before the violation:
    ...
    t=338  n1 CRASH (term 14, log 36, commit 36)
    t=340  n3 CRASH (term 14, log 36, commit 34)
    t=370  n1 restart: term 14, voted 1, log 36 kept; commit/applied/kv lost
    t=381  n3 restart: term 14, voted 1, log 36 kept; commit/applied/kv lost
    t=389  n4 wins term 17 with a majority -> LEADER
  replay: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  same seed 1 with the correct code: violation=""
```

عددها چه می‌گویند:

- checker **واقعاً** هشدار می‌دهد. نسخه‌ی ۱ دو اجرا از ۳۰۰۰ را خراب کرد. کم است چون لازم دارد leader یک entry قدیمی را commit کند و بعد در لحظه‌ی بد بمیرد، و بعد nodeای که آن entry را ندارد برنده شود. در seed شماره‌ی ۳۷۳، leader یعنی n2 شماره‌ی ۳۸ را که یک entry از term ۲۵ بود فقط با شمردن نسخه‌ها commit کرد (`t=853`). بعد از یک partition و یک restart، n0 در term ۴۵ بدون آن entry برنده شد و checker گزارش داد Leader Completeness: یک entry committed در leader جدید نبود.
- نسخه‌ی ۲ هر ۲۹۶۳ اجرا از ۳۰۰۰ را خراب کرد، تقریباً همه را. بدون بررسی رأی، nodeای با log کهنه می‌تواند انتخابات را ببرد. در seed شماره‌ی ۱، n4 در term ۱۷ بدون entry committed شماره‌ی ۱ leader شد.
- هر دو خط با شاهد تمام می‌شوند: **همان seed با کد درست هیچ تخطی ندارد.** شبیه‌سازی قطعی است، پس همان seed همان crashها و partitionها را می‌سازد؛ فقط قاعده فرق می‌کند. یک تست (`TestBrokenVariantsAreCaught`) دقیقاً همین دو seed را ثابت نگه می‌دارد.

## چند node لازم است؟

اگر برای همه‌چیز اکثریت لازم است، چند node را می‌توانیم از دست بدهیم؟ آخرین دمو (`go run . sweep`) خوشه‌ای با n node می‌سازد، در همان ابتدا k تای آن‌ها را crash می‌دهد و می‌پرسد آیا ۵ دستور در ۴۰۰ tick هنوز commit می‌شوند، برای هر یک از ۲۰ seed. هر ردیف یک اندازه‌ی خوشه است و مقدارهای `yes` و `no` برای k برابر ۰ و ۱ و ۲ و به همین ترتیب‌اند:

```
nodes  majority  crashed-from-start -> committed 5 commands in 400 ticks?
1      1         yes no  => tolerates 0 (formula (n-1)/2 = 0)
2      2         yes no no  => tolerates 0 (formula (n-1)/2 = 0)
3      2         yes yes no no  => tolerates 1 (formula (n-1)/2 = 1)
4      3         yes yes no no no  => tolerates 1 (formula (n-1)/2 = 1)
5      3         yes yes yes no no no  => tolerates 2 (formula (n-1)/2 = 2)
6      4         yes yes yes no no no no  => tolerates 2 (formula (n-1)/2 = 2)
7      4         yes yes yes yes no no no no  => tolerates 3 (formula (n-1)/2 = 3)
```

ردیف ۵ node را بگیرید: با ۰ یا ۱ یا ۲ node خراب commit می‌کند و با ۳ یا بیشتر نه، چون ۲ node زنده اکثریتِ ۵ نیست. برای تحمل f خرابی به 2f + 1 node نیاز دارید. ردیف‌های ۴ و ۶ جالب‌اند: node چهارم بیشتر از ۳ node خرابی تحمل نمی‌کند (باز فقط ۱)، و node ششم بیشتر از ۵ node. تعداد زوج node هزینه اضافه می‌کند ولی تحمل اضافه نمی‌دهد. یک تست این جدول را برای هر اندازه از ۱ تا ۷ اجرا می‌کند.

## تله‌های Raft

- **هر نوشتن از leader می‌گذرد، و leader می‌تواند کهنه باشد.** leaderی که کنار گذاشته شده ممکن است هنوز نداند، پس خواندن از او می‌تواند کهنه باشد. خواندن linearizable به read-index یا lease نیاز دارد (اسمشان را می‌آورم، نساختمشان).
- **nodeی که دوباره وصل می‌شود می‌تواند leader سالم را مختل کند.** nodeی که جدا مانده مدام timeout می‌زند و term را بالا می‌برد؛ وقتی برگردد، term بزرگش leader را مجبور می‌کند کنار برود. pre-vote راه معمول حل آن است (آن هم ساخته نشده).
- **Raft و Paxos یک مسئله را حل می‌کنند.** etcd و Consul از Raft استفاده می‌کنند. NATS replication در JetStream را مبتنی بر Raft مستند کرده، که برای این مقاله دوباره نخواندم؛ ببینید [JetStream در production](/fa/posts/nats-jetstream-production/).
- **persistence جایی است که باگ‌ها قایم می‌شوند.** طبق تجربه‌ی من بیشترین باگ‌ها همین‌جا جمع می‌شوند: اگر nodeی پیش از ذخیره‌ی term و رأی روی دیسک به درخواست رأی جواب بدهد، یک crash می‌تواند باعث شود در یک term دو بار رأی بدهد که Election Safety را می‌شکند. شبیه‌سازی درون‌حافظه‌ای من نمی‌تواند این را نشان دهد.
- **پیدا نکردن چیزی در ۳۰۰۰ اجرا شاهد است، نه اثبات.** دو نسخه‌ی خراب نشان می‌دهند checker باگ پیدا می‌کند؛ باگی که به توالی عجیب‌تری نیاز دارد هنوز می‌تواند قایم بماند.

## تمرین

no-op leader را حذف کنید ولی قاعده‌ی commit را نگه دارید، و ۳۰۰۰ seed را دوباره اجرا کنید. آیا safety می‌شکند؟ چه چیزی کندتر می‌شود و چرا؟ (راهنمایی: فکر کنید یک entry قدیمی پیش از commit شدن به چه چیزی نیاز دارد.)

## قدم بعدی

بعد، «saga یا 2PC؟» می‌آید. Raft برای یک گروه از node‌ها یک log توافق‌شده می‌دهد. یک عملیات کسب‌وکاری که چند سرویس جدا را پوشش می‌دهد، هرکدام با پایگاه‌داده‌ی خودش و بدون log مشترک، چه می‌شود؟
