+++
date = '2026-11-21T10:00:00+03:30'
draft = false
title = 'ماژول‌ها: ESM و CommonJS'
description = 'ESM و CommonJS در Node.js با اجرای واقعی: انتخاب سیستم ماژول، interop، خطای ERR_REQUIRE_ESM، نگاشت exports، cache و import چرخه‌ای.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "modules", "esm", "commonjs", "javascript"]
cover = { image = "/images/covers/node-modules-esm-cjs.fa.png", alt = "ماژول‌ها: ESM و CommonJS", hiddenInSingle = true }
+++

Node.js دو سیستم ماژول دارد و ترکیب این دو منشأ بیشتر خطاهای «روی سیستم من کار می‌کرد» در import است. در [مقاله‌ی قبلی](/fa/posts/node-event-loop/) دیدیم کد چطور اجرا می‌شود؛ اینجا می‌بینیم فایل‌ها چطور بارگذاری می‌شوند. اگر از Go می‌آیید، آن را با [پکیج‌ها و ماژول‌های Go](/fa/posts/go-packages-modules/) مقایسه کنید که فقط یک سیستم دارد.

> همه‌ی مثال‌ها با Node نسخه‌ی v20.13.1 در یک پروژه‌ی موقت اجرا شده‌اند. نسخه‌های جدیدتر Node بعضی از این‌ها را تغییر داده‌اند، ولی من فقط 20.13.1 را اجرا کردم.

## دو سیستم، یک تصمیم

**{{< term "commonjs" "CommonJS" >}}** از `require()` و `module.exports` استفاده می‌کند. **{{< term "esm" "ES modules" >}}** (ESM) از `import` و `export`. Node برای هر فایل جدا تصمیم می‌گیرد: `.mjs` یعنی ESM، `.cjs` یعنی CommonJS و `.js` تابع نزدیک‌ترین `package.json` است: `"type": "module"` یعنی ESM و در غیر این صورت CommonJS. با انتخاب اشتباه این خطاها را می‌گیرید (هر دو واقعی):

```text
SyntaxError: Cannot use import statement outside a module
ReferenceError: require is not defined in ES module scope, you can use import instead
```

اولی از `import` در یک فایل `.js` بدون `"type"` آمد و دومی از `require` در فایل `.js` با `"type": "module"`.

## هر طرف چه دارد

```js
// main.cjs
console.log(typeof __dirname, typeof __filename, typeof require, typeof module);
```

خروجی `string string function object` است. در ES module همین بررسی `typeof` برای `__dirname`، `require` و `module` چاپ می‌کند `undefined undefined undefined`. به‌جایش ESM شیء `import.meta` را دارد:

```text
import.meta.url      file:///.../basic/main.mjs
import.meta.dirname  /.../basic
import.meta.filename /.../basic/main.mjs
```

`import.meta.dirname` و `filename` روی 20.13.1 درست کار کردند (طبق مستندات از 20.11 اضافه شده‌اند). ESM **{{< term "top-level-await" "top-level await" >}}** هم دارد: `const v = await somePromise` در بالای یک فایل `.mjs` خروجی `top-level await: resolved` داد. همین خط در فایل `.cjs` خطای `SyntaxError: await is only valid in async functions and the top level bodies of modules` داد.

## import کردن CommonJS از ESM

import پیش‌فرض همیشه همان `module.exports` است. importهای نام‌دار فقط وقتی کار می‌کنند که Node بتواند نام‌ها را از روی سورس به‌صورت ایستا تشخیص دهد:

```js
// static.cjs: exports.alpha = 1; exports.beta = () => 'beta';
import { alpha, beta } from './static.cjs';   // کار می‌کند

// dynamic.cjs: for (const n of ['gamma']) module.exports[n] = n;
import { gamma } from './dynamic.cjs';        // خطا
```

```text
SyntaxError: Named export 'gamma' not found. The requested module './dynamic.cjs' is a CommonJS module, which may not support all module.exports as named exports.
```

راه‌حل، import پیش‌فرض و destructuring است: `import whole from './dynamic.cjs'; const { gamma } = whole;` خروجی `gamma` داد.

## require کردن ESM از CommonJS

روی 20.13.1 دستور `require('./esm.mjs')` خطا می‌دهد:

```text
Error [ERR_REQUIRE_ESM]: require() of ES Module .../esm.mjs not supported.
Instead change the require of .../esm.mjs to a dynamic import() which is available in all CommonJS modules.
```

راه‌حل `import()` پویاست که promise برمی‌گرداند: `import('./esm.mjs').then(m => console.log(m.x))` چاپ کرد `1`. جهت برعکس هم راه دارد: `createRequire(import.meta.url)` به ES module یک `require` کارا می‌دهد.

## پکیج‌ها: نگاشت exports

پکیج می‌تواند هر دو build را همراه کند و با **{{< term "conditional-exports" "conditional exports" >}}** بگذارد Node انتخاب کند. پکیج محلی کوچک من، `dual`:

```json
"exports": {
  ".": { "import": "./lib/index.mjs", "require": "./lib/index.cjs" }
}
```

`import { kind } from 'dual'` چاپ کرد `esm build` و `require('dual').kind` چاپ کرد `cjs build`. فایل‌هایی که در نگاشت نیامده‌اند بسته‌اند: `require('dual/lib/internal.cjs')` خطای `ERR_PACKAGE_PATH_NOT_EXPORTED` داد.

## cache و import چرخه‌ای

ماژول CommonJS فقط یک بار اجرا می‌شود و نتیجه در `require.cache` می‌ماند. فایل `math.cjs` من با دو بار `require` فقط یک بار `math.cjs evaluated` چاپ کرد و `Object.keys(require.cache)` دو فایل `main.cjs` و `math.cjs` را نشان داد. ESM هم cache دارد: برای دو import، `lib.mjs evaluated` یک بار آمد.

وابستگی چرخه‌ای فرق می‌کند. در CommonJS، `a` فایل `b` را require می‌کند و `b` دوباره `a` را و یک `exports` **ناقص** می‌گیرد:

```text
in b, a.done = false
in a, b.done = true
```

در ESM همین ساختار با exportهای `const` به خطای **{{< term "live-binding" "live binding" >}}** خورد، چون `b` پیش از مقداردهی `a` اجرا شد:

```text
ReferenceError: Cannot access 'aval' before initialization
```

live binding در `export let count` هم دیده می‌شود: importکننده بعد از `inc()` اول `0` و بعد `1` چاپ کرد. در CommonJS، `const { count } = require(...)` مقدار را کپی کرد و خروجی `0` و بعد `0` بود.

## پیشوند node:

`import fs from 'fs'` و `'node:fs'` یک شیء‌اند (`true`). پیشوند، ماژول‌های داخلی را صریح می‌کند و برای `node:test` اجباری است: `require('test')` خطای `MODULE_NOT_FOUND` داد و `require('node:test')` کار کرد.

## چند نکته‌ی مهم

- برای هر پروژه یک سیستم انتخاب کنید و `"type"` را صریح بنویسید. این نظر شخصی من است: کد جدید با ESM و `.cjs` فقط جایی که ابزاری لازم دارد.
- importهای نام‌دار از CommonJS را قطعی فرض نکنید؛ اگر مطمئن نیستید از import پیش‌فرض استفاده کنید.
- وابستگی چرخه‌ای بوی بد طراحی است؛ ESM آن را به خطای بلند تبدیل می‌کند و CommonJS به `undefined` بی‌صدا.
- کتابخانه‌ها حتماً `exports` تعریف کنند، وگرنه همه‌ی فایل‌های داخلی API عمومی می‌شوند.

## تمرین

پکیجی با `exports` برای `import` و `require` و یک ورودی `"./package.json"` بسازید. آن را از `.mjs` و `.cjs` مصرف کنید، بعد یک import عمیق امتحان کنید و خطا را بخوانید.

## قدم بعدی

مقاله‌ی بعدی «npm، package.json و قفل وابستگی» است.
