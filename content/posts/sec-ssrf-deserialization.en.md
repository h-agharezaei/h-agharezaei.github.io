+++
date = '2027-05-12T10:00:00+03:30'
draft = false
title = 'SSRF and unsafe deserialization'
description = 'SSRF and unsafe deserialization with real runs: blocklists that fail, redirects, DNS rebinding, a safe Go fetcher, and pickle and YAML pitfalls.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "ssrf", "deserialization", "go", "python", "pickle"]
cover = { image = "/images/covers/sec-ssrf-deserialization.png", alt = "SSRF and unsafe deserialization", hiddenInSingle = true }
+++

The previous post, [The supply chain and vulnerable dependencies](/posts/sec-supply-chain-vulns/), was about code you did not write. This one is about input you did not write: a URL, or a blob of bytes. In [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/) I showed a one-line {{< term "ssrf" "SSRF" >}} and a one-host fix, and admitted I had not tested redirects or DNS. Here I test them. The service style is the one from [Building an API with net/http in Go](/posts/go-http-api-stdlib/); [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) is a good companion.

> Defensive only. Everything ran in my own demo on `127.0.0.1` (a {{< term "loopback" "loopback" >}} address) or on documentation addresses. Nothing contacted a third-party host. Go 1.26, macOS.

## The vulnerable fetcher

A preview endpoint does `http.Get(userURL)`. An "internal" service on another port stands in for an admin or cloud metadata service (the classic target is the link-local range 169.254.0.0/16):

```
$ curl -s '127.0.0.1:18403/fetch?url=http://127.0.0.1:18401/secret'
internal-only: db-password-demo
```

## Weak defences, each tested

A string blocklist (`localhost`, `127.0.0.1`) blocks the obvious URL. Then I sent eight spellings of the same machine straight to the fetcher:

```
http://127.0.0.1:18401/secret     host=127.0.0.1   blocklist-passes=false got secret
http://127.1:18401/secret         host=127.1       blocklist-passes=true  got secret
http://0x7f000001:18401/secret    host=0x7f000001  blocklist-passes=true  got secret
http://2130706433:18401/secret    host=2130706433  blocklist-passes=true  got secret
http://[::1]:18401/secret         host=::1         blocklist-passes=true  got secret
http://localhost.:18401/secret    host=localhost.  blocklist-passes=false got secret
http://[::ffff:127.0.0.1]:18401/secret  ...        blocklist-passes=false got secret
http://x@127.0.0.1:18401/secret   host=127.0.0.1   blocklist-passes=false got secret
```

Every form reached the secret on this Mac; the system resolver accepts the shorthand and hex forms, and other systems may differ. Four slip past the substring check; the other four are caught only because they contain the literal text, and an exact match like `host == "localhost"` would miss them too. A prefix check (`HasPrefix(url, "http://allowed.example")`) fails too, because userinfo comes before the host:

```
$ curl -s '127.0.0.1:18405/fetch?url=http://allowed.example@127.0.0.1:18401/secret'
internal-only: db-password-demo
```

A check that parses the URL and compares the host is better, but it only looks at the first URL. A partner server on 18404 redirects, and the client follows:

```
$ curl -s '127.0.0.1:18406/fetch?url=http://127.0.0.1:18404/go'
internal-only: db-password-demo
```

{{< term "dns-rebinding" "DNS rebinding" >}} is a {{< term "toctou" "time-of-check to time-of-use" >}} bug. If you resolve a name, validate the answer, and then connect by name, the second lookup can differ. With a fake resolver (first answer a documentation address, then loopback):

```
  check : rebind.example -> 203.0.113.10 (public-looking: allowed)
  connect: rebind.example -> 127.0.0.1
  internal-only: db-password-demo
```

## The fix: validate what you connect to

Resolve once, validate the IP, connect to that IP. Repeat the check in `net.Dialer.Control`, which sees the real socket address, and so also covers every redirect hop:

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

Around it: an {{< term "allow-list" "allow-list" >}} of schemes (`http`, `https`) and ports, `CheckRedirect` capped at three hops, a client timeout, and `io.LimitReader` on the body. A table-driven test sends all the bypass forms (with the port allowed, so only the address check can stop them), plus `file://` and `gopher://`, and asserts the internal service saw zero hits. It passes. Other tests, as logged:

```
blocked: address 127.0.0.1          (redirect from the allowed partner to loopback)
lookups=1 dialed=[203.0.113.10:80]  (rebinding resolver asked once, dialed once)
```

The size test returns `response too large` for a 1 MiB body with a 64 KiB limit. Through the HTTP handler, the redirect and `127.1` cases now give `{"error":"url not allowed"}` with status 403.

Notes from the runs: `netip` already treats `::ffff:127.0.0.1` as loopback and `::ffff:10.0.0.1` as private, so `Unmap` is belt and braces here (it also normalises the exception list). I did not test IPv6 ranges beyond those. Network egress policy (a firewall that stops the service from reaching internal ranges at all) is defence in depth; I did not run one.

## Unsafe deserialization

Python's {{< term "pickle" "pickle" >}} stores instructions, not just data. A class can define `__reduce__` to say which function to call on load. My payload only calls `print`:

```
-- calling pickle.loads on those bytes
payload ran during loads(): this was only print()
-- json.loads on a document with the same idea
{'__reduce__': ['print', ['x']]}
```

`pickletools.dis` shows the bytes contain `builtins print` and a `REDUCE` opcode. JSON gave back a plain dict. The docs say: "The pickle module is not secure. Only unpickle data you trust." That is {{< term "unsafe-deserialization" "unsafe deserialization" >}}. Never unpickle input from users, caches others can write to, or message queues you do not control.

PyYAML 6.0.3 (pinned, throwaway venv, deleted afterwards) has the same split:

```
-- yaml.safe_load
ConstructorError could not determine a constructor for the tag 'tag:yaml.org,2002:python/object/apply:builtins.print'
-- yaml.unsafe_load (only for the demo)
yaml tag ran print()
```

Use `safe_load`. Better, parse into plain data and validate against a schema, as in [Input validation with Zod](/posts/node-validation-zod/) and [FastAPI and Pydantic](/posts/py-fastapi-pydantic/).

Go: `json.Unmarshal` into `any` gave `map[string]interface {}` and ran nothing. `encoding/gob` refused an unregistered type (`gob: type not registered for interface: main.Cmd`). Neither format names a function to call. Your own `UnmarshalJSON` methods do run, so keep them free of side effects. Java, PHP and Node serializers have had gadget-chain problems; I only name that and did not test them.

## A few things to watch

- Block-lists lose; allow-list schemes, ports and, when you can, hosts.
- Validate the address you actually connect to, on every hop.
- Never reflect the fetched body or error details back raw.
- A local test on `127.0.0.1` proves the logic, not your production network.

## Exercise

Add a `/preview` endpoint to one of your services. Write the table test of bypass URLs first, watch it fail, then add the dialer check.

## What's next

The next post is “Common cryptography mistakes”.
