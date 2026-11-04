+++
date = '2027-02-06T10:00:00+03:30'
draft = false
title = 'ارتباط Go و Rust با gRPC'
description = 'یک فایل proto، یک سرور Go و یک سرور Rust با tonic که هرکدام را زبان دیگر صدا می‌زند: فیلد optional، status code، metadata، deadline و استریم.'
contentType = 'tutorial'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "grpc", "protobuf", "interop", "tonic"]
cover = { image = "/images/covers/go-rust-grpc-interop.fa.png", alt = "ارتباط Go و Rust با gRPC", hiddenInSingle = true }
+++

دو سرویس را تصور کنید. سرویس orders با Go نوشته شده. سرویس تازه‌ای که باید سفارش‌ها را بخواند با Rust نوشته شده، چون آن تیم Rust را ترجیح می‌دهد. این دو چطور روی شکل یک سفارش روی سیم، روی اینکه اگر مشتری خالی باشد چه می‌شود یا روی اینکه «بدون فیلتر» یعنی چه، به توافق می‌رسند؟ اگر هر تیم struct‌های JSON خودش را دستی بنویسد، توافق در دو جا زندگی می‌کند و دیر یا زود دو نسخه با هم نمی‌خوانند.

در gRPC توافق در یک فایل زندگی می‌کند: `.proto`. هر زبان کد client و server خودش را از روی همان فایل تولید می‌کند، پس هر دو طرف تضمین‌شده درباره‌ی پیام‌های یکسانی حرف می‌زنند. در [نوشته‌ی قبل](/fa/posts/go-grpc-service/) این کار را با Go در هر دو سر کردیم. اینجا Rust را اضافه می‌کنم: یک client به Rust که server Go را صدا می‌زند و یک server به Rust که همان client Go بدون هیچ تغییری صدایش می‌زند. بعد از [مقایسه‌ی دو زبان](/fa/posts/go-vs-rust-when-to-use/)، این اولین بار است که با هم کار می‌کنند.

سمت Rust از [async و Tokio](/fa/posts/rust-async-tokio/) استفاده می‌کند؛ اگر [نوشته‌ی axum](/fa/posts/rust-http-axum-api/) و [نوشته‌ی thiserror](/fa/posts/rust-thiserror-anyhow/) را خوانده باشید، handlerها آشنا به نظر می‌رسند. اگر هنوز با gRPC، protobuf، status code و deadline آشنا نشده‌اید، اول نوشته‌ی قبل را بخوانید: هرکدام را از ابتدا توضیح می‌دهد.

> همه‌چیز زیر روی یک ماشین و فقط روی loopback اجرا شد (macOS با arm64). سمت Rust تازه با Rust 1.90، tonic نسخه‌ی 0.14.6، prost نسخه‌ی 0.14.4، tokio نسخه‌ی 1.54.1 و protox نسخه‌ی 0.10.0 ساخته شد. سمت Go مجموعه‌ی باینری‌هایی است که پیش‌تر از همین کد با Go 1.26 و grpc-go نسخه‌ی v1.84.0 ساخته شده بودند (تولیدشده با protoc نسخه‌ی 33.4، protoc-gen-go نسخه‌ی v1.36.11 و protoc-gen-go-grpc نسخه‌ی 1.6.1). همان باینری‌ها را دوباره اجرا کردم و کد Go را دوباره تولید نکردم. کد یک مثال محلی است و ریپوی منتشرشده ندارد.

## دو طرف چه چیزی را مشترک دارند

پیش از کد، دقیق بگوییم قرارداد چیست. `.proto` سه چیز می‌گوید: چه فراخوانی‌هایی وجود دارد (`CreateOrder`، `GetOrder`، `ListOrders`)، چه پیام‌هایی داخل و بیرون آن‌ها می‌رود و شماره‌ی فیلدهایی که هر فیلد را روی سیم مشخص می‌کنند. خودِ gRPC دو چیز مشترک دیگر هم اضافه می‌کند: **status code**ها (`NotFound`، `InvalidArgument` و غیره) و **metadata** (headerها). این همه‌ی چیزی است که هر دو زبان تضمین‌شده روی آن توافق دارند.

چیزی که `.proto` نمی‌گوید این است که یک مقدار *چه معنایی* دارد: آیا فیلتر status خالی یعنی «همه‌ی سفارش‌ها» یا «سفارش‌هایی که status‌شان رشته‌ی خالی است»؟ یک فراخوانی چقدر وقت دارد؟ این‌ها رفتارند، نه شکل، و هر طرف خودش آن‌ها را پیاده می‌کند. بیشتر غافلگیری‌های این نوشته از همین فاصله می‌آید.

## یک منبع حقیقت

`.proto` در ماژول Go است. Go با همان فرمان قبلی از آن کد تولید می‌کند:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

crate مربوط به Rust فایل را کپی نمی‌کند؛ `build.rs` آن (اسکریپت ساختی که Cargo پیش از compile اجرا می‌کند) آن را از همان‌جا می‌خواند. من از **protox** استفاده کردم، یک compiler برای protobuf که با Rust نوشته شده، پس برای ساخت به باینری `protoc` نیازی نیست:

```rust
const PROTO_DIR: &str = "../../../golang/blog-series/go-rust-grpc-interop/proto";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fds = protox::compile(["orders/v1/orders.proto"], [PROTO_DIR])?;
    tonic_prost_build::configure().compile_fds(fds)?;
    Ok(())
}
```

`src/lib.rs` خط `tonic::include_proto!("orders.v1")` را دارد که کد تولیدشده‌ی Rust را وارد می‌کند. یک ریپوی مشترک یا ابزاری مثل `buf` (اینجا اجرا نشده) می‌تواند جای این مسیر نسبی را بگیرد؛ نکته همان می‌ماند: proto را یک بار ویرایش کنید و هر دو طرف را دوباره تولید کنید. نسخه‌ی همه‌ی crateها را با `=` ثابت کردم تا ساخت زیر دستم عوض نشود.

## server به Go، client به Rust

جهت اول. server Go نوشته‌ی قبل را بالا آوردم و یک client به Rust را روی آن اجرا کردم. بخش‌های اصلی client:

```rust
let mut c = OrdersServiceClient::connect("http://127.0.0.1:50051").await?;

let mut req = Request::new(CreateOrderRequest { customer: "bob".into(), cents: 300, note: Some("gift".into()) });
req.metadata_mut().insert("x-request-id", "rust-7".parse()?);
let r = c.create_order(req).await?;

let mut stream = c.list_orders(ListOrdersRequest { status: None }).await?.into_inner();
while let Some(o) = stream.message().await? { /* ... */ }
```

(در دمو آدرس از یک متغیر محیطی می‌آید و پیش‌فرضش همین است.) client چند سفارش می‌سازد، یک شناسه‌ی درخواست را به‌عنوان metadata اضافه می‌کند و سفارش‌ها را با چهار فیلتر مختلف فهرست می‌کند. خروجی‌اش این است:

```
create "alice": Order { id: "1", customer: "alice", cents: 1250, status: "new" } header=Some("rust-7")
create "bob": Order { id: "2", customer: "bob", cents: 300, status: "new" } header=Some("rust-7")
create "": code=InvalidArgument msg="invalid order: customer and positive amount required"
get 99: NotFound | order not found
list None: ["1:alice", "2:bob"]
list Some("new"): ["1:alice", "2:bob"]
list Some("paid"): []
list Some(""): ["1:alice", "2:bob"]
slow with 300ms deadline: Cancelled | Timeout expired
boom: Internal | internal error
```

خواندنش: دو create اول موفق شدند و بخش `header=Some("rust-7")` نشان می‌دهد interceptor در Go مقدار `x-request-id` را از فراخوانی Rust خواند و پس فرستاد. create سوم (customer خالی) از اعتبارسنجی domain در server Go `InvalidArgument` گرفت و کد وضعیت در Rust به‌شکل `tonic::Code` متناظر رسید. `get 99` همان `NotFound` است. چهار خط `list` نشان می‌دهند server stream به یک حلقه‌ی `message().await` تبدیل می‌شود که در پایان `None` برمی‌گرداند؛ بدون فیلتر (`None`) و با `"new"` هر دو سفارش می‌آیند و با `"paid"` هیچ‌کدام. فیلتر چهارم، رشته‌ی خالی، هر دو سفارش را برگرداند: این را یادتان بماند، برمی‌گردیم. دو خط آخر حالت deadline و panic هستند که پایین‌تر می‌آید.

## server به Rust، client به Go

جهت دوم. server به Rust، trait تولیدشده را پیاده می‌کند و پیام و status به‌شکل مقدارهای معمولی Rust برمی‌گردند:

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

`ListOrders` یک `Stream` از نوع box‌شده را برمی‌گرداند که با `tokio_stream::iter` ساخته شده و crate به نام `tonic-health` سرویس استاندارد health را می‌دهد. حالا client Go موجود، بدون هیچ تغییری، روی این server Rust:

```
create "alice": order=id:"1"  customer:"alice"  cents:1250  status:"new" code=OK err=<nil> header=[req-42]
create "bob": order=id:"2"  customer:"bob"  cents:300  status:"new" code=OK err=<nil> header=[req-42]
create "": order=<nil> code=InvalidArgument err=rpc error: code = InvalidArgument desc = invalid order: customer and positive amount required header=[]
get 99: NotFound | order not found
stream got: 1 alice 1250
stream got: 2 bob 300
stream done
slow with 300ms deadline: DeadlineExceeded
boom: Internal | internal error
health: SERVING <nil>
```

همان چیزی را چاپ می‌کند که روی server Go چاپ کرده بود، به‌جز یک خط: create ناموفق `header=[]` دارد، چون آن handler در Rust پیش از افزودن header به `x-request-id` خطا را برمی‌گرداند. این تفاوت دو پیاده‌سازی من است، نه تفاوت دو زبان. (فاصله‌های دوتایی داخل `order=...` از روش چاپ پیام در کتابخانه‌ی protobuf در Go می‌آیند؛ این متن را parse نکنید.)

## مولدها چه چیزی را متفاوت می‌سازند

هر دو مولد همان proto را به روش طبیعی زبان خودشان نگاشت می‌کنند. فیلد `optional` در proto3 در Rust می‌شود `Option<String>` و در Go می‌شود `*string`. برای دیدن اینکه اطلاعات «حضور» در راه می‌ماند، یک برنامه‌ی کوچک Go سه note به server Rust فرستاد: هیچ، رشته‌ی خالی و `"gift"`. log server Rust چاپ کرد چه رسیده:

```
create rid=- note=None cents=500
create rid=- note=Some("") cents=500
create rid=- note=Some("gift") cents=500
```

حضور باقی ماند: nil در Go شد `None` و رشته‌ی خالی شد `Some("")`. یک scalar ساده حضور ندارد: client اول Go مقدار `cents: 0` فرستاد و log در Rust `cents=0` را نشان می‌دهد، اما فیلد غایب هم دقیقاً همین را نشان می‌داد.

اما حضور فقط داده است. هر server خودش تصمیم می‌گیرد چه معنایی دارد و اینجا دو server ما متفاوت تصمیم گرفتند. همان برنامه‌ی Go سفارش‌ها را با سه فیلتر (هیچ، `"paid"` و `""`) فهرست می‌کند و می‌شمارد هرکدام چند سفارش برگرداند. اول روی server Go، بعد روی server Rust (پیش از این هر دو server پنج سفارش با status برابر `new` داشتند):

```
# against the Go server
list filter=false: 5 orders
list filter=true: 0 orders
list filter=true: 5 orders

# against the Rust server
list filter=false: 5 orders
list filter=true: 0 orders
list filter=true: 0 orders
```

خط اول در هر دو یکی است: بدون فیلتر، هر پنج سفارش. خط دوم هم یکی است: هیچ سفارشی `paid` نیست. خط سوم تفاوت است: فیلتر `""`. server Go `GetStatus()` را صدا می‌زند که هم برای «تنظیم‌نشده» و هم برای «خالی» مقدار `""` می‌دهد و آن را «همه» حساب می‌کند. server Rust مقدار `Some("")` را می‌بیند و با هر status مقایسه‌اش می‌کند؛ هیچ status برابر رشته‌ی خالی نیست، پس چیزی برنمی‌گرداند. هیچ‌کدام اشتباه نمی‌کنند. این یک پرسش قرارداد است، نه زبان: `.proto` نمی‌تواند به شما بگوید، پس خودتان بنویسید یک مقدار حاضرِ خالی یعنی چه.

(proto ما `enum` ندارد. در prost یک فیلد enum به‌شکل `i32` نگه داشته می‌شود، پس مقدار ناشناخته از یک همتای جدیدتر نباید decode را خراب کند؛ این را اینجا امتحان نکردم.)

## deadline و لغو

`WithTimeout(300ms)` در client Go به‌شکل یک header به server Rust می‌رسد. server Rust آن را برای شناسه‌ی دموی `slow`، handlerی که دو ثانیه می‌خوابد، چاپ کرد:

```
get id="slow" grpc-timeout=Some("299986u")
  slow: handler future dropped
```

`u` یعنی میکروثانیه، پس `299986u` حدود ۳۰۰ میلی‌ثانیه است (مقدار دقیق از اجرایی به اجرای دیگر فرق می‌کند). بعد future مربوط به handler دور انداخته شد و خواب تمام نشد: خط `slow: finished the sleep` هرگز ظاهر نشد. نقشه‌ام یک `tokio::select!` روی یک سیگنال لغو بود، اما در API مربوط به handler در tonic چنین توکنی پیدا نکردم. آنچه دمو نشان می‌دهد این است که وقتی فراخوانی لغو می‌شود tonic ساده future مربوط به handler را دور می‌اندازد (drop). در Rust، futureای که فقط پای یک `.await` منتظر است با drop شدن خودبه‌خود می‌ایستد. struct به نام `Guard` در دمو در تابع `Drop` خودش چاپ می‌کند و از همین راه می‌بینیم؛ یک `Drop` guard جای پاکسازی هم هست.

کاری که بخشی از آن future نیست فرق دارد. برای شناسه‌ی `spawn` handler یک task جدا با `tokio::spawn` راه می‌اندازد و بعد می‌خوابد. client همان‌طور timeout شد و server چاپ کرد:

```
get id="spawn" grpc-timeout=Some("299335u")
  spawn: handler future dropped
  spawn: background task still ran
```

handler دور انداخته شد، اما task spawn‌شده به کارش ادامه داد و یک ثانیه بعد تمامش کرد. در Go باید خودتان `ctx.Done()` را زیر نظر بگیرید؛ در Rust future برایتان لغو می‌شود، اما taskهای spawn‌شده و هر چیزی که بدون `.await` بلاک می‌کند لغو نمی‌شوند. حالت بلاک‌کننده را امتحان نکردم.

client Rust `Request::set_timeout` را دارد. روی server Go، فراخوانیِ `slow` با `Cancelled | Timeout expired` تمام شد (خروجی بالا را ببینید)، نه با `DeadlineExceeded` که client Go می‌گیرد: client در tonic timeout خودش را به `Cancelled` نگاشت می‌کند. پیش از اینکه روی status codeها alert بگذارید این نگاشت را بررسی کنید.

## نکته‌های بین‌زبانی

- **یک `.proto` نگه دارید و هر دو طرف را در CI دوباره تولید کنید.** فایل‌های proto کپی‌شده منحرف می‌شوند، همان مشکلی که از آن شروع کردیم.
- **`optional` حضور را می‌گوید، نه معنا را.** معنای مقدارهای خالی را مستند کنید؛ دو server ما روی `""` اختلاف داشتند.
- **خطاها را در هر طرف در یک جا به status code نگاشت کنید.** `NotFound` در یک زبان در زبان دیگر هم `NotFound` می‌رسد.
- **deadline از سمت client می‌آید.** در Go با context و در Rust صریح (`set_timeout`) بگذارید و ببینید هر client انقضای deadline را چطور گزارش می‌کند.
- **future دورانداخته‌شده task متوقف‌شده نیست.** کار spawn‌شده ادامه پیدا می‌کند.

## قدم بعدی

نوشته‌ی بعدی این سری «صدا زدن Rust از Go با FFI» است. gRPC دو زبان را از طریق مرز شبکه به هم وصل می‌کند؛ FFI آن‌ها را داخل یک پروسه به هم وصل می‌کند، یعنی Go مستقیم کد Rust را صدا می‌زند و مبادله‌ها فرق می‌کند.
