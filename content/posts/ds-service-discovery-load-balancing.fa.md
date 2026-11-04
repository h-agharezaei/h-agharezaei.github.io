+++
date = '2027-06-01T10:00:00+03:30'
draft = false
title = 'service discovery و load balancing'
description = 'service discovery و load balancing با Go: registry با TTL، پنجره‌ی ورودی کهنه، round robin در برابر power of two choices، health check و herd.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "service-discovery", "load-balancing", "nats", "go"]
cover = { image = "/images/covers/ds-service-discovery-load-balancing.fa.png", alt = "service discovery و load balancing", hiddenInSingle = true }
+++
یکی از سه instance سرویس پرداخت شما crash می‌کند. بدون اینکه به کسی خبر بدهد می‌میرد، پس نشانی‌اش هنوز در فهرستی است که همه‌ی کلاینت‌ها استفاده می‌کنند. تا وقتی آن ورودی ناپدید نشود، حدود یک‌سوم درخواست‌ها به نشانی‌ای می‌روند که کسی آنجا جواب نمی‌دهد. حتی retry درست هم این را مجانی نمی‌کند: هر درخواستی که به نشانی مرده خورده باشد قبلاً یک تلاش را هدر داده است.

این پرسشی است که فراخوانی مستقیم سرویس‌به‌سرویس باید جوابش را بداند و bus مقاله‌ی [قبل](/fa/posts/ds-messaging-event-driven/) لازم نداشت: سرویس مقابل الان کجاست؟ instanceها بالا می‌آیند، پایین می‌روند و جابه‌جا می‌شوند، پس جواب مدام عوض می‌شود. پیدا کردن نشانی‌های فعلی را {{< term "service-discovery" "service discovery" >}} (کشف سرویس) می‌گویند. انتخاب یکی از آن‌ها برای هر درخواست load balancing است. مبانی {{< term "load-balancer" "load balancer" >}} در لایه‌ی ۴ و ۷ در [مقاله‌ی شبکه](/fa/posts/net-load-balancer-l4-l7/) آمده است. این مقاله دو پرسش دیگر دارد: چه کسی نشانی‌ها را می‌داند و چه کسی یکی را انتخاب می‌کند.

> برچسب صادقانه: یک ماشین، فقط loopback. در دموی registry، instanceها سرورهای HTTP واقعی روی پورت تصادفی‌اند، ولی ساعت تزریق‌شده است و heartbeatها را حلقه‌ی من می‌فرستد. بخش‌های balancing و health check و herd شبیه‌سازی seedدار صف‌ها هستند، نه شبکه. همه را با Go 1.27 دوباره اجرا کردم و `go test -race` می‌گذرد. شمارش نشان می‌دهم، نه زمان.

## ثابت، DNS یا registry

سه راه رایج برای دانستن اینکه سرویس کجاست هست.

**فهرست ثابت** نشانی‌ها در یک فایل تنظیم ساده‌ترین راه است. با اولین deploy که نشانی عوض شود می‌شکند.

{{< term "dns" "DNS" >}} همه‌جا کار می‌کند و یک نام می‌تواند به چند نشانی اشاره کند. ولی جواب‌های DNS تا {{< term "ttl" "TTL" >}} (مدت اعتبار) خودشان cache می‌شوند و آن cache مال شما نیست. مثلاً resolver خود Go cache نمی‌کند، ولی سیستم‌عامل یا runtime زبان ممکن است (JVM از قدیم cache سنگین داشته؛ نسخه‌تان را بررسی کنید). رکوردهای SRV، یک نوع رکورد DNS، می‌توانند پورت را هم داشته باشند، نه فقط نشانی را.

{{< term "service-registry" "registry" >}} کنترل را به شما می‌دهد. سرویس کوچکی است که نگه می‌دارد کدام instanceها زنده‌اند. هر instance خودش را با یک TTL ثبت می‌کند و با پیام کوچک دوره‌ای، یعنی {{< term "heartbeat" "heartbeat" >}}، مدام آن را تمدید می‌کند. اگر heartbeatها قطع شوند، ورودی منقضی می‌شود و instance از فهرست ناپدید می‌شود. registry هرگز لازم نیست بفهمد instance crash کرده: سکوت خودش علامت است.

## یک registry کوچک و پنجره‌ی کهنگی

یک registry با چهار عملیات ساختم: `/register` و `/renew` و `/deregister` و `/list`. انقضا روی یک ساعت تزریق‌شده چک می‌شود، پس تست‌ها و دمو قطعی‌اند.

آزمایش: سه instance به نام a و b و c هر ۲ tick تمدید می‌کنند. instance b در tick ۱۱ بدون deregister crash می‌کند. آخرین تمدیدش در tick ۱۰ بود، آخرین باری که registry از او خبر گرفت. client در هر tick سه درخواست را به‌صورت round robin روی فهرستی که از registry می‌گیرد می‌فرستد، پس دقیقاً در هر tick یک درخواست به هر instance می‌رسد.

ورودی b را با TTL برابر ۳ tick دنبال کنید. در tick ۱۱ و ۱۲ و ۱۳ آخرین تمدیدش ۱ و ۲ و ۳ tick قدمت دارد، که از TTL بیشتر نیست، پس b هنوز در فهرست است و در هر tick یک درخواست به نشانی مرده می‌رود. در tick ۱۴ ورودی ۴ tick قدمت دارد و منقضی می‌شود. این ۳ tick کهنگی است. این را برای سه TTL اجرا کردم، هرکدام با retry روی instance دیگر هنگام شکست تماس و بدون آن:

```
ttl= 3 retry=false stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 3
ttl= 3 retry=true  stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 0
ttl= 6 retry=false stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 6
ttl= 6 retry=true  stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 0
ttl=10 retry=false stale-ticks=10 wasted-attempts=10 user-visible-failures=10
ttl=10 retry=true  stale-ticks=10 wasted-attempts=10 user-visible-failures= 0
```

instance خراب دقیقاً به‌اندازه‌ی TTL tick در فهرست می‌ماند (`stale-ticks`)، چون درست پیش از crash تمدید کرده بود. در هر tick یک درخواست به آن می‌خورد، پس `wasted-attempts` برابر tickهای کهنگی است. بدون retry هر کدام از این تلاش‌های هدررفته شکستی است که کاربر می‌بیند (`user-visible-failures`). با retry روی instance دیگر کاربر چیزی نمی‌بیند، ولی تلاش باز هم هدر رفته است: retry مشکل را پنهان می‌کند، هزینه‌اش را حذف نمی‌کند.

در این جدول دو داد و ستد هست. TTL کوتاه پنجره‌ی کهنگی را کوچک می‌کند ولی heartbeat زیاد می‌خواهد، و TTLی که به interval heartbeat نزدیک باشد با گم شدن یک تمدید یک instance سالم را منقضی می‌کند. طبق تجربه‌ی من، TTL دست‌کم ۳ برابر interval شروع معقولی است. و آن retryها را محدود کنید ([timeout و backoff](/fa/posts/ds-timeouts-retries-backoff/))، وگرنه ورودی کهنه می‌تواند به retry storm تبدیل شود.

## انتخاب instance

وقتی client فهرست را دارد، کسی باید برای هر درخواست یک instance را انتخاب کند. در load balancing سمت client، خود client عکسی از registry می‌گیرد و انتخاب می‌کند. چهار قاعده‌ی ساده هست:

- **Random**: هر instance‌ای را تصادفی بردار.
- **Round robin**: به نوبت، ۱ و ۲ و ۳ و ۱ و ۲ و ۳.
- **Least in flight**: همه‌ی instanceها را نگاه کن و آن را که کوتاه‌ترین صف را دارد بردار.
- **{{< term "power-of-two-choices" "Power of two choices" >}}** (دو انتخاب): دو instance را تصادفی بردار و درخواست را به آن که صف کوتاه‌تر دارد بفرست.

یک مثال ساختگی برای حس کردن فرق (از دمو نیست). چهار سرور صف‌هایی با ۴ و ۱ و ۶ و ۰ درخواست دارند و درخواست بعدی می‌رسد. round robin اصلاً به صف‌ها نگاه نمی‌کند: اگر نوبت سرور سوم باشد، درخواست همان‌جا می‌رود و صفش ۷ می‌شود. least in flight هر چهار صف را می‌خواند و چهارمی (طول ۰) را برمی‌دارد. power of two دو سرور را تصادفی برمی‌دارد، مثلاً اولی و سومی را، ۴ را با ۶ مقایسه می‌کند و اولی را می‌گیرد. بهترین سرور را پیدا نکرد، ولی بدتر از آن دو را کنار گذاشت، با فقط دو بار خواندن به‌جای چهار.

حالا شبیه‌سازی. ۸ سرور با سرعت‌های مختلف هست: ۴ و ۴ و ۴ و ۴ و ۲ و ۲ و ۱ و ۱ درخواست در tick. ورود درخواست‌ها انفجاری است: ۲۰٪ tickها ۴۰ درخواست می‌آورند و بقیه ۸. اجرا ۲۰۰۰ tick است، با seed ثابت، و «صف» یعنی درخواست‌های منتظر در یک سرور:

```
random           max-queue=1742 avg-queue= 202.40
round-robin      max-queue=1581 avg-queue= 197.50
least-in-flight  max-queue=  14 avg-queue=   1.18
power-of-two     max-queue=  19 avg-queue=   1.81
```

چرا دو مورد اول این‌قدر بد است؟ حساب کنید. میانگین ورود ۰٫۸ × ۸ + ۰٫۲ × ۴۰ = ۱۴٫۴ درخواست در tick است و سرورها در tick می‌توانند ۴+۴+۴+۴+۲+۲+۱+۱ = ۲۲ را سرویس بدهند، پس در مجموع ظرفیت کافی است. ولی random و round robin به‌طور میانگین به هر یک از ۸ سرور سهم برابر ۱۴٫۴ / ۸ = ۱٫۸ درخواست در tick می‌دهند و دو سرور کندتر فقط ۱ درخواست در tick سرویس می‌دهند. صف آن‌ها هر tick حدود ۰٫۸ بزرگ می‌شود، برای همیشه. در ۲۰۰۰ tick این تقریباً ۱۶۰۰ است، که اندازه‌ی بیشینه‌ی صف در دو ردیف اول است. میانگین صف در آن ردیف‌ها، حدود ۲۰۰، هم جور است: دو صفی که تا حدود ۱۶۰۰ رشد می‌کنند میانگین هرکدام حدود ۸۰۰ است و پخش روی ۸ سرور حدود ۲۰۰ می‌شود. least in flight و power of two از این مشکل در امان‌اند چون به صف نگاه می‌کنند: صف بلند دیگر درخواست نمی‌گیرد. power of two تقریباً به خوبی پرسیدن از همه است، با دو بار خواندن به‌جای N. بار کاری ساختگی است، پس شکل نتیجه را بگیرید، نه عددها را.

## balancer کجا زندگی می‌کند

کدی که instance را انتخاب می‌کند می‌تواند در سه جا باشد:

| | سمت client | proxy / سمت سرور | sidecar در {{< term "service-mesh" "service mesh" >}} |
|---|---|---|---|
| چه کسی انتخاب می‌کند | کتابخانه‌ی برنامه | یک proxy مرکزی | proxy کنار هر برنامه |
| hop اضافه | ندارد | یکی | hop محلی |
| مستقل از زبان | نه | بله | بله |
| هزینه | کتابخانه برای هر زبان | proxy گلوگاه/SPOF | یک process بیشتر برای هر instance |

(SPOF یعنی نقطه‌ی شکست واحد.) Envoy و Istio و Linkerd نام‌های رایج در این حوزه‌اند؛ اجرایشان نکردم.

## NATS: discovery بدون registry

broker مقاله‌ی قبل یک میان‌بُر غافلگیرکننده می‌دهد. با {{< term "queue-group" "queue group" >}} روی nats-server توکار، سه responder را روی یک subject بالا آوردم و ۳۰ درخواست فرستادم، بعد responder r2 را کشتم و ۳۰ درخواست دیگر فرستادم، بعد بقیه را کشتم:

```
30 requests, 3 responders: r1=17 r2=2 r3=11
r2 killed, 30 more:        r1=12 r2=0 r3=18
all responders gone:       err = nats: no responders available for request
```

هیچ‌کس چیزی ثبت نکرد. subscription همان ثبت است و سرور وقتی اتصال بسته شود آن را برمی‌دارد. بعد از کشتن r2 هیچ درخواستی به آن نرسید (۰)، و وقتی همه رفتند client خطای «no responders» گرفت. تقسیم بین responderها از اجرایی به اجرای دیگر فرق می‌کند (این عددها از اجرای اصلی است؛ اجراهای دوباره‌ام با Go 1.27 در خط اول ۸ و ۱۳ و ۹ و ۸ و ۹ و ۱۳ دادند). بعد از هر kill ۲۰۰ میلی‌ثانیه صبر کردم تا سرور بسته شدن اتصال را بفهمد. بدون این صبر، در یک اجرای اولیه یک درخواست timeout شد، که همان پنجره‌ی کهنگی در مقیاس کوچک است.

## health check و flapping

registry می‌داند instance زنده است، نه اینکه سالم است. {{< term "health-check" "health checkها" >}} این فاصله را پر می‌کنند. به اصطلاح Kubernetes، liveness می‌پرسد «این instance را restart کنم؟»، readiness می‌پرسد «به آن ترافیک بدهم؟» و startup بوت کند را محافظت می‌کند. checkهای فعال طبق برنامه probe می‌کنند؛ checkهای غیرفعال ترافیک واقعی را می‌بینند و instanceای را که مدام شکست می‌خورد بیرون می‌اندازند، که کار [circuit breaker](/fa/posts/ds-circuit-breaker-bulkhead/) است.

مشکل با instanceای پیدا می‌شود که نه بالا است و نه پایین. در شبیه‌سازی ۵۵٪ probeها موفق‌اند، جمعاً ۱۲۰ probe. اگر instance را با هر probe داخل یا خارج چرخش ببریم، مدام می‌چرخد. {{< term "hysteresis" "hysteresis" >}} یعنی چند probe پشت‌سرهم لازم باشد تا حالت عوض شود. `need 3 ok / 3 fail` یعنی برای برگشتن ۳ موفقیت پشت‌سرهم و برای بیرون رفتن ۳ شکست پشت‌سرهم. سه خط اول می‌شمارند مسیر چند بار عوض شد. سه خط آخر ورودی دیگری دارند: instanceای که ۲۰ probe اول سالم است و از probe ۲۰ به بعد واقعاً مرده است (probeها از ۰ شماره می‌خورند) و نشان می‌دهند در کدام probe بیرون انداخته شد:

```
need 1 ok / 1 fail: route changes=58
need 3 ok / 3 fail: route changes=11
need 5 ok / 5 fail: route changes=3
really down from probe 20, need 1 fails: ejected at probe 20
really down from probe 20, need 3 fails: ejected at probe 22
really down from probe 20, need 5 fails: ejected at probe 24
```

لازم کردن ۳ پشت‌سرهم تعداد چرخش را از ۵۸ به ۱۱ می‌رساند و ۵ پشت‌سرهم به ۳. بها در نیمه‌ی دوم است: با need برابر ۳ یک instance واقعاً مرده ۲ probe دیرتر از need برابر ۱ بیرون انداخته می‌شود و با ۵ حدود ۴ probe دیرتر. چرخش کمتر، تشخیص کندتر.

## herd بعد از restart شدن registry

یک خرابی دیگر که از هم‌زمانی می‌آید. اگر registry restart شود و ورودی‌هایش را از دست بدهد، ۵۰۰ instance همه با هم دوباره ثبت می‌شوند. این شبیه‌سازی seedدار است که در آن هر instance پیش از ثبت دوباره بین ۰ و `spread` tick تصادفی صبر می‌کند. خروجی بیشترین تعداد ثبت در یک tick است:

```
spread= 0 ticks: peak registrations in one tick=500
spread=10 ticks: peak registrations in one tick=64
spread=50 ticks: peak registrations in one tick=16
```

بدون پخش‌شدگی هر ۵۰۰ در یک tick می‌رسند. با پخش ۱۰ tick حالت کاملاً یکنواخت ۵۰ در هر tick است؛ قرعه‌های تصادفی اوج ۶۴ دادند. با ۵۰ tick حالت یکنواخت ۱۰ است و اوج ۱۶ شد. این همان thundering herd (گله‌ی هجوم‌آور) است: بسیاری از clientها در یک لحظه یک کار را می‌کنند. {{< term "jitter" "jitter" >}} تصادفی آن‌ها را پخش می‌کند. ظرفیت registry در این مدل نیست، پس فقط اوج را نشان می‌دهم، نه اینکه registry از پا می‌افتد یا نه.

خود registry هم یک سیستم توزیع‌شده است. تا جایی که مستنداتشان را فهمیده‌ام، Consul و etcd و ZooKeeper به سمت consistency می‌روند و Eureka به سمت availability؛ [CAP و PACELC](/fa/posts/ds-cap-pacelc/) را ببینید. هیچ‌کدام را اجرا نکردم.

## کجا فهرست سرویس‌ها گمراه می‌کند

- **فهرست را راهنما بدانید، نه حقیقت.** می‌تواند یک TTL کامل کهنه باشد. همیشه timeout داشته باشید و retry روی instance دیگر.
- **در graceful shutdown ثبت را پاک کنید** ([graceful shutdown](/fa/posts/go-graceful-shutdown-workers/)). TTL فقط crash را پوشش می‌دهد و نباید چیزی باشد که در deploy عادی instanceها را حذف می‌کند.
- **به هر چیز poll‌کننده یا ثبت‌شونده‌ی مجدد hysteresis و jitter بدهید.** بدون آن‌ها flapping و herd دقیقاً وقتی ظاهر می‌شوند که سیستم از قبل در تنگنا است.
- **منطق registry را با ساعت تزریق‌شده تست کنید.** تست‌های دمو با `go test -race` اجرا می‌شوند و هیچ‌وقت sleep نمی‌کنند.

## تمرین

به هر instance یک `weight` بدهید و کاری کنید که power of two choices «صف تقسیم بر وزن» را مقایسه کند.

## قدم بعدی

[rate limit توزیع‌شده](/fa/posts/ds-distributed-rate-limiting/): rate limitی که روی یک ماشین کار می‌کند وقتی سرویس چند replica دارد از کار می‌افتد.
