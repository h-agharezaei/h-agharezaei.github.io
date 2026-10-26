+++
date = '2027-01-21T10:00:00+03:30'
draft = false
title = 'ساخت API با Axum در Rust'
description = 'ساخت یک API کوچک سفارش‌ها با Axum: route، extractor، state مشترک، enum خطا، لایه‌های tower-http، graceful shutdown با SIGTERM و تست با oneshot.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "axum", "http", "api", "tokio", "tower", "intermediate"]
cover = { image = "/images/covers/rust-http-axum-api.fa.png", alt = "ساخت API با Axum در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-serde-json/) با serde و JSON آشنا شدیم و قول دادیم همان تایپ‌ها را برای بدنه‌ی درخواست و پاسخ به کار ببریم. این مقاله همان است. روی runtime مقاله‌ی [async در Rust با Tokio](/fa/posts/rust-async-tokio/) همان API کوچک سفارش‌های نسخه‌ی Go، یعنی [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/)، را می‌سازیم: ساخت، گرفتن با id، فهرست، `422` برای خطای اعتبارسنجی و `404` برای سفارش ناموجود. از **Axum** استفاده می‌کنم، یک فریم‌ورک وب سبک روی Hyper و Tower.

> همه‌چیز را با Rust نسخه‌ی 1.90، `axum` نسخه‌ی 0.8.9، `tokio` نسخه‌ی 1.54.1، `tower-http` نسخه‌ی 0.7.1 و `tower` نسخه‌ی 0.5.3 اجرا کرده‌ام که در `Cargo.lock` قفل شده‌اند. خروجی‌ها از اجرای واقعی یک نمونه‌ی محلی کپی شده‌اند و هدرهایی مثل `date` حذف شده‌اند.

## Router، handler و extractor

handler یک تابع async است. آرگومان‌هایش **extractor** هستند که از درخواست داده بیرون می‌کشند و نوع بازگشتی‌اش هر چیزی است که `IntoResponse` را پیاده کند:

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

`Path` مقدار `{id}` را می‌خواند، `Query` عبارت `?customer=x&limit=2` را در یک struct می‌ریزد، `Json<T>` بدنه را با قواعد serde مقاله‌ی قبل می‌خواند و `State` داده‌ی مشترک را می‌دهد. آخرین extractor می‌تواند بدنه را مصرف کند، برای همین `Json` آخر می‌آید. `Order` تایپ `Serialize` است و `CreateOrder` تایپ `Deserialize` با `deny_unknown_fields`.

## State

```rust
#[derive(Default)]
pub struct AppState { orders: Mutex<Vec<Order>> }
pub type Shared = Arc<AppState>;
```

`State` به تایپی با `Clone` نیاز دارد و `Arc` آن را ارزان می‌دهد. من `std::sync::Mutex` گذاشته‌ام، چون تا وقتی قفل در دست است هیچ `.await`ای نداریم. اگر مجبورید قفل را از روی await رد کنید، `tokio::sync::Mutex` بگذارید. id برابر طول فهرست به‌اضافه‌ی یک است، به‌صورت رشته، مثل Go.

## یک تایپ خطا

در Go یک تابع (`statusOf`) خطا را به status تبدیل می‌کرد. در Rust این کار با enumی است که `IntoResponse` را پیاده می‌کند؛ بعد handlerها `Result<T, ApiError>` برمی‌گردانند و `?` بقیه‌ی کار را می‌کند:

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

مثل Go، جزئیات یک `500` فقط در لاگ می‌رود و به کلاینت نمی‌رسد. یک tuple به شکل `(StatusCode, Json<T>)` خودش یک پاسخ است. اجراهای واقعی:

```text
$ curl -si -X POST localhost:8096/orders -H 'content-type: application/json' -d '{"customer":"roham","cents":2500}'
HTTP/1.1 201 Created
{"id":"1","customer":"roham","cents":2500,"status":"new"}

$ curl -si localhost:8096/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}

$ curl -si -X POST localhost:8096/orders -H 'content-type: application/json' -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -si localhost:8096/broken
HTTP/1.1 500 Internal Server Error
{"error":"internal error"}
```

برخلاف نسخه‌ی Go، اعتبارسنجی هر دو فیلد خراب را با هم گزارش می‌کند. `/broken` یک route فقط برای دمو است که `ApiError::Internal` برمی‌گرداند. `?customer=sara` و `?limit=1` هم فهرست را همان‌طور که انتظار می‌رفت فیلتر کردند.

## extractorهای داخلی چه چیزی را رد می‌کنند

وقتی یک extractor شکست بخورد، Axum خودش جواب می‌دهد، با بدنه‌ی متن ساده:

```text
{"customer":"a",                 -> 400 Failed to parse the request body as JSON: EOF while parsing a value at line 1 column 16
{"customer":"a","cents":"12"}    -> 422 Failed to deserialize the JSON body into the target type: cents: invalid type: string "12", expected i64 at line 1 column 28
{"customer":"a"}                 -> 422 ... missing field `cents` at line 1 column 16
{"customer":"a","cents":1,"vip":true} -> 422 ... vip: unknown field `vip`, expected `customer` or `cents` at line 1 column 31
(no content-type header)         -> 415 Expected request with `Content-Type: application/json`
/orders?limit=abc                -> 400 Failed to deserialize query string: limit: invalid digit found in string
```

پس خطای نحوی `400` است، JSON درست با شکل غلط `422` و نبودن هدر `415`. این بدنه‌ها متن‌اند، نه JSON خودمان. اگر کلاینت‌ها یک قالب خطا انتظار دارند، extractor را در extractor خودتان بپیچید که rejection را به `ApiError` تبدیل کند. من برای نشان دادن پیش‌فرض‌ها همین‌طور رهایش کردم. خطاهای routing هم فرق دارند: `DELETE /orders/1` پاسخ `405` با `allow: GET,HEAD` داد و مسیر ناشناخته `404` با بدنه‌ی خالی.

## لایه‌ها

Axum روی Tower ساخته شده، پس middleware همان **layer** است. سه تا از `tower-http`:

```rust
.layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, timeout))
.layer(PropagateRequestIdLayer::new(x_request_id.clone()))
.layer(TraceLayer::new_for_http().make_span_with(/* span with request_id */))
.layer(SetRequestIdLayer::new(x_request_id, Counter::default()))
```

آخرین layerی که اضافه می‌شود بیرونی‌ترین است، برعکس `Chain` در Go که اولی بیرونی‌ترین بود. پس `SetRequestIdLayer` اول اجرا می‌شود، با یک `MakeRequestId` ساده‌ی خودم که می‌شمارد (`req-1` و ...). نتیجه:

```text
$ curl -si localhost:8096/slow?ms=2000     # timeout is 1s
HTTP/1.1 408 Request Timeout
x-request-id: req-12

$ curl -si -H 'x-request-id: mine-1' localhost:8096/orders/1
HTTP/1.1 200 OK
x-request-id: mine-1
```

شناسه‌ی کلاینت حفظ می‌شود و در غیر این صورت یکی ساخته می‌شود. در لاگ، `500` مربوط به `/broken` شناسه را از span دارد:

```text
ERROR request{method=GET path=/broken request_id="req-1"}: request failed detail=disk on fire
ERROR request{method=GET path=/broken request_id="req-1"}: response failed classification=Status code: 500 Internal Server Error latency=0 ms
```

با فیلتر پیش‌فرض فقط شکست‌ها دیده می‌شوند؛ درخواست‌های موفق وقتی ظاهر می‌شوند که `DEBUG` را برای `tower_http` روشن کنید.

## Graceful shutdown

```rust
axum::serve(listener, router)
    .with_graceful_shutdown(shutdown_signal())
    .await?;
```

`shutdown_signal` با `select!` منتظر Ctrl-C یا SIGTERM (`tokio::signal::unix`) می‌ماند. درخواستی ۸۰۰ میلی‌ثانیه‌ای فرستادم، ۲۰۰ میلی‌ثانیه بعد SIGTERM زدم و بعد درخواست تازه‌ای فرستادم:

```text
new request: exit=7            # connection refused
done
 -> 200 after 0.803108s
 INFO shutting down
 INFO stopped
```

listener بسته شد، درخواست در جریان با `200` تمام شد و پروسه خارج شد. `ps` بعدش هیچ پروسه‌ای نشان نداد.

## تست بدون باز کردن پورت

`Router` یک service در Tower است، پس `oneshot` مستقیم صدایش می‌زند:

```rust
use tower::ServiceExt; // for oneshot

let res = app.clone().oneshot(post(r#"{"customer":"roham","cents":2500}"#)).await?;
assert_eq!(res.status(), StatusCode::CREATED);
```

`clone()` ارزان است و state را به اشتراک می‌گذارد، پس `oneshot` دوم می‌تواند سفارش را بخواند. جدولی از هفت حالت (اعتبارسنجی، JSON خراب، نوع غلط، 404، 405، 500، timeout) به‌اضافه‌ی تست request-id نتیجه‌ی `3 passed` داد.

## چند نکته

- ترتیب extractor مهم است: `Json` (یا هر extractor بدنه) باید آخر باشد.
- rejectionهای پیش‌فرض متن ساده‌اند؛ تصمیم بگیرید API شما خطای JSON لازم دارد یا نه.
- guard یک `std::sync::Mutex` را هرگز از روی `.await` رد نکنید.
- ترتیب layerها برعکس `Chain` در Go است.
- Axum نسخه‌ی 0.8 پارامتر مسیر را `{id}` می‌نویسد؛ شکل `:id` که در آموزش‌های قدیمی می‌بینید مال نسخه‌های قبلی است.

## تمرین

1. route با `PUT /orders/{id}/pay` اضافه کنید که status را `paid` کند و برای id ناموجود `404` بدهد.
2. `Json` را با یک extractor پوشاننده عوض کنید که rejectionها را به `ApiError` تبدیل کند.

## قدم بعدی

در مقاله‌ی بعد انبار درون‌حافظه را با یک پایگاه‌داده‌ی واقعی عوض می‌کنیم: پایگاه‌داده با SQLx در Rust.
