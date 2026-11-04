+++
date = '2027-01-21T10:00:00+03:30'
draft = false
title = 'Building an API with Axum in Rust'
description = 'Build a JSON orders API with Rust Axum: routes, extractors, shared state, an error enum, tower-http layers, graceful shutdown on SIGTERM and oneshot tests.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "axum", "http", "api", "tokio", "tower", "intermediate"]
cover = { image = "/images/covers/rust-http-axum-api.png", alt = "Building an API with Axum in Rust", hiddenInSingle = true }
+++

What should a server answer when a client sends broken JSON? When the JSON is fine but a field has the wrong type? When the order the client asks for does not exist? An API is not only the happy path. Half of its quality is in these answers: the right status code (`400`, `422`, `404`), and a body the client can act on.

In this post we build a small orders API in Rust and watch it answer exactly those questions. It uses the types from [Serde and JSON in Rust](/posts/rust-serde-json/) as request and response bodies, and it runs on the Tokio runtime from [async/await and Tokio in Rust](/posts/rust-async-tokio/). It is the same API as the Go counterpart, [Building an API with net/http in Go](/posts/go-http-api-stdlib/): create an order, get one by id, list orders, a `422` for validation errors and a `404` for unknown orders. This time the web framework is **Axum**, a thin layer on top of Hyper (an HTTP implementation) and Tower (a library of reusable middleware).

> I ran everything with Rust 1.90, `axum` 0.8.9, `tokio` 1.54.1, `tower-http` 0.7.1 and `tower` 0.5.3, as pinned in the demo's `Cargo.lock`. I re-ran the server and the tests for this version of the post, on a random free local port, and the outputs below are copied from those runs. Headers such as `date` and `content-length` are removed. Request ids such as `req-5` depend on how many requests came before, so they vary.

## A handler, and what an extractor is

A **handler** is an async function that receives a request and returns a response. Axum has a nice trick for what comes in and goes out. Each *argument* of the handler is an **extractor**: a type that knows how to pull one piece out of the request, such as the path, the query string or the body. Whatever the function *returns* only has to implement a trait called `IntoResponse`, which says how to turn the value into an HTTP response.

Here is how the three routes of our API are declared, and the signature of one handler:

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

`get_order` asks for two things. `Path(id)` extracts the `{id}` part of the URL, and `State(st)` hands over the data shared by all requests (more on that in a moment). The other extractors we use:

- `Query<T>` reads the query string, for example `?customer=sara&limit=2`, into a struct `T`.
- `Json<T>` reads the request body as JSON into `T`, using exactly the serde rules from the last post.

One rule: the body can be consumed only once, so an extractor that reads the body (`Json`) must be the last argument. In the demo, `Order` is `Serialize` (we only send it) and `CreateOrder` is `Deserialize` with `deny_unknown_fields` (we only receive it, and we want typos rejected).

## Shared state

Every request needs the list of orders, and requests are handled concurrently, possibly on different threads. So the store has to be shared and protected:

```rust
#[derive(Default)]
pub struct AppState { orders: Mutex<Vec<Order>> }
pub type Shared = Arc<AppState>;
```

This is the {{< term "arc" "Arc" >}} plus {{< term "rust-mutex" "Mutex" >}} pattern from the post on [threads](/posts/rust-concurrency-threads/): the `Arc` lets every handler own the state, and the `Mutex` lets one at a time change it. Axum asks the state type to be cheap to `Clone`, and cloning an `Arc` only bumps a counter. I used `std::sync::Mutex`. That is fine here because no `.await` happens while the lock is held; if you ever must hold a lock across an await, use `tokio::sync::Mutex` instead. The order id is the number of orders plus one, written as a string, as in the Go version. It is a demo store; the next post replaces it with a real database.

## One error type for the whole API

When something goes wrong in a handler, the client needs the right status code and a body in a consistent format. In the Go version a single function (`statusOf`) mapped errors to statuses. In Rust the same job goes to an enum that implements `IntoResponse`. Then every handler can return `Result<T, ApiError>`, and the `?` operator does the rest, because axum turns the `Err` side into a response too:

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

Three things to notice. A tuple `(StatusCode, Json<T>)` is already a valid response, which keeps each arm short. `Validation` carries a map from field name to message, so the client can show each problem next to its field. And `Internal` keeps its detail for the log and sends the client only `internal error`: as in the Go version, what went wrong inside your server is not the client's business.

Now the real runs. I started the server on a random port and called it with `curl` (`-s` silent, `-i` to print the status line and headers). The first request creates an order, the second asks for an id that does not exist, the third sends an order that breaks two rules, and the fourth calls `/broken`, a route that exists only in the demo and always returns `ApiError::Internal`:

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

Each answer has the status code we planned and the same JSON shape. Notice that the validation response lists *both* broken fields; the Go version reports only the first broken rule. The `500` body says nothing about the disk; the real reason went to the log (we will see it below). I also checked that `?customer=sara` and `?limit=1` filter the list as expected.

## What the built-in extractors reject

We did not write any code for bad JSON, a wrong type or a missing header. Still, the server answers them. When an extractor fails, axum replies for you with a *rejection*: a status code and a plain-text message. This is what the demo returned (`->` separates what I sent from what came back):

```text
{"customer":"a",                      -> 400 Failed to parse the request body as JSON: EOF while parsing a value at line 1 column 16
{"customer":"a","cents":"12"}         -> 422 Failed to deserialize the JSON body into the target type: cents: invalid type: string "12", expected i64 at line 1 column 28
{"customer":"a"}                      -> 422 ... missing field `cents` at line 1 column 16
{"customer":"a","cents":1,"vip":true} -> 422 ... vip: unknown field `vip`, expected `customer` or `cents` at line 1 column 31
(no content-type header)              -> 415 Expected request with `Content-Type: application/json`
/orders?limit=abc                     -> 400 Failed to deserialize query string: limit: invalid digit found in string
```

Look at how the status code splits the problems in two. Text that is not JSON at all is `400`. Text that is valid JSON but does not fit our type is `422`; the message after it is the serde error from the previous post, so you already know how to read it. A missing `content-type: application/json` header is `415`. A bad query string is `400`.

The bodies are plain text, not our `{"error": ...}` format. If your clients expect one error format everywhere, write a small wrapper around `Json` that converts the rejection into `ApiError`. I left the defaults as they are, to show what you get for free. (One difference from the Go version: there a body with an unknown field was a `400`, here it is a `422`.)

Routing mistakes behave a little differently, and they have no body at all. `DELETE /orders/1` returned `405 Method Not Allowed` with the header `allow: GET,HEAD`, and an unknown path returned `404` with an empty body.

## Layers: middleware around the whole router

Some things should apply to every request: a timeout, a request id, logging. In Axum these are **layers**. Axum is built on Tower, in which a service is a thing that takes a request and returns a response, and a layer wraps one service in another. The crate `tower-http` provides ready-made layers. We use four:

```rust
.layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, timeout))
.layer(PropagateRequestIdLayer::new(x_request_id.clone()))
.layer(TraceLayer::new_for_http().make_span_with(/* span with request_id */))
.layer(SetRequestIdLayer::new(x_request_id, Counter::default()))
```

The order needs care. Each `.layer(...)` wraps everything above it, so the *last* one added is the *outermost* and sees the request first. That is the opposite of the Go `Chain` helper, where the first one listed is the outermost. So here `SetRequestIdLayer` runs first. It gives each request an id (a small generator of mine that counts: `req-1`, `req-2`, ...) unless the caller already sent one. Then `TraceLayer` logs with that id, `PropagateRequestIdLayer` copies the id onto the response, and `TimeoutLayer` cuts off a handler that takes too long (one second in the demo).

To try it, `/slow?ms=2000` sleeps for two seconds, longer than the timeout. The second call sends its own request id:

```text
$ curl -si localhost:$PORT/slow?ms=2000
HTTP/1.1 408 Request Timeout
x-request-id: req-17

$ curl -si -H 'x-request-id: mine-1' localhost:$PORT/orders/1
HTTP/1.1 200 OK
x-request-id: mine-1
```

The slow request was answered with `408` after the timeout. A caller's id (`mine-1`) is kept and echoed back; when there is none, the server makes one. The same id appears in the log, so you can follow one request through the system. This is the log of the `500` from `/broken` above:

```text
ERROR request{method=GET path=/broken request_id="req-5"}: request failed detail=disk on fire
ERROR request{method=GET path=/broken request_id="req-5"}: response failed classification=Status code: 500 Internal Server Error latency=0 ms
```

The first line is the one we wrote in `ApiError::Internal`: here is the detail the client never saw (`disk on fire`). The second is from `TraceLayer`, noting that the response was a failure. Both carry the request id. With the default log filter only failures show up; successful requests appear when you enable `DEBUG` for `tower_http`.

## Graceful shutdown

A deploy sends your process `SIGTERM`. If the server just dies, every request in flight is cut in half. With Axum you attach a shutdown signal to the server:

```rust
axum::serve(listener, router)
    .with_graceful_shutdown(shutdown_signal())
    .await?;
```

`shutdown_signal` is a function in `main.rs` that waits for Ctrl-C or `SIGTERM` (using `tokio::signal::unix`) inside a `select!`, which finishes as soon as either happens. When it does, the server stops accepting connections and waits for the running requests. {{< term "graceful-shutdown" "Graceful shutdown" >}} is exactly this. To test it, I started a request that takes 800 ms, sent `SIGTERM` to the server after 200 ms, and then tried a new request:

```text
new request: exit=7
 -> 200 after 0.803547s
 INFO shutting down
 INFO stopped
```

`exit=7` is curl saying "connection refused": the listener was already closed, so the new request was turned away. The old request still finished with `200` after about 0.8 seconds, which proves it was not cut. Then the log shows the server announcing the shutdown and stopping, and the process exited. (The time `0.80…s` varies a little from run to run.) `ps` showed no process of mine left afterwards.

## Tests without opening a port

A `Router` is a Tower service, and a Tower service can be called as a plain function. So tests do not need a socket at all: `oneshot` sends one request straight into the router.

```rust
use tower::ServiceExt; // for oneshot

let res = app.clone().oneshot(post(r#"{"customer":"roham","cents":2500}"#)).await?;
assert_eq!(res.status(), StatusCode::CREATED);
```

`clone()` of a router is cheap and shares the same state, so a second `oneshot` on the clone can read the order back. The demo has three tests: create then get; a table of seven error cases (validation, bad JSON, wrong type, 404, 405, 500 and timeout, each with its expected status); and one that checks the request id is echoed. `cargo test` reported `3 passed`.

## Where Axum surprises you

- **Extractor order matters.** `Json` (or any extractor that reads the body) must be last, or the code does not compile.
- **Default rejections are plain text.** Decide early whether your API needs JSON errors, and wrap the extractor if it does.
- **Do not hold a `std::sync::Mutex` guard across `.await`.** The future stops being `Send` and the compiler refuses it, as in the Tokio post.
- **Layer order is reversed from what you may expect.** The last `.layer(...)` is the outermost.
- **Path syntax changed.** Axum 0.8 writes path parameters as `{id}`; the `:id` form you see in older tutorials belongs to earlier versions.

## Exercise

1. Add `PUT /orders/{id}/pay` that sets the status to `paid` and returns `404` for unknown ids.
2. Replace `Json` with a wrapper extractor that turns rejections into `ApiError`, so that a broken body also gets the `{"error": ...}` format.

## What's next

The in-memory list is lost on every restart, so the next post, *Databases with SQLx in Rust*, replaces it with a real Postgres database.
