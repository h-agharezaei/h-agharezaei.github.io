+++
date = '2027-04-16T10:00:00+03:30'
draft = false
title = 'عیب‌یابی شبکه با curl، dig و traceroute'
description = 'عیب‌یابی شبکه با curl، dig و traceroute: exit codeهای واقعی، redirect، هدر Host، جواب DNS، NXDOMAIN و چک‌لیست لایه‌به‌لایه.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "troubleshooting", "curl", "dig", "traceroute", "dns"]
cover = { image = "/images/covers/net-troubleshooting-curl-traceroute.fa.png", alt = "عیب‌یابی شبکه با curl، dig و traceroute", hiddenInSingle = true }
+++

«درخواست آویزان می‌ماند.» این جمله می‌تواند پنج معنی متفاوت داشته باشد و هرکدام راه‌حل جدایی می‌خواهد. شاید نام هرگز به آدرس تبدیل نشده. شاید آدرس پیدا شده ولی هیچ‌کس جواب نداده. شاید اتصال باز شده و سرور ساکت مانده. یا سرور با یک خطا جواب داده که یعنی شبکه‌ی سالمی کارش را درست انجام داده. زل‌زدن به لاگ‌های برنامه به شما نمی‌گوید کدام‌یک است.

ایده‌ی این پست ساده است: درخواست از یک نردبان بالا می‌رود و می‌تواند از هر پله بیفتد. اول نام جست‌وجو می‌شود ({{< term "dns" "DNS" >}})، بعد یک اتصال {{< term "tcp" "TCP" >}} باز می‌شود، بعد (برای https) دست‌دادن {{< term "tls" "TLS" >}} انجام می‌شود، بعد به درخواست {{< term "http" "HTTP" >}} جواب داده می‌شود و در آخر برنامه کارش را می‌کند. عیب‌یابی یعنی پیدا کردن پایین‌ترین پله‌ای که خراب است. هر پله ابزاری دارد: `dig` برای نام‌ها، `nc` برای port، `openssl` برای TLS، `curl` برای HTTP و `traceroute` برای مسیر. و `curl` خاص است، چون **exit code** آن همین حالا می‌گوید از کدام پله افتاده‌اید.

هر جعبه‌ای که به مسیر اضافه شود، مثل balancer [پست قبل](/fa/posts/net-load-balancer-l4-l7/)، یک مظنون دیگر است. اینجا نردبان را با دستورهای واقعی بالا می‌روم. روی [مدل TCP/IP و مسیر یک بسته](/fa/posts/net-tcp-ip-model/)، [DNS در عمل](/fa/posts/net-dns-in-practice/) و [HTTP/1.1 با دست](/fa/posts/net-http1-by-hand/) بنا شده است.

> حریم خصوصی و محیط: macOS (Darwin arm64)، curl نسخه‌ی 8.7.1 (خط اول `curl --version` این است: `curl 8.7.1 (x86_64-apple-darwin26.0) libcurl/8.7.1 (SecureTransport) LibreSSL/3.3.6 zlib/1.2.12 nghttp2/1.69.0`) و DiG 9.10.6. سرورها روی `127.0.0.1` با یک port آزاد تصادفی اجرا شدند که پایین‌تر `PORT` می‌نویسم (در دستورها `$B` یعنی `http://127.0.0.1:$PORT`). سرور آزمایش یک برنامه‌ی کوچک Go است با یک handler برای هر وضعیت (`/ok`، `/missing`، `/boom`، `/slow`، `/old`، `/host`، `/gzip`، `/early`). برای DNS از resolver عمومی `1.1.1.1` پرسیدم و فقط درباره‌ی `example.com` و یک نام ناموجود. هیچ `traceroute`ای روی اینترنت نچسباندم، چون routerهای واقعی شبکه‌ی من را فهرست می‌کند؛ خروجی را توضیح می‌دهم و از یک مثال ساختگی استفاده می‌کنم. زمان‌سنجی نشان نمی‌دهم (ماشین مشغول بود). `ss` و `ip` ابزار Linux هستند و اجرایشان نکردم.

## پله‌های بالا: سرور چه گفت؟

از بالا شروع می‌کنم، چون بیشتر مشکل‌ها در نهایت در HTTP پیدا می‌شوند. `curl -v` کل گفتگو را چاپ می‌کند. خط‌هایی که با `>` شروع می‌شوند چیزی است که curl فرستاده، خط‌های `<` پاسخ سرورند و خط‌های `*` توضیح‌های خود curl:

```
$ curl -sv $B/ok
*   Trying 127.0.0.1:PORT...
* Connected to 127.0.0.1 (127.0.0.1) port PORT
> GET /ok HTTP/1.1
> Host: 127.0.0.1:PORT
> User-Agent: curl/8.7.1
> Accept: */*
>
* Request completely sent off
< HTTP/1.1 200 OK
< Date: Wed, 04 Nov 2026 16:49:55 GMT
< Content-Length: 3
< Content-Type: text/plain; charset=utf-8
<
{ [3 bytes data]
* Connection #0 to host 127.0.0.1 left intact
ok
```

آن را مثل نردبان بخوانید. «Trying» و «Connected» پله‌ی TCP هستند: curl آدرس را پیدا کرد و اتصال باز شد. خط‌های `>` درخواست‌اند، با هدر `Host` که curl اضافه کرد. خط‌های `<` پاسخ‌اند: وضعیت 200 و سه بایت بدنه، یعنی `ok`. اگر فقط هدرها را می‌خواهید `-I` هست که درخواست `HEAD` می‌فرستد. اگر واقعیت‌های انتقال را می‌خواهید `-w` هست که بعد از انتقال یک رشته‌ی قالب را چاپ می‌کند. وضعیت یک صفحه‌ی ناموجود و یک صفحه‌ی خراب‌شده را بپرسیم:

```
$ curl -s -o /dev/null -w 'http=%{http_code}\n' $B/missing
http=404
$ curl -s -o /dev/null -w 'http=%{http_code}\n' $B/boom
http=500
```

(`-o /dev/null` بدنه را دور می‌ریزد و `-s` نوار پیشرفت را پنهان می‌کند.) هر دو با exit code صفر تمام شدند. این اولین چیزی است که باید یاد گرفت: 404 یا 500 یک *جواب* است، پس از دید curl انتقال درست کار کرده. وضعیت HTTP و خطای انتقال دو چیز جدا هستند. اگر صفحه 500 می‌گوید سرور را ببینید، نه شبکه را.

## پله‌های پایین: وقتی جوابی نیست

وقتی curl اصلاً جوابی نمی‌گیرد، سیگنال exit code است. هرکدام از این حالت‌ها را اجرا کردم:

```
--max-time 1 on a handler that sleeps 3 s   -> exit 28
port with no listener                        -> exit 7  (connection refused)
http://nonexistent.invalid/                  -> exit 6  (could not resolve)
--connect-timeout 1 to 203.0.113.1:81        -> exit 28
server closes after 10 of 100 bytes          -> exit 18 (transfer closed with 90 bytes remaining)
```

این هم پیام‌های واقعی سه‌تای آن‌ها (از `-sS` استفاده کنید: `-s` تنها پیام خطا را پنهان می‌کند و `-S` آن را برمی‌گرداند):

```
curl: (28) Operation timed out after 1011 milliseconds with 0 bytes received
curl: (7) Failed to connect to 127.0.0.1 port PORT2 after 0 ms: Couldn't connect to server
curl: (6) Could not resolve host: nonexistent.invalid
```

هرکدام چه می‌گویند:

- **exit 6** پله‌ی نام است. نام به آدرس تبدیل نشد، پس هیچ بسته‌ای به سمت سرور فرستاده نشد. `.invalid` نامی است که قرار است هرگز وجود نداشته باشد و برای آزمایش بی‌خطر است.
- **exit 7** پله‌ی اتصال است و سریع شکست خورد. ماشین جواب داد و گفت هیچ برنامه‌ای روی آن port گوش نمی‌دهد. این همان «connection refused» است: یک بسته‌ی reset فوراً برگشت.
- **exit 28** یک timeout است و دو بار با دو معنی متفاوت آمده. در خط اول curl وصل شد، درخواست را فرستاد و منتظر handlerی ماند که می‌خوابد. در خط چهارم اصلاً وصل نشد: `203.0.113.1` آدرسی از بازه‌ی مستندات است، پس SYN به جایی نمی‌رسد و هرگز جوابی نمی‌آید. timeout بدون هیچ جوابی یعنی بسته‌ها گم می‌شوند، مثلاً در یک firewall یا در ماشینی که خاموش است. refused سریع است و یعنی «بسته»؛ timeout کند است و یعنی «سکوت». این دو به مشکل‌های متفاوتی اشاره می‌کنند.
- **exit 18** یعنی سرور در `Content-Length` قول ۱۰۰ بایت داد و بعد از ۱۰ بایت اتصال را بست. انتقال وسط راه بریده شد؛ شکستی در پله‌ی HTTP که شبیه مشکل شبکه است.

## redirect، Host و فشرده‌سازی

سه جزئیات HTTP هست که سردرگمی‌ای شبیه مشکل شبکه می‌سازد. اول redirect. بدون `-L` curl redirect را نشان می‌دهد و می‌ایستد. با `-L` دنبالش می‌رود و `-w` می‌تواند قدم‌ها را بشمارد:

```
$ curl -s -o /dev/null -w 'code=%{http_code} redirect_url=%{redirect_url}\n' $B/old
code=301 redirect_url=http://127.0.0.1:PORT/mid
$ curl -s -o /dev/null -L -w 'redirects=%{num_redirects} final=%{url_effective} code=%{http_code}\n' $B/old
redirects=2 final=http://127.0.0.1:PORT/ok code=200
```

دستور اول سر 301 می‌ایستد و می‌گوید به کجا اشاره می‌کند. دستور دوم دو قدم را دنبال می‌کند و به `/ok` می‌رسد. با `-v` دو درخواست اضافه را می‌بینید: `/old` با 301 و `Location: /mid` جواب می‌دهد، `/mid` با 302 و `Location: /ok`، و `/ok` با 200. این یک زنجیره‌ی {{< term "http-redirect" "redirect" >}} است.

دوم، هدر `Host`. سروری که چند سایت دارد، یا یک proxy، با هدر `Host` تصمیم می‌گیرد با چه کسی حرف می‌زنید، نه با آدرس IP. برای آزمایش سایتی پیش از ساخته‌شدن رکورد DNS آن، می‌توانید با `--resolve` یک نام را به یک آدرس بچسبانید یا فقط هدر را با `-H` بگذارید. handler به‌نام `/host` هدری را که گرفته چاپ می‌کند:

```
$ curl -s $B/host
Host header seen: 127.0.0.1:PORT
$ curl -s --resolve shop.example.test:PORT:127.0.0.1 http://shop.example.test:PORT/host
Host header seen: shop.example.test:PORT
$ curl -s -H 'Host: api.example.test' $B/host
Host header seen: api.example.test
```

در دستور دوم curl به `127.0.0.1` وصل شد ولی طوری رفتار کرد که انگار `shop.example.test` به آن resolve شده. این از ویرایش فایل hosts سیستم تمیزتر است.

سوم، فشرده‌سازی. سرور می‌تواند وقتی کلاینت می‌گوید قبول می‌کند بدنه‌ی gzip بفرستد. اگر بایت‌های عجیب دیدید این را بررسی کنید. handler به‌نام `/gzip` همیشه فشرده می‌فرستد:

```
$ curl -s $B/gzip | xxd | head -2
00000000: 1f8b 0800 0000 0000 00ff 0011 00ee ff63  ...............c
00000010: 6f6d 7072 6573 7365 6420 6865 6c6c 6f0a  ompressed hello.
$ curl -s --compressed $B/gzip
compressed hello
```

بایت‌های `1f 8b` در ابتدا امضای جریان gzip هستند. با `--compressed` curl فشرده‌سازی را درخواست می‌کند و خودش بازش می‌کند.

## dig: از یک resolver مشخص بپرسید

برای پله‌ی نام، `dig` نشان می‌دهد DNS واقعاً چه جواب می‌دهد. همیشه resolverی را که می‌پرسید نام ببرید (بخش بعد از `@`) تا بدانید چه کسی جواب داده. این پرسش‌ها به resolver عمومی `1.1.1.1` می‌روند، یک {{< term "recursive-resolver" "recursive resolver" >}} که جست‌وجو را برای شما انجام می‌دهد، و فقط درباره‌ی `example.com` می‌پرسند:

```
$ dig @1.1.1.1 example.com NS +short
hera.ns.cloudflare.com.
elliott.ns.cloudflare.com.
$ dig @1.1.1.1 example.com MX +short
0 .
$ dig @1.1.1.1 example.com TXT +short
"v=spf1 -all"
"_k2n1y4vw3qtb4skdx9e7dxt97qrmmq9"
```

`NS` نشان می‌دهد کدام سرورها مسئول دامنه‌اند. جواب MX یعنی `0 .` یک «null MX» است: دامنه می‌گوید هیچ ایمیلی نمی‌پذیرد. جواب TXT یک سیاست SPF دارد (`-all` یعنی «هیچ سروری حق ندارد برای این دامنه ایمیل بفرستد») و یک توکن تأیید. جواب‌های DNS عمومی با گذشت زمان عوض می‌شوند، پس ممکن است جواب شما فرق کند.

یک نکته‌ی عملی. بار اول که این پرسش‌ها را با `+time=3 +tries=1` اجرا کردم، پرسش‌های NS و MX و A پیام `connection timed out; no servers could be reached` چاپ کردند و فقط TXT کار کرد. اجرای دوباره با `+time=4 +tries=3` جواب کامل داد. timeout در `dig` همان «سکوت» timeout در curl است: به این معنا نیست که نام وجود ندارد.

{{< term "ttl" "TTL" >}} ستون دوم خط جواب است، تعداد ثانیه‌هایی که cache اجازه دارد جواب را نگه دارد. یک رکورد TXT را سه بار با فاصله‌ی سه ثانیه پرسیدم و `300` و `300` و `62` گرفتم. به‌طور پیوسته کم نشد. حدسم این است که پشت یک آدرس resolver چند cache هست، ولی این را بررسی نکردم.

نامی که وجود ندارد {{< term "nxdomain" "NXDOMAIN" >}} می‌دهد، که یک جواب واقعی DNS است، نه شکست:

```
$ dig @1.1.1.1 nonexistent.invalid A
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 2216
;; flags: qr rd ra ad; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1
...
;; AUTHORITY SECTION:
.			86400	IN	SOA	a.root-servers.net. nstld.verisign-grs.com. 2026110400 1800 900 604800 86400
```

فقط خط وضعیت، خط flagها و بخش authority را نگه داشتم؛ خط‌هایی را که آدرس resolver و زمان پرسش را چاپ می‌کنند حذف کردم. بخش مهم `status: NXDOMAIN` است. `id` و شماره‌ی سریال SOA با گذشت زمان عوض می‌شوند.

`dig +trace` نشان می‌دهد جست‌وجو بدون resolver کمک‌کننده چطور پیش می‌رفت، قدم‌به‌قدم از ریشه. برای `example.com A` جواب‌ها اول از یک root server آمدند (این‌بار `j.root-servers.net`)، بعد از یک سرور `.com` (`k.gtld-servers.net`) و بعد از یکی از سرورهای خود دامنه (`hera.ns.cloudflare.com`) که رکورد نهایی را داد. اینکه کدام root و کدام سرور `.com` جواب بدهد ممکن است در اجراهای مختلف فرق کند.

## port و مسیر

برای پله‌ی اتصال بدون HTTP، `nc -z` فقط سعی می‌کند اتصال باز کند و `-v` نتیجه را گزارش می‌دهد. `lsof` نشان می‌دهد چه کسی روی یک port همین ماشین گوش می‌دهد:

```
$ nc -zv 127.0.0.1 PORT
Connection to 127.0.0.1 port PORT [tcp/*] succeeded!
$ nc -zv 127.0.0.1 PORT2
nc: connectx to 127.0.0.1 port PORT2 (tcp) failed: Connection refused
$ lsof -nP -iTCP:PORT -sTCP:LISTEN     (only my line kept, columns reduced)
srv  IPv4  TCP  127.0.0.1:PORT (LISTEN)
```

`PORT` سرور من را دارد و `PORT2` portی است که کسی روی آن گوش نمی‌دهد. `lsof` سرور من یعنی `srv` را به‌عنوان شنونده نشان می‌دهد، پس «آیا کسی گوش می‌دهد و کدام برنامه؟» به‌صورت محلی جواب داده می‌شود.

آخرین ابزار {{< term "traceroute" "traceroute" >}} است. بسته‌هایی با TTL کوچک می‌فرستد (TTL یعنی «زمان زنده‌ماندن»، شمارنده‌ای که هر router یکی از آن کم می‌کند)؛ routerی که آن را به صفر برساند بسته را دور می‌اندازد و با یک پیام {{< term "icmp" "ICMP" >}} جواب می‌دهد، پس آدرسش را یاد می‌گیرید. بعد TTL را یکی زیاد می‌کند و دوباره می‌فرستد، و مسیر router به router آشکار می‌شود. برای آدرس {{< term "loopback" "loopback" >}} یک hop دارد:

```
$ traceroute -m 3 127.0.0.1
traceroute to 127.0.0.1 (127.0.0.1), 3 hops max, 40 byte packets
 1  localhost (127.0.0.1)  <three ms values omitted>
```

روی اینترنت یک خط برای هر router چاپ می‌کند و آن فهرست مسیر واقعی شبکه‌ی شماست، که دقیقاً چیزی است که منتشر نمی‌کنم. پس این یک مثال **ساختگی** با آدرس‌هایی از بازه‌های مستندات است، فقط برای نشان‌دادن طرز خواندن:

```
 1  192.0.2.1
 2  198.51.100.7
 3  * * *
 4  * * *
 5  203.0.113.9
```

خط `* * *` یعنی برای آن hop جوابی نیامد. این لزوماً به معنی قطع‌بودن مسیر نیست: خیلی از routerها به این پروب‌ها جواب نمی‌دهند و مسیر باز هم کار می‌کند، همان‌طور که جواب hop پنجم نشان می‌دهد. مسیری که از یک hop تا آخر همه‌ی خط‌هایش `* * *` است مشکوک‌تر است، ولی آن هم می‌تواند فقط firewallی باشد که پروب‌ها را دور می‌ریزد.

## نردبان به‌شکل چک‌لیست

| پله | دستور | شکست چه شکلی است |
|---|---|---|
| نام | `dig @1.1.1.1 name +short` | جواب خالی، NXDOMAIN؛ curl با exit 6 |
| مسیر | `traceroute host` | `* * *` تا آخر |
| port | `nc -zv host port` | refused (سریع) یا timeout (کند)؛ curl با exit 7 یا 28 |
| TLS | `openssl s_client` | خطای handshake |
| HTTP | `curl -sS -I url` | 4xx یا 5xx، redirect اشتباه |
| برنامه | لاگ‌ها، `lsof` | نبودن listener |

از بالای جدول به پایین بروید و سر اولین شکست بایستید. برای پله‌ی TLS در [TLS و گواهی با openssl](/fa/posts/net-tls-openssl/) از openssl استفاده کردم. برای هیچ ادعای مربوط به گواهی از curl استفاده نکردم: این curl روی SecureTransport ساخته شده و بررسی گواهی‌اش در اجراهای قبلی رفتار عجیبی داشت.

در این پست عدد زمانی نیاورده‌ام. ولی `curl -w` می‌تواند مدت هر پله را هم چاپ کند (`time_namelookup`، `time_connect`، `time_appconnect`، `time_starttransfer`، `time_total`). این همان ابزاری است که پست بعد برای پیدا کردن پله‌ی کند به کار می‌برد.

## برداشت‌های غلطی که باید پرهیز کرد

- **حساب‌کردن 404 به‌عنوان مشکل شبکه.** exit code و وضعیت HTTP را جدا بخوانید. 404 یا 500 یک جواب است؛ شبکه کار کرده.
- **ویرایش فایل‌های سیستم برای آزمایش یک نام.** `--resolve` یک نام را فقط برای یک دستور می‌چسباند و چیز دیگری را در ماشین شما عوض نمی‌کند.
- **قاطی‌کردن refused و timeout.** refused یک «نه»ی سریع از ماشینی است که در دسترس است، timeout سکوت است. آن‌ها را جور دیگری دنبال کنید.
- **نگفتن اینکه از کدام resolver پرسیده‌اید.** یک نام می‌تواند از resolverهای مختلف جواب‌های مختلف بگیرد و cacheها آن را بدتر می‌کنند. در هر `dig`ای که به اشتراک می‌گذارید `@resolver` را بنویسید.
- **اعتماد به `* * *` در traceroute.** hopهای ساکت عادی‌اند. مسیر را با اینکه مقصد جواب می‌دهد یا نه بسنجید.

## تمرین

handlerی اضافه کنید که برای همیشه به خودش redirect می‌کند. `curl -L` چه می‌کند و کدام exit code و پیام ظاهر می‌شود؟ بعد `--max-redirs` را در راهنمای curl بخوانید. این یکی را اجرا نکردم.

## قدم بعدی

پست بعد «case study: چرا این درخواست کند است» است. نردبان می‌گوید کدام پله خراب شده؛ وقتی چیزی خراب نیست ولی درخواست کند است، باید اندازه بگیرید هر پله چقدر طول می‌کشد، و case study همین را انجام می‌دهد.
