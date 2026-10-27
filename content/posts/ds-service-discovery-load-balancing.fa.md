+++
date = '2027-06-01T10:00:00+03:30'
draft = false
title = 'service discovery و load balancing'
description = 'service discovery و load balancing با Go: registry با TTL، پنجره‌ی ورودی کهنه، round robin در برابر power of two choices، health check و herd.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "service-discovery", "load-balancing", "nats", "go"]
cover = { image = "/images/covers/ds-service-discovery-load-balancing.fa.png", alt = "service discovery و load balancing", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-messaging-event-driven/) با سرویس‌هایی تمام شد که از طریق یک bus حرف می‌زنند. در فراخوانی مستقیم اول باید جواب داد «سرویس مقابل الان کجاست؟». این همان {{< term "service-discovery" "service discovery" >}} است. مبانی لایه‌ی ۴ و ۷ در {{< term "load-balancer" "load balancer" >}} در [مقاله‌ی قبلی](/fa/posts/net-load-balancer-l4-l7/) آمده؛ اینجا: چه کسی نشانی‌ها را می‌داند و انتخاب می‌کند.

> برچسب صادقانه: یک ماشین، loopback. در registry، instanceها سرورهای HTTP واقعی روی پورت تصادفی‌اند، ولی ساعت تزریق‌شده است و heartbeat را حلقه‌ی من می‌فرستد. بخش balancing و herd شبیه‌سازی seed‌دار صف‌ها هستند، نه شبکه. فقط شمارش.

## ثابت، DNS یا registry

فهرست ثابت با اولین deploy می‌شکند. {{< term "dns" "DNS" >}} همه‌جا کار می‌کند، ولی جواب‌ها تا TTL خودشان cache می‌شوند و آن cache مال شما نیست: resolver خود Go cache نمی‌کند، ولی OS یا runtime ممکن است (JVM از قدیم cache سنگین داشته؛ نسخه‌تان را بررسی کنید). رکورد SRV پورت را هم دارد. {{< term "service-registry" "registry" >}} کنترل را به شما می‌دهد: instanceها با یک {{< term "ttl" "TTL" >}} ثبت می‌شوند و با {{< term "heartbeat" "heartbeat" >}} مدام آن را تمدید می‌کنند.

## یک registry کوچک و پنجره‌ی کهنگی

`/register` و `/renew` و `/deregister` و `/list`، با انقضا که روی یک ساعت تزریق‌شده چک می‌شود تا تست‌ها قطعی باشند. سه instance هر ۲ tick تمدید می‌کنند؛ instance با نام b در tick شماره‌ی ۱۱ بدون deregister crash می‌کند. client در هر tick سه درخواست روی فهرست می‌فرستد:

```
ttl= 3 retry=false stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 3
ttl= 3 retry=true  stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 0
ttl= 6 retry=false stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 6
ttl= 6 retry=true  stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 0
ttl=10 retry=false stale-ticks=10 wasted-attempts=10 user-visible-failures=10
ttl=10 retry=true  stale-ticks=10 wasted-attempts=10 user-visible-failures= 0
```

instance خراب دقیقاً به‌اندازه‌ی TTL در فهرست می‌ماند و بخشی از درخواست‌ها (اینجا یکی در هر tick) به آن می‌خورد. retry روی instance دیگر آن را از کاربر پنهان می‌کند، ولی تلاش هدر می‌رود. TTL کوتاه پنجره را کوچک می‌کند ولی heartbeat زیاد می‌خواهد؛ TTL نزدیک به interval با گم‌شدن یک تمدید instance سالم را منقضی می‌کند. طبق تجربه‌ی من، TTL حداقل ۳ برابر interval شروع معقولی است. آن retryها را محدود کنید ([timeout و backoff](/fa/posts/ds-timeouts-retries-backoff/)) وگرنه ورودی کهنه به retry storm تبدیل می‌شود.

## انتخاب instance

load balancing سمت client عکس registry را می‌گیرد و انتخاب می‌کند. ۸ سرور با سرعت ۴ و ۴ و ۴ و ۴ و ۲ و ۲ و ۱ و ۱ درخواست در tick و ورود انفجاری (۲۰٪ tickها ۴۰ درخواست، بقیه ۸) را ۲۰۰۰ tick شبیه‌سازی کردم، با seed ثابت:

```
random           max-queue=1742 avg-queue= 202.40
round-robin      max-queue=1581 avg-queue= 197.50
least-in-flight  max-queue=  14 avg-queue=   1.18
power-of-two     max-queue=  19 avg-queue=   1.81
```

random و round robin سهم برابر به سرورهای کند می‌دهند که از توان آن‌ها بیشتر است، پس صف بی‌نهایت رشد می‌کند. {{< term "power-of-two-choices" "Power of two choices" >}} دو instance نمونه می‌گیرد و صف کوتاه‌تر را برمی‌دارد: تقریباً به خوبی پرسیدن از همه، با دو عدد به‌جای N. بار کاری ساختگی است: شکل را نشان می‌دهد، نه عددهای شما را.

## balancer کجا زندگی می‌کند

| | سمت client | proxy / سمت سرور | sidecar در {{< term "service-mesh" "service mesh" >}} |
|---|---|---|---|
| چه کسی انتخاب می‌کند | کتابخانه‌ی برنامه | یک proxy مرکزی | proxy کنار هر برنامه |
| hop اضافه | ندارد | یکی | hop محلی |
| مستقل از زبان | نه | بله | بله |
| هزینه | کتابخانه برای هر زبان | proxy گلوگاه/SPOF | یک process بیشتر برای هر instance |

Envoy و Istio و Linkerd نام‌های رایج‌اند؛ اینجا اجرا نشدند.

## NATS: discovery بدون registry

با {{< term "queue-group" "queue group" >}} روی nats-server توکار، سه responder و ۳۰ درخواست:

```
30 requests, 3 responders: r1=17 r2=2 r3=11
r2 killed, 30 more:        r1=12 r2=0 r3=18
all responders gone:       err = nats: no responders available for request
```

هیچ‌کس چیزی ثبت نکرد؛ subscription همان ثبت است و سرور با قطع اتصال آن را برمی‌دارد. تقسیم بین اجراها فرق می‌کند. بعد از هر kill ۲۰۰ms صبر کردم؛ بدون آن، در یک اجرای اولیه یک درخواست timeout شد: همان پنجره‌ی کهنگی در مقیاس کوچک.

## health check و flapping

liveness می‌پرسد «من را restart کنید؟»، readiness می‌پرسد «به من ترافیک بدهید؟»، startup بوت کند را محافظت می‌کند؛ این‌ها اصطلاحات Kubernetes‌اند. {{< term "health-check" "health checkهای" >}} فعال طبق برنامه probe می‌کنند؛ غیرفعال ترافیک واقعی را می‌بینند ([circuit breaker](/fa/posts/ds-circuit-breaker-bulkhead/)). instance ناپایدار (۵۵٪ probeها موفق، ۱۲۰ probe) بدون {{< term "hysteresis" "hysteresis" >}} مدام می‌چرخد:

```
need 1 ok / 1 fail: route changes=58
need 3 ok / 3 fail: route changes=11
need 5 ok / 5 fail: route changes=3
really down from probe 20, need 3 fails: ejected at probe 22
really down from probe 20, need 5 fails: ejected at probe 24
```

## herd بعد از restart شدن registry

۵۰۰ instance بعد از restart شدن registry همزمان دوباره ثبت می‌شوند، شبیه‌سازی seed‌دار:

```
spread= 0 ticks: peak registrations in one tick=500
spread=10 ticks: peak registrations in one tick=64
spread=50 ticks: peak registrations in one tick=16
```

این همان {{< term "thundering-herd" "thundering herd" >}} است؛ {{< term "jitter" "jitter" >}} تصادفی آن را پخش می‌کند. خود registry هم یک سیستم توزیع‌شده است: Consul و etcd و ZooKeeper طبق مستندات‌شان به سمت consistency می‌روند و Eureka به سمت availability؛ [CAP و PACELC](/fa/posts/ds-cap-pacelc/).

## چند نکته‌ی مهم

- فهرست را راهنما بدانید: timeout و retry روی instance دیگر لازم است.
- در graceful shutdown ثبت را پاک کنید ([graceful shutdown](/fa/posts/go-graceful-shutdown-workers/))؛ TTL crash را پوشش می‌دهد.
- به هر چیز poll‌کننده hysteresis و jitter بدهید.

## تمرین

به هر instance یک `weight` بدهید و کاری کنید که power of two choices «صف تقسیم بر وزن» را مقایسه کند.

## قدم بعدی

مقاله‌ی بعدی «rate limit توزیع‌شده» است.
