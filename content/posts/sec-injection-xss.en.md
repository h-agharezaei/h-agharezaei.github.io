+++
date = '2027-03-07T10:00:00+03:30'
draft = false
title = 'Injection and XSS'
description = 'SQL injection, command injection, path traversal and XSS in a tiny Go demo on localhost: the vulnerable code, the real behavior and the fix for each.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "injection", "xss", "sql-injection", "appsec", "go"]
cover = { image = "/images/covers/sec-injection-xss.png", alt = "Injection and XSS", hiddenInSingle = true }
+++

The previous post, [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/), listed the categories. This one goes deep on the family behind most of them: untrusted input that is mixed into something an interpreter reads. The interpreter can be Postgres, a shell, the filesystem or a browser, and the bug is always the same: data crosses a {{< term "trust-boundary" "trust boundary" >}} and is treated as code. The subject is again the orders-style API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), now with [pgx](/posts/go-postgres-pgx-sqlc/) behind it.

> Defensive only. Everything below is one tiny Go program of mine on `127.0.0.1`, against a real PostgreSQL 18.3 with two throwaway tables (`items`, `secrets`), run with Go 1.26. No third-party target. This program does not continue the previous post's demo; it is a separate one. I did not test anything in a browser.

Each endpoint exists twice: `/v1/...` is vulnerable, `/v2/...` is fixed.

## SQL injection

The vulnerable handler builds SQL by string formatting:

```go
q := fmt.Sprintf("SELECT id, name, price FROM items WHERE name = '%s'", name)
```

A normal request, then the classic payload (sent URL-encoded by `curl --data-urlencode`):

```
$ name=book
[{"id":1,"name":"book","price":1500}]
$ name=' OR '1'='1
[{"id":1,"name":"book","price":1500},{"id":2,"name":"pen","price":200},{"id":3,"name":"lamp","price":4500}]
```

The server log shows why: the quote closed the string, so the query became `WHERE name = '' OR '1'='1'`. A second payload reads another table, on my own demo data only:

```
$ name=x' UNION SELECT id, token, 0 FROM secrets --
[{"id":2,"name":"demo-token-BBBB","price":0},{"id":1,"name":"demo-token-AAAA","price":0}]
```

The fix is a {{< term "parameterized-query" "parameterized query" >}}, where the value travels separately from the SQL text:

```go
pool.Query(ctx, "SELECT id, name, price FROM items WHERE name = $1", name)
```

`book` still returns the book; both payloads return `[]`, because they are now just a strange product name that matches nothing.

**Identifiers cannot be parameters.** `ORDER BY` takes a column name, not a value. The vulnerable `/v1/sort` concatenates it, and a subquery was accepted as the sort key (the query ran and returned the rows in table order). The fix is an allow-list that maps user choices to fixed strings:

```go
var sortable = map[string]string{"name": "name", "price": "price"}
```

`by=price` works; `by=price; DROP TABLE items` gets `400 bad sort column`. Stored procedures and ORMs are not magic: if they build SQL from strings inside, the same bug lives there. See also {{< term "sql-injection" "SQL injection" >}} in the glossary.

## Command injection

The vulnerable handler passes a string to a shell. I used harmless `echo`, never a network tool:

```go
exec.Command("sh", "-c", "echo pinging "+host)
```

```
$ host=x; echo INJECTED
pinging x
INJECTED
```

The `;` started a second command. This is {{< term "command-injection" "command injection" >}}. The fix is no shell and an argument list, so the input stays one argument:

```go
exec.Command("echo", "pinging", host)
```

```
$ host=x; echo INJECTED
pinging x; echo INJECTED
```

## Path traversal

The vulnerable file handler joins the input to a `public/` directory. A file `secret.txt` sits next to it, outside:

```
$ name=hello.txt
hello from public
$ name=../secret.txt
TOP-SECRET-FILE
```

`filepath.Join` cleans the path, so `..` climbs out: this is {{< term "path-traversal" "path traversal" >}}. Fix 1 makes the path absolute and checks the prefix; `../secret.txt` gives `403`. But I also put a symlink `public/link.txt` pointing to `../secret.txt`, and fix 1 serves it, because the check is on the string, not on where the symlink leads. Fix 2 uses `os.OpenRoot` (it exists in Go 1.26):

```go
root, _ := os.OpenRoot("public")
f, err := root.Open(name)
```

```
$ name=hello.txt    -> hello from public
$ name=../secret.txt -> 404, log: path escapes from parent
$ name=link.txt     -> 404, log: path escapes from parent
```

## XSS

A page built with `fmt.Fprintf` echoes the input raw:

```
$ name=<script>alert(1)</script>
<h1>Hello, <script>alert(1)</script></h1>
```

That is {{< term "xss" "XSS" >}} (reflected): the script tag is in the body, so a browser would run it. I only looked at the response text. With `html/template`:

```
<h1>Hello, &lt;script&gt;alert(1)&lt;/script&gt;</h1>
```

The template escapes by context ({{< term "output-encoding" "output encoding" >}}). One template, input `"><script>alert(1)</script>`:

```
body:  <p>&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</p>
attr:  <a title="&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">x</a>
js:    <script>var n = "\"><script>alert(1)</script>";</script>
url:   <a href="/s?q=%22%3e%3cscript%3ealert%281%29%3c%2fscript%3e">x</a>
```

Four contexts, four different escapings. Stored XSS is the same bug with a database in the middle: the payload is saved and runs for everyone who views it.

Two headers limit the damage, shown with `curl -i` (I did not verify browser behavior):

```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'
Set-Cookie: session=demo; Path=/; HttpOnly; Secure; SameSite=Lax
```

A {{< term "content-security-policy" "Content Security Policy" >}} restricts script sources, and {{< term "httponly" "HttpOnly" >}} hides the cookie from page JavaScript. Neither replaces escaping.

On the Node side, I ran nothing. Template literals (`` `<h1>${name}</h1>` ``) do no escaping at all, so they behave like `Fprintf`. Use a template engine that escapes by default, and parameters (`$1`) in `pg`, as in [Postgres from Node.js with pg](/posts/node-postgres-pg/) and [an HTTP server with node:http](/posts/node-http-server/).

## A few things to watch

- Blocklists ("remove quotes") fail; separate data from code instead of cleaning it.
- Never put user input into `sh -c`; prefer a library over spawning programs.
- Errors that echo SQL help attackers; log them, return a generic message, as in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).
- Escape on output, for the context; do not trust "sanitized on input".
- Rate limiting does not fix injection, see [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/).

## Exercise

Add a `/v1/search` endpoint that uses `LIKE '%` + input + `%'`. Break it, then fix it with a parameter (`$1` with `"%" + input + "%"`). Which characters still act as wildcards, and is that a security problem?

## What's next

The next post is Storing passwords safely: argon2 and bcrypt.
