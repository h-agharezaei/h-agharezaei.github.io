+++
date = '2027-03-01T10:00:00+03:30'
draft = false
title = 'TLS و گواهی با openssl'
description = 'TLS و گواهی با openssl روی loopback: ساخت CA، امضای گواهی با SAN، خواندن خطاهای verify، TLS 1.2 و 1.3، ALPN و mutual TLS.'
contentType = 'tutorial'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tls", "openssl", "certificates", "mtls", "security"]
cover = { image = "/images/covers/net-tls-openssl.fa.png", alt = "TLS و گواهی با openssl", hiddenInSingle = true }
+++

یک صفحه باز می‌کنید یا یک API را صدا می‌زنید و چنین چیزی می‌بینید:

```
verify error:num=20:unable to get local issuer certificate
```

بیشتر آدم‌ها پیامی مثل این را دیده‌اند و نمی‌دانسته‌اند با آن چه کنند، پس واکنش معمول خاموش‌کردن بررسی است. حیف است، چون هر یک از این خطاها معنای دقیقی دارد و یادگرفتنشان فقط یک آزمایش کوتاه می‌خواهد. بیشتر دردسر {{< term "tls" "TLS" >}} از رمزنگاری نیست، از گواهی‌ها و پیام‌های خطاست.

درخواست‌های [HTTP/1.1 با دست](/fa/posts/net-http1-by-hand/) به شکل متن خوانا از یک socket ساده عبور می‌کردند، پس هر کسی در مسیر می‌توانست بخواند یا عوضشان کند. TLS میان TCP و HTTP می‌نشیند (ببینید [مدل TCP/IP](/fa/posts/net-tcp-ip-model/) و [اتصال‌های TCP](/fa/posts/net-tcp-handshake-states/)) و سه چیز به اتصال می‌دهد: **رمزنگاری** (کسی در مسیر نمی‌تواند بخواند)، **یکپارچگی** (کسی نمی‌تواند بی‌خبر تغییرش دهد) و **احراز هویت** (می‌دانید با کدام سرور حرف می‌زنید). سومی جایی است که گواهی‌ها وارد می‌شوند و تقریباً همه‌ی پیام‌های خطا از آن‌جا می‌آیند.

ایده در یک جمله: سرور یک کلید خصوصی دارد و یک **گواهی** (certificate)، سندی که می‌گوید «این کلید عمومی مال نام `localhost` است» و کسی که کلاینت به او اعتماد دارد آن را امضا کرده است. در handshake سرور گواهی‌اش را نشان می‌دهد و ثابت می‌کند کلید خصوصیِ هم‌جفتش را دارد. کلاینت امضا، نام و تاریخ‌ها را بررسی می‌کند. اگر هر سه درست باشند اتصال ادامه می‌یابد؛ اگر یکی خراب باشد خطایی می‌گیرید که می‌گوید کدام.

برای فهمیدن معنای این بررسی‌ها همه‌چیز را خودمان با `openssl` می‌سازیم: مرجع صدور گواهی خودمان، یک گواهی سرور، یک سرور آزمایشی و یک کلاینت آزمایشی. بعد عمداً خرابش می‌کنیم و هر خطا را می‌خوانیم.

> همه‌چیز روی `127.0.0.1` اجرا شد، با کلیدها و گواهی‌های یک‌بارمصرفی که خودم در یک پوشه‌ی موقت (`<tmp>`) ساختم، پس چیز شخصی در خروجی نیست. از `/opt/homebrew/bin/openssl` که با Homebrew نصب شده استفاده کردم (OpenSSL 3.6.4)؛ `/usr/bin/openssl` در macOS نسخه‌ی LibreSSL 3.3.6 است و گزینه‌هایش فرق دارد. Go نسخه‌ی 1.27.3 روی macOS (Darwin، arm64) است. port تصادفی بود و با `PORT` نشان داده شده است. چون گواهی‌ها را دوباره ساختم، تاریخ‌ها و اثرانگشت‌ها با اجرای اولیه فرق دارند. packet capture ممکن نبود (دسترسی root ندارم).

## یک CA و یک گواهی سرور

{{< term "certificate-authority" "مرجع صدور گواهی" >}} (CA) چیز جادویی‌ای نیست: یک کلید است به‌علاوه‌ی گواهی‌ای که خودش را امضا می‌کند. کلاینت‌هایی که به آن گواهی اعتماد کنند به هرچه آن امضا کند هم اعتماد می‌کنند. یکی می‌سازیم:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 30 -subj "/CN=Demo Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" -out ca.pem
```

دستور اول یک کلید خصوصی روی منحنی بیضوی P-256 می‌سازد. دستور دوم گواهی خودامضایی با اعتبار ۳۰ روز می‌سازد که `CN` (نام عمومی) آن `Demo Root CA` است. `CA:TRUE` می‌گوید این گواهی می‌تواند گواهی‌های دیگر را امضا کند و `keyCertSign` می‌گوید کلیدش برای همین کار است.

حالا سرور کلید خودش را می‌گیرد، یک **درخواست امضای گواهی** (CSR، یعنی «لطفاً این کلید را برای این نام تأیید کن») و CA آن را امضا می‌کند:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key
openssl req -new -key server.key -subj "/CN=localhost" -out server.csr
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -days 7 -sha256 -extfile ext.cnf -out server.pem
```

`ext.cnf` بخش مهم را دارد، یعنی {{< term "subject-alt-name" "SubjectAltName" >}}، فهرست نام‌هایی که این گواهی برایشان معتبر است:

```
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
```

`CA:FALSE` یعنی این گواهی نمی‌تواند گواهی دیگری را امضا کند و `serverAuth` می‌گوید می‌تواند هویت یک سرور TLS را نشان دهد. خط آخر می‌گوید برای نام DNS با عنوان `localhost` و برای آدرس IP برابر `127.0.0.1` معتبر است.

چرا فقط از نام عمومی استفاده نکنیم؟ چون کلاینت‌ها نام میزبان را با فهرست SAN تطبیق می‌دهند و بسیاری از کلاینت‌های جدید نام عمومی را نادیده می‌گیرند. برای دیدن فرق، گواهی دومی با همان کلید ولی بدون SAN ساختم (`nosan.pem`، که تنها افزونه‌اش `basicConstraints=CA:FALSE` است) و امتحانش کردم. گزینه‌ی `-verify_hostname localhost` در OpenSSL باز هم `Verification: OK` چاپ کرد، چون به نام عمومی برمی‌گردد. کلاینت Go (`crypto/tls`) آن را رد کرد:

```
error: tls: failed to verify certificate: x509: certificate relies on legacy Common Name field, use SANs instead
```

یعنی یک گواهی برای یک ابزار «سالم» است و برای ابزار دیگر «خراب». همیشه SAN بگذارید.

این هم فیلدهای اصلی گواهی واقعی، از `openssl x509 -in server.pem -noout -text` (گواهی {{< term "x509-certificate" "X.509" >}}؛ این خط‌ها را انتخاب کردم و هر فیلد را به مقدارش چسباندم):

```
Issuer: CN=Demo Root CA
Not Before: Nov  4 16:50:43 2026 GMT
Not After : Nov 11 16:50:43 2026 GMT
Subject: CN=localhost
Public Key Algorithm: id-ecPublicKey
X509v3 Extended Key Usage: TLS Web Server Authentication
X509v3 Subject Alternative Name: DNS:localhost, IP Address:127.0.0.1
```

مثل یک کارت شناسایی بخوانیدش: چه کسی تضمینش می‌کند (`Issuer`)، درباره‌ی کیست (`Subject`)، چه زمانی معتبر است، چه نوع کلیدی دارد و برای چه کاری مجاز است. این تاریخ‌ها مال همین اجرا هستند و هر بار فرق می‌کنند. دستور `openssl verify -CAfile ca.pem server.pem` چاپ می‌کند `server.pem: OK`.

## اتصال و بررسی

حالا یک سرور و یک کلاینت می‌خواهیم. `openssl s_server` یک سرور آزمایشی TLS است و `-www` باعث می‌شود به درخواست وب با یک صفحه‌ی وضعیت جواب بدهد. آن را روی یک port تصادفی اجرا کردم:

```
openssl s_server -accept PORT -cert server.pem -key server.key -www
```

بعد `openssl s_client` به‌عنوان کلاینت وصل می‌شود. `-CAfile ca.pem` می‌گوید به کدام CA اعتماد کند و `-verify_hostname` از آن می‌خواهد نام را هم بررسی کند. خروجی کاملش بلند است، پس فقط خط‌های مربوط به بررسی را نگه داشتم:

```
$ openssl s_client -connect 127.0.0.1:PORT -CAfile ca.pem -servername localhost -verify_hostname localhost </dev/null
depth=1 CN=Demo Root CA
depth=0 CN=localhost
Peer signature type: ecdsa_secp256r1_sha256
Verification: OK
Verified peername: localhost
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
Verify return code: 0 (ok)
```

دو خط `depth` همان {{< term "certificate-chain" "زنجیره‌ی گواهی" >}} است که از بالا بررسی می‌شود: عمق ۱ CA ماست و عمق ۰ گواهی خود سرور. `Verification: OK` و `Verified peername: localhost` یعنی امضا، تاریخ‌ها و نام هر سه درست بودند. خط `New` نتیجه‌ی مذاکره است: TLS 1.3 با رمز `TLS_AES_256_GCM_SHA384`. با `-tls1_2` به‌جایش `TLSv1.2` و `ECDHE-ECDSA-AES256-GCM-SHA384` آمد. یک کلاینت Go (برنامه‌ی کوچکی با `crypto/tls` که `ca.pem` را CA مورد اعتماد خود می‌گیرد) هم به همین سرور وصل شد و چاپ کرد `ok: version=TLS 1.3 cipher=TLS_AES_128_GCM_SHA256`؛ دو طرف می‌توانند رمزهای متفاوتی بردارند، چون هرکدام ترجیح‌های خودش را دارد.

`-servername` مقدار {{< term "sni" "SNI" >}} (نام سرور مورد نظر) را می‌فرستد: نامی که کلاینت می‌خواهد، داخل خود handshake. با آن یک IP و port می‌تواند چند گواهی را سرویس بدهد، برای هر نام یکی.

`curl --cacert ca.pem https://localhost:PORT/` را هم امتحان کردم. روی این Mac، `/usr/bin/curl` (نسخه‌ی 8.7.1) از SecureTransport اپل استفاده می‌کند و مثل یک کلاینت بررسی‌کننده رفتار نکرد: حتی بدون `--cacert` با کد وضعیت ۰ تمام شد و با `--cacert` متغیر `%{ssl_verify_result}` عدد ۲۰ را چاپ کرد. در این دمو به آن اعتماد نمی‌کنم، پس فقط نتیجه‌های `openssl` و Go را نشان می‌دهم.

## شکست‌ها، واقعی

حالا خراب‌کردن. هر کدام از این‌ها یک اجرای واقعی روی سرور آزمایشی ماست و خط‌های مهم هر یک را نشان می‌دهم. اول، کلاینت CA ما را نمی‌شناسد، چون `-CAfile` را نگذاشتم:

```
# 1. client does not know our CA
verify error:num=20:unable to get local issuer certificate
verify error:num=21:unable to verify the first certificate
Verification error: unable to verify the first certificate
Verify return code: 21 (unable to verify the first certificate)
```

گواهی را «Demo Root CA» امضا کرده بود ولی این کلاینت چنین CAیی در فهرست مورد اعتمادش ندارد، پس نمی‌تواند امضا را تا چیزی که به آن اعتماد دارد دنبال کند. این همان خطای ابتدای پست است. راه‌حل این است که به CA درست اعتماد کنید، نه اینکه بررسی را خاموش کنید. (Go همین مشکل را به شکل `x509: certificate signed by unknown authority` چاپ می‌کند؛ آن را هم اجرا کردم، با یک گواهی نادرست به‌جای CA.)

دوم، گواهی معتبر است ولی نامی را می‌خواهیم که در SAN نیست (`-verify_hostname example.org`):

```
# 2. name not in the SAN
verify error:num=62:hostname mismatch
Verify return code: 62 (hostname mismatch)
```

امضا و تاریخ‌ها درست‌اند، اما گواهی برای آن نام نیست. این بررسی شما را از گواهی معتبرِ یک سایت دیگر محافظت می‌کند.

سوم، گواهی‌ای که تاریخش گذشته است. یکی با `openssl x509 -req ... -not_before 20260101000000Z -not_after 20260102000000Z` ساختم (این گزینه‌ها در OpenSSL 3.6 هستند) و سرور را با آن اجرا کردم:

```
# 3. expired certificate
verify error:num=10:certificate has expired
Verify return code: 10 (certificate has expired)
```

`openssl verify -CAfile ca.pem expired.pem` همان خطای ۱۰ را می‌دهد. گواهی‌ها عمداً منقضی می‌شوند تا گواهیِ دزدیده‌شده یا فراموش‌شده تا ابد معتبر نماند.

## TLS 1.2 و 1.3 و handshake

پیش از اولین بایت HTTP داخل اتصال چه می‌گذرد؟ اینجا نمی‌توانم بسته‌ها را capture کنم، اما `s_client -msg` هر پیام handshake را چاپ می‌کند. برای TLS 1.3، فقط خط‌های پیام‌های handshake و alert را نگه داشتم (`[length ...]` اندازه‌ی پیام به بایت و در مبنای شانزده است):

```
>>> TLS 1.3, Handshake [length 05ff], ClientHello
<<< TLS 1.3, Handshake [length 04ba], ServerHello
<<< TLS 1.3, Handshake [length 0006], EncryptedExtensions
<<< TLS 1.3, Handshake [length 01cc], Certificate
<<< TLS 1.3, Handshake [length 0050], CertificateVerify
<<< TLS 1.3, Handshake [length 0034], Finished
>>> TLS 1.3, Handshake [length 0034], Finished
>>> TLS 1.3, Alert [length 0002], warning close_notify
```

`>>>` آن چیزی است که کلاینت فرستاد و `<<<` آنچه سرور فرستاد. با کلمه:

- **ClientHello:** کلاینت می‌گوید کدام نسخه‌ها و رمزها را پشتیبانی می‌کند، چه نامی می‌خواهد (SNI) و نیمه‌ی خودش از یک تبادل کلید («key share») را می‌گذارد.
- **ServerHello:** سرور یک گزینه را انتخاب می‌کند و key share خودش را می‌فرستد. حالا هر دو طرف می‌توانند بدون فرستادن کلیدها همان کلیدهای مخفی را حساب کنند و هرچه بعد از این پیام بیاید رمزنگاری‌شده است.
- **Certificate:** گواهی سرور. سرور ما فقط گواهی خودش را می‌فرستد، چون کلاینت CA را از قبل دارد. پیام `Certificate` این‌جا 0x1cc، یعنی ۴۶۰ بایت است.
- **CertificateVerify:** یک {{< term "digital-signature" "امضا" >}} روی handshake تا این لحظه، با کلید خصوصی. این همان اثبات است که سرور واقعاً کلیدی را دارد که گواهی نامش را می‌برد. گواهیِ دزدیده‌شده بدون آن بی‌فایده است.
- **Finished** (در هر دو جهت): هر طرف تأیید می‌کند که کسی handshake را دست‌کاری نکرده است.
- **close_notify:** خداحافظی مؤدبانه‌ی کلاینت، چون فرمان من اتصال را تمام کرد.

در این اجرا پیام `NewSessionTicket` (بلیتی برای وصل‌شدن سریع‌تر دوباره) ندیدم. طبق RFC 8446، handshake در TLS 1.3 یک رفت‌وبرگشت لازم دارد و در TLS 1.2 دو تا؛ این را اندازه‌گیری نکردم.

## ALPN

همین handshake تعیین می‌کند چه پروتکلی درون TLS اجرا شود، با {{< term "alpn" "ALPN" >}}. سرور را با `-alpn h2,http/1.1` اجرا کردم و سه کلاینت را امتحان کردم:

```
client offers h2,http/1.1    -> ALPN protocol: h2
client offers http/1.1 only  -> ALPN protocol: http/1.1
client offers only foo       -> alert number 120: tlsv1 alert no application protocol
```

کلاینت فهرست آنچه را که می‌تواند حرف بزند می‌دهد و سرور انتخاب می‌کند. کلاینتی که هیچ مورد مشترکی ندارد با یک alert رد می‌شود، و کلاینتی که اصلاً ALPN پیشنهاد نمی‌دهد فقط «No ALPN negotiated» می‌گیرد. `h2` همان HTTP/2 است، موضوع پست بعدی.

## Mutual TLS

تا اینجا فقط سرور هویتش را ثابت کرد. در {{< term "mutual-tls" "mutual TLS" >}} کلاینت هم باید گواهی نشان دهد. یک گواهی کلاینت از همان CA ساختم (`extendedKeyUsage=clientAuth`، نام عمومی `demo-client`) و سرور را با `-CAfile ca.pem -Verify 1` اجرا کردم:

```
# no client cert
client: alert number 116 (tlsv13 alert certificate required)
server: peer did not return a certificate
# with -cert client.pem -key client.key
HTTP/1.0 200 ok
server: depth=0 CN=demo-client   verify return:1
```

بدون گواهی، سرور رد می‌کند و به کلاینت می‌گوید چرا. با گواهی، سرور آن را با همان CA بررسی کرد، نام `demo-client` را لاگ کرد و درخواست جواب گرفت. در TLS 1.3 ممکن است سمت کلاینت handshake پیش از رد شدن توسط سرور تمام‌شده به نظر برسد، برای همین رد شدن در اولین خواندن کلاینت به شکل alert می‌رسد.

## یک سایت عمومی

برای دیدن یک زنجیره‌ی واقعی، `openssl s_client -connect example.com:443 -servername example.com` گواهی‌هایی را که سرور می‌فرستد نشان می‌دهد. این‌جا فقط خط‌های subject (`s:`) و issuer (`i:`) را می‌گذارم که عمومی هستند:

```
0 s:CN=example.com
   i:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
1 s:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
   i:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
2 s:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
   i:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
3 s:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
   i:C=GB, ST=Greater Manchester, L=Salford, O=Comodo CA Limited, CN=AAA Certificate Services
```

issuer هر گواهی همان subject گواهی بعدی است: گواهی برگ برای `example.com`، دو CA میانی و ریشه‌ی SSL.com که این‌جا یک ریشه‌ی قدیمی‌تر آن را امضا کرده است. من آن آخری را یک امضای متقابل (cross-signature) می‌خوانم که به کلاینت‌های قدیمی که فقط ریشه‌ی قدیمی را می‌شناسند اجازه می‌دهد زنجیره بسازند. نتیجه‌ی بررسی با این OpenSSL برابر `OK` بود. سیستم شما به یک ریشه اعتماد دارد و بقیه را سرور می‌فرستد، و این زنجیره هر زمان ممکن است عوض شود.

## اشتباه‌های گواهی که باید از آن‌ها دوری کنید

- همیشه SAN بگذارید، و برای آدرس IP مدخل `IP:` اضافه کنید.
- هرگز خطای verify را با `-k` یا ردکردن بررسی «درست» نکنید. به‌جایش CA را به فهرست مورد اعتماد اضافه کنید، همان‌طور که با `-CAfile` کردیم.
- کلید CA را خصوصی نگه دارید و گواهی‌ها را کوتاه‌مدت. CA دموی من ۳۰ روز اعتبار دارد.
- `s_client` و کتابخانه‌ی TLS زبان شما ممکن است هم‌نظر نباشند، همان‌طور که بازگشت به نام عمومی نشان داد. با همان کلاینتی که تحویل می‌دهید آزمایش کنید.
- بررسی کنید کدام `openssl` را اجرا می‌کنید: LibreSSL و OpenSSL در گزینه‌ها و خروجی فرق دارند.

## تمرین

یک گواهی سرور دوم بسازید که SAN آن فقط `DNS:demo.test` باشد. با `-verify_hostname demo.test` روی `127.0.0.1` وصل شوید. بعد `-verify_hostname localhost` را بزنید و هر دو نتیجه را توضیح دهید.

## قدم بعدی

پست بعدی «HTTP/2 و فرق‌هایش» است، پروتکلی که ALPN در بالا با نام `h2` برگزید. یک سری بعدی TLS و گواهی‌های x509 را در عمل بررسی می‌کند.
