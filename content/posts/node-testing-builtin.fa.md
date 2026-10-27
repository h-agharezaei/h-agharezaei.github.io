+++
date = '2027-01-16T10:00:00+03:30'
draft = false
title = 'تست در Node.js با node:test'
description = 'تست در Node.js با node:test روی v20.13.1: describe/it، hook، mock، تایمر mock، reporter، coverage، کد خروج و چیزهایی که این نسخه ندارد.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "testing", "node-test", "mocking", "coverage"]
cover = { image = "/images/covers/node-testing-builtin.fa.png", alt = "تست در Node.js با node:test", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [ساخت API با Fastify](/fa/posts/node-fastify-api/)، یک API راه انداختیم. حالا می‌خواهم مطمئن باشم که کار کردنش ادامه پیدا می‌کند. Node یک {{< term "test-runner" "test runner" >}} داخل کتابخانه‌ی استاندارد دارد، پس برای شروع به Jest یا Mocha نیازی نیست. این معادل Node برای [تست در Go](/fa/posts/go-testing-basics/) است و از [async/await](/fa/posts/node-promises-async-await/) و [سرور HTTP](/fa/posts/node-http-server/) قبلی استفاده می‌کند.

> Node نسخه‌ی v20.13.1 (خروجی `node --version`). دمو یک مثال محلی است: `price.js`، `app.js` و دو فایل در `test/`. همه‌ی خروجی‌ها واقعی‌اند. زمان‌ها را منتشر نمی‌کنم: ماشین شلوغ بود (load average بالای ۱۰) و مدت اجرا را از خروجی‌ها حذف کرده‌ام.

## پایه

`test()` یک تست ثبت می‌کند و `describe()`/`it()` گروه‌بندی می‌کنند. با `node:assert/strict` همه‌ی مقایسه‌ها strict هستند. تست جدولی فقط یک `for ... of` روی case‌هاست (در Go الگو یک slice از struct و `t.Run` است):

```js
describe('applyDiscount cases', () => {
  const cases = [
    { price: 100, percent: 0, want: 100 },
    { price: 19.99, percent: 10, want: 17.99 },
  ];
  for (const c of cases) {
    it(`${c.price} at ${c.percent}%`, () => {
      assert.equal(applyDiscount(c.price, c.percent), c.want);
    });
  }
  it('throws on bad percent', () => {
    assert.throws(() => applyDiscount(10, 101), { name: 'RangeError', message: 'bad percent' });
  });
});
```

کد async با برگرداندن promise کار می‌کند: `await assert.rejects(fetchUser(7, db), { message: 'not found' })`. subtestها با `await t.test(...)` ساخته می‌شوند؛ `{ skip: 'reason' }` تست را رد می‌کند و `{ todo: true }` کار نیمه‌تمام را نشان می‌دهد. hookها `before`، `after`، `beforeEach` و `afterEach` هستند؛ در تست hook من برای دو تست دقیقاً `before,beforeEach,afterEach,beforeEach,afterEach` ثبت شد.

## اجرا و خواندن نتیجه

`node --test` خودش فایل‌ها را پیدا می‌کند. در اجرای من `test/*.js` و `*.test.js` برداشته شدند، ولی فایلی به نام `failing.js` در ریشه تا وقتی صریح ندادمش اجرا نشد. `--test-name-pattern=health` فقط تست‌های هم‌نام را اجرا کرد و بقیه را skip نشان داد. `--watch` با هر تغییر دوباره اجرا می‌کند؛ چون تعاملی است اجرایش نکردم. reporter از نوع spec:

```text
▶ async
  ✔ resolves
  ✔ rejects
  ﹣ skipped one # no network here
  ✖ later # TODO
▶ async
✔ mock.fn and mock.method
ℹ tests 17
ℹ pass 15
ℹ fail 0
ℹ skipped 1
ℹ todo 1
```

تست `todo` در assertion شکست می‌خورد ولی جزو failure شمرده نمی‌شود. reporter از نوع dot خروجی `...............X....` می‌دهد (یک نویسه برای هر تست) و tap خطوط TAP چاپ می‌کند. وقتی stdout ترمینال نیست، پیش‌فرض tap است. یک تست شکست‌خورده‌ی واقعی diff نشان می‌دهد و فرایند با کد ۱ خارج می‌شود:

```text
✖ bad sum
  AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal:
  + actual - expected
    {
      a: 1,
      b: [
        1,
  +     2
  -     3
      ]
    }
```

## mock و injection

`mock.fn()` فراخوانی‌ها را ثبت می‌کند (`db.get.mock.callCount()` و `.calls[0].arguments`) و `mock.method(Math, 'random', () => 0.5)` یک متد را تا `.mock.restore()` عوض می‌کند. قبل از mock کردن حالت سراسری، {{< term "dependency-injection" "injection" >}} را ترجیح بدهید: `makeToken({ now, rand })` زمان و تصادف را پارامتر می‌گیرد و پیش‌فرض واقعی دارد؛ پس تست `now: () => 42, rand: () => 0.1` می‌دهد و دقیقاً `t42-100` می‌گیرد، بدون flaky بودن.

`t.mock.timers` روی 20.13.1 هست، ولی `ExperimentalWarning: The MockTimers API is an experimental feature` چاپ کرد. با آن، `setTimeout(fn, 60_000)` بلافاصله بعد از `tick(60_000)` اجرا شد، بدون انتظار. این‌ها {{< term "test-double" "test double" >}} هستند؛ کم استفاده‌شان کنید.

## handler‌ی HTTP

برای سرور ساده‌ی `node:http` ([مقاله](/fa/posts/node-http-server/)) در `before` روی پورت ۰ listen می‌کنم، پورت واقعی را از `server.address()` می‌خوانم و با `fetch` سراسری روی loopback صدایش می‌زنم. `/health` جواب ۲۰۰ و `{ ok: true }` داد و مسیر ناشناخته ۴۰۴. در `after` هم `server.close()` و `closeAllConnections()` را صدا می‌زنم تا فرایند تمام شود. اپ Fastify به این‌ها نیاز ندارد: `inject()` دارد که بدون socket یک درخواست ساختگی می‌فرستد (مقاله‌ی قبل را ببینید).

## coverage و snapshot

`--experimental-test-coverage` جدول چاپ می‌کند. نتیجه‌ی من:

```text
file                 | line % | branch % | funcs % | uncovered lines
app.js               | 100.00 |   100.00 |  100.00 |
price.js             | 100.00 |    88.89 |   60.00 |
test/price.test.js   | 100.00 |   100.00 |   96.67 |
```

این قابلیت experimental است و در این نسخه خود فایل‌های تست را هم فهرست می‌کند. `price.js` ۶۰٪ تابع پوشش داده چون `notUsed()` را هرگز صدا نزدم. {{< term "code-coverage" "Coverage" >}} می‌گوید چه چیزی اجرا شد، نه اینکه خوب assert شده یا نه.

تست snapshot: بررسی کردم و روی v20.13.1 مقدار `t.assert` برابر `undefined` است و `--test-update-snapshots` با `bad option` شکست می‌خورد. پس اینجا در دسترس نیست؛ نسخه‌های جدیدتر را آزمایش نکردم.

## چند نکته‌ی مهم

- در اجرای من، `before()` سطح بالا کنار `test()`های سطح بالا اول اجرا نشد: `base` مقدار `undefined` داشت و fetch با `Failed to parse URL from undefined/health` شکست خورد. گذاشتن همه‌چیز در `describe` درستش کرد.
- پیدا شدن فایل‌ها بر اساس نام و پوشه است؛ اگر شک دارید مسیر بدهید.
- `todo`ی شکست‌خورده failure نیست؛ تست واقعی را آنجا نگذارید.
- سرور و timer را در `after` ببندید، وگرنه اجرا معلق می‌ماند.
- mock باگ‌های یکپارچگی را پنهان می‌کند؛ چند اجرای واقعی هم داشته باشید.

## تمرین

مسیر `GET /price?value=...&percent=...` را به `app.js` اضافه کنید که `applyDiscount` را صدا بزند، و حالت ۲۰۰ و یک ۴۰۰ برای ورودی بد را با fetch روی پورت ۰ تست کنید.

## قدم بعدی

بعدی: ساختار پروژه و کانفیگ در Node.js.
