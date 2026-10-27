+++
date = '2027-05-17T10:00:00+03:30'
draft = false
title = 'Common cryptography mistakes'
description = 'Common cryptography mistakes in Go: ECB, nonce reuse, no authentication, math/rand, hash misuse, fixed IVs, XOR ciphers and weak keys, with real output.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "cryptography", "encryption", "go", "hmac"]
cover = { image = "/images/covers/sec-crypto-mistakes.png", alt = "Common cryptography mistakes", hiddenInSingle = true }
+++

The previous post, [SSRF and unsafe deserialization](/posts/sec-ssrf-deserialization/), was about trusting input too much. Cryptography fails the same way: the code works, the tests pass, and the design is still broken. [Managing secrets and keys](/posts/sec-secrets-management/) covered AES-GCM, nonces and envelope encryption, so I will not repeat them. This is the "what goes wrong" catalogue. Password storage is in [Storing passwords safely](/posts/sec-password-hashing/) and certificates in [TLS and x509 certificates in practice](/posts/sec-tls-x509-certificates/).

> Defensive only. Every key and sentence is an obvious FAKE and everything ran locally with Go 1.26 and `golang.org/x/crypto` v0.31.0. I did not try to find hash collisions or attack anything real. The demo is one small `main.go` plus a test, run with `go test -race`, which passed.

## 1. ECB leaks patterns

Go has no ECB helper, so I encrypt block by block with `cipher.Block`. Plaintext: 64 bytes of `A`.

```
block 0 9716d7a815f1ccfe34e0a747bd079f4c
block 1 9716d7a815f1ccfe34e0a747bd079f4c
block 2 9716d7a815f1ccfe34e0a747bd079f4c
block 3 9716d7a815f1ccfe34e0a747bd079f4c
ECB: 4 blocks, 3 duplicates
CBC: 4 blocks, 0 duplicates
GCM: 5 blocks (incl. tag), 0 duplicates
```

{{< term "ecb-mode" "ECB" >}} encrypts equal blocks to equal blocks, so structure shows through. CBC with a random IV and GCM do not. Fix: use an {{< term "aead" "AEAD" >}} mode.

## 2. Nonce reuse

Two fake sentences under the same key and the same zero counter block (CTR is what GCM uses inside):

```
c1^c2 == p1^p2: true
knowing p1, p2 = "transfer 900 to bobby"
```

The key cancels out. Knowing one message gives the other. Use a fresh random {{< term "nonce" "nonce" >}} per message with {{< term "aes-gcm" "AES-GCM" >}}.

## 3. Encryption without authentication

I flipped one ciphertext bit:

```
CTR tampered: "transfer 000 to alice" (no error)
GCM tampered: cipher: message authentication failed
```

CTR silently changed `100` into `000`. GCM refused. Encryption hides content; only authentication detects change.

## 4. `math/rand` for tokens

Since Go 1.20 the top-level `math/rand` functions are seeded randomly, but an explicit seed is still deterministic. I ran two processes:

```
run 1: seeded math/rand: afbf64b1967f8c53   unseeded: f08b0fe9b34522d4
run 2: seeded math/rand: afbf64b1967f8c53   unseeded: 9da761b5e88de565
```

The seeded value repeated. Even the auto-seeded one is not designed to be secret, and `math/rand/v2` is the same kind of generator. Tokens and keys come from `crypto/rand`.

## 5. Hash misuse

- MD5 and SHA-1 have publicly known collision attacks; do not use them where an attacker chooses the input.
- Plain hashes are far too fast for passwords; see the password post.
- `sha256(secret || msg)` as a MAC is open to a {{< term "length-extension-attack" "length extension attack" >}} (explained, not demonstrated). Use {{< term "hmac" "HMAC" >}}:

```
HMAC-SHA256: 504c1fb4aec45d534910476e45d37c2feb925e4978ae10d99635a698cd14d93b
hmac.Equal(valid, forged): false
```

Compare tags with `hmac.Equal`, a {{< term "constant-time-comparison" "constant-time comparison" >}}, never `==`.

## 6. Fixed IVs and keys in code

```
fixed IV, equal ciphertexts: true
random IV, equal ciphertexts: false
```

A constant IV makes CBC deterministic, so an observer sees repeated messages. A key in source code is a leaked key.

## 7. Rolling your own

A repeating-key XOR "cipher" with a 3-byte key falls to a guess of the first word:

```
recovered key: "K3y"
decrypted: "Meet me at the old bridge at noon, bring the fake documents, tell nobody at all."
```

## 8. Password as key

```
password as key: 7 bytes: crypto/aes: invalid key size 7
zero-padded password is a valid key: true
```

Padding makes it "work" and makes it weak. Derive keys with a {{< term "key-derivation-function" "key derivation function" >}} and a random {{< term "salt" "salt" >}}: `scrypt.Key(pw, salt, 1<<15, 8, 1, 32)` returned 32 bytes.

## 9 and 10. TLS and signatures

`InsecureSkipVerify` turns off certificate checks, so anyone on the path can impersonate the server; I did not run it here. ECDSA needs a unique secret nonce per signature; reuse is documented to leak the private key (the PS3 case is the usual story, which I mention from memory and did not reproduce). Ed25519 avoids this by design:

```
sig bytes: 64 verify: true
tampered message verify: false
```

## What to use

| Need | Use |
|---|---|
| Encrypt data | AES-GCM or ChaCha20-Poly1305 |
| Authenticate | HMAC-SHA256 |
| Passwords | Argon2id |
| Randomness | `crypto/rand` |
| Signatures | {{< term "digital-signature" "Ed25519" >}} |
| Transport | TLS |

This is my opinion backed by the docs. Better still, use a high-level library (age, NaCl `secretbox`, Tink; I only name them) and get a review.

## A few things to watch

- Never build your own scheme from primitives.
- Authenticate everything you encrypt.
- Every nonce or IV comes from `crypto/rand`.
- Keys come from a KDF or a manager, not a string.

## Exercise

Write a test that encrypts 1000 messages with GCM and asserts that no two nonces repeat, then change the code to a counter and think about when that breaks.

## What's next

The next post is Memory safety: C versus Rust.
