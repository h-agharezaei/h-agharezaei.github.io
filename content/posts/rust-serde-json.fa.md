+++
date = '2027-01-15T10:00:00+03:30'
draft = false
title = 'Serde و JSON در Rust'
description = 'کار با serde و serde_json در Rust: derive کردن Serialize و Deserialize، attributeهای rename و default، سه شکل enum، Value و json! و پیام‌های خطای واقعی.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "serde", "json", "intermediate"]
cover = { image = "/images/covers/rust-serde-json.fa.png", alt = "Serde و JSON در Rust", hiddenInSingle = true }
+++

مشتری‌ای برای سرویس شما این بدنه را می‌فرستد: `{"name": "Roham", "age": "thirty"}`. کد شما انتظار دارد `age` عدد باشد. چه اتفاقی می‌افتد؟ در یک زبان پویا ممکن است آن رشته بی‌صدا از سه لایه‌ی کد رد شود و جایی دور از ورودی خودش بترکد. در Rust دلتان عکس این را می‌خواهد: JSON همان دم در بررسی شود و یا یک `User` درست تحویل بگیرید یا یک خطای روشن، و چیزی میان این دو نباشد.

کار **serde** همین است، کتابخانه‌ی استاندارد serialization در Rust. *سریالایز* یعنی تبدیل یک مقدار داخل حافظه به متن یا بایت‌هایی که بشود ذخیره یا ارسال کرد، و *دیسریالایز* راه برگشت است. تقریباً هر سرویسی JSON حرف می‌زند، پس این مقاله جایی است که نوع‌های Rust ما با دنیای بیرون روبه‌رو می‌شوند. بعد از [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) می‌آید. اگر هم‌ارز Go را خوانده باشید، [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/)، شکلش آشناست و همان payload ‏`User` را برای مقایسه برداشته‌ام.

> همه‌چیز را با Rust نسخه‌ی 1.90، `serde` نسخه‌ی 1.0.229 (با feature به نام `derive`) و `serde_json` نسخه‌ی 1.0.154 اجرا کرده‌ام. خروجی‌ها از اجرای واقعی یک پروژه‌ی demo محلی با شش برنامه‌ی کوچک کپی شده‌اند و برای این نسخه‌ی مقاله همه را دوباره اجرا کردم. هشدارهای کامپایلر درباره‌ی فیلدهای استفاده‌نشده را از خروجی‌ها حذف کرده‌ام.

## ایده: شکل داده را یک بار توصیف کنید

serde کار را دو نیم می‌کند. نیمه‌ی اول *نوع داده‌ی شماست*: یک بار می‌گویید یک `User` چه شکلی دارد. نیمه‌ی دوم *فرمت* است، در اینجا JSON، که crate ‏`serde_json` آن را می‌دهد. خود serde از JSON چیزی نمی‌داند و `serde_json` هم از نوع‌های شما. این دو از طریق دو {{< term "trait" "trait" >}} به نام‌های `Serialize` و `Deserialize` به هم می‌رسند.

تقریباً هیچ‌وقت این trait‌ها را با دست نمی‌نویسید. `#[derive(Serialize, Deserialize)]` را روی struct می‌گذارید و یک *ماکروی derive* موقع کامپایل و با نگاه به فیلدهای شما پیاده‌سازی را می‌نویسد. `User` از demo این است:

```rust
#[derive(Debug, Serialize, Deserialize)]
struct User {
    name: String,
    age: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    email: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    tags: Vec<String>,
    #[serde(skip)]
    password: String,
}
```

`name` و `age` فیلدهای ساده‌اند. سه‌تای دیگر `#[serde(...)]` دارند، دستورهای کوچکی برای ماکروی derive. کمی بعد یکی‌یکی توضیحشان می‌دهم؛ اول خروجی. `serde_json::to_string(&u)` برای کاربری بدون ایمیل و تگ این را می‌دهد:

```text
{"name":"Roham","age":30}
```

سه فیلد غایب‌اند. `email` و `tags` به‌خاطر `skip_serializing_if` نیامده‌اند (خالی‌اند) و `password` همیشه نمی‌آید. وقتی ایمیل و تگ‌ها پر باشند، `to_string_pretty` خروجی تورفته می‌دهد (مثل `MarshalIndent` در Go):

```text
{
  "name": "Roham",
  "age": 30,
  "email": "r@example.com",
  "tags": [
    "rust",
    "backend"
  ]
}
```

باز هم از `password` خبری نیست. حالا attribute‌ها، یکی‌یکی:

- `skip_serializing_if = "Option::is_none"` وقتی مقدار `None` است کلید را کلاً نمی‌نویسد، به‌جای اینکه `"email": null` بنویسد.
- `default` یعنی اگر کلید در ورودی نبود، مقدار پیش‌فرض نوع (اینجا یک `Vec` خالی) را بگذار. بدون آن، نبودن `tags` خطا می‌شد.
- `skip` فیلد را در هر دو جهت کنار می‌گذارد. موقع خواندن، `password` از ورودی گرفته نمی‌شود و با `String::default()`، یعنی رشته‌ی خالی، پر می‌شود. پس نوع فیلد باید `Default` داشته باشد.

خواندن با `from_str` انجام می‌شود و نوع مقصد به serde می‌گوید چه انتظاری داشته باشد:

```rust
let back: User = serde_json::from_str(&serde_json::to_string(&u)?)?;
let min: User = serde_json::from_str(r#"{"name":"A","age":1}"#)?;
```

```text
User { name: "Roham", age: 30, email: Some("r@example.com"), tags: ["rust", "backend"], password: "" }
User { name: "A", age: 1, email: None, tags: [], password: "" }
```

خط اول رفت‌وبرگشت است: آنچه رفت برگشت، به‌جز `password: ""` که هیچ‌وقت نوشته نشده بود. خط دوم یک ورودی حداقلی است: `email` یک `Option` است پس نبودنش یعنی `None`، و `tags` که `default` دارد در غیاب ورودی لیست خالی می‌شود.

برای فایل و stream هم `to_writer(File::create(..)?, &u)` و `from_reader(BufReader::new(File::open(..)?))` هست. demo کاربر را در یک فایل موقت می‌نویسد و می‌خواند و `User` چاپ‌شده با نمونه‌ی بالا یکی است. فایل را در `BufReader` بپیچید، چون `from_reader` در تکه‌های کوچک زیاد می‌خواند.

## وقتی نام‌های JSON با فیلدهای شما نمی‌خواند

JSON‌ای که دیگران می‌نویسند به‌ندرت به سبک Rust است. ممکن است فیلد `orderId` باشد و سبک Rust بگوید `order_id`، یا API اسمش را `customer` گذاشته باشد و struct شما `customer_name`. attribute‌ها بی‌آنکه Rust شما زشت شود این را حل می‌کنند:

```rust
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Order {
    order_id: u64,
    #[serde(rename = "customer")]
    customer_name: String,
    #[serde(alias = "qty")]
    quantity: u32,
    #[serde(default)]
    is_gift: bool,
    #[serde(flatten)]
    shipping: Shipping, // struct با city و zip
}
```

demo یک سفارش را سریالایز می‌کند، بعد رشته‌ی `{"orderId":8,"customer":"X","qty":5,"city":"Rasht","zip":"9"}` را می‌خواند:

```text
{"orderId":7,"customer":"Roham","quantity":2,"isGift":false,"city":"Tehran","zip":"1234"}
Order { order_id: 8, customer_name: "X", quantity: 5, is_gift: false, shipping: Shipping { city: "Rasht", zip: "9" } }
```

در خط اول، `rename_all` همه‌ی نام‌ها را camelCase کرد، `rename` یک نام را جدا عوض کرد (`customer`)، و `flatten` فیلدهای `shipping` را به همان شیء بالا آورد، پس `city` و `zip` کنار `orderId` نشسته‌اند. در خط دوم ورودی `qty` داشت: `alias` به فیلد اجازه می‌دهد موقع خواندن این نام را هم بپذیرد. `isGift` نبود و `default` آن را `false` کرد.

## enum: سه راه برای نوشتن یک مقدار

یک enum در Rust می‌تواند در هر variant داده‌ی متفاوتی داشته باشد و JSON چنین چیزی ندارد. پس serde باید یک نمایش انتخاب کند و این انتخاب جزو قرارداد API شما می‌شود. سه variant را در نظر بگیرید: `Created { id }` و `Paid { id, amount }` و یک `Cancelled` ساده. این‌ها با سه attribute ممکن:

```text
default:    {"Created":{"id":1}}   {"Paid":{"id":1,"amount":9.5}}   "Cancelled"
tag="type": {"type":"Created","id":1}   {"type":"Paid","id":1,"amount":9.5}   {"type":"Cancelled"}
untagged:   {"id":1}   {"id":1,"amount":9.5}   null
```

(demo هر مقدار را در یک خط جدا چاپ می‌کند؛ من سه‌تای هر نوع را در یک خط گذاشته‌ام.)

- **Externally tagged** پیش‌فرض است. داده در یک شیء پیچیده می‌شود که تنها کلیدش نام variant است. variant بدون داده یک رشته‌ی ساده می‌شود.
- **Internally tagged** با `#[serde(tag = "type")]` نام variant را به‌شکل یک فیلد داخل خود شیء می‌گذارد. معمولاً انتظار clientهای API برای event‌ها همین است.
- **Untagged** فقط داده را می‌نویسد و هیچ نامی نه. برای همین `Cancelled` که داده ندارد `null` می‌شود. موقع خواندن serde variant‌ها را به همان ترتیبی که تعریف شده‌اند امتحان می‌کند و اولین مناسب را برمی‌دارد.

این قاعده‌ی آخر نتیجه‌ای دارد که راحت از آن غافل می‌شوید. شاید انتظار داشته باشید خواندن `{"id":2,"amount":3.0}` با enum از نوع untagged، `Paid` بدهد چون ورودی `amount` دارد. خروجی واقعی این است:

```text
Created { id: 2 }
```

`Created` اول تعریف شده و فقط به `id` نیاز دارد؛ `amount` اضافه بی‌صدا نادیده گرفته می‌شود و variant اول از قبل جور است. ورودی `{"id":2}` هم `Created` می‌دهد. یعنی در این enum از JSON هرگز به `Paid` نمی‌رسید. enum‌های untagged فقط وقتی درست‌اند که variantها با هم اشتباه نشوند، یا variant دقیق‌تر اول بیاید. (شکل internally tagged این مشکل را ندارد: `{"type":"Paid","id":2,"amount":3.0}` همان `Paid { id: 2, amount: 3.0 }` را می‌دهد.)

پیام خطا هم بین نمایش‌ها فرق می‌کند:

```text
unknown variant `Refunded`, expected one of `Created`, `Paid`, `Cancelled`
missing field `type`
data did not match any variant of untagged enum Untagged
```

اولی برای enum از نوع internally tagged و مقداری از `type` است که کسی نمی‌شناسد؛ حتی مقدارهای مجاز را هم می‌شمارد. دومی برای همان enum است وقتی کلید `type` اصلاً نیست. سومی برای enum از نوع untagged و ورودی `{"foo":1}` است و بی‌فایده‌ترین آن‌هاست: موقعیت درستی ندارد (خط ۰، ستون ۰)، چون serde همه‌ی variant‌ها را امتحان کرده و جای مشخصی برای سرزنش ندارد. این بهای `untagged` است.

## وقتی شکل داده را نمی‌دانید: Value و json!

گاهی JSON شکل ثابتی ندارد یا فقط یک فیلدش را لازم دارید. برایش `serde_json::Value` هست، یک enum که هر JSON را نگه می‌دارد: null، bool، عدد، رشته، آرایه یا شیء. اگر با کلیدی که وجود ندارد اندیس بزنید panic نمی‌کند و `Value::Null` می‌دهد. ماکروی `json!` مقدارها را درجا می‌سازد:

```rust
let mut v: Value = serde_json::from_str(r#"{"id":7,"name":"x","ok":true,"list":[1,2.5],"nested":{"a":null}}"#)?;
println!("missing: {}", v["nope"]);
v["name"] = json!("changed");
v["extra"] = json!({"n": 1, "tags": ["a", "b"]});
println!("{v}");
```

```text
missing: null
{"extra":{"n":1,"tags":["a","b"]},"id":7,"list":[1,2.5],"name":"changed","nested":{"a":null},"ok":true}
```

کلید غایب `null` چاپ کرد. خط دوم کل مقدار بعد از دو انتساب است. ببینید کلیدها به ترتیب حروف آمده‌اند، نه ترتیبی که من نوشتم: شیء پشت `Value` بر اساس کلید مرتب است، مگر اینکه feature ‏`preserve_order` از `serde_json` را روشن کنید. (`map[string]any` در Go هم با کلیدهای مرتب نوشته می‌شود.)

`Value` راحت است ولی هر دسترسی به آن می‌تواند موقع اجرا شکست بخورد؛ فقط برای بخش‌های واقعاً پویای payload از آن استفاده کنید و بقیه را struct با نوع بدهید.

## با عددها باید دقت کرد

JSON فقط یک نوع عدد دارد ولی Rust چندتا. `Value` عدد صحیح و اعشاری را جدا نگه می‌دارد. برای ورودی `[1, 1.0, 18446744073709551615, 9223372036854775808]` demo از هر عضو می‌پرسد چیست:

```text
1: is_i64=true is_u64=true is_f64=false
1.0: is_i64=false is_u64=false is_f64=true
18446744073709551615: is_i64=false is_u64=true is_f64=false
9223372036854775808: is_i64=false is_u64=true is_f64=false
```

`1` صحیح است و هم در `i64` جا می‌شود هم `u64`. `1.0` اعشاری است و فقط اعشاری. دو عدد بزرگ فقط در `u64` جا می‌شوند و رقم‌هایشان دقیق است. در Go اگر داخل `map[string]any` بخوانید هر چهار تا `float64` می‌شوند و بزرگ‌ترین‌شان دقتش را از دست می‌دهد.

نوشتن اعشاری هم تمایز را نگه می‌دارد: `(i64::MIN, u64::MAX, 1.0, 0.1, 1e21)` به‌شکل `[-9223372036854775808,18446744073709551615,1.0,0.1,1e+21]` نوشته می‌شود، پس `1.0` همان `1.0` می‌ماند.

وقتی مقصد نوع مشخص است سخت‌گیری می‌شود. `i64` خواستن و `1.0` دادن شکست می‌خورد، ولی `f64` خواستن و `1` دادن درست است:

```text
Err(Error("invalid type: floating point `1.0`, expected i64", line: 1, column: 3))
Ok(1.0)
Err(Error("invalid value: integer `300`, expected u8", line: 1, column: 3))
Err(Error("invalid value: integer `-1`, expected u8", line: 1, column: 2))
Ok("null")
```

سه خط آخر می‌گویند: `300` در `u8` جا نمی‌شود، `-1` هم نه، و سریالایز `NaN` (یعنی «عدد نیست») شکست نمی‌خورد و `null` می‌نویسد، چون JSON راهی برای نوشتنش ندارد. خلاصه اینکه عدد صحیحِ بزرگ‌تر از ظرفیت خطاست، نه سرریز بی‌صدا.

## خطاهایی که واقعاً می‌بینید

حالا برگردیم به سؤال ابتدای مقاله. هشت ورودی برنامه‌ی `errors` را ببینید، که همه با `struct User { name: String, age: u8 }` خوانده می‌شوند:

```text
trailing comma: trailing comma at line 1 column 14  [line=1 col=14 classify=Syntax]
truncated: EOF while parsing an object at line 1 column 12  [line=1 col=12 classify=Eof]
multiline: key must be a string at line 4 column 3  [line=4 col=3 classify=Syntax]
missing field: missing field `age` at line 1 column 12  [line=1 col=12 classify=Data]
wrong type: invalid type: string "thirty", expected u8 at line 1 column 26  [line=1 col=26 classify=Data]
overflow u8: invalid value: integer `300`, expected u8 at line 1 column 21  [line=1 col=21 classify=Data]
negative u8: invalid value: integer `-1`, expected u8 at line 1 column 20  [line=1 col=20 classify=Data]
unknown ok: ok User { name: "x", age: 3 }
```

payload ابتدای مقاله همان خط `wrong type` است: خطا می‌گوید چه پیدا کرد (رشته‌ی `"thirty"`)، چه می‌خواست (`u8`) و کجا (خط ۱، ستون ۲۶). هر خطا `line()` و `column()` و `classify()` هم دارد که می‌گوید مشکل از نوع `Syntax` است (JSON معتبر نیست)، `Data` (JSON معتبر ولی محتوا غلط)، `Eof` (متن زود تمام شد) یا `Io`. یک handler وب می‌تواند از آن برای جواب ۴۰۰ با پیام مفید استفاده کند.

دو فرق با Go را باید دانست. در Go فیلد غایب بی‌صدا صفر می‌ماند؛ در serde خطاست مگر اینکه فیلد `Option` باشد یا `default` داشته باشد. فیلد ناشناخته، مثل `nickname` در خط آخر، در هر دو به‌طور پیش‌فرض نادیده گرفته می‌شود. اگر ترجیح می‌دهید رد شود، `#[serde(deny_unknown_fields)]` را روی struct بگذارید و همان ورودی این خطا را می‌دهد:

```text
unknown field `nickname`, expected `name` or `age` at line 1 column 30
```

## یک ابزار دیگر: دیسریالایزر سفارشی

بعضی API‌ها یک‌دست نیستند: یک id جایی `5` می‌آید و جای دیگر `"5"`. با `deserialize_with` می‌شود این را سامان داد، تابعی که فیلد را به روش خودتان می‌خواند. اینجا از یک enum خصوصی و کوچک از نوع untagged استفاده می‌کند، یعنی اول عدد را امتحان می‌کند بعد رشته را:

```rust
#[derive(Deserialize)]
#[serde(untagged)]
enum StrOrNum { Num(u64), Str(String) }

fn id_from_str_or_num<'de, D: Deserializer<'de>>(d: D) -> Result<u64, D::Error> {
    match StrOrNum::deserialize(d)? {
        StrOrNum::Num(n) => Ok(n),
        StrOrNum::Str(s) => s.trim().parse().map_err(serde::de::Error::custom),
    }
}
// روی فیلد: #[serde(deserialize_with = "id_from_str_or_num")] id: u64
```

(`'de` یک lifetime است که deserializer را به متن ورودی می‌بندد؛ می‌توانید این امضا را همان‌طور که هست کپی کنید.) demo چهار ورودی به آن می‌دهد:

```text
{"id":5} -> Item { id: 5 }
{"id":"6"} -> Item { id: 6 }
{"id":"abc"} -> error: invalid digit found in string at line 1 column 12
{"id":true} -> error: data did not match any variant of untagged enum StrOrNum at line 1 column 11
```

هم `5` هم `"6"` یک `u64` می‌شوند. رشته‌ی `"abc"` داخل `parse()` خودمان شکست می‌خورد و پیامش از راه `Error::custom` رد می‌شود. مقدار boolean به هیچ‌کدام از دو variant نمی‌خورد و دوباره همان خطای مبهم untagged را می‌گیریم، این بار با موقعیت.

## جاهایی که serde گاز می‌گیرد

- **نمایش enum را عمداً انتخاب کنید.** پیش‌فرض، externally tagged، چیزی نیست که بیشتر clientهای REST انتظار دارند؛ `tag = "type"` معمولاً همان است.
- **`untagged` به ترتیب حساس است و خطاهایش مبهم‌اند.** همان‌طور که دیدیم، variant کلی‌تری که اول تعریف شود ورودی variant دقیق‌تر را می‌بلعد.
- **`skip` به `Default` نیاز دارد** روی نوع فیلد، چون خواندن باید باز هم مقداری بسازد.
- **struct با نوع را ترجیح بدهید.** `Value` را فقط برای بخش واقعاً پویا بگذارید؛ هر دسترسی روی آن می‌تواند موقع اجرا شکست بخورد.
- **عددی که جا نشود خطاست،** نه سرریز یا برش. این خوب است، ولی مطمئن شوید نوع‌های صحیح API شما با آنچه clientها واقعاً می‌فرستند جور است.

## تمرین

۱. روی یک enum خودتان `#[serde(tag = "type")]` بگذارید و JSON را با حالت پیش‌فرض مقایسه کنید.
۲. variantهای یک enum از نوع untagged را طوری جابه‌جا کنید که variant دقیق‌تر اول بیاید و دوباره `{"id":2,"amount":3.0}` را بخوانید.
۳. یک struct را طوری بسازید که فیلد ناشناخته را رد کند و خطای غلط‌املایی در یک کلید را بخوانید.
۴. همین payload را با tag‌های struct در Go بنویسید و خروجی دو برنامه را مقایسه کنید.

## قدم بعدی

نوع‌هایی که اینجا توصیف کردیم دقیقاً همان چیزی هستند که یک سرویس HTTP دریافت و برمی‌گرداند. مقاله‌ی بعد، «ساخت API با Axum در Rust»، آن‌ها را به بدنه‌ی درخواست و پاسخ تبدیل می‌کند.
