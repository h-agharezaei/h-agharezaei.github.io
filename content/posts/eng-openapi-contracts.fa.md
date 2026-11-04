+++
date = '2027-04-04T10:00:00+03:30'
draft = false
title = 'OpenAPI و قرارداد API'
contentType = 'tutorial'
description = 'OpenAPI و قرارداد API در Go: نوشتن spec، lint، سنجیدن پاسخ‌های واقعی با kin-openapi و دیدن شکست تست روی یک تغییر ناسازگار، با اجرای واقعی.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["openapi", "api-contract", "software-engineering", "testing", "go"]
cover = { image = "/images/covers/eng-openapi-contracts.fa.png", alt = "OpenAPI و قرارداد API", hiddenInSingle = true }
+++

یک اپلیکیشن موبایل را تصور کنید که یک سال است برای server درخواستی مثل `{"item":"pen","qty":3}` می‌فرستد. یک روز تیم server تصمیم می‌گیرد هر سفارش `currency` هم داشته باشد و آن را فیلد اجباری می‌کند. به تیم اپلیکیشن چیزی نمی‌گویند، چون کسی این را «تغییر ناسازگار» نمی‌دانست. اپلیکیشن در محیط تست درست کار می‌کند، چون آن‌جا دوباره اجرا نشده، و درست لحظه‌ای که server جدید در production بالا می‌آید خطا می‌گیرد.

مشکل از باگ یکی از دو طرف نیست. دو طرف فقط تصویر متفاوتی از شکل API در ذهن داشتند و جایی نبود که این تصویر نوشته و بررسی شود. {{< term "api-contract" "قرارداد API" >}} همان جاست: توصیفی مکتوب از آنچه server می‌پذیرد و برمی‌گرداند، به شکلی که یک برنامه بتواند آن را بسنجد. قرارداد، شکل مکتوب تصمیم‌های [طراحی API: نسخه‌بندی و pagination](/fa/posts/eng-api-design-versioning-pagination/) است. server این پست یک server کوچک به سبک [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است و مبانی تست در [تست در Go](/fa/posts/go-testing-basics/) آمده. نظرهای خودم را با **به نظر من** مشخص کرده‌ام. بقیه‌ی چیزها اجرا شده است.

> demo یک API کوچک سفارش‌هاست که برای همین پست با Go نوشتم. در اجرای اولیه با Go 1.26 و Node 20.13.1 اجرایش کردم و برای این ویرایش تست‌های Go را با Go 1.27.3 دوباره اجرا کردم. این demo همان demo پست قبلی نیست: روی آن یکی بنا نکردم. این بار نتوانستم linter را که با Node اجرا می‌شود دوباره اجرا کنم (دانلودش به timeout خورد)، پس خروجی lint در پایین از اجرای اولیه است.

## یک spec کوچک

قالبی که برای قرارداد به کار می‌برم {{< term "openapi" "OpenAPI" >}} است؛ یک روش استاندارد برای توصیف یک API روی HTTP در یک فایل YAML یا JSON. این فایل مسیرها، متدها، محتوای لازم هر درخواست و شکل هر پاسخ را فهرست می‌کند. نسخه‌ی 3.1 را برای سه کار نوشتم: `GET /orders` که یک صفحه از سفارش‌ها را با cursor و limit برمی‌گرداند (همان {{< term "pagination" "pagination" >}})، `POST /orders` برای ساختن سفارش، و یک شکل `Error` برای خطاها.

شکل درخواست‌ها و پاسخ‌ها با {{< term "json-schema" "JSON Schema" >}} نوشته می‌شود؛ زبانی کوچک برای گفتن این‌که «این باید یک شیء باشد، با این فیلدها و این نوع‌ها». schema یک صفحه از نتیجه‌ها این است:

```yaml
    OrderPage:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Order" }
        next_cursor: { type: string }
```

این‌طور بخوانیدش: یک صفحه یک شیء است. حتماً باید `items` داشته باشد، یعنی فهرستی از `Order`. می‌تواند یک رشته‌ی `next_cursor` هم داشته باشد. `{ $ref: ... }` فقط ارجاع به schema دیگری در همین فایل است.

## lint کردن

spec هم یک فایل معمولی است و می‌تواند اشتباه یا ناقص باشد. linter آن را می‌خواند و از چیزهایی ایراد می‌گیرد که استاندارد اجازه‌شان را می‌دهد ولی یک spec خوب نباید جا بیندازدشان. من linter شرکت Redocly را با نسخه‌ی ثابت استفاده کردم: `npx --yes @redocly/cli@1.34.5 lint openapi.yaml`. پیش‌نویس اولم معتبر بود، اما linter راضی نبود. این چهار تا از ایرادهایش است:

```text
openapi.yaml:
  1:1   error    no-empty-servers        Servers must be present.
  7:5   error    operation-summary       Operation object should contain `summary` field.
  7:5   error    security-defined        Every operation should have security defined on it or on the root level.
  16:7  warning  operation-4xx-response  Operation must have at least one `4XX` response.
  (5 errors and 2 warnings in total)
```

به زبان ساده: spec نگفته بود server کجاست، برای عملیات summary ننوشته بود، نگفته بود درخواست‌ها چطور احراز هویت می‌شوند، و برای list هیچ پاسخ خطایی توصیف نکرده بود. `servers`، summary، یک security scheme از نوع bearer، license و پاسخ `400` برای list را اضافه کردم. اجرای دوم نوشت `Your API description is valid`، با دو warning باقی‌مانده: server روی `localhost` و license بدون `url` و `identifier`. هر دو را نگه داشتم. دومی کمی بعد مهم می‌شود.

## سنجیدن پاسخ واقعی با spec

تا این‌جا spec فقط متن است. وقتی چیزی server واقعی را با آن بسنجد، تازه قرارداد می‌شود. {{< term "contract-test" "تست قرارداد" >}} همین کار را می‌کند: handler واقعی را صدا می‌زند، پاسخ را می‌گیرد و با spec اعتبارسنجی می‌کند. من از کتابخانه‌ی Go با نام `github.com/getkin/kin-openapi` نسخه‌ی v0.133.0 استفاده کردم. فراخوانی مهم این است:

```go
err = openapi3filter.ValidateResponse(ctx, &openapi3filter.ResponseValidationInput{
	RequestValidationInput: in, Status: rec.Code, Header: rec.Header(),
	Body: nopCloser{bytes.NewReader(rec.Body.Bytes())},
})
```

این تابع status و header و body را که handler تولید کرده می‌گیرد، پاسخ متناظر را در spec پیدا می‌کند و اگر با هم نخوانند خطا برمی‌گرداند. سه تست (list، create و create با `qty: 0`) زیر `go test -race` سبز شدند. سبز بودن تست آخر شاید عجیب باشد. این تست `qty: 0` می‌فرستد، server با `400` جواب می‌دهد و بدنه‌ی آن `400` شکل `Error` را دارد. spec این را اجازه می‌دهد، پس قرارداد رعایت شده است.

تستی که سبز می‌شود تا وقتی ندیده‌ام قرمز هم می‌شود چیز زیادی ثابت نمی‌کند. برای همین handler را عمداً خراب کردم. اول tag جیسون `qty` را به `quantity` عوض کردم؛ دقیقاً کاری که یک تغییر نام بی‌دقت می‌کند:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": property "qty" is missing
```

پیام می‌گوید کدام درخواست شکست خورده، با کدام schema سنجیده شده و مشکل کدام فیلد است. بعد نوع `Qty` را از عدد به string عوض کردم:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": value must be an integer
POST /orders -> 201 violates the contract: response body doesn't match schema #/components/schemas/Order: Error at "/qty": value must be an integer
```

این‌جا دو endpoint هم‌زمان شکست می‌خورند، چون هر دو یک `Order` برمی‌گردانند. بعد از آن handler را به حالت اول برگرداندم. **به نظر من** این ارزان‌ترین تست پرارزش در یک codebase مبتنی بر API است: یک تابع کمکی و همه‌ی endpointها پوشش داده می‌شوند.

یک نکته‌ی صادقانه. spec اولم از دو ویژگی 3.1 استفاده می‌کرد و kin-openapi ردشان کرد. `type: [string, "null"]` پیام `unsupported 'type' value "null"` داد و `identifier` در license پیام `extra sibling fields: [identifier]` (همان warningی که پیش‌تر نگه داشتم). پس هر دو را حذف کردم و `next_cursor` را در آخرین صفحه اصلاً نمی‌فرستم. پیش از اعتماد به یک validator بررسی کنید چقدر از نسخه‌ی spec شما را واقعاً پشتیبانی می‌کند.

## تغییر ناسازگار

حالا برگردیم به داستان اول. {{< term "breaking-change" "تغییر ناسازگار" >}} تغییری است که clientی را می‌شکند که درست و مطابق قرارداد قدیمی نوشته شده بود. برای دیدنش spec دومی ساختم که در آن `currency` فیلد اجباری درخواست است. بعد درخواست قدیمی `{"item":"pen","qty":3}` را با هر دو spec اعتبارسنجی کردم:

```text
openapi.yaml: err=<nil>
openapi.v2.yaml: err=request body has an error: doesn't match schema #/components/schemas/NewOrder: Error at "/currency": property "currency" is missing
```

spec قدیمی درخواست را می‌پذیرد (`err=<nil>` یعنی خطایی نیست). spec جدید ردش می‌کند و دقیقاً می‌گوید چرا. این همان چیزی است که یک ابزار diff باید پیش از merge در {{< term "ci" "CI" >}} گزارش کند. سعی کردم `oasdiff`، ابزاری که برای همین کار ساخته شده، را با نسخه‌ی ثابت و با `go run` اجرا کنم، ولی محیط من دستور را رد کرد؛ پس **اجرا نشد**. بررسی بالا جایگزین دستی و کوچک من است.

با همین منطق: حذف یک فیلد، افزودن فیلد اجباری جدید و محدودتر کردن یک نوع، ناسازگارند. فیلد اختیاری جدید در پاسخ معمولاً ناسازگار نیست، هرچند یک client خیلی سخت‌گیر ممکن است سر فیلدی که نمی‌شناسد گیر کند.

## اول spec یا اول کد

برای داشتن spec دو راه هست. در spec-first اول spec را می‌نویسید و کد از آن پیروی می‌کند. در code-first اول کد را می‌نویسید و spec را از آن تولید می‌کنید. **به نظر من** spec-first به APIهایی می‌خورد که چند مصرف‌کننده دارند، چون spec پیش از وجود کد review می‌شود. code-first به تیمی می‌خورد که هر دو طرف را دارد، به شرطی که spec تولید شود و تستی مثل تست بالا آن را صادق نگه دارد. در هر دو حالت spec فقط وقتی قابل اعتماد است که تستی آن را به کد در حال اجرا ببندد.

## مفاهیمی که اجرا نکردم

- تولید stub سرور یا client از روی spec (مثلاً با `oapi-codegen`): اجرا نکردم.
- {{< term "consumer-driven-contract" "قرارداد مبتنی بر مصرف‌کننده" >}} با Pact: در آن clientها می‌نویسند واقعاً چه چیزی را استفاده می‌کنند و server راستی‌آزمایی می‌کند که هنوز آن را فراهم می‌کند. فقط اسمش را می‌آورم.

## قرارداد چطور از کد جدا می‌افتد

- spec‌ای که هیچ تستی آن را نمی‌سنجد، مستنداتی است و مستندات کم‌کم از کد جدا می‌شود. با یک تست آن را به کد ببندید.
- linter را در {{< term "ci" "CI" >}} بگذارید و نسخه‌اش را ثابت کنید، تا یک نسخه‌ی تازه‌ی linter ناگهان pipeline شما را قرمز نکند.
- پاسخ‌های خطا را هم تست کنید، نه فقط مسیر موفق. clientها به بدنه‌ی خطا هم به اندازه‌ی بدنه‌ی موفق تکیه می‌کنند.
- «spec معتبر است» با «validator من همه‌ی ویژگی‌های 3.1 را پشتیبانی می‌کند» دو ادعای جداست. یک validator می‌تواند spec را بپذیرد و قسمتی از آن را نادیده بگیرد.

## تمرین

یک endpoint خودتان را بردارید، schemaاش را بنویسید و یک تست قرارداد اضافه کنید. بعد نام یک فیلد پاسخ را عوض کنید و پیام شکست را بخوانید.

## قدم بعدی

پست بعدی «بدهی فنی» است. صادق نگه داشتن یک قرارداد کار کوچک و قابل بررسی است. بدهی فنی سؤال بزرگ‌تری می‌پرسد: هزینه در کل یک repo کجا جمع می‌شود و چطور اندازه‌اش بگیریم؟
