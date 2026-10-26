+++
date = '2026-12-03T10:00:00+03:30'
draft = false
title = 'Promise و async/await در Node.js'
description = 'Promise و async/await در Node.js با اجرای واقعی: زنجیره، return await، اشتباهات رایج، Promise.all، AbortController و محدودکننده‌ی concurrency.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "promises", "async-await", "javascript", "abortcontroller"]
cover = { image = "/images/covers/node-promises-async-await.fa.png", alt = "Promise و async/await در Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [npm، package.json و قفل وابستگی](/fa/posts/node-npm-package-json/)، وابستگی‌ها را مدیریت کردیم. حالا سراغ خود کد می‌رویم و تقریباً هر API در Node.js که با آن کار می‌کنید یک **{{< term "promise" "promise" >}}** برمی‌گرداند. این مقاله مستقیم روی [event loop](/fa/posts/node-event-loop/) بنا شده: callback یک promise یک microtask است. اگر از Go می‌آیید، مقایسه‌ی کوتاهش را نزدیک پایان ببینید و برای مدل دیگر به [goroutine و channel](/fa/posts/go-goroutines-channels/) سر بزنید.

> همه‌چیز با Node نسخه‌ی v20.13.1 اجرا شده است. اسکریپت‌ها مثال‌های محلی هستند و خروجی‌ها از اجرای واقعی کپی شده‌اند.

## حالت‌ها و زنجیره

یک promise اول pending است و فقط یک بار fulfilled یا rejected می‌شود. اگر `.then` یک مقدار ساده برگرداند همان به مرحله‌ی بعد می‌رود؛ اگر promise برگرداند منتظرش می‌ماند؛ و throw مستقیم به `.catch` بعدی می‌پرد:

```js
const p = new Promise((res) => setTimeout(() => res('done'), 50));
console.log('right after creation:', p);
p.then(() => console.log('after settle:', p));

Promise.resolve(1)
  .then((v) => v + 1)
  .then((v) => Promise.resolve(v * 10))
  .then((v) => { console.log('chain value:', v); throw new Error('boom'); })
  .then(() => console.log('skipped'))
  .catch((e) => { console.log('caught:', e.message); return 'recovered'; })
  .then((v) => console.log('after catch:', v));
```

```text
right after creation: Promise { <pending> }
chain value: 20
caught: boom
after catch: recovered
after settle: Promise { 'done' }
```

## async/await شکر سینتکسی است، با قاعده‌های microtask

**{{< term "async-await" "async/await" >}}** سینتکسی روی همین promiseهاست. تابع `async` همیشه یک promise برمی‌گرداند و کد بعد از `await` به شکل **{{< term "microtask" "microtask" >}}** اجرا می‌شود:

```js
async function f() {
  console.log('f start');
  await null;
  console.log('f after await');
}
console.log('script start');
f();
Promise.resolve().then(() => console.log('then 1'));
process.nextTick(() => console.log('nextTick'));
setTimeout(() => console.log('timeout'), 0);
console.log('script end');
```

```text
script start
f start
script end
nextTick
f after await
then 1
timeout
```

تابع تا اولین `await` همزمان (synchronous) اجرا می‌شود؛ بقیه‌اش پشت `nextTick` و قبل از timer در صف می‌رود، دقیقاً مثل مقاله‌ی event loop.

## return در برابر return await

داخل `try/catch` این تفاوت مهم است:

```js
async function fail() { throw new Error('inner failure'); }
async function withoutAwait() {
  try { return fail(); } catch (e) { return 'caught inside (no await)'; }
}
async function withAwait() {
  try { return await fail(); } catch (e) { return 'caught inside (with await)'; }
}
```

```text
withAwait -> caught inside (with await)
withoutAwait rejected -> inner failure
```

بدون `await` همان promiseِ ردشده از تابع بیرون می‌رود و `catch` هرگز آن را نمی‌بیند.

## اشتباهات کلاسیک

```js
const forgotten = getUser();           // no await
console.log('forgotten await:', forgotten, forgotten.name);
[1, 2, 3].forEach(async (n) => { await sleep(10); seen.push(n); });
console.log('right after forEach, seen =', seen);
```

```text
forgotten await: Promise { <pending> } undefined
right after forEach, seen = []
later, seen = [ 1, 2, 3 ]
```

`await` فراموش‌شده یک promise در حالت pending و propertyهای `undefined` به شما می‌دهد. `forEach` به promiseهایی که callbackاش برمی‌گرداند توجهی ندارد، پس هیچ‌چیز منتظر نمی‌ماند. از `for...of` همراه `await` یا از `Promise.all(items.map(...))` استفاده کنید. سه کار ۱۰۰ میلی‌ثانیه‌ای، در حلقه‌ی awaitها در برابر `Promise.all` (load average کمتر از ۲٫۵ بود):

```text
sequential ~ 300 ms, Promise.all ~ 100 ms (measured here)
```

## all، allSettled، race و any

```text
all: [ 'a', 'b' ]
all rejected: bad
allSettled: [ { status: 'fulfilled', value: 'a' }, { status: 'rejected', reason: Error: bad ... } ]
race: fast
any: winner
AggregateError All promises were rejected [ 'x', 'y' ]
```

(stack خطای `allSettled` را در متن کوتاه کرده‌ام.) `all` با اولین rejection فوراً شکست می‌خورد، `allSettled` همیشه نتیجه‌ی همه را گزارش می‌کند، `race` اولین تمام‌شده را برمی‌دارد و `any` اولین fulfilled را؛ فقط اگر همه شکست بخورند `AggregateError` پرتاب می‌کند.

## یک unhandled rejection

```js
Promise.reject(new Error('nobody handles me'));
setTimeout(() => console.log('never printed'), 100);
```

در Node 20 این کد خطا را با stack چاپ می‌کند، بعد `Node.js v20.13.1` می‌آید و exit code برابر 1 است؛ timer هرگز اجرا نمی‌شود. یک **{{< term "unhandled-rejection" "unhandled rejection" >}}** process را می‌کشد. مقاله‌ی بعدی خطاها را عمیق‌تر بررسی می‌کند.

## لغو و timeout

```js
const { setTimeout: sleep } = require('node:timers/promises');
const ac = new AbortController();
setTimeout(() => ac.abort(), 50);
try { await sleep(1000, 'x', { signal: ac.signal }); }
catch (e) { console.log('manual abort:', e.name, e.code); }
try { await sleep(1000, 'x', { signal: AbortSignal.timeout(50) }); }
catch (e) { console.log('timeout signal:', e.name, e.code); }
```

```text
manual abort: AbortError ABORT_ERR
timeout signal: AbortError ABORT_ERR
```

سیگنال یک **{{< term "abort-controller" "AbortController" >}}** روش استاندارد لغو است و `AbortSignal.timeout(ms)` یک مهلت می‌سازد. هر دو sleep را زودتر با `AbortError` تمام کردند. signal را به هر APIای که می‌پذیرد بدهید.

## APIهای callback و محدودیت concurrency

`util.promisify` تابع callback به سبک Node یعنی `(err, result)` را به promise تبدیل می‌کند:

```text
double(21) = 42
rejected: negative
isFile: true
```

`Promise.all` بی‌حد روی هزاران آیتم می‌تواند دیتابیس را زیر فشار بگذارد. یک محدودکننده‌ی دست‌نویس که N worker از یک index مشترک برمی‌دارند:

```js
async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
```

ده کار ۱۰۰ میلی‌ثانیه‌ای با limit برابر 3، با شمارش تعداد کارهای هم‌زمان:

```text
results: 0,1,4,9,16,25,36,49,64,81
max in flight: 3
elapsed ~ 400 ms (measured here)
```

عدد 3 برای max همان اثبات است؛ چهار دور ۱۰۰ میلی‌ثانیه‌ای هم با ده کار در گروه‌های سه‌تایی می‌خواند. این کد بدون قفل امن است چون JavaScript روی یک thread اجرا می‌شود (`next++` وسط کار قطع نمی‌شود).

## مقایسه با Go

promise مقداری است که نماینده‌ی نتیجه‌ای در آینده است. goroutine تابعی است که زمان‌بندی می‌شود تا هم‌زمان اجرا شود و نتیجه‌ها روی channel رد و بدل می‌شوند. promiseها برای کد JavaScript موازی‌کاری نمی‌آورند؛ فقط انتظار را سازمان می‌دهند.

## چند نکته‌ی مهم

- هر promise باید await شود، return شود یا `.catch` داشته باشد.
- وقتی می‌خواهید خطا همان‌جا گرفته شود، داخل `try/catch` از `return await` استفاده کنید.
- هرگز داخل `forEach` از `await` استفاده نکنید؛ `for...of` یا `Promise.all` بهتر است.
- برای منابع بیرونی concurrency را محدود کنید و برای timeout یک `AbortSignal` بدهید.

## تمرین

`mapLimit` را طوری تغییر دهید که وقتی یک کار throw کرد، کار تازه‌ای شروع نشود. با یک شمارنده‌ی کارهای شروع‌شده ثابتش کنید.

## قدم بعدی

مقاله‌ی بعدی «خطا و unhandled rejection در Node.js» است.
