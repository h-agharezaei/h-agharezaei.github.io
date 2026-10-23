+++
date = '2026-12-28T10:00:00+03:30'
draft = false
title = 'Config, structured logging and errors in Go'
description = 'Typed config from environment variables, slog with text and JSON handlers and request IDs, and mapping domain errors to HTTP status codes in one place.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "slog", "config", "errors"]
cover = { image = "/images/covers/go-config-logging-errors.png", alt = "Config, structured logging and errors in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-project-layout-clean-architecture/) we built a small `orders` service with a hard-coded `:8080` and a bare `log.Println`. Here we fix both and add the third thing every real service needs: a deliberate policy for errors at the boundary. The code is the same module, standard library only, evolved in place.

> Everything was run with Go 1.26 on macOS (arm64).

## Config: one struct, loaded once

The rule: read the environment in exactly one place, into a typed struct, and fail at startup if anything is wrong.

```go
type Config struct {
	Addr        string
	LogLevel    slog.Level
	LogFormat   string // "text" or "json"
	ReadTimeout time.Duration
	MaxCents    int64
	DBPassword  Secret
}
```

`Load` uses `os.LookupEnv`, applies defaults, parses, and collects every problem instead of stopping at the first:

```go
fail := func(key string, err error) { errs = append(errs, fmt.Errorf("%s: %w", key, err)) }
// ...
if c.ReadTimeout, err = time.ParseDuration(str("ORDERS_READ_TIMEOUT", "5s")); err != nil {
	fail("ORDERS_READ_TIMEOUT", err)
}
// ...
return c, errors.Join(errs...)
```

`str` is a tiny helper that returns the variable or its default. With four bad values and a missing password, `main` prints one report and exits with code 2:

```
$ ORDERS_LOG_LEVEL=loud ORDERS_LOG_FORMAT=yaml ORDERS_READ_TIMEOUT=5 ORDERS_MAX_CENTS=lots ./orders
invalid configuration:
ORDERS_LOG_LEVEL: slog: level string "loud": unknown name
ORDERS_LOG_FORMAT: must be text or json, got "yaml"
ORDERS_READ_TIMEOUT: time: missing unit in duration "5"
ORDERS_MAX_CENTS: strconv.ParseInt: parsing "lots": invalid syntax
ORDERS_DB_PASSWORD: required
```

`errors.Join` joins the messages with newlines, so the operator fixes everything in one deploy instead of five. No config library needed.

## Secrets that cannot leak

`Secret` is a string type with a `LogValue` method, which makes it a `slog.LogValuer`:

```go
type Secret string

func (Secret) LogValue() slog.Value { return slog.StringValue("[REDACTED]") }
```

I tested the limits of this with a throwaway program:

```
level=INFO msg=direct pw=[REDACTED]
level=INFO msg="in struct" cfg="{User:app Pw:s3cr3t-pw}"
Println: s3cr3t-pw
```

Redaction works only when slog sees the `Secret` itself. Inside a plain struct, or with `Println`, the value leaks. So `Config` also implements `LogValue` and lists its fields explicitly, which is what the startup log uses.

## slog: handlers, levels, attributes

`log/slog` separates the API (`Info`, `With`, `Group`) from the handler that formats records. Config picks the handler, and `SetDefault` makes it the global logger (it also redirects the old `log` package):

```go
func New(w io.Writer, format string, level slog.Level) *slog.Logger {
	opts := &slog.HandlerOptions{Level: level}
	var h slog.Handler = slog.NewTextHandler(w, opts)
	if format == "json" {
		h = slog.NewJSONHandler(w, opts)
	}
	return slog.New(ctxHandler{h})
}
```

`main` then calls `slog.SetDefault(logger)` and gives the service `logger.With("component", "service")`, so every line from that layer carries the attribute. Inside the service:

```go
s.log.LogAttrs(ctx, slog.LevelInfo, "order created",
	slog.Group("order", slog.String("id", o.ID), slog.Int64("cents", o.Cents)))
```

`LogAttrs` takes only typed `Attr`s, so it avoids the odd-number-of-arguments mistake of key/value lists. With `ORDERS_LOG_LEVEL=warn` the "order created" line disappeared and only the warning for a missing order remained. Startup in text mode (the secret is redacted):

```
level=INFO msg=starting config.addr=:8091 config.log_level=INFO config.log_format=text config.read_timeout=5s config.max_cents=1000000 config.db_password=[REDACTED]
```

(I dropped the `time=` field from the output for width.) In JSON the same record nests the group, but note that the duration becomes nanoseconds: `"read_timeout":5000000000`.

## A request ID through the context

A small middleware generates an ID, stores it in the context and echoes it as `X-Request-ID`. The handler wrapper `ctxHandler` embeds the real handler and adds `request_id` to every record whose context carries one:

```go
func (h ctxHandler) Handle(ctx context.Context, r slog.Record) error {
	if id := RequestID(ctx); id != "" {
		r.AddAttrs(slog.String("request_id", id))
	}
	return h.Handler.Handle(ctx, r)
}
```

It also overrides `WithAttrs` and `WithGroup` to re-wrap the result, otherwise `logger.With(...)` would silently drop the wrapper. For this to work you must pass the context: `LogAttrs(ctx, ...)` or `InfoContext(ctx, ...)`, not plain `Info`.

## Errors at the boundary

The basics are in [functions, defer and errors](/posts/go-functions-defer-errors/); here is the policy. The domain owns sentinels and one custom type that says which field is wrong:

```go
type ValidationError struct{ Field, Reason string }

func (e *ValidationError) Error() string { return fmt.Sprintf("invalid order: %s %s", e.Field, e.Reason) }
func (e *ValidationError) Unwrap() error { return ErrInvalidOrder }
```

The service adds context with `%w`, for example `fmt.Errorf("get order %s: %w", id, err)`. The transport layer decides the status code in one function:

```go
func statusOf(err error) (int, string) {
	var ve *domain.ValidationError
	switch {
	case errors.As(err, &ve):
		return http.StatusUnprocessableEntity, ve.Error()
	case errors.Is(err, domain.ErrNotFound):
		return http.StatusNotFound, domain.ErrNotFound.Error()
	default:
		return http.StatusInternalServerError, "internal error"
	}
}
```

The client message is fixed text chosen here, never `err.Error()` of an arbitrary chain. The full chain goes to the log, with the level from the status. To test a 500 I added a demo-only hook: the in-memory store fails for id `boom` with a fake database error.

```
$ curl -si localhost:8091/orders/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: cbec0bb8
{"error":"internal error"}
```

```
{"time":"...","level":"ERROR","msg":"request failed","method":"GET","path":"/orders/boom","status":500,"error":"get order boom: dial tcp 10.0.0.5:5432: connect: connection refused","request_id":"cbec0bb8"}
```

The client learns nothing about the database address, while the log has the whole chain and the same `request_id` that the response header returned. A missing order logs a `WARN` with `"error":"get order 99: order not found"` but answers with just `{"error":"order not found"}`.

## A few things to watch

- Log an error once, at the boundary. If every layer logs and returns, you get the same failure five times.
- `%v` instead of `%w` keeps the text but breaks `errors.Is` and `errors.As`.
- Environment variables are strings: parse them early, never call `os.Getenv` from deep inside a package.
- `LogValue` redaction is not a guarantee. Review what you pass to loggers, and prefer never logging config as a raw struct.
- A request ID helps only if the client can see it too, so return it in a response header.

## What's next

Next: building an API with net/http in Go.
