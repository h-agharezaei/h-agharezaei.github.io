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

What does it actually mean to say "this coin belongs to Alice"? In our toy chain the answer is a rule written into the node's code. In [Transactions and the UTXO model](/posts/bc-transactions-utxo/), every {{< term "utxo" "UTXO" >}} stores an address. To spend it, an input must bring a public key whose hash is that address, and a signature that this key verifies. The node checks exactly that, every time.

That works, as long as everyone only wants that one kind of ownership. But what if a coin should need two signatures out of three? Or should only be spendable after a certain date? With a rule written into the node, every new kind of ownership means changing and updating every node in the network.

Bitcoin's answer is to turn ownership into data. Each output carries a small program, the **lock**. Whoever wants to spend the output brings another small program, the **unlock**. The node runs the two one after the other: if the result is "true", the coin can move. Think of a padlock on a box. The owner chooses the padlock when the coin is created, and the spender has to bring something that opens it. The node does not need to know what kind of padlock it is; it only needs to know how to try it.

The language of these programs is {{< term "bitcoin-script" "Bitcoin Script" >}}. In Bitcoin the lock is called `scriptPubKey` and the unlock `scriptSig`; in newer SegWit outputs the unlock data goes in a separate part called the witness. In the [previous post](/posts/bc-mempool-fees/) we saw which transactions get into a block; this post asks who is allowed to spend a single coin.

Below I build a small interpreter for it in Rust. One warning up front: this is a **teaching subset, not compatible with Bitcoin's consensus**. It has about ten opcodes, its own text format and a simplified signature check. It is good for understanding the idea, not for checking real transactions.

> Everything below was run with Rust 1.90 on macOS (arm64). I used `k256` 0.13.4 for {{< term "ecdsa" "ECDSA" >}} on the {{< term "secp256k1" "secp256k1" >}} curve, and `sha2` 0.10.9 and `ripemd` 0.1.3 for hashing. The keys are new on every run, throwaway, and never funded. The code is a local example.

## A machine that only has a stack

Script runs on a {{< term "stack" "stack" >}}, the same data structure as in [Stacks, queues and deques](/posts/algo-stacks-queues-deques/): a pile on which you can only put something on top or take the top item off. A Script program is a list of instructions read from left to right. Each instruction is called an **opcode**. Data in the program, such as a number or a key, is simply put on top of the stack. An opcode takes its inputs from the top of the stack and puts its result back there.

A tiny example before any code: the unlock is `2 3` and the lock is `OP_ADD 5 OP_EQUAL`. The machine runs them one after the other:

1. `2`: the stack is `[2]`.
2. `3`: the stack is `[2, 3]`.
3. `OP_ADD` takes the two top items and puts their sum on top: `[5]`.
4. `5`: `[5, 5]`.
5. `OP_EQUAL` takes the two top items and puts "true" if they are equal: `[true]`.

The program ends with "true" on top, so the spend is valid. In plain words, this lock says: "anyone who brings two numbers that add up to 5 can spend this coin". That is of course a terrible lock, since anyone can solve it, but it shows how it works.

Script deliberately has no loops and no backward jumps. According to the Bitcoin wiki, it is intentionally not {{< term "turing-complete" "Turing-complete" >}}, that is, it cannot express every possible computation. That is a feature, not a limitation. Since each opcode runs at most once, a node knows before running a script that its cost is at most proportional to its length. No one can send a script that runs forever.

## Opcodes as an enum

In Rust, an enum whose variants can carry data, as in [Structs, enums and pattern matching in Rust](/posts/rust-structs-enums-pattern-matching/), is a natural fit for opcodes:

```rust
pub enum Op {
    Push(Vec<u8>),
    Dup, Hash160, Equal, EqualVerify, CheckSig,
    Add, If, Else, EndIf, Return,
}
```

`Push` carries the bytes it puts on the stack; the other variants are the opcodes themselves. The parser reads text like `OP_DUP <89ab..> 5`: each name starting with `OP_` becomes its variant, `<hex>` becomes a push of those bytes, a decimal number becomes a push of that number in Script's encoding (more on that below), and anything else is an error.

The stack itself is `Vec<Vec<u8>>`: a list of byte strings. Script has no types; a number, a key and a signature are all just bytes on the stack, and each opcode decides how to read them. Errors are an enum, and every step returns a `Result`, as in [Error handling with Result and Option in Rust](/posts/rust-error-handling-result/). Here are the opcodes that matter most for this post:

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

- **`OP_DUP`** copies the top item and puts the copy on top. If the stack is empty, that is a `StackUnderflow` error.
- **`OP_HASH160`** takes the top item and puts its HASH160 on top: first SHA-256, then RIPEMD-160 of the result, which gives 20 bytes. It uses the real `sha2` and `ripemd` crates. A test pins the HASH160 of an empty input (`b472a266…`), and I checked the same value separately with `openssl`.
- **`OP_EQUALVERIFY`** takes the two top items. If they are equal, it continues and leaves nothing on the stack. If not, the script fails right there with an error.
- **`OP_CHECKSIG`** takes a public key and a signature and checks the signature. Pay attention to this one: a bad signature is **not** an error. It just puts "false" on the stack (empty bytes), and the script fails at the end, because "false" is on top.
- **`OP_RETURN`** fails immediately, always.

`verify` puts it all together. It first runs the unlock, then runs the lock on **the same stack**, and succeeds only if the item on top at the end is "true". It also has one more rule: the unlock may only push data. The unlock's job is to supply data, such as a signature and a key; all the logic belongs to the lock the owner chose.

## The signature check is simplified

Before the main example, a note on what I simplified. A signature in Bitcoin does not sign "anything"; it signs a hash of the spending transaction. That hash is called the {{< term "sighash" "sighash" >}}. So a signature for one transaction is useless for another one.

My `check_sig` takes a 33-byte compressed public key and a 64-byte signature (`r` and `s` side by side), and checks the signature against a 32-byte sighash that is handed to the machine. In the demo that sighash is only the SHA-256 of a sentence like "toy tx: alice pays bob 1 coin", a stand-in for a real transaction. According to the Bitcoin wiki, the real `OP_CHECKSIG` takes a DER-encoded signature with one extra byte for the sighash type at the end, and computes the hash itself from the spending transaction according to that type. None of that is here.

## A P2PKH spend

Now the classic Bitcoin lock, {{< term "p2pkh" "P2PKH" >}}, short for pay to public key hash. In plain words it says: "whoever brings a public key with this hash, and a valid signature from that key, can spend this coin". It is the same rule as in our toy chain, only written as a program:

```
lock:   OP_DUP OP_HASH160 <pubkey hash> OP_EQUALVERIFY OP_CHECKSIG
unlock: <sig> <pubkey>
```

Let's follow the stack step by step. The unlock runs first:

1. `<sig>`: `[sig]`
2. `<pubkey>`: `[sig, pubkey]`

Then the lock, on the same stack:

3. `OP_DUP` copies the key: `[sig, pubkey, pubkey]`
4. `OP_HASH160` hashes the copy: `[sig, pubkey, hash(pubkey)]`
5. `<pubkey hash>`, the hash written in the lock: `[sig, pubkey, hash(pubkey), pubkey hash]`
6. `OP_EQUALVERIFY` compares the two top items. If the key is not the right one, the script stops here. If it is, both are removed: `[sig, pubkey]`
7. `OP_CHECKSIG` checks the signature with the key: `[true]`

Seven steps, and "true" on top. `OP_DUP` exists because the key is needed twice: once to compare its hash, and once to check the signature.

`cargo run` builds a lock for Alice and tries it in several ways. Since the keys are new on every run, the hash in the first line is different every time:

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

The first two lines are the lock (the hash is shortened) and the shape of the unlock: a 64-byte signature and a 33-byte key. Then each line is one attempt:

- **`alice spends`:** Alice's signature and key. Exactly the seven steps above, and it succeeds.
- **`mallory's key`:** Mallory signs with her own key and brings her own key. The hash of her key is not the hash in the lock, so the script stops at `OP_EQUALVERIFY`.
- **`mallory sig, alice key`:** Mallory is smarter this time: she brings Alice's key, which is public, so it passes the hash check. But the signature is hers, and it does not verify with Alice's key. `OP_CHECKSIG` puts "false", and the script ends with false on top.
- **`tampered sig`:** Alice's real signature, with one bit changed. Again "false".
- **`tx changed after sign`:** Alice's correct signature, but checked against a different sighash, as if someone had changed the transaction after it was signed (for example, the recipient became Mallory). The signature does not cover the new transaction, so "false".
- **`OP_RETURN output`:** the lock is `OP_RETURN <68656c6c6f>` (the bytes after it spell "hello"). It does not matter what the unlock is: `OP_RETURN` fails at once, so nobody can ever spend this output. According to the Bitcoin docs, this is how data is embedded in transactions: since such an output can never be spent, nodes do not need to keep it among the unspent outputs.
- **`unlock with OP_DUP`:** an unlock that contains an opcode instead of just data. `verify` rejects it before running anything.

Three of these failures, Mallory's signature, the tampered signature and the changed transaction, end the same way: with "false" on top. That is the difference between `OP_EQUALVERIFY`, which stops the script with an error, and `OP_CHECKSIG`, which only produces a value.

## Numbers and branches

The same `cargo run` then tries numbers and branches:

```
2 + 3 == 5             ok (5 steps)
if/else, true branch   ok (4 steps)
if/else, false branch  error: script ended with false on top
parse OP_LOOP          error: unknown token "OP_LOOP"
```

- **`2 + 3 == 5`:** the small example from the start of this post. Five steps: two pushes in the unlock, then `OP_ADD`, the push of `5`, and `OP_EQUAL`.
- **The two branch lines** use the same lock: `OP_IF 10 OP_ELSE 20 OP_ENDIF 10 OP_EQUAL`. `OP_IF` takes the top item. If it is true, the part up to `OP_ELSE` runs; if not, the part after it. With an unlock of `1`, the first branch runs and pushes 10, and 10 equals 10. Only four steps are counted, because the opcodes that were skipped, and `OP_IF`, `OP_ELSE` and `OP_ENDIF` themselves, are not counted. With an unlock of `0`, the second branch pushes 20, and 20 does not equal 10.
- **`parse OP_LOOP`:** there is no such opcode, and the parser rejects it. No loop can be written in this language.

Numbers in Script have their own encoding, the one the Bitcoin wiki describes: bytes in little-endian order (least significant byte first), with the sign in the top bit of the last byte. So 1 is `01`, -1 is `81`, and 128 needs two bytes, `80 00`, because the top bit of `80` would otherwise be read as a minus sign. The inputs of arithmetic opcodes may be at most 4 bytes long. One odd consequence: a byte string whose only set bit is the sign bit, such as `80` or `00 80`, is "negative zero", and it must count as false. A test checks exactly that. Here is the output of `cargo test` (the order of the tests can change from run to run):

```
test errors ... ok
test numbers_round_trip ... ok
test hash160_known_vector ... ok
test p2pkh_spends_and_rejects_other_sighash ... ok
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

- **`errors`:** a stack underflow, an `OP_IF` without `OP_ENDIF` and an `OP_ENDIF` without `OP_IF`, a number longer than 4 bytes, bad hex in the parser, and an `OP_RETURN` inside a branch that is not taken, which does nothing.
- **`numbers_round_trip`:** a list of numbers is encoded and decoded back, and negative zero is false.
- **`hash160_known_vector`:** the HASH160 of an empty input, the same value I checked with `openssl`.
- **`p2pkh_spends_and_rejects_other_sighash`:** a P2PKH spend with a fixed test key succeeds in 7 steps, and fails against a different sighash.

## Script subtleties

- **A bad signature is a value, not an error.** `OP_CHECKSIG` puts "false" and the script goes on. So "it ran without an error" does not mean "it is valid". Always check what is on top of the stack at the end, as `verify` does.
- **No loops means a known cost.** Since nothing runs twice, a node knows the worst-case cost of a script before it runs it. That matters a lot in a network where anyone can send any script.
- **This is only a subset.** Real Bitcoin has many more rules that I did not implement: the exact signature encoding, sighash types, size limits, disabled opcodes, and more. Do not use this interpreter to check real transactions.

## Exercise

1. Add `OP_SUB` and `OP_VERIFY`, with tests for stack underflow.
2. Add `OP_SWAP`, then write a 2-of-2 lock with two `OP_CHECKSIG`s and an `OP_ADD`, and show that one signature is not enough.
3. Add a limit on the number of steps to `Machine`, and write a test that shows the limit is hit.

## What's next

The next post is "Part one wrap-up: a small full node in Go". Until now our nodes have lived inside demo processes and forgotten everything when they stopped; there they get a disk, and all the pieces of the first part come together in one node.
