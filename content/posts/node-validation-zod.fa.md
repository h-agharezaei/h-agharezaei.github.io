+++
date = '2027-03-15T10:00:00+03:30'
draft = false
title = 'اعتبارسنجی ورودی با Zod'
description = 'اعتبارسنجی ورودی با Zod در Node.js: parse و safeParse، شکل واقعی خطاها، coerce، strict، refine، transform و پاسخ 400 در مرز HTTP، همه با اجرای واقعی.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "zod", "validation", "security", "http"]
cover = { image = "/images/covers/node-validation-zod.fa.png", alt = "اعتبارسنجی ورودی با Zod", hiddenInSingle = true }
+++

کسی برای ثبت سفارش این JSON را به سرور شما می‌فرستد: `{ "id": "nope", "qty": "2", "admin": true }`. `id` شناسه‌ی معتبری نیست، `qty` به‌جای عدد متن `"2"` است و `admin` فیلدی است که هرگز از او نخواسته‌اید. اگر کدتان بی‌نگاه‌کردن `body.qty * price` را بخواند، چیزی حساب می‌کند و حتی ممکن است درست به نظر برسد: `"2" * 5` در JavaScript می‌شود 10. فیلد `admin` اگر بدنه را در یک ردیف دیتابیس کپی کنید ممکن است بی‌صدا آسیب بزند. بدنه‌ی درخواست فقط متنی است که یک غریبه نوشته.

راه‌حل این نیست که همه‌جا `if` بپاشیم. راه‌حل این است که داده را یک‌بار، همان لبه‌ای که وارد برنامه می‌شود، بررسی کنیم و بگذاریم هرچه پشت آن لبه است با داده‌ای کار کند که شکلش معلوم است. آن لبه یک {{< term "trust-boundary" "مرز اعتماد" >}} است: جایی که داده از چیزی که کنترلش با شما نیست (اینترنت، سرویس دیگر، صف پیام) وارد کد خودتان می‌شود. این بررسی را {{< term "schema-validation" "اعتبارسنجی با schema" >}} می‌نامند: شکل معتبر را یک‌بار توصیف می‌کنید و یک کتابخانه داده‌ی ورودی را با آن مقایسه می‌کند.

داده‌ی [NATS JetStream از Node.js](/fa/posts/node-nats-jetstream/) هم در همین معنا هنوز نامطمئن است، و هر بدنه‌ی HTTP در [سرور HTTP با node:http](/fa/posts/node-http-server/) هم. در این مقاله این بررسی را با Zod انجام می‌دهم، یک کتابخانه‌ی schema برای JavaScript. این کار در برابر {{< term "mass-assignment" "mass assignment" >}} هم کمک می‌کند (وقتی کلاینت فیلدهایی را تنظیم می‌کند که نباید؛ [OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/) را ببینید) و در برابر ترفندهای [تزریق و XSS](/fa/posts/sec-injection-xss/).

> همه‌چیز را با Node نسخه‌ی v20.13.1 و `zod` نسخه‌ی 4.1.5 (major نسخه‌ی ۴) اجرا کردم. اسکریپت‌ها مثال محلی‌اند؛ سرور روی 127.0.0.1 و یک پورت تصادفی گوش می‌دهد. خروجی‌ها واقعی‌اند و زمان‌بندی نشان نمی‌دهم. `typescript` نصب نبود، پس بررسی نوع با `z.infer` را اجرا نکردم.

## یک schema برای سفارش

schema در Zod مثل توصیف داده‌ی معتبر خوانده می‌شود. این یکی برای سفارش است:

```js
export const Order = z.object({
  id: z.uuid(),
  email: z.email(),
  status: z.enum(['new', 'paid']).default('new'),
  note: z.string().max(20).optional(),
  items: z.array(z.object({
    sku: z.string().min(3),
    qty: z.coerce.number().int().min(1).max(10),
  })).min(1),
});
```

از بالا بخوانید: `id` باید UUID باشد، `email` آدرس ایمیل، `status` یا `new` است یا `paid` و اگر نباشد `new` می‌شود، `note` متن اختیاری حداکثر ۲۰ کاراکتری است، و `items` فهرستی غیرخالی است که هر آیتمش یک `sku` حداقل ۳ کاراکتری و یک `qty` صحیح بین ۱ تا ۱۰ دارد. `z.coerce.number()` یعنی «اول متن را به عدد تبدیل کن».

حالا `Order.parse(...)` روی این ورودی، یک سفارش خوب به‌اضافه‌ی `admin: true` اضافی و مقداری که به‌شکل متن نوشته شده:

```js
{ id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c', email: 'a@example.com',
  items: [{ sku: 'abc', qty: '2' }], admin: true }
```

این را برگرداند:

```text
{
  id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c',
  email: 'a@example.com',
  status: 'new',
  items: [ { sku: 'abc', qty: 2 } ]
}
```

سه اتفاق افتاد. `status` نبود، پس مقدار پیش‌فرض `new` را گرفت. `qty` که `'2'` بود به‌خاطر `z.coerce` عدد 2 شد. و کلید ناشناخته‌ی `admin` از بین رفت: به‌طور پیش‌فرض شیء Zod کلیدهایی را که نمی‌شناسد حذف می‌کند. آنچه از `parse` بیرون می‌آید شیء تازه و تمیزی است، نه خود ورودی.

## parse، safeParse و issueها

اگر داده بد باشد چه؟ `parse` یک `ZodError` پرتاب می‌کند. `safeParse` پرتاب نمی‌کند: `{ success: true, data }` یا `{ success: false, error }` برمی‌گرداند. برای ورودی شبکه من `safeParse` را ترجیح می‌دهم، چون بدنه‌ی بد چیزی عادی و قابل‌انتظار است، نه یک رویداد استثنایی.

یک payload بد دادم: `{ id: 'nope', email: 'x', items: [{ sku: 'a', qty: 99 }] }`. `parse` یک `ZodError` با ۴ issue پرتاب کرد. هر عضو `error.issues` یک `code`، یک `path` (جای مشکل در ورودی) و یک `message` دارد. مثلاً مشکل `qty`:

```text
{
 "origin": "number",
 "code": "too_big",
 "maximum": 10,
 "inclusive": true,
 "path": ["items", 0, "qty"],
 "message": "Too big: expected number to be <=10"
}
```

(این یکی از issueهای خروجی واقعی است؛ آرایه‌ی `path` را برای کم‌کردن جا در یک خط گذاشتم.) مسیر `["items", 0, "qty"]` می‌گوید: در `items`، عضو اول، فیلد `qty`.

برای پاسخ API معمولاً خطاها را بر حسب فیلد می‌خواهید. این نسخه `z.flattenError` دارد که `fieldErrors` را می‌دهد، با فهرست پیام‌ها برای هر کلید سطح بالا:

```text
{
  formErrors: [],
  fieldErrors: {
    id: [ 'Invalid UUID' ],
    email: [ 'Invalid email address' ],
    items: [
      'Too small: expected string to have >=3 characters',
      'Too big: expected number to be <=10'
    ]
  }
}
```

ببینید که دو مشکل `items` در یک فهرست ادغام شده‌اند و جایشان (کدام آیتم، کدام فیلد) از دست رفته. `z.treeifyError` تو در تو بودن را نگه می‌دارد. برای همین خطا، بخش `items` آن این بود:

```text
{"errors":[],"items":[{"errors":[],"properties":{"sku":{"errors":["Too small: expected string to have >=3 characters"]},"qty":{"errors":["Too big: expected number to be <=10"]}}}]}
```

این‌جا `items[0].properties.qty` را می‌توانید پیدا کنید. بر حسب نیاز کلاینت‌هایتان انتخاب کنید: تخت ساده‌تر است و درختی دقیق‌تر.

## strict، refine و transform

سه ابزار دیگر. خط‌های بعد از یک اسکریپت‌اند و خروجی هرکدام به‌صورت کامنت آمده:

```js
const P = z.object({ name: z.string() });
P.strict().safeParse({ name: 'a', extra: 1 }).error.issues;
// [ { code: 'unrecognized_keys', keys: [ 'extra' ], path: [], message: 'Unrecognized key: "extra"' } ]

const Range = z.object({ from: z.number(), to: z.number() })
  .refine(v => v.from < v.to, { message: 'from must be < to', path: ['to'] });
Range.safeParse({ from: 5, to: 1 }).error.issues;
// [ { code: 'custom', path: [ 'to' ], message: 'from must be < to' } ]

const Tag = z.string().trim().toLowerCase().transform(s => s.split(','));
Tag.parse('  A,B ');
// [ 'a', 'b' ]
```

(در اسکریپت، `P.parse({ name: 'a', extra: 1 })` بدون `strict` مقدار `{ name: 'a' }` را برمی‌گرداند؛ کلید اضافه فقط حذف می‌شود.)

- **`.strict()`** کلیدهای ناشناخته را به‌جای نادیده‌گرفتن بی‌صدا، خطا می‌کند. وقتی فیلد غیرمنتظره یعنی کلاینت گیج شده از آن استفاده کنید.
- **`.refine`** قاعده‌ای را بررسی می‌کند که چند فیلد را درگیر می‌کند، مثل «from باید کوچک‌تر از to باشد». یک `path` بدهید تا پیام روی یک فیلد بنشیند.
- **`.transform`** خروجی را عوض می‌کند، پس مقدار parse‌شده ممکن است دیگر شبیه ورودی نباشد. این‌جا متن `'  A,B '` تمیز شد، به حروف کوچک رفت و به آرایه شکسته شد.

## در مرز HTTP

حالا بخشی که برای سرور مهم است. handler بدنه را می‌خواند، JSON را parse می‌کند و بعد schema را اجرا می‌کند. اگر رد شود، جواب ۴۰۰ با خطای فیلدهاست. اگر قبول شود، فقط مقدار تمیز ادامه می‌دهد:

```js
const r = Order.safeParse(data);
if (!r.success) return send(res, 400, { error: 'validation', issues: z.flattenError(r.error).fieldErrors });
send(res, 200, { id: r.data.id, status: r.data.status, units: total(r.data) });
```

تابع کسب‌وکار `total` همیشه فقط سفارش معتبر می‌گیرد و به بررسی خودش نیاز ندارد. اسکریپت سرور را بالا می‌آورد، پنج درخواست واقعی با `fetch` می‌فرستد و وضعیت و بدنه‌ی هرکدام را چاپ می‌کند:

```text
ok      200 {"id":"3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c","status":"new","units":2}
bad     400 {"error":"validation","issues":{"id":["Invalid UUID"],"email":["Invalid email address"],"items":["Too small: expected array to have >=1 items"]}}
type    400 {"error":"validation","issues":{"id":["Invalid input: expected string, received number"],"email":["Invalid input: expected string, received null"],"items":["Invalid input: expected array, received string"]}}
proto   200 {"id":"3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c","status":"new","units":1}
broken  400 {"error":"invalid JSON"}
```

- `ok`: سفارش خوب، با `qty` به‌شکل متن. جواب ۲۰۰ با ۲ واحد.
- `bad`: id غلط، ایمیل غلط، فهرست `items` خالی. هر مشکل زیر فیلد خودش آمده.
- `type`: فیلدهای درست ولی نوع‌های غلط (`id` عدد است، `email` برابر null و `items` یک رشته). پیام‌ها می‌گویند چه انتظار می‌رفت و چه رسید.
- `proto`: بدنه‌ای با کلید `__proto__`؛ بخش بعد توضیحش می‌دهد. جواب یک ۲۰۰ معمولی است.
- `broken`: `{oops` اصلاً JSON نیست. `JSON.parse` پیش از آنکه Zod چیزی ببیند شکست می‌خورد، پس این حالت ۴۰۰ و پیام جداگانه‌ی خودش را دارد.

## کلیدهایی مثل `__proto__`

JSON می‌تواند کلیدی به اسم `__proto__` داشته باشد. بعد از `JSON.parse` این یک کلید معمولی خود شیء است، نه prototype آن. ولی اگر کدی بعداً کلیدها را با انتساب ساده کپی کند، `__proto__` می‌تواند مهم شود. این ایده‌ی پشت {{< term "prototype-pollution" "آلودگی prototype" >}} است.

با `{"name":"x","__proto__":{"isAdmin":true},"constructor":{"prototype":{"polluted":1}}}` امتحان کردم. parse‌کردنش با `z.object({ name: z.string() })` مقدار `{ name: 'x' }` داد. prototype آن هنوز `Object.prototype` بود و `isAdmin` برابر `undefined`. همین ورودی با `.loose()`، که کلیدهای ناشناخته را نگه می‌دارد، فرق داشت: نتیجه `isAdmin: true` داشت، البته فقط روی همان یک شیء (`({}).isAdmin` همچنان `undefined` ماند). یک `Object.assign({}, evil)` ساده هم همین اثر را نشان داد. برداشت من این است که کلید `__proto__` با انتساب کپی شده و این کار prototype نتیجه را تعیین می‌کند؛ کد Zod را نخوانده‌ام تا این را تأیید کنم.

پس در حالت پیش‌فرض چنین کلیدی بی‌ضرر است و این دلیل خوبی است که `.loose()` را روی ورودی عمومی نگذاریم. همین بدنه به سرور هم فرستاده شد (خط `proto` بالا) و جواب ۲۰۰ معمولی بود و بعدش `({}).isAdmin` در process سرور هنوز `undefined` بود. این یک بررسی محلی روی همین نسخه بود، نه اثبات امنیتی.

## مقایسه با Go

در Go، `encoding/json` به‌طور پیش‌فرض فیلدهای ناشناخته را نادیده می‌گیرد، مگر اینکه روی decoder تابع `DisallowUnknownFields` را صدا بزنید. تگ‌های struct مثل `json:"qty"` فقط فیلدها را نام می‌برند و بازه‌ها را بررسی نمی‌کنند ([فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/) را ببینید). Zod شکل و قاعده‌ها را یک‌جا انجام می‌دهد.

## چیزهایی که اعتبارسنجی پوشش نمی‌دهد

- **اعتبارسنجی در چند جا.** یک‌بار در مرز اعتبارسنجی کنید و مقدار parse‌شده را ادامه دهید، نه بدنه‌ی خام را. وگرنه یک مسیر کد از داده‌ی بررسی‌نشده استفاده می‌کند.
- **تبدیل بیش از حد مهربان.** در اجرای من `z.coerce.number()` مقدار `''` را `0` کرد، در حالی که `'abc'` شکست خورد. بدون `coerce`، مقدار `'2'` رد می‌شود («expected number, received string»). فقط جایی coerce کنید که واقعاً متن می‌پذیرید.
- **برگرداندن issueها همان‌طور که هستند.** پیام‌ها ممکن است نام فیلدهای داخلی را لو بدهند. تصمیم بگیرید کلاینت چه ببیند.
- **باور اینکه همه‌چیز را بررسی می‌کند.** اعتبارسنجی شکل را می‌سنجد، نه دسترسی و نه قاعده‌های کسب‌وکار. سفارش معتبر از کاربر اشتباه باز هم اشتباه است.
- **نسخه‌ی شناور.** major نسخه‌ی Zod را ثابت کنید؛ پیام‌های v4 با نسخه‌های قدیمی‌تر فرق دارند.

## تمرین

یک schema برای `PATCH /orders` از `Order.partial()` بسازید و کلیدهای ناشناخته را ۴۰۰ کنید. با یک `refine` که حداقل یک فیلد را الزامی می‌کند، تست کنید که بدنه‌ی خالی همچنان رد می‌شود.

## قدم بعدی

مقاله‌ی بعد «worker thread و cluster در Node.js» است. ورودی معتبر هم می‌تواند پردازشش گران باشد: یک تابع همزمانِ کند همه‌ی درخواست‌ها را بلوکه می‌کند و آن مقاله نشان می‌دهد چطور از سر راه برش داریم.
