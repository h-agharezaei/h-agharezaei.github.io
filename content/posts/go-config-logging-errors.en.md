+++
date = '2026-12-28T10:00:00+03:30'
draft = false
title = 'Config, structured logging and errors in Go'
description = 'Typed config from environment variables, slog with text and JSON handlers and request IDs, and mapping domain errors to HTTP status codes in one place.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "slog", "config", "errors"]
cover = { image = "/images/covers/go-config-logging-errors.png", alt = "Config, structured logging and errors in Go", hiddenInSingle = true }
+++

Imagine the `orders` service is running in production and something goes wrong. Three questions decide how bad the evening will be. Was the service started with the settings you thought it had? Can you tell from its logs what it was doing when it failed? And when a request fails, does the client get a sensible answer, without being told things it should never see, such as a database address?

Config, logging and errors are the three places where a service either tells the operator what is going on or quietly misleads, and sometimes leaks secrets. The `orders` service from [project layout and clean architecture](/posts/go-project-layout-clean-architecture/) still has a hard-coded `:8080` and a bare `log` call. In this post we fix both and add a deliberate policy for errors. The code is the same module, standard library only, evolved in place (so the domain errors here are a little richer than in the previous post).

One small example of why this matters, which we will test properly later: if you give a password type a `LogValue` method, `slog` prints `[REDACTED]`. But put the same value inside a plain struct, or hand it to `fmt.Println`, and the real password lands in the output.

> Everything was re-run with Go 1.27 on macOS (arm64). The addresses and request IDs in the outputs differ from run to run; I started the server on a random free local port each time.

## Config: one struct, loaded once

Start with the simplest thing a service needs: its settings. Where do they come from? The usual answer is {{< term "environment-variable" "environment variables" >}}: named strings that the process inherits from whoever started it, such as a deploy tool. You can change a setting without rebuilding the program.

The risk is that environment variables are untyped strings, and it is tempting to read them with `os.Getenv` wherever you need one. Then a typo in a value shows up as a strange failure deep inside the program, long after startup. The rule I follow instead is: **read the environment in exactly one place, into a typed struct, and fail at startup if anything is wrong.**

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

The rest of the program receives a `Config`, in which the timeout is already a `time.Duration` and the limit is already an integer. `Load` uses `os.LookupEnv`, applies defaults, parses each value, and collects every problem instead of stopping at the first one:

```go
fail := func(key string, err error) { errs = append(errs, fmt.Errorf("%s: %w", key, err)) }
// ...
if c.ReadTimeout, err = time.ParseDuration(str("ORDERS_READ_TIMEOUT", "5s")); err != nil {
	fail("ORDERS_READ_TIMEOUT", err)
}
// ...
return c, errors.Join(errs...)
```

`str` is a tiny helper that returns the variable, or its default if it is unset or empty. Why collect all the errors? To see it, I started the service with four bad values and no password. `main` prints one report and exits with code 2:

```
$ ORDERS_LOG_LEVEL=loud ORDERS_LOG_FORMAT=yaml ORDERS_READ_TIMEOUT=5 ORDERS_MAX_CENTS=lots ./orders
invalid configuration:
ORDERS_LOG_LEVEL: slog: level string "loud": unknown name
ORDERS_LOG_FORMAT: must be text or json, got "yaml"
ORDERS_READ_TIMEOUT: time: missing unit in duration "5"
ORDERS_MAX_CENTS: strconv.ParseInt: parsing "lots": invalid syntax
ORDERS_DB_PASSWORD: required
```

Each line names the variable and says what is wrong with it. Note the timeout line: `5` is rejected because a Go duration needs a unit, such as `5s`. `errors.Join` puts the messages on separate lines, so the operator can fix everything in one deploy instead of discovering the problems one at a time. No config library was needed.

## Secrets that cannot leak

Configuration contains secrets, and the config is the first thing we log at startup. So the password needs its own type. `Secret` is a string type with a `LogValue` method, which makes it a `slog.LogValuer`: when `slog` is about to print the value, it asks the value how to print itself.

```go
type Secret string

func (Secret) LogValue() slog.Value { return slog.StringValue("[REDACTED]") }
```

This is helpful but it has limits, and I tested them with a throwaway program that logs the same password three ways:

```
level=INFO msg=direct pw=[REDACTED]
level=INFO msg="in struct" cfg="{User:app Pw:s3cr3t-pw}"
Println: s3cr3t-pw
```

(I removed the `time=` field from the first two lines.) The first line is what we want. The second and third show the limit: redaction works only when `slog` sees the `Secret` itself. Wrapped in a plain struct, `slog` just prints the struct as a whole, as the output shows, and does not ask the inner field how to print itself. With `Println` it is just a string.

So I do not rely on this alone. `Config` also implements `LogValue` and lists its fields explicitly. A new field is then never logged by accident; you have to add it to the list on purpose. That method is what the startup log uses.

## slog: handlers, levels and attributes

`log/slog` is the standard library's {{< term "structured-logging" "structured logging" >}} package. Instead of one sentence with values glued inside, a record has a message plus separate key/value pairs (**attributes**), so a log system can filter on `status=500` without parsing English. A record also has a **level**: debug, info, warn or error.

`slog` splits the work in two. The API you call (`Info`, `With`, `Group`) creates records. A **handler** decides how to format and where to write them. Config picks the handler, and `SetDefault` makes our logger the global one (it also redirects the old `log` package to it):

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

(`ctxHandler` is a wrapper we meet in the next section.) `main` calls `slog.SetDefault(logger)` and gives the service `logger.With("component", "service")`, so every line coming from that layer carries `component=service`. Inside the service, a creation is logged like this:

```go
s.log.LogAttrs(ctx, slog.LevelInfo, "order created",
	slog.Group("order", slog.String("id", o.ID), slog.Int64("cents", o.Cents)))
```

`LogAttrs` accepts only typed `Attr` values, so it avoids the classic mistake of an odd number of arguments in a key/value list. `slog.Group` nests related attributes under one name. Here is the startup line in text mode, where the secret is redacted by `Config.LogValue` (without the `time=` field, for width):

```
level=INFO msg=starting config.addr=127.0.0.1:54402 config.log_level=INFO config.log_format=text config.read_timeout=5s config.max_cents=1000000 config.db_password=[REDACTED]
```

The `config.` prefix comes from the group. In JSON mode the same record nests the group as an object. Note that the duration is printed in nanoseconds there:

```
{"time":"...","level":"INFO","msg":"starting","config":{"addr":"127.0.0.1:54402","log_level":"INFO","log_format":"json","read_timeout":5000000000,"max_cents":1000000,"db_password":"[REDACTED]"}}
```

Levels are the second reason for the config: with `ORDERS_LOG_LEVEL=warn`, I created an order and asked for a missing one. The "order created" line (an info) did not appear, and only the warning for the missing order was printed.

## A request ID through the context

When many requests run at once, their log lines interleave. To pick out the lines of one request you need an identifier on each of them. That is a {{< term "request-id" "request ID" >}}.

The plan has two parts. A small **middleware** (a function that wraps the handler and runs for every request) generates an ID, stores it in the request's {{< term "context" "context" >}}, and also echoes it to the client in an `X-Request-ID` header. Then a wrapper around the slog handler, `ctxHandler`, adds `request_id` to every record whose context carries one:

```go
func (h ctxHandler) Handle(ctx context.Context, r slog.Record) error {
	if id := RequestID(ctx); id != "" {
		r.AddAttrs(slog.String("request_id", id))
	}
	return h.Handler.Handle(ctx, r)
}
```

The wrapper must also override `WithAttrs` and `WithGroup` to wrap their results. Otherwise `logger.With(...)` would return the inner handler, and the wrapper would silently disappear. And for this to work you must pass the context when you log: `LogAttrs(ctx, ...)` or `InfoContext(ctx, ...)`, not plain `Info`.

## Errors at the boundary

The basics of Go errors are in [functions, defer and errors](/posts/go-functions-defer-errors/). Here is the policy for a service. Errors travel upward through layers, and at some point one function must decide: what does the client see, and what does the log see? I want that decision in exactly one place.

The domain owns the ready-made error values (**sentinels**, such as `ErrNotFound`) and one custom type that says which field is wrong:

```go
type ValidationError struct{ Field, Reason string }

func (e *ValidationError) Error() string { return fmt.Sprintf("invalid order: %s %s", e.Field, e.Reason) }
func (e *ValidationError) Unwrap() error { return ErrInvalidOrder }
```

`Unwrap` returns `ErrInvalidOrder`, so `errors.Is(err, ErrInvalidOrder)` is still true for it, while `errors.As` can pull out the field and the reason.

As an error goes up, each layer adds context with `%w`, for example `fmt.Errorf("get order %s: %w", id, err)`. The `%w` verb wraps the original error inside the new one, so the message grows but `errors.Is` and `errors.As` still see the original. The transport layer then decides the status code in one function:

```go
func statusOf(err error) (int, string) {
	var ve *domain.ValidationError
	switch {
	case errors.As(err, &ve):
		return http.StatusUnprocessableEntity, ve.Error()
	case errors.Is(err, domain.ErrNotFound):
		return http.StatusNotFound, domain.ErrNotFound.Error()
	case errors.Is(err, errBadJSON):
		return http.StatusBadRequest, "bad json"
	default:
		return http.StatusInternalServerError, "internal error"
	}
}
```

The message sent to the client is fixed text chosen here (or the validation message the domain wrote for clients), never `err.Error()` of an arbitrary chain. The full chain goes only to the log, at a level that follows the status: warn below 500, error from 500 up.

To try a 500 I added a demo-only hook: the in-memory store fails for the id `boom` with a fake database error (the address in it is an invented example). Here is what the client sees:

```
$ curl -si localhost:8091/orders/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: aef11965
{"error":"internal error"}
```

and here is the log line the server wrote for the same request (text mode, without the `time=` field). In JSON mode it carries the same fields:

```
level=ERROR msg="request failed" method=GET path=/orders/boom status=500 error="get order boom: dial tcp 10.0.0.5:5432: connect: connection refused" request_id=aef11965
```

The client learns nothing about the database address, while the log has the whole chain and the same `request_id` that the response header returned. That is how an operator can start from a client's complaint and find the line.

Other cases follow the same path. A missing order logs a `WARN` with `"error":"get order 99: order not found"` but answers with only `{"error":"order not found"}`. An order above the limit or with an empty customer gets a `422` with the specific message, for example `{"error":"invalid order: cents is above the limit"}`. A body that is not JSON gets `400`; the log keeps the decoder's detail (`invalid character 'z' looking for beginning of value`), the client gets only `{"error":"bad json"}`.

## Common error and logging mistakes

- **Logging the same error at every layer.** If each layer logs and also returns the error, one failure appears five times. Log once, at the boundary, and let the other layers just add context.
- **Using `%v` instead of `%w`.** `%v` keeps the text but breaks the chain, so `errors.Is` and `errors.As` stop working further up.
- **Reading environment variables deep inside the code.** They are strings; parse them early in one place, and never call `os.Getenv` from inside a package.
- **Trusting redaction too much.** `LogValue` is not a guarantee, as the leak test showed. Review what you pass to loggers, and do not log a config as a raw struct.
- **A request ID the client cannot see.** It helps only if the client (or the support person) can read it too, so return it in a response header.

## What's next

Next is "Building an API with net/http in Go". The server here is still minimal, and that post adds proper middleware, timeouts and tests on top of it.
