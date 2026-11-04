+++
date = '2027-02-04T10:00:00+03:30'
draft = false
title = 'A gRPC service in Go'
description = 'A gRPC service in Go: proto3 contract, generated code, status codes, interceptors, deadlines, server streaming, metadata, health checks and graceful stop.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "grpc", "protobuf", "interceptors", "api"]
cover = { image = "/images/covers/go-grpc-service.png", alt = "A gRPC service in Go", hiddenInSingle = true }
+++

Here is a bug that every team with more than one service meets. Service A calls the orders service over HTTP with JSON. Someone on the orders team renames the field `cents` to `amount_cents` and deploys. Nothing fails to compile. The tests of both sides pass, because each side tests against its own idea of the JSON. In production, service A keeps sending `cents`, the orders service does not see it, reads zero, and rejects every order (or worse, accepts them as free). The contract between the two services lived only in people's heads, and it drifted.

gRPC attacks this problem at the root. You write the contract once, in a `.proto` file, and generate the client and server code from it. If the contract changes, the generated code changes, and the code that no longer fits stops compiling.

A few words first, in plain terms. An **RPC** (remote procedure call) means calling a function that runs in another process, as if it were a local function. **Protocol Buffers** (protobuf) is a small language for describing messages, plus a compact binary format to send them. {{< term "grpc" "gRPC" >}} is the framework that ties these together: you describe a **service** (a set of RPCs) and the **messages** they take and return, and it generates the code. The calls travel over HTTP/2 as binary protobuf messages, not as JSON text.

Return a plain `error` from a gRPC handler and the client sees `Unknown`; skip the client deadline and a call may wait forever. Those two rules, and a few more, are what this post is about. The service is the `orders` service again. We built its REST version in [the net/http post](/posts/go-http-api-stdlib/); here the operations are the same (create, get, list), but the contract is a `.proto` file. The domain, service and in-memory store are copied unchanged from that one, plus a `List` method. This demo uses the in-memory store only: it is not wired to Postgres or to the outbox from [the previous post](/posts/go-outbox-pattern-nats/). The error idea from [the config and errors post](/posts/go-config-logging-errors/) returns too: one function maps errors to codes.

> The client and server are the ones built from this code earlier (Go 1.26, grpc-go v1.84.0); I re-ran those binaries on macOS arm64 for this rewrite and pasted the output. The generated code is from the original run with protoc 33.4 (recorded in the generated files as `v6.33.4`), protoc-gen-go v1.36.11 and protoc-gen-go-grpc 1.5.1; I did not regenerate it now. Log lines have the timestamp removed. `grpcurl` is not installed on my machine, so every call below comes from a small Go client. The code is a local example, not a published repo.

## The contract

Here is the whole contract of our service:

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

Read it from the top. `syntax = "proto3"` is the version of the language, and `package orders.v1` puts a version into the name from day one. The `service` block lists three RPCs, each with its request message and response message. A `message` is a record with typed fields. The word `stream` in front of `Order` in `ListOrders` means the server sends back many `Order` messages one after another, instead of a single one. That is called **server streaming**, and we use it below.

The numbers after the fields are **field numbers**, not values. They are what identifies a field on the wire: the binary format does not send the name `customer`, it sends "field 2". Renaming a field is therefore safe, but changing or reusing a number is not: an old client would read new data as the wrong field. When you delete a field, mark its number `reserved` so nobody reuses it.

## One more detail: "not set" versus zero

In proto3 a plain field like `int64 cents` has no way to say "not set". A zero value is simply not sent. I checked it with a tiny program, `cmd/zerovalue`:

```
cents unset vs 0, same bytes: true 0
note unset:  true | note empty: false
empty note on the wire: 2 bytes
```

The first line says that an unset `cents` and `cents = 0` produce the same bytes, and that those bytes are empty (0 bytes long). So the receiver cannot tell "no amount" from "zero". Marking a field **`optional`** fixes this: in Go it becomes a pointer (`*string`), and `nil` means "not set". The next two lines show it for `note`: with no note, the pointer is nil (`true`); with an empty-string note it is not nil (`note empty: false` means "`Note == nil` is false"), and the empty note really goes on the wire, as 2 bytes (the field number and a length of 0). We use `optional` for `note` and for the status filter in `ListOrdersRequest`, where an empty string must not silently mean "all".

## Generating the code

This one command turns the `.proto` into Go code:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

It writes `gen/ordersv1/orders.pb.go` (the message types) and `orders_grpc.pb.go` (the client and the server skeleton). The generated file contains the server interface, and a base type you must embed:

```go
type OrdersServiceServer interface {
	CreateOrder(context.Context, *CreateOrderRequest) (*Order, error)
	GetOrder(context.Context, *GetOrderRequest) (*Order, error)
	ListOrders(*ListOrdersRequest, grpc.ServerStreamingServer[Order]) error
	mustEmbedUnimplementedOrdersServiceServer()
}
```

Our job is to implement that interface. This is also where the contract starts to protect us: if the `.proto` changes a method's signature, our server stops compiling.

## The server

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

Embedding `UnimplementedOrdersServiceServer` means that when a new RPC is added to the proto, old servers still compile, and they answer `Unimplemented` for the new method. Use the `Get...` getters (`req.GetCustomer()`) rather than the fields: they are safe to call even when the message is nil.

Errors need a little more care. Every gRPC call ends with a **status code**: a short standard word that tells the client what kind of outcome it was. The ones we use are:

- `OK`: it worked.
- `InvalidArgument`: the caller sent something wrong (the equivalent of HTTP 400).
- `NotFound`: the thing does not exist (like 404).
- `DeadlineExceeded`: the caller's time limit ran out.
- `Canceled`: the caller gave up.
- `Internal`: a bug or failure on the server side (like 500).
- `Unknown`: what the client sees when a handler returns a plain `error` that is not a status.

One function maps our domain errors to these codes:

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

As with HTTP, an error we did not expect becomes a fixed message, and the detail goes only to the log, never to the client. The client is created with `grpc.NewClient("127.0.0.1:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))`. It connects lazily, on the first call. (`insecure` means no TLS, which is fine on loopback for a demo and not for production.)

## Interceptors and metadata

Logging every call, recovering from panics: this is the job of middleware. In gRPC it is called an **interceptor**. A unary interceptor (for calls with one request and one response) wraps a handler; for streaming RPCs we need a stream twin.

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

`Recovery` catches a panic in the handler and turns it into an `Internal` status, so one bad request cannot crash the server. `Logging` is listed first, so it is the outermost: it sees the code that `Recovery` produced. It logs the method, the code and the duration. It also reads `x-request-id` from the incoming **metadata**, which is gRPC's name for headers: small key-value pairs that travel next to the message. It echoes the id back with `grpc.SetHeader`. The client sets the id with `metadata.AppendToOutgoingContext(ctx, "x-request-id", "req-42")` and reads the reply header with the `grpc.Header(&md)` call option.

## A real run

The demo client makes a series of calls. I started the server, ran the client once, and here is the client's output:

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

Line by line. The first two creates return `OK`, with the new order and the `x-request-id` header echoed back by the server. (The odd double spaces inside `order=...` are how the protobuf library prints a message: it deliberately varies the whitespace between builds, so never parse that text.) The third create sends an empty customer and amount 0; the domain refuses it and the client sees `InvalidArgument` with the message. `get 99` asks for an order that does not exist: `NotFound`. The two `stream got` lines are the `ListOrders` stream. `slow` and `boom` are demo-only ids that make the handler wait two seconds or panic; we look at them next. The last line is a health check.

The server's log for the same run:

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

Every call has one line with the method, the code, the duration and the request id from the client. The panic produced two lines: one from `Recovery` with the panic value, and one from `Logging` showing that the client got `Internal`. (The exact milliseconds vary from run to run.)

On the client, `status.Code(err)` gives you the code. `ListOrders` is the **server-streaming** RPC: the server calls `stream.Send` once per order, and the client loops on `Recv` until it gets `io.EOF`, which means the stream is finished.

## Deadlines

A call to another service can be slow, or hang. A **deadline** is the moment after which the caller no longer wants the answer. In gRPC the client sets it, and it travels with the call, so the server knows how long it has. For the `slow` line, the client used `context.WithTimeout(ctx, 300*time.Millisecond)`. The demo-only id `slow` makes the handler wait two seconds, using a `select` on `ctx.Done()` so that it can stop early. The handler did stop after about 300 ms.

Look closely at what each side saw. The client got `DeadlineExceeded`, which is right. But my server logged `context canceled`, not `deadline exceeded`: the client's cancellation reached the server first. So do not depend on which of the two the server sees; handle both as "the caller is gone, stop working".

## Health checks

Load balancers and orchestrators need to ask "are you up?". gRPC has a standard answer, the `grpc.health.v1` service. In the server it is `health.NewServer()` plus `healthpb.RegisterHealthServer`, and the client's `Check` call returned `SERVING`, as the last line of the client output shows.

## Graceful stop

When the server gets SIGTERM, it should not just die in the middle of calls. It calls `hs.Shutdown()` (health turns `NOT_SERVING`), and then `srv.GracefulStop()`, which refuses new calls and waits for the running ones to finish. To see it, I started the client's two-second `slow` call and sent SIGTERM to the server after half a second:

```
INFO shutting down
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=2.001s request_id=req-42
INFO stopped
```

The server announced the shutdown, and the running call still finished normally after two seconds (`NotFound`, since no order has the id `slow`), instead of being cut. Only then did the server report `stopped`. `Stop()`, by contrast, would have closed the call immediately.

## Rules not to break

- **Never reuse or renumber fields.** Mark deleted ones `reserved`. Adding new fields is the safe change.
- **Plain proto3 scalars cannot say "unset".** Use `optional` where "missing" and "zero" mean different things.
- **Always set a client deadline.** Without one, a call may wait forever, and so may the work behind it.
- **Return `status` errors.** A plain `error` becomes `Unknown` on the client, and internal details would leak if you wrote them into the message.
- **`GracefulStop` can wait forever on a stuck call.** Give it a timeout and fall back to `Stop()`.

## What's next

The next post is "Go and Rust talking over gRPC". The same `.proto` can generate a Rust client and server as well, so the contract can sit between two languages. That post tries it with this very service.
