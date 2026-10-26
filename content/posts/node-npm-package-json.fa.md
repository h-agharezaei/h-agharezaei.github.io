+++
date = '2026-11-27T10:00:00+03:30'
draft = false
title = 'npm، package.json و قفل وابستگی'
description = 'npm و package.json با اجرای واقعی: انواع وابستگی، بازه‌های semver، package-lock.json، خطای npm ci، npm audit و آنچه npm pack منتشر می‌کند.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "npm", "package-json", "semver", "lockfile"]
cover = { image = "/images/covers/node-npm-package-json.fa.png", alt = "npm، package.json و قفل وابستگی", hiddenInSingle = true }
+++

هر پروژه‌ی Node.js با **{{< term "npm" "npm" >}}** و یک `package.json` شروع می‌شود و بیشتر شگفتی‌های پروداکشن («روی سیستم من کار می‌کرد») از نفهمیدن همین دو می‌آید. این سومین مقاله‌ی سری Node.js است. در مقاله‌ی قبل، [ماژول‌ها: ESM و CommonJS](/fa/posts/node-modules-esm-cjs/)، دیدیم Node کد را چطور بارگذاری می‌کند؛ اینجا می‌بینیم کدِ دیگران چطور به دیسک شما می‌رسد. مقاله‌ی [event loop در Node.js](/fa/posts/node-event-loop/) پایه‌ی این سری است.

> همه‌چیز با Node v20.13.1 و npm 10.5.2 در یک پوشه‌ی دموی تازه و روی رجیستری واقعی اجرا شده است. خروجی‌ها از اجرای واقعی کپی شده‌اند و نتایج رجیستری مربوط به روز اجرا هستند.

## package.json، فیلد به فیلد

`npm init -y` یک اسکلت می‌نویسد. بعد چند فیلد را با `npm pkg set` اضافه کردم:

- `name` و `version`: هویت پکیج. `private: true` باعث می‌شود `npm publish` رد شود؛ برای اپلیکیشن‌ها محافظ خوبی است.
- `type`: مقدار `commonjs` یا `module`؛ تعیین می‌کند فایل‌های `.js` چطور بارگذاری شوند (مقاله‌ی قبل).
- `engines`: نسخه‌های Node پشتیبانی‌شده. npm فقط هشدار می‌دهد، مگر `engine-strict` فعال باشد.
- `scripts`: دستورهای نام‌دار. `exports` و `main`: اینکه `require` یا `import` پکیج شما به کجا می‌رسد. `files`: چه چیزی منتشر شود.

```json
"scripts": { "hello": "node -e \"console.log('hello')\"", "prehello": "echo pre", "posthello": "echo post" }
```

`npm run hello` اول `prehello`، بعد `hello` و بعد `posthello` را اجرا کرد و ترتیب خروجی `pre`، `hello`، `post` بود. `npx <tool>` فایل اجرایی یک پکیج را اجرا می‌کند و اول `node_modules` محلی را نگاه می‌کند.

## چهار نوع وابستگی

`semver` و `ms` را به‌عنوان dependency و `prettier` را به‌عنوان dev dependency نصب کردم (`npm install -D`).

- `dependencies`: در زمان اجرا لازم است.
- `devDependencies`: ابزار توسعه و تست.
- `peerDependencies`: «پروژه‌ی میزبان باید این را فراهم کند»؛ معمولاً برای پلاگین‌ها.
- `optionalDependencies`: شکست نصب تحمل می‌شود.

```text
$ npm ls --omit=dev
├── ms@2.1.3
└── semver@7.6.0
```

`npm ls` ساده `prettier@3.2.5` را هم نشان می‌دهد. image پروداکشن با `npm ci --omit=dev` ابزارهای توسعه را کنار می‌گذارد.

## بازه‌های semver

**{{< term "semver" "Semantic versioning" >}}** یعنی MAJOR.MINOR.PATCH. از خود پکیج `semver` پرسیدم هر بازه چه چیزی را می‌پذیرد:

```js
const semver = require('semver');
const ranges = ['^1.2.3', '~1.2.3', '1.2.3', '^0.2.3'];
const vers = ['1.2.3', '1.2.9', '1.3.0', '2.0.0', '0.2.9', '0.3.0'];
for (const r of ranges) console.log(r.padEnd(7), vers.filter(v => semver.satisfies(v, r)).join(' '));
```

```text
^1.2.3  1.2.3 1.2.9 1.3.0
~1.2.3  1.2.3 1.2.9
1.2.3   1.2.3
^0.2.3  0.2.9
```

`^` به‌روزرسانی minor و patch را می‌پذیرد، `~` فقط patch را، نسخه‌ی بدون علامت دقیق است و زیر 1.0.0 علامت `^` خیلی سخت‌گیرتر می‌شود. نسخه‌ی خط فرمان: `npx semver -r '^1.2.3' 1.9.0 2.0.0` فقط `1.9.0` را چاپ کرد.

## فایل قفل

بازه می‌گوید چه چیزی مجاز است؛ **{{< term "lockfile" "lockfile" >}}** ثبت می‌کند چه چیزی انتخاب شد. این ورودی `semver` در `package-lock.json` است:

```json
"node_modules/semver": {
  "version": "7.6.0",
  "resolved": "https://registry.npmjs.org/semver/-/semver-7.6.0.tgz",
  "integrity": "sha512-EnwXhrlwXMk9gKu5/...",
  "dependencies": { "lru-cache": "^6.0.0" }
}
```

نسخه‌ی دقیق، آدرس دانلود و hash یکپارچگی ثبت شده که npm آن را بررسی می‌کند. برای اپلیکیشن‌ها آن را commit کنید تا لپ‌تاپ و CI یک درخت یکسان نصب کنند. `npm ls --all` نشان می‌دهد `semver` چند **{{< term "transitive-dependency" "وابستگی غیرمستقیم" >}}** آورده است: `lru-cache@6.0.0` و `yallist@4.0.0`. این‌ها کنار `ms` و `prettier` به‌صورت تخت در `node_modules` اصلی نشسته‌اند. موردی با دو نسخه از یک پکیج نساختم، پس مثال deduplication نشان نمی‌دهم.

## npm install در برابر npm ci

`npm install` ممکن است lockfile را عوض کند. `npm ci` پوشه‌ی `node_modules` را پاک می‌کند، دقیقاً همان را که lockfile می‌گوید نصب می‌کند و اگر دو فایل هم‌خوان نباشند شکست می‌خورد. من `ms` را در `package.json` به نسخه‌ی دقیق `1.0.0` تغییر دادم و lock را دست نزدم:

```text
npm ERR! code EUSAGE
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json
 or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install`
 before continuing.
npm ERR! Invalid: lock file's ms@2.1.3 does not satisfy ms@1.0.0
```

(یک خط طولانی را شکسته‌ام.) در CI از `npm ci` استفاده کنید: همین شکست هدف است.

## outdated، view و audit

مربوط به روزی که اجرا کردم:

```text
$ npm outdated
Package   Current  Wanted  Latest
prettier    3.2.5  3.9.10  3.9.10
semver      7.6.0   7.8.5   7.8.5
```

`npm view ms dist-tags` مقدار `latest: '2.1.3'` را با tagهای beta، canary و nightly چاپ کرد و `npm view semver@7 version` همه‌ی نسخه‌های 7.x را فهرست می‌کند. `npm audit` چاپ کرد `found 0 vulnerabilities`. این دستور از رجیستری می‌پرسد، پس به شبکه نیاز دارد و جوابش در طول زمان عوض می‌شود: نتیجه‌ی تمیز امروز چیزی درباره‌ی هفته‌ی بعد ثابت نمی‌کند.

## چه چیزی منتشر می‌شود

در پوشه‌ای دیگر `lib/index.js`، `test/t.js`، `.env` و `NOTES.md` داشتم و `"files": ["lib"]` را گذاشتم. `npm pack --dry-run` فقط `lib/index.js` و `package.json` را فهرست کرد. بدون `files`، npm به قواعدی مثل `.npmignore` برمی‌گردد، پس قبل از انتشار حتماً با dry run بررسی کنید. ابزارهای دیگر (pnpm و yarn) و فایل `.npmrc` برای تنظیمات رجیستری هم هستند؛ اینجا استفاده‌شان نکردم.

## چند نکته‌ی مهم

- `package-lock.json` را commit کنید و با دست ویرایشش نکنید.
- در CI و ساخت Docker از `npm ci` استفاده کنید.
- `^` به پایبندی نگه‌دارندگان به semver اعتماد می‌کند؛ تور ایمنی واقعی شما lockfile است.
- اسکریپت‌های نصبِ وابستگی‌ها روی ماشین شما کد اجرا می‌کنند؛ چیزی را که اضافه می‌کنید بررسی کنید.
- خروجی `npm audit` یک عکس لحظه‌ای است، نه تضمین.

## تمرین

یک پروژه بسازید، `ms` را نصب کنید، بعد بازه‌اش را در `package.json` به چیزی تغییر دهید که lock نتواند برآورده کند و خطای `npm ci` را بخوانید. سپس فیلد `files` را اضافه کنید و با `npm pack --dry-run` بررسی کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ «Promise و async/await در Node.js» می‌رویم.
