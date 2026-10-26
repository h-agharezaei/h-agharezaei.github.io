+++
date = '2027-02-04T10:00:00+03:30'
draft = false
title = 'A gRPC service in Go'
description = 'A gRPC service in Go: proto3 contract, generated code, status codes, interceptors, deadlines, server streaming, metadata, health checks and graceful stop.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "grpc", "protobuf", "interceptors", "api"]
cover = { image = "/images/covers/go-grpc-service.png", alt = "A gRPC service in Go", hiddenInSingle = true }
+++

In the [previous post](/posts/go-outbox-pattern-nats/) we made sure events leave the service reliably. Now the same `orders` service gets a second front door. We built its REST version in [the net/http post](/posts/go-http-api-stdlib/); here the operations are the same (create, get, list) but the contract is a `.proto` file and the wire is HTTP/2 with binary messages. The domain, service and in-memory store are copied unchanged, plus a `List` method. The error idea from [the config and errors post](/posts/go-config-logging-errors/) returns too: one function maps errors to codes.

> Go 1.26, macOS arm64, protoc 33.4, protoc-gen-go v1.36.11, protoc-gen-go-grpc 1.5.1, grpc-go v1.84.0. Log lines have the timestamp removed. `grpcurl` is not installed on my machine, so every call below comes from a small Go client.

## The contract

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

The numbers are **field numbers**, not values. They identify the field on the wire, so renaming a field is safe but changing or reusing a number is not: an old client would read new data as the wrong field. When you delete a field, `reserved` its number.

proto3 has no "unset" for plain scalar fields. A zero value is simply not sent. I checked that in `cmd/zerovalue`:

```
cents unset vs 0, same bytes: true 0
note unset:  true | note empty: false
empty note on the wire: 2 bytes
```

An unset `cents` and `cents = 0` are the same zero bytes, so "no amount" and "zero" cannot be told apart. Marking a field **`optional`** gives Go a pointer (`*string`), so nil means unset. We use it for `note` and for the status filter, where an empty string must not mean "all".

## Generating code

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

This writes `gen/ordersv1/orders.pb.go` (messages) and `orders_grpc.pb.go` (client and server). The generated file contains the server interface and a base type you must embed:

```go
type OrdersServiceServer interface {
	CreateOrder(context.Context, *CreateOrderRequest) (*Order, error)
	GetOrder(context.Context, *GetOrderRequest) (*Order, error)
	ListOrders(*ListOrdersRequest, grpc.ServerStreamingServer[Order]) error
	mustEmbedUnimplementedOrdersServiceServer()
}
```

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

Embedding `UnimplementedOrdersServiceServer` means that when a new RPC is added to the proto, old servers still compile and answer `Unimplemented` for it. Use the `Get...` getters: they are safe on nil messages. The error mapping:

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

As with HTTP, unknown errors become a fixed message and the detail goes only to the log. (The demo file also maps `context.Canceled`.) The client is created with `grpc.NewClient("127.0.0.1:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))`; it connects lazily, on the first call.

## Interceptors

An **interceptor** is {{< term "grpc" "gRPC" >}}'s middleware. A unary one wraps a handler; we need a stream twin for streaming RPCs.

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

`Logging` is outermost, so it sees the code `Recovery` produced. It logs method, code and duration, and reads `x-request-id` from incoming **metadata** (gRPC's headers). It also echoes it back with `grpc.SetHeader`. The client sets it with `metadata.AppendToOutgoingContext(ctx, "x-request-id", "req-42")` and reads the reply header with the `grpc.Header(&md)` call option.

## A real run

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

and the server log:

```
INFO rpc method=/orders.v1.OrdersService/CreateOrder code=InvalidArgument dur=0s request_id=req-42
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=0s request_id=req-42
INFO handler saw ctx.Done err="context canceled"
INFO rpc method=/orders.v1.OrdersService/GetOrder code=Canceled dur=300ms request_id=req-42
ERROR panic method=/orders.v1.OrdersService/GetOrder value="something broke"
ERROR rpc method=/orders.v1.OrdersService/GetOrder code=Internal dur=0s request_id=req-42
```

On the client, `status.Code(err)` gives the code. `ListOrders` is a **server-streaming** RPC: the server calls `stream.Send` per order and the client loops on `Recv` until `io.EOF`.

For the deadline, the client used `context.WithTimeout(ctx, 300*time.Millisecond)`; the deadline travels with the call. The demo-only id `slow` makes the handler wait two seconds with `select` on `ctx.Done()`. The handler stopped after 300ms. Look closely: the client got `DeadlineExceeded`, but my server saw `context canceled`, because the client's cancellation reached it first. Do not depend on which of the two the server sees.

Health is `grpc.health.v1`: `health.NewServer()` plus `healthpb.RegisterHealthServer`, and the client's `Check` returned `SERVING`.

## Graceful stop

On SIGTERM the server calls `hs.Shutdown()` (health turns `NOT_SERVING`) and then `srv.GracefulStop()`, which refuses new calls and waits for running ones. I started the client's two-second `slow` call, sent SIGTERM after 0.5s:

```
INFO shutting down
INFO rpc method=/orders.v1.OrdersService/GetOrder code=NotFound dur=2s request_id=req-42
INFO stopped
```

The call finished normally (`NotFound`, since no order has id `slow`) instead of being cut. `Stop()` would have closed it immediately.

## A few things to watch

- Never reuse or renumber fields; `reserved` them. Adding new fields is the safe change.
- Plain proto3 scalars cannot say "unset"; use `optional` where it matters.
- Always set a client deadline. Without one a call may wait forever.
- Return `status` errors. A plain `error` becomes `Unknown` on the client, and internal detail would leak if you wrote it into the message.
- `GracefulStop` can wait forever on a stuck call; give it a timeout and fall back to `Stop()`.

## What's next

Next: Go and Rust talking over gRPC. The same `.proto` will generate a Rust client, to show what interop looks like in practice.
