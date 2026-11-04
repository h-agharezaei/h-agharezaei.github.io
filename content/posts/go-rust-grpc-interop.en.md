+++
date = '2027-02-06T10:00:00+03:30'
draft = false
title = 'Go and Rust talking over gRPC'
description = 'Go and Rust over gRPC: one .proto file, a Go server and a Rust tonic server, each called by the other, with optional fields, deadlines and streaming.'
contentType = 'tutorial'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "grpc", "protobuf", "interop", "tonic"]
cover = { image = "/images/covers/go-rust-grpc-interop.png", alt = "Go and Rust talking over gRPC", hiddenInSingle = true }
+++

Imagine two services. The orders service is written in Go. A new service that needs to read orders is written in Rust, because that team prefers it. How do the two agree on what an order looks like on the wire, what happens when the customer is missing, or what "no filter" means? If each team writes its own JSON structs by hand, the agreement lives in two places, and sooner or later the two copies disagree.

With gRPC the agreement lives in one file, the `.proto`. Each language generates its own client and server code from that file, so both sides are guaranteed to talk about the same messages. In [the previous post](/posts/go-grpc-service/) we did this with Go on both ends. Here I add Rust: a Rust client that calls the Go server, and a Rust server that the same Go client calls, with no change to the Go code. After [comparing the two languages](/posts/go-vs-rust-when-to-use/), this is the first time they work together.

The Rust side uses [async and Tokio](/posts/rust-async-tokio/); the handlers will look familiar if you read the [axum post](/posts/rust-http-axum-api/) and the [thiserror post](/posts/rust-thiserror-anyhow/). If you have not met gRPC, protobuf, status codes or deadlines, read the previous post first: it explains each of them from the start.

> Everything below ran locally on one machine (macOS arm64, loopback only). The Rust side was built fresh with Rust 1.90, tonic 0.14.6, prost 0.14.4, tokio 1.54.1 and protox 0.10.0. The Go side is the set of binaries built earlier from this code with Go 1.26 and grpc-go v1.84.0 (generated with protoc 33.4, protoc-gen-go v1.36.11 and protoc-gen-go-grpc 1.6.1); I re-ran those binaries and did not regenerate the Go code. The code is a local example, not a published repo.

## What the two sides share

Before the code, let us be precise about what the contract is. The `.proto` says three things: which calls exist (`CreateOrder`, `GetOrder`, `ListOrders`), what messages go in and out of them, and the field numbers that identify each field on the wire. gRPC itself adds two more shared things: **status codes** (`NotFound`, `InvalidArgument` and so on) and **metadata** (headers). That is everything both languages are guaranteed to agree on.

What the `.proto` does not say is what a value *means*: does an empty status filter mean "all orders" or "orders whose status is the empty string"? How long may a call take? Those are behaviours, not shapes, and each side implements them itself. Most of the surprises in this post come from that gap.

## One source of truth

The `.proto` lives in the Go module. Go generates from it with the same command as before:

```
protoc --go_out=. --go_opt=module=example.com/ordersgrpc \
       --go-grpc_out=. --go-grpc_opt=module=example.com/ordersgrpc \
       proto/orders/v1/orders.proto
```

The Rust crate does not copy the file; its `build.rs` (the build script Cargo runs before compiling) reads it from there. I used **protox**, a protobuf compiler written in Rust, so the build needs no `protoc` binary:

```rust
const PROTO_DIR: &str = "../../../golang/blog-series/go-rust-grpc-interop/proto";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fds = protox::compile(["orders/v1/orders.proto"], [PROTO_DIR])?;
    tonic_prost_build::configure().compile_fds(fds)?;
    Ok(())
}
```

`src/lib.rs` has `tonic::include_proto!("orders.v1")`, which pulls the generated Rust code in. A shared repository, or a tool like `buf` (not run here), can replace that relative path; the point stays the same: edit the proto once, regenerate both sides. I pinned every crate version with `=` so that the build does not change under me.

## Go server, Rust client

First direction. I started the Go server from the previous post and ran a Rust client against it. The key parts of the client:

```rust
let mut c = OrdersServiceClient::connect("http://127.0.0.1:50051").await?;

let mut req = Request::new(CreateOrderRequest { customer: "bob".into(), cents: 300, note: Some("gift".into()) });
req.metadata_mut().insert("x-request-id", "rust-7".parse()?);
let r = c.create_order(req).await?;

let mut stream = c.list_orders(ListOrdersRequest { status: None }).await?.into_inner();
while let Some(o) = stream.message().await? { /* ... */ }
```

(In the demo the address comes from an environment variable and defaults to this one.) The client creates orders, adds a request id as metadata, and lists orders with four different filters. This is its output:

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

Reading it: the first two creates succeeded, and the `header=Some("rust-7")` part shows that the Go interceptor read `x-request-id` from the Rust call and echoed it back. The third create (empty customer) got `InvalidArgument` from the Go server's domain validation, and the status code arrived in Rust as the matching `tonic::Code`. `get 99` is `NotFound`. The four `list` lines show the server stream turning into a `message().await` loop that returns `None` at the end; with no filter (`None`) and with `"new"` we get both orders, with `"paid"` none. The fourth filter, the empty string, returned both orders: remember that, we come back to it. The last two lines are the deadline and the panic case, covered below.

## Rust server, Go client

Second direction. The Rust server implements the generated trait, and the message and the status come back as ordinary Rust values:

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

`ListOrders` returns a boxed `Stream` made with `tokio_stream::iter`, and the `tonic-health` crate provides the standard health service. Now the existing Go client, with no change, against this Rust server:

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

It prints the same as it did against the Go server, apart from one line: the failed create has `header=[]`, because that Rust handler returns the error before it adds the `x-request-id` header. That is a difference in my two implementations, not in the languages. (The doubled spaces inside `order=...` come from how the Go protobuf library prints messages; do not parse that text.)

## What the generators do differently

The two generators map the same proto in the natural way for their language. A proto3 `optional` field becomes `Option<String>` in Rust and `*string` in Go. To see the presence information survive the trip, a small Go program sent three notes to the Rust server: none, an empty string and `"gift"`. The Rust server's log printed what arrived:

```
create rid=- note=None cents=500
create rid=- note=Some("") cents=500
create rid=- note=Some("gift") cents=500
```

Presence survived: Go's nil became `None` and the empty string became `Some("")`. A plain scalar has no presence: the first Go client sent `cents: 0`, and the Rust log shows `cents=0`, but a missing field would show exactly the same.

But presence is only data. Each server decides what it means, and here our two servers decided differently. The same Go program lists orders with three filters (none, `"paid"` and `""`) and prints how many orders each returned. First against the Go server, then against the Rust server (before this, both servers held five orders, all with status `new`):

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

The first line is the same on both: no filter, all five orders. The second is the same too: no order is `paid`. The third line is the difference: the filter `""`. The Go server calls `GetStatus()`, which gives `""` for "unset" as well as for "empty", and treats it as "all". The Rust server sees `Some("")` and compares it with each status; no status equals the empty string, so it returns nothing. Neither server is wrong. This is a contract question, not a language one: the `.proto` cannot tell you, so write down what a present-but-empty value means.

(Our proto has no `enum`. In prost an enum field is stored as an `i32`, so an unknown value from a newer peer should not break decoding; I did not test that here.)

## Deadlines and cancellation

The Go client's `WithTimeout(300ms)` reaches the Rust server as a header. The Rust server printed it for the demo id `slow`, a handler that sleeps for two seconds:

```
get id="slow" grpc-timeout=Some("299986u")
  slow: handler future dropped
```

The `u` means microseconds, so `299986u` is about 300 ms (the exact value changes from run to run). Then the handler future was dropped, and the sleep never finished: the line `slow: finished the sleep` never appeared. My plan had been a `tokio::select!` on a cancellation signal, but I found no such token in tonic's handler API. What the demo shows is that when a call is cancelled, tonic simply drops the handler's future. In Rust, a future that is only waiting at an `.await` stops by itself when it is dropped. The `Guard` struct in the demo prints in its `Drop` function, which is how we see that; a `Drop` guard is also the place for cleanup.

Work that is not part of that future is different. For the id `spawn`, the handler starts a separate `tokio::spawn` task and then sleeps. The client timed out the same way, and the server printed:

```
get id="spawn" grpc-timeout=Some("299335u")
  spawn: handler future dropped
  spawn: background task still ran
```

The handler was dropped, but the spawned task kept running and finished its job a second later. In Go you must watch `ctx.Done()` yourself; in Rust the future is cancelled for you, but spawned tasks, and anything that blocks without an `.await`, are not. I did not test the blocking case.

The Rust client has `Request::set_timeout`. Against the Go server the slow call returned `Cancelled | Timeout expired` (see the output above), not `DeadlineExceeded` like the Go client gets: the tonic client maps its own timeout to `Cancelled`. Check that mapping before you alert on status codes.

## Cross-language gotchas

- **Keep one `.proto` and regenerate both sides in CI.** Copied proto files drift, which is the problem we started with.
- **`optional` tells you presence, not meaning.** Document what empty values mean; our two servers disagreed on `""`.
- **Map errors to status codes in one place per side.** `NotFound` in one language arrives as `NotFound` in the other.
- **Deadlines come from the client.** Set them with a context on the Go side and explicitly (`set_timeout`) on the Rust side, and check how each client reports an expired deadline.
- **A dropped future is not a stopped task.** Spawned work keeps running.

## What's next

The next post in this series is "Calling Rust from Go over FFI". gRPC joins the two languages across a network boundary; FFI joins them inside one process, so Go calls Rust code directly, and the trade-offs are different.
