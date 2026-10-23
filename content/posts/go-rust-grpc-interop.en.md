+++
date = '2027-02-06T10:00:00+03:30'
draft = false
title = 'Go and Rust talking over gRPC'
description = 'Go and Rust over gRPC: one .proto file, a Go server and a Rust tonic server, each called by the other, with optional fields, deadlines and streaming.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "grpc", "protobuf", "interop", "tonic"]
cover = { image = "/images/covers/go-rust-grpc-interop.png", alt = "Go and Rust talking over gRPC", hiddenInSingle = true, hiddenInList = true }
+++

[The last post in this series](/posts/go-vs-rust-when-to-use/) compared the two languages. This one makes them work together, which is where gRPC is really useful: the contract is a `.proto` file, so the language behind each end does not matter. We take the orders service from [the Go gRPC post](/posts/go-grpc-service/), unchanged (same proto, same Go server and client), and add Rust on both sides: a client that calls the Go server, and a server that the Go client calls. The Rust side uses [async and Tokio](/posts/rust-async-tokio/); the handlers will look familiar if you read the [axum post](/posts/rust-http-axum-api/) and the [thiserror post](/posts/rust-thiserror-anyhow/).

> Go 1.26, Rust 1.90, macOS arm64, grpc-go v1.84.0, protoc 33.4, protoc-gen-go v1.36.11, protoc-gen-go-grpc 1.6.1, tonic 0.14.6, prost 0.14.4, tokio 1.54.1, protox 0.10.0. Everything below was run locally on one machine.

## One source of truth

The `.proto` lives in the Go module. Go generates from it with the same command as before:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

The Rust crate does not copy the file; its `build.rs` reads it from there. I used **protox**, a pure-Rust protobuf compiler, so the build needs no `protoc` binary:

```rust
const PROTO_DIR: &str = "../../../golang/blog-series/go-rust-grpc-interop/proto";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fds = protox::compile(["orders/v1/orders.proto"], [PROTO_DIR])?;
    tonic_prost_build::configure().compile_fds(fds)?;
    Ok(())
}
```

`src/lib.rs` has `tonic::include_proto!("orders.v1")`. A shared repo or a tool like `buf` (not run here) can replace that relative path; the point stays: edit the proto once, regenerate both sides. I pinned every crate version with `=`.

## Go server, Rust client

I started the Go server from the previous post and ran this Rust client against it. The key parts:

```rust
let mut c = OrdersServiceClient::connect("http://127.0.0.1:50051").await?;

let mut req = Request::new(CreateOrderRequest { customer: "bob".into(), cents: 300, note: Some("gift".into()) });
req.metadata_mut().insert("x-request-id", "rust-7".parse()?);
let r = c.create_order(req).await?;

let mut stream = c.list_orders(ListOrdersRequest { status: None }).await?.into_inner();
while let Some(o) = stream.message().await? { /* ... */ }
```

Output:

```
create "alice": Order { id: "1", customer: "alice", cents: 1250, status: "new" } header=Some("rust-7")
create "bob": Order { id: "2", customer: "bob", cents: 300, status: "new" } header=Some("rust-7")
create "": code=InvalidArgument msg="invalid order: customer and positive amount required"
get 99: NotFound | order not found
list None: ["1:alice", "2:bob"]
list Some("new"): ["1:alice", "2:bob"]
list Some("paid"): []
```

The Go interceptor read `x-request-id` from the Rust call and echoed it, `NotFound` arrived as `tonic::Code::NotFound`, and the server stream became a `message().await` loop that returns `None` at the end.

## Rust server, Go client

The server implements the generated trait. The message and the status come back as ordinary Rust values:

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

`ListOrders` returns a boxed `Stream` made with `tokio_stream::iter`, and `tonic-health` provides the health service. Now the existing Go client, with no change, against this server:

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

The client printed the same as against the Go server.

## What the generators do differently

A proto3 `optional` field becomes `Option<String>` in Rust and `*string` in Go. A small Go program sent three notes to the Rust server, and its log printed what arrived:

```
create rid=- note=None cents=500
create rid=- note=Some("") cents=500
create rid=- note=Some("gift") cents=500
```

Presence survived the trip: nil became `None` and an empty string became `Some("")`. A plain scalar has no presence: the first Go client sent `cents: 0` and the Rust log shows `cents=0`, but a missing field would show the same. Presence is only data, though; each server decides its meaning. I sent the status filter `""` to both. The Go server calls `GetStatus()`, which gives `""`, and treats it as "all". The Rust server compares `Some("")` with each status and returns nothing. That is a contract question, not a language one: write down what a present-but-empty value means. (Our proto has no enum. In prost an enum field is an `i32`, so an unknown value from a newer peer does not break decoding.)

## Deadlines and cancellation

The Go client's `WithTimeout(300ms)` arrived at the Rust server as a header: `grpc-timeout=Some("299991u")`, in microseconds. For the demo id `slow` (a handler that sleeps two seconds) the server then printed:

```
get id="slow" grpc-timeout=Some("299991u")
  slow: handler future dropped
```

My plan was a `tokio::select!` on a cancellation signal, but tonic gives no such token. A cancelled call simply drops the handler future, so a handler that is only awaiting stops by itself at the next `.await`; the sleep never finished. A `Drop` guard is the place for cleanup. Work that is not part of that future is different: for id `spawn` the handler started a `tokio::spawn` task, the client timed out, and the server still printed `spawn: background task still ran`. In Go you must watch `ctx.Done()` yourself; here the future is cancelled for you, but spawned tasks and anything blocking without `.await` are not. I did not test the blocking case.

The Rust client has `Request::set_timeout`. Against the Go server the slow call returned `Cancelled | Timeout expired`, not `DeadlineExceeded`: the tonic client maps its own timeout to `Cancelled`. Check that mapping before alerting on codes.

## A few things to watch

- Keep one `.proto` and regenerate both sides in CI; copied proto files drift.
- `optional` tells you presence, not meaning. Document the meaning of empty values.
- Map errors to status codes in one place per side; `NotFound` in one language is `NotFound` in the other.
- Deadlines come from the client. Set them on the Go side with a context and on the Rust side explicitly.
- A dropped future is not a stopped task: spawned work keeps running.

## What's next

The Rust series continues with trait objects and `dyn`, which is how Rust does the runtime polymorphism we got for free from Go interfaces.
