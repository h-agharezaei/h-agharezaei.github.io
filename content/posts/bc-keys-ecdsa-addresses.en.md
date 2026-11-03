+++
date = '2026-11-05T18:00:00+03:30'
draft = false
title = 'Keys, ECDSA signatures and addresses on secp256k1'
description = 'secp256k1 keys in Go: ECDSA sign and verify, RFC 6979 nonces, nonce reuse leaking the key, low-S and an EIP-55 Ethereum address, with real output.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ecdsa", "secp256k1", "ethereum", "cryptography"]
cover = { image = "/images/covers/bc-keys-ecdsa-addresses.png", alt = "Keys, ECDSA signatures and addresses on secp256k1", hiddenInSingle = true }
+++

In the chain we have built so far, anyone can write a transaction: `"alice -> bob: 10"`. Nothing shows that Alice actually wrote it. In an ordinary system the answer is simple: Alice logs in with a username and password, and the server knows who she is. But a blockchain has no login server to ask. So how can a node that has never met Alice tell that she created this transaction herself?

The answer is a digital signature. The idea is like a strange kind of seal: only one person can stamp with it, but anyone can look at the stamp and say "this really is Alice's seal". Alice has a secret number that only she knows, and she signs with it. From that secret number a public number is derived, which everybody can have and use to check her signatures. The public number is enough to check a signature, but not enough to make one.

In [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/) we proved that a transaction is in a block; here we want to prove who created it. The result of this post is a small Go package called `wallet`, which the next post uses to sign transactions. In [Common cryptography mistakes](/posts/sec-crypto-mistakes/) I only quoted the docs saying that ECDSA nonce reuse leaks the private key; this time I reproduce it myself.

> All keys on this page are fresh throwaway keys that were never funded, or private key `1`, a famous public test key. Never send money to any address on this page. Everything was run with Go 1.27.3, `github.com/decred/dcrd/dcrec/secp256k1/v4` v4.4.1 and `golang.org/x/crypto` v0.58.0 on macOS (arm64). The demo is a local module: a `wallet` package with its tests and a `cmd/demo` program.

## Private key, public key

First, two terms:

- The **private key** is that secret number. It is just a large random number, about 256 bits. Anyone who has it can sign in your name, so in practice the private key **is the account**.
- The **public key** is derived from the private key and can be given to everyone. All it can do is check signatures.

Bitcoin and Ethereum sign with {{< term "ecdsa" "ECDSA" >}}, on an elliptic curve called {{< term "secp256k1" "secp256k1" >}}. You do not need the curve math to follow the rest of this post. It is enough to know this: the curve has a fixed, public point called `G`, and a "multiplication" that multiplies a number by a point and gives another point. If the private key is `d`, the public key is the point `d·G`.

The key fact is that this multiplication is easy in one direction only. Computing `d·G` from `d` is fast. But if all you have is `d·G`, finding `d` is, with the methods we know today, practically impossible. The security of the whole thing rests on that one-way property.

## Why an external library

Go has ECDSA in `crypto/ecdsa`, but only on the standard NIST curves such as P-256. secp256k1 is not in the standard library, so we need a library. go-ethereum's `crypto` package can do it, but it is a large module. The Decred project's secp256k1 package is small and does only this, so I chose it.

## The `wallet` package

I kept the package API deliberately small. Five functions, and that is everything we need to do with a key:

```go
func Generate() (*Key, error)
func (k *Key) PublicKey() []byte        // 65 bytes: 0x04 || X || Y
func (k *Key) Sign(hash [32]byte) []byte // 64 bytes: r || s
func (k *Key) Address() string
func Verify(pub []byte, hash [32]byte, sig []byte) bool
```

- `Generate` creates a fresh random private key.
- `PublicKey` returns the public key. A point on the curve has two coordinates, `X` and `Y`, 32 bytes each. They are preceded by a `0x04` byte, which means "full, uncompressed form". 65 bytes in total.
- `Sign` signs and `Verify` checks a signature.
- `Address` we build at the end of the post.

One detail about `Sign`: it does not take the message itself, it takes the message's 32-byte hash. ECDSA always works on a fixed-size number, and which hash function produces that number is each chain's choice, not the signing package's job.

`Sign` itself just calls the library and puts the two numbers of the signature side by side:

```go
func (k *Key) Sign(hash [32]byte) []byte {
	sig := ecdsa.Sign(k.priv, hash[:])
	r, s := sig.R(), sig.S()
	out := make([]byte, 64)
	r.PutBytesUnchecked(out[:32])
	s.PutBytesUnchecked(out[32:])
	return out
}
```

An ECDSA signature is two numbers called `r` and `s`, 32 bytes each. We put them one after the other and return a 64-byte signature.

## Sign, verify, change one byte

Now let's see what a signature actually guarantees. The `sign` demo creates a fresh key, hashes the message `"pay 10 coins to bob"` and signs it twice. Then it changes one byte of the message so that `10` becomes `90`, and checks the old signature against the new message. Finally it checks the signature against someone else's public key:

```go
h := sha256.Sum256(msg) // "pay 10 coins to bob"
sig1, sig2 := k.Sign(h), k.Sign(h)
...
msg[4] = '9' // "pay 90 coins to bob"
fmt.Println("verify after one byte:", wallet.Verify(k.PublicKey(), sha256.Sum256(msg), sig1))
```

The output of `go run ./cmd/demo sign`:

```
sig: 155740b11dbd144a... 64 bytes
same sig twice: true
verify: true
verify after one byte: false
verify with other key: false
```

Line by line:

- **`sig`:** the start of the signature and its size, 64 bytes. Because a fresh key is created each time, this hex will be different if you run it yourself.
- **`same sig twice: true`:** we signed one message with one key twice and got exactly the same bytes. That is not obvious; a few sections down I explain why it matters.
- **`verify: true`:** the signature checks out against the right public key.
- **`verify after one byte: false`:** only one byte of the message changed, and the same signature is no longer accepted. You cannot take the signature for "10 coins" and put it under "90 coins".
- **`verify with other key: false`:** the same signature is rejected with someone else's public key. The signature is tied to one particular key.

That is exactly what we want from a {{< term "digital-signature" "digital signature" >}}: it ties one particular hash to one particular key. Change the message or the key and the check fails.

## The nonce: a secret number per signature

Back to `same sig twice: true`. To understand it, we need to know how ECDSA signs. Besides the private key, every signature needs another secret number that is used for that one signature only. It is called a {{< term "nonce" "nonce" >}}, and formulas call it `k`. This number must never leak and must never be reused for two different messages. Why? The next section answers that with an experiment.

The old approach was to make `k` random each time. The problem is that if the random number generator is broken, or returns the same number twice, the key leaks. Our library takes a different approach, defined in {{< term "rfc-6979" "RFC 6979" >}}: it computes `k` from the private key and the message hash using HMAC. HMAC is a keyed hash function: the same input always gives the same output, but without the key you cannot predict the output.

This has two consequences. First, the same key and message always give the same `k`, so the signature is the same too; that is what we saw in the output. Second, two different messages get different values of `k` (except with a vanishingly small probability), and no random generator is needed at signing time at all.

## Why nonce reuse leaks the key

Now let's look at the formula itself. If `z` is the message hash, ECDSA builds the signature like this:

```
r = (k·G).x
s = k⁻¹(z + r·d) mod n
```

`r` is the `x` coordinate of the point `k·G`. `s` is built from `k`, the message hash, `r` and the private key `d`. `n` is a fixed number of the curve, and `mod n` means all arithmetic is done modulo `n`.

Now suppose someone signs two different messages, `z1` and `z2`, with the same `k`. Since `r` depends only on `k`, both signatures have the same `r`, and anyone can see that. Now there are two equations and only two unknowns: `k` and `d`. This is the same two-equation system from high school:

```
k = (z1 - z2) / (s1 - s2)
d = (s1·k - z1) / r
```

Every number on the right-hand side is public: the two message hashes and the two signatures. So anyone who sees two signatures with a reused `k` can compute the private key.

To see this with my own eyes, I wrote a hand-made signer that takes `k` as input. Never do this in real code; it is only for this experiment. The `reuse` demo creates a throwaway key, signs two different messages with one `k`, and then solves the two formulas above with the library's own arithmetic. The output of `go run ./cmd/demo reuse`:

```
sig1 valid: true
sig2 valid: true
same r: true
recovered k == k: true
recovered d == private key: true
```

- **The first two lines:** both signatures are perfectly valid. Nothing about the signatures themselves is wrong.
- **`same r: true`:** the sign an attacker looks for: two signatures with the same `r`.
- **The last two lines:** from the two signatures and two hashes alone, first `k` and then the private key were recovered exactly.

So no bug in the library is needed. The math alone gives the key away. That is why RFC 6979 matters so much.

## Low-S: one signature, two forms

ECDSA has one more property we have to deal with. If `(r, s)` is a valid signature, then `(r, n - s)` is valid too. So anyone who sees your signature can, without your key, make a second valid signature for the same message.

Why is that a problem? The message has not changed and no money moves. The problem is the identifier. If a system builds a transaction ID from the hash of the whole transaction, **signature included**, then changing the signature changes the ID. Now one transaction exists with two different IDs, and software that tracks payments by ID can get confused. This property is called {{< term "signature-malleability" "signature malleability" >}}.

The usual fix is simple: of the two forms, accept only the one with the smaller `s`, meaning `s` less than half of `n`. Our library always produces that form, and my `Verify` rejects the larger one. The `lows` demo takes a normal signature, turns `s` into `n - s`, and checks the new signature in two ways:

```
high-S, raw ECDSA verify: true
high-S, wallet.Verify:   false
```

The first line shows that, as far as ECDSA's math is concerned, the high-S signature is perfectly valid. The second shows that `wallet.Verify` rejects it, so in our system every valid signature has exactly one form.

According to the specs, Ethereum has required low S in transactions since EIP-2, and Bitcoin Core's relay policy does not relay transactions with a high S either.

## An Ethereum-style address

A public key is 65 bytes, which is too long to write down, copy and read. So chains use an **address** instead: a shorter form made from a hash of the public key. An Ethereum address is built like this:

1. Drop the leading `0x04` byte of the public key, leaving the 64 bytes `X || Y`.
2. Take the {{< term "keccak-256" "Keccak-256" >}} of those 64 bytes.
3. The last 20 bytes of the hash are the address.

```go
func Address(pub []byte) string {
	h := Keccak256(pub[1:]) // drop the 0x04 prefix
	return checksum(hex.EncodeToString(h[12:]))
}
```

There is a small trap here. Keccak is the algorithm that later, with a small change, became the SHA-3 standard. Ethereum uses the original Keccak, not NIST's standard SHA3-256. They differ only in the padding, the bytes appended to the end of the input before hashing. But that small difference changes the whole output. In Go you have to use `sha3.NewLegacyKeccak256`; pick `sha3.New256` and you build wrong addresses.

The last step is `checksum`. A 20-byte address is written as 40 hex characters, and people make mistakes when they copy it. If one character is wrong, the money goes to an address nobody has the key for. {{< term "eip-55" "EIP-55" >}} has a clever trick for this: it uses upper and lower case as a checksum. First it computes the Keccak of the lowercase address itself. Then, for every letter `a` to `f` in the address, it looks at the nibble (half a byte, one hex digit) in the same position of the hash. If that digit is 8 or more, it writes the letter in uppercase. Now if someone mistypes a character, the pattern of upper and lower case will very likely no longer match the hash, and a wallet can warn before sending.

The output of `go run ./cmd/demo keys`:

```
pubkey: 65 bytes, prefix 04
address: 0x2E0B564f4791229D3e027B595be21Da9f9fbbaF2
checksum ok: true
test key 1: 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf
```

- **The first line:** the public key is 65 bytes and starts with `04`, the uncompressed form.
- **`address`:** the address of a fresh key, with EIP-55 mixed case. This address changes on every run too.
- **`checksum ok`:** `ValidChecksum` recomputed the case pattern and it matches the address.
- **`test key 1`:** the address of private key `1`. This key is used as an example everywhere and its address is well known, so it is a good way to check the whole path.

The tests pin three things: the address of key `1` (which was also compared against pycryptodome's Keccak), the example from the EIP-55 text itself, and Keccak-256 of empty input. All passed:

```
ok  	example.com/bckeys/wallet	0.344s
```

Bitcoin addresses are different and I did not implement them here. As far as I know, Bitcoin hashes the public key (usually the 33-byte compressed form) first with SHA-256 and then with RIPEMD-160, and, depending on the address type, shows the result as Base58Check or Bech32.

## Key and signature traps

- **The private key is the account.** Anyone who sees it can spend all the money, and there is no "password reset". So never log, print or commit it; even in a test environment, a bad habit reaches production easily.
- **Never generate nonces yourself.** As the `reuse` demo showed, one repetition is enough to leak the key. Use a library that implements RFC 6979, or a signature algorithm that does not have this problem by design.
- **If anything identifies data by its signature bytes, enforce low-S.** Otherwise anyone can build the second form of a signature and quietly change the identifier.
- **An address is a hash and there is no way back.** You cannot get the public key from an address. To check a signature, the public key has to come from somewhere else, for example inside the transaction itself.

## Exercise

1. Write a `Compressed()` method that returns the 33-byte public key, and check that `secp256k1.ParsePubKey` accepts both forms.
2. Write a test that flips one random byte of a signature and asserts that `Verify` fails.
3. Make `ValidChecksum` also accept all-lowercase addresses (as far as I know, tools treat such an address as carrying no checksum) and write a test for it.

## What's next

The next post is "Transactions and the UTXO model". Now that we can sign, we sign transactions with this same `wallet` package and see how Bitcoin moves money without any "account balance".
