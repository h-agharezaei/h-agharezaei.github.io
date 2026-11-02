+++
date = '2026-12-01T18:00:00+03:30'
draft = false
title = 'Zero-knowledge proof basics in Rust'
description = 'Zero-knowledge proofs in Rust: a Schnorr proof on secp256k1, a cheating prover, Fiat-Shamir and its forgery bug, and nonce reuse leaking the secret.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "zero-knowledge", "schnorr", "cryptography", "secp256k1"]
cover = { image = "/images/covers/bc-zero-knowledge-rust.png", alt = "Zero-knowledge proof basics in Rust", hiddenInSingle = true }
+++

The previous post, [Bridges and cross-chain messaging](/posts/bc-bridges-cross-chain/), was about one chain trusting a claim about another. Zero-knowledge proofs go further: convince someone a statement is true without showing why. In [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/) the proof revealed the leaf; in [Keys, ECDSA signatures and addresses on secp256k1](/posts/bc-keys-ecdsa-addresses/) a reused nonce leaked a private key. Both come back here.

> Toy code for learning, not production. Every secret is a fresh random scalar and is never printed. Rust 1.90, `k256` 0.13.4 (feature `arithmetic`), `sha2` 0.10.9, `rand_core` 0.6.4, macOS (arm64). The demo is a local Cargo project.

## What a proof promises

A {{< term "zero-knowledge-proof" "zero-knowledge proof" >}} runs between a prover and a verifier and promises:

- **Completeness**: an honest prover with the secret always convinces.
- **Soundness**: a prover without the secret fails, except with negligible probability.
- **Zero-knowledge**: the verifier learns only "true"; it could have generated everything it saw by itself.

Our statement: "I know `x` with `X = x·G`" on secp256k1. Finding `x` from `X` is the {{< term "discrete-logarithm" "discrete logarithm" >}} problem, believed infeasible on this curve.

## The interactive Schnorr protocol

In the {{< term "schnorr" "Schnorr protocol" >}} the prover commits `R = r·G` for a random `r`, the verifier sends a random challenge `c`, the prover answers `s = r + c·x`:

```rust
fn commit() -> (Scalar, Point) {
    let r = Scalar::random(&mut OsRng);
    (r, G * r)
}
fn respond(x: Scalar, r: Scalar, c: Scalar) -> Scalar {
    r + c * x
}
fn verify(pub_x: Point, big_r: Point, c: Scalar, s: Scalar) -> bool {
    G * s == big_r + pub_x * c
}
```

`r` is a {{< term "nonce" "nonce" >}} that hides `x` inside `s`. Completeness:

```
== interactive, honest prover ==
accepted 1000/1000
```

## Soundness: a cheater and an extractor

A cheater without `x` can guess `c`, pick any `s` and set `R = s·G - c_guess·X`. It passes only if the verifier sends exactly `c_guess`: probability 1/q for group order q. On secp256k1 that is about 2^-256, so I also used a toy group where 4 has order 11 modulo 23:

```
== cheating prover (does not know x) ==
toy group q=11: 8837/100000 = 0.0884 (1/q = 0.0909)
secp256k1:      0/10000
```

Three more runs gave 0.0905, 0.0920 and 0.0895.

Why no better strategy? A prover answering two challenges for one `R` reveals `x = (s1 - s2) / (c1 - c2)`, so reliable answering means knowing `x`:

```
== extractor: same R, two challenges ==
both transcripts valid: true, extracted x == x: true
```

## Zero-knowledge: a simulator

Pick `c` and `s` first, then `R = s·G - c·X`, with no `x`:

```
== simulator: valid transcript without x ==
simulated (R, c, s) verifies: true
```

Simulated transcripts look like real ones, so a transcript teaches nothing about `x`. This assumes a random `c` (honest-verifier zero-knowledge).

## Fiat-Shamir: no verifier needed

The {{< term "fiat-shamir" "Fiat-Shamir transform" >}} replaces the verifier with a hash of the transcript, so anyone can check the proof later, like a {{< term "digital-signature" "signature" >}}:

```rust
fn challenge(pub_x: Point, big_r: Point, msg: &[u8]) -> Scalar {
    hash_to_scalar(&[b"bc30/schnorr/v1", &enc(G), &enc(pub_x), &enc(big_r), msg])
}
```

```
== Fiat-Shamir ==
proof: R=02010fea30003cab.. s=5be1affab357361e..
check: true
check other msg: false
check other key: false
```

The classic bug is leaving something out of the hash. My buggy `challenge_no_r` skips `R`, so the attacker learns `c` before choosing `R`, the simulator's trick:

```rust
let c = challenge_no_r(pub_x, msg);
let s = Scalar::random(&mut OsRng);
let forged = Proof { big_r: G * s - pub_x * c, s };
```

```
== bug: R not hashed -> forgery ==
forged, buggy verifier: true
forged, correct verifier: false
```

A valid proof for a key whose secret the attacker never had. Omitting the public key is documented to break things similarly; I did not demonstrate that.

## Nonce reuse leaks the secret

The extractor is also an attack. Two proofs with the same `r` have different challenges:

```
== nonce reuse leaks x ==
both valid: true, same R: true
recovered x == x: true
```

Same algebra as the {{< term "ecdsa" "ECDSA" >}} leak in BC4. According to BIP-340, Bitcoin's Schnorr signatures are this construction on secp256k1, with tagged hashes and a recommended nonce derivation.

## Zooming out (no code)

Schnorr proves one fixed statement. General systems prove "this program ran correctly on secret inputs":

- **Circuits**: the computation becomes arithmetic constraints over a finite field (arithmetization); the prover shows a satisfying assignment exists.
- A {{< term "zk-snark" "zk-SNARK" >}} has tiny proofs (Groth16: three group elements, according to its paper) and fast verification. Many SNARKs need a {{< term "trusted-setup" "trusted setup" >}}; whoever keeps its secret randomness can forge proofs.
- A {{< term "zk-stark" "zk-STARK" >}} is transparent (only hash functions, no setup); as far as I know its proofs are much larger, tens of kilobytes or more.
- **ZK-rollups** post a batch plus a validity proof; an L1 contract verifies it before accepting the new state root (see [Layer 2 and rollups: optimistic and ZK](/posts/bc-layer2-rollups/)).
- **Privacy**: prove membership in a Merkle tree without revealing the leaf. Zcash's shielded transactions use zk-SNARKs.

Real systems use libraries such as arkworks, halo2 or RISC Zero; I did not use them here.

## A few things to watch

- Hash everything into the challenge: domain tag, generator, public key, commitment, message.
- Never reuse or bias a nonce; one repeat gives the secret away.
- Use audited libraries; this code is neither constant-time nor reviewed.
- Ask what a trusted setup trusts and who destroyed its secrets.

## Exercise

1. Remove `pub_x` from `challenge` and try to forge: pick `R` first, hash, then choose the key.
2. Use q = 5 (4 has order 5 modulo 11) and check the cheat rate.
3. Turn `prove` into a signature with BIP-340-style nonces.

## What's next

Next post: **Exchange engineering: deposits, withdrawals, confirmations and reorgs**.
