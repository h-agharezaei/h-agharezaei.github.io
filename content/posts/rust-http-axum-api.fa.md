+++
date = '2027-01-21T10:00:00+03:30'
draft = false
title = 'ساخت API با Axum در Rust'
description = 'ساخت یک API کوچک سفارش‌ها با Axum: route، extractor، state مشترک، enum خطا، لایه‌های tower-http، graceful shutdown با SIGTERM و تست با oneshot.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "axum", "http", "api", "tokio", "tower", "intermediate"]
cover = { image = "/images/covers/rust-http-axum-api.fa.png", alt = "ساخت API با Axum در Rust", hiddenInSingle = true }
+++

وقتی کلاینت JSON خراب می‌فرستد، سرور چه جوابی بدهد؟ وقتی JSON سالم است ولی نوع یک فیلد غلط است؟ وقتی سفارشی که می‌خواهد وجود ندارد؟ یک API فقط مسیر خوش‌اقبال نیست. نیمی از کیفیتش در همین جواب‌هاست: کد وضعیت درست (`400` و `422` و `404`) و بدنه‌ای که کلاینت بتواند با آن کاری بکند.

در این مقاله یک API کوچک سفارش‌ها را با Rust می‌سازیم و می‌بینیم دقیقاً به همین سؤال‌ها چه جواب می‌دهد. نوع‌های [Serde و JSON در Rust](/fa/posts/rust-serde-json/) را به‌عنوان بدنه‌ی درخواست و پاسخ به کار می‌برد و روی runtime ‏Tokio از [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) اجرا می‌شود. همان API هم‌ارز Go است، [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/): ساختن سفارش، گرفتن یک سفارش با id، فهرست سفارش‌ها، `422` برای خطای اعتبارسنجی و `404` برای سفارش ناشناخته. این بار فریم‌ورک وب **Axum** است، لایه‌ای نازک روی Hyper (یک پیاده‌سازی HTTP) و Tower (کتابخانه‌ای از middleware‌های قابل‌استفاده‌ی مجدد).

> همه‌چیز را با Rust نسخه‌ی 1.90، `axum` نسخه‌ی 0.8.9، `tokio` نسخه‌ی 1.54.1، `tower-http` نسخه‌ی 0.7.1 و `tower` نسخه‌ی 0.5.3 اجرا کرده‌ام، همان‌طور که در `Cargo.lock` ‏demo قفل شده‌اند. برای این نسخه‌ی مقاله سرور و تست‌ها را دوباره روی یک پورت آزاد تصادفی اجرا کردم و خروجی‌های زیر از همین اجراها کپی شده‌اند. headerهایی مثل `date` و `content-length` را حذف کرده‌ام. شناسه‌هایی مثل `req-5` بستگی به تعداد درخواست‌های قبلی دارند و هر بار فرق می‌کنند.

## handler و extractor یعنی چه

**handler** یک تابع async است که درخواست می‌گیرد و پاسخ برمی‌گرداند. Axum برای ورودی و خروجی آن یک ترفند خوب دارد. هر *آرگومان* handler یک **extractor** است: نوعی که بلد است یک تکه را از درخواست بیرون بکشد، مثل مسیر، query string یا بدنه. هر چه تابع *برمی‌گرداند* فقط باید trait‌ای به نام `IntoResponse` را پیاده کند، که می‌گوید مقدار چطور به پاسخ HTTP تبدیل شود.

سه مسیر API ما و امضای یکی از handlerها این‌طور تعریف می‌شود:

```rust
let app = Router::new()
    .route("/orders", get(list_orders).post(create_order))
    .route("/orders/{id}", get(get_order))
    .with_state(state);

async fn get_order(
    State(st): State<Shared>,
    Path(id): Path<String>,
) -> Result<Json<Order>, ApiError> { /* ... */ }
```

`get_order` دو چیز می‌خواهد. `Path(id)` بخش `{id}` از URL را بیرون می‌کشد و `State(st)` داده‌ی مشترک همه‌ی درخواست‌ها را می‌دهد (کمی بعد درباره‌اش). extractor‌های دیگری که به کار می‌بریم:

- `Query<T>` رشته‌ی query، مثلاً `?customer=sara&limit=2`، را داخل یک struct به نام `T` می‌خواند.
- `Json<T>` بدنه‌ی درخواست را با همان قاعده‌های serde مقاله‌ی قبل به `T` می‌خواند.

یک قاعده: بدنه را فقط یک بار می‌شود مصرف کرد، پس extractorی که بدنه را می‌خواند (`Json`) باید آخرین آرگومان باشد. در demo، `Order` از نوع `Serialize` است (فقط می‌فرستیمش) و `CreateOrder` از نوع `Deserialize` با `deny_unknown_fields` (فقط دریافتش می‌کنیم و غلط‌املایی را رد می‌کنیم).

## state مشترک

هر درخواستی به فهرست سفارش‌ها نیاز دارد و درخواست‌ها هم‌زمان رسیدگی می‌شوند، شاید روی thread‌های مختلف. پس ذخیره‌گاه باید مشترک و محافظت‌شده باشد:

```rust
#[derive(Default)]
pub struct AppState { orders: Mutex<Vec<Order>> }
pub type Shared = Arc<AppState>;
```

این همان الگوی {{< term "arc" "Arc" >}} به‌علاوه‌ی {{< term "rust-mutex" "Mutex" >}} از مقاله‌ی [thread‌ها](/fa/posts/rust-concurrency-threads/) است: `Arc` به هر handler اجازه می‌دهد مالک state باشد و `Mutex` اجازه می‌دهد هر بار فقط یکی آن را تغییر بدهد. Axum می‌خواهد نوع state ارزان `Clone` شود و کلون‌کردن `Arc` فقط یک شمارنده را بالا می‌برد. از `std::sync::Mutex` استفاده کرده‌ام. اینجا اشکالی ندارد چون وقتی قفل در دست است هیچ `.await` رخ نمی‌دهد؛ اگر روزی مجبور شدید قفل را از روی await نگه دارید، `tokio::sync::Mutex` بگذارید. id سفارش تعداد سفارش‌ها به‌علاوه‌ی یک است، به‌شکل رشته، مثل نسخه‌ی Go. این یک ذخیره‌گاه demo است؛ مقاله‌ی بعد جایش پایگاه داده‌ی واقعی می‌گذارد.

## یک نوع خطا برای کل API

وقتی داخل handler چیزی خراب می‌شود، کلاینت کد وضعیت درست و بدنه‌ای با قالب یک‌دست لازم دارد. در نسخه‌ی Go یک تابع (`statusOf`) خطاها را به status نگاشت می‌کرد. در Rust همین کار به یک enum می‌رسد که `IntoResponse` را پیاده می‌کند. آن‌وقت هر handler می‌تواند `Result<T, ApiError>` برگرداند و عملگر `?` بقیه را انجام دهد، چون axum سمت `Err` را هم به پاسخ تبدیل می‌کند:

```rust
pub enum ApiError {
    NotFound,
    Validation(BTreeMap<&'static str, &'static str>),
    Internal(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        match self {
            ApiError::NotFound => (StatusCode::NOT_FOUND,
                Json(json!({"error": "order not found"}))).into_response(),
            ApiError::Validation(f) => (StatusCode::UNPROCESSABLE_ENTITY,
                Json(json!({"error": "validation failed", "fields": f}))).into_response(),
            ApiError::Internal(detail) => {
                tracing::error!(%detail, "request failed");
                (StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({"error": "internal error"}))).into_response()
            }
        }
    }
}
```

سه نکته. تاپل `(StatusCode, Json<T>)` خودش یک پاسخ معتبر است و همین هر شاخه را کوتاه نگه می‌دارد. `Validation` یک نگاشت از نام فیلد به پیام دارد، پس کلاینت می‌تواند هر مشکل را کنار فیلدش نشان دهد. و `Internal` جزئیاتش را برای log نگه می‌دارد و به کلاینت فقط `internal error` می‌گوید: مثل نسخه‌ی Go، اینکه داخل سرور شما چه خراب شد به کلاینت ربطی ندارد.

حالا اجراهای واقعی. سرور را روی یک پورت تصادفی بالا آوردم و با `curl` صدایش زدم (`-s` ساکت، `-i` برای چاپ status line و headerها). درخواست اول یک سفارش می‌سازد، دومی id ای را می‌خواهد که وجود ندارد، سومی سفارشی می‌فرستد که دو قاعده را می‌شکند، و چهارمی `/broken` را صدا می‌زند، مسیری که فقط در demo هست و همیشه `ApiError::Internal` برمی‌گرداند:

```text
$ curl -si -X POST localhost:$PORT/orders -H 'content-type: application/json' -d '{"customer":"roham","cents":2500}'
HTTP/1.1 201 Created
{"id":"1","customer":"roham","cents":2500,"status":"new"}

$ curl -si localhost:$PORT/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}

$ curl -si -X POST localhost:$PORT/orders -H 'content-type: application/json' -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -si localhost:$PORT/broken
HTTP/1.1 500 Internal Server Error
{"error":"internal error"}
```

هر جواب همان کد وضعیتی را دارد که برنامه‌اش را ریخته بودیم و شکل JSON هم یکی است. ببینید جواب اعتبارسنجی *هر دو* فیلد خراب را می‌شمارد؛ نسخه‌ی Go فقط اولین قاعده‌ی شکسته را گزارش می‌کرد. بدنه‌ی `500` چیزی درباره‌ی دیسک نمی‌گوید؛ علت واقعی به log رفت (پایین‌تر می‌بینیم). این را هم بررسی کردم که `?customer=sara` و `?limit=1` فهرست را همان‌طور که باید فیلتر می‌کنند.

## extractor‌های آماده چه چیزی را رد می‌کنند

برای JSON خراب، نوع غلط یا header گم‌شده خودمان کدی ننوشتیم. باز هم سرور جواب می‌دهد. وقتی یک extractor شکست می‌خورد، axum به‌جای شما یک *rejection* برمی‌گرداند: یک کد وضعیت و یک پیام متنی ساده. این چیزی است که demo برگرداند (`->` آنچه فرستادم را از آنچه برگشت جدا می‌کند):

```text
{"customer":"a",                      -> 400 Failed to parse the request body as JSON: EOF while parsing a value at line 1 column 16
{"customer":"a","cents":"12"}         -> 422 Failed to deserialize the JSON body into the target type: cents: invalid type: string "12", expected i64 at line 1 column 28
{"customer":"a"}                      -> 422 ... missing field `cents` at line 1 column 16
{"customer":"a","cents":1,"vip":true} -> 422 ... vip: unknown field `vip`, expected `customer` or `cents` at line 1 column 31
(no content-type header)              -> 415 Expected request with `Content-Type: application/json`
/orders?limit=abc                     -> 400 Failed to deserialize query string: limit: invalid digit found in string
```

ببینید کد وضعیت مشکل‌ها را چطور دو دسته می‌کند. متنی که اصلاً JSON نیست `400` است. متنی که JSON معتبر است ولی با نوع ما نمی‌خواند `422` است؛ پیام بعد از آن همان خطای serde مقاله‌ی قبل است، پس خواندنش را بلدید. نبودن header ‏`content-type: application/json` می‌شود `415`. و query string خراب `400` است.

بدنه‌ها متن ساده‌اند، نه قالب `{"error": ...}` ما. اگر کلاینت‌های شما همه‌جا یک قالب خطا انتظار دارند، دور `Json` یک wrapper کوچک بنویسید که rejection را به `ApiError` تبدیل کند. من پیش‌فرض‌ها را گذاشتم تا ببینید چه چیزی مفت به دست می‌آید. (یک فرق با نسخه‌ی Go: آنجا بدنه‌ی با فیلد ناشناخته `400` بود، اینجا `422` است.)

خطای مسیریابی کمی فرق دارد و اصلاً بدنه ندارد. `DELETE /orders/1` جواب `405 Method Not Allowed` با header ‏`allow: GET,HEAD` داد و یک مسیر ناشناخته `404` با بدنه‌ی خالی.

## layer: middleware دور کل router

بعضی چیزها باید برای همه‌ی درخواست‌ها اعمال شوند: timeout، شناسه‌ی درخواست، log. در Axum این‌ها **layer** هستند. Axum روی Tower ساخته شده و در Tower یک service چیزی است که درخواست می‌گیرد و پاسخ می‌دهد، و یک layer یک service را داخل service دیگر می‌پیچد. crate ‏`tower-http` layer‌های آماده دارد. ما چهارتا را به کار می‌بریم:

```rust
.layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, timeout))
.layer(PropagateRequestIdLayer::new(x_request_id.clone()))
.layer(TraceLayer::new_for_http().make_span_with(/* span with request_id */))
.layer(SetRequestIdLayer::new(x_request_id, Counter::default()))
```

ترتیب دقت می‌خواهد. هر `.layer(...)` همه‌ی چیزهای بالای خودش را می‌پیچد، پس *آخرین* layer اضافه‌شده *بیرونی‌ترین* است و درخواست را اول می‌بیند. این عکس تابع کمکی `Chain` در Go است که آنجا اولی بیرونی‌ترین بود. پس اینجا `SetRequestIdLayer` اول اجرا می‌شود. به هر درخواست یک id می‌دهد (مولد کوچکی از خودم که می‌شمارد: `req-1` و `req-2` و ...) مگر اینکه فرستنده خودش یکی فرستاده باشد. بعد `TraceLayer` با آن id log می‌نویسد، `PropagateRequestIdLayer` همان id را روی پاسخ هم می‌گذارد، و `TimeoutLayer` handlerی را که زیادی طول بکشد قطع می‌کند (در demo یک ثانیه).

برای امتحان، `/slow?ms=2000` دو ثانیه می‌خوابد، بیشتر از timeout. درخواست دوم id خودش را می‌فرستد:

```text
$ curl -si localhost:$PORT/slow?ms=2000
HTTP/1.1 408 Request Timeout
x-request-id: req-17

$ curl -si -H 'x-request-id: mine-1' localhost:$PORT/orders/1
HTTP/1.1 200 OK
x-request-id: mine-1
```

درخواست کند بعد از timeout با `408` جواب گرفت. id فرستنده (`mine-1`) نگه داشته و برگردانده شد؛ وقتی id نیست، سرور یکی می‌سازد. همین id در log هم هست، پس می‌توان یک درخواست را در کل سیستم دنبال کرد. این log مربوط به `500` مسیر `/broken` است:

```text
ERROR request{method=GET path=/broken request_id="req-5"}: request failed detail=disk on fire
ERROR request{method=GET path=/broken request_id="req-5"}: response failed classification=Status code: 500 Internal Server Error latency=0 ms
```

خط اول همان است که در `ApiError::Internal` نوشتیم: جزئیاتی که کلاینت هرگز ندید (`disk on fire`). خط دوم از `TraceLayer` است و می‌گوید پاسخ شکست بود. هر دو id درخواست را دارند. با فیلتر پیش‌فرض log فقط شکست‌ها دیده می‌شوند؛ درخواست‌های موفق وقتی ظاهر می‌شوند که `DEBUG` را برای `tower_http` روشن کنید.

## خاموش‌شدن مرتب

یک deploy به پروسه‌ی شما `SIGTERM` می‌فرستد. اگر سرور همان لحظه بمیرد، هر درخواستِ در حال انجام نصفه می‌ماند. در Axum یک سیگنال خاموشی به سرور وصل می‌کنید:

```rust
axum::serve(listener, router)
    .with_graceful_shutdown(shutdown_signal())
    .await?;
```

`shutdown_signal` تابعی در `main.rs` است که داخل یک `select!` منتظر Ctrl-C یا `SIGTERM` می‌ماند (با `tokio::signal::unix`)؛ `select!` به محض رخ‌دادن یکی از آن‌ها تمام می‌شود. وقتی تمام شد، سرور اتصال تازه نمی‌پذیرد و منتظر درخواست‌های در حال اجرا می‌ماند. {{< term "graceful-shutdown" "خاموش‌شدن مرتب" >}} (graceful shutdown) دقیقاً همین است. برای آزمایش، درخواستی شروع کردم که ۸۰۰ میلی‌ثانیه طول می‌کشد، بعد از ۲۰۰ میلی‌ثانیه `SIGTERM` فرستادم و بعد یک درخواست تازه امتحان کردم:

```text
new request: exit=7
 -> 200 after 0.803547s
 INFO shutting down
 INFO stopped
```

`exit=7` یعنی curl می‌گوید «اتصال رد شد»: listener از قبل بسته بود و درخواست تازه برگشت خورد. درخواست قدیمی بعد از حدود ۰٫۸ ثانیه با `200` تمام شد، یعنی نصفه نماند. بعد log می‌گوید سرور خاموشی را اعلام کرد و ایستاد، و پروسه خارج شد. (عدد `0.80…s` در هر اجرا کمی فرق می‌کند.) `ps` بعد از آن هیچ پروسه‌ای از من نشان نداد.

## تست بدون باز کردن پورت

`Router` یک service در Tower است و یک service در Tower را می‌شود مثل تابع معمولی صدا زد. پس تست‌ها اصلاً socket لازم ندارند: `oneshot` یک درخواست را مستقیم داخل router می‌فرستد.

```rust
use tower::ServiceExt; // for oneshot

let res = app.clone().oneshot(post(r#"{"customer":"roham","cents":2500}"#)).await?;
assert_eq!(res.status(), StatusCode::CREATED);
```

`clone()` یک router ارزان است و همان state را به اشتراک می‌گذارد، پس یک `oneshot` دوم روی نسخه‌ی کلون‌شده می‌تواند سفارش را بخواند. demo سه تست دارد: ساختن و بعد گرفتن؛ جدولی از هفت حالت خطا (اعتبارسنجی، JSON خراب، نوع غلط، ۴۰۴، ۴۰۵، ۵۰۰ و timeout، هر کدام با status مورد انتظار)؛ و تستی که بررسی می‌کند id درخواست برگردانده می‌شود. `cargo test` گزارش داد `3 passed`.

## جاهایی که Axum غافلگیر می‌کند

- **ترتیب extractor مهم است.** `Json` (یا هر extractor که بدنه را می‌خواند) باید آخر باشد، وگرنه کد کامپایل نمی‌شود.
- **rejection‌های پیش‌فرض متن ساده‌اند.** زود تصمیم بگیرید API شما خطای JSON لازم دارد یا نه، و اگر دارد extractor را wrap کنید.
- **guard یک `std::sync::Mutex` را از روی `.await` نگه ندارید.** future دیگر `Send` نیست و کامپایلر رد می‌کند، همان‌طور که در مقاله‌ی Tokio بود.
- **ترتیب layerها برعکس چیزی است که شاید انتظار دارید.** آخرین `.layer(...)` بیرونی‌ترین است.
- **سینتکس مسیر عوض شده.** Axum نسخه‌ی 0.8 پارامتر مسیر را `{id}` می‌نویسد؛ شکل `:id` که در آموزش‌های قدیمی می‌بینید مال نسخه‌های قبلی است.

## تمرین

۱. مسیر `PUT /orders/{id}/pay` را اضافه کنید که وضعیت را `paid` می‌کند و برای id ناشناخته `404` برمی‌گرداند.
۲. `Json` را با یک extractor پوشاننده عوض کنید که rejection‌ها را به `ApiError` تبدیل کند، تا بدنه‌ی خراب هم قالب `{"error": ...}` بگیرد.

## قدم بعدی

فهرست درون‌حافظه با هر راه‌اندازی مجدد از بین می‌رود، پس مقاله‌ی بعد، «دیتابیس با SQLx در Rust»، جای آن یک پایگاه داده‌ی واقعی Postgres می‌گذارد.
