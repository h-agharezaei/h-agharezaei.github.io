+++
date = '2027-05-12T10:00:00+03:30'
draft = false
title = 'SSRF and unsafe deserialization'
description = 'SSRF and unsafe deserialization with real runs: blocklists that fail, redirects, DNS rebinding, a safe Go fetcher, and pickle and YAML pitfalls.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "ssrf", "deserialization", "go", "python", "pickle"]
cover = { image = "/images/covers/sec-ssrf-deserialization.png", alt = "SSRF and unsafe deserialization", hiddenInSingle = true }
+++

Many products have a small feature like this: you paste a link, and the server fetches the page and shows you a preview (a title, an image, a summary). It looks harmless. But think about who is making the request. It is not the user's browser. It is your server, which sits inside your network, behind your firewall, and can reach things the user cannot: an admin panel on another port, a database dashboard, or the metadata service that many cloud providers expose on a link-local address (the `169.254.0.0/16` range). The user only types a URL, and your server becomes a messenger that carries the request to places the user could never reach alone. This is {{< term "ssrf" "SSRF" >}}, server-side request forgery.

The usual first reaction is to block `localhost` and `127.0.0.1`. In my own demo, `127.1` and `0x7f000001` walked straight past that blocklist and reached an internal secret. This post shows why such blocklists fail, and what a fetcher that validates the right thing looks like.

It also covers a second kind of input you did not write: a blob of bytes that your program turns back into objects. After code you did not write ([The supply chain and vulnerable dependencies](/posts/sec-supply-chain-vulns/)), these are the two ways outside data can take control of your program. In [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/) I showed a one-line SSRF and a one-host fix, and admitted I had not tested redirects or DNS. Here I do. The service style follows [Building an API with net/http in Go](/posts/go-http-api-stdlib/), and [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) is a good companion.

> Defensive only. Everything ran in my own demo on `127.0.0.1` (a {{< term "loopback" "loopback" >}} address, which means "this same machine") or on documentation addresses. Nothing contacted a third-party host, and the "secret" is a fake string I made up. The original run used Go 1.26 on macOS; for this rewrite I re-ran the Go demo with Go 1.27.3 and the output was the same. The demo hard-codes its ports (18401 and up), so I re-ran a throwaway copy on other ports; the port numbers below are the demo's own.

## The vulnerable fetcher

The preview endpoint is just `http.Get(userURL)` and returns the body. To play the part of the internal service, I run a second small server on another port. It has one route, `/secret`, which returns a fake password. Think of it as the admin page or the metadata service: the user should never see it, but the machine running the fetcher can reach it.

```
$ curl -s '127.0.0.1:18403/fetch?url=http://127.0.0.1:18401/secret'
internal-only: db-password-demo
```

Port 18403 is the vulnerable preview server, port 18401 is the internal service. I asked the preview server to fetch a URL, and it returned the internal secret. That is the whole bug: the server did something on behalf of a user that the user was not allowed to do.

## Weak defences, each tested

The first fix people try is a string blocklist: refuse the URL if it contains `localhost` or `127.0.0.1`. The reason this fails is that one machine has many names. I sent eight spellings of the same machine straight to the fetcher. The `blocklist-passes` column tells whether my blocklist would have let the URL through:

```
http://127.0.0.1:18401/secret            host=127.0.0.1      blocklist-passes=false got secret
http://127.1:18401/secret                host=127.1          blocklist-passes=true  got secret
http://0x7f000001:18401/secret           host=0x7f000001     blocklist-passes=true  got secret
http://2130706433:18401/secret           host=2130706433     blocklist-passes=true  got secret
http://[::1]:18401/secret                host=::1            blocklist-passes=true  got secret
http://localhost.:18401/secret           host=localhost.     blocklist-passes=false got secret
http://[::ffff:127.0.0.1]:18401/secret   host=::ffff:127.0.0.1 blocklist-passes=false got secret
http://x@127.0.0.1:18401/secret          host=127.0.0.1      blocklist-passes=false got secret
```

Reading the rows:

- `127.1` is a shorthand that the system resolver expands to `127.0.0.1`. `0x7f000001` is the same address written in hex, and `2130706433` is the same address as one decimal number. `::1` is the IPv6 loopback.
- `localhost.` has a trailing dot, which is still `localhost` to the resolver.
- `::ffff:127.0.0.1` is an IPv4 address wrapped inside an IPv6 one.
- `x@127.0.0.1` has a username before the `@`. In a URL, that part is "userinfo", and the host comes after it.

Every row ended with `got secret`, so on this Mac all eight forms reached the internal service. (The system resolver accepts the shorthand and hex forms here; other systems may differ.) Four rows slip past the blocklist. The other four are blocked only by luck, because the URL still contains the literal text `127.0.0.1` or `localhost`. An exact comparison like `host == "localhost"` would miss `localhost.` and `::ffff:127.0.0.1` too.

An allow-style check on the start of the string fails for a related reason. If the code only checks `HasPrefix(url, "http://allowed.example")`, the attacker writes `allowed.example@127.0.0.1`, because everything before the `@` is userinfo, not the host:

```
$ curl -s '127.0.0.1:18405/fetch?url=http://allowed.example@127.0.0.1:18401/secret'
internal-only: db-password-demo
```

A better check parses the URL and compares the real host. But it only looks at the first URL. In my demo, a "partner" server on port 18404 answers every request with a redirect to the internal secret. The check approves the partner, and the HTTP client happily follows the redirect:

```
$ curl -s '127.0.0.1:18406/fetch?url=http://127.0.0.1:18404/go'
internal-only: db-password-demo
```

The last weak defence is the subtle one. {{< term "dns-rebinding" "DNS rebinding" >}} is a {{< term "toctou" "time-of-check to time-of-use" >}} bug: the world changes between the moment you check something and the moment you use it. Suppose your code resolves a hostname, checks that the answer is a public address, and then connects by hostname. Connecting means a second lookup, and the second answer can be different. I simulate a malicious DNS server with a fake resolver whose first answer is a documentation address and whose second answer is loopback:

```
  check : rebind.example -> 203.0.113.10 (public-looking: allowed)
  connect: rebind.example -> 127.0.0.1
  internal-only: db-password-demo
```

The first line is the check: the name looked fine. The second is the real connection: the name now points to loopback. The third is what came back. So a check on the name, or on an earlier lookup, proves nothing about where the connection really goes.

## The fix: validate what you connect to

All four failures have the same root. The check looks at text (a URL, a name), while the thing that matters is the IP address of the socket that is actually opened. So the fix is to move the check to that point:

1. Resolve the name once.
2. Validate the resulting IP.
3. Connect to that exact IP, not to the name.
4. Repeat the check in `net.Dialer.Control`, which sees the real socket address just before the connection is made. Every redirect hop goes through a new dial, so it is covered too.

The validation function rejects everything a user-supplied URL has no business reaching:

```go
func checkIP(ip netip.Addr) error {
	ip = ip.Unmap()
	if !ip.IsValid() || ip.IsLoopback() || ip.IsPrivate() ||
		ip.IsLinkLocalUnicast() || ip.IsUnspecified() || ip.IsMulticast() {
		return fmt.Errorf("%w: address %s", ErrBlocked, ip)
	}
	return nil
}
```

`Unmap` turns `::ffff:127.0.0.1` back into `127.0.0.1` before the checks. Loopback, private ranges (`10.x`, `172.16-31.x`, `192.168.x`), link-local (where the metadata services live), unspecified (`0.0.0.0`) and multicast are all refused.

Around this function there are a few more rules. Only the `http` and `https` schemes are allowed, because `file://` and `gopher://` are not web fetches. Only an {{< term "allow-list" "allow-list" >}} of ports is allowed. Redirects are capped at three hops. The client has a timeout, and the body is read through `io.LimitReader`, so a huge response cannot eat memory.

To test it, I wrote a table-driven test that sends all the bypass forms from above, plus `file://` and `gopher://`, to a fetcher whose port is allowed on purpose, so only the address check can stop them. It also asserts that the internal service saw zero hits. It passes. Running the fetcher by hand on a few inputs shows the reasons:

```
http://127.0.0.1:18401/secret              -> Get "http://127.0.0.1:18401/secret": blocked: address 127.0.0.1
http://127.1:80/                           -> Get "http://127.1:80/": blocked: address 127.0.0.1
file:///etc/hosts                          -> blocked: scheme "file"
http://[::ffff:127.0.0.1]:18401/secret     -> address 127.0.0.1
```

(The last line is shorter only because the demo's printing helper cuts long error messages after the last colon; the full error is the same `blocked: address 127.0.0.1`.) Notice that `127.1` is reported as `127.0.0.1`: the check saw the real address, not the spelling.

Two more tests print what they saw:

```
blocked: address 127.0.0.1          (redirect from the allowed partner to loopback)
lookups=1 dialed=[203.0.113.10:80]  (rebinding resolver asked once, dialed once)
```

The first is the redirect case: the partner was allowed, but the hop to loopback was refused. In the second the resolver was asked exactly once, and the dial went to the IP that was validated, so the rebinding trick has nothing to work with. A size test also passes: a 1 MiB body with a 64 KiB limit returns `response too large`. Through the HTTP handler, the redirect case and the `127.1` case now answer `{"error":"url not allowed"}` with status 403.

A few notes from running it. In my demo the partner server lives on loopback too, so the safe fetcher gets one explicit exception for that single address and port; a real partner would be on a public address and need no exception. `netip` already treats `::ffff:127.0.0.1` as loopback and `::ffff:10.0.0.1` as private (my test prints `true` for the raw and the unmapped form), so `Unmap` is belt and braces here; it also keeps the exception list consistent. I did not test IPv6 ranges beyond those. And a network rule that stops the service from reaching internal ranges at all is a good extra layer; I did not run one.

## Unsafe deserialization

Now the second kind of input: bytes that your program turns back into objects. The danger depends on what the format is allowed to describe. A format like JSON describes only data: numbers, strings, lists. Some formats can also describe code to run while loading.

Python's {{< term "pickle" "pickle" >}} is the classic example. It stores instructions for rebuilding an object, and a class can define `__reduce__` to say which function to call on load. My toy payload calls nothing more dangerous than `print`:

```
-- calling pickle.loads on those bytes
payload ran during loads(): this was only print()
-- json.loads on a document with the same idea
{'__reduce__': ['print', ['x']]}
```

The first line is printed by `loads()` itself: the bytes made Python call `print` before it handed me any object. The second shows JSON given a document with the same idea; it just returned a plain dictionary with a key called `__reduce__`, because JSON cannot name a function to call. `pickletools.dis`, which prints the pickle's opcodes, shows the bytes contain `builtins print` and a `REDUCE` opcode, which is the instruction to call it (Python 3.14.0 here). The Python docs say it plainly: "The pickle module is not secure. Only unpickle data you trust." This is {{< term "unsafe-deserialization" "unsafe deserialization" >}}. Never unpickle input from users, from caches others can write to, or from message queues you do not control.

YAML has the same split. I ran this with PyYAML 6.0.3 in a throwaway venv in the original run. For this rewrite I could not reinstall PyYAML (the download stalled), so these two outputs are from the original run:

```
-- yaml.safe_load
ConstructorError could not determine a constructor for the tag 'tag:yaml.org,2002:python/object/apply:builtins.print'
-- yaml.unsafe_load (only for the demo)
yaml tag ran print()
```

`safe_load` refuses the Python-specific tag, while `unsafe_load` obeys it and calls `print`. Use `safe_load`. Even better, parse into plain data and then validate it against a schema, as in [Input validation with Zod](/posts/node-validation-zod/) and [FastAPI and Pydantic](/posts/py-fastapi-pydantic/).

What about Go? `json.Unmarshal` into `any` gave a `map[string]interface {}` and ran nothing. `encoding/gob` refused to carry a type that was not registered (`gob: type not registered for interface: main.Cmd`); after `gob.Register`, decoding returned the plain `main.Cmd{hello}` value. Neither format can name a function to call. One catch: your own `UnmarshalJSON` methods do run, so keep them free of side effects. Other ecosystems, such as Java, PHP and Node serializers, have had gadget-chain problems (chains of existing classes whose loading code does something dangerous); I only mention that and did not test them.

## Rules for any URL fetcher

- Blocklists lose. Allow-list schemes, ports and, when you can, hosts.
- Validate the address you actually connect to, on every hop, not the text of the URL.
- Never reflect the fetched body or error details back to the user raw. Error messages can leak what exists inside your network.
- A local test on `127.0.0.1` proves the logic, not your production network.

## Exercise

Add a `/preview` endpoint to one of your services. Write the table test of bypass URLs first and watch it fail. Then add the dialer check and watch it pass.

## What's next

The next post is "Common cryptography mistakes". It shows the same kind of failure from another angle: code that works perfectly in a demo and is still broken by design.
