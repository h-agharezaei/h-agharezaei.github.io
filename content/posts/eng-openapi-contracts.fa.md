+++
date = '2027-04-04T10:00:00+03:30'
draft = false
title = 'OpenAPI و قرارداد API'
description = 'OpenAPI و قرارداد API در Go: نوشتن spec، lint، سنجیدن پاسخ‌های واقعی با kin-openapi و دیدن شکست تست روی یک تغییر ناسازگار، با اجرای واقعی.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["openapi", "api-contract", "software-engineering", "testing", "go"]
cover = { image = "/images/covers/eng-openapi-contracts.fa.png", alt = "OpenAPI و قرارداد API", hiddenInSingle = true }
+++

در [طراحی API: نسخه‌بندی و pagination](/fa/posts/eng-api-design-versioning-pagination/) تصمیم گرفتیم API چه شکلی داشته باشد. {{< term "api-contract" "قرارداد API" >}} همان تصمیم است به شکل مکتوب و قابل بررسی. بدون آن، عوض شدن نام یک فیلد client را می‌شکند و تا production کسی نمی‌فهمد. خود server از [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) می‌آید و مبانی تست از [تست در Go](/fa/posts/go-testing-basics/). نظرها با **به نظر من** مشخص شده‌اند و بقیه اجرا شده است.

> Go 1.26، Node 20.13.1، یک demo محلی از خودم. یک API کوچک سفارش‌هاست، نه demo پست قبلی: روی آن یکی بنا نکردم.

## یک spec کوچک

یک سند {{< term "openapi" "OpenAPI" >}} نسخه‌ی 3.1 نوشتم با `GET /orders` (cursor و limit، یعنی {{< term "pagination" "pagination" >}})، `POST /orders` و schemaی `Error`. شکل درخواست و پاسخ با {{< term "json-schema" "JSON Schema" >}} نوشته می‌شود:

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

## lint کردن

نسخه‌ی linter را ثابت کردم: `npx --yes @redocly/cli@1.34.5 lint openapi.yaml`. پیش‌نویس اولم معتبر بود، اما linter راضی نبود:

```text
openapi.yaml:
  1:1   error    no-empty-servers        Servers must be present.
  7:5   error    operation-summary       Operation object should contain `summary` field.
  7:5   error    security-defined        Every operation should have security defined on it or on the root level.
  16:7  warning  operation-4xx-response  Operation must have at least one `4XX` response.
  (5 errors and 2 warnings in total)
```

`servers`، summary، یک security scheme از نوع bearer، license و پاسخ `400` برای list را اضافه کردم. اجرای دوم نوشت `Your API description is valid` و دو warning ماند: server روی `localhost` و license بدون `url`/`identifier`. هر دو را نگه داشتم. دومی بعداً مهم می‌شود.

## سنجیدن پاسخ واقعی با spec

یک {{< term "contract-test" "تست قرارداد" >}} handler واقعی را صدا می‌زند و پاسخ را با spec اعتبارسنجی می‌کند. از `github.com/getkin/kin-openapi` نسخه‌ی v0.133.0 استفاده کردم:

```go
err = openapi3filter.ValidateResponse(ctx, &openapi3filter.ResponseValidationInput{
	RequestValidationInput: in, Status: rec.Code, Header: rec.Header(),
	Body: nopCloser{bytes.NewReader(rec.Body.Bytes())},
})
```

سه تست (list، create و create با `qty: 0`) زیر `go test -race` سبز شدند. برای `400` هم سبز است، چون بدنه‌ی خطا با `Error` می‌خواند.

حالا handler را عمداً خراب کنید. عوض کردن tag جیسون `qty` به `quantity`:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": property "qty" is missing
```

عوض کردن `Qty` به string:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": value must be an integer
POST /orders -> 201 violates the contract: response body doesn't match schema #/components/schemas/Order: Error at "/qty": value must be an integer
```

بعد handler را به حالت اول برگرداندم. **به نظر من** این ارزان‌ترین تست پرارزش در یک codebase مبتنی بر API است: یک helper و همه‌ی endpointها.

یک نکته‌ی صادقانه: spec اول من از ویژگی‌های 3.1 استفاده می‌کرد و kin-openapi ردشان کرد: `type: [string, "null"]` پیام `unsupported 'type' value "null"` داد و `identifier` در license پیام `extra sibling fields: [identifier]`. پس هر دو را حذف کردم و `next_cursor` را در آخرین صفحه نمی‌فرستم. قبل از اعتماد به validator، پشتیبانی‌اش از 3.1 را بررسی کنید.

## تغییر ناسازگار

{{< term "breaking-change" "تغییر ناسازگار" >}} تغییری است که client درست‌نوشته را می‌شکند. spec دومی ساختم که در آن `currency` فیلد اجباری درخواست شده، و درخواست قدیمی `{"item":"pen","qty":3}` را با هر دو اعتبارسنجی کردم:

```text
openapi.yaml: err=<nil>
openapi.v2.yaml: err=request body has an error: ... Error at "/currency": property "currency" is missing
```

این همان چیزی است که ابزار diff باید در CI گزارش کند. سعی کردم `oasdiff` را (با نسخه‌ی ثابت) با `go run` اجرا کنم، ولی محیط دستور را رد کرد؛ پس **اجرا نشد** و بررسی بالا جایگزین دستی و کوچک من است. حذف فیلد، فیلد اجباری جدید، نوع محدودتر: ناسازگار. فیلد اختیاری جدید در پاسخ معمولاً نه، هرچند client سخت‌گیر ممکن است گیر کند.

## اول spec یا اول کد

**به نظر من** spec-first به APIهایی می‌خورد که چند مصرف‌کننده دارند: spec قبل از وجود کد review می‌شود. code-first به یک تیم می‌خورد که هر دو طرف را دارد، به شرطی که spec تولید شود و تستی مثل بالا آن را صادق نگه دارد. در هر دو حالت spec فقط وقتی قابل اعتماد است که تستی آن را به کد در حال اجرا ببندد.

## مفاهیمی که اجرا نکردم

- تولید stub سرور یا client (مثلاً با `oapi-codegen`): اجرا نکردم.
- {{< term "consumer-driven-contract" "قرارداد مبتنی بر مصرف‌کننده" >}} با Pact: client‌ها می‌نویسند چه چیزی را استفاده می‌کنند و server راستی‌آزمایی می‌کند. فقط اسمش را می‌آورم.

## چند نکته‌ی مهم

- spec‌ای که تستی آن را نمی‌سنجد، مستنداتی است که کم‌کم از کد جدا می‌شود.
- lint را در {{< term "ci" "CI" >}} بگذارید و نسخه‌ی linter را ثابت کنید.
- پاسخ‌های خطا را هم تست کنید، نه فقط مسیر موفق.
- «spec معتبر است» با «validator همه‌ی ویژگی‌های 3.1 را پشتیبانی می‌کند» دو ادعای جداست.

## تمرین

یک endpoint خودتان را بردارید، schemaاش را بنویسید و یک تست قرارداد اضافه کنید. بعد نام یک فیلد پاسخ را عوض کنید و پیام شکست را بخوانید.

## قدم بعدی

پست بعدی «بدهی فنی» است.
