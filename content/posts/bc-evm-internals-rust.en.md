+++
date = '2026-11-14T18:00:00+03:30'
draft = false
title = 'Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter'
seoTitle = 'Inside the EVM: a tiny Rust interpreter'
description = 'EVM internals in Rust: a tiny interpreter with 256-bit stack, memory, storage, calldata, JUMPDEST checks, REVERT and gas that stops loops.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "rust", "ethereum", "evm", "interpreter"]
cover = { image = "/images/covers/bc-evm-internals-rust.png", alt = "Inside the EVM: stack, memory, storage and gas with a tiny Rust interpreter", hiddenInSingle = true }
+++

Imagine thousands of computers around the world that do not trust each other, and that all have to run the same program and get exactly the same result. Now imagine someone sends them a program containing `while true {}`. If every computer obediently runs it, they all hang forever, and the network stops. How can you let strangers run code on your machine without handing them a way to freeze it?

This is the problem Ethereum had to solve. In part one of this series, which ended with [a small full node in Go](/posts/bc-toy-node-go/), transactions only moved coins. Ethereum lets a transaction run a program. [Bitcoin Script](/posts/bc-bitcoin-script-rust/) dodged the frozen-machine problem by simply having no loops. Ethereum chose the opposite: loops are allowed, but every single step costs something. You pay up front for a fixed amount of "fuel", every instruction burns a little of it, and when the fuel runs out the program stops, wherever it is.

The machine that runs these programs is the {{< term "evm" "EVM" >}} (Ethereum Virtual Machine), and the fuel is called {{< term "gas" "gas" >}}. Part two of the series starts here, one level below Solidity: I wrote a tiny EVM interpreter in Rust to see with my own eyes what happens to a program step by step, and where gas fits in.

> Everything below was run with Rust 1.90 on macOS (arm64), with no dependencies. The code is a local example, not a published repo. This is a **teaching subset, not a conformant EVM**: 19 opcodes plus `PUSH1`..`PUSH32`, simplified gas, and no calls between contracts, no logs and no contract creation.

## From accounts to contracts

In [the account model post](/posts/bc-account-model-nonce/) an {{< term "account-model" "account" >}} was just two numbers next to an address: a balance and a nonce. According to the Ethereum docs, Ethereum has two kinds of accounts. The first kind is the one we already know: it belongs to a person and is controlled by a private key. The second kind is a {{< term "smart-contract" "smart contract" >}}: an account that, besides a balance, also holds **code** and its own **storage**, a small permanent database. Nobody holds a key for it; it does whatever its code says.

When a transaction is sent to a contract, every node runs that contract's code on its own copy of the EVM. Because they all run the same code on the same data, they all reach the same new state. That is the whole trick: not one server that everybody trusts, but many machines that each check the result for themselves.

The contract's code is not stored as Solidity. It is stored as {{< term "bytecode" "bytecode" >}}: a sequence of bytes, where each instruction, or {{< term "opcode" "opcode" >}}, is a single byte. For example `0x01` means `ADD` and `0x55` means `SSTORE` (write to storage). A few instructions carry data right after them: `0x60` is `PUSH1`, which means "put the next byte on the stack", so the two bytes `60 05` mean "push the number 5". I checked every opcode value in this post against the opcode table in go-ethereum's source.

## Four places to keep data

Before running anything, we need to know where a program can keep data while it runs. According to the Ethereum docs, a running contract sees four areas. A simple analogy helps me keep them apart:

- **stack**: a pile of plates. You can only put a plate on top or take the top one off. Almost every instruction works here: `ADD` takes the top two numbers off and puts their sum back. The EVM is a {{< term "stack" "stack" >}} machine, and according to the docs the pile can hold at most 1024 items. It is thrown away when the call ends.
- **memory**: a whiteboard. A plain array of bytes you can read and write anywhere. It starts empty and grows in 32-byte steps, and growing it costs gas. It is also wiped when the call ends.
- **storage**: the contract's notebook. A permanent map from a 256-bit key to a 256-bit value. This is the only one of the four that survives after the call, so writing to it is by far the most expensive thing a contract does.
- **calldata**: the letter the caller sent. The input bytes of the transaction, read-only. At the end, `RETURN` can copy some bytes from memory and hand them back as the answer.

Every item on the stack, and every key and value in storage, is a **word** of 256 bits, that is 32 bytes. That is handy, because the hashes and keys we worked with in part one are exactly 32 bytes.

## The interpreter loop

With those four areas defined, the interpreter itself is a simple loop: read the byte at the current position (called `pc`, the program counter), charge its gas, do the work, move on to the next instruction.

The first small obstacle is that Rust has no 256-bit integer type. So I wrote a small one: four `u64` pieces side by side, with arithmetic that **wraps around**, meaning that if a result is bigger than 2^256 - 1 it starts again from zero, just like the EVM. It has tests that compare it with Rust's `u128` on small numbers and check the wrap cases. In real code I would use a well-tested crate instead.

Here is the heart of the loop. It charges gas first, and only then does the work:

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

Two details in this snippet matter later:

- **Operand order.** For instructions with two inputs, the number on top of the stack is the left-hand side. So if the stack holds `10` with `1` on top, `SUB` computes `1 - 10`, not `10 - 1`. This is easy to get backwards when you write bytecode by hand.
- **Storage changes are provisional.** The `Vm` works on a copy of storage. The copy replaces the real storage only if the program finishes successfully with `STOP` or `RETURN`. If it fails halfway, all of its writes are thrown away, as if it never ran.

Now the prices. My gas costs are **simplified, not the real mainnet prices**. The cheap instructions cost 3, `JUMP` 8 and `JUMPI` 10, and growing memory costs 3 per new 32-byte word; these small numbers follow the classic tiers of the real EVM. But `SLOAD` (read storage) at a flat 100 and `SSTORE` (write storage) at a flat 5000 are numbers I picked. Real storage pricing depends on whether the slot was already touched in this transaction ("warm" or "cold", EIP-2929) and on the old and new values, and real memory cost also has a part that grows with the square of the size. For this post, only one thing matters: writing to storage is far more expensive than anything else.

## First program: a counter

Time to run something. The first program is a counter that adds one to storage slot 0 every time it is called. In instructions:

```
PUSH1 1, PUSH1 0, SLOAD, ADD, PUSH1 0, SSTORE, STOP
```

In plain words: push 1; push 0 (the slot number); read slot 0; add the two; push 0 again; write the sum into slot 0; stop. As bytes that is `6001 6000 54 01 6000 55 00`.

`cargo run` calls it three times: twice with a gas limit of 10,000, and once with only 1,000. For the first call the interpreter prints a trace: one line per instruction, with the stack **before** that instruction runs, and the gas left **after** its cost was charged:

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

Let's follow the first call:

- **`pc=00` and `pc=02`:** the two `PUSH1`s, 3 gas each. Notice that `pc` jumps by 2, because each `PUSH1` is two bytes: the instruction and its number. Before `SLOAD` the stack is `[1, 0]`, with 0 on top.
- **`pc=04 SLOAD`:** costs 100. It takes the 0 off the top as the slot number, reads slot 0 (empty, so 0) and pushes that. That is why the stack before `ADD` is again `[1, 0]`, but now the 0 is the value read from storage, not the slot number.
- **`pc=05 ADD`:** 1 + 0 = 1, so the stack becomes `[1]`.
- **`pc=06` and `pc=08 SSTORE`:** push the slot number 0, then `SSTORE` takes the slot from the top and the value under it, and writes 1 into slot 0. Look at the gas: it drops from 9888 to 4888 in one step. That single write costs more than everything else combined.
- **`success, gas used 5112`:** 3 + 3 + 100 + 3 + 3 + 5000 = 5112.

The second call prints `(0, 2)`: storage remembered the 1 from the first call, and the counter went up again. The stack, on the other hand, started empty, as it does on every call. That is the difference between the notebook and the plate pile.

The third call has only 1,000 gas. The first five instructions cost 112, which leaves 888, and `SSTORE` needs 5000. So the program stops at `pc: 8` with `OutOfGas`. The last line shows the important part: storage is still `(0, 2)`. A program that runs out of gas changes nothing, and all of its gas is gone.

## Input, memory and the answer

The counter took no input and gave no answer. Real contracts do both: they read their input from calldata and send back an answer from memory. The next program returns its input plus one:

```
PUSH1 0, CALLDATALOAD, PUSH1 1, ADD, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
```

`CALLDATALOAD` reads 32 bytes of input from position 0. After adding 1, `MSTORE` writes the result into memory at position 0, and `RETURN` sends back 32 bytes starting at position 0. I ran it with 41 as input, then with the largest possible 256-bit number, 2^256 - 1. A third program stores a value far away in memory, at byte 1000, to show the price of a big whiteboard:

```
== add one, calldata 41 (gas limit 1000)
  success, gas used 27, output 42
== add one, calldata 2^256-1 (gas limit 1000)
  success, gas used 27, output 0
== mstore at offset 1000 (gas limit 1000)
  success, gas used 108
```

(I trimmed the `storage after: []` lines; none of these programs touch storage.)

- **41 gives 42.** Eight instructions at 3 gas each, plus 3 for the first memory word: 27.
- **2^256 - 1 gives 0.** No error, no warning. The number simply wrapped around to zero. The EVM itself never checks for overflow; we come back to this in the pitfalls.
- **Writing at byte 1000 costs 108.** The 32 bytes written end at byte 1032, so memory has to grow to 33 words, even though we use only one of them. 33 words at 3 gas each is 99 of the 108. Memory is not free just because it is temporary.

## Loops, and why gas exists

So far every program ran straight from top to bottom. Now for the scary part from the opening: a loop. The EVM has two jump instructions. `JUMP` moves `pc` to another position. `JUMPI` jumps only if a condition is true (not zero). And a jump may only land on a `JUMPDEST` instruction, which marks "jumping here is allowed".

This program is a countdown, `while n != 0 { n = n - 1 }`, where `n` comes from calldata. Here it is with each instruction's position, which we need to read the trace:

```
00 PUSH1 0  02 CALLDATALOAD  03 JUMPDEST  04 DUP1  05 ISZERO  06 PUSH1 0x10  08 JUMPI
09 PUSH1 1  0b SWAP1  0c SUB  0d PUSH1 3  0f JUMP  10 JUMPDEST  11 STOP
```

Position 03 is the top of the loop. `DUP1` copies `n`, `ISZERO` turns it into 1 if it is zero, and `JUMPI` jumps out to position 0x10 if so. Otherwise `PUSH1 1` and `SWAP1` (which swaps the top two items) put `n` on top of the 1, so `SUB` computes `n - 1`, and `JUMP` goes back to 03.

I ran it with `n = 2` and a trace, then with `n = 1000000`, and then a third program that pushes a number on the stack forever:

```
== countdown n=2 (gas limit 1000)
  pc=00 PUSH1        gas_left=997    stack=[]
  pc=02 CALLDATALOAD gas_left=994    stack=[0]
  pc=03 JUMPDEST     gas_left=993    stack=[2]
  pc=04 DUP1         gas_left=990    stack=[2]
  pc=05 ISZERO       gas_left=987    stack=[2, 2]
  pc=06 PUSH1        gas_left=984    stack=[2, 0]
  pc=08 JUMPI        gas_left=974    stack=[2, 0, 16]
  pc=09 PUSH1        gas_left=971    stack=[2]
  pc=0b SWAP1        gas_left=968    stack=[2, 1]
  pc=0c SUB          gas_left=965    stack=[1, 2]
  pc=0d PUSH1        gas_left=962    stack=[1]
  pc=0f JUMP         gas_left=954    stack=[1, 3]
  pc=03 JUMPDEST     gas_left=953    stack=[1]
  ... (9 lines trimmed)
  pc=03 JUMPDEST     gas_left=913    stack=[0]
  pc=04 DUP1         gas_left=910    stack=[0]
  pc=05 ISZERO       gas_left=907    stack=[0, 0]
  pc=06 PUSH1        gas_left=904    stack=[0, 1]
  pc=08 JUMPI        gas_left=894    stack=[0, 1, 16]
  pc=10 JUMPDEST     gas_left=893    stack=[0]
  pc=11 STOP         gas_left=893    stack=[0]
  success, gas used 107
== countdown n=1000000 (gas limit 1000)
  halted: OutOfGas { pc: 15, op: "JUMP" }, all gas consumed, storage changes discarded
== stack grows forever (gas limit 100000)
  halted: StackOverflow { pc: 3 }, all gas consumed, storage changes discarded
```

Reading the trace:

- **The first pass, `pc=03` to `pc=0f`:** `n` is 2. Before `JUMPI` the stack is `[2, 0, 16]`: the jump target 16 (that is 0x10) on top, then the condition 0 (because 2 is not zero), then `n`. The condition is false, so there is no jump. Before `SUB` the stack is `[1, 2]`, with 2 on top, so `SUB` computes 2 - 1. Before `JUMP` the stack is `[1, 3]`: the new `n` and the target 3.
- **Back at `pc=03` with `n = 1`.** One pass of the loop cost 40 gas (993 down to 953). I trimmed the second pass, which looks the same.
- **The last lines:** `n` is now 0, `ISZERO` gives 1, the stack before `JUMPI` is `[0, 1, 16]`, and this time it jumps to 0x10 and stops. Total: 107 gas.

The next two runs are what this post is about. With `n = 1000000` the loop would need about 40 million gas. The limit is 1000, so after about 25 passes the gas runs out, at the `JUMP` at position 15 (0x0f). And the program that pushes forever is stopped by a second safety net: the stack is full at 1024 items, and the next push halts the program with `StackOverflow`.

Why not just check programs for infinite loops before running them? Because that is impossible in general. The EVM is {{< term "turing-complete" "Turing-complete" >}}, meaning it can express any computation, given enough gas. And the {{< term "halting-problem" "halting problem" >}}, a classic result in computer science, proves that no algorithm can look at an arbitrary program and always say whether it will stop. So a node cannot know in advance. Without a meter, anyone could freeze every node with one `while true`, a {{< term "denial-of-service" "denial of service" >}} against the whole network. Gas does not answer the question "will it stop?". It makes the question irrelevant: every program stops when its gas runs out, and the sender pays for every step it took.

## Jump targets have to be real

The countdown jumped to `JUMPDEST` instructions. That rule hides a subtle trap. The byte `0x5b` means `JUMPDEST`, but the same byte can also appear as plain data after a `PUSH`. In `60 5b` the `5b` is not an instruction, just the number pushed by `PUSH1`. If a jump could land there, an attacker could hide instructions inside data and run code that nobody reviewing the program would see.

So before running anything, my interpreter scans the code once from the start and marks which positions are real `JUMPDEST`s, skipping over the data bytes of every `PUSH`. The test program is `PUSH1 4, JUMP, PUSH1 0x5b, STOP`: it tries to jump to byte 4, which is `0x5b`:

```
== jumpdest map for [60, 04, 56, 60, 5b, 00]: [false, false, false, false, false, false]
== jump into push data (gas limit 1000)
  halted: InvalidJump { pc: 2, dest: 4 }, all gas consumed, storage changes discarded
```

The first line is the map: six bytes, and not one valid jump target. Byte 4 is `0x5b`, but the scan knows it is the argument of the `PUSH1` at byte 3. So the `JUMP` at position 2 is rejected with `InvalidJump`, and like any other error, it costs all the gas.

## REVERT: saying no on purpose

Running out of gas and invalid jumps are accidents. But sometimes a contract wants to refuse on purpose: "this amount is too small", "you are not the owner". That is what `REVERT` is for. It stops the program, throws away all of its changes, and, unlike the errors above, does not burn the remaining gas.

This program first stores the input in slot 0, and only then checks it: if it is below 10, it reverts. I ran it with 42 and then with 7:

```
== guarded store x=42 (gas limit 20000)
  success, gas used 5034
  storage after: [(0, 42)]
== guarded store x=7 (gas limit 20000)
  REVERT, gas used 5041, storage changes discarded
  storage after: [(0, 42)]
```

- **42 passes.** It is written and stays in storage.
- **7 does not.** Look at the gas: 5041, which includes the 5000 of `SSTORE`. So the write of 7 really did happen. But then `REVERT` ran, and storage still says 42. The write vanished with the working copy.

In my interpreter a revert keeps the gas already spent (5041) and nothing more is taken. According to the docs, the real EVM also gives the unused gas back on `REVERT`, while errors like an invalid jump consume all of it. `cargo test` passes all 7 tests, which check things like operand order and the jump map.

## Where an interpreter goes wrong

- **Operand order.** `SUB` is top minus the one under it, and `LT` asks whether the top is less than the one under it. If you write bytecode by hand, or write an interpreter, this is the easiest mistake to make and the hardest to see.
- **Arithmetic wraps silently.** As the "add one" demo showed, 2^256 - 1 plus one is 0, with no error. According to the Solidity docs, Solidity 0.8 and later adds its own overflow checks on top, and reverts instead.
- **The bytes after a `PUSH` are data.** Find the valid jump targets before running, skipping `PUSH` data, or you let hidden code run.
- **Do not use a toy for real work.** For anything real, use a conformant implementation. revm is a widely used EVM written in Rust (Foundry and Reth build on it); I did not run it for this post.

## Exercise

1. Add `POP` (0x50) and `GT` (0x11), with tests.
2. Charge the real memory formula, including the part that grows with the square of the size.
3. Price `SLOAD` by whether the slot is warm or cold, per call.

## What's next

The next post is "A first contract with Solidity and Foundry". Nobody writes bytecode by hand like we did here; there a compiler writes it for us, and we see the same stack, storage and gas from the comfortable side.
