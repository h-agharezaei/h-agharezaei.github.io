+++
date = '2027-02-04T10:00:00+03:30'
draft = false
title = 'سرویس gRPC با Go'
description = 'سرویس orders را با gRPC در Go بسازید: قرارداد proto3، کد تولیدشده، status code، interceptor، deadline، استریم سمت سرور، metadata، health check و توقف مرتب.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "grpc", "protobuf", "interceptors", "api"]
cover = { image = "/images/covers/go-grpc-service.fa.png", alt = "سرویس gRPC با Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-outbox-pattern-nats/) مطمئن شدیم رویدادها قابل‌اعتماد از سرویس بیرون می‌روند. حالا همان سرویس `orders` یک در ورودی دوم می‌گیرد. نسخه‌ی REST آن را در [مقاله‌ی net/http](/fa/posts/go-http-api-stdlib/) ساختیم؛ اینجا عملیات همان است (ساخت، گرفتن، فهرست) اما قرارداد یک فایل `.proto` است و روی سیم، HTTP/2 با پیام‌های باینری داریم. دامنه، سرویس و store در حافظه بدون تغییر کپی شده‌اند، فقط یک متد `List` اضافه شده است. ایده‌ی [مقاله‌ی config و خطاها](/fa/posts/go-config-logging-errors/) هم برمی‌گردد: یک تابع خطاها را به code نگاشت می‌کند.

> Go 1.26، macOS (arm64)، protoc 33.4، protoc-gen-go v1.36.11، protoc-gen-go-grpc 1.5.1 و grpc-go v1.84.0. در لاگ‌ها زمان حذف شده است. `grpcurl` روی ماشین من نصب نیست، پس همه‌ی فراخوانی‌های زیر از یک کلاینت کوچک Go آمده‌اند.

## قرارداد

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

عددها **شماره‌ی فیلد** (field number) هستند، نه مقدار. فیلد را روی سیم با همین شماره می‌شناسند؛ پس عوض‌کردن نام فیلد بی‌خطر است، اما تغییر یا استفاده‌ی دوباره از یک شماره نه: کلاینت قدیمی داده‌ی جدید را به‌جای فیلد دیگری می‌خواند. وقتی فیلدی را حذف می‌کنید، شمارهاش را `reserved` کنید.

در proto3 برای فیلدهای اسکالر ساده حالت «تنظیم‌نشده» وجود ندارد؛ مقدار صفر اصلاً فرستاده نمی‌شود. این را در `cmd/zerovalue` بررسی کردم:

```
cents unset vs 0, same bytes: true 0
note unset:  true | note empty: false
empty note on the wire: 2 bytes
```

`cents` تنظیم‌نشده با `cents = 0` دقیقاً همان بایت‌های خالی است، پس «بدون مبلغ» و «مبلغ صفر» از هم جدا نمی‌شوند. علامت **`optional`** برای فیلد در Go یک اشاره‌گر (`*string`) می‌سازد و nil یعنی تنظیم‌نشده. از آن برای `note` و فیلتر status استفاده کرده‌ایم، چون رشته‌ی خالی نباید یعنی «همه».

## تولید کد

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

این دستور `gen/ordersv1/orders.pb.go` (پیام‌ها) و `orders_grpc.pb.go` (کلاینت و سرور) را می‌نویسد. در فایل دوم، interface سرور و یک نوع پایه هست که باید embed کنید:

```go
type OrdersServiceServer interface {
	CreateOrder(context.Context, *CreateOrderRequest) (*Order, error)
	GetOrder(context.Context, *GetOrderRequest) (*Order, error)
	ListOrders(*ListOrdersRequest, grpc.ServerStreamingServer[Order]) error
	mustEmbedUnimplementedOrdersServiceServer()
}
```

## سرور

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

embed‌کردن `UnimplementedOrdersServiceServer` یعنی اگر بعداً RPC تازه‌ای به proto اضافه شود، سرورهای قدیمی هنوز کامپایل می‌شوند و برای آن `Unimplemented` برمی‌گردانند. از getter‌های `Get...` استفاده کنید؛ روی پیام nil هم امن‌اند. نگاشت خطا:

```go
func toStatus(err error) error {
	switch {
	case errors.Is(err, domain.ErrInvalidOrder):
		return status.Error(codes.InvalidArgument, err.Error())
	case errors.Is(err, domain.ErrNotFound):
		return status.Error(codes.NotFound, err.Error())
	case errors.Is(err, context.DeadlineExceeded):
		return status.Error(codes.DeadlineExceeded, "deadline exceeded")
	default:
		slog.Error("unexpected error", "err", err)
		return status.Error(codes.Internal, "internal error")
	}
}
```

مثل HTTP، خطای ناشناخته به یک متن ثابت تبدیل می‌شود و جزئیات فقط به لاگ می‌رود. (فایل دموی من `context.Canceled` را هم نگاشت می‌کند.) کلاینت با `grpc.NewClient("127.0.0.1:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))` ساخته می‌شود؛ اتصال تنبل است و با اولین فراخوانی برقرار می‌شود.

## Interceptor

**Interceptor** همان middleware در gRPC است. نوع unary دور یک handler را می‌گیرد؛ برای RPCهای استریم هم جفتی جدا لازم است.

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

`Logging` بیرونی‌ترین است، پس codeای را می‌بیند که `Recovery` ساخته. متد، code و مدت را لاگ می‌کند و `x-request-id` را از **metadata** ورودی (هدرهای gRPC) می‌خواند، سپس با `grpc.SetHeader` پس می‌فرستد. کلاینت آن را با `metadata.AppendToOutgoingContext(ctx, "x-request-id", "req-42")` می‌گذارد و هدر پاسخ را با گزینه‌ی `grpc.Header(&md)` می‌خواند.

## یک اجرای واقعی

```
create "alice": order=id:"1" customer:"alice" cents:1250 status:"new" code=OK header=[req-42]
create "": order=<nil> code=InvalidArgument err=rpc error: code = InvalidArgument desc = invalid order: customer and positive amount required
get 99: NotFound | order not found
stream got: 1 alice 1250
stream got: 2 bob 300
stream done
slow with 300ms deadline: DeadlineExceeded
boom: Internal | internal error
health: SERVING <nil>
```

و لاگ سرور:

```
INFO rpc method=/orders.v1.OrdersService/CreateOrder code=InvalidArgument dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=0s request_id=req-42
INFO handler saw ctx.Done err="context canceled"
INFO rpc method=/orders.v1.OrdersService/GetOrder code=Canceled dur=300ms request_id=req-42
ERROR panic method=/orders.v1.OrdersService/GetOrder value="something broke"
ERROR rpc method=/orders.v1.OrdersService/GetOrder code=Internal dur=0s request_id=req-42
```

در کلاینت، `status.Code(err)` همان code را می‌دهد. `ListOrders` یک RPC با **استریم سمت سرور** است: سرور برای هر سفارش `stream.Send` می‌زند و کلاینت تا `io.EOF` در حلقه `Recv` می‌کند.

برای deadline، کلاینت `context.WithTimeout(ctx, 300*time.Millisecond)` گذاشت و deadline همراه فراخوانی می‌رود. شناسه‌ی `slow` (فقط برای دمو) باعث می‌شود handler با `select` روی `ctx.Done()` دو ثانیه صبر کند. handler بعد از ۳۰۰ میلی‌ثانیه متوقف شد. دقت کنید: کلاینت `DeadlineExceeded` گرفت، اما سرور من `context canceled` دید، چون لغو کلاینت زودتر رسید. به این‌که سرور کدام را ببیند تکیه نکنید.

health همان `grpc.health.v1` است: `health.NewServer()` و `healthpb.RegisterHealthServer`، و `Check` کلاینت `SERVING` برگرداند.

## توقف مرتب

با SIGTERM سرور `hs.Shutdown()` را صدا می‌زند (health می‌شود `NOT_SERVING`) و بعد `srv.GracefulStop()`، که فراخوانی تازه را رد می‌کند و منتظر فراخوانی‌های در حال اجرا می‌ماند. فراخوانی دو‌ثانیه‌ای `slow` کلاینت را شروع کردم و بعد از ۰٫۵ ثانیه SIGTERM فرستادم:

```
INFO shutting down
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=2s request_id=req-42
INFO stopped
```

فراخوانی عادی تمام شد (`NotFound`، چون سفارشی با شناسه‌ی `slow` نیست) و قطع نشد. `Stop()` آن را فوراً می‌بست.

## چند نکته که باید حواستان باشد

- شماره‌ی فیلد را هرگز دوباره استفاده یا عوض نکنید؛ `reserved` کنید. افزودن فیلد تازه تغییر امن است.
- اسکالرهای ساده‌ی proto3 نمی‌توانند «تنظیم‌نشده» را بگویند؛ جایی که مهم است از `optional` استفاده کنید.
- همیشه برای کلاینت deadline بگذارید. بدون آن، فراخوانی ممکن است تا ابد منتظر بماند.
- خطای `status` برگردانید. `error` ساده در کلاینت `Unknown` می‌شود، و اگر جزئیات داخلی را در پیام بنویسید لو می‌رود.
- `GracefulStop` ممکن است پشت یک فراخوانی گیرکرده تا ابد بماند؛ برایش timeout بگذارید و در نهایت `Stop()` را صدا بزنید.

## قدم بعدی

مقاله‌ی بعد: Go و Rust با gRPC با هم حرف می‌زنند. همین `.proto` یک کلاینت Rust هم تولید می‌کند تا ببینیم تعامل بین دو زبان در عمل چه شکلی دارد.
