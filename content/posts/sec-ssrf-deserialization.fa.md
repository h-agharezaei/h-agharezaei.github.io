+++
date = '2027-05-12T10:00:00+03:30'
draft = false
title = 'SSRF و deserialization ناامن'
description = 'SSRF و deserialization ناامن با اجرای واقعی: blocklistهای شکست‌خورده، redirect، DNS rebinding، fetcher امن در Go و دام‌های pickle و YAML.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "ssrf", "deserialization", "go", "python", "pickle"]
cover = { image = "/images/covers/sec-ssrf-deserialization.fa.png", alt = "SSRF و deserialization ناامن", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها](/fa/posts/sec-supply-chain-vulns/)، درباره‌ی کدی بود که شما ننوشته‌اید. این مقاله درباره‌ی ورودی‌ای است که شما ننوشته‌اید: یک URL یا مشتی بایت. در [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/) یک {{< term "ssrf" "SSRF" >}} تک‌خطی و یک راه‌حل تک‌میزبانی نشان دادم و اعتراف کردم redirect و DNS را آزمایش نکرده‌ام. اینجا آزمایششان می‌کنم. سبک سرویس همان [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است؛ [Rate limiting و caching در Go](/fa/posts/go-rate-limiting-caching/) هم مکمل خوبی است.

> فقط دفاعی. همه‌چیز در demo خودم روی `127.0.0.1` (آدرس {{< term "loopback" "loopback" >}}) یا آدرس‌های مستندات اجرا شد. هیچ میزبان بیرونی تماس نگرفت. Go 1.26 روی macOS.

## fetcher آسیب‌پذیر

یک endpoint پیش‌نمایش `http.Get(userURL)` را صدا می‌زند. یک سرویس «داخلی» روی port دیگر نقش سرویس admin یا metadata ابری را بازی می‌کند (هدف کلاسیک، بازه‌ی link-local یعنی 169.254.0.0/16 است):

```
$ curl -s '127.0.0.1:18403/fetch?url=http://127.0.0.1:18401/secret'
internal-only: db-password-demo
```

## دفاع‌های ضعیف، هرکدام آزمایش‌شده

blocklist رشته‌ای (`localhost` و `127.0.0.1`) URL آشکار را می‌بندد. بعد هشت نوشتار از همان ماشین را مستقیم به fetcher دادم:

```
http://127.0.0.1:18401/secret     host=127.0.0.1   blocklist-passes=false got secret
http://127.1:18401/secret         host=127.1       blocklist-passes=true  got secret
http://0x7f000001:18401/secret    host=0x7f000001  blocklist-passes=true  got secret
http://2130706433:18401/secret    host=2130706433  blocklist-passes=true  got secret
http://[::1]:18401/secret         host=::1         blocklist-passes=true  got secret
http://localhost.:18401/secret    host=localhost.  blocklist-passes=false got secret
http://[::ffff:127.0.0.1]:18401/secret  ...        blocklist-passes=false got secret
http://x@127.0.0.1:18401/secret   host=127.0.0.1   blocklist-passes=false got secret
```

همه‌ی نوشتارها روی این Mac به secret رسیدند؛ resolver سیستم شکل‌های کوتاه و hex را می‌پذیرد و سیستم‌های دیگر ممکن است فرق کنند. چهار مورد از بررسی substring رد شدند؛ چهار تای دیگر فقط چون متن دقیق را دارند گرفته می‌شوند و مقایسه‌ی دقیق مثل `host == "localhost"` آن‌ها را هم از دست می‌داد. بررسی پیشوند (`HasPrefix(url, "http://allowed.example")`) هم شکست می‌خورد، چون userinfo قبل از host می‌آید:

```
$ curl -s '127.0.0.1:18405/fetch?url=http://allowed.example@127.0.0.1:18401/secret'
internal-only: db-password-demo
```

بررسی‌ای که URL را parse و host را مقایسه می‌کند بهتر است، اما فقط URL اول را می‌بیند. یک سرور شریک روی 18404 redirect می‌دهد و client دنبالش می‌رود:

```
$ curl -s '127.0.0.1:18406/fetch?url=http://127.0.0.1:18404/go'
internal-only: db-password-demo
```

{{< term "dns-rebinding" "DNS rebinding" >}} یک باگ {{< term "toctou" "time-of-check to time-of-use" >}} است. اگر نام را resolve کنید، جواب را بررسی کنید و بعد با نام وصل شوید، lookup دوم می‌تواند فرق کند. با یک resolver ساختگی (جواب اول آدرس مستندات، بعد loopback):

```
  check : rebind.example -> 203.0.113.10 (public-looking: allowed)
  connect: rebind.example -> 127.0.0.1
  internal-only: db-password-demo
```

## راه‌حل: چیزی را که به آن وصل می‌شوید بررسی کنید

یک بار resolve کنید، IP را بررسی کنید و به همان IP وصل شوید. بررسی را در `net.Dialer.Control` هم تکرار کنید، که آدرس واقعی socket را می‌بیند و پس هر مرحله‌ی redirect را هم پوشش می‌دهد:

```go
func checkIP(ip netip.Addr) error {
	ip = ip.Unmap()
	if !ip.IsValid() || ip.IsLoopback() || ip.IsPrivate() ||
		ip.IsLinkLocalUnicast() || ip.IsUnspecified() || ip.IsMulticast() {
		return fmt.Errorf("%w: address %s", ErrBlocked, ip)
	}
	return nil
}
```

دور آن: {{< term "allow-list" "allow-list" >}} برای scheme (`http` و `https`) و port، `CheckRedirect` با سقف سه مرحله، timeout روی client و `io.LimitReader` روی body. یک تست جدولی همه‌ی نوشتارهای دور زدن را می‌فرستد (با port مجاز، تا فقط بررسی آدرس بتواند جلویشان را بگیرد)، به‌علاوه‌ی `file://` و `gopher://`، و بررسی می‌کند سرویس داخلی صفر hit دیده باشد. تست پاس می‌شود. تست‌های دیگر، همان‌طور که log شدند:

```
blocked: address 127.0.0.1          (redirect from the allowed partner to loopback)
lookups=1 dialed=[203.0.113.10:80]  (rebinding resolver asked once, dialed once)
```

تست اندازه برای body یک مگابایتی با سقف 64 کیلوبایت `response too large` برمی‌گرداند. از طریق handler HTTP، حالت redirect و `127.1` حالا `{"error":"url not allowed"}` با status 403 می‌دهند.

نکته‌های اجرا: `netip` خودش `::ffff:127.0.0.1` را loopback و `::ffff:10.0.0.1` را private می‌داند، پس `Unmap` اینجا احتیاط اضافه است (فهرست استثناها را هم نرمال می‌کند). بازه‌های IPv6 دیگر را آزمایش نکردم. سیاست egress شبکه (فایروالی که اصلاً اجازه نمی‌دهد سرویس به بازه‌های داخلی برسد) دفاع در عمق است؛ اجرایش نکردم.

## deserialization ناامن

{{< term "pickle" "pickle" >}} در Python دستورالعمل ذخیره می‌کند، نه فقط داده. کلاس می‌تواند با `__reduce__` بگوید هنگام load کدام تابع صدا زده شود. payload من فقط `print` را صدا می‌زند:

```
-- calling pickle.loads on those bytes
payload ran during loads(): this was only print()
-- json.loads on a document with the same idea
{'__reduce__': ['print', ['x']]}
```

`pickletools.dis` نشان می‌دهد بایت‌ها `builtins print` و opcode به نام `REDUCE` دارند. JSON فقط یک dict ساده برگرداند. مستندات می‌گویند: «The pickle module is not secure. Only unpickle data you trust.» این همان {{< term "unsafe-deserialization" "deserialization ناامن" >}} است. هرگز ورودی کاربر، cacheهای قابل‌نوشتن توسط دیگران یا صف‌هایی را که کنترل نمی‌کنید unpickle نکنید.

PyYAML نسخه‌ی 6.0.3 (pin‌شده، venv موقت که بعد پاک شد) همین تفکیک را دارد:

```
-- yaml.safe_load
ConstructorError could not determine a constructor for the tag 'tag:yaml.org,2002:python/object/apply:builtins.print'
-- yaml.unsafe_load (only for the demo)
yaml tag ran print()
```

از `safe_load` استفاده کنید. بهتر: به داده‌ی ساده parse کنید و با schema اعتبارسنجی کنید، مثل [اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/) و [FastAPI و Pydantic](/fa/posts/py-fastapi-pydantic/).

در Go: `json.Unmarshal` به `any` یک `map[string]interface {}` داد و چیزی اجرا نکرد. `encoding/gob` نوع ثبت‌نشده را رد کرد (`gob: type not registered for interface: main.Cmd`). هیچ‌کدام از این دو قالب نام تابعی برای صدا زدن نمی‌دهند. اما متدهای `UnmarshalJSON` خودتان اجرا می‌شوند، پس آن‌ها را بدون عارضه‌ی جانبی نگه دارید. serializerهای Java، PHP و Node مشکل gadget chain داشته‌اند؛ فقط نامشان را می‌آورم و آزمایششان نکردم.

## چند نکته‌ی مهم

- block-list می‌بازد؛ scheme، port و اگر می‌شود host را allow-list کنید.
- آدرسی را که واقعاً به آن وصل می‌شوید بررسی کنید، در هر مرحله.
- body واکشی‌شده یا جزئیات خطا را خام به کاربر برنگردانید.
- تست محلی روی `127.0.0.1` منطق را ثابت می‌کند، نه شبکه‌ی production شما را.

## تمرین

به یکی از سرویس‌هایتان endpoint `/preview` اضافه کنید. اول تست جدولیِ URLهای دور زدن را بنویسید، شکستنش را ببینید، بعد بررسی dialer را اضافه کنید.

## قدم بعدی

مقاله‌ی بعدی «اشتباه‌های رایج رمزنگاری» است.
