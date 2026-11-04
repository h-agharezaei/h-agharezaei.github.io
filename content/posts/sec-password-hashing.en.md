+++
date = '2027-03-22T10:00:00+03:30'
draft = false
title = 'Storing passwords safely: argon2 and bcrypt'
description = 'Password hashing in Go with bcrypt and argon2id: salts, cost, the 72-byte limit, the PHC format, constant-time compare and rehash on login, with output.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "passwords", "argon2", "bcrypt", "hashing", "go"]
cover = { image = "/images/covers/sec-password-hashing.png", alt = "Storing passwords safely: argon2 and bcrypt", hiddenInSingle = true }
+++

Suppose someone reads your `users` table, for example through a bug like those in [Injection and XSS](/posts/sec-injection-xss/). What do they see in the password column? If it holds the passwords themselves, every account is gone at once. And because people reuse passwords, their accounts on other sites are gone too.

You cannot make a leak impossible. What you can do is decide what the leak is worth. The goal of {{< term "password-hashing" "password hashing" >}} is that a stolen table is still expensive to use: the attacker gets a column of scrambled values, and every guess at turning one back into a password costs real work. The context is the login of the orders-style API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/); errors and logs follow [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).

> Defensive only. This is a small Go program (go.mod says Go 1.25, I re-ran it with Go 1.27) using `golang.org/x/crypto` v0.31.0, run locally. I did not crack anything and did not use any real leaked data. The password in the demo (`correct horse`) is a throwaway. It is a separate demo, not a continuation of an earlier one.

## The core idea in plain words

A password hash is a one-way scramble. When a user registers you store the scramble of the password, not the password. When they log in you scramble what they typed and compare the two results. You never need the original again, and nobody can run the scramble backwards. An attacker with the table can only guess: scramble a candidate password, and see whether it matches a stored value.

So everything comes down to the cost of one guess. A good password hash does three things to make it high:

1. It is **salted**, so the attacker cannot reuse one guess against every user.
2. It is **deliberately slow**, so each guess takes real time. The size of that slowness is called the work factor (or cost).
3. For argon2, it also needs **a lot of memory**, which is awkward for the specialised hardware attackers like to use.

The next sections show why each of these is needed.

## Why SHA-256 is the wrong tool

SHA-256 is designed to be fast. For checking that a file did not change, that is good. For passwords it is bad, because an attacker holding a stolen table wants speed too. A fast function lets them try an enormous number of guesses per second. A password hash should allow very few. (That is general knowledge, not my measurement: I did not measure how many SHA-256 hashes per second this machine does. It is loaded by other apps, so any number would mislead.)

SHA-256 has a second problem here: it is deterministic. The same input always gives the same output. The demo hashes the same password twice and prints the first 8 bytes of each:

```
sha256 #1 4104d36f8da2c254
sha256 #2 4104d36f8da2c254
```

Equal passwords give equal hashes. That has two consequences. Anyone reading the table can see which users share a password. And an attacker can compute the hashes of common passwords once and look them up in every table they ever steal (a precomputed list like this is often called a rainbow table, though the simple version is just a big dictionary of hash to password).

The fix for this one is a {{< term "salt" "salt" >}}: a random value, different for every user, mixed in before hashing and stored next to the hash. Two users with the same password now get different hashes, and a precomputed table is useless because it would be needed once per salt. The fix for the speed problem is a function that is slow on purpose. bcrypt and argon2 do both.

## bcrypt

The Go API is two calls, one to hash and one to check:

```go
h, _ := bcrypt.GenerateFromPassword([]byte(pw), 10)
err := bcrypt.CompareHashAndPassword(h, []byte(pw))
```

The second argument, 10, is the cost. The demo hashes the same password three times, at cost 10, 10 and 12, and then checks a right and a wrong password. This is the real output; the salts are random, so your hashes will look different:

```
bcrypt #1 $2a$10$IK9Cgg.Vh.LkdGaWkinWOObMI7BcCp2D9wRXfUxUykn7aOPMo8bW.
bcrypt #2 $2a$10$iZbbNurr61aUTKmGpPpq4eZkP1wZsmAI5To22dkVY5GFdlhJCR.bS
bcrypt c12 $2a$12$dWTa2PbXW62fcB0Nv/D8yuDIy8g6iKeYYvZGAy2ERvn5106DqujUu
Cost(h3) = 12
compare ok: <nil>
compare bad: crypto/bcrypt: hashedPassword is not the hash of the given password
```

Reading it line by line:

- **Lines 1 and 2** are the same password hashed twice at cost 10, and they are different. That is the salt at work: {{< term "bcrypt" "bcrypt" >}} generates a random salt for each call and stores it inside the string.
- **The string format** is `$version$cost$salt+hash`. In `$2a$10$IK9C…`, `2a` is the bcrypt version and `10` the cost, followed by the salt and hash in one run of characters. Because the cost and salt are inside the string, `CompareHashAndPassword` needs nothing but the stored string and the password.
- **Line 3** is cost 12. Each cost step doubles the work, so cost 12 is about four times the work of cost 10. That doubling is the work factor: you raise it as computers get faster.
- **`Cost(h3) = 12`** reads the cost back out of the string.
- **The last two lines** are the check: `<nil>` (no error) means the password matched, and the error means it did not.

**The 72-byte limit.** bcrypt only uses the first 72 bytes of the password. This version of the library refuses to create a hash for longer input. The demo tries 73 bytes, then 72, and then compares a hash made from 72 `a` characters with 73 `a` characters:

```
73 bytes: bcrypt: password length exceeds 72 bytes
72 bytes: <nil>
72 a's vs 73 a's compare: <nil>
```

The last line is the one to notice. A hash made from 72 `a` characters accepts 73 `a` characters in `CompareHashAndPassword`: the check silently ignores the tail. So either reject long passwords at registration, or pre-hash them. I did not test pre-hashing here. According to the OWASP Password Storage Cheat Sheet, pre-hashing with a fast hash before bcrypt is risky (it mentions NUL-byte truncation and "password shucking"), and it suggests limiting the password to 72 bytes. The same page treats bcrypt as the choice for legacy systems and gives 10 as the minimum cost. So do not copy a pre-hash recipe blindly.

## argon2id

{{< term "argon2" "argon2" >}}id is the newer function. It has three knobs: time (how many passes), memory (in KiB) and threads. The memory knob is the clever one. Hardware built to test huge numbers of guesses in parallel (GPUs, for example) has little memory per guess, so forcing each guess to use, say, 19 MiB makes it far more expensive than only making it slow.

The demo hashes the same password twice with argon2id, using 19456 KiB (19 MiB), 1 pass and 1 thread. It stores the result in the usual PHC string format (Password Hashing Competition, the convention for writing a hash and its parameters in one string):

```
argon2id #1 $argon2id$v=19$m=19456,t=1,p=1$YdKfdriUuXrVZ7YNRE0JeA$d+uWuqitadxkbzoSXGsb03AcI+SIrgwxyGaprFMI2TY
argon2id #2 $argon2id$v=19$m=19456,t=1,p=1$GKF7XACVZUFNlW2+pB4msg$SoLnX3oGuS7UvxRKUEOwliGu/X7nMBHNyEeSJdZuENw
```

Read it between the dollar signs: the algorithm (`argon2id`), the version (`v=19`), the parameters (`m=19456,t=1,p=1`, meaning memory in KiB, passes and threads), the salt, and finally the hash. Again, two runs of the same password differ because of the random salt. The `argon2` package only gives the raw function, so I wrote the encode and parse code myself (about 40 lines in the demo, in `hasher.go`). Then the demo verifies a right and a wrong password:

```
verify: true false
```

`true` for the right password and `false` for the wrong one.

My numbers (19 MiB, 1 pass) are only for the demo. When I checked the OWASP cheat sheet again while rewriting this post, its minimum for argon2id was 19 MiB of memory with 2 passes and 1 thread (or 46 MiB with 1 pass, among other trade-offs), and it says to benchmark on your own system. So my demo's setting of 19 MiB with 1 pass is below that minimum; size your own parameters against the current guidance and your server, not against my demo.

## Compare in constant time

After recomputing the hash, the program compares it with the stored one:

```go
got := argon2.IDKey([]byte(password), salt, p.Time, p.MemKiB, p.Threads, p.KeyLen)
ok := subtle.ConstantTimeCompare(got, want) == 1
```

The ordinary `==` on byte strings can stop at the first byte that differs, which makes the answer slightly faster for guesses that are "more wrong". {{< term "constant-time-comparison" "Constant-time comparison" >}} always looks at every byte, so the running time reveals nothing about where the two differ. bcrypt's `CompareHashAndPassword` already does this for you. I did not try to measure a timing leak.

## Rehash on login

Parameters age: what is expensive today is cheap in five years. When you raise them, old hashes stay valid and still carry their old parameters. You can upgrade them at the one moment you have the plain password in hand, which is a successful login.

```go
func Login(password, stored string, want Params) (ok, rehash bool, err error) {
	ok, have, err := VerifyArgon2id(password, stored)
	if err != nil || !ok { return false, false, err }
	return true, have != want, nil
}
```

`Login` verifies with the parameters stored in the hash, and reports whether they differ from the parameters you want now. The caller hashes again with the new parameters and saves. In the demo, going from the first set (1 pass, 19 MiB, 1 thread) to a new one (2 passes, 32 MiB, 2 threads) prints:

```
rehash needed with new params: true
```

The tests use tiny parameters (8 KiB, 1 pass) so they stay fast, with no sleeps:

```
--- PASS: TestSaltMakesHashesDiffer
--- PASS: TestVerify
--- PASS: TestRehashOnLogin
```

(`go test -v` also prints a time for each test; I left those out.) They check that two hashes of one password differ, that a wrong password and a foreign hash format are rejected, and that a wrong password never triggers a rehash.

## Beyond the hash function

- **A pepper helps in one specific case.** A {{< term "pepper" "pepper" >}} is a secret key kept outside the database and mixed in, for example with HMAC. It helps if only the database leaks. It also adds key management, and per the OWASP page it is defence in depth on top of strong hashing, not a replacement. I describe it; I did not build it.
- **Never log passwords or login request bodies.** Check your logger and your error messages.
- **Weak passwords fall to guessing no matter the algorithm.** A list like `123456`, `password`, `qwerty` is tried first. Length and a breached-password check at signup help more than composition rules. I ran no cracker; this is reasoning, not a result.
- **Reset tokens are passwords too.** Make them random, long, single use and short-lived, and store only their hash.
- **Slow hashing can be abused to burn CPU.** Every login attempt costs you what it costs the attacker, so combine it with [rate limiting](/posts/go-rate-limiting-caching/).

## Exercise

Add a bcrypt-to-argon2id migration: on login, if the stored hash starts with `$2`, verify with bcrypt, then store an argon2id hash. Write the test with cost 4 so it stays fast.

## What's next

The next post is "Sessions or JWT?". A successful login is where this post ends and that one starts: how does the server remember who you are on the next request?
