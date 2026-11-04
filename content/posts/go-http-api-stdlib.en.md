+++
date = '2027-01-03T10:00:00+03:30'
draft = false
title = 'Building an API with net/http in Go'
description = 'Build a JSON API with Go net/http: ServeMux patterns, middleware, safe JSON decoding, validation errors, server timeouts, graceful shutdown and httptest.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "http", "api", "net-http", "middleware"]
cover = { image = "/images/covers/go-http-api-stdlib.png", alt = "Building an API with net/http in Go", hiddenInSingle = true }
+++

The shortest way to start a Go web server is one line: `http.ListenAndServe(":8080", handler)`. It works, and that is the problem, because it hides decisions you have not made yet. It uses a server with all settings at zero, and for timeouts zero means "no limit". A client that sends its request headers one byte at a time can keep a connection, and the goroutine serving it, open for as long as it likes. A bug that panics inside a handler is not reported properly either. And a deploy that restarts the process can cut requests in half.

After [config, structured logging and errors](/posts/go-config-logging-errors/), the `orders` server is still that minimal: one read timeout, no panic protection, no limit on request bodies, no shutdown. This post fixes those one at a time. Since Go 1.22 the standard router understands HTTP methods and path wildcards, so for a small API I skip web frameworks. We used `net/http` in the [URL shortener](/posts/go-mini-project-url-shortener/) too; here we add middleware, safe JSON decoding, timeouts and tests, with the standard library only.

> Everything was re-run with Go 1.27 on macOS (arm64), standard library only. The demo is the previous post's module, evolved. Log lines below have the `time=` field removed. Request IDs and durations vary from run to run; I used random free local ports.

## ServeMux patterns

First, how does a request find its handler? A **handler** is a function that receives the request and writes a response. A router (in `net/http`, the `ServeMux`) chooses which handler runs for which request. Registering routes looks like this:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /orders", /* decode, validate, create */)
mux.HandleFunc("GET /orders/{id}", func(w http.ResponseWriter, r *http.Request) {
	o, err := orders.Get(r.Context(), r.PathValue("id"))
	// ...
})
```

The HTTP method is part of the pattern, and `{id}` is a wildcard whose value you read with `r.PathValue`. The nice side effect is that the mux answers wrong requests for you. I tried a wrong method on a known path and a path that does not exist (headers trimmed to the interesting ones):

```
$ curl -si -X DELETE localhost:8095/orders/1
HTTP/1.1 405 Method Not Allowed
Allow: GET, HEAD
Content-Type: text/plain; charset=utf-8

$ curl -si localhost:8095/nope
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8
```

A known path with the wrong method gives `405` plus an `Allow` header that lists what is allowed. An unknown path gives `404`. Both bodies are plain text, not our JSON; we come back to this in the last section. (The port in these commands is written as `8095`; the real runs used random free ports.)

## Middleware

Some work must happen for every request, whatever the route: give it an ID, log it, survive a panic. Writing that in each handler would be repetition, so Go code uses a **middleware**: a function of type `func(http.Handler) http.Handler`. It receives the next handler and returns a new handler that does something before and/or after calling it. Picture layers of an onion, with the real handler in the centre.

A tiny helper stacks them:

```go
func Chain(h http.Handler, mws ...Middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

return Chain(mux, RequestID, AccessLog, Recover)
```

The first one listed is the outermost layer, so it sees the request first and the response last. Here is what each of the three does:

- `RequestID` is the previous post's code moved into a middleware: it stores the ID in the context with `logging.WithRequestID` and sets the `X-Request-ID` header. Because the `slog` handler already adds `request_id` to every record whose context has one, the other middleware does not need to know the ID.
- `AccessLog` writes one line per request after the handler returns. To print the status code it wraps the `ResponseWriter` in a small struct that remembers the status passed to `WriteHeader`.
- `Recover` is new. A handler that panics would otherwise take the request down with it. `Recover` catches the panic and, instead of writing its own response, reuses the error path from the last post:

```go
defer func() {
	if v := recover(); v != nil {
		writeErr(w, r, fmt.Errorf("panic: %v", v))
	}
}()
next.ServeHTTP(w, r)
```

`writeErr` is the function from the previous post: an unknown error becomes a `500` with fixed text, and the details go only to the log. Note the order: `Recover` is inside `AccessLog`, so even the `500` produced by a panic is logged by the access log. To try it, I added a demo-only `/boom` route that panics:

```
$ curl -si localhost:8095/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: 4a899758

{"error":"internal error"}
```

The server wrote two lines for this request, with the same `request_id` as the header the client received:

```
level=ERROR msg="request failed" method=GET path=/boom status=500 error="panic: something broke" request_id=4a899758
level=INFO msg=request method=GET path=/boom status=500 dur=170µs request_id=4a899758
```

The first line is the error with its cause. The second is the access log, with the status and how long the request took.

What happens without `Recover`? I tested it with a server that panics in a plain `http.ListenAndServe` (`cmd/barepanic`). `net/http` itself catches the panic so the process survives, and it prints a stack trace in the server log. But the client gets no response at all: the connection is just closed, and `curl` exits with code 52 ("empty reply from server").

## Decoding JSON safely

The request body is input from outside, so it deserves distrust. Two things can go wrong: a body that is huge (it would fill memory), and a body with fields you did not expect (a typo that silently does nothing). One small function handles both:

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

`MaxBytesReader` caps how much of the body can be read. `DisallowUnknownFields` turns a typo like `"vip":true` into an error instead of silently ignoring it. Both failures wrap sentinel errors (`errTooBig`, `errBadJSON`), so `statusOf` from the previous post gains one case: `errTooBig` gives `413`. For `422` I added the offending field to the response body, taken from the `ValidationError` the domain already returns. Two requests:

```
$ curl -si -X POST localhost:8095/orders -d '{"customer":"a","cents":1,"vip":true}'
HTTP/1.1 400 Bad Request
{"error":"bad json"}

$ curl -si -X POST localhost:8095/orders -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"invalid order: customer is required","fields":{"customer":"is required"}}
```

The first has an unknown field, so it is a `400`. The client sees only `bad json`, while the log keeps the reason (`bad json: json: unknown field "vip"`). The second is well-formed JSON that breaks a business rule, so it is a `422`, and `fields` tells the client which field to fix. A 2 MiB body got `413 Request Entity Too Large` with `{"error":"body too large"}`. One more detail: the domain reports only the first broken rule, so in the second request `cents` is not mentioned until `customer` is fixed. When I sent `{"customer":"a","cents":0}`, the response named `cents`.

## Server timeouts

Now back to the problem from the beginning. A zero timeout means no limit, and a client that sends headers one byte at a time exploits it. This is called **{{< term "slowloris" "slowloris" >}}**: each slow connection holds a goroutine and a {{< term "file-descriptor" "file descriptor" >}}, and enough of them exhaust the server.

`http.Server` has four timeouts, and each protects a different phase of a request:

- `ReadHeaderTimeout`: how long the client has to send the request headers.
- `ReadTimeout`: how long to read the whole request, headers and body.
- `WriteTimeout`: how long to write the response.
- `IdleTimeout`: how long an idle {{< term "keep-alive" "keep-alive" >}} connection stays open waiting for the next request.

Last time `Config` had one `ReadTimeout`, which `main` passed as `ReadHeaderTimeout`. Now `Config` has all four, each with a default, a parser that rejects zero (because zero would mean "no limit" again), and one cross-check:

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

The cross-check says the header deadline cannot be longer than the deadline for the whole request, which would make no sense. `main` just copies the four values into the server:

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

With `ORDERS_WRITE_TIMEOUT=0s ORDERS_READ_HEADER_TIMEOUT=9s`, startup printed both problems and exited with code 2:

```
invalid configuration:
ORDERS_WRITE_TIMEOUT: must be positive
ORDERS_READ_HEADER_TIMEOUT: must not exceed ORDERS_READ_TIMEOUT
```

To see the timeout work, I wrote a small client, `cmd/slowheader`. It sends a request line and a `Host` header, then one extra byte every 500 ms, and never finishes the headers. It gives up after 8 seconds. I pointed it at this server (with the defaults) and at a second server that uses plain `http.ListenAndServe`, so a zero-value server:

```
$ slowheader localhost:8095
server reacted after 2.0s: read 103 bytes, err=<nil>
"HTTP/1.1 400 Bad Request\r\n...\r\n\r\n400 Bad Request"

$ slowheader localhost:8081
still connected after 8.0s
```

(The second line of the first output is shortened in the middle.) With `ReadHeaderTimeout` at 2 seconds, the configured server answered `400 Bad Request` and hung up after 2.0 seconds. The zero-value server was still waiting when my client gave up at 8 seconds.

## Graceful shutdown

Restarting a server should not cut running requests in half. The earlier post [graceful shutdown with workers](/posts/go-graceful-shutdown-workers/) explains the idea in detail for background workers. For an HTTP server it is a few lines:

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

The server runs in a goroutine, and `main` waits until a signal cancels `ctx`. `Shutdown` then stops accepting new connections and waits for requests that are in flight, up to the deadline of the context we give it. `ListenAndServe` returns `http.ErrServerClosed` immediately after `Shutdown` is called, so that error is the normal case, not a failure. I sent `SIGTERM` to the demo and it logged `shutting down` and then `stopped`. Nothing was in flight at that moment, so this run does not show the waiting; it only shows that the signal path works.

## Testing handlers

`httptest.NewServer` starts the real handler chain on a random local port, so a test talks to it with an ordinary HTTP client:

```go
svc := service.New(memory.New(), quiet, 1_000_000)
srv := httptest.NewServer(transport.NewHandler(svc))
defer srv.Close()
resp, _ := http.Post(srv.URL+"/orders", "application/json", strings.NewReader(body))
```

A table test sends eight failing cases (unknown field, validation, oversized body, not found, wrong method, unknown path, storage failure, panic) and checks the status code of each. A second test covers the timeout defaults and the config validation. I ran everything with the race detector on (times vary):

```
$ go test -race ./...
ok  	example.com/orders/internal/config	2.313s
ok  	example.com/orders/internal/service	2.318s
ok  	example.com/orders/internal/transport/http	2.550s
```

## Where net/http surprises you

- The mux's own `404` and `405` answers are plain text. They still get a request ID and an access log line (I saw both above), but if your clients expect JSON, wrap them.
- `WriteTimeout` also limits how long a handler may take to write its answer, so a long download or a stream needs a larger value, or per-request deadlines with `http.ResponseController`. Check the `net/http` documentation for how it interacts with your handlers.
- `MaxBytesReader` limits what you read. Check the error it returns, or an oversized body looks like a generic decode failure.
- Middleware order matters. `Recover` sits inside `AccessLog` so that the `500` is still logged; swapped, the access log would never see the panic's status.
- The status-recording wrapper hides optional interfaces such as `http.Flusher`. Its `Unwrap() http.ResponseWriter` method keeps `http.ResponseController` working through it.

## What's next

Next is "Postgres with pgx and sqlc in Go". All the data still lives in an in-memory map, and a real service needs a database.
