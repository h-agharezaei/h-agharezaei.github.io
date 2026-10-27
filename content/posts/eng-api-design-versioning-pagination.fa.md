+++
date = '2027-03-26T10:00:00+03:30'
draft = false
title = 'طراحی API: نسخه‌بندی و pagination'
description = 'طراحی API در Go: offset pagination ردیف را تکرار یا حذف می‌کند و cursor نه؛ تغییر افزایشی در برابر شکننده و هدر Sunset، با اجرای واقعی.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["api-design", "pagination", "versioning", "software-engineering", "go"]
cover = { image = "/images/covers/eng-api-design-versioning-pagination.fa.png", alt = "طراحی API: نسخه‌بندی و pagination", hiddenInSingle = true }
+++

بعد از [code review مؤثر](/fa/posts/eng-code-review/) سراغ چیزی می‌رویم که reviewerها بعداً به‌سختی درستش می‌کنند: شکل یک API عمومی. وقتی کلاینت‌ها به آن وابسته شدند، هر اشتباه یک migration است. دو تصمیم بیشتر از همه گاز می‌گیرند: فهرست‌ها چطور {{< term "pagination" "صفحه‌بندی" >}} شوند و API در گذر زمان چطور عوض شود. سرور همان `net/http` ساده است، به سبک [ساخت API با net/http](/fa/posts/go-http-api-stdlib/)؛ یک سرور کوچک تازه نوشتم با ۲۵۰ سفارش در حافظه. نظرها با **به نظر من** مشخص شده‌اند و بقیه با curl روی `127.0.0.1` اجرا شده‌اند.

## offset pagination و تله‌اش

طراحی بدیهی این است: `?page=2&per_page=100` روی `/v1/orders`، جدیدترین اول. صفحه‌ی ۱ را گرفتم، یک سفارش جدید ساختم، بعد صفحه‌ی ۲ را:

```text
page 1: 100 ids [250, 249] ... [152, 151]
(POST /admin/orders  -> new order 251)
page 2: 100 ids [151, 150] ... [53, 52]
```

سفارش ۱۵۱ در هر دو صفحه آمد: ردیف جدید همه را یکی پایین برد. حذف قرینه‌ی همین است. در صفحه‌ی ۱ بعدی (id از ۲۵۱ تا ۱۵۲) سفارش ۲۰۰ را حذف کردم و صفحه‌ی ۲ را گرفتم:

```text
page 2: 100 ids [150, 149] ... [52, 51]
```

سفارش ۱۵۱ هیچ‌وقت نشان داده نشد: بعد از اینکه کلاینت صفحه‌ی اول را خوانده بود، به محدوده‌ی آن صفحه بالا رفت. کلاینتی که «همه‌چیز» را sync می‌کند بی‌صدا یک ردیف را از دست می‌دهد. این خاصیت «N ردیف را رد کن» است، نه باگ کد من، و فقط یک جدول پرتردد لازم دارد.

## keyset pagination

راه‌حل این است که بگویید از کجا ادامه بدهد، نه چند ردیف را رد کند. `/v2/orders` از صفحه‌بندی {{< term "keyset-pagination" "keyset" >}} استفاده می‌کند و یک `next_cursor` مبهم برمی‌گرداند: base64 از `(created_at, id)` آخرین ردیف. رمزگشایی‌شده شامل `{"t":"2027-01-01T02:31:00Z","id":151` و آکولاد بسته است. همان سناریو روی سرور تازه: صفحه‌ی ۱ شامل id از ۲۵۰ تا ۱۵۱ بود، سفارش ۲۵۱ را درج و سفارش ۲۰۰ را حذف کردم و cursor را دنبال کردم:

```text
page 2: 100 ids [150, 149] ... [52, 51]
page 3:  50 ids [50, 49] ... [2, 1]   next_cursor = null
```

نه تکرار، نه جاافتادگی. کلید مرتب‌سازی باید یکتا و پایدار باشد؛ برای همین `id` timestampهای برابر را از هم جدا می‌کند و ترتیب `(created_at desc, id desc)` است. پاسخ هدر `Link` هم دارد؛ با `limit=2` صفحه‌ی اول این را برگرداند:

```text
Link: </v2/orders?cursor=eyJ0Ijoi...&limit=2>; rel="next"
```

cursor را مبهم نگه دارید تا بعداً محتوایش را عوض کنید. هزینه‌اش این است که کلاینت نمی‌تواند مستقیم به صفحه‌ی ۷ برود.

## سقف و ورودی بد

`limit` بدون سقف کلید قطع سرویس است. مال من روی ۱۰۰ سقف دارد و بقیه را با ۴۰۰ و پیام رد می‌کند:

```text
GET /v1/orders?per_page=1000  -> 400 {"error":"page must be >= 1 and per_page 1..100"}
GET /v2/orders?limit=abc      -> 400 {"error":"limit must be an integer from 1 to 100"}
GET /v2/orders?cursor=zzz     -> 400 {"error":"invalid cursor"}
```

**به نظر من** رد کردن بهتر از بریدن بی‌صدا است: کلاینت می‌فهمد فرضش غلط بود. شمارش `total` بحث جدایی است. شمارش دقیق یعنی یک query دوم برای هر صفحه که روی جدول بزرگ معمولاً ارزان نیست؛ اندازه نگرفتم. دموی من `total` ندارد.

## گزینه‌های نسخه‌بندی

هر سه کار می‌کنند؛ این **نظر من** است.

- مسیر URL (`/v1/`): در log دیده می‌شود، route و امتحان آن با curl آسان است.
- هدر (`Accept: application/vnd.example.v2+json` یا هدر سفارشی): URL تمیز، اما cache و debug سخت‌تر.
- query parameter (`?version=2`): ساده؛ وقتی نباشد به یک پیش‌فرض نیاز دارید.

من مسیر را انتخاب می‌کنم. مهم‌تر از مکانیزم این است که کم به نسخه‌ی جدید احتیاج پیدا کنید.

## افزایشی در برابر شکننده

اضافه‌کردن فیلد معمولاً امن است؛ حذف یا تغییر نام نه. decoder سخت‌گیر در برابر {{< term "tolerant-reader" "tolerant reader" >}} روی سه پاسخ برای یک سفارش:

```text
same     {"customer":"c007","id":7,"status":"paid"}
  strict:   ok
  tolerant: ok
added    {"currency":"EUR","customer":"c007","id":7,"status":"paid"}
  strict:   err=json: unknown field "currency"
  tolerant: ok
removed  {"customer":"c007","id":7}
  strict:   err=missing field status
  tolerant: Status:"" err=<nil>
```

decoder سخت‌گیر (`DisallowUnknownFields`) با یک فیلد اضافه می‌شکند. نوع بردبار زنده می‌ماند اما فیلد حذف‌شده را بی‌صدا `""` می‌خواند که بدتر است. پس: کلاینت‌ها بردبار باشند، سرور حذف و تغییر نام را شکننده حساب کند، و تغییر معنا (همان نام فیلد با واحد جدید) بدترین تغییر شکننده است چون هیچ decoderای متوجه نمی‌شود.

## Deprecation و Sunset

endpoint قدیمی offset حالا می‌گوید چه در راه است:

```text
Deprecation: true
Link: </v2/orders>; rel="successor-version"
Sunset: Wed, 31 Dec 2031 23:59:59 GMT
```

تاریخ ساختگی است. طبق RFC 8594 هدر `Sunset` تاریخ HTTP را می‌گوید که بعد از آن منبع ممکن است پاسخ ندهد. گمان می‌کنم RFC جدیدتری `Deprecation` را با مقدار تاریخ تعریف کرده، نه `true`؛ بررسی نکردم، پیش از کپی‌کردن خودتان ببینید. ثبت کنید کدام کلاینت‌ها هنوز مسیر قدیمی را صدا می‌زنند.

## تلاش مجدد و idempotency

pagination فقط می‌خواند و تکرارش امن است. برای POSTها یک کلید از سمت کلاینت بپذیرید تا retry دو سفارش نسازد؛ ایده همان {{< term "idempotency" "idempotency" >}} در [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) است. اینجا نساختمش.

## چند نکته‌ی مهم

- برای هر فهرستی که حین خواندن بزرگ یا عوض می‌شود keyset بگیرید؛ offset فقط برای فهرست کوچک و ثابت.
- معنای یک فیلد را در جا عوض نکنید؛ فیلد تازه اضافه کنید.
- deprecation بدون تاریخ و جانشین شایعه است.

## تمرین

دو سناریو را روی endpoint فهرست خودتان اجرا کنید: بین صفحه‌ی ۱ و ۲ یک ردیف درج و یکی حذف کنید. آیا idای تکرار یا گم می‌شود؟ اگر بله، بنویسید نسخه‌ی keyset بر چه اساسی مرتب می‌کرد.

## قدم بعدی

پست بعدی «OpenAPI و قرارداد API» است.
