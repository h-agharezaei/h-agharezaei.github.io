+++
date = '2027-06-25T10:00:00+03:30'
draft = false
title = 'Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter'
seoTitle = 'Inside the EVM: a tiny Rust interpreter'
description = 'EVM internals in Rust: a tiny interpreter with 256-bit stack, memory, storage, calldata, JUMPDEST checks, REVERT and gas that stops loops.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "ethereum", "evm", "interpreter"]
cover = { image = "/images/covers/bc-evm-internals-rust.png", alt = "Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter", hiddenInSingle = true }
+++

The previous post, [Part one wrap-up: a small full node in Go](/posts/bc-toy-node-go/), closed part one. Part two is Ethereum, starting below Solidity: the machine that runs contracts.

In [The account model, nonces and replay protection](/posts/bc-account-model-nonce/) an {{< term "account-model" "account" >}} was a balance and a nonce. Ethereum adds a {{< term "smart-contract" "smart contract" >}}: an account that also has code and storage. A transaction to it runs the code on the {{< term "evm" "EVM" >}}.

In [Bitcoin Script: a tiny stack interpreter in Rust](/posts/bc-bitcoin-script-rust/) I wrote a stack machine without loops. This one has loops, so it needs gas.

> Rust 1.90 on macOS (arm64), no dependencies. Local example code. This is a **teaching subset, not a conformant EVM**: 19 opcodes plus `PUSH1`..`PUSH32`, simplified gas, no calls, logs or contract creation.

## The machine

According to the Ethereum docs, the EVM is a {{< term "stack" "stack" >}} machine whose words are 256 bits, with a stack depth limit of 1024. A call sees:

- **stack**: up to 1024 words, gone after the call;
- **memory**: bytes that grow in 32-byte words, paid in gas, gone after the call;
- **storage**: the contract's persistent map, 256-bit key to 256-bit value;
- **calldata**: read-only input; `RETURN` hands memory bytes back.

Code is {{< term "bytecode" "bytecode" >}}: each {{< term "opcode" "opcode" >}} is one byte. I checked every value against the opcode table in go-ethereum's source: `ADD` 0x01, `SSTORE` 0x55, `JUMPDEST` 0x5b, `PUSH1`..`PUSH32` 0x60..0x7f, `REVERT` 0xfd, and so on.

## The interpreter loop

Rust has no `u256`, so I wrote a small one: four `u64` limbs, wrapping arithmetic, tested against `u128` and the wrap cases. In real code I would use a tested crate.

Every step charges gas, then works. Binary ops take the top of the stack as the left operand:

```rust
self.charge(pc, opname, base_gas(op))?;
match op {
    0x01 | 0x02 | 0x03 | 0x10 | 0x14 => {
        let a = self.pop(pc, opname)?; // top of stack
        let b = self.pop(pc, opname)?;
        // ADD, MUL, SUB, LT, EQ on a and b, push result
    }
    0x55 => {
        let key = self.pop(pc, opname)?;
        let val = self.pop(pc, opname)?;
        self.storage.insert(key, val);
    }
    // ...
}
```

`Vm` works on a copy of storage, committed only after `STOP` or `RETURN`.

The {{< term "gas" "gas" >}} costs are **simplified, not mainnet values**: cheap ops 3, `JUMP` 8, `JUMPI` 10, memory 3 per new word, and flat `SLOAD` 100 and `SSTORE` 5000 that I picked. Real storage pricing depends on warm or cold access (EIP-2929) and on old and new values; real memory cost has a quadratic term.

## A counter

`PUSH1 1, PUSH1 0, SLOAD, ADD, PUSH1 0, SSTORE, STOP` increments slot 0. The trace shows the stack before each opcode and gas left after charging:

```
== counter, call 1 (gas limit 10000)
  pc=00 PUSH1        gas_left=9997   stack=[]
  pc=02 PUSH1        gas_left=9994   stack=[1]
  pc=04 SLOAD        gas_left=9894   stack=[1, 0]
  pc=05 ADD          gas_left=9891   stack=[1, 0]
  pc=06 PUSH1        gas_left=9888   stack=[1]
  pc=08 SSTORE       gas_left=4888   stack=[1, 0]
  pc=09 STOP         gas_left=4888   stack=[]
  success, gas used 5112
  storage after: [(0, 1)]
== counter, call 2 (gas limit 10000)
  success, gas used 5112
  storage after: [(0, 2)]
== counter, gas too low (gas limit 1000)
  halted: OutOfGas { pc: 8, op: "SSTORE" }, all gas consumed, storage changes discarded
  storage after: [(0, 2)]
```

Storage survives between calls; the stack does not. With too little gas nothing is written.

## Calldata, memory, return

`PUSH1 0, CALLDATALOAD, PUSH1 1, ADD, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN` returns input plus one; `2^256-1` silently wraps to 0. A distant `MSTORE` shows memory cost:

```
== add one, calldata 41 (gas limit 1000)
  success, gas used 27, output 42
== add one, calldata 2^256-1 (gas limit 1000)
  success, gas used 27, output 0
== mstore at offset 1000 (gas limit 1000)
  success, gas used 108
```

(`storage after: []` lines trimmed.) Writing at byte 1000 grows memory to 33 words: 99 of the 108 gas.

## Loops, and why gas exists

A countdown, `while n != 0 { n = n - 1 }`, with `JUMPI` and `JUMP`:

```
== countdown n=2 (gas limit 1000)
  pc=00 PUSH1        gas_left=997    stack=[]
  pc=02 CALLDATALOAD gas_left=994    stack=[0]
  pc=03 JUMPDEST     gas_left=993    stack=[2]
  ... (24 lines trimmed)
  pc=10 JUMPDEST     gas_left=893    stack=[0]
  pc=11 STOP         gas_left=893    stack=[0]
  success, gas used 107
== countdown n=1000000 (gas limit 1000)
  halted: OutOfGas { pc: 15, op: "JUMP" }, all gas consumed, storage changes discarded
== stack grows forever (gas limit 100000)
  halted: StackOverflow { pc: 3 }, all gas consumed, storage changes discarded
```

The EVM is {{< term "turing-complete" "Turing-complete" >}} up to gas, and by the {{< term "halting-problem" "halting problem" >}} no node can tell in advance whether arbitrary code stops. Without a meter, one `while true` would hang every node: a {{< term "denial-of-service" "denial of service" >}}. Bitcoin Script has no loops; the EVM allows them and charges every step, paid by the sender.

## Jump targets

A jump may only land on a real `JUMPDEST` instruction. Before running, the VM scans the code, skipping `PUSH` data:

```
== jumpdest map for [60, 04, 56, 60, 5b, 00]: [false, false, false, false, false, false]
== jump into push data (gas limit 1000)
  halted: InvalidJump { pc: 2, dest: 4 }, all gas consumed, storage changes discarded
```

Byte 4 is `0x5b`, but it is the argument of `PUSH1`.

## REVERT

This stores the input in slot 0, then reverts if it is below 10:

```
== guarded store x=42 (gas limit 20000)
  success, gas used 5034
  storage after: [(0, 42)]
== guarded store x=7 (gas limit 20000)
  REVERT, gas used 5041, storage changes discarded
  storage after: [(0, 42)]
```

The `SSTORE` of 7 ran, then vanished. According to the docs, real `REVERT` refunds unused gas; errors like an invalid jump consume all of it. `cargo test` passes 7 tests.

## A few things to watch

- Operand order: `SUB` computes top minus second; easy to get wrong by hand.
- Arithmetic wraps silently at 2^256; Solidity 0.8 and later adds overflow checks on top.
- Bytes after `PUSH` are data. Analyse jump targets before running.
- For real work use a conformant implementation; revm is a widely used Rust EVM (Foundry and Reth build on it); I did not run it here.

## Exercise

1. Add `POP` (0x50) and `GT` (0x11), with tests.
2. Charge the real memory formula, quadratic part included.
3. Price `SLOAD` by warm and cold slots per call.

## What's next

Next post: **A first contract with Solidity and Foundry**.
