+++
date = '2027-01-16T10:00:00+03:30'
draft = false
title = 'تست در Node.js با node:test'
description = 'تست در Node.js با node:test روی v20.13.1: describe/it، hook، mock، تایمر mock، reporter، coverage، کد خروج و چیزهایی که این نسخه ندارد.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "testing", "node-test", "mocking", "coverage"]
cover = { image = "/images/covers/node-testing-builtin.fa.png", alt = "تست در Node.js با node:test", hiddenInSingle = true }
+++

تابعی دارید و می‌خواهید مطمئن باشید بعد از تغییر بعدی هنوز درست کار می‌کند. جواب کلاسیک این است که یک فریم‌ورک تست مثل Jest یا Mocha نصب کنید، با فایل کانفیگ و ده‌ها وابستگی‌اش. در Node.js برای شروع به این‌ها نیازی نیست: کتابخانه‌ی استاندارد یک {{< term "test-runner" "اجراکننده‌ی تست" >}} (test runner) دارد، به اسم `node:test`، و دستور `node --test` آن را اجرا می‌کند. این معادل Node برای [تست در Go](/fa/posts/go-testing-basics/) است، که آنجا هم ابزار داخلی است.

در [ساخت API با Fastify](/fa/posts/node-fastify-api/) یک API را بالا آوردم؛ حالا می‌خواهم بدانم کار کردنش ادامه پیدا می‌کند. این مقاله از [async/await](/fa/posts/node-promises-async-await/) و [سرور HTTP](/fa/posts/node-http-server/) مقاله‌های قبل استفاده می‌کند. یک غافلگیری کوچک را هم که با آن روبه‌رو شدم نشان می‌دهم، چون یادآوری خوبی است: نتیجه‌ی سبز فقط وقتی قابل اعتماد است که رفتار ابزارتان را بدانید.

> Node نسخه‌ی v20.13.1 (چاپ‌شده با `node --version`). دمو یک مثال محلی است: `price.js`، `app.js` و دو فایل در `test/`. همه‌ی خروجی‌ها از اجرای واقعی‌اند. در همه‌ی خروجی‌های زیر زمان‌ها حذف شده، چون ماشین شلوغ بود (میانگین بار بالای ۲۰) و زمان‌سنجی معنایی نداشت.

## پایه‌ها

تست تابعی است که اگر چیزی غلط باشد خطا پرتاب می‌کند. `test()` یکی را ثبت می‌کند و `describe()` و `it()` تست‌ها را گروه می‌کنند، دقیقاً مثل فریم‌ورک‌های دیگر. برای assertion، `node:assert/strict` همه‌ی مقایسه‌ها را سخت‌گیر می‌کند (پس `1` با `'1'` برابر نیست).

کدی که تست می‌کنیم یک تابع کوچک است، `applyDiscount(price, percent)`، که قیمت را بعد از تخفیف درصدی برمی‌گرداند و برای درصد نامعتبر `RangeError` پرتاب می‌کند. تست جدولی فقط یک حلقه‌ی `for ... of` روی حالت‌هاست که برای هر کدام یک `it` می‌سازد (در Go ایده‌اش یک slice از struct و `t.Run` است):

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

کد async چیز خاصی نمی‌خواهد: تابع تست را `async` کنید یا یک promise برگردانید و برای حالت شکست از `assert.rejects` استفاده کنید: `await assert.rejects(fetchUser(7, db), { message: 'not found' })`. زیرتست‌ها با `await t.test(...)` نوشته می‌شوند. گزینه‌ی `{ skip: 'reason' }` یک تست را رد می‌کند و `{ todo: true }` کار نیمه‌تمام را علامت می‌زند.

چهار hook برای کد آماده‌سازی و پاک‌سازی هست: `before` و `after` (یک بار برای هر گروه) و `beforeEach` و `afterEach` (دور هر تست). تست hookهای من اسم هر hook را در یک آرایه می‌ریخت و آخر چاپ می‌کرد. برای دو تست آرایه این بود: `before,beforeEach,afterEach,beforeEach,afterEach`. یعنی hookها با همان ترتیبی که انتظار دارید اجرا شدند.

## اجرا و خواندن نتیجه

`node --test` فایل‌های تست را خودش پیدا می‌کند، پس لازم نیست فهرستشان کنید. در دموی من دو فایل داخل `test/` را برداشت و `failing.js` را در ریشه‌ی پروژه نادیده گرفت؛ برای اجرای آن باید اسمش را صریح می‌دادم. `--test-name-pattern=health` فقط تست‌هایی را که اسمشان می‌خورد اجرا کرد و ۱۲ تای دیگر را رد‌شده (skipped) گزارش کرد. `--watch` هم هست که با تغییر فایل دوباره تست می‌کند؛ اجرایش نکردم چون تعاملی است.

reporter با نام `spec` یک درخت خوانا چاپ می‌کند. این خروجی واقعی کل دموست، با حذف زمان‌ها و stack trace بلند (خط‌های `…`):

```text
▶ http
  ✔ GET /health
  ✔ unknown path is 404
after, log = before,beforeEach,afterEach,beforeEach,afterEach
✔ applies a discount
▶ applyDiscount cases
  ✔ 100 at 0%
  ✔ 100 at 100%
  ✔ 19.99 at 10%
  ✔ throws on bad percent
▶ hooks
  ✔ one
  ✔ two
▶ async
  ✔ resolves
  ✔ rejects
  ﹣ skipped one # no network here
  ✖ later # TODO
    AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
    1 !== 2
    …
✔ mock.fn and mock.method
✔ injected time and randomness
✔ mock.timers
ℹ tests 17
ℹ suites 3
ℹ pass 15
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 1
```

این‌طور بخوانیدش: `▶` یک گروه را باز می‌کند و `✔` یعنی موفق. خط `﹣` تست رد‌شده است و دلیلش بعد از `#` می‌آید. خط `✖` تست `todo` است: assertion آن واقعاً شکست می‌خورد (`1 !== 2`) ولی تستی که `todo` علامت خورده شکست حساب نمی‌شود، پس `fail` صفر است و اجرا همچنان موفق است. برای کار نیمه‌تمام مفید است، و اگر یک تست واقعی را آنجا فراموش کنید خطرناک.

reporterهای دیگری هم هست. reporter نقطه‌ای `...............X....` چاپ کرد، یک نویسه برای هر تست (`X` همان تست todo است). وقتی خروجی ترمینال نیست، مثلاً در pipe یا CI، پیش‌فرض در Node 20 `tap` است، یک قالب خط‌به‌خط که با `TAP version 13` شروع می‌شود. یک تست واقعاً شکست‌خورده (فایل `failing.js` عبارت `{ a: 1, b: [1, 2] }` را با `{ a: 1, b: [1, 3] }` مقایسه می‌کند) یک diff نشان می‌دهد و process با کد 1 خارج می‌شود، که چیزی است که CI نگاه می‌کند:

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

خط `+` چیزی است که کد تولید کرد و خط `-` چیزی است که تست انتظار داشت، پس تفاوت را فوراً می‌بینید.

## mock و تزریق

گاهی یک تست نباید چیز واقعی را صدا بزند: دیتابیس، ساعت، مولد عدد تصادفی. **mock** یک جانشین است که ثبت می‌کند چطور صدا زده شده. `mock.fn()` یک تابع ثبت‌کننده می‌سازد (`db.get.mock.callCount()` و `.calls[0].arguments`) و `mock.method(Math, 'random', () => 0.5)` یک متد موجود را جایگزین می‌کند تا وقتی `.mock.restore()` را صدا بزنید.

قبل از اینکه state سراسری را عوض کنید، به راه تمیزتری فکر کنید: {{< term "dependency-injection" "تزریق" >}} (injection)، یعنی وابستگی را به‌عنوان پارامتر بدهید. در دمو، `makeToken({ now, rand })` زمان و تصادف را به‌عنوان پارامتر با پیش‌فرض‌های واقعی می‌گیرد. تست `now: () => 42, rand: () => 0.1` می‌دهد و هر بار دقیقاً `t42-100` می‌گیرد، بدون ناپایداری و بدون mock.

اجراکننده می‌تواند زمان را هم جعل کند. `t.mock.timers` در 20.13.1 هست و `ExperimentalWarning: The MockTimers API is an experimental feature` چاپ کرد. با آن، `setTimeout(fn, 60_000)` درست بعد از `tick(60_000)` اجرا شد، بدون انتظار واقعی. mockها، timerهای جعلی و مانند آن‌ها {{< term "test-double" "جایگزین‌های تست" >}} (test double) نام دارند؛ کم استفاده‌شان کنید، چون تستی پر از جایگزین ممکن است سبز باشد در حالی که سیستم واقعی خراب است.

## یک handler HTTP

برای یک سرور ساده‌ی `node:http` ([مقاله](/fa/posts/node-http-server/)) الگو همان الگوی آن مقاله است. داخل `before` سرور را روی پورت 0 بالا می‌آورم (سیستم‌عامل یک پورت آزاد می‌دهد)، پورت واقعی را از `server.address()` می‌خوانم و با `fetch` سراسری روی loopback صدایش می‌زنم. `/health` جواب 200 و `{ ok: true }` داد و یک مسیر ناشناخته 404. در `after` هم `server.close()` و `closeAllConnections()` را صدا می‌زنم تا process بتواند خارج شود؛ وگرنه اتصال‌های باز آن را زنده نگه می‌دارند و اجرا گیر می‌کند. اپ Fastify به هیچ‌کدام نیاز ندارد: `inject()` دارد که درخواست ساختگی را بدون سوکت می‌فرستد (مقاله‌ی قبل).

## coverage و snapshot

`--experimental-test-coverage` جدولی اضافه می‌کند که نشان می‌دهد تست‌ها چقدر از کد را اجرا کردند. جدول من (با reporter از نوع spec و بدون پیشوند `ℹ`):

```text
file               | line % | branch % | funcs % | uncovered lines
app.js             | 100.00 |   100.00 |  100.00 |
price.js           | 100.00 |    88.89 |   60.00 |
test/app.test.js   | 100.00 |   100.00 |  100.00 |
test/price.test.js | 100.00 |   100.00 |   96.67 |
all files          | 100.00 |    98.08 |   93.18 |
```

این قابلیت آزمایشی است و در این نسخه خود فایل‌های تست را هم فهرست می‌کند. `price.js` ۶۰٪ تابع‌هایش پوشش دارد چون `notUsed()` را هیچ‌وقت صدا نمی‌زنم، که برای دیدن همین اضافه‌اش کردم. {{< term "code-coverage" "Coverage" >}} می‌گوید چه چیزی اجرا شد، نه اینکه خوب assert شد یا نه: تستی که تابعی را صدا می‌زند و هیچ‌چیز را نمی‌سنجد هم حساب می‌شود.

snapshot testing، که در آن اجراکننده یک خروجی را ذخیره می‌کند و دفعه‌ی بعد با آن مقایسه می‌کند، اینجا در دسترس نیست. در v20.13.1 مقدار `t.assert` برابر `undefined` است و `--test-update-snapshots` با `bad option` شکست می‌خورد. نسخه‌های جدیدتر Node را امتحان نکردم.

## جاهایی که node:test غافلگیر می‌کند

- **`before()` سطح بالا باعث نمی‌شود تست‌های سطح بالا منتظرش بمانند.** در یک فایل scratch با `before(async () => {...})` و یک `test()` سطح بالا در کنارش، hook شروع شد (`before ran` چاپ کرد) ولی بدنه‌ی تست پیش از تمام شدن `await` داخل hook اجرا شد: `base` برابر `undefined` بود و fetch با `Failed to parse URL from undefined/health` شکست خورد. گذاشتن hook و تست‌ها داخل `describe` درستش کرد، که دمو همین کار را می‌کند. این را در یک نسخه‌ی scratch بازتولید کردم؛ جزو فایل‌های دمو نیست.
- **کشف فایل‌ها بر اساس اسم و پوشه است.** `failing.js` در ریشه برداشته نشد. اگر شک دارید مسیرها را صریح بدهید.
- **`todo`ی شکست‌خورده شکست حساب نمی‌شود.** تست واقعی را آنجا نگذارید.
- **سرورها و timerها را در `after` ببندید.** وگرنه اجرا گیر می‌کند.
- **mockها باگ‌های یکپارچگی را پنهان می‌کنند.** چند تست را با بخش‌های واقعی ترکیب کنید.

## تمرین

مسیر `GET /price?value=...&percent=...` را به `app.js` اضافه کنید که `applyDiscount` را صدا بزند، و حالت 200 و یک 400 برای ورودی بد را با fetch روی پورت 0 تست کنید.

## قدم بعدی

«ساختار پروژه و کانفیگ در Node.js» مقاله‌ی بعدی است. تست‌پذیری به ساختار برمی‌گردد، یعنی به اینکه وابستگی‌ها و کانفیگ کجا ساخته و تزریق می‌شوند.
