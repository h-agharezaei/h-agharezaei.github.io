+++
date = '2026-11-21T10:00:00+03:30'
draft = false
title = 'ماژول‌ها: ESM و CommonJS'
description = 'ESM و CommonJS در Node.js با اجرای واقعی: انتخاب سیستم ماژول، interop، خطای ERR_REQUIRE_ESM، نگاشت exports، cache و import چرخه‌ای.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "modules", "esm", "commonjs", "javascript"]
cover = { image = "/images/covers/node-modules-esm-cjs.fa.png", alt = "ماژول‌ها: ESM و CommonJS", hiddenInSingle = true }
+++

یک مثال کوچک را از یک آموزش کپی می‌کنید، `node app.js` را اجرا می‌کنید و Node جواب می‌دهد: `SyntaxError: Cannot use import statement outside a module`. `import` را به `require` تبدیل می‌کنید، فایل دیگری را اجرا می‌کنید و این بار می‌شنوید `require is not defined`. در هیچ‌کدام از این دو حالت کد ایرادی ندارد. دارید با این واقعیت روبه‌رو می‌شوید که Node.js **دو سیستم ماژول** دارد و ترکیب این دو منشأ بیشتر خطاهای «روی سیستم من کار می‌کرد» در import است.

**ماژول** فقط یک فایل است که متغیرهایش را برای خودش نگه می‌دارد و خودش انتخاب می‌کند چه چیزی را با فایل‌های دیگر به اشتراک بگذارد. هر زبانی شکلی از این را دارد. اگر از Go می‌آیید، به [پکیج‌ها و ماژول‌های Go](/fa/posts/go-packages-modules/) فکر کنید که فقط یک سیستم دارد. Node به دلایل تاریخی دو سیستم دارد: سیستم قدیمی‌تر از اول داخل Node بود و سیستم جدیدتر بعدها به خود زبان JavaScript اضافه شد. وقتی بدانید Node چطور بین این دو تصمیم می‌گیرد، خطاها دیگر مرموز نیستند. در [مقاله‌ی event loop](/fa/posts/node-event-loop/) دیدیم کد چطور اجرا می‌شود؛ اینجا می‌بینیم فایل‌ها چطور همدیگر را پیدا و بارگذاری می‌کنند.

> همه‌ی مثال‌ها با Node نسخه‌ی v20.13.1 در یک پروژه‌ی موقت اجرا شده‌اند و مسیرها را در خروجی‌ها با `<tmp>` عوض کرده‌ام. نسخه‌های جدیدتر Node بعضی از این‌ها را تغییر داده‌اند (مثلاً در بعضی حالت‌ها اجازه می‌دهند یک ES module را `require()` کنید؛ برای نسخه‌ی خودتان مستندات Node.js را ببینید)، ولی من فقط 20.13.1 را اجرا کردم.

## دو سیستم، یک مثال کوچک

**{{< term "commonjs" "CommonJS" >}}** سیستم قدیمی‌تر است. یک فایل با `module.exports` چیزی را به اشتراک می‌گذارد و فایل دیگر با `require()` آن را می‌گیرد:

```js
// math.cjs
module.exports = { add: (a, b) => a + b };

// main.cjs
const { add } = require('./math.cjs');
```

**{{< term "esm" "ES modules" >}}** (به‌اختصار ESM) سیستم جدیدتر و استاندارد است. همین ایده با `export` و `import` نوشته می‌شود:

```js
// math.mjs
export const add = (a, b) => a + b;

// main.mjs
import { add } from './math.mjs';
```

حالا سؤال مهم: وقتی Node یک فایل را باز می‌کند، از کجا بفهمد آن فایل کدام سیستم را به کار برده؟ این تصمیم برای هر فایل جداگانه گرفته می‌شود:

- `.mjs` همیشه ESM است.
- `.cjs` همیشه CommonJS است.
- `.js` از نزدیک‌ترین `package.json` در پوشه‌های بالاتر پیروی می‌کند: `"type": "module"` یعنی ESM، و هر چیز دیگر (از جمله نبودن `"type"`) یعنی CommonJS.

اگر فایل شما با این تصمیم نخواند، همان دو خطای ابتدای مقاله را می‌گیرید. هر دو خروجی واقعی هستند:

```text
SyntaxError: Cannot use import statement outside a module
ReferenceError: require is not defined in ES module scope, you can use import instead
```

اولی از `import` در یک فایل `.js` بدون `"type"` آمد (که پیش‌فرضش CommonJS است). دومی از `require` در یک فایل `.js` با `"type": "module"`. اولی را در یک پوشه‌ی موقت بدون `package.json` دوباره تولید کردم؛ دومی فایل `basic/y.js` خود پوشه‌ی دمو است. Node جدید حتی یک خط اضافه می‌کند که توضیح می‌دهد چرا فایل را ES module حساب کرده و پیشنهاد می‌کند اسمش را به `.cjs` عوض کنید.

## هر طرف چه چیزهایی دارد

این دو سیستم فقط ظاهرشان فرق نمی‌کند؛ اسم‌های آماده‌ی متفاوتی هم به کد شما می‌دهند. این `main.cjs` بررسی می‌کند کدام اسم‌ها وجود دارند:

```js
// main.cjs
console.log(typeof __dirname, typeof __filename, typeof require, typeof module);
```

خروجی `string string function object` است. در یک ES module همین بررسی `typeof` برای `__dirname` و `require` و `module` چاپ می‌کند `undefined undefined undefined`. آن اسم‌ها آنجا اصلاً وجود ندارند. به‌جایشان ESM چیزی به نام `import.meta` دارد:

```text
import.meta.url      file:///<tmp>/basic/main.mjs
import.meta.dirname  <tmp>/basic
import.meta.filename <tmp>/basic/main.mjs
```

`import.meta.dirname` و `import.meta.filename` روی 20.13.1 درست کار کردند. طبق مستندات از نسخه‌ی 20.11 اضافه شده‌اند، پس روی نسخه‌های قدیمی‌تر Node 20 نیستند (`import.meta.url` همه‌جا هست).

ESM همچنین **{{< term "top-level-await" "top-level await" >}}** را مجاز می‌کند: می‌توانید `await` را بیرون از هر تابعی بنویسید. این دو خط در بالای یک فایل `.mjs` چاپ کرد `top-level await: resolved`:

```js
const v = await new Promise(r => setTimeout(() => r('resolved'), 20));
console.log('top-level await:', v);
```

همین نوع خط در یک فایل `.cjs` با `SyntaxError: await is only valid in async functions and the top level bodies of modules` شکست می‌خورد. Node فایل CommonJS را داخل یک تابع می‌پیچد و مثل کد معمولی اجرا می‌کند، پس نمی‌تواند در سطح بالا منتظر بماند.

## import کردن CommonJS از ESM

در پروژه‌های واقعی اغلب هر دو نوع کنار هم هستند، پس ببینیم با هم چطور حرف می‌زنند. جهت اول: یک ES module یک فایل CommonJS را import می‌کند. import **پیش‌فرض** (default) همیشه کار می‌کند و هر چه `module.exports` باشد به شما می‌دهد. import **نام‌دار** (`import { alpha }`) فقط وقتی کار می‌کند که Node بتواند نام‌ها را بدون اجرا کردن کد، فقط با خواندن متن آن، دربیاورد. دو فایل کوچک CommonJS تفاوت را نشان می‌دهند:

```js
// static.cjs: exports.alpha = 1; exports.beta = () => 'beta';
import { alpha, beta } from './static.cjs';   // works

// dynamic.cjs: for (const n of ['gamma', 'delta']) module.exports[n] = n;
import { gamma } from './dynamic.cjs';        // fails
```

در `static.cjs` نام‌ها صریح نوشته شده‌اند. در `dynamic.cjs` در یک حلقه ساخته می‌شوند و Node پیش از اجرا نمی‌تواند آن‌ها را ببیند. import ناموفق این را چاپ می‌کند:

```text
SyntaxError: Named export 'gamma' not found. The requested module './dynamic.cjs' is a CommonJS module, which may not support all module.exports as named exports.
```

Node زیر همین خط راه‌حل را هم چاپ می‌کند: import پیش‌فرض را بگیرید و نام‌ها را خودتان بیرون بکشید. `import whole from './dynamic.cjs'; const { gamma } = whole;` چاپ کرد `gamma`.

## require کردن ESM از CommonJS

جهت دیگر سخت‌تر است. روی 20.13.1 دستور `require('./esm.mjs')` خطا می‌دهد:

```text
Error [ERR_REQUIRE_ESM]: require() of ES Module <tmp>/interop/esm.mjs not supported.
Instead change the require of <tmp>/interop/esm.mjs to a dynamic import() which is available in all CommonJS modules.
```

دلیلش این است که بارگذاری یک ES module می‌تواند ناهمگام باشد (top-level await را یادتان بیاید) ولی `require()` باید همان لحظه مقدار برگرداند. راه‌حل `import()` پویاست، تابعی که یک **{{< term "promise" "promise" >}}** برمی‌گرداند: `import('./esm.mjs').then(m => console.log(m.x))` چاپ کرد `1`. ترفند برعکس هم هست: `createRequire(import.meta.url)` به یک ES module یک `require` کارا می‌دهد و `require('./static.cjs').alpha` از این راه چاپ کرد `1`.

## پکیج‌ها: نقشه‌ی exports

تا اینجا فایل‌های خودمان بودند. یک پکیج منتشرشده مشکل اضافه‌ای دارد: ممکن است هم نسخه‌ی CommonJS و هم نسخه‌ی ESM را همراه خودش بدهد و باید به Node بگوید کدام را استفاده کند. این کار را با فیلد `exports` در `package.json` و **{{< term "conditional-exports" "conditional exports" >}}** انجام می‌دهد. این هم پکیج محلی کوچک من به اسم `dual`:

```json
"exports": {
  ".": { "import": "./lib/index.mjs", "require": "./lib/index.cjs" }
}
```

ورودی `"."` چیزی است که با `import 'dual'` می‌گیرید و اسم شرط‌ها فایل را بر اساس نحوه‌ی بارگذاری انتخاب می‌کنند. `import { kind } from 'dual'` چاپ کرد `esm build` و `require('dual').kind` چاپ کرد `cjs build`.

این نقشه کار دومی هم دارد: فایل‌هایی که در آن نیامده‌اند مهروموم می‌شوند. `require('dual/lib/internal.cjs')` خطای `ERR_PACKAGE_PATH_NOT_EXPORTED` داد، با اینکه فایل واقعاً آنجاست:

```text
Error [ERR_PACKAGE_PATH_NOT_EXPORTED]: Package subpath './lib/internal.cjs' is not defined by "exports" in <tmp>/exports/node_modules/dual/package.json
```

## cache و import حلقه‌ای

وقتی دو فایل یک ماژول را بارگذاری می‌کنند، آیا کد آن دو بار اجرا می‌شود؟ نه. ماژول CommonJS یک بار اجرا می‌شود و نتیجه‌اش در `require.cache` می‌ماند. فایل `math.cjs` من وقتی اجرا می‌شود `math.cjs evaluated` چاپ می‌کند. دو بار `require` شد و این خط فقط یک بار چاپ شد، و `Object.keys(require.cache)` فقط `main.cjs` و `math.cjs` را نشان داد. ESM هم cache می‌کند: `lib.mjs evaluated` برای دو import فقط یک بار آمد.

cache به یک حالت جالب می‌رسد: **وابستگی حلقه‌ای**، یعنی `a` به `b` نیاز دارد و `b` به `a`. Node نمی‌تواند هیچ‌کدام را اول تمام کند. در CommonJS، `a` شروع می‌شود، `exports.done = false` را می‌گذارد و `b` را require می‌کند. وقتی `b` آن را require می‌کند، `exports` **ناقص** `a` را می‌گیرد: هر چه `a` تا آن لحظه گذاشته باشد.

```text
in b, a.done = false
in a, b.done = true
```

`b` دید `a.done = false` است، چون `a` هنوز تمام نشده بود. چیزی خراب نشد، ولی `b` با یک ماژول نیمه‌کاره کار کرد و این را به‌راحتی از دست می‌دهید.

ESM همین شکل را جور دیگری اداره می‌کند. با exportهای `const`، کد با خطایی درباره‌ی **{{< term "live-binding" "live binding" >}}** شکست خورد. در ESM یک import رونوشت نیست، نمایی زنده از متغیر ماژول دیگر است و اینجا `b` پیش از آنکه `a` آن را مقدار بدهد اجرا شد:

```text
ReferenceError: Cannot access 'aval' before initialization
```

live binding بدون حلقه هم دیده می‌شود. با `export let count` در یک ES module، importکننده بعد از صدا زدن `inc()` اول `0` و بعد `1` چاپ کرد: مقدار فعلی را می‌بیند. در CommonJS، `const { count } = require(...)` عدد را یک بار کپی کرد و من `0` و بعد دوباره `0` گرفتم.

## پیشوند node:

یک نکته‌ی آخر. ماژول‌های داخلی را می‌توان با پیشوند `node:` نوشت. `import fs from 'fs'` و `import nfs from 'node:fs'` یک شیء را می‌دهند (بررسی‌اش `true` چاپ کرد). پیشوند روشن می‌کند که منظورتان ماژول داخلی است، نه یک پکیج از npm، و برای `node:test` اجباری است: در یک فایل موقت، `require('test')` خطای `MODULE_NOT_FOUND` داد و `require('node:test')` کار کرد.

## جاهایی که interop خراب می‌شود

- **قاطی کردن سیستم‌ها از سر ناخواسته.** برای هر پروژه یکی را انتخاب کنید و `"type"` را صریح در `package.json` بنویسید. این قضاوت خودم است، نه یک قانون: کد جدید را ESM بنویسید و `.cjs` را فقط جایی که یک ابزار می‌خواهد.
- **فرض کردن اینکه import نام‌دار از CommonJS کار می‌کند.** به این بستگی دارد که Node بتواند نام‌ها را ایستا بخواند. وقتی مطمئن نیستید، import پیش‌فرض را بگیرید و destructure کنید.
- **import حلقه‌ای.** در هر دو سیستم نشانه‌ی طراحی بد است. ESM آن را به خطای بلند تبدیل می‌کند و CommonJS به شیءهای بی‌صدا ناقص.
- **منتشر کردن پکیج بدون `exports`.** آن‌وقت هر فایل داخلی بخشی از API عمومی می‌شود و نمی‌توانید هیچ‌کدام را جابه‌جا کنید بی‌آنکه کسی را خراب کنید.

## تمرین

یک پکیج با `exports` برای `import` و `require` بسازید، به‌اضافه‌ی ورودی `"./package.json"`. آن را از یک فایل `.mjs` و یک فایل `.cjs` استفاده کنید، بعد یک import عمیق از فایلی که export نکرده‌اید امتحان کنید و خطا را بخوانید.

## قدم بعدی

«npm، package.json و قفل وابستگی»: ماژول‌های خودمان را دیدیم و حالا نوبت پکیج‌هایی است که از بیرون می‌آیند و نسخه‌شان باید ثابت بماند.
