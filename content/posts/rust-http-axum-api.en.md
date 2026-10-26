+++
date = '2027-01-21T10:00:00+03:30'
draft = false
title = 'Building an API with Axum in Rust'
description = 'Build a JSON orders API with Rust Axum: routes, extractors, shared state, an error enum, tower-http layers, graceful shutdown on SIGTERM and oneshot tests.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "axum", "http", "api", "tokio", "tower", "intermediate"]
cover = { image = "/images/covers/rust-http-axum-api.png", alt = "Building an API with Axum in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-serde-json/) we learned serde and JSON, and promised to use those types for request and response bodies. This is that post. On top of the Tokio runtime from [async Rust with Tokio](/posts/rust-async-tokio/) we build the same small orders API as in the Go counterpart, [Building an API with net/http in Go](/posts/go-http-api-stdlib/): create, get by id, list, a `422` for validation errors and a `404` for unknown orders. I use **Axum**, a thin web framework on top of Hyper and Tower.

> I ran everything with Rust 1.90, `axum` 0.8.9, `tokio` 1.54.1, `tower-http` 0.7.1 and `tower` 0.5.3, pinned in `Cargo.lock`. Outputs are copied from real runs of a local demo; headers like `date` are removed.

## Router, handlers, extractors

A handler is an async function. Its arguments are **extractors**, which pull data out of the request, and its return type is anything that implements `IntoResponse`:

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

`Path` reads `{id}`, `Query` reads `?customer=x&limit=2` into a struct, `Json<T>` reads the body with the serde rules from the last post, and `State` hands you shared data. The last extractor may consume the body, so `Json` goes last. `Order` is `Serialize`; `CreateOrder` is `Deserialize` with `deny_unknown_fields`.

## State

```rust
#[derive(Default)]
pub struct AppState { orders: Mutex<Vec<Order>> }
pub type Shared = Arc<AppState>;
```

`State` needs a `Clone` type, and `Arc` gives that cheaply. I used `std::sync::Mutex`, which is fine because no `.await` happens while the lock is held. If you must hold a lock across an await, use `tokio::sync::Mutex`. The id is the length plus one, as a string like in Go.

## One error type

In Go one function (`statusOf`) mapped errors to statuses. In Rust that job belongs to an enum that implements `IntoResponse`; then handlers return `Result<T, ApiError>` and `?` does the rest:

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

As in Go, the detail of a `500` goes to the log, never to the client. A tuple `(StatusCode, Json<T>)` is itself a response. Real runs:

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

Unlike the Go version, validation reports both broken fields at once. `/broken` is a demo-only route that returns `ApiError::Internal`. `?customer=sara` and `?limit=1` filtered the list as expected.

## What the built-in extractors reject

When an extractor fails, Axum answers for you, with a plain-text body:

```text
{"customer":"a",                 -> 400 Failed to parse the request body as JSON: EOF while parsing a value at line 1 column 16
{"customer":"a","cents":"12"}    -> 422 Failed to deserialize the JSON body into the target type: cents: invalid type: string "12", expected i64 at line 1 column 28
{"customer":"a"}                 -> 422 ... missing field `cents` at line 1 column 16
{"customer":"a","cents":1,"vip":true} -> 422 ... vip: unknown field `vip`, expected `customer` or `cents` at line 1 column 31
(no content-type header)         -> 415 Expected request with `Content-Type: application/json`
/orders?limit=abc                -> 400 Failed to deserialize query string: limit: invalid digit found in string
```

So broken syntax is `400`, valid JSON of the wrong shape is `422`, and a missing header is `415`. These bodies are text, not our JSON. If clients expect one error format, wrap the extractor with your own that converts the rejection into `ApiError`. I left it as is, to show the defaults. Routing errors differ too: `DELETE /orders/1` gave `405` with `allow: GET,HEAD`, and an unknown path gave `404` with an empty body.

## Layers

Axum is built on Tower, so middleware is a **layer**. Three from `tower-http`:

```rust
.layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, timeout))
.layer(PropagateRequestIdLayer::new(x_request_id.clone()))
.layer(TraceLayer::new_for_http().make_span_with(/* span with request_id */))
.layer(SetRequestIdLayer::new(x_request_id, Counter::default()))
```

The last layer added is the outermost, the opposite of the Go `Chain` helper where the first listed is outermost. So `SetRequestIdLayer` runs first, with a small `MakeRequestId` of mine that counts (`req-1`, ...). Results:

```text
$ curl -si localhost:8096/slow?ms=2000     # timeout is 1s
HTTP/1.1 408 Request Timeout
x-request-id: req-12

$ curl -si -H 'x-request-id: mine-1' localhost:8096/orders/1
HTTP/1.1 200 OK
x-request-id: mine-1
```

A caller's id is kept; otherwise one is generated. In the log, the `500` from `/broken` carries the id from the span:

```text
ERROR request{method=GET path=/broken request_id="req-1"}: request failed detail=disk on fire
ERROR request{method=GET path=/broken request_id="req-1"}: response failed classification=Status code: 500 Internal Server Error latency=0 ms
```

With the default filter only failures show; successful requests appear when you enable `DEBUG` for `tower_http`.

## Graceful shutdown

```rust
axum::serve(listener, router)
    .with_graceful_shutdown(shutdown_signal())
    .await?;
```

`shutdown_signal` waits for Ctrl-C or SIGTERM (`tokio::signal::unix`) in a `select!`. I started a request taking 800 ms, sent SIGTERM after 200 ms, then tried a new request:

```text
new request: exit=7            # connection refused
done
 -> 200 after 0.803108s
 INFO shutting down
 INFO stopped
```

The listener stopped, the in-flight request finished with `200`, and the process exited. `ps` showed no process left afterwards.

## Tests without a port

A `Router` is a Tower service, so `oneshot` calls it directly:

```rust
use tower::ServiceExt; // for oneshot

let res = app.clone().oneshot(post(r#"{"customer":"roham","cents":2500}"#)).await?;
assert_eq!(res.status(), StatusCode::CREATED);
```

`clone()` is cheap and shares the state, so a second `oneshot` can read the order back. A table of seven cases (validation, bad JSON, wrong type, 404, 405, 500, timeout) plus the request-id test gave `3 passed`.

## A few things to watch

- Extractor order matters: `Json` (or any body extractor) must be last.
- Default rejections are plain text; decide whether your API needs JSON errors.
- Never hold a `std::sync::Mutex` guard across `.await`.
- Layer order is reversed compared to the Go `Chain` helper.
- Axum 0.8 writes path parameters as `{id}`; the `:id` form you see in older tutorials belongs to earlier versions.

## Exercise

1. Add `PUT /orders/{id}/pay` that sets the status to `paid` and returns `404` for unknown ids.
2. Replace `Json` with a wrapper extractor that turns rejections into `ApiError`.

## What's next

Next we replace the in-memory store with a real database: databases with SQLx in Rust.
