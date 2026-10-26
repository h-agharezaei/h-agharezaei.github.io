+++
date = '2027-01-03T10:00:00+03:30'
draft = false
title = 'Building an API with net/http in Go'
description = 'Build a JSON API with Go net/http: ServeMux patterns, middleware, safe JSON decoding, validation errors, server timeouts, graceful shutdown and httptest.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "http", "api", "net-http", "middleware"]
cover = { image = "/images/covers/go-http-api-stdlib.png", alt = "Building an API with net/http in Go", hiddenInSingle = true }
+++

In the [previous post](/posts/go-config-logging-errors/) the `orders` service got a typed `Config` loaded from the environment, `slog` with text and JSON handlers, a request ID carried in the context, and one function (`statusOf`) that maps errors to HTTP statuses. The server itself was still minimal: one read timeout, no panic protection, no body limit, no shutdown. Now we build the HTTP layer on top, standard library only. Since Go 1.22 the router understands methods and wildcards, so for a small API I skip frameworks. We used `net/http` in the [URL shortener](/posts/go-mini-project-url-shortener/) too; here we add middleware, safe decoding, timeouts and tests.

> Everything was run with Go 1.26 on macOS (arm64), standard library only. The demo is the previous post's module, evolved. Log lines below have the `time=` field removed.

## ServeMux patterns

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /orders", /* decode, validate, create */)
mux.HandleFunc("GET /orders/{id}", func(w http.ResponseWriter, r *http.Request) {
	o, err := orders.Get(r.Context(), r.PathValue("id"))
	// ...
})
```

The method is part of the pattern, and `{id}` is a wildcard you read with `r.PathValue`. The mux also answers wrong requests for you:

```
$ curl -si -X DELETE localhost:8095/orders/1
HTTP/1.1 405 Method Not Allowed
Allow: GET, HEAD
Content-Type: text/plain; charset=utf-8

$ curl -si localhost:8095/nope
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8
```

A known path with the wrong method gives `405` plus an `Allow` header; an unknown path gives `404`. Both bodies are plain text, not our JSON.

## Middleware

A middleware is a `func(http.Handler) http.Handler`: it receives the next handler and returns a new one. A tiny helper composes them:

```go
func Chain(h http.Handler, mws ...Middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

return Chain(mux, RequestID, AccessLog, Recover)
```

The first one listed is the outermost. `RequestID` is the previous post's code moved into a middleware: it stores the ID with `logging.WithRequestID` and sets `X-Request-ID`. Since the `slog` handler adds `request_id` to every record whose context has one, `AccessLog` need not know the ID. It wraps the `ResponseWriter` to remember the status and logs after the handler returns. `Recover` is new, and it reuses the error path instead of writing its own response:

```go
defer func() {
	if v := recover(); v != nil {
		writeErr(w, r, fmt.Errorf("panic: %v", v))
	}
}()
next.ServeHTTP(w, r)
```

`writeErr` is the previous post's function: an unknown error becomes a `500` with fixed text, and details only reach the log. I added a demo-only `/boom` route that panics:

```
$ curl -si localhost:8095/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: 2d45c299

{"error":"internal error"}

level=ERROR msg="request failed" method=GET path=/boom status=500 error="panic: something broke" request_id=2d45c299
level=INFO msg=request method=GET path=/boom status=500 dur=96.25µs request_id=2d45c299
```

Without it, `net/http` recovers the panic but just drops the connection; curl exits with code 52 ("empty reply"), checked with `cmd/barepanic`.

## Decoding JSON safely

```go
func decode(w http.ResponseWriter, r *http.Request, dst any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBody) // 1 MiB
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			return fmt.Errorf("%w: %v", errTooBig, err)
		}
		return fmt.Errorf("%w: %v", errBadJSON, err)
	}
	return nil
}
```

`MaxBytesReader` caps the body, and `DisallowUnknownFields` turns a typo like `"vip":true` into an error instead of silently ignoring it. Both failures wrap sentinel errors, so `statusOf` gains one case: `errTooBig` gives `413`. For `422` I added the offending field to the response, taken from the `ValidationError` the domain already returns:

```
$ curl -si -X POST localhost:8095/orders -d '{"customer":"a","cents":1,"vip":true}'
HTTP/1.1 400 Bad Request
{"error":"bad json"}

$ curl -si -X POST localhost:8095/orders -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"invalid order: customer is required","fields":{"customer":"is required"}}
```

The log keeps the reason (`unknown field "vip"`). A 2 MiB body got `413 Request Entity Too Large`. The domain reports only the first broken rule, so `cents` is not mentioned until `customer` is fixed.

## Server timeouts

`http.ListenAndServe` uses a zero-value `http.Server`, and zero means no limit. A client can send headers one byte at a time and hold a goroutine and file descriptor forever; this is **slowloris**. Last time `Config` had one `ReadTimeout`, used as `ReadHeaderTimeout`. Now it has all four, each with a default, a parser that rejects zero, and one cross-check:

```go
positive := func(key, def string) time.Duration {
	d, err := time.ParseDuration(str(key, def))
	if err == nil && d <= 0 {
		err = errors.New("must be positive")
	}
	if err != nil {
		fail(key, err)
	}
	return d
}
c.ReadHeaderTimeout = positive("ORDERS_READ_HEADER_TIMEOUT", "2s")
c.ReadTimeout = positive("ORDERS_READ_TIMEOUT", "5s")
c.WriteTimeout = positive("ORDERS_WRITE_TIMEOUT", "10s")
c.IdleTimeout = positive("ORDERS_IDLE_TIMEOUT", "60s")
if c.ReadHeaderTimeout > c.ReadTimeout {
	fail("ORDERS_READ_HEADER_TIMEOUT", errors.New("must not exceed ORDERS_READ_TIMEOUT"))
}
```

`main` just copies them into the server:

```go
srv := &http.Server{
	Addr:              cfg.Addr,
	Handler:           transport.NewHandler(svc),
	ReadHeaderTimeout: cfg.ReadHeaderTimeout,
	ReadTimeout:       cfg.ReadTimeout,
	WriteTimeout:      cfg.WriteTimeout,
	IdleTimeout:       cfg.IdleTimeout,
}
```

With `ORDERS_WRITE_TIMEOUT=0s ORDERS_READ_HEADER_TIMEOUT=9s` startup printed both problems and exited with code 2. To see the timeout work, `cmd/slowheader` sends a request line and a `Host` header, then one extra byte every 500 ms, never finishing the headers. I pointed it at this server (defaults) and at a second one using plain `http.ListenAndServe`:

```
$ slowheader localhost:8095
server reacted after 2.0s: read 103 bytes, err=<nil>
"HTTP/1.1 400 Bad Request\r\n...\r\n\r\n400 Bad Request"

$ slowheader localhost:8081
still connected after 8.0s
```

With the configured `ReadHeaderTimeout` of 2s the server answered and hung up. The zero-value server was still waiting when my client gave up at 8s.

## Graceful shutdown

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
go func() {
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server failed", "err", err)
		os.Exit(1)
	}
}()
<-ctx.Done()
slog.Info("shutting down")
shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
```

`Shutdown` stops accepting connections and waits for in-flight requests, up to the context deadline. `ListenAndServe` returns `http.ErrServerClosed` right away, so that is not a failure. Workers are covered in [graceful shutdown with workers](/posts/go-graceful-shutdown-workers/). After `SIGTERM` the demo logged `shutting down` and `stopped`, with nothing in flight.

## Testing handlers

`httptest.NewServer` runs the real handler chain on a random port:

```go
svc := service.New(memory.New(), quiet, 1_000_000)
srv := httptest.NewServer(transport.NewHandler(svc))
defer srv.Close()
resp, _ := http.Post(srv.URL+"/orders", "application/json", strings.NewReader(body))
```

A table test sends eight failing cases (unknown field, validation, oversized body, not found, wrong method, unknown path, storage failure, panic) and checks the status codes. A config test covers the timeouts.

```
$ go test -race ./...
ok  	example.com/orders/internal/config
ok  	example.com/orders/internal/service
ok  	example.com/orders/internal/transport/http
```

## A few things to watch

- The mux's own `404` and `405` are plain text. They still get a request ID and a log line, but if clients expect JSON, wrap them.
- `WriteTimeout` also covers slow handlers: a long download or stream needs a larger value or `http.ResponseController` deadlines.
- `MaxBytesReader` limits what you read. Check the error, or an oversized body looks like a generic decode failure.
- Middleware order matters: `Recover` sits inside `AccessLog`, so the `500` is still logged.
- The status-recording wrapper hides optional interfaces like `http.Flusher`; its `Unwrap() http.ResponseWriter` method keeps `http.ResponseController` working.

## What's next

Next: Postgres with pgx and sqlc in Go, where the in-memory store gives way to a real database.
