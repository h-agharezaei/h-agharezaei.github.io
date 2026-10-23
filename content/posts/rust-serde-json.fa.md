+++
date = '2027-01-15T10:00:00+03:30'
draft = false
title = 'Serde و JSON در Rust'
description = 'کار با serde و serde_json در Rust: derive کردن Serialize و Deserialize، attributeهای rename و default، سه شکل enum، Value و json! و پیام‌های خطای واقعی.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "serde", "json", "intermediate"]
cover = { image = "/images/covers/rust-serde-json.fa.png", alt = "Serde و JSON در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-async-tokio/) کد async را با Tokio اجرا کردیم. تقریباً هر سرویسی که I/O دارد، JSON هم حرف می‌زند؛ برای همین این مقاله درباره‌ی **serde** است، چارچوب استاندارد serialization در Rust. اگر نسخه‌ی Go را خوانده باشید، یعنی [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/)، ساختار این مقاله آشنا به نظر می‌رسد و برای مقایسه از همان payload مربوط به `User` استفاده کرده‌ام.

> همه‌چیز را با Rust نسخه‌ی 1.90، `serde` نسخه‌ی 1.0.229 (با feature به نام `derive`) و `serde_json` نسخه‌ی 1.0.154 اجرا کرده‌ام. خروجی‌ها از اجرای واقعی کپی شده‌اند.

## derive و فراخوانی‌های پایه

`serde` دو trait به نام‌های `Serialize` و `Deserialize` تعریف می‌کند و `serde_json` فرمت JSON را روی آن‌ها پیاده می‌کند. ماکروهای derive پیاده‌سازی را برایتان می‌نویسند:

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

```text
{"name":"Roham","age":30}
```

این خروجیِ `serde_json::to_string(&u)` است وقتی ایمیل و تگ نداریم. با پر بودن هر دو، `to_string_pretty` خروجی تورفته می‌دهد (مثل `MarshalIndent` در Go) و `from_str` آن را برمی‌گرداند:

```text
User { name: "Roham", age: 30, email: Some("r@example.com"), tags: ["rust", "backend"], password: "" }
```

`skip` فیلد `password` را در هر دو جهت حذف می‌کند و موقع خواندن مقدارش از `Default` می‌آید، پس نوعش باید `Default` داشته باشد. `default` اجازه می‌دهد `tags` در ورودی نباشد. نبودنِ فیلد `Option` هم مشکلی ندارد. برای فایل و stream از `to_writer(File::create(..)?, &u)` و `from_reader(BufReader::new(File::open(..)?))` استفاده کنید؛ هر دو در اجرای من درست رفت‌وبرگشت کردند. فایل را در `BufReader` بپیچید، چون `from_reader` خواندن‌های کوچک زیادی انجام می‌دهد.

## تغییر نام، flatten و alias

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
    shipping: Shipping, // struct with city and zip
}
```

```text
{"orderId":7,"customer":"Roham","quantity":2,"isGift":false,"city":"Tehran","zip":"1234"}
```

`rename_all` نام همه‌ی فیلدها را عوض می‌کند، `rename` فقط یکی را، `alias` موقع خواندن یک نام اضافه می‌پذیرد (من `"qty":5` دادم) و `flatten` فیلدهای struct داخلی را در همان سطح می‌آورد، پس `city` و `zip` کنار `orderId` قرار می‌گیرند.

## enum: سه شکل

اینجا جایی است که serde خیلی‌ها را غافلگیر می‌کند. سه variant یکسان (`Created { id }`، `Paid { id, amount }` و `Cancelled`) و سه attribute:

```text
default:    {"Created":{"id":1}}   {"Paid":{"id":1,"amount":9.5}}   "Cancelled"
tag="type": {"type":"Created","id":1}   {"type":"Paid","id":1,"amount":9.5}   {"type":"Cancelled"}
untagged:   {"id":1}   {"id":1,"amount":9.5}   null
```

- **Externally tagged** (پیش‌فرض) داده را داخل نام variant می‌پیچد. variantهای بدون داده به یک رشته‌ی ساده تبدیل می‌شوند.
- **Internally tagged** (`#[serde(tag = "type")]`) برچسب را داخل خود شیء می‌گذارد. معمولاً کلاینت‌های API برای event همین را انتظار دارند.
- **Untagged** فقط داده را می‌نویسد. موقع خواندن variantها به ترتیب امتحان می‌شوند و اولین موردِ سازگار انتخاب می‌شود؛ برای همین `{"id":2,"amount":3.0}` شد `Paid` ولی `{"id":2}` شد `Created` و `Cancelled` به `null` تبدیل شد. فقط وقتی استفاده کنید که شکل‌ها با هم اشتباه گرفته نشوند.

خطاها هم فرق دارند:

```text
unknown variant `Refunded`, expected one of `Created`, `Paid`, `Cancelled`
missing field `type`
data did not match any variant of untagged enum Untagged
```

پیام آخر مکان مفیدی ندارد (خط 0، ستون 0). این هزینه‌ی `untagged` است.

## Value و json!

برای داده‌ای که شکل ثابت ندارد از `serde_json::Value` استفاده کنید. ایندکس کردن با کلیدِ ناموجود به‌جای panic مقدار `Value::Null` می‌دهد و `json!` مقدارها را درجا می‌سازد:

```rust
let mut v: Value = serde_json::from_str(r#"{"id":7,"name":"x","list":[1,2.5]}"#)?;
v["name"] = json!("changed");
v["extra"] = json!({"n": 1, "tags": ["a", "b"]});
```

```text
{"extra":{"n":1,"tags":["a","b"]},"id":7,"list":[1,2.5],"name":"changed","nested":{"a":null},"ok":true}
```

کلیدها مرتب شدند، چون بدون feature به نام `preserve_order` نقشه بر اساس کلید مرتب است. (`map[string]any` در Go هم موقع encode کلیدها را مرتب می‌نویسد.)

## عددها

`Value` عدد صحیح و اعشاری را از هم جدا نگه می‌دارد. برای `[1, 1.0, 18446744073709551615, 9223372036854775808]`: عدد `1` هم `i64` است هم `u64`، عدد `1.0` فقط `f64` است و دو عدد بزرگ فقط `u64` هستند، با ارقام دقیق. در Go، `map[string]any` همه را `float64` می‌کند. سریالایز کردن `(i64::MIN, u64::MAX, 1.0, 0.1, 1e21)` این را داد: `[-9223372036854775808,18446744073709551615,1.0,0.1,1e+21]`. یعنی عدد اعشاری `.0` خود را نگه می‌دارد.

نوع‌های مشخص سخت‌گیرند: `from_str::<i64>("1.0")` با ``invalid type: floating point `1.0`, expected i64`` شکست می‌خورد ولی `from_str::<f64>("1")` مقدار `1.0` می‌دهد.

## خطاها

برای `struct User { name: String, age: u8 }` این‌ها را گرفتم:

```text
trailing comma at line 1 column 14
EOF while parsing an object at line 1 column 12
key must be a string at line 4 column 3
missing field `age` at line 1 column 12
invalid type: string "thirty", expected u8 at line 1 column 26
invalid value: integer `300`, expected u8 at line 1 column 21
```

خطا متدهای `line()`، `column()` و `classify()` دارد (مقدارهای `Syntax`، `Data`، `Eof` و `Io`). برخلاف Go، فیلدِ نبود خطاست مگر اینکه `Option` باشد یا `default` داشته باشد؛ Go بی‌صدا مقدار صفر را می‌گذارد. فیلدهای ناشناس به‌طور پیش‌فرض نادیده گرفته می‌شوند (این هم مثل Go) و `#[serde(deny_unknown_fields)]` آن را به خطا تبدیل می‌کند: ``unknown field `nickname`, expected `name` or `age` at line 1 column 30``.

## deserializer سفارشی

بعضی API‌ها id را یک‌جا `5` و جای دیگر `"5"` می‌فرستند. `deserialize_with` با یک enum خصوصیِ untagged این را حل می‌کند:

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
// on the field: #[serde(deserialize_with = "id_from_str_or_num")] id: u64
```

```text
{"id":5} -> Item { id: 5 }
{"id":"6"} -> Item { id: 6 }
{"id":"abc"} -> error: invalid digit found in string at line 1 column 12
{"id":true} -> error: data did not match any variant of untagged enum StrOrNum at line 1 column 11
```

## چند نکته که باید حواستان باشد

- شکل enum را آگاهانه انتخاب کنید؛ پیش‌فرض چیزی نیست که بیشتر کلاینت‌های REST انتظار دارند.
- `skip` برای deserialize به `Default` روی نوع فیلد نیاز دارد.
- struct با نوع مشخص را ترجیح دهید و `Value` را فقط برای بخش‌های واقعاً پویا بگذارید.
- سرریز عدد صحیح خطاست، نه wrap شدن یا بریده شدن.
- خطای `untagged` مبهم است و ترتیب variantها مهم است.

## تمرین

1. به یک enum خودتان `#[serde(tag = "type")]` اضافه کنید و JSON را با حالت پیش‌فرض مقایسه کنید.
2. یک struct بسازید که فیلد ناشناس را رد کند و خطای یک غلط املایی را بخوانید.
3. همین payload را با struct tag در Go بنویسید و خروجی دو برنامه را مقایسه کنید.

## قدم بعدی

در مقاله‌ی بعد با Axum در Rust یک API می‌سازیم و از همین نوع‌ها برای بدنه‌ی درخواست و پاسخ استفاده می‌کنیم.
