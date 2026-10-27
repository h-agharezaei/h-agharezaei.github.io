+++
date = '2027-04-16T10:00:00+03:30'
draft = false
title = 'عیب‌یابی شبکه با curl، dig و traceroute'
description = 'عیب‌یابی شبکه با curl، dig و traceroute: exit codeهای واقعی، redirect، هدر Host، جواب DNS، NXDOMAIN و چک‌لیست لایه‌به‌لایه.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "troubleshooting", "curl", "dig", "traceroute", "dns"]
cover = { image = "/images/covers/net-troubleshooting-curl-traceroute.fa.png", alt = "عیب‌یابی شبکه با curl، dig و traceroute", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/net-load-balancer-l4-l7/) درخواست از یک جعبه‌ی دیگر هم رد شد. وقتی چیزی خراب می‌شود، مهارت اصلی پیدا کردن لایه‌ی خراب است. این پست یک جعبه‌ابزار کوچک است: curl برای {{< term "http" "HTTP" >}}، dig برای {{< term "dns" "DNS" >}}، nc و lsof برای port و traceroute برای مسیر. از ایده‌های [مدل TCP/IP](/fa/posts/net-tcp-ip-model/)، [DNS در عمل](/fa/posts/net-dns-in-practice/) و [HTTP/1.1 با دست](/fa/posts/net-http1-by-hand/) استفاده می‌کند.

> حریم خصوصی: سرورها روی `127.0.0.1:18080` بودند (یک سرور تست کوچک Go، macOS، curl نسخه‌ی 8.7.1). برای DNS همیشه یک resolver عمومی را صریح نام بردم و خط‌هایی را که اسم ماشین یا شبکه‌ی من را دارند حذف کردم. هیچ traceroute‌ای روی اینترنت نچسباندم چون hopهای واقعی را فاش می‌کند. ماشین مشغول بود، پس زمان‌سنجی ندارم. `ss` و `ip` ابزار Linux هستند و اجرایشان نکردم.

## curl: سرور چه گفت

`curl -v` هدرهای درخواست و پاسخ را نشان می‌دهد. یک نکته که دیدم: هدر `Host` ارسالی curl برابر `127.0.0.1:18080` بود. `-I` فقط هدر می‌خواهد. `-w` واقعیت‌های انتقال را چاپ می‌کند:

```
$ curl -s -o /dev/null -w 'http=%{http_code}\n' http://127.0.0.1:18080/missing
http=404
```

404 و 500 هم جواب‌اند، برای همین curl در هر دو با exit code صفر تمام می‌شود. وضعیت HTTP و خطای انتقال دو چیز جدا هستند.

## curl: وقتی جوابی نیست

exit code سیگنال واقعی است. همه‌ی این‌ها را اجرا کردم:

```
--max-time 1 روی handlerی که 3 ثانیه می‌خوابد -> exit 28
port بدون listener                             -> exit 7  (connection refused)
http://nonexistent.invalid/                    -> exit 6  (could not resolve)
--connect-timeout 1 به 203.0.113.1:81          -> exit 28
سرور بعد از 10 از 100 بایت اتصال را می‌بندد    -> exit 18 (transfer closed with 90 bytes remaining)
```

exit 28 دو بار آمده: اولی وصل شد و منتظر ماند، دومی هیچ‌وقت وصل نشد. آن آدرس در بازه‌ی مستندات است. refused (کد 7) سریع است و یعنی port بسته است؛ timeout یعنی بسته‌ها گم می‌شوند، مثلاً firewall یا میزبان خاموش. از `-sS` استفاده کنید، وگرنه `-s` پیام خطا را پنهان می‌کند.

## Redirect، Host و فشرده‌سازی

بدون `-L` curl فقط 301 را چاپ می‌کند و می‌ایستد. با آن، `-w` زنجیره را می‌شمارد:

```
$ curl -s -o /dev/null -L -w 'redirects=%{num_redirects} final=%{url_effective} code=%{http_code}\n' .../old
redirects=2 final=http://127.0.0.1:18080/ok code=200
```

یک 301 و بعد یک 302 بود: زنجیره‌ی {{< term "http-redirect" "redirect" >}}. برای تست یک virtual host پیش از وجود DNS، نام را pin کنید: `--resolve shop.example.test:18080:127.0.0.1` باعث شد سرور `Host: shop.example.test:18080` ببیند و `-H 'Host: api.example.test'` دقیقاً همان را. پاسخ gzip تا وقتی `--compressed` نگذاشتم بایت‌هایی شروع‌شده با `1f 8b` بود.

## dig: از یک resolver مشخص بپرسید

همیشه resolver را نام ببرید (`@1.1.1.1`) تا بدانید چه کسی جواب می‌دهد. این‌ها جواب‌های عمومی یک {{< term "recursive-resolver" "recursive resolver" >}} هستند:

```
$ dig @1.1.1.1 example.com NS +short
hera.ns.cloudflare.com.
elliott.ns.cloudflare.com.
$ dig @1.1.1.1 example.com MX +short
0 .
$ dig @1.1.1.1 example.com TXT +short
"v=spf1 -all"
```

MX برابر `0 .` یعنی «null MX»: دامنه ایمیل نمی‌پذیرد. یک رکورد TXT دوم توکن تأیید بود که نیاوردم. ستون {{< term "ttl" "TTL" >}} عدد دوم هر خط جواب است. همان نام را سه بار با چند ثانیه فاصله پرسیدم و 71، 96 و 80 گرفتم؛ یکنواخت کم نشد. حدسم این است که پشت یک آدرس resolver چند cache هست، ولی این را راستی‌آزمایی نکردم.

نامِ ناموجود {{< term "nxdomain" "NXDOMAIN" >}} می‌دهد:

```
$ dig @1.1.1.1 nonexistent.invalid A
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN
;; AUTHORITY SECTION:
.   86400 IN SOA a.root-servers.net. nstld.verisign-grs.com. ...
```

`+trace` از root شروع می‌کند. با فقط نام سرورها، اجرای من اول root (`i.root-servers.net`)، بعد یک سرور `.com` (`l.gtld-servers.net`) و بعد سرور authoritative (`elliott.ns.cloudflare.com`) را رفت که رکورد A نهایی را داد.

## Port و مسیر

```
$ nc -zv 127.0.0.1 18080
Connection to 127.0.0.1 port 18080 [tcp/*] succeeded!
$ nc -zv 127.0.0.1 18999
nc: connectx to 127.0.0.1 port 18999 (tcp) failed: Connection refused
$ lsof -nP -iTCP:18080 -sTCP:LISTEN     (فقط خط من نگه داشته شد)
srv  IPv4  TCP  127.0.0.1:18080 (LISTEN)
```

{{< term "traceroute" "traceroute" >}} بسته‌هایی با {{< term "ttl" "TTL" >}} رو‌به‌افزایش می‌فرستد؛ هر روتری که یکی را دور بیندازد با {{< term "icmp" "ICMP" >}} جواب می‌دهد. روی {{< term "loopback" "loopback" >}} فقط یک hop دارد:

```
$ traceroute -m 3 127.0.0.1
 1  localhost (127.0.0.1)  <مقدارهای ms حذف شد>
```

روی اینترنت هر hop یک خط است؛ دیدن `* * *` اغلب فقط یعنی آن روتر جواب نمی‌دهد، نه اینکه مسیر خراب است.

## چک‌لیست لایه‌ای

| لایه | دستور | شکل خرابی |
|---|---|---|
| نام | `dig @1.1.1.1 name +short` | خالی، NXDOMAIN؛ curl با exit 6 |
| مسیر | `traceroute host` | `* * *` تا آخر |
| Port | `nc -zv host port` | refused (سریع) یا timeout (کند) |
| TLS | `openssl s_client` | خطای handshake |
| HTTP | `curl -sS -I url` | 4xx یا 5xx، redirect اشتباه |
| برنامه | لاگ، `lsof` | نبودن listener |

برای TLS در [TLS و گواهی‌ها با openssl](/fa/posts/net-tls-openssl/) از openssl استفاده کردم. برای هیچ ادعای گواهی از curl استفاده نکردم: این curl روی SecureTransport ساخته شده و در اجراهای قبلی رفتار تأییدش عجیب بود.

## چند نکته‌ی مهم

- 404 مشکل شبکه نیست؛ exit code و status را جدا بررسی کنید.
- نام‌ها را با `--resolve` pin کنید، نه با ویرایش فایل‌های سیستم.
- refused و timeout دو علت متفاوت دارند؛ قاطی‌شان نکنید.
- همیشه بگویید از کدام resolver پرسیدید.

## تمرین

handlerی اضافه کنید که بی‌نهایت redirect کند. curl با `-L` چه می‌کند و کدام exit code و پیام می‌آید؟ بعد `--max-redirs` را ببینید.

## قدم بعدی

پست بعدی «case study: چرا این درخواست کند است» است.
