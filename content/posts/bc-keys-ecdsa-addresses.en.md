+++
date = '2026-11-05T18:00:00+03:30'
draft = false
title = 'Keys, ECDSA signatures and addresses on secp256k1'
description = 'secp256k1 keys in Go: ECDSA sign and verify, RFC 6979 nonces, nonce reuse leaking the key, low-S and an EIP-55 Ethereum address, with real output.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ecdsa", "secp256k1", "ethereum", "cryptography"]
cover = { image = "/images/covers/bc-keys-ecdsa-addresses.png", alt = "Keys, ECDSA signatures and addresses on secp256k1", hiddenInSingle = true }
+++

The previous post, [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/), was about proving that data is in a block. A chain also has to answer: who may spend? There is no login server. You sign with a private key and every node checks the signature with your public key. This post builds a small Go package for that, for the next post to reuse. In [Common cryptography mistakes](/posts/sec-crypto-mistakes/) I only quoted the docs saying that ECDSA nonce reuse leaks the private key; this time I reproduce it.

> All keys below are fresh throwaway keys that were never funded, or private key `1`, a famous public test key. Never send money to any address on this page. Go 1.27.3, `github.com/decred/dcrd/dcrec/secp256k1/v4` v4.4.1 and `golang.org/x/crypto` v0.58.0 on macOS (arm64). The demo is a local module: a `wallet` package with tests and a `cmd/demo` program.

## Why a library

Bitcoin and Ethereum sign with {{< term "ecdsa" "ECDSA" >}} on the {{< term "secp256k1" "secp256k1" >}} curve. Go's `crypto/ecdsa` supports the NIST curves (P-256 and friends) but not secp256k1, so we need a library. go-ethereum's `crypto` package would work but is a large module; Decred's secp256k1 package is small and focused, so I used it.

A private key is a random number `d` in [1, n-1], about 256 bits. The public key is the curve point `d·G`, where `G` is a fixed generator. Going from `d` to the point is cheap; going back is infeasible.

## The `wallet` package

The API is deliberately tiny:

```go
func Generate() (*Key, error)
func (k *Key) PublicKey() []byte        // 65 bytes: 0x04 || X || Y
func (k *Key) Sign(hash [32]byte) []byte // 64 bytes: r || s
func (k *Key) Address() string
func Verify(pub []byte, hash [32]byte, sig []byte) bool
```

`Sign` takes a 32-byte hash, not a message; which hash to use is the chain's choice.

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

## Sign, verify, change one byte

```go
h := sha256.Sum256(msg) // "pay 10 coins to bob"
sig1, sig2 := k.Sign(h), k.Sign(h)
...
msg[4] = '9' // "pay 90 coins to bob"
fmt.Println("verify after one byte:", wallet.Verify(k.PublicKey(), sha256.Sum256(msg), sig1))
```

```
sig: 155740b11dbd144a... 64 bytes
same sig twice: true
verify: true
verify after one byte: false
verify with other key: false
```

A {{< term "digital-signature" "digital signature" >}} binds this exact hash to this exact key. Change the amount or the key and it fails.

Note `same sig twice: true`. ECDSA needs a secret per-signature {{< term "nonce" "nonce" >}} `k`. The library derives it with {{< term "rfc-6979" "RFC 6979" >}}: an HMAC of the private key and the hash, instead of a random number. Same key and hash, same signature, and no random generator needed at signing time.

## Why nonce reuse leaks the key

A signature is `r = (k·G).x` and `s = k⁻¹(z + r·d) mod n`, where `z` is the hash. If one key signs two hashes with the same `k`, both share `r`, and two equations with two unknowns are enough:

```
k = (z1 - z2) / (s1 - s2)
d = (s1·k - z1) / r
```

To check that, I wrote a textbook signer that takes `k` as a parameter (never do this), signed two messages with one throwaway key and one reused `k`, and solved the equations with the library's scalar arithmetic:

```
sig1 valid: true
sig2 valid: true
same r: true
recovered k == k: true
recovered d == private key: true
```

Both signatures are valid; the math alone gives the key away.

## Low-S and malleability

If `(r, s)` is valid then `(r, n - s)` is valid too. This is {{< term "signature-malleability" "signature malleability" >}}: anyone can make a second valid signature, and if a transaction ID covers the signature, the ID changes. The library always outputs the lower `s`, and my `Verify` rejects the higher one:

```
high-S, raw ECDSA verify: true
high-S, wallet.Verify:   false
```

According to the specs, Ethereum transactions (EIP-2) require low S, and Bitcoin Core's relay policy does too.

## An Ethereum-style address

An Ethereum address is the last 20 bytes of {{< term "keccak-256" "Keccak-256" >}} of the 64 bytes `X || Y`. Keccak-256 is not the NIST SHA3-256 (the padding differs), so in Go use `sha3.NewLegacyKeccak256`. Then {{< term "eip-55" "EIP-55" >}} uppercases each hex letter whose nibble in the Keccak hash of the lowercase address is 8 or more:

```go
func Address(pub []byte) string {
	h := Keccak256(pub[1:]) // drop the 0x04 prefix
	return checksum(hex.EncodeToString(h[12:]))
}
```

```
pubkey: 65 bytes, prefix 04
address: 0x2E0B564f4791229D3e027B595be21Da9f9fbbaF2
checksum ok: true
test key 1: 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf
```

The tests pin the key-1 address (cross-checked with pycryptodome's Keccak), the EIP-55 spec example and Keccak-256 of empty input. All passed:

```
ok  	example.com/bckeys/wallet	0.344s
```

Bitcoin addresses differ and I did not implement them: as far as I know, they hash the (usually compressed) public key with SHA-256 then RIPEMD-160 and encode it as Base58Check or Bech32, depending on type.

## A few things to watch

- The private key is the account. Never log, print or commit it.
- Never generate nonces yourself; use a library that does RFC 6979.
- Enforce low-S in verification if anything identifies data by its signature bytes.
- An address is a hash: you cannot get the public key back from it.

## Exercise

1. Add `Compressed()` that returns the 33-byte public key, and check that `secp256k1.ParsePubKey` accepts both forms.
2. Write a test that flips one random byte in a signature and asserts `Verify` fails.
3. Make `ValidChecksum` accept all-lowercase addresses (as far as I know, tools treat them as carrying no checksum) and test it.

## What's next

Next post: **Transactions and the UTXO model**. We sign transactions with this `wallet` package.
