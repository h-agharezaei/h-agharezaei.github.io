+++
date = '2027-03-15T10:00:00+03:30'
draft = false
title = 'اعتبارسنجی ورودی با Zod'
description = 'اعتبارسنجی ورودی با Zod در Node.js: parse و safeParse، شکل واقعی خطاها، coerce، strict، refine، transform و پاسخ 400 در مرز HTTP، همه با اجرای واقعی.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "zod", "validation", "security", "http"]
cover = { image = "/images/covers/node-validation-zod.fa.png", alt = "اعتبارسنجی ورودی با Zod", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [NATS JetStream از Node.js](/fa/posts/node-nats-jetstream/)، گفتم payload هنوز ورودی غیرقابل‌اعتماد است. همین درباره‌ی هر body در [سرور HTTP با node:http](/fa/posts/node-http-server/) هم درست است. هر چیزی که از یک **{{< term "trust-boundary" "مرز اعتماد" >}}** رد می‌شود باید یک بار و در لبه از **{{< term "schema-validation" "اعتبارسنجی با schema" >}}** بگذرد؛ کدِ پشت آن با داده‌ای به شکل معلوم کار می‌کند. اینجا با Zod این کار را می‌کنم. این کار راه **mass assignment** ([OWASP Top 10 در کد واقعی](/fa/posts/sec-owasp-top10-in-code/)) و ترفندهای مشابه [Injection و XSS](/fa/posts/sec-injection-xss/) را هم می‌بندد.

> Node نسخه‌ی v20.13.1، `zod` نسخه‌ی 4.1.5 (major نسخه‌ی ۴). اسکریپت‌های محلی روی 127.0.0.1، خروجی‌های واقعی و بدون زمان‌بندی. `typescript` نصب نبود، پس بررسی نوع با `z.infer` را اجرا نکردم.

## یک schema برای سفارش

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

`parse` روی `{ id, email, items: [{ sku: 'abc', qty: '2' }], admin: true }` این را داد:

```text
{
  id: '3f2b8c1e-5d4a-4b7e-9a1c-0d2e4f6a8b1c',
  email: 'a@example.com',
  status: 'new',
  items: [ { sku: 'abc', qty: 2 } ]
}
```

سه اتفاق افتاد: `status` مقدار پیش‌فرض گرفت، `qty` برابر `'2'` با `z.coerce` عدد ۲ شد و کلید ناشناخته‌ی `admin` حذف شد. به‌طور پیش‌فرض objectها کلیدهای ناشناخته را strip می‌کنند.

## parse، safeParse و issueها

`parse` یک `ZodError` پرتاب می‌کند (برای payload خراب من ۴ issue)؛ `safeParse` بدون پرتاب، `{ success, data }` یا `{ success: false, error }` برمی‌گرداند. برای ورودی شبکه `safeParse` را ترجیح می‌دهم، چون body خراب عادی است، نه استثنا. در `error.issues` هر مورد `code`، `path` و `message` دارد، مثلاً:

```text
{ "code": "too_big", "maximum": 10, "path": ["items", 0, "qty"],
  "message": "Too big: expected number to be <=10" }
```

(`origin` و `inclusive` را حذف کردم.) این نسخه `z.flattenError` هم دارد که برای هر کلید سطح بالا فهرست پیام می‌دهد:

```text
fieldErrors: { id: [ 'Invalid UUID' ], email: [ 'Invalid email address' ],
  items: [ 'Too small: expected string to have >=3 characters',
           'Too big: expected number to be <=10' ] }
```

دقت کنید دو پیام `items` در هم ریخته و اندیس از دست رفته است. `z.treeifyError` تو در تویی را نگه می‌دارد (`items[0].properties.qty`). بسته به نیاز کلاینت انتخاب کنید.

## strict، refine، transform

```text
P.strict() روی {name, extra}: code 'unrecognized_keys', keys ['extra'], message 'Unrecognized key: "extra"'
refine از from<to روی {from:5,to:1}: code 'custom', path ['to'], message 'from must be < to'
z.string().trim().toLowerCase().transform(s => s.split(',')).parse('  A,B ')  ->  [ 'a', 'b' ]
```

وقتی فیلد ناشناخته باید خطا باشد، نه نادیده گرفته شود، از `.strict()` استفاده کنید. `.refine` برای قاعده‌هایی است که چند فیلد را درگیر می‌کنند؛ `path` بدهید تا پیام روی یک فیلد بنشیند. `.transform` خروجی را عوض می‌کند، پس مقدار parse‌شده ممکن است با ورودی برابر نباشد.

## در مرز HTTP

```js
const r = Order.safeParse(data);
if (!r.success) return send(res, 400, { error: 'validation', issues: z.flattenError(r.error).fieldErrors });
send(res, 200, { id: r.data.id, status: r.data.status, units: total(r.data) });
```

`total` همیشه فقط سفارش معتبر می‌گیرد. درخواست‌های واقعی به سرور:

```text
ok     200 {"id":"3f2b8c1e-...","status":"new","units":2}
bad    400 {"error":"validation","issues":{"id":["Invalid UUID"],"email":["Invalid email address"],"items":["Too small: expected array to have >=1 items"]}}
type   400 {"error":"validation","issues":{"id":["Invalid input: expected string, received number"],"email":["Invalid input: expected string, received null"],"items":["Invalid input: expected array, received string"]}}
broken 400 {"error":"invalid JSON"}
```

JSON خراب مورد جدایی است: `JSON.parse` پیش از Zod شکست می‌خورد، پس ۴۰۰ مخصوص خودش را دارد.

## کلیدهایی مثل __proto__

`JSON.parse` روی `{"name":"x","__proto__":{"isAdmin":true},"constructor":{...}}` شیءای می‌دهد که `__proto__` در آن یک کلید own عادی است. parse با `z.object({ name: z.string() })` نتیجه‌ی `{ name: 'x' }` داد، با prototype برابر `Object.prototype` و بدون `isAdmin`. با `.loose()` که کلیدهای ناشناخته را نگه می‌دارد، نتیجه `isAdmin: true` گرفت (از راه `__proto__` کپی‌شده، به‌صورت ارثی)، اما `({}).isAdmin` همچنان `undefined` ماند. پس کلیدی به سبک **{{< term "prototype-pollution" "prototype pollution" >}}** در حالت پیش‌فرض بی‌خطر است و دلیل خوبی است که `.loose()` را روی ورودی عمومی نگذارید. همین payload به سرور هم ۲۰۰ عادی و نتیجه‌ی تمیز داد. این یک بررسی محلی روی همین نسخه بود، نه اثبات امنیتی.

## مقایسه با Go

در Go، `encoding/json` به‌طور پیش‌فرض فیلد ناشناخته را نادیده می‌گیرد مگر روی decoder متد `DisallowUnknownFields` را صدا بزنید، و struct tagهایی مثل `json:"qty"` فقط نام فیلد را می‌گویند و بازه را نمی‌سنجند (مقاله‌ی [فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/)). Zod شکل و قاعده را یک‌جا انجام می‌دهد.

## چند نکته‌ی مهم

- یک بار در مرز اعتبارسنجی کنید و مقدار parse‌شده را جلو ببرید، نه body خام را.
- در اجرای من `z.coerce.number()` رشته‌ی `''` را `0` کرد و `'abc'` رد شد؛ فقط جایی coerce کنید که واقعاً رشته می‌پذیرید.
- issueهای خام را بی‌فکر برنگردانید اگر نام فیلدهای داخلی را لو می‌دهند.
- اعتبارسنجی شکل را می‌سنجد، نه مجوز دسترسی یا قواعد کسب‌وکار.
- major را pin کنید؛ پیام‌های v4 با نسخه‌های قدیمی فرق دارند.

## تمرین

یک schema برای `PATCH /orders` از `Order.partial()` بسازید و کلید ناشناخته را ۴۰۰ کنید. با یک `refine` که حداقل یک فیلد می‌خواهد، آزمایش کنید که body خالی همچنان رد می‌شود.

## قدم بعدی

مقاله‌ی بعدی «worker thread و cluster در Node.js» است.
