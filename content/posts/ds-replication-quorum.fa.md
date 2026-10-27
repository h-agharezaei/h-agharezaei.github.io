+++
date = '2027-05-11T10:00:00+03:30'
draft = false
title = 'replication و quorum'
description = 'replication و quorum با شبیه‌سازی Go: نوشتن‌های تأییدشده‌ی گم‌شده، قاعده‌ی R+W>N، read repair، Merkle tree، از دست رفتن LWW و خواندن غیر linearizable.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "replication", "quorum", "consistency", "go"]
cover = { image = "/images/covers/ds-replication-quorum.fa.png", alt = "replication و quorum", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-circuit-breaker-bulkhead/) درباره‌ی زنده‌ماندن در برابر وابستگی بیمار بود. راه زنده‌ماندن در برابر ماشین مرده این است که چند نسخه از داده نگه دارید، یعنی {{< term "replication" "replication" >}}. ببینید [replication با دو instance واقعی](/fa/posts/db-replication-streaming/).

> صادقانه: همه‌ی این‌ها **شبیه‌سازی** Go 1.26 روی یک ماشین است. از دست رفتن پیام و تأخیر عددهای تصادفی با seed ثابت‌اند و فقط شمارش نشان می‌دهم، نه زمان.

## مبتنی بر leader: نوشتن کی تأیید می‌شود؟

یک leader، دو follower، ۲۰ نوشتن، و leader در tick تصادفی crash می‌کند. برای هر حالت ۱۰۰۰ اجرای seed‌دار انجام دادم و نوشتن‌هایی را شمردم که به کلاینت تأیید شده بودند ولی روی followerی که جای leader را گرفت نبودند.

```
  async                                            acked=13170 lost-acked=1505 runs-with-loss= 932  acked/20 with a follower down=20
  semi-sync (1 of 2), promote most advanced        acked=11665 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=20
  semi-sync (1 of 2), promote follower 0 blindly   acked=11665 lost-acked= 417 runs-with-loss= 323  acked/20 with a follower down=20
  sync (2 of 2)                                    acked=10840 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=0
```

async فوراً تأیید می‌کند و در ۹۳۲ اجرا از ۱۰۰۰ نوشتن تأییدشده را گم کرد. صبر برای هر دو follower چیزی گم نمی‌کند، ولی وقتی یک follower خاموش است هیچ نوشتنی را تأیید نمی‌کند؛ همان قطعی که در مقاله‌ی Postgres با یک standby همگام دیدید. semi-sync، یعنی صبر برای هر یک follower، حالت میانی است: بدون گم‌شدن، اما فقط اگر followerی را promote کنید که بیشترین log را دارد. promote کورکورانه ۴۱۷ نوشتن را گم کرد. طبق مستندات Postgres عبارت `synchronous_standby_names = 'ANY 1 (a, b)'` همین را بیان می‌کند؛ من اینجا اجرایش نکردم.

## quorum بدون leader: R + W > N

در طراحی شبیه Dynamo هر replica نوشتن را می‌پذیرد. N=3. نوشتن به هر سه می‌رود و اگر W تأیید برگردد موفق است؛ خواندن از هر سه می‌پرسد و جدیدترین پاسخ از R پاسخ را برمی‌دارد. وقتی R+W>N باشد، {{< term "quorum" "quorum" >}} خواندن و نوشتن هم‌پوشانی دارند. در هر یک از ۲۰۰۰۰ دور، نسخه‌ی تازه‌ای از یکی از ۸ کلید نوشته و سپس خوانده می‌شود؛ هر پیام با احتمال ۲۰٪ گم می‌شود.

```
  R=1 W=1 R+W>N=false failed-writes=  941 failed-reads=  946 stale= 3368 read-uncommitted=  404
  R=1 W=3 R+W>N=true  failed-writes=14733 failed-reads=  946 stale=    0 read-uncommitted=12822
  R=3 W=1 R+W>N=true  failed-writes=  955 failed-reads=14685 stale=    0 read-uncommitted=  212
  R=2 W=2 R+W>N=true  failed-writes= 5897 failed-reads= 5884 stale=    0 read-uncommitted= 3763
```

stale یعنی قدیمی‌تر از جدیدترین نوشتن تأییدشده. هر جا R+W>N باشد صفر است و برای R=1 و W=1 برابر ۳۳۶۸. اما به `read-uncommitted` نگاه کنید: نوشتنی که به کمتر از W replica رسیده «ناموفق» گزارش می‌شود، ولی مقدارش روی همان replicaها می‌ماند و خواندن‌های بعدی آن را برمی‌گردانند.

## ترمیم: read repair، anti-entropy، hinted handoff

{{< term "read-repair" "Read repair" >}} جدیدترین نسخه را روی پاسخ‌دهنده‌های عقب‌مانده می‌نویسد. بعد از ۳۰۰۰ عملیات روی ۲۵۶ کلید، تعداد جفت‌های replica-کلید که از جدیدترین نسخه عقب بودند: ۱۴۶ بدون repair و ۱۱۱ با آن. فقط به کلیدهای خوانده‌شده کمک می‌کند. {{< term "anti-entropy" "Anti-entropy" >}} در پس‌زمینه replicaها را با {{< term "merkle-tree" "Merkle tree" >}} مقایسه می‌کند: rootهای برابر یعنی داده‌ی برابر، و فقط در زیردرخت‌های متفاوت پایین می‌روید.

```
  differing keys=0  found=[]  hash comparisons=1 (full scan: 1024)
  differing keys=1  found=[17]  hash comparisons=21 (full scan: 1024)
  differing keys=3  found=[17 18 900]  hash comparisons=41 (full scan: 1024)
```

{{< term "hinted-handoff" "Hinted handoff" >}} را فقط توضیح می‌دهم و پیاده نکردم: تا وقتی replica خاموش است، node دیگری نوشتن‌هایش را نگه می‌دارد و بعداً تحویل می‌دهد. این sloppy quorum است و هم‌پوشانی بالا دیگر برقرار نیست.

## conflict: LWW در برابر version vector

دو نویسنده یک کلید را از دو replica مختلف به‌روز می‌کنند، ۲۰۰۰ آزمایش؛ نیمی واقعاً همزمان، نیمی که نویسنده‌ی دوم اولی را خوانده بود. ساعت‌ها تا ۵ tick انحراف دارند.

```
  concurrent trials=1000: LWW silently lost a write in 1000; version vectors flagged 1000 as concurrent
  causal trials=1000: LWW lost the NEWER write (clock skew) in 355; version vectors false conflicts=0
```

{{< term "last-write-wins" "Last-write-wins" >}} از دو نوشتن همزمان یکی را نگه می‌دارد، پس گم‌شدن یکی ذاتی است. بدتر، با ساعت‌های منحرف در ۳۵۵ حالت علّی نوشتن جدیدتر را دور ریخت. {{< term "version-vector" "version vector" >}} (ببینید [ساعت‌های منطقی](/fa/posts/ds-logical-clocks/)) همه‌ی جفت‌های همزمان را علامت زد و هیچ جفت مرتبی را نه، ولی برنامه باید siblingها را merge کند.

## availability

با p=0.99 برای هر replica، quorum با W نیاز دارد دست‌کم W replica بالا باشند. دقیقاً، W=2 برابر 0.999702 (غیرقابل‌دسترس: 0.000298) و W=3 برابر 0.970299 (0.029701) است؛ با فرمول دوجمله‌ای و تست. Monte Carlo با seed ثابت و 10^6 آزمایش، ۳۲۰ و ۲۹۵۳۷ شکست داد در برابر ۲۹۸ و ۲۹۷۰۱ مورد انتظار. اگر همه‌ی replicaها لازم باشند، عدم‌دسترسی حدود ۱۰۰ برابر می‌شود. فرض شکست‌های مستقل طبق تجربه‌ی من بخش خوش‌بینانه است.

## quorum ها linearizable نیستند

interleaving دست‌نویس، N=3 و R=2 و W=2: نوشتن 1 فقط به replica A رسیده و هنوز برنگشته. خواننده‌ی ۱ از A و B می‌پرسد و ۱ می‌گیرد. خواننده‌ی ۲ بعد از آن شروع می‌کند، از B و C می‌پرسد و ۰ می‌گیرد. با ایده‌ی checker از مقاله‌ی [consistency modelها](/fa/posts/ds-consistency-models/):

```
  writeBack=false reader1 saw 1, reader2 (started later) saw 0, linearizable=false
  writeBack=true  reader1 saw 1, reader2 (started later) saw 1, linearizable=true
```

اگر خواننده‌ها قبل از برگشتن آنچه دیدند را بنویسند، history می‌گذرد. {{< term "linearizability" "Linearizability" >}} در حالت کلی به consensus نیاز دارد؛ Raft و Paxos بعداً در همین سری مقاله‌ی جدا دارند. نمونه‌ی واقعی: `R3` در [JetStream در production](/fa/posts/nats-jetstream-production/).

## چند نکته‌ی مهم

- نوشتن «ناموفق» quorum ممکن است همچنان دیده شود.
- LWW فقط وقتی قابل قبول است که گم‌شدن یک نوشتن قابل قبول باشد.
- failover باید پیشرفته‌ترین follower را انتخاب کند.

## تمرین

replica چهارم اضافه کنید با N=4 و W=3 و R=2 و جدول را دوباره اجرا کنید. زیر message loss چیزی عوض می‌شود؟

## قدم بعدی

مقاله‌ی بعدی «sharding و consistent hashing» است.
