+++
date = '2026-11-12T18:00:00+03:30'
draft = false
title = 'Bitcoin Script: a tiny stack interpreter in Rust'
description = 'Bitcoin Script in Rust: a small stack interpreter running a P2PKH unlock with HASH160 and OP_CHECKSIG, plus wrong keys, tampered signatures and OP_RETURN.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "bitcoin", "bitcoin-script", "interpreter"]
cover = { image = "/images/covers/bc-bitcoin-script-rust.png", alt = "Bitcoin Script: a tiny stack interpreter in Rust", hiddenInSingle = true }
+++

What does "owned by Alice" mean for a single output? The previous post, [The mempool, fees and transaction selection](/posts/bc-mempool-fees/), chose which transactions enter a block; this one asks who may spend one coin.

In [Transactions and the UTXO model](/posts/bc-transactions-utxo/) our toy chain answered with a hardcoded rule: a {{< term "utxo" "UTXO" >}} stores an address, and the node checks that the input's public key hashes to it and the signature verifies. In Bitcoin, each output carries a small program, the locking script (`scriptPubKey`), and the spender supplies an unlocking script (`scriptSig`, or a witness in SegWit outputs). If running both ends in true, the coin moves. The language is {{< term "bitcoin-script" "Bitcoin Script" >}}.

It is a {{< term "stack" "stack" >}} machine, like the one in [Stacks, queues and deques](/posts/algo-stacks-queues-deques/), and, according to the Bitcoin wiki, deliberately not {{< term "turing-complete" "Turing-complete" >}}: no loops, no jumps backward. Every opcode runs at most once, so checking a script costs at most its length.

Below is a small interpreter in Rust. It is a **teaching subset, not consensus-compatible**: about ten opcodes, my own text format, a simplified signature check.

> Rust 1.90 on macOS (arm64), `k256` 0.13.4 for {{< term "ecdsa" "ECDSA" >}} on {{< term "secp256k1" "secp256k1" >}}, `sha2` 0.10.9 and `ripemd` 0.1.3. Fresh throwaway keys on every run, never funded. Local example code.

## Opcodes as an enum

An enum with data, as in [Structs, enums and pattern matching in Rust](/posts/rust-structs-enums-pattern-matching/), fits opcodes well:

```rust
pub enum Op {
    Push(Vec<u8>),
    Dup, Hash160, Equal, EqualVerify, CheckSig,
    Add, If, Else, EndIf, Return,
}
```

The parser reads text like `OP_DUP <89ab..> 5`: `OP_` names map to variants, `<hex>` pushes bytes, a decimal pushes an encoded number, anything else is an error.

The stack is `Vec<Vec<u8>>` of byte strings. Errors are an enum and every step returns `Result`, as in [Error handling with Result and Option in Rust](/posts/rust-error-handling-result/):

```rust
Op::Dup => {
    let top = self.stack.last().ok_or(ScriptError::StackUnderflow("OP_DUP"))?;
    self.stack.push(top.clone());
}
Op::Hash160 => {
    let x = self.pop("OP_HASH160")?;
    self.stack.push(hash160(&x).to_vec()); // RIPEMD-160(SHA-256(x))
}
Op::EqualVerify => {
    let (a, b) = (self.pop("OP_EQUALVERIFY")?, self.pop("OP_EQUALVERIFY")?);
    if a != b { return Err(ScriptError::EqualVerifyFailed); }
}
Op::CheckSig => {
    let pubkey = self.pop("OP_CHECKSIG")?;
    let sig = self.pop("OP_CHECKSIG")?;
    let ok = check_sig(&pubkey, &sig, self.sighash);
    self.stack.push(if ok { vec![1] } else { vec![] });
}
Op::Return => return Err(ScriptError::OpReturn),
```

`HASH160` uses the real `sha2` and `ripemd` crates; a test pins the hash of empty input, cross-checked with `openssl`. `OP_CHECKSIG` does not fail on a bad signature; it pushes false (empty bytes) and the script fails at the end.

`verify` runs the unlock script, then the lock script on the same stack, and succeeds only if the top item is true. The unlock script may only push data.

## The signature check is simplified

My `check_sig` takes a 33-byte compressed key and a 64-byte `r || s` signature and verifies it over a 32-byte {{< term "sighash" "sighash" >}} handed to the machine. According to the Bitcoin wiki, real `OP_CHECKSIG` takes a DER-encoded signature with a sighash-type byte appended, and computes the hash from the spending transaction according to that type. Here the sighash is just SHA-256 of a string.

## A P2PKH spend

{{< term "p2pkh" "P2PKH" >}} (pay to public key hash) is the classic Bitcoin lock:

```
lock:   OP_DUP OP_HASH160 <pubkey hash> OP_EQUALVERIFY OP_CHECKSIG
unlock: <sig> <pubkey>
```

The unlock pushes the signature and key. `OP_DUP` copies the key, `OP_HASH160` hashes the copy, the lock pushes the expected hash, `OP_EQUALVERIFY` compares and drops both, and `OP_CHECKSIG` checks the signature with the remaining key. That is our toy chain's hardcoded rule, written as data.

`cargo run`:

```
lock:   OP_DUP OP_HASH160 <9405bb1b..> OP_EQUALVERIFY OP_CHECKSIG
unlock: <sig 64 bytes> <pubkey 33 bytes>

alice spends           ok (7 steps)
mallory's key          error: OP_EQUALVERIFY failed
mallory sig, alice key error: script ended with false on top
tampered sig           error: script ended with false on top
tx changed after sign  error: script ended with false on top
OP_RETURN output       error: OP_RETURN: output is unspendable
unlock with OP_DUP     error: unlock script must only push data
```

Mallory's own key fails the hash check. Alice's key with Mallory's {{< term "digital-signature" "signature" >}}, one flipped bit in the signature, or a different sighash all reach `OP_CHECKSIG` and leave false. An output locked with `OP_RETURN` cannot be spent by anyone; according to the Bitcoin docs, that is how data gets embedded in outputs that nodes can forget.

## Numbers and branches

```
2 + 3 == 5             ok (5 steps)
if/else, true branch   ok (4 steps)
if/else, false branch  error: script ended with false on top
parse OP_LOOP          error: unknown token "OP_LOOP"
```

Both branch lines use the lock `OP_IF 10 OP_ELSE 20 OP_ENDIF 10 OP_EQUAL`. Unlocked with `1` it takes the first branch; with `0` it pushes 20, not 10. Skipped opcodes are not counted.

Numbers follow what the wiki describes: little-endian, sign in the top bit of the last byte, and arithmetic inputs at most 4 bytes. So `0x80` is "negative zero" and must count as false; a test checks it:

```
test errors ... ok
test numbers_round_trip ... ok
test hash160_known_vector ... ok
test p2pkh_spends_and_rejects_other_sighash ... ok
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

## Script subtleties

- A bad signature is a value (false), not an error. Check the final stack, not just "no error".
- No loops means a node knows the worst-case cost before running a script.
- This is a subset. Real Bitcoin has many more rules (signature encoding, sighash types, size limits, disabled opcodes) that I did not implement.

## Exercise

1. Add `OP_SUB` and `OP_VERIFY`, with tests for underflow.
2. Add `OP_SWAP`, then write a 2-of-2 lock with two `OP_CHECKSIG`s and `OP_ADD`, and show that one signature is not enough.
3. Add a step limit to `Machine` and test that it triggers.

## What's next

Next post: **Part one wrap-up: a small full node in Go**. It moves our nodes out of a demo process and onto disk.
