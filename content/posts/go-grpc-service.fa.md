+++
date = '2027-02-04T10:00:00+03:30'
draft = false
title = 'سرویس gRPC با Go'
description = 'سرویس orders را با gRPC در Go بسازید: قرارداد proto3، کد تولیدشده، status code، interceptor، deadline، استریم سمت سرور، metadata، health check و توقف مرتب.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "grpc", "protobuf", "interceptors", "api"]
cover = { image = "/images/covers/go-grpc-service.fa.png", alt = "سرویس gRPC با Go", hiddenInSingle = true }
+++

باگی هست که هر تیمِ دارای بیش از یک سرویس با آن روبه‌رو می‌شود. سرویس A با HTTP و JSON سرویس orders را صدا می‌زند. یکی از تیم orders فیلد `cents` را به `amount_cents` تغییر می‌دهد و deploy می‌کند. هیچ چیز compile نمی‌شود که شکست بخورد. تست‌های هر دو طرف هم پاس می‌شوند، چون هر طرف با برداشت خودش از JSON تست می‌شود. در production سرویس A همچنان `cents` می‌فرستد، سرویس orders آن را نمی‌بیند، صفر می‌خواند و همه‌ی سفارش‌ها را رد می‌کند (یا بدتر، رایگان قبولشان می‌کند). قرارداد بین دو سرویس فقط در ذهن آدم‌ها بود و منحرف شد.

gRPC این مشکل را از ریشه می‌گیرد. قرارداد را یک بار در یک فایل `.proto` می‌نویسید و کد client و server را از روی آن تولید می‌کنید. اگر قرارداد عوض شود، کد تولیدشده عوض می‌شود و کدی که دیگر جور نیست compile نمی‌شود.

اول چند واژه به زبان ساده. **RPC** (فراخوانی رویه‌ی راه‌دور) یعنی صدازدن تابعی که در پروسه‌ای دیگر اجرا می‌شود، انگار تابعی محلی است. **Protocol Buffers** (به‌اختصار protobuf) زبان کوچکی برای توصیف پیام‌هاست، به‌علاوه‌ی یک قالب باینری فشرده برای فرستادنشان. {{< term "grpc" "gRPC" >}} چارچوبی است که این‌ها را به هم وصل می‌کند: شما یک **service** (مجموعه‌ای از RPCها) و **پیام‌هایی** (message) را که می‌گیرند و برمی‌گردانند توصیف می‌کنید و آن کد را تولید می‌کند. فراخوانی‌ها روی HTTP/2 و به‌شکل پیام‌های باینری protobuf می‌روند، نه متن JSON.

از handler یک gRPC یک `error` ساده برگردانید و client `Unknown` می‌بیند؛ deadline را در client نگذارید و ممکن است یک فراخوانی برای همیشه منتظر بماند. موضوع این نوشته همین دو قاعده و چند قاعده‌ی دیگر است. سرویس باز هم `orders` است. نسخه‌ی REST آن را در [نوشته‌ی net/http](/fa/posts/go-http-api-stdlib/) ساختیم. اینجا عملیات همان است (ساخت، گرفتن، فهرست)، ولی قرارداد یک فایل `.proto` است. domain، service و store درون‌حافظه‌ای بدون تغییر از آن نوشته کپی شده‌اند، به‌علاوه‌ی یک متد `List`. این دمو فقط store درون‌حافظه‌ای دارد: به Postgres یا به outbox [نوشته‌ی قبل](/fa/posts/go-outbox-pattern-nats/) وصل نیست. ایده‌ی خطا از [نوشته‌ی config و خطاها](/fa/posts/go-config-logging-errors/) هم برمی‌گردد: یک تابع خطاها را به کدها نگاشت می‌کند.

> client و server همان‌هایی هستند که پیش‌تر از همین کد ساخته شده بودند (Go 1.26 و grpc-go نسخه‌ی v1.84.0). برای این بازنویسی همان باینری‌ها را روی macOS (arm64) دوباره اجرا کردم و خروجی را گذاشتم. کد تولیدشده مال اجرای اصلی است، با protoc نسخه‌ی 33.4 (در فایل‌های تولیدشده به‌شکل `v6.33.4` ثبت شده)، protoc-gen-go نسخه‌ی v1.36.11 و protoc-gen-go-grpc نسخه‌ی 1.5.1؛ آن را الان دوباره تولید نکردم. از خط‌های log زمان حذف شده است. `grpcurl` روی ماشین من نصب نیست، پس هر فراخوانی زیر از یک client کوچک Go آمده است. کد یک مثال محلی است و ریپوی منتشرشده ندارد.

## قرارداد

این کل قرارداد سرویس ماست:

```proto
syntax = "proto3";
package orders.v1;
option go_package = "example.com/ordersgrpc/gen/ordersv1;ordersv1";

service OrdersService {
  rpc CreateOrder(CreateOrderRequest) returns (Order);
  rpc GetOrder(GetOrderRequest) returns (Order);
  rpc ListOrders(ListOrdersRequest) returns (stream Order);
}

message Order {
  string id = 1;  string customer = 2;  int64 cents = 3;  string status = 4;
}
message CreateOrderRequest {
  string customer = 1;  int64 cents = 2;  optional string note = 3;
}
message GetOrderRequest { string id = 1; }
message ListOrdersRequest { optional string status = 1; }  // unset = all
```

از بالا بخوانیدش. `syntax = "proto3"` نسخه‌ی زبان است و `package orders.v1` از روز اول یک نسخه در نام می‌گذارد. بلوک `service` سه RPC را فهرست می‌کند، هرکدام با پیام درخواست و پیام پاسخش. `message` رکوردی با فیلدهای نوع‌دار است. کلمه‌ی `stream` پیش از `Order` در `ListOrders` یعنی سرور به‌جای یک `Order` چند `Order` را پشت سر هم برمی‌گرداند. این را **server streaming** می‌گویند و پایین‌تر از آن استفاده می‌کنیم.

عددهای بعد از فیلدها **شماره‌ی فیلد** (field number) هستند، نه مقدار. چیزی که فیلد را روی سیم مشخص می‌کند همین‌هاست: قالب باینری نام `customer` را نمی‌فرستد، «فیلد ۲» را می‌فرستد. پس عوض‌کردن نام فیلد امن است، اما عوض‌کردن یا دوباره‌استفاده‌کردن یک شماره امن نیست: client قدیمی داده‌ی جدید را فیلد اشتباه می‌خواند. وقتی فیلدی را حذف می‌کنید شماره‌اش را `reserved` کنید تا کسی دوباره به کار نبرد.

## یک نکته‌ی دیگر: «تنظیم‌نشده» در برابر صفر

در proto3 یک فیلد ساده مثل `int64 cents` راهی برای گفتن «تنظیم نشده» ندارد. مقدار صفر اصلاً فرستاده نمی‌شود. با یک برنامه‌ی کوچک به نام `cmd/zerovalue` امتحانش کردم:

```
cents unset vs 0, same bytes: true 0
note unset:  true | note empty: false
empty note on the wire: 2 bytes
```

خط اول می‌گوید `cents` تنظیم‌نشده و `cents = 0` بایت‌های یکسانی تولید می‌کنند و آن بایت‌ها خالی‌اند (طول ۰). پس گیرنده نمی‌تواند «مبلغی نیست» را از «صفر» تشخیص بدهد. علامت‌زدن فیلد با **`optional`** این را درست می‌کند: در Go به یک اشاره‌گر (`*string`) تبدیل می‌شود و `nil` یعنی «تنظیم نشده». دو خط بعد این را برای `note` نشان می‌دهند: بدون note اشاره‌گر nil است (`true`)؛ با note رشته‌ی خالی nil نیست (`note empty: false` یعنی «`Note == nil` نادرست است») و note خالی واقعاً روی سیم می‌رود، به‌شکل ۲ بایت (شماره‌ی فیلد و طول ۰). `optional` را برای `note` و برای فیلتر status در `ListOrdersRequest` به کار می‌بریم، جایی که رشته‌ی خالی نباید بی‌صدا به معنی «همه» باشد.

## تولید کد

این یک فرمان `.proto` را به کد Go تبدیل می‌کند:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

فایل `gen/ordersv1/orders.pb.go` (نوع‌های پیام) و `orders_grpc.pb.go` (client و اسکلت server) را می‌نویسد. فایل تولیدشده interface سرور و یک نوع پایه را دارد که باید embed کنید:

```go
type OrdersServiceServer interface {
	CreateOrder(context.Context, *CreateOrderRequest) (*Order, error)
	GetOrder(context.Context, *GetOrderRequest) (*Order, error)
	ListOrders(*ListOrdersRequest, grpc.ServerStreamingServer[Order]) error
	mustEmbedUnimplementedOrdersServiceServer()
}
```

کار ما پیاده‌کردن همین interface است. اینجا هم قرارداد از ما محافظت می‌کند: اگر `.proto` امضای یک متد را عوض کند، server ما دیگر compile نمی‌شود.

## server

```go
type Server struct {
	pb.UnimplementedOrdersServiceServer // by value
	svc *service.Service
}

func (s *Server) CreateOrder(ctx context.Context, req *pb.CreateOrderRequest) (*pb.Order, error) {
	o, err := s.svc.Create(ctx, req.GetCustomer(), req.GetCents())
	if err != nil {
		return nil, toStatus(err)
	}
	return toPB(o), nil
}
```

embed‌کردن `UnimplementedOrdersServiceServer` یعنی وقتی RPC تازه‌ای به proto اضافه شود، serverهای قدیمی همچنان compile می‌شوند و برای متد جدید `Unimplemented` جواب می‌دهند. به‌جای خود فیلدها از getterهای `Get...` (مثل `req.GetCustomer()`) استفاده کنید: حتی وقتی پیام nil باشد امن‌اند.

خطاها کمی دقت بیشتر می‌خواهند. هر فراخوانی gRPC با یک **status code** (کد وضعیت) تمام می‌شود: واژه‌ی کوتاه و استانداردی که به client می‌گوید نتیجه از چه نوعی بود. آن‌هایی که به کار می‌بریم:

- `OK`: درست انجام شد.
- `InvalidArgument`: فراخواننده چیز اشتباهی فرستاد (معادل HTTP 400).
- `NotFound`: چیزی که خواسته شد وجود ندارد (مثل 404).
- `DeadlineExceeded`: مهلتِ فراخواننده تمام شد.
- `Canceled`: فراخواننده منصرف شد.
- `Internal`: باگ یا خرابی سمت server (مثل 500).
- `Unknown`: چیزی که client می‌بیند وقتی handler یک `error` ساده‌ی غیر از status برگرداند.

یک تابع خطاهای domain ما را به این کدها نگاشت می‌کند:

```go
func toStatus(err error) error {
	switch {
	case errors.Is(err, domain.ErrInvalidOrder):
		return status.Error(codes.InvalidArgument, err.Error())
	case errors.Is(err, domain.ErrNotFound):
		return status.Error(codes.NotFound, err.Error())
	case errors.Is(err, context.DeadlineExceeded):
		return status.Error(codes.DeadlineExceeded, "deadline exceeded")
	case errors.Is(err, context.Canceled):
		return status.Error(codes.Canceled, "canceled")
	default:
		slog.Error("unexpected error", "err", err)
		return status.Error(codes.Internal, "internal error")
	}
}
```

مثل HTTP، خطایی که انتظارش را نداشتیم یک پیام ثابت می‌شود و جزئیاتش فقط به log می‌رود، نه به client. client با `grpc.NewClient("127.0.0.1:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))` ساخته می‌شود و تنبل متصل می‌شود، در اولین فراخوانی. (`insecure` یعنی بدون TLS؛ روی loopback و برای دمو خوب است، برای production نه.)

## interceptor و metadata

log‌کردن هر فراخوانی و بازیابی از panic کار middleware است. در gRPC به آن **interceptor** می‌گویند. interceptor نوع unary (برای فراخوانی‌های یک درخواست و یک پاسخ) دور handler می‌پیچد. برای RPCهای streaming یک همتای stream لازم داریم.

```go
func Recovery(ctx context.Context, req any, info *grpc.UnaryServerInfo, h grpc.UnaryHandler) (resp any, err error) {
	defer func() {
		if v := recover(); v != nil {
			slog.Error("panic", "method", info.FullMethod, "value", v)
			err = status.Error(codes.Internal, "internal error")
		}
	}()
	return h(ctx, req)
}

srv := grpc.NewServer(
	grpc.ChainUnaryInterceptor(grpcapi.Logging, grpcapi.Recovery),
	grpc.ChainStreamInterceptor(grpcapi.StreamLogging, grpcapi.StreamRecovery),
)
```

`Recovery` panic داخل handler را می‌گیرد و به وضعیت `Internal` تبدیل می‌کند، پس یک درخواست بد نمی‌تواند server را از کار بیندازد. `Logging` اول فهرست است، یعنی بیرونی‌ترین است: کدی را که `Recovery` ساخت می‌بیند. متد، کد و مدت را log می‌کند. همچنین `x-request-id` را از **metadata** ورودی می‌خواند، اسم gRPC برای headerها: جفت کلید-مقدارهای کوچکی که کنار پیام می‌روند. شناسه را با `grpc.SetHeader` به client پس می‌فرستد. client شناسه را با `metadata.AppendToOutgoingContext(ctx, "x-request-id", "req-42")` می‌گذارد و header پاسخ را با گزینه‌ی فراخوانی `grpc.Header(&md)` می‌خواند.

## یک اجرای واقعی

client دمو یک سری فراخوانی انجام می‌دهد. server را بالا آوردم، client را یک بار اجرا کردم و خروجی client این است:

```
create "alice": order=id:"1"  customer:"alice"  cents:1250  status:"new" code=OK err=<nil> header=[req-42]
create "bob": order=id:"2"  customer:"bob"  cents:300  status:"new" code=OK err=<nil> header=[req-42]
create "": order=<nil> code=InvalidArgument err=rpc error: code = InvalidArgument desc = invalid order: customer and positive amount required header=[req-42]
get 99: NotFound | order not found
stream got: 1 alice 1250
stream got: 2 bob 300
stream done
slow with 300ms deadline: DeadlineExceeded
boom: Internal | internal error
health: SERVING <nil>
```

خط به خط. دو create اول `OK` برمی‌گردانند، با سفارش تازه و header به نام `x-request-id` که server پس فرستاده. (فاصله‌های دوتایی عجیب داخل `order=...` روش چاپ پیام در کتابخانه‌ی protobuf است: عمداً فاصله‌ها را بین buildهای مختلف عوض می‌کند، پس این متن را هرگز parse نکنید.) create سوم customer خالی و مبلغ ۰ می‌فرستد؛ domain آن را رد می‌کند و client `InvalidArgument` را با پیامش می‌بیند. `get 99` سفارشی را می‌خواهد که نیست: `NotFound`. دو خط `stream got` stream مربوط به `ListOrders` هستند. `slow` و `boom` شناسه‌هایی فقط برای دمو هستند که handler را دو ثانیه منتظر نگه می‌دارند یا panic می‌دهند؛ بعداً سراغشان می‌رویم. خط آخر health check است.

log سرور برای همین اجرا:

```
INFO rpc method=/orders.v1.OrdersService/CreateOrder code=OK dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/CreateOrder code=OK dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/CreateOrder code=InvalidArgument dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/ListOrders code=OK dur=0s request_id=req-42
INFO handler saw ctx.Done err="context canceled"
INFO rpc method=/orders.v1.OrdersService/GetOrder code=Canceled dur=301ms request_id=req-42
ERROR panic method=/orders.v1.OrdersService/GetOrder value="something broke"
ERROR rpc method=/orders.v1.OrdersService/GetOrder code=Internal dur=0s request_id=req-42
INFO rpc method=/grpc.health.v1.Health/Check code=OK dur=0s request_id=req-42
```

هر فراخوانی یک خط دارد با متد، کد، مدت و شناسه‌ی درخواست از client. panic دو خط ساخت: یکی از `Recovery` با مقدار panic و یکی از `Logging` که نشان می‌دهد client `Internal` گرفت. (میلی‌ثانیه‌ها از اجرایی به اجرای دیگر فرق می‌کنند.)

در client، `status.Code(err)` کد را می‌دهد. `ListOrders` همان RPC از نوع **server-streaming** است: server برای هر سفارش یک بار `stream.Send` را صدا می‌زند و client در یک حلقه `Recv` می‌کند تا `io.EOF` بگیرد، یعنی stream تمام شده.

## deadline

فراخوانی یک سرویس دیگر ممکن است کند باشد یا گیر کند. **deadline** (مهلت) لحظه‌ای است که بعد از آن فراخواننده دیگر جواب را نمی‌خواهد. در gRPC client آن را می‌گذارد و همراه فراخوانی می‌رود، پس server می‌داند چقدر وقت دارد. برای خط `slow` client از `context.WithTimeout(ctx, 300*time.Millisecond)` استفاده کرد. شناسه‌ی فقط‌دمو `slow` باعث می‌شود handler دو ثانیه صبر کند، با یک `select` روی `ctx.Done()` تا بتواند زود متوقف شود. handler حدود ۳۰۰ میلی‌ثانیه بعد واقعاً متوقف شد.

دقیق ببینید هر طرف چه دید. client `DeadlineExceeded` گرفت که درست است. اما server من `context canceled` را log کرد، نه `deadline exceeded`: لغو client زودتر به server رسید. پس به اینکه server کدام‌یک از این دو را می‌بیند تکیه نکنید؛ هر دو را به معنی «فراخواننده رفته، کار را متوقف کن» بگیرید.

## health check

load balancerها و orchestratorها باید بپرسند «بالایی؟». gRPC جواب استانداردی دارد، سرویس `grpc.health.v1`. در server این `health.NewServer()` به‌علاوه‌ی `healthpb.RegisterHealthServer` است و `Check` در client مقدار `SERVING` برگرداند، همان‌طور که خط آخر خروجی client نشان می‌دهد.

## توقف تمیز

وقتی server سیگنال SIGTERM می‌گیرد نباید وسط فراخوانی‌ها بمیرد. `hs.Shutdown()` را صدا می‌زند (health می‌شود `NOT_SERVING`) و بعد `srv.GracefulStop()` را، که فراخوانی تازه نمی‌پذیرد و منتظر تمام‌شدن فراخوانی‌های در حال اجرا می‌ماند. برای دیدنش فراخوانی دو‌ثانیه‌ای `slow` از client را راه انداختم و بعد از نیم ثانیه SIGTERM را به server فرستادم:

```
INFO shutting down
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=2.001s request_id=req-42
INFO stopped
```

server خاموشی را اعلام کرد و فراخوانی در حال اجرا بعد از دو ثانیه عادی تمام شد (`NotFound`، چون هیچ سفارشی شناسه‌ی `slow` ندارد)، به‌جای اینکه قطع شود. فقط بعد از آن server `stopped` را گزارش کرد. `Stop()` برعکس فراخوانی را فوراً می‌بست.

## قاعده‌هایی که نباید شکست

- **شماره‌ی فیلد را هرگز دوباره استفاده یا عوض نکنید.** فیلدهای حذف‌شده را `reserved` کنید. اضافه‌کردن فیلد تازه تغییر امن است.
- **scalarهای ساده‌ی proto3 نمی‌توانند «تنظیم نشده» بگویند.** جایی که «نبودن» و «صفر» فرق دارند از `optional` استفاده کنید.
- **همیشه برای client deadline بگذارید.** بدون آن یک فراخوانی ممکن است برای همیشه منتظر بماند و کار پشتش هم.
- **خطای `status` برگردانید.** `error` ساده در client می‌شود `Unknown` و اگر جزئیات داخلی را در پیام بنویسید نشت می‌کنند.
- **`GracefulStop` ممکن است روی یک فراخوانی گیرکرده تا ابد صبر کند.** برایش timeout بگذارید و به `Stop()` برگردید.

## قدم بعدی

نوشته‌ی بعد «ارتباط Go و Rust با gRPC» است. همین `.proto` می‌تواند client و server Rust هم تولید کند، پس قرارداد می‌تواند بین دو زبان بنشیند. آن نوشته این را با همین سرویس امتحان می‌کند.
