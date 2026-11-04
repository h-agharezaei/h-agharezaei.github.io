+++
date = '2027-03-07T10:00:00+03:30'
draft = false
title = 'Injection and XSS'
description = 'SQL injection, command injection, path traversal and XSS in a tiny Go demo on localhost: the vulnerable code, the real behavior and the fix for each.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "injection", "xss", "sql-injection", "appsec", "go"]
cover = { image = "/images/covers/sec-injection-xss.png", alt = "Injection and XSS", hiddenInSingle = true }
+++

Picture a login form or a product search box. Behind it, the server builds a SQL query by pasting what you typed into a string. Type `book` and you get the book. Type `' OR '1'='1` and you get every row in the table. The program did not break; it did exactly what the string told it to do, and the string was partly written by a stranger.

That is the whole idea behind this family of bugs, called injection. A program sends text to an interpreter (a database, a shell, the filesystem, a browser) and part of that text came from an untrusted source. If the interpreter cannot tell where the program's own instructions end and the user's data begins, the user's data becomes instructions. Input has crossed a {{< term "trust-boundary" "trust boundary" >}} and is being treated as code. [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/) only named this family (A05 in its table). Here I give each member a demo, on an orders-style API like the one from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), with [Postgres through pgx](/posts/go-postgres-pgx-sqlc/) behind it.

> Defensive only. Everything below is one tiny Go program of mine on `127.0.0.1`, against a real PostgreSQL 18.3 with two throwaway tables (`items` and `secrets`, filled with made-up data). No third-party target. This program does not continue the previous post's demo; it is a separate one. I did not test anything in a browser. I re-ran every output below with Go 1.27 (the first run used Go 1.26), with the server on a random free port instead of the program's hard-coded one, so the commands below show only the paths and parameters.

Each endpoint exists twice. `/v1/...` is the vulnerable version and `/v2/...` is the fixed one, so you can send the same request to both and compare.

## SQL injection

The vulnerable handler builds its SQL by string formatting:

```go
q := fmt.Sprintf("SELECT id, name, price FROM items WHERE name = '%s'", name)
```

The user's `name` is dropped between two quotes. As long as `name` contains no quote, all is well. First a normal request, then the classic payload (`curl --data-urlencode` takes care of URL-encoding it):

```
$ name=book
[{"id":1,"name":"book","price":1500}]
$ name=' OR '1'='1
[{"id":1,"name":"book","price":1500},{"id":2,"name":"pen","price":200},{"id":3,"name":"lamp","price":4500}]
```

The second request returned every row. The server log shows why. After the string was filled in, the query looked like this:

```
SELECT id, name, price FROM items WHERE name = '' OR '1'='1'
```

The quote in the payload closed the string early, `OR '1'='1'` became part of the SQL, and `'1'='1'` is always true. The database could not know that half of this was supposed to be a plain value.

A second payload goes further and reads a different table. It works the same way: `UNION SELECT` glues the rows of another table onto the result, and `--` turns the rest of the original query into a comment. This is against my own demo data only:

```
$ name=x' UNION SELECT id, token, 0 FROM secrets --
[{"id":2,"name":"demo-token-BBBB","price":0},{"id":1,"name":"demo-token-AAAA","price":0}]
```

Those are the made-up tokens from the `secrets` table, shown in the place of product names. A search box just leaked a table it was never meant to touch.

The fix is a {{< term "parameterized-query" "parameterized query" >}}. The SQL text and the value travel to the database separately, so the database knows from the start that `$1` is a value and never code:

```go
pool.Query(ctx, "SELECT id, name, price FROM items WHERE name = $1", name)
```

Now `book` still returns the book. Both payloads return `[]`, because they are no longer SQL; they are just a strange product name that matches nothing.

**Identifiers cannot be parameters.** A parameter can stand in for a value, but not for a column name. `ORDER BY` takes a column name, so the vulnerable `/v1/sort` has to concatenate it:

```go
q := "SELECT id, name, price FROM items ORDER BY " + by
```

A subquery is accepted as the sort key: `by=(select 1)` runs and returns the rows in table order, which proves the input is read as SQL. (The classic `by=price; DROP TABLE items` did not work here, but not because the code is safe: pgx sends one statement at a time, and Postgres answered `cannot insert multiple commands into a prepared statement`, so the handler returned `query failed`. I would not rely on a driver detail to protect a table.)

The fix for a sort column is an allow-list that maps the user's choice to a fixed string, so the input never reaches the query:

```go
var sortable = map[string]string{"name": "name", "price": "price"}
```

`by=price` sorts by price; `by=price; DROP TABLE items` gets `400 bad sort column`.

Stored procedures and ORMs are not magic. If they build SQL from strings inside, the same bug lives there. The glossary entry for {{< term "sql-injection" "SQL injection" >}} has the short version.

## Command injection

Sometimes a program needs to run another program. The vulnerable handler passes one string to a shell, which parses it. I used a harmless `echo`, never a network tool:

```go
exec.Command("sh", "-c", "echo pinging "+host)
```

```
$ host=x; echo INJECTED
pinging x
INJECTED
```

The `;` is the shell's separator between commands, so `host` supplied a second command and the shell ran it. This is {{< term "command-injection" "command injection" >}}: the second line of output is a whole extra command that the user chose. The fix is to use no shell at all and to pass an argument list. Then the input is always one argument, whatever characters it contains:

```go
exec.Command("echo", "pinging", host)
```

```
$ host=x; echo INJECTED
pinging x; echo INJECTED
```

Same input, now printed as plain text on one line, with the `;` just a character.

## Path traversal

The third interpreter is the filesystem. The vulnerable file handler joins the user's `name` onto a `public/` directory. Next to that directory sits a file `secret.txt`, outside it:

```
$ name=hello.txt
hello from public
$ name=../secret.txt
TOP-SECRET-FILE
```

`..` means "the parent directory", and `filepath.Join` cleans the path, so `public/../secret.txt` becomes `secret.txt` and the handler happily climbs out of `public/`. This is {{< term "path-traversal" "path traversal" >}}.

Fix 1 makes the path absolute and checks that it still starts with the `public` directory. `../secret.txt` now gets `403`. But I also put a symlink in the directory, `public/link.txt`, pointing to `../secret.txt`. Fix 1 still serves it, because its check looks at the string, not at where the symlink leads.

Fix 2 uses `os.OpenRoot`, which opens a directory as a root that the program cannot escape (it was added in Go 1.24):

```go
root, _ := os.OpenRoot("public")
f, err := root.Open(name)
```

```
$ name=hello.txt     -> hello from public
$ name=../secret.txt -> 404, log: path escapes from parent
$ name=link.txt      -> 404, log: path escapes from parent
```

Both escape attempts fail, including the symlink. The browser gets a plain 404 and the reason stays in the server log.

## XSS

The last interpreter is the browser. A page built with `fmt.Fprintf` echoes its input raw:

```
$ name=<script>alert(1)</script>
<h1>Hello, <script>alert(1)</script></h1>
```

That is {{< term "xss" "XSS" >}} (cross-site scripting), the reflected kind: the `<script>` tag is now part of the page, so a browser would run it. If the page is shown to a victim through a link, the script runs with that site's powers. I only looked at the response text; I did not open it in a browser. With `html/template`:

```
<h1>Hello, &lt;script&gt;alert(1)&lt;/script&gt;</h1>
```

The `<` and `>` became `&lt;` and `&gt;`, which the browser shows as text instead of reading as a tag. The template does this escaping by context ({{< term "output-encoding" "output encoding" >}}), and the context matters because the same text needs different escaping in different places. One template, with four contexts, and the input `"><script>alert(1)</script>`:

```
body:  <p>&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</p>
attr:  <a title="&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">x</a>
js:    <script>var n = "\"><script>alert(1)</script>";</script>
url:   <a href="/s?q=%22%3e%3cscript%3ealert%281%29%3c%2fscript%3e">x</a>
```

Four contexts, four different escapings. In the body and in the attribute the characters become HTML entities; inside the script the string is escaped the JavaScript way (the `<` forms); in the URL they become percent-escapes. (On Go 1.27 the script line is escaped as above; the first run of this post showed `<` and `>` unescaped there. I did not find out why, so I show the output of the re-run.)

Stored XSS is the same bug with a database in the middle: the payload is saved, for example in a comment, and runs for everyone who views the page.

Two response headers limit the damage when escaping fails somewhere. They are shown with `curl -i` (I did not verify browser behaviour; the demo also sets `X-Content-Type-Options: nosniff`, which I do not discuss):

```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'
Set-Cookie: session=demo; Path=/; HttpOnly; Secure; SameSite=Lax
```

A {{< term "content-security-policy" "Content Security Policy" >}} tells the browser which sources of script it may trust, and {{< term "httponly" "HttpOnly" >}} hides the cookie from JavaScript on the page. Neither replaces escaping. They are the second line of defence.

On the Node side I ran nothing. Template literals (`` `<h1>${name}</h1>` ``) do no escaping at all, so they behave like `Fprintf`. Use a template engine that escapes by default, and use parameters (`$1`) in `pg`, as in [Postgres from Node.js with pg](/posts/node-postgres-pg/) and [An HTTP server with node:http](/posts/node-http-server/).

## Traps in the defence

- **Blocklists fail.** "Remove quotes" or "reject the word DROP" always misses a case. Separate data from code instead of trying to clean the data.
- **Never put user input into `sh -c`.** Pass arguments as a list, and when a library does the job, use the library instead of spawning a program.
- **Errors that echo SQL help the attacker.** Log them and return a generic message, as in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).
- **Escape on output, for the context.** "We sanitized it on input" does not help once the same value is shown somewhere else.
- **Rate limiting does not fix injection.** It slows a person down; it does not change what the query means. See [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) for what it is good for.

## Exercise

Add a `/v1/search` endpoint that uses `LIKE '%` + input + `%'`. Break it, then fix it with a parameter (`$1` with `"%" + input + "%"`). Which characters still act as wildcards, and is that a security problem?

## What's next

The next post is "Storing passwords safely: argon2 and bcrypt". It starts from the case where an injection already worked and someone has read your `users` table: what should that table contain so the passwords stay safe?
