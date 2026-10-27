+++
date = '2027-03-01T10:00:00+03:30'
draft = false
title = 'TLS و گواهی با openssl'
description = 'TLS و گواهی با openssl روی loopback: ساخت CA، امضای گواهی با SAN، خواندن خطاهای verify، TLS 1.2 و 1.3، ALPN و mutual TLS.'
categories = ["Networking"]
series = ["Networking"]
tags = ["networking", "tls", "openssl", "certificates", "mtls", "security"]
cover = { image = "/images/covers/net-tls-openssl.fa.png", alt = "TLS و گواهی با openssl", hiddenInSingle = true }
+++

در پست قبلی، [HTTP/1.1 با دست](/fa/posts/net-http1-by-hand/)، درخواست‌های HTTP را روی یک socket ساده تایپ کردیم و هر کسی در مسیر می‌توانست آنها را بخواند. {{< term "tls" "TLS" >}} این مشکل را حل می‌کند: اتصال را رمزنگاری می‌کند و هویت سرور را ثابت می‌کند. بیشتر دردسر TLS به رمزنگاری برنمی‌گردد، به گواهی و پیام‌های خطاست. پس کل زنجیره را خودمان با `openssl` می‌سازیم، عمداً خرابش می‌کنیم و هر خطا را می‌خوانیم. این پست روی [مدل TCP/IP](/fa/posts/net-tcp-ip-model/) و [اتصال‌های TCP](/fa/posts/net-tcp-handshake-states/) سوار است.

> همه‌چیز روی `127.0.0.1` و با فایل‌های موقت در یک پوشه‌ی temp (`<tmp>`) اجرا شد، پس چیز شخصی در خروجی نیست. از `/opt/homebrew/bin/openssl` (نسخه‌ی OpenSSL 3.6.4) استفاده کردم؛ `/usr/bin/openssl` مک LibreSSL 3.3.6 است و گزینه‌هایش فرق دارد. پورت را `PORT` نوشته‌ام. بدون root امکان capture بسته نبود.

## یک CA و یک گواهی سرور

{{< term "certificate-authority" "مرجع صدور گواهی" >}} (CA) فقط یک کلید به‌علاوه‌ی یک گواهی خودامضاست. یکی می‌سازیم، بعد کلید و درخواست سرور را می‌سازیم و امضا می‌کنیم:

```
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 30 -subj "/CN=Demo Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" -out ca.pem
openssl genpkey ... -out server.key ; openssl req -new -key server.key -subj "/CN=localhost" -out server.csr
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 7 -sha256 \
  -extfile ext.cnf -out server.pem
```

بخش مهم در `ext.cnf` است، یعنی {{< term "subject-alt-name" "SubjectAltName" >}}:

```
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
```

چرا فقط Common Name کافی نیست؟ کلاینت نام میزبان را با فهرست SAN تطبیق می‌دهد. گواهی دومی بدون SAN ساختم (`nosan.pem`) و امتحانش کردم. `-verify_hostname localhost` در OpenSSL باز هم `Verification: OK` چاپ کرد، چون به CN برمی‌گردد. اما کلاینت Go (`crypto/tls`) رد کرد:

```
error: tls: failed to verify certificate: x509: certificate relies on legacy Common Name field, use SANs instead
```

پس همیشه SAN بگذارید. بخشی از خروجی `openssl x509 -in server.pem -noout -text` ({{< term "x509-certificate" "X.509" >}}):

```
Issuer: CN=Demo Root CA
Not Before: Oct 27 05:49:49 2026 GMT
Not After : Nov  3 05:49:49 2026 GMT
Subject: CN=localhost
Public Key Algorithm: id-ecPublicKey
X509v3 Extended Key Usage: TLS Web Server Authentication
X509v3 Subject Alternative Name: DNS:localhost, IP Address:127.0.0.1
```

دستور `openssl verify -CAfile ca.pem server.pem` چاپ می‌کند `server.pem: OK`.

## اتصال و verify

سرور را با `openssl s_server -accept PORT -cert server.pem -key server.key -www` بالا آوردم و بعد:

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

گزینه‌ی `-servername` همان {{< term "sni" "SNI" >}} را می‌فرستد، یعنی اسمی که کلاینت می‌خواهد، داخل handshake. خط cipher نتیجه‌ی مذاکره است. با `-tls1_2` می‌شود `ECDHE-ECDSA-AES256-GCM-SHA384`.

`curl --cacert` را هم امتحان کردم، ولی هر دو curl این مک (سیستم و Homebrew) با backend اپل (SecureTransport) `continuing anyway` چاپ کردند و صفحه را گرفتند. به آن اعتماد ندارم، پس فقط `openssl` و Go را نشان می‌دهم.

## خطاها، واقعی

```
# 1. کلاینت CA ما را نمی‌شناسد
Verification error: unable to verify the first certificate     (code 21؛ همراه num=20 unable to get local issuer certificate)
# 2. نام در SAN نیست (-verify_hostname example.org)
verify error:num=62:hostname mismatch
# 3. گواهی منقضی
verify error:num=10:certificate has expired
```

1. بدون `-CAfile` هیچ CA مورد اعتمادی گواهی را امضا نکرده است. راه‌حل: به CA درست اعتماد کنید، نه خاموش کردن verify.
2. گواهی معتبر است اما برای آن نام نیست. این بررسی جلوی استفاده از گواهی معتبرِ یک سایت دیگر را می‌گیرد.
3. گواهی سوم را با `openssl x509 -req ... -not_before 20260101000000Z -not_after 20260102000000Z` ساختم (OpenSSL 3.6 من این گزینه‌ها را قبول می‌کند). `openssl verify` همان خطای 10 را می‌دهد.

## TLS 1.2 و 1.3 و handshake

نمی‌توانم بسته را capture کنم، ولی `s_client -msg` پیام‌های handshake را چاپ می‌کند. برای TLS 1.3 (خلاصه‌شده):

```
>>> Handshake, ClientHello
<<< Handshake, ServerHello
<<< Handshake, EncryptedExtensions
<<< Handshake, Certificate
<<< Handshake, CertificateVerify
<<< Handshake, Finished
>>> Handshake, Finished
<<< Handshake, NewSessionTicket
```

به زبان ساده: ClientHello نسخه‌ها، cipherها، SNI و سهم کلاینت از تبادل کلید را فهرست می‌کند. ServerHello یکی را انتخاب می‌کند و سهم سرور را می‌فرستد، پس هر دو طرف می‌توانند کلید بسازند؛ از اینجا به بعد همه‌چیز رمز است. سرور بعد زنجیره‌ی گواهی و یک CertificateVerify می‌فرستد، امضایی که ثابت می‌کند کلید خصوصی را دارد. دو پیام `Finished` تأیید می‌کنند کسی handshake را دستکاری نکرده است. طبق مستندات TLS 1.3 اینجا یک رفت‌وبرگشت لازم دارد و TLS 1.2 دو تا؛ اندازه نگرفتم.

## ALPN

وقتی سرور با `-alpn h2,http/1.1` بالا آمد، کلاینتی که `-alpn h2,http/1.1` پیشنهاد داد جواب `ALPN protocol: h2` گرفت. کلاینتی که فقط `foo` پیشنهاد داد، `tlsv1 alert no application protocol` (alert شماره‌ی 120) گرفت. این {{< term "alpn" "ALPN" >}} است: پروتکل داخل TLS انتخاب می‌شود، موضوع پست بعد.

## Mutual TLS

از همان CA یک گواهی کلاینت ساختم (`extendedKeyUsage=clientAuth` و CN برابر `demo-client`) و `s_server -CAfile ca.pem -Verify 1` را اجرا کردم. این {{< term "mutual-tls" "mutual TLS" >}} است:

```
# بدون گواهی کلاینت
SSL alert number 116  (tlsv13 alert certificate required)
server: peer did not return a certificate
# با -cert client.pem -key client.key
HTTP/1.0 200 ok
server: depth=0 CN=demo-client   verify return:1
```

در TLS 1.3 رد شدن به شکل alert در اولین خواندن کلاینت می‌رسد.

## یک سایت عمومی

دستور `openssl s_client -connect example.com:443 -servername example.com` زنجیره را نشان می‌دهد (فقط خط‌های subject، خلاصه‌شده):

```
0 s:CN=example.com
1 s:C=US, O=SSL Corporation, CN=Cloudflare TLS Issuing ECC CA 3
2 s:C=US, O=SSL Corporation, CN=SSL.com TLS Transit ECC CA R2
3 s:C=US, O=SSL Corporation, CN=SSL.com TLS ECC Root CA 2022
```

برگ، دو میانی و یک ریشه. سیستم شما به ریشه اعتماد دارد و سرور بقیه را می‌فرستد.

## چند نکته‌ی مهم

- همیشه SAN بگذارید و برای آدرس IP مدخل `IP:` اضافه کنید.
- خطای verify را با `-k` یا خاموش کردن بررسی «درست» نکنید؛ CA را اضافه کنید.
- کلید CA را خصوصی نگه دارید و عمر گواهی‌ها را کوتاه؛ CA دمو من ۳۰ روز اعتبار دارد.
- `s_client` و کتابخانه‌ی TLS زبان شما ممکن است اختلاف داشته باشند (برگشت به CN). با همان کلاینتی تست کنید که تحویل می‌دهید.
- ببینید کدام `openssl` را اجرا می‌کنید: LibreSSL و OpenSSL فرق دارند.

## تمرین

یک گواهی سرور دیگر بسازید که SAN اش فقط `DNS:demo.test` باشد. با `-verify_hostname demo.test` به `127.0.0.1` وصل شوید. بعد `-verify_hostname localhost` را امتحان کنید و هر دو نتیجه را توضیح دهید.

## قدم بعدی

پست بعدی «HTTP/2 و فرق‌هایش» است. در سری‌ای دیگر «TLS and x509 certificates in practice» را عملی‌تر می‌بینیم.
