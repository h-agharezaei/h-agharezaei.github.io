+++
date = '2026-12-14T10:00:00+03:30'
draft = false
title = 'Mini project: a URL shortener in Go'
description = 'Build a Go URL shortener with only the standard library: net/http routing, an RWMutex-protected store, crypto/rand codes, JSON and httptest tests.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "project", "http"]
cover = { image = "/images/covers/go-mini-project-url-shortener.png", alt = "Mini project: a URL shortener in Go", hiddenInSingle = true }
+++

Long links are awkward. They break in chat messages, they look ugly in print, and nobody wants to type them. A **URL shortener** solves this: you give it a long address, it gives back a short code, and when someone opens the short link, it sends them to the long one. Services like this look big from the outside, but the core is tiny: a table that maps short codes to long URLs, plus two HTTP endpoints.

This is the last post of the Go Fundamentals series, so instead of a new feature we use what we have learned so far. After [the command-line tool](/posts/go-cli-tool/), we build a small HTTP service with nothing but the standard library. You send a long URL as JSON with `POST /shorten` and get a code back. Visiting `/<code>` redirects you to the original address. The part I find most interesting is not the code itself but the order of things at shutdown, because a service that keeps its data in memory has to save it before it exits. We will get to that.

> I ran everything below with Go 1.27 on macOS, and the outputs are copied from real runs, except that random codes differ from run to run. The code is a local example, not a published repo.

## How the pieces fit

Following [the packages post](/posts/go-packages-modules/), the module `example.com/shortener` has three small pieces:

- `store` keeps the data: which code points to which URL, and how to save and load it.
- `server` is the HTTP layer: the handlers that read a request and write a response.
- `main.go` wires them together and handles startup and shutdown.

The dependency goes one way: `server` knows about `store`, and `store` knows nothing about HTTP. That means we can test the store without any web server, and we could put a different front end on it later.

## The store

At its heart, the store is a map from code to URL. But HTTP handlers run in many goroutines at once, and a map must not be written by one goroutine while another reads it. So we guard the map with a `sync.RWMutex`, as in [the sync post](/posts/go-sync-select-context/). A **read-write mutex** has two kinds of lock. Many readers can hold the read lock at the same time; the write lock is exclusive. Our traffic is mostly redirects, which only read, so this lets them run in parallel; only `Add` needs the exclusive lock:

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

`Get` returns a **sentinel error**, `ErrNotFound`, a named error value the caller can recognize with `errors.Is`. We will see the handler use it.

Where do codes come from? We generate 7 random characters from the digits and the upper- and lowercase letters, 62 symbols in all (this alphabet is called **base62**). Randomness comes from `crypto/rand`. One detail: taking a random byte modulo 62 makes the first few characters of the alphabet very slightly more likely than the others. For a short link that does not matter. For a secret token it would, so use a different method there.

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

`Add` holds the write lock, generates a code and checks that it is free. If the code happens to exist already, which is rare but possible, it simply draws another one:

```go
func (s *Store) Add(target string) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for {
		code, err := newCode(7)
		if err != nil {
			return "", err
		}
		if _, taken := s.links[code]; !taken {
			s.links[code] = target
			return code, nil
		}
	}
}
```

Persistence is a `Save(path)` and `Load(path)` pair that marshal the map to JSON, using the same `encoding/json` and `os.WriteFile` idioms from [the file I/O and JSON post](/posts/go-file-io-json/). `Load` treats a missing file as "start empty" by checking `errors.Is(err, os.ErrNotExist)`, so the very first run does not fail.

## The handlers

Now the HTTP side. Since Go 1.22 the standard `ServeMux` understands HTTP methods and path wildcards in its patterns, so no router library is needed. Two lines declare our whole API:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /shorten", srv.shorten)
mux.HandleFunc("GET /{code}", srv.redirect)
```

`POST /shorten` only matches POST requests to that path. `GET /{code}` matches a GET to any single-segment path and gives us the segment as `code`.

The `shorten` handler does four things in order: it limits the body size (with `http.MaxBytesReader`, 1 MiB here), decodes the JSON, validates the URL, and stores it. On success it answers `201 Created`. Validation uses `net/url`. The URL must parse, the scheme must be `http` or `https`, and there must be a host:

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

Why validate at all? Without it someone could store `javascript:...` or a string that is not a URL, and our redirect would send users there.

The redirect handler reads the wildcard with `r.PathValue("code")`, and turns the store's sentinel error into an HTTP status code:

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

The store says "not found" in its own words, and the handler translates it into 404. The last line sends a {{< term "http-redirect" "redirect" >}}: a response with status `302` and a `Location` header holding the long URL. The browser then requests that address by itself.

I chose 302 on purpose. Browsers may cache a 301 (permanent redirect) for a long time, and then you could never change or count a link later, because the browser would no longer ask us. 302 means "temporary", so every visit comes back to our server.

## Shutdown and saving

The store lives in memory, so the data survives only if we write it to disk before the process ends. `main` does it like this:

```go
st := store.New()
if err := st.Load(dataFile); err != nil {
	log.Fatal(err)
}
srv := &http.Server{Addr: addr, Handler: server.New(st, "http://localhost:8080")}

ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()

go func() {
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}()
log.Printf("listening on %s", addr)

<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
if err := st.Save(dataFile); err != nil {
	log.Fatal(err)
}
log.Printf("saved %s, bye", dataFile)
```

Step by step: `main` loads `links.json` (empty if it does not exist) and starts the server in a goroutine, so `main` itself is free to wait. `signal.NotifyContext` gives a context that is cancelled when the process receives Ctrl+C (`os.Interrupt`) or `SIGTERM`, the polite "please stop" signal that most deployment tools send. The line `<-ctx.Done()` blocks until that happens.

Then comes the part that matters. `srv.Shutdown` stops accepting new connections and waits for requests that are already running, for at most 5 seconds. Only after it returns do we call `Save`. The order is the point: if we saved first, a link created by a request that was still running could be missing from the file. Because `Shutdown` has waited for those requests, the save sees every link.

## Tests with httptest

Starting a real server for every test would be slow, and it would need a free port. The `net/http/httptest` package avoids that: `httptest.NewRequest` builds a request and `httptest.NewRecorder` records the response, so we call the handler directly, as a plain function. As in [the testing post](/posts/go-testing-basics/), the invalid inputs are a table:

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

Each row is some input that must be rejected with `400 Bad Request`. Other tests cover create-then-redirect, an unknown code, 405 for a wrong method, a save/load round trip, and 50 concurrent POSTs. Here they are, first plain and then with the race detector (`-race`), which would flag an unprotected map access:

```text
$ go test -count=1 ./...
?   	example.com/shortener	[no test files]
ok  	example.com/shortener/server	0.289s
ok  	example.com/shortener/store	0.192s
$ go test -race -count=1 ./...
ok  	example.com/shortener/server	1.315s
ok  	example.com/shortener/store	1.297s
```

The first line says the root package, `main.go`, has no tests. The other two packages pass. The race run takes longer because the detector slows the program down, and it passes too, which tells us the mutex really protects the map. The times change from run to run.

## Running it for real

Tests are good, but let us also run the real server and talk to it with `curl`. The `-i` flag shows the response headers. First we shorten a URL, then we follow the code, then we try a code that does not exist, then an invalid URL:

```text
$ curl -i -X POST localhost:8080/shorten -d '{"url":"https://go.dev/doc/"}'
HTTP/1.1 201 Created
Content-Type: application/json
Content-Length: 63

{"code":"LcUU3Dk","short_url":"http://localhost:8080/LcUU3Dk"}

$ curl -i localhost:8080/LcUU3Dk
HTTP/1.1 302 Found
Content-Type: text/html; charset=utf-8
Location: https://go.dev/doc/
Content-Length: 42

<a href="https://go.dev/doc/">Found</a>.

$ curl -i localhost:8080/zzzzzzz
HTTP/1.1 404 Not Found
{"error":"unknown code"}

$ curl -i -X POST localhost:8080/shorten -d '{"url":"example.com"}'
HTTP/1.1 400 Bad Request
{"error":"url must start with http:// or https://"}
```

(I trimmed some headers such as `Date`.) The first response is `201 Created` with the new code (it is random, so yours will differ). The second is the redirect: status `302` and a `Location` header with the original address. The body is a small HTML link for clients that do not follow redirects. The third request used a code that was never created and got `404`, and the fourth was rejected by the validation with `400` and a message that says why.

The last test is the one that matters for the shutdown story. After Ctrl+C the log said `saved links.json, bye`, and the file held the two links I had created. I started the server again, and the old code still redirected with a `302`.

## Where this version falls short

- **`GET /{code}` also matches `GET /shorten`.** I tried it, and `/shorten` was treated as an unknown code and returned 404. Real services reserve some words so that they can never be codes.
- **Always cap the request body.** Without a limit, one client can send a huge body and use all your memory. Here `http.MaxBytesReader` limits it to 1 MiB.
- **The file is only written on a clean shutdown.** A crash or `kill -9` loses everything since the last save. A database, or saving periodically, would fix that.
- **The lock is held while the code is generated.** It is simple and fine at this scale, but it would be a bottleneck for a busy service.
- **Redirecting to any user-supplied URL is risky.** Our service will redirect to whatever people submit, which can be abused for phishing. A real service needs abuse checks.

## Exercise

1. Add `GET /stats/{code}` returning how many times a code was visited (hint: a counter inside the store, under the same lock).
2. Let `POST /shorten` accept an optional `"code"` custom alias and return `409 Conflict` when it is taken.

## What's next

The fundamentals are done, and from here the Go posts move to backend topics. "Graceful shutdown for Go workers" carries the shutdown problem we met here over to workers that read from NATS.
