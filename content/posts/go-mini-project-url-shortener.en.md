+++
date = '2026-12-14T10:00:00+03:30'
draft = false
title = 'Mini project: a URL shortener in Go'
description = 'Build a Go URL shortener with only the standard library: net/http routing, an RWMutex-protected store, crypto/rand codes, JSON and httptest tests.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "project", "http"]
cover = { image = "/images/covers/go-mini-project-url-shortener.png", alt = "Mini project: a URL shortener in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-cli-tool/) we built a command-line tool. This is the last post of the Go Fundamentals series, so instead of a new feature we put the pieces together: a small HTTP service that shortens URLs, using nothing but the standard library. You POST a long URL as JSON, get a short code back, and visiting `/<code>` redirects you. I ran everything with Go 1.26 on macOS, and the outputs are copied from real runs.

## Layout

Following [the packages post](/posts/go-packages-modules/), the module `example.com/shortener` has three small pieces: `store` (the data), `server` (HTTP handlers) and `main.go` (wiring and shutdown). The server depends on the store, never the other way around.

## The store

The store is a map guarded by a `sync.RWMutex`, as in [the sync post](/posts/go-sync-select-context/). Many requests only read, so they take the read lock and can run at the same time; only `Add` needs the exclusive lock:

```go
type Store struct {
	mu    sync.RWMutex
	links map[string]string
}

func (s *Store) Get(code string) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	target, ok := s.links[code]
	if !ok {
		return "", ErrNotFound
	}
	return target, nil
}
```

Codes come from `crypto/rand`, mapped onto a base62 alphabet. Taking a byte modulo 62 is slightly biased toward the first characters, which doesn't matter for a short link, though it would for a secret. `Add` holds the lock and retries on the rare collision:

```go
func newCode(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	for i := range b {
		b[i] = alphabet[int(b[i])%len(alphabet)]
	}
	return string(b), nil
}
```

Persistence is a `Save(path)` and `Load(path)` pair that marshal the map to JSON, the same `encoding/json` and `os.WriteFile` idioms from [the file I/O and JSON post](/posts/go-file-io-json/). `Load` treats a missing file as "start empty" using `errors.Is(err, os.ErrNotExist)`.

## The handlers

Since Go 1.22 the standard `ServeMux` understands methods and path wildcards, so no router library is needed:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /shorten", srv.shorten)
mux.HandleFunc("GET /{code}", srv.redirect)
```

The `shorten` handler decodes the JSON, validates, stores and answers `201 Created`. Validation uses `net/url`: it must parse, the scheme must be `http` or `https`, and there must be a host.

```go
func validate(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return errors.New("url is not valid")
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return errors.New("url must start with http:// or https://")
	}
	if u.Host == "" {
		return errors.New("url must have a host")
	}
	return nil
}
```

The redirect handler reads the wildcard with `r.PathValue("code")`, and turns the store's sentinel error into a status code:

```go
func (s *Server) redirect(w http.ResponseWriter, r *http.Request) {
	target, err := s.store.Get(r.PathValue("code"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "unknown code")
		return
	}
	// ...
	http.Redirect(w, r, target, http.StatusFound)
}
```

I chose 302 on purpose: browsers cache a 301 permanently, which makes a link impossible to change or count later.

## Shutdown and saving

`main` loads `links.json`, starts the server in a goroutine, and waits on `signal.NotifyContext` for Ctrl+C or SIGTERM. Then it calls `srv.Shutdown` with a 5-second timeout so in-flight requests finish, and only after that saves the file. The order matters: saving first could miss a link created during shutdown.

## Tests with httptest

With `httptest.NewRequest` and `httptest.NewRecorder` we call the handler directly, no port needed. As in [the testing post](/posts/go-testing-basics/), invalid input is a table:

```go
func TestShortenInvalid(t *testing.T) {
	tests := []struct{ name, body string }{
		{"not json", `hello`},
		{"empty url", `{"url":""}`},
		{"no scheme", `{"url":"example.com"}`},
		{"bad scheme", `{"url":"ftp://example.com/file"}`},
		{"no host", `{"url":"https://"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if rec := post(newTestServer(), tt.body); rec.Code != http.StatusBadRequest {
				t.Errorf("status = %d, want 400", rec.Code)
			}
		})
	}
}
```

Other tests cover create-then-redirect, an unknown code, 405 for a wrong method, a save/load round trip, and 50 concurrent POSTs. Plain and with the race detector:

```text
$ go test -count=1 ./...
?   	example.com/shortener	[no test files]
ok  	example.com/shortener/server	0.289s
ok  	example.com/shortener/store	0.192s
$ go test -race -count=1 ./...
ok  	example.com/shortener/server	1.315s
ok  	example.com/shortener/store	1.297s
```

## Running it for real

```text
$ curl -i -X POST localhost:8080/shorten -d '{"url":"https://go.dev/doc/"}'
HTTP/1.1 201 Created
Content-Type: application/json
Content-Length: 63

{"code":"LcUU3Dk","short_url":"http://localhost:8080/LcUU3Dk"}

$ curl -i localhost:8080/LcUU3Dk
HTTP/1.1 302 Found
Location: https://go.dev/doc/
Content-Length: 42

$ curl -i localhost:8080/zzzzzzz
HTTP/1.1 404 Not Found
{"error":"unknown code"}

$ curl -i -X POST localhost:8080/shorten -d '{"url":"example.com"}'
HTTP/1.1 400 Bad Request
{"error":"url must start with http:// or https://"}
```

(I trimmed some headers such as `Date`.) After Ctrl+C the log said `saved links.json, bye`, and the file held the two links I created. Starting the server again, the old code still redirected with a 302.

## A few things to watch

- `GET /{code}` also matches `GET /shorten`, so that path is treated as an unknown code. Real services reserve some words.
- Always cap the request body; here `http.MaxBytesReader` limits it to 1 MiB.
- The file is only written on a clean shutdown. A crash or `kill -9` loses everything since the last save; a database or periodic saves would fix that.
- Holding the lock while generating the code is simple but fine only at this scale.
- Redirecting to any user URL makes this an open redirect service; a real one needs abuse checks.

## Exercise

1. Add `GET /stats/{code}` returning how many times a code was visited (hint: a counter inside the store, under the same lock).
2. Let `POST /shorten` accept an optional `"code"` custom alias and return `409 Conflict` when it is taken.

## What's next

The fundamentals are done. From here the Go posts move to backend topics: next is graceful shutdown for Go workers with NATS, then project layout and clean architecture.
