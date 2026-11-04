+++
date = '2027-05-17T10:00:00+03:30'
draft = false
title = 'Common cryptography mistakes'
description = 'Common cryptography mistakes in Go: ECB, nonce reuse, no authentication, math/rand, hash misuse, fixed IVs, XOR ciphers and weak keys, with real output.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "cryptography", "encryption", "go", "hmac"]
cover = { image = "/images/covers/sec-crypto-mistakes.png", alt = "Common cryptography mistakes", hiddenInSingle = true }
+++

Here is a program that encrypts 64 bytes with AES. The plaintext is 64 letters `A`. The code compiles, the round trip works, the tests pass. Then you print the ciphertext in 16-byte blocks and all four blocks are identical. Nothing crashed, no error was returned, and the design is still broken.

That is how cryptography usually fails. A mistake in a cipher does not look like a bug, because the program does what you asked. It fails quietly, and only an attacker notices. This is much like trusting input too much in [SSRF and unsafe deserialization](/posts/sec-ssrf-deserialization/), where the code also worked as written.

[Managing secrets and keys](/posts/sec-secrets-management/) covered AES-GCM, nonces and envelope encryption, so I will not repeat them. This post is the "what goes wrong" catalogue: ten mistakes, and for most of them a small experiment you can run. Password storage has its own post, [Storing passwords safely](/posts/sec-password-hashing/), and certificates are in [TLS and x509 certificates in practice](/posts/sec-tls-x509-certificates/).

> Defensive only. Every key and message below is an obvious FAKE I made up for the demo, and everything ran locally. The original run used Go 1.26 and `golang.org/x/crypto` v0.31.0; for this rewrite I re-ran the same program with Go 1.27.3 and the same x/crypto version and got the same output (apart from random values, which I say below). I did not try to find hash collisions or attack anything real. The demo is one small `main.go` plus a test, and `go test -race` passed.

Before the list, three words. A **block cipher** such as AES encrypts a fixed-size block (16 bytes for AES), so for longer data you need a **mode** that says how to chain the blocks. A **key** is the secret. A {{< term "nonce" "nonce" >}} (also called an IV, initialization vector, in some modes) is a value that must be different for every message you encrypt under the same key; it is not secret, but its reuse can be fatal.

## 1. ECB leaks patterns

The simplest way to use a block cipher is to encrypt every block independently. That mode is called {{< term "ecb-mode" "ECB" >}}. Go has no ECB helper (a hint in itself), so the demo encrypts block by block with `cipher.Block`. The plaintext is 64 bytes of `A`, which is four equal blocks:

```
block 0 9716d7a815f1ccfe34e0a747bd079f4c
block 1 9716d7a815f1ccfe34e0a747bd079f4c
block 2 9716d7a815f1ccfe34e0a747bd079f4c
block 3 9716d7a815f1ccfe34e0a747bd079f4c
ECB: 4 blocks, 3 duplicates
CBC: 4 blocks, 0 duplicates
GCM: 5 blocks (incl. tag), 0 duplicates
```

The four `block` lines are the ciphertext. They are the same because ECB maps the same input block to the same output block under one key. An observer who cannot read anything still learns the structure: which parts of the message repeat, and where. Real data has a lot of repetition, such as padding, headers and flat colours in images.

The last three lines count duplicate blocks. ECB: 3 duplicates out of 4. CBC (each block is mixed with the previous ciphertext block, starting from a random IV) has none. GCM has none either; it has 5 blocks because it appends a 16-byte authentication tag. The fix is to use an {{< term "aead" "AEAD" >}} mode, one that encrypts and authenticates together.

## 2. Nonce reuse

Now take a mode that uses a nonce, and reuse it. I encrypted two fake sentences under the same key and the same all-zero counter block, using CTR mode (the encryption mode GCM uses inside). CTR turns AES into a stream of key bytes and XORs it with the message. So with the same key and nonce, both messages are XORed with the same stream:

```
c1^c2 == p1^p2: true
p1^p2 = 0000000000000000000800000000000003030b011c
knowing p1, p2 = "transfer 900 to bobby"
```

`c1` and `c2` are the two ciphertexts, `p1` and `p2` the two plaintexts. The first line says that XORing the two ciphertexts gives the XOR of the two plaintexts: the key stream cancels out and the key is not needed at all. The second line is that XOR of the plaintexts. Where the two sentences have the same letters it is zero, so even without the key you see where they differ (here the digit `1` versus `9`, and `alice` versus `bobby`). The third line shows the full break: if an attacker knows one message, say because it is a predictable template, they get the other one.

The fix is a fresh random nonce for every message with {{< term "aes-gcm" "AES-GCM" >}}, taken from `crypto/rand`. A counter works only if you can guarantee it never repeats, even after a restart or across several servers.

## 3. Encryption without authentication

Encryption hides content. It does not tell you whether somebody changed the content. I flipped a single bit of one ciphertext byte and decrypted:

```
CTR tampered: "transfer 000 to alice" (no error)
GCM tampered: cipher: message authentication failed
```

With CTR, the flipped bit flipped the same bit of the plaintext: `100` silently became `000`, and the code got no error. GCM checks an authentication tag and refused to return anything. An attacker who can change bytes in transit, but cannot read them, can still do real damage to a mode with no authentication. Only authentication detects change.

## 4. `math/rand` for tokens

Session tokens, reset links and keys must be unpredictable. `math/rand` is built for simulations, not for secrets. Since Go 1.20 its top-level functions are seeded randomly, but an explicit seed is still fully deterministic. The demo has a `token` mode that prints one number from a generator seeded with 42, one from the automatically seeded generator, one from `math/rand/v2` and one from `crypto/rand`. I ran it twice:

```
run 1: seeded math/rand: afbf64b1967f8c53   unseeded: f2b0bdfc212d35dc   math/rand/v2: c09364093f1e9e26   crypto/rand: beed10f156ec3ad5
run 2: seeded math/rand: afbf64b1967f8c53   unseeded: 35bf76bacec1a4e3   math/rand/v2: a9c446ec0e2daa62   crypto/rand: a14fb6ed9f0c1072
```

(The demo prints these on four lines per run; I put each run on one line. The values other than the seeded one change on every run.) The seeded value is identical in both runs: anyone who knows the seed knows every "random" number. The other values differ here, but that does not make them safe. The Go documentation for `math/rand` and `math/rand/v2` says their output may be predictable and points to `crypto/rand` for security-sensitive work. Tokens and keys come from `crypto/rand`.

## 5. Hash misuse and the MAC

Three separate mistakes live here:

- MD5 and SHA-1 have publicly known collision attacks. Do not use them where an attacker chooses the input.
- Plain hashes are far too fast for passwords; the password post explains why.
- Using `sha256(secret || message)` as a message authentication code (a keyed fingerprint that proves a message came from someone who knows the key) is open to a {{< term "length-extension-attack" "length extension attack" >}}. I explain this, but I did not demonstrate it. The right tool is {{< term "hmac" "HMAC" >}}:

```
HMAC-SHA256: 504c1fb4aec45d534910476e45d37c2feb925e4978ae10d99635a698cd14d93b
hmac.Equal(valid, forged): false
hmac.Equal(valid, valid):  true
```

I computed a tag for `user=42&role=user`, then one for the forged `user=42&role=admin` and compared them with `hmac.Equal`: different, as expected, and a tag equals itself. (The real demo prints one more line, a plain `sha256(secret||msg)`, which is the construction you should not use.)

Why `hmac.Equal` and not `==`? Because a normal comparison stops at the first different byte, so a wrong guess that is closer to the right value can take slightly longer to reject. An attacker measuring response times could in principle guess a tag byte by byte. A {{< term "constant-time-comparison" "constant-time comparison" >}} always does the same work. Timings are noisy, so I do not show a stopwatch; I wrote a tiny separate program that counts how many bytes a naive comparison looks at for guesses with a growing number of correct leading bytes (this is a scratch program, not in the demo directory, and the numbers are exact counts, not times):

```
guess with  0 correct leading bytes: naive compare looked at  1 bytes, ConstantTimeCompare=0
guess with  1 correct leading bytes: naive compare looked at  2 bytes, ConstantTimeCompare=0
guess with  8 correct leading bytes: naive compare looked at  9 bytes, ConstantTimeCompare=0
guess with 31 correct leading bytes: naive compare looked at 32 bytes, ConstantTimeCompare=0
```

The work of the naive comparison grows with the number of correct leading bytes. That growth is the signal an attacker would try to measure. `subtle.ConstantTimeCompare` gives the same answer without that dependence. Compare tags and other secrets with `hmac.Equal` or `subtle.ConstantTimeCompare`, never `==`.

## 6. Fixed IVs and keys in code

CBC needs a fresh random IV for each message. What if you hard-code it? I encrypted the same 16-byte message twice, once with a fixed all-zero IV and once with two random IVs:

```
fixed IV, equal ciphertexts: true
random IV, equal ciphertexts: false
```

A constant IV makes the scheme deterministic: the same message always gives the same ciphertext, so an observer sees when messages repeat. Related and even worse: a key written in source code is a leaked key, because every copy of the repository and every build carries it.

## 7. Rolling your own

Inventing a "cipher" feels clever until somebody guesses the start of your message. Here is a repeating-key XOR with a 3-byte key, which is a classic home-made scheme. Messages often start with a predictable word, and the demo assumes the attacker guesses that the text begins with `Meet me`:

```
recovered key: "K3y"
decrypted: "Meet me at the old bridge at noon, bring the fake documents, tell nobody at all."
```

XORing the ciphertext with the guessed start gives the key bytes directly, and the key repeats, so the whole message falls. The lesson is not about XOR. It is that a scheme that looks fine to its author can be broken in a few lines, and real ciphers got their strength from years of public attack.

## 8. Password as key

AES wants a key of exactly 16, 24 or 32 bytes. A password is whatever length the user typed:

```
password as key: 7 bytes (aes.NewCipher accepts only 16/24/32): crypto/aes: invalid key size 7
zero-padded password is a valid key: true
```

Go refuses a 7-byte key, so the tempting "fix" is to pad the password with zeros. That works, which is the problem: it gives you a valid key that is only as strong as the password, with no cost for the attacker who tries many guesses. Derive keys with a {{< term "key-derivation-function" "key derivation function" >}} and a random {{< term "salt" "salt" >}} instead. In the demo, `scrypt.Key(pw, salt, 1<<15, 8, 1, 32)` returned a 32-byte key (the first four bytes it printed are random, since the salt is random).

## 9 and 10. TLS and signatures

Two more mistakes I only describe. `InsecureSkipVerify` turns off certificate checks in Go's TLS client, so anyone on the network path can impersonate the server; I did not run it. ECDSA signatures need a unique secret nonce for every signature, and reusing one is documented to leak the private key. The PS3 case is the usual story, which I mention from memory and did not reproduce. Ed25519 avoids the problem by design: it derives the nonce from the key and the message. The demo signs and verifies:

```
sig bytes: 64 verify: true
tampered message verify: false
```

A 64-byte signature verifies for the right message, and fails when one character of the message changes.

## What to use

| Need | Use |
|---|---|
| Encrypt data | AES-GCM or ChaCha20-Poly1305 |
| Authenticate | HMAC-SHA256 |
| Passwords | Argon2id |
| Randomness | `crypto/rand` |
| Signatures | {{< term "digital-signature" "Ed25519" >}} |
| Transport | TLS |

This table is my opinion, backed by the docs. Better still, use a high-level library and get a review. Age, NaCl `secretbox` and Tink are examples; I only name them and did not test them.

## Four short rules

- Never build your own scheme from primitives.
- Authenticate everything you encrypt.
- Every nonce or IV comes from `crypto/rand`.
- Keys come from a KDF or a key manager, not from a string in the code.

## Exercise

Write a test that encrypts 1000 messages with GCM and asserts that no two nonces repeat. Then change the code to use a counter as the nonce, and think about when that breaks (a restart, two servers).

## What's next

The next post is "Memory safety: C versus Rust". It goes one layer lower, to code that reads or writes memory it does not own.
