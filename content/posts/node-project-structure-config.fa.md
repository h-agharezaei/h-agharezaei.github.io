+++
date = '2027-01-26T10:00:00+03:30'
draft = false
title = 'ساختار پروژه و کانفیگ در Node.js'
description = 'ساختار پروژه و کانفیگ در Node.js: لایه‌بندی، subpath imports، کانفیگ اعتبارسنجی‌شده از env، --env-file، parseArgs، پنهان‌کردن secret و تست با node:test.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "config", "project-structure", "environment-variables", "parseargs"]
cover = { image = "/images/covers/node-project-structure-config.fa.png", alt = "ساختار پروژه و کانفیگ در Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [تست در Node.js با node:test](/fa/posts/node-testing-builtin/)، تابع‌های کوچک را تست کردیم. حالا ساختاری می‌خواهم که با بزرگ‌شدن پروژه هم تست‌پذیر بماند، و کانفیگی که اگر غلط باشد بلند خطا بدهد. این مقاله معادل Node برای [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/) و [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) است و روی [سرور HTTP](/fa/posts/node-http-server/) و [ماژول‌های ESM](/fa/posts/node-modules-esm-cjs/) سوار می‌شود.

> Node نسخه‌ی v20.13.1. کد یک مثال محلی است (پروژه‌ی ESM و بدون وابستگی)؛ همه‌ی خروجی‌ها از اجرای واقعی روی loopback کپی شده‌اند. زمان‌بندی نگرفتم چون سیستم مشغول بود.

## ساختار پوشه‌ها و composition root

```text
src/config.js        loadConfig, redact
src/routes/orders.js HTTP only: parse request, call service, write response
src/services/orders.js  business rules
src/repos/orders.js  storage (in memory here)
src/main.js          wires everything
```

route سرویس را می‌شناسد، سرویس repo را می‌شناسد و هیچ‌کس `main.js` را import نمی‌کند. هر لایه یک factory است که چیزهای لازمش را می‌گیرد، و `main.js` همان **{{< term "composition-root" "composition root" >}}** است، تنها جایی که همه‌ی قطعه‌های واقعی را می‌شناسد:

```js
const repo = newOrdersRepo();
const service = newOrdersService({ repo, newId: () => randomUUID().slice(0, 8) });
const server = http.createServer(ordersRoutes(service));
```

این همان **{{< term "dependency-injection" "تزریق وابستگی" >}}** ساده با آرگومان است، بدون فریم‌ورک. تست می‌تواند repo ساختگی یا `newId` ثابت بدهد.

## Subpath imports

مسیرهای عمیق `../../services/orders.js` زشت می‌شوند. فیلد `imports` در `package.json` **{{< term "subpath-imports" "subpath imports" >}}** تعریف می‌کند:

```json
"imports": { "#config": "./src/config.js", "#services/*": "./src/services/*.js" }
```

یکی را واقعی resolve کردم و یکی را که تعریف نشده:

```text
import.meta.resolve("#services/orders") -> <demo>/src/services/orders.js
import("#nope/x")                       -> ERR_PACKAGE_IMPORT_NOT_DEFINED
```

نام باید با `#` شروع شود و فقط داخل همان پکیج کار می‌کند.

## مقدار env همیشه رشته است

**{{< term "environment-variable" "متغیرهای محیطی" >}}** همیشه رشته‌اند:

```text
typeof process.env.N  -> string      (I assigned the number 8080)
process.env.F = false -> "false"     truthy!  process.env.N + 1 -> 80801
process.env.U = undefined -> "undefined"
```

پس `if (process.env.DEBUG)` برای `DEBUG=false` هم درست است و `PORT + 1` رشته‌ها را به هم می‌چسباند. هر مقدار را باید parse کرد.

## loadConfig: همه‌ی مشکل‌ها یک‌جا

`loadConfig({ env, file, argv })` یک تابع خالص است: داخلش `process.env` نیست، پس تست‌ها ورودی خودشان را می‌دهند. اول پیش‌فرض‌ها، بعد شیء فایل، بعد env و بعد flagها را روی هم می‌گذارد، هر مقدار را parse می‌کند، همه‌ی مشکل‌ها را جمع می‌کند و یک بار خطا می‌دهد (همان ایده‌ی «همه را گزارش کن» در مقاله‌ی Go). `main.js` پیام را چاپ می‌کند و با کد 2 خارج می‌شود. اجرای واقعی:

```text
$ node src/main.js
invalid config:
  - APP_API_KEY: required
exit=2

$ APP_PORT=abc APP_DEBUG=yes APP_LOG_LEVEL=loud node src/main.js
invalid config:
  - APP_PORT: "abc" is not an integer
  - APP_DEBUG: "yes" is not a boolean (use true/false)
  - logLevel: "loud" must be one of debug, info, warn, error
  - APP_API_KEY: required
exit=2
```

flagهای خط فرمان با `util.parseArgs` می‌آیند و `--port`، `--host` و `--log-level` را گزینه‌ی رشته‌ای تعریف کرده‌ام. پورت را خودم parse می‌کنم، پس `--port abc` هم در همین فهرست و به شکل `--port: "abc" is not an integer` گزارش می‌شود.

## فایل‌های .env

Node از نسخه‌ی 20.6 گزینه‌ی `--env-file` دارد. با یک `.env` که `APP_API_KEY` و `APP_PORT=4100` و `APP_LOG_LEVEL` دارد:

```text
node --env-file=.env -e '...'               -> from-file 4100
APP_PORT=5200 node --env-file=.env -e '...' -> 5200 from-file
node --env-file=nope.env -e '1'             -> node: nope.env: not found   (exit=9)
```

متغیر محیطی واقعی از فایل جلوتر است و نبودن فایل خطاست. روی 20.13.1 تابع `process.loadEnvFile` هم هست (`typeof` برابر `function` چاپ شد) و بارگذاری همان فایل، `APP_PORT` را 4100 کرد. هشداری ندیدم، ولی هر دو قابلیت جدیدند؛ هنگام ارتقای Node دوباره بررسی‌شان کنید.

## secret را لاگ نکنید

`redact(cfg)` مقدار `apiKey` و `dbUrl` را با `***` عوض می‌کند. این خط شروع واقعی است، بعد با `curl -XPOST` یک سفارش ساختم و `SIGTERM` فرستادم:

```text
{"level":"info","msg":"config loaded","config":{"port":4300,"host":"127.0.0.1","logLevel":"debug","dbUrl":"","apiKey":"***","debug":false}}
{"level":"info","msg":"listening","addr":"127.0.0.1:4300"}
{"level":"info","msg":"shutting down","signal":"SIGTERM"}
```

سیم‌کشی خاموشی در `main.js` همان مقاله‌ی سرور HTTP است: با سیگنال، `server.close()` و `closeIdleConnections()` و بعد خروج.

## تست loadConfig

چون تابع ورودی‌هایش را می‌گیرد، تست کوتاه است (`npm test`، چهار تست، همه موفق). پیش‌فرض‌ها، ترتیب file < env < flags، گزارش هر چهار مشکل با هم و پنهان‌شدن کلید توسط `redact` را چک می‌کند:

```js
const cfg = loadConfig({ file: { port: 1111 }, env: { ...base, APP_PORT: '2222' }, argv: ['--port', '3333'] });
assert.equal(cfg.port, 3333);
```

## چند نکته‌ی مهم

- `NODE_ENV` فقط یک رشته می‌گذارد. خود Node با آن کاری نمی‌کند؛ طبق مستندات بعضی کتابخانه‌ها (مثلاً Express) رفتارشان را عوض می‌کنند. بدون آن `undefined` و با آن `production` چاپ شد. منطق خودتان را روی آن بنا نکنید؛ تنظیم صریح بگذارید.
- `.env` را در git نگذارید و secret واقعی commit نکنید.
- `process.env` را در سراسر کد نخوانید؛ یک بار در `loadConfig` بخوانید.
- برای چند متغیر همین اعتبارسنجی دستی کافی است؛ برای بدنه‌ی درخواست و schemaهای بزرگ‌تر، بعداً در سری مقاله‌ی «اعتبارسنجی ورودی با Zod» می‌آید.

## تمرین

متغیر `APP_TIMEOUT_MS` (عدد صحیح، پیش‌فرض 5000، باید بزرگ‌تر از 0 باشد) و flag به نام `--timeout-ms` اضافه کنید. برای خطای بازه و برای اولویت‌ها تست بنویسید و ببینید مقدار غلط همراه بقیه‌ی خطاها گزارش می‌شود.

## قدم بعدی

مقاله‌ی بعد «Postgres از Node.js با pg» است: وصل‌کردن `dbUrl` همین کانفیگ به یک دیتابیس واقعی.
