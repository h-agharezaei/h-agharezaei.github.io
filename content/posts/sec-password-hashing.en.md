+++
date = '2027-03-22T10:00:00+03:30'
draft = false
title = 'Storing passwords safely: argon2 and bcrypt'
description = 'Password hashing in Go with bcrypt and argon2id: salts, cost, the 72-byte limit, the PHC format, constant-time compare and rehash on login, with output.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "passwords", "argon2", "bcrypt", "hashing", "go"]
cover = { image = "/images/covers/sec-password-hashing.png", alt = "Storing passwords safely: argon2 and bcrypt", hiddenInSingle = true }
+++

The previous post, [Injection and XSS](/posts/sec-injection-xss/), was about attackers getting in through input. This one assumes the worst case after that: someone reads your `users` table. If it holds plain passwords, every account is gone, and since people reuse passwords, accounts on other sites too. The goal of {{< term "password-hashing" "password hashing" >}} is that a leaked table is still expensive to use. The context is the login of the orders-style API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/); errors and logs follow [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).

> Defensive only. This is a small Go 1.26 program with `golang.org/x/crypto` v0.31.0, run locally. I did not crack anything and did not use any real leaked data. It is a separate demo, not a continuation of an earlier one.

## Why SHA-256 is the wrong tool

SHA-256 is designed to be fast. For checking a file that is good; for passwords it is bad, because an attacker with a stolen table also wants to be fast. Also, it is deterministic:

```
sha256 #1 4104d36f8da2c254
sha256 #2 4104d36f8da2c254
```

Equal passwords give equal hashes, so one precomputed table covers all users, and anyone can see who shares a password. I did not measure how many SHA-256 hashes per second this machine does: it is loaded by other apps, so any number would mislead. Generally, a fast hash lets an attacker test enormous numbers of guesses per second and a password hash allows very few; that is general knowledge, not my measurement.

A {{< term "salt" "salt" >}} fixes the sharing problem, and a deliberately slow function fixes the speed problem. bcrypt and argon2 do both.

## bcrypt

```go
h, _ := bcrypt.GenerateFromPassword([]byte(pw), 10)
err := bcrypt.CompareHashAndPassword(h, []byte(pw))
```

Real output for the same password:

```
bcrypt #1  $2a$10$jv.fkgkg6LQqdoQUxi8XFOPK9TtcOqPqXMfP14OjXZjWjz2756q3S
bcrypt #2  $2a$10$q32SQpWrZBP4b0hDELouMuoRaag8edDnQW.gNPUnganwEl256uk1C
bcrypt c12 $2a$12$mdeSknpMc5r1cNGfd.jCa.xu7piNjrFuqmCXdoS6UBnml0K0akEFy
Cost(h3) = 12
compare ok: <nil>
compare bad: crypto/bcrypt: hashedPassword is not the hash of the given password
```

Two hashes of one password differ because {{< term "bcrypt" "bcrypt" >}} generates a random salt and stores it inside the string. The format is `$version$cost$salt+hash`; the cost is inside too, so `Compare` needs nothing but the stored string. Each cost step doubles the work.

**The 72-byte limit.** bcrypt only uses the first 72 bytes of the password. This version refuses to create a hash for longer input:

```
73 bytes: bcrypt: password length exceeds 72 bytes
72 bytes: <nil>
72 a's vs 73 a's compare: <nil>
```

The last line surprised me: a hash made from 72 `a` characters accepts 73 `a` characters in `CompareHashAndPassword`, so the check silently ignores the tail. Either reject long passwords at registration, or pre-hash them; I did not test pre-hashing here, and it has its own pitfalls (for example NUL bytes in a raw digest), so do not copy it blindly.

## argon2id

{{< term "argon2" "argon2" >}}id takes three knobs: time (passes), memory (KiB) and threads. The memory cost is what makes GPU attacks harder. I stored hashes in the usual PHC string format:

```
argon2id #1 $argon2id$v=19$m=19456,t=1,p=1$R/oNzVeBFwd1WsDpJjMLJg$X58e/1beHxPCFb0hEJ2Rnn/6lZMQjmv0jLjf4I4PrGY
argon2id #2 $argon2id$v=19$m=19456,t=1,p=1$ZhQgiCn7TIbCwgmlenuTsQ$H6BmcgnWq1iaJYGaTRNavg8rHsO8v6NwywoIkOjfayI
```

Algorithm, version, parameters, salt, hash: all in one string. My numbers (19 MiB, 1 pass) are only for the demo; check the current OWASP guidance and size them for your server. The `argon2` package gives only the raw function, so I wrote the encode/parse code myself (about 40 lines in the demo).

## Compare in constant time

```go
got := argon2.IDKey([]byte(password), salt, p.Time, p.MemKiB, p.Threads, p.KeyLen)
ok := subtle.ConstantTimeCompare(got, want) == 1
```

{{< term "constant-time-comparison" "Constant-time comparison" >}} avoids a timing leak from `==` stopping at the first different byte. bcrypt's `CompareHashAndPassword` already does this for you. I did not try to measure a timing leak.

## Rehash on login

Parameters age. When you raise them, old hashes stay valid, so upgrade them at the one moment you have the plain password: a successful login.

```go
func Login(password, stored string, want Params) (ok, rehash bool, err error) {
	ok, have, err := VerifyArgon2id(password, stored)
	if err != nil || !ok { return false, false, err }
	return true, have != want, nil
}
```

The caller hashes again with the new parameters and saves. The tests use tiny parameters (8 KiB, 1 pass) and no sleeps:

```
--- PASS: TestSaltMakesHashesDiffer
--- PASS: TestVerify
--- PASS: TestRehashOnLogin
```

They check that a wrong password never triggers a rehash.

## A few things to watch

- A {{< term "pepper" "pepper" >}} (a secret key outside the database, mixed in with HMAC) helps if only the database leaks. It adds key management; I describe it, I did not build it.
- Never log passwords or request bodies of login; check your logger and your error messages.
- Weak passwords fall to guessing no matter the algorithm: a list like `123456`, `password`, `qwerty` is tried first. Length and a breached-password check at signup help more than composition rules. I ran no cracker; this is reasoning.
- Reset tokens: random, long, single use, short expiry, store only their hash, same as a password.
- Slow hashing can be abused to burn CPU; combine it with [rate limiting](/posts/go-rate-limiting-caching/).

## Exercise

Add a bcrypt-to-argon2id migration: on login, if the stored hash starts with `$2`, verify with bcrypt, then store an argon2id hash. Write the test with cost 4 so it stays fast.

## What's next

The next post is Sessions or JWT?.
