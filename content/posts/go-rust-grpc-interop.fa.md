+++
date = '2027-02-06T10:00:00+03:30'
draft = false
title = 'ارتباط Go و Rust با gRPC'
description = 'یک فایل proto، یک سرور Go و یک سرور Rust با tonic که هرکدام را زبان دیگر صدا می‌زند: فیلد optional، status code، metadata، deadline و استریم.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "grpc", "protobuf", "interop", "tonic"]
cover = { image = "/images/covers/go-rust-grpc-interop.fa.png", alt = "ارتباط Go و Rust با gRPC", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبلی این سری](/fa/posts/go-vs-rust-when-to-use/) دو زبان را مقایسه کرد. این یکی آن‌ها را وادار به همکاری می‌کند، و همین‌جاست که gRPC به کار می‌آید: قرارداد یک فایل `.proto` است و فرقی نمی‌کند پشت هر سر کدام زبان باشد. سرویس orders را از [مقاله‌ی gRPC در Go](/fa/posts/go-grpc-service/) بدون تغییر برمی‌داریم (همان proto، همان سرور و کلاینت Go) و Rust را در هر دو سمت اضافه می‌کنیم: کلاینتی که سرور Go را صدا می‌زند و سروری که کلاینت Go صدایش می‌زند. سمت Rust از [async و Tokio](/fa/posts/rust-async-tokio/) استفاده می‌کند؛ اگر [مقاله‌ی axum](/fa/posts/rust-http-axum-api/) و [مقاله‌ی thiserror](/fa/posts/rust-thiserror-anyhow/) را خوانده باشید، handlerها آشنا به نظر می‌رسند.

> Go 1.26، Rust 1.90، macOS (arm64)، grpc-go v1.84.0، protoc 33.4، protoc-gen-go v1.36.11، protoc-gen-go-grpc 1.6.1، tonic 0.14.6، prost 0.14.4، tokio 1.54.1 و protox 0.10.0. همه‌چیز روی یک ماشین و به‌صورت محلی اجرا شده است.

## یک منبع حقیقت

فایل `.proto` در ماژول Go است. Go با همان دستور قبلی از آن کد تولید می‌کند:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

crate Rust فایل را کپی نمی‌کند؛ `build.rs` آن را از همان‌جا می‌خواند. من از **protox** استفاده کردم، یک کامپایلر protobuf که کاملاً با Rust نوشته شده، پس build به باینری `protoc` نیاز ندارد:

```rust
const PROTO_DIR: &str = "../../../golang/blog-series/go-rust-grpc-interop/proto";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fds = protox::compile(["orders/v1/orders.proto"], [PROTO_DIR])?;
    tonic_prost_build::configure().compile_fds(fds)?;
    Ok(())
}
```

در `src/lib.rs` فقط `tonic::include_proto!("orders.v1")` هست. یک مخزن مشترک یا ابزاری مثل `buf` (که اینجا اجرا نکردم) می‌تواند جای این مسیر نسبی را بگیرد؛ نکته همان است: proto را یک بار ویرایش کنید و هر دو سمت را دوباره تولید کنید. نسخه‌ی همه‌ی crateها را با `=` قفل کرده‌ام.

## سرور Go، کلاینت Rust

سرور Go مقاله‌ی قبل را بالا آوردم و این کلاینت Rust را روی آن اجرا کردم. بخش‌های اصلی:

```rust
let mut c = OrdersServiceClient::connect("http://127.0.0.1:50051").await?;

let mut req = Request::new(CreateOrderRequest { customer: "bob".into(), cents: 300, note: Some("gift".into()) });
req.metadata_mut().insert("x-request-id", "rust-7".parse()?);
let r = c.create_order(req).await?;

let mut stream = c.list_orders(ListOrdersRequest { status: None }).await?.into_inner();
while let Some(o) = stream.message().await? { /* ... */ }
```

خروجی:

```
create "alice": Order { id: "1", customer: "alice", cents: 1250, status: "new" } header=Some("rust-7")
create "bob": Order { id: "2", customer: "bob", cents: 300, status: "new" } header=Some("rust-7")
create "": code=InvalidArgument msg="invalid order: customer and positive amount required"
get 99: NotFound | order not found
list None: ["1:alice", "2:bob"]
list Some("new"): ["1:alice", "2:bob"]
list Some("paid"): []
```

interceptor در Go هدر `x-request-id` را از فراخوانی Rust خواند و پس فرستاد، `NotFound` به شکل `tonic::Code::NotFound` رسید و استریم سرور به یک حلقه‌ی `message().await` تبدیل شد که در انتها `None` می‌دهد.

## سرور Rust، کلاینت Go

سرور، trait تولیدشده را پیاده می‌کند. پیام و status مثل مقدارهای معمولی Rust برمی‌گردند:

```rust
async fn create_order(&self, req: Request<CreateOrderRequest>) -> Result<Response<Order>, Status> {
    let rid = request_id(&req);
    let r = req.get_ref();
    if r.customer.is_empty() || r.cents <= 0 {
        return Err(Status::invalid_argument("invalid order: customer and positive amount required"));
    }
    /* store the order, build `o` */
    let mut resp = Response::new(o);
    resp.metadata_mut().insert("x-request-id", rid.parse().unwrap());
    Ok(resp)
}
```

`ListOrders` یک `Stream` جعبه‌شده برمی‌گرداند که با `tokio_stream::iter` ساخته شده، و `tonic-health` سرویس health را می‌دهد. حالا کلاینت Go موجود، بدون هیچ تغییری، روی این سرور:

```
create "alice": order=id:"1" customer:"alice" cents:1250 status:"new" code=OK err=<nil> header=[req-42]
create "": order=<nil> code=InvalidArgument err=rpc error: code = InvalidArgument desc = invalid order: customer and positive amount required header=[]
get 99: NotFound | order not found
stream got: 1 alice 1250
stream got: 2 bob 300
slow with 300ms deadline: DeadlineExceeded
boom: Internal | internal error
health: SERVING <nil>
```

کلاینت همان چیزی را چاپ کرد که با سرور Go چاپ می‌کرد.

## مولدها کجا فرق دارند

فیلد `optional` در proto3 در Rust می‌شود `Option<String>` و در Go می‌شود `*string`. یک برنامه‌ی کوچک Go سه note به سرور Rust فرستاد و لاگ سرور نشان داد چه رسیده است:

```
create rid=- note=None cents=500
create rid=- note=Some("") cents=500
create rid=- note=Some("gift") cents=500
```

حضور فیلد درست منتقل شد: nil شد `None` و رشته‌ی خالی شد `Some("")`. اسکالر ساده حضور ندارد: اولین کلاینت Go مقدار `cents: 0` فرستاد و لاگ Rust `cents=0` را نشان می‌دهد، اما اگر فیلد اصلاً فرستاده نمی‌شد هم همین را می‌دیدیم. با این حال حضور فقط داده است؛ معنایش را هر سرور خودش تعیین می‌کند. فیلتر status با مقدار `""` را به هر دو سرور فرستادم. سرور Go با `GetStatus()` مقدار `""` می‌گیرد و آن را «همه» حساب می‌کند. سرور Rust `Some("")` را با status هر سفارش مقایسه می‌کند و چیزی برنمی‌گرداند. این پرسش قرارداد است، نه زبان: بنویسید مقدار حاضر ولی خالی یعنی چه. (proto ما enum ندارد. در prost فیلد enum یک `i32` است، پس مقدار ناشناخته از یک همتای جدیدتر رمزگشایی را خراب نمی‌کند.)

## Deadline و لغو

مقدار `WithTimeout(300ms)` کلاینت Go به صورت یک هدر به سرور Rust رسید: `grpc-timeout=Some("299991u")` که واحدش میکروثانیه است. برای شناسه‌ی `slow` (handlerی که دو ثانیه می‌خوابد) سرور این را چاپ کرد:

```
get id="slow" grpc-timeout=Some("299991u")
  slow: handler future dropped
```

نقشه‌ام یک `tokio::select!` روی سیگنال لغو بود، اما tonic چنین token‌ای نمی‌دهد. وقتی فراخوانی لغو می‌شود، future مربوط به handler رها (drop) می‌شود؛ پس handlerی که فقط منتظر است در اولین `.await` خودش متوقف می‌شود و خواب هیچ‌وقت تمام نشد. برای پاک‌سازی، `Drop` جای مناسب است. کاری که بیرون از آن future باشد فرق دارد: برای شناسه‌ی `spawn` یک task با `tokio::spawn` شروع شد، کلاینت timeout خورد و سرور باز هم `spawn: background task still ran` را چاپ کرد. در Go خودتان باید `ctx.Done()` را بپایید؛ اینجا future برایتان لغو می‌شود، اما taskهای spawn‌شده و هر کار مسدودکننده‌ی بدون `.await` نه. حالت مسدودکننده را آزمایش نکردم.

کلاینت Rust متد `Request::set_timeout` دارد. روی سرور Go، فراخوانیِ کند `Cancelled | Timeout expired` برگرداند، نه `DeadlineExceeded`: کلاینت tonic timeout خودش را به `Cancelled` نگاشت می‌کند. پیش از ساختن alert روی code، این نگاشت را بررسی کنید.

## چند نکته که باید حواستان باشد

- یک `.proto` نگه دارید و هر دو سمت را در CI دوباره تولید کنید؛ فایل‌های کپی‌شده از هم دور می‌شوند.
- `optional` حضور را می‌گوید، نه معنا را. معنای مقدارهای خالی را مستند کنید.
- خطاها را در هر سمت در یک نقطه به status code نگاشت کنید؛ `NotFound` در یک زبان در زبان دیگر هم `NotFound` است.
- deadline را کلاینت تعیین می‌کند. در Go با context و در Rust صریحاً بگذارید.
- future رهاشده یعنی task متوقف نشده: کار spawn‌شده ادامه می‌دهد.

## قدم بعدی

سری Rust با trait object و `dyn` ادامه پیدا می‌کند، یعنی راه Rust برای چندریختی در زمان اجرا، که در Go با interface رایگان گرفته بودیم.
