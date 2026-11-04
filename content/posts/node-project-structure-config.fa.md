+++
date = '2027-01-26T10:00:00+03:30'
draft = false
title = 'ساختار پروژه و کانفیگ در Node.js'
description = 'ساختار پروژه و کانفیگ در Node.js: لایه‌بندی، subpath imports، کانفیگ اعتبارسنجی‌شده از env، --env-file، parseArgs، پنهان‌کردن secret و تست با node:test.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "config", "project-structure", "environment-variables", "parseargs"]
cover = { image = "/images/covers/node-project-structure-config.fa.png", alt = "ساختار پروژه و کانفیگ در Node.js", hiddenInSingle = true }
+++

باگی هست که هر توسعه‌دهنده‌ی Node.js دیر یا زود با آن روبه‌رو می‌شود. در محیط `DEBUG=false` می‌گذارید تا debug خاموش شود و لاگ‌های debug همچنان می‌آیند. دلیلش این است که `if (process.env.DEBUG)` برای متن `"false"` درست (truthy) است: هر مقدار محیطی یک رشته است و هر رشته‌ی غیرخالی truthy است. چنین باگی چیزی را کرش نمی‌دهد. برنامه فقط با تنظیم غلط اجرا می‌شود، شاید در production، تا وقتی کسی بفهمد.

پس این مقاله دو پرسش دارد. یک پروژه چطور چیده شود تا با بزرگ شدن، تغییرش و تستش آسان بماند؟ و کانفیگ چطور خوانده شود تا مقدار غلط برنامه را همان لحظه‌ی شروع و با پیام روشن متوقف کند، نه اینکه بعداً رفتار عجیب بسازد؟ [تست در Node.js با node:test](/fa/posts/node-testing-builtin/) تابع‌های کوچک را پوشش داد؛ اینجا شکلی از پروژه را می‌خواهم که تست کردنش آسان بماند.

این معادل Node برای [ساختار پروژه و معماری تمیز در Go](/fa/posts/go-project-layout-clean-architecture/) و [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) است. روی [سرور HTTP](/fa/posts/node-http-server/) و [ماژول‌های ESM](/fa/posts/node-modules-esm-cjs/) بنا شده.

> Node نسخه‌ی v20.13.1. کد یک مثال محلی است (یک پروژه‌ی ESM بدون وابستگی)؛ خروجی‌ها از اجرای واقعی روی loopback با یک پورت آزاد تصادفی کپی شده‌اند، پس شماره‌ی پورت‌هایی که می‌بینید در هر اجرا فرق می‌کند. زمان‌سنجی نکردم.

## چیدمان و composition root

ایده این است که هر نوع کار جای خودش را داشته باشد و هر لایه فقط لایه‌ی زیر خودش را بشناسد:

```text
src/config.js        loadConfig, redact
src/routes/orders.js HTTP only: parse request, call service, write response
src/services/orders.js  business rules
src/repos/orders.js  storage (in memory here)
src/main.js          wires everything
```

route‌ها service‌ها را می‌شناسند، service‌ها repo‌ها را، و هیچ‌کس `main.js` را import نمی‌کند. این چه فایده‌ای دارد؟ فرض کنید handler مسیر هم قاعده‌های کسب‌وکار را داشت و هم کد ذخیره‌سازی را. برای تست یک قاعده باید یک سرور HTTP بالا می‌آوردید، و برای عوض کردن دیتابیس باید handler را ویرایش می‌کردید. با لایه‌ها هر بخش را جدا می‌شود تست کرد.

برای اینکه این ممکن شود، هر لایه یک *factory* است: تابعی که چیزهای لازمش را به‌عنوان آرگومان می‌گیرد، نه اینکه import کند. بعد باید چیزی قطعه‌های واقعی را بسازد و به هم وصل کند. آن `main.js` است، که {{< term "composition-root" "composition root" >}} نام دارد: تنها جایی که همه‌ی قطعه‌های واقعی را می‌شناسد.

```js
const repo = newOrdersRepo();
const service = newOrdersService({ repo, newId: () => randomUUID().slice(0, 8) });
const server = http.createServer(ordersRoutes(service));
```

از بالا بخوانیدش: انبار را بساز، آن را به service بده (همراه تابعی که شناسه می‌سازد) و service را به route‌ها بده. این تکنیک {{< term "dependency-injection" "تزریق وابستگی" >}} (dependency injection) نام دارد؛ اینجا چیزی جز آرگومان تابع نیست، بدون هیچ فریم‌ورکی. یک تست می‌تواند یک repo جعلی بدهد، یا یک `newId` ثابت تا شناسه‌ها قابل پیش‌بینی باشند.

## subpath import

با بزرگ شدن درخت، مسیرهایی مثل `../../services/orders.js` زشت می‌شوند و با جابه‌جا کردن یک فایل می‌شکنند. فیلد `imports` در `package.json` اجازه می‌دهد نام‌های مستعار کوتاه و خصوصی تعریف کنید که {{< term "subpath-imports" "subpath import" >}} نام دارند:

```json
"imports": { "#config": "./src/config.js", "#services/*": "./src/services/*.js" }
```

(`package.json` دمو به همین شکل `#repos/*` و `#routes/*` را هم دارد.) برای بررسی، یک نام مستعار را واقعاً resolve کردم و یکی را که تعریف نشده بود:

```text
import.meta.resolve("#services/orders") -> <demo>/src/services/orders.js
import("#nope/x")                       -> ERR_PACKAGE_IMPORT_NOT_DEFINED
```

خط اول نشان می‌دهد نام مستعار به مسیر واقعی فایل تبدیل می‌شود (پوشه‌ی ماشین را با `<demo>` عوض کردم). خط دوم نشان می‌دهد نام مستعاری که در فهرست نیست با یک کد خطای روشن شکست می‌خورد. نام‌های مستعار باید با `#` شروع شوند و فقط داخل بسته‌ی خودتان کار می‌کنند.

## مقدارهای محیطی رشته‌اند

حالا برگردیم به کانفیگ. {{< term "environment-variable" "متغیرهای محیطی" >}} (environment variable) مقدارهای نام‌داری هستند که یک process از برنامه‌ای که آن را شروع کرده به ارث می‌برد، و راه معمول دادن پورت، کلید و تنظیمات به سرورند. گیرش این است که همیشه رشته‌اند. وقتی نوع‌های دیگر را انتساب دادم این شد:

```text
typeof process.env.N  -> string      (I assigned the number 8080)
process.env.F = false -> "false"     truthy!  process.env.N + 1 -> 80801
process.env.U = undefined -> "undefined"
```

عدد 8080 را انتساب دادم و رشته پس گرفتم. `false` تبدیل شد به متن `"false"` که truthy است. چون `N` رشته است، `process.env.N + 1` دو رشته را به هم چسباند و `80801` شد، نه جمع. حتی `undefined` هم متن `"undefined"` شد. پس باید هر مقدار را خودتان parse کنید و تصمیم بگیرید چه چیزی معتبر است.

## loadConfig: همه‌ی مشکل‌ها یک‌جا

برنامه یک تابع است، `loadConfig({ env, file, argv })`، که ورودی‌های خام را به یک شیء کانفیگ تمیز تبدیل می‌کند. تابع خالص (pure) است: خودش هرگز به `process.env` دست نمی‌زند، پس تست‌ها ورودی خودشان را می‌دهند. منبع‌ها را از ضعیف به قوی لایه‌لایه می‌کند: پیش‌فرض‌ها، بعد یک شیء فایل، بعد متغیرهای محیطی، بعد flagهای خط فرمان. هر مقدار parse می‌شود، همه‌ی مشکل‌ها جمع می‌شوند و تابع یک بار با همه‌شان خطا می‌دهد. این همان ایده‌ی «همه را یک‌جا گزارش کن» در مقاله‌ی Go است. اگر یک خطا را درست کنید و در اجرای بعد خطای بعدی را ببینید وقت از دست می‌دهید؛ اینجا همه را با هم می‌بینید.

`main.js` خطا را می‌گیرد، چاپ می‌کند و با کد 2 خارج می‌شود. (آرگومان `file` در `loadConfig` هست، ولی `main.js` فایل کانفیگی نمی‌خواند؛ فقط `process.env` و flagهای خط فرمان را می‌دهد.) این‌ها اجراهای واقعی‌اند. اولی کلید API ندارد. دومی سه مقدار غلط دارد و کلید هم ندارد:

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

هر مشکل یک خط است که اسم تنظیم را می‌گوید و اینکه چه اشکالی دارد. توجه کنید `APP_DEBUG=yes` عمداً رد می‌شود: فقط `true`/`false` (و `1`/`0`) پذیرفته می‌شود، پس حدس‌زدنی در کار نیست.

flagهای خط فرمان از `util.parseArgs` در کتابخانه‌ی استاندارد می‌آیند، با `--port`، `--host` و `--log-level` که به‌عنوان گزینه‌ی رشته‌ای تعریف شده‌اند. پورت را خودم parse می‌کنم، پس `--port abc` در همان فهرست گزارش می‌شود، به شکل `--port: "abc" is not an integer`. پورت بالاتر از 65535 هم گرفته می‌شود: `port: 99999 is out of range 0-65535`.

## فایل‌های .env

نوشتن متغیرهای زیاد روی خط فرمان خسته‌کننده است، برای همین مردم آن‌ها را در یک فایل `.env` نگه می‌دارند. Node 20.6 و بعدتر می‌تواند یکی را خودش با `--env-file` بخواند، بدون هیچ بسته‌ای. یک `.env` ساختم که `APP_API_KEY=from-file`، `APP_PORT=4100` و `APP_LOG_LEVEL=debug` دارد و سه بررسی کردم:

```text
node --env-file=.env -e '...'               -> from-file 4100
APP_PORT=5200 node --env-file=.env -e '...' -> 5200 from-file
node --env-file=nope.env -e '1'             -> node: nope.env: not found   (exit=9)
```

`'...'` یک اسکریپت یک‌خطی است که `APP_API_KEY` و `APP_PORT` را چاپ می‌کند. اجرای اول هر دو مقدار را از فایل می‌خواند. در دومی `APP_PORT=5200` را در محیط واقعی گذاشتم و از فایل (4100) جلو افتاد، در حالی که کلید همچنان از فایل آمد. پس متغیر محیطی واقعی از فایل قوی‌تر است. سومی نشان می‌دهد فایل ناموجود خطاست و بی‌صدا نادیده گرفته نمی‌شود. در 20.13.1، `process.loadEnvFile` هم هست (`typeof` برابر `function` چاپ شد) و بارگذاری همان فایل `APP_PORT` را 4100 داد. هشداری ندیدم، ولی هر دو قابلیت تازه‌اند، پس هنگام ارتقای Node دوباره بررسی‌شان کنید.

## هرگز رمز را لاگ نکنید

خط شروع جای خوبی برای چاپ کانفیگ است، چون می‌گوید process واقعاً چه تنظیماتی گرفته. جای کلاسیک نشت رمز به لاگ هم هست. `redact(cfg)` وقتی `apiKey` و `dbUrl` مقدار داشته باشند آن‌ها را با `***` عوض می‌کند. این یک اجرای واقعی با کلید API، آدرس دیتابیس، پورت تصادفی و `APP_LOG_LEVEL=debug` است؛ یک `curl -XPOST` فرستادم که سفارشی ساخت و بعد `SIGTERM`:

```text
{"level":"info","msg":"config loaded","config":{"port":61944,"host":"127.0.0.1","logLevel":"debug","dbUrl":"***","apiKey":"***","debug":false}}
{"level":"info","msg":"listening","addr":"127.0.0.1:61944"}
{"level":"info","msg":"shutting down","signal":"SIGTERM"}
```

هر دو رمز پنهان‌اند و بقیه‌ی تنظیمات دیده می‌شوند. (بدون `APP_DB_URL` خط `"dbUrl":""` را نشان می‌دهد، چون مقدار خالی چیزی برای پنهان کردن ندارد.) سیم‌کشی خاموشی در `main.js` همان مقاله‌ی سرور HTTP است: با سیگنال، `server.close()` و `closeIdleConnections()` و بعد خروج.

## تست loadConfig

چون تابع ورودی‌هایش را آرگومان می‌گیرد، تست کوتاه است. `npm test` چهار تست اجرا کرد و همه موفق بودند. پیش‌فرض‌ها، ترتیب file < env < flags، اینکه یک ورودی بد هر چهار مشکل را با هم گزارش می‌کند، و اینکه `redact` کلید را پنهان می‌کند را بررسی می‌کنند. تست اولویت این شکلی است:

```js
const cfg = loadConfig({ file: { port: 1111 }, env: { ...base, APP_PORT: '2222' }, argv: ['--port', '3333'] });
assert.equal(cfg.port, 3333);
```

همان پورت سه بار داده شده، 1111 در فایل، 2222 در محیط و 3333 به‌صورت flag، و flag برنده می‌شود.

## کانفیگی که بی‌صدا غلط است

- **`NODE_ENV` فقط یک رشته می‌گذارد.** خود Node با آن کاری نمی‌کند؛ طبق مستندات، بعضی کتابخانه‌ها (مثلاً Express) رفتارشان را عوض می‌کنند. بدون آن `undefined` و با آن `production` چاپ کردم. منطق خودتان را روی آن شاخه نزنید؛ از تنظیمات صریح استفاده کنید.
- **`.env` را از git بیرون نگه دارید.** رمز واقعی را هرگز commit نکنید.
- **`process.env` را در سراسر کد نخوانید.** یک بار در `loadConfig` بخوانید تا یک جا باشد که parse و اعتبارسنجی می‌کند.
- **اعتبارسنجی دستی مقیاس‌پذیر نیست.** برای چند متغیر خوب است؛ برای بدنه‌ی درخواست و schemaهای بزرگ‌تر [اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/) را در ادامه‌ی سری ببینید.

## تمرین

`APP_TIMEOUT_MS` (عدد صحیح، پیش‌فرض 5000، باید بزرگ‌تر از 0 باشد) و یک flag به اسم `--timeout-ms` اضافه کنید. برای خطای بازه‌ی جدید و برای اولویت تست بنویسید و بررسی کنید مقدار بد همراه بقیه گزارش می‌شود.

## قدم بعدی

«Postgres از Node.js با pg» مقاله‌ی بعدی است. آنجا `dbUrl` همین کانفیگ به یک دیتابیس واقعی وصل می‌شود.
