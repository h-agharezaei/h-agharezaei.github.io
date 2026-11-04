+++
date = '2026-12-03T10:00:00+03:30'
draft = false
title = 'Promise و async/await در Node.js'
description = 'Promise و async/await در Node.js با اجرای واقعی: زنجیره، return await، اشتباهات رایج، Promise.all، AbortController و محدودکننده‌ی concurrency.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "promises", "async-await", "javascript", "abortcontroller"]
cover = { image = "/images/covers/node-promises-async-await.fa.png", alt = "Promise و async/await در Node.js", hiddenInSingle = true }
+++

فرض کنید تابعی باید یک کاربر را از پایگاه داده بخواند. نمی‌تواند همان لحظه کاربر را برگرداند، چون جواب آن طرف یک اتصال شبکه است. در Node.js (به [event loop](/fa/posts/node-event-loop/) فکر کنید: فقط یک thread هست و نباید بنشیند و منتظر بماند) چنین تابعی همان لحظه چیز دیگری به شما می‌دهد: یک **بلیت**. مثل شماره‌ی کوچکی که پشت پیشخوان رستوران می‌گیرید. آن شماره غذای شما نیست، ولی نماینده‌ی غذای شماست و بعداً یا اعلام می‌کند «آماده است» یا «تمام شد». این بلیت یک **{{< term "promise" "promise" >}}** است و تقریباً هر API در Node.js که با آن کار کنید یکی از آن‌ها را برمی‌گرداند.

این مقاله درباره‌ی درست به کار بردن بلیت‌هاست. چند قاعده‌ی کوچک تعیین می‌کنند خطا مهار شود یا کل process را بکشد. مثلاً اگر در یک تابع async، `return fail()` را داخل `try/catch` بگذارید، `catch` هیچ‌وقت اجرا نمی‌شود؛ یک `await` اضافه کنید و اجرا می‌شود. دلیلش را می‌بینیم. حالا که وابستگی‌ها در [npm، package.json و قفل وابستگی](/fa/posts/node-npm-package-json/) سر جایشان هستند، سری به خود کد می‌رسد. اگر از Go می‌آیید، نزدیک آخر یک مقایسه‌ی کوتاه هست و [goroutine و channel](/fa/posts/go-goroutines-channels/) مدل دیگر را نشان می‌دهد.

> همه‌چیز با Node نسخه‌ی v20.13.1 اجرا شده است. اسکریپت‌ها مثال‌های محلی هستند و خروجی‌ها از اجرای واقعی کپی شده‌اند.

## حالت‌ها و زنجیر کردن

یک promise در یکی از سه حالت است: **pending** (هنوز جواب نیامده)، **fulfilled** (مقدار دارد) یا **rejected** (خطا دارد). فقط یک بار از pending بیرون می‌آید و بعد دیگر عوض نمی‌شود. کار را با `.then(...)` برای موفقیت و `.catch(...)` برای شکست به آن وصل می‌کنید. سه قاعده زنجیر کردن را توضیح می‌دهند:

- `.then`ای که مقدار ساده برگرداند، آن را به `.then` بعدی می‌دهد.
- `.then`ای که یک promise برگرداند، زنجیر را وادار می‌کند منتظر آن promise بماند.
- `throw` تا `.catch` بعدی جلو می‌پرد. و چیزی که `.catch` برمی‌گرداند دوباره یک مقدار عادی می‌شود.

اسکریپت زیر یک promise می‌سازد که بعد از ۵۰ میلی‌ثانیه fulfilled می‌شود، آن را همان لحظه چاپ می‌کند و دوباره بعد از تکلیف‌شدنش. بعد یک زنجیر اجرا می‌کند که هر سه قاعده را به کار می‌برد:

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

خط به خط:

- `right after creation`: promise هنوز pending است، چون timer شلیک نکرده.
- `chain value: 20`: عدد 1 شد 2 و بعد `.then`ای که promise برگرداند زنجیر را منتظر نگه داشت و 20 ساخت. هم مقدار ساده و هم promise درست اداره شدند.
- `caught: boom`: `throw` از مرحله‌ی `skipped` پرید (هیچ‌وقت چاپ نشد) و به `.catch` رسید.
- `after catch: recovered`: `.catch` مقداری برگرداند، پس زنجیر دوباره عادی ادامه پیدا کرد.
- `after settle`: timer ۵۰ میلی‌ثانیه‌ای بالاخره شلیک کرد، خیلی دیرتر از بقیه، و حالا promise مقدار `'done'` را دارد.

## async/await نحوی روی همان promiseهاست

وقتی منطق طولانی شود، زنجیرها سخت خوانده می‌شوند. **{{< term "async-await" "async/await" >}}** اجازه می‌دهد همان را مثل کد پشت‌سرهم معمولی بنویسید. تابع `async` همیشه یک promise برمی‌گرداند و `await somePromise` منتظر آن promise می‌ماند و مقدارش را (یا خطایش را) به شما می‌دهد. سؤال کلیدی این است که `await` با برنامه‌ی شما چه می‌کند، چون thread نباید بلاک شود. این اسکریپت نشانش می‌دهد:

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

در `await` این اتفاق می‌افتد:

1. `f()` مثل هر تابعی صدا زده می‌شود و روی call stack اجرا می‌شود. `f start` را چاپ می‌کند.
2. در `await null`، `f` **متوقف** می‌شود. جایش روی call stack را رها می‌کند و `f()` یک promise در حالت pending به صدازننده برمی‌گرداند. بقیه‌ی `f` به شکل یک callback، یعنی یک **{{< term "microtask" "microtask" >}}**، ذخیره می‌شود تا به‌محض آماده شدن مقدارِ `await`شده ادامه پیدا کند.
3. اسکریپت ادامه می‌دهد: `script end` چاپ می‌شود و call stack خالی می‌شود.
4. صف‌ها با همان ترتیبی که در مقاله‌ی event loop دیدیم خالی می‌شوند: اول `nextTick`، بعد microtaskها به ترتیب اضافه شدن. `f` ادامه‌ی خودش را پیش از `then 1` در صف گذاشت، پس `f after await` زودتر می‌آید.
5. timer در فاز بعدی است، پس `timeout` آخر می‌آید.

پس `await` هیچ چیز را بلاک نمی‌کند. تابع را به دو نیم می‌کند: نیمه‌ی پیش از آن همین حالا اجرا می‌شود و نیمه‌ی بعد از آن بعداً به‌عنوان microtask. thread در این فاصله برای بقیه‌ی کارها آزاد می‌ماند.

## return در برابر return await

حالا معمای اول مقاله. هر دو تابع زیر `fail()` را صدا می‌زنند که همیشه reject می‌شود و هر دو آن را در `try/catch` گذاشته‌اند:

```js
async function fail() { throw new Error('inner failure'); }
async function withoutAwait() {
  try { return fail(); } catch (e) { return 'caught inside (no await)'; }
}
async function withAwait() {
  try { return await fail(); } catch (e) { return 'caught inside (with await)'; }
}
```

دمو هر دو را صدا می‌زند و چاپ می‌کند هر promise چطور تمام شد:

```text
is promise: true
withAwait -> caught inside (with await)
withoutAwait rejected -> inner failure
```

بدون `await`، `return fail()` promise ردشده را بی‌آنکه نگاهش کند از تابع بیرون می‌دهد. تا promise reject شود تابع تمام شده و `catch` دیگر آنجا نیست که ببیندش، پس رد شدن به صدازننده می‌رسد. با `await`، تابع داخل `try` منتظر می‌ماند، رد شدن همان‌جا به یک خطای پرتاب‌شده تبدیل می‌شود و `catch` آن را مهار می‌کند.

## اشتباه‌های کلاسیک

سه اشتباه بارها تکرار می‌شوند. این دمویی است که آن‌ها را بازتولید می‌کند (`sleep` و `getUser` دو تابع کمکی کوچک در فایل‌اند):

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

- **`await` فراموش‌شده.** به‌جای کاربر، بلیت را می‌گیرید: یک promise در حالت pending و `undefined` برای هر ویژگی‌ای که از آن بخوانید.
- **`forEach` با callback ناهمگام.** `forEach` promiseهایی را که callback برمی‌گرداند نادیده می‌گیرد، پس همان لحظه تمام می‌شود و هیچ‌چیز منتظر نمی‌ماند. `seen` درست بعد از حلقه خالی است و بعداً پر می‌شود. از `for...of` با `await` یا از `Promise.all(items.map(...))` استفاده کنید.
- **یکی‌یکی منتظر ماندن وقتی می‌شد با هم منتظر ماند.** سه کار صدمیلی‌ثانیه‌ای، اول در یک حلقه‌ی awaitها و بعد با `Promise.all`:

```text
sequential ~ 300 ms, Promise.all ~ 100 ms (measured here)
```

حلقه کارها را پشت سر هم اجرا می‌کند (۳ × ۱۰۰ میلی‌ثانیه). `Promise.all` هر سه را با هم شروع می‌کند و منتظر کندترین می‌ماند. عددها به ۱۰۰ میلی‌ثانیه گرد شده‌اند. اجرای اصلی با load average زیر ۲٫۵ انجام شد و اجرای دوباره‌ام برای این نسخه همین خط را چاپ کرد.

## all، allSettled، race، any

وقتی چند promise دارید، چهار راه برای ترکیبشان هست. این اسکریپت هر کدام را با چند timer امتحان می‌کند که بعد از تأخیری کوتاه موفق یا ناموفق می‌شوند:

```js
// inside an async function
console.log('all:', await Promise.all([later(10, 'a'), later(20, 'b')]));
// ... a rejecting input for all; then allSettled, race, any ...
```

```text
all: [ 'a', 'b' ]
all rejected: bad
allSettled: [ { status: 'fulfilled', value: 'a' }, { status: 'rejected', reason: Error: bad ... } ]
race: fast
any: winner
AggregateError All promises were rejected [ 'x', 'y' ]
```

(stack چاپ‌شده‌ی `reason` در `allSettled` را کوتاه کرده‌ام. اسکریپت کامل در پوشه‌ی دمو است.) به زبان ساده:

- `Promise.all` منتظر همه می‌ماند و آرایه‌ای از مقدارها می‌دهد. **زود شکست می‌خورد**: اولین رد شدن کل کار را رد می‌کند (`all rejected: bad`).
- `Promise.allSettled` هیچ‌وقت reject نمی‌شود. منتظر همه می‌ماند و برای هرکدام یک وضعیت گزارش می‌دهد، پس موفقیت‌ها و شکست‌ها را کنار هم می‌بینید.
- `Promise.race` هر promiseای را که اول تکلیفش روشن شود می‌گیرد، چه موفق چه ناموفق (`fast`).
- `Promise.any` اولین promiseای را می‌گیرد که *fulfilled* شود. فقط وقتی reject می‌شود که همه شکست بخورند، آن هم با یک **{{< term "aggregate-error" "AggregateError" >}}** که همه‌ی دلیل‌ها را جمع کرده.

## یک unhandled rejection

اگر یک promise ردشده کسی را نداشته باشد که مهارش کند چه می‌شود؟ این اسکریپت دو‌خطی جوابش را پیدا می‌کند:

```js
Promise.reject(new Error('nobody handles me'));
setTimeout(() => console.log('never printed'), 100);
```

روی Node 20 این خطا را با stack چاپ می‌کند و بعد `Node.js v20.13.1` (خط‌های stack را که مسیر دارند حذف کرده‌ام)، exit code برابر ۱ است و timer هیچ‌وقت شلیک نمی‌کند. **{{< term "unhandled-rejection" "unhandled rejection" >}}** process را می‌کشد. برای همین `.catch`ی فراموش‌شده خطرناک است: باگ بی‌صدا نیست، crash است. مقاله‌ی بعد خطاها را عمیق‌تر بررسی می‌کند.

## لغو کردن و timeout

یک promise خودش را لغو نمی‌کند، برای همین Node از یک شیء جدا برای این کار استفاده می‌کند: **{{< term "abort-controller" "AbortController" >}}**. `signal` آن را به عملیات می‌دهید و صدا زدن `abort()` عملیات را با یک `AbortError` متوقف می‌کند. `AbortSignal.timeout(ms)` signalای می‌دهد که بعد از یک مهلت خودش abort می‌شود. اسکریپت زیر ۱۰۰۰ میلی‌ثانیه می‌خوابد ولی بعد از ۵۰ میلی‌ثانیه لغو می‌کند، و بعد همین کار را با signal مهلت‌دار انجام می‌دهد. چون `await` به کار رفته، دمو کد را داخل یک تابع async گذاشته است:

```js
const { setTimeout: sleep } = require('node:timers/promises');
(async () => {
  const ac = new AbortController();
  setTimeout(() => ac.abort(), 50);
  try { await sleep(1000, 'x', { signal: ac.signal }); }
  catch (e) { console.log('manual abort:', e.name, e.code); }
  try { await sleep(1000, 'x', { signal: AbortSignal.timeout(50) }); }
  catch (e) { console.log('timeout signal:', e.name, e.code); }
})();
```

```text
manual abort: AbortError ABORT_ERR
timeout signal: AbortError ABORT_ERR
```

هر دو خواب به‌جای ۱۰۰۰ میلی‌ثانیه حدود ۵۰ میلی‌ثانیه بعد با `AbortError` تمام شدند. signal را به هر APIای که می‌پذیرد بدهید (مثلاً `fetch` می‌پذیرد).

## APIهای callback و محدود کردن هم‌زمانی

APIهای قدیمی‌تر Node به‌جای برگرداندن promise یک callback به شکل `(err, result)` می‌گیرند. `util.promisify` چنین تابعی را طوری می‌پیچد که promise برگرداند. این دمو یک تابع ساختگی و `fs.stat` را می‌پیچد:

```js
const double = promisify(legacyDouble);
const stat = promisify(fs.stat);
```

```text
double(21) = 42
rejected: negative
isFile: true
```

محدودیت دیگری که به آن می‌خورید: `Promise.all` بدون سقف روی هزاران آیتم، هزاران عملیات را هم‌زمان شروع می‌کند و می‌تواند پایگاه داده را زیر فشار بگذارد. راه‌حل یک limiter است: N کارگر که آیتم بعدی را از یک اندیس مشترک برمی‌دارند تا چیزی نماند.

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

دمو ده کار صدمیلی‌ثانیه‌ای را با سقف ۳ اجرا می‌کند و می‌شمارد چند کار هم‌زمان در حال اجرا بودند:

```text
results: 0,1,4,9,16,25,36,49,64,81
max in flight: 3
elapsed ~ 400 ms (measured here)
```

`max in flight: 3` ثابت می‌کند سقف رعایت شد. ده کار در گروه‌های سه‌تایی چهار دور صدمیلی‌ثانیه‌ای می‌خواهد که با ۴۰۰ میلی‌ثانیه جور است. این بدون هیچ قفلی امن است، چون JavaScript روی یک thread اجرا می‌شود و `next++` را کارگر دیگری نیمه‌کاره قطع نمی‌کند. (خط elapsed به ۱۰۰ میلی‌ثانیه گرد شده و در اجرای دوباره‌ام هم همین بود.)

## مقایسه با Go

promise مقداری است که نماینده‌ی یک نتیجه‌ی آینده است. goroutine تابعی است که برای اجرای هم‌زمان زمان‌بندی می‌شود و نتیجه‌ها از راه channel می‌روند. promiseها برای کد JavaScript شما موازی‌سازی نمی‌دهند؛ انتظار را سازمان می‌دهند.

## promiseهایی که گم می‌شوند

- **promiseای که کسی مهارش نمی‌کند.** هر promise باید await شود، return شود یا `.catch` بگیرد؛ وگرنه یک rejection می‌تواند process را بکشد.
- **`return` به‌جای `return await` داخل `try/catch`.** وقتی می‌خواهید خطا در همان تابع مهار شود از `return await` استفاده کنید.
- **`await` داخل `forEach`.** منتظر نمی‌ماند. از `for...of` یا `Promise.all` استفاده کنید.
- **هم‌زمانی بی‌سقف.** برای منبع‌های بیرونی مثل پایگاه داده محدودش کنید و یک `AbortSignal` بدهید تا فراخوانی‌های کند timeout شوند.

## تمرین

`mapLimit` را طوری تغییر دهید که وقتی یک کار throw کرد، کار جدیدی شروع نشود. با یک شمارنده‌ی کارهای شروع‌شده ثابتش کنید.

## قدم بعدی

«خطا و unhandled rejection در Node.js»: دیدیم یک unhandled rejection process را می‌کشد، پس قدم بعد این است که تصمیم بگیریم خطا کجا باید گرفته شود و کجا نه.
