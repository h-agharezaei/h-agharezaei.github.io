+++
date = '2026-11-15T18:00:00+03:30'
draft = false
title = 'A first contract with Solidity and Foundry'
description = 'A first Solidity contract with Foundry: a small ETH vault, its storage layout, a deploy to a local anvil chain, cast calls, a revert and the gas used.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "ethereum", "solidity", "foundry", "evm"]
cover = { image = "/images/covers/bc-solidity-first-contract.png", alt = "A first contract with Solidity and Foundry", hiddenInSingle = true }
+++

Here is something that surprised me about Ethereum: a transaction that fails still lands in a block, and its sender still pays for it. To see that with your own eyes you need a real contract, not the hand-assembled bytecode of [the previous post](/posts/bc-evm-internals-rust/), where we ran tiny programs on a toy interpreter.

Nobody writes bytecode by hand. People write in a programming language, and a compiler turns it into bytecode. The main language for Ethereum is {{< term "solidity" "Solidity" >}}. In this post I write a small {{< term "smart-contract" "smart contract" >}} in Solidity (a vault that holds people's ETH), compile it, look at what the compiler produced, deploy it to a chain running on my own laptop, and talk to it.

The tool for all of that is {{< term "foundry" "Foundry" >}}, which is really three programs:

- `forge` builds and tests contracts.
- `anvil` is a local Ethereum node: a private test chain with a few pre-funded accounts, running on your machine.
- `cast` is a command-line client that talks to a node: send a transaction, read a value, decode a result.

Foundry's tests are written in Solidity too, which matters for the next post. If you read [the account model post](/posts/bc-account-model-nonce/), a contract is simply one more kind of account: one that has code and its own storage.

> Everything below was run with Foundry 1.8.7 on macOS (arm64). For `pragma ^0.8.24` (explained below) `forge` chose and downloaded solc 0.8.38. The code is a local example, and anvil listens on `127.0.0.1` only. The addresses below are anvil's public test accounts: everybody knows their keys, so they hold no real money on any real network.

## The project

```
$ forge init --no-git --shallow bc-solidity-foundry
$ rm src/Counter.sol test/Counter.t.sol script/Counter.s.sol
```

`forge init` creates a project: `src/` for contracts, `test/` for tests, `script/` for deploy scripts, a `foundry.toml` config file, and a copy of the helper library `forge-std` under `lib/`. It also adds a sample counter contract, which I removed and replaced with a vault: people deposit ETH, move balances to each other inside the vault, and withdraw.

## The contract

Before the code, two words. ETH is Ethereum's coin. Its smallest unit is the {{< term "wei" "wei" >}}: one ETH is 10^18 wei, so contracts always count in wei, as plain integers. And the whole contract is one long list of rules that nobody can bend, because every node runs the same code.

```solidity
contract Vault {
    address public owner;   // slot 0 (20 bytes)
    bool public paused;     // slot 0 too (1 byte, packed after owner)
    mapping(address => uint256) public balanceOf; // slot 1
    uint256 public totalDeposits;                 // slot 2

    error ZeroAmount();
    error NotOwner();
    error IsPaused();
    error InsufficientBalance(uint256 available, uint256 requested);
    error TransferFailed();

    event Deposited(address indexed account, uint256 amount);
    event Withdrawn(address indexed account, uint256 amount);
    event Moved(address indexed from, address indexed to, uint256 amount);
    event PausedSet(bool paused);

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert IsPaused();
        _;
    }

    function deposit() external payable whenNotPaused {
        if (msg.value == 0) revert ZeroAmount();
        balanceOf[msg.sender] += msg.value;
        totalDeposits += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external {
        uint256 bal = balanceOf[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (amount > bal) revert InsufficientBalance(bal, amount);
        // effects before the external call
        balanceOf[msg.sender] = bal - amount;
        totalDeposits -= amount;
        emit Withdrawn(msg.sender, amount);
        (bool ok, ) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function move(address to, uint256 amount) external whenNotPaused {
        uint256 bal = balanceOf[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (amount > bal) revert InsufficientBalance(bal, amount);
        balanceOf[msg.sender] = bal - amount;
        balanceOf[to] += amount;
        emit Moved(msg.sender, to, amount);
    }

    function setPaused(bool p) external onlyOwner {
        paused = p;
        emit PausedSet(p);
    }
}
```

(The file also starts with a license comment and `pragma solidity ^0.8.24;`, which tells the compiler to accept any 0.8.x version from 0.8.24 on. I left them out above.)

If you know Go or Rust, most of this reads naturally. These are the parts that are new:

- **State variables** at the top (`owner`, `paused`, `balanceOf`, `totalDeposits`) live in the contract's storage, the permanent notebook from the previous post. A `mapping` is Solidity's key-value map. `public` makes the compiler generate a free read function for that variable, so `balanceOf(address)` exists without us writing it.
- **The constructor** runs exactly once, when the contract is deployed. Here it records who deployed it as the `owner`.
- **`msg.sender`** is the account that called this function, and **`msg.value`** is the amount of wei sent along with the call. Only functions marked `payable` accept wei; a call that carries money to a non-payable function fails.
- **`external`** means "callable from outside the contract".
- **A `modifier`** is a reusable check that wraps a function. In `onlyOwner` the `_;` line is where the body of the wrapped function runs. So `setPaused` first checks the caller and only then does its job.
- **Custom errors** like `InsufficientBalance(available, requested)` are what `revert` throws. They carry typed data, and as I understand it they cost less gas than the older style of revert with a text message.
- **Events** (`emit Deposited(...)`) write a record into the transaction's log. Contracts cannot read their own logs; they exist so that outside programs, like a website or an indexer, can find out what happened cheaply.

Two design decisions are worth a sentence each. Withdrawals are never paused, so users can always leave. And `withdraw` updates its storage **before** sending the ETH, with the external call last. The reason is a classic attack, and it gets its own post on contract security later in the series.

## What the compiler produced

`forge build --sizes` compiles and shows how big the code is:

```
$ forge build --sizes
| Contract | Runtime Size (B) | Initcode Size (B) | Runtime Margin (B) | Initcode Margin (B) |
| Vault    | 2,931            | 3,022             | 21,645             | 46,130              |
```

"Runtime" is the code that stays on the chain and runs on every call: 2,931 bytes. "Initcode" is the code that runs once at deployment, runs the constructor and returns the runtime code to be stored. The margin columns show how much room is left below the size limits: 2,931 + 21,645 = 24,576 bytes for the runtime code, and 3,022 + 46,130 = 49,152 for the initcode.

Now the connection with the last post. The first bytes of the runtime code are a **dispatcher**: a little program that decides which of your functions was called. It is made of the same opcodes we saw there. `cast disassemble` turns bytecode back into readable opcodes (here the first bytes of the Vault's runtime code):

```
$ cast disassemble 0x60806040526004361061007a575f3560e01c80637d882097
00000000: PUSH1 0x80
00000002: PUSH1 0x40
00000004: MSTORE
00000005: PUSH1 0x04
00000007: CALLDATASIZE
00000008: LT
00000009: PUSH2 0x007a
0000000c: JUMPI
0000000d: PUSH0
0000000e: CALLDATALOAD
0000000f: PUSH1 0xe0
00000011: SHR
00000012: DUP1
00000013: PUSH4 0x7d882097
```

Reading it:

- `PUSH1 0x80, PUSH1 0x40, MSTORE` stores 0x80 at memory position 0x40, a bookkeeping value (the "free memory pointer") that every Solidity program sets up first.
- `PUSH1 0x04, CALLDATASIZE, LT, PUSH2 0x007a, JUMPI` means: if the input is shorter than 4 bytes, jump to position 0x7a, which handles calls that match no function.
- `PUSH0, CALLDATALOAD, PUSH1 0xe0, SHR` loads the first 32 bytes of the input and shifts them right by 224 bits (0xe0), which leaves only the first 4 bytes.
- Those 4 bytes are compared one by one with the {{< term "function-selector" "function selector" >}} of each function. `PUSH4 0x7d882097` is the first candidate, and it is the selector of `totalDeposits()`.

A function selector is the first 4 bytes of the {{< term "keccak-256" "Keccak-256" >}} hash of the function's signature, such as `totalDeposits()`. It is how a caller says which function it wants: the first 4 bytes of the calldata. The compiler can list them all:

```
$ forge inspect Vault methodIdentifiers
| balanceOf(address)    | 70a08231   |
| deposit()             | d0e30db0   |
| move(address,uint256) | 987ff31c   |
| totalDeposits()       | 7d882097   |
| withdraw(uint256)     | 2e1a7d4d   |
(trimmed)
```

(I trimmed `owner()`, `paused()` and `setPaused(bool)`.) The format of this calldata, the 4-byte selector followed by the arguments, is part of the contract {{< term "abi" "ABI" >}}.

The compiler also decides where each state variable lives. This is the {{< term "storage-layout" "storage layout" >}}, and it decides which slot every `SLOAD` and `SSTORE` touches:

```
$ forge inspect Vault storageLayout
| Name          | Type                        | Slot | Offset | Bytes |
| owner         | address                     | 0    | 0      | 20    |
| paused        | bool                        | 0    | 20     | 1     |
| balanceOf     | mapping(address => uint256) | 1    | 0      | 32    |
| totalDeposits | uint256                     | 2    | 0      | 32    |
(Contract column trimmed)
```

A slot is 32 bytes. `owner` takes 20 of them, so the compiler packs `paused` (1 byte) into the same slot 0, starting at byte 20. That saves a storage slot, which saves gas. The mapping is a special case: it stores nothing in slot 1 itself. According to the Solidity docs, the entry for key `k` lives at the slot `keccak256(k . 1)`, which means the key and the number 1 joined together and hashed. A mapping is a hash table spread over the whole 2^256 space of slots.

## Deploy to anvil and talk to it

In another terminal, I start the local chain with `anvil --host 127.0.0.1 --port 8545`. It prints a list of funded test accounts. Their keys are unlocked inside anvil, so I can tell the tools `--unlocked --from <address>` and not handle any private key:

```
$ export ETH_RPC_URL=http://127.0.0.1:8545
$ A0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266   # anvil test account 0
$ A1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8   # anvil test account 1
$ forge create src/Vault.sol:Vault --unlocked --from $A0 --broadcast
Deployer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
(transaction hash trimmed)
```

`ETH_RPC_URL` tells all the tools where the node is. `forge create` compiles the contract and sends the deployment transaction, and the contract now has an address. That address comes from the deployer's address and nonce, so on a fresh anvil it is always the same one. Now I use it:

```
$ V=0x5FbDB2315678afecb367f032d93F642f64180aa3
$ cast send $V "deposit()" --value 1ether --unlocked --from $A0
gasUsed              69752
status               1 (success)
(trimmed)
$ cast call $V "totalDeposits()(uint256)"
1000000000000000000 [1e18]
$ cast send $V "move(address,uint256)" $A1 0.25ether --unlocked --from $A0
gasUsed              54287
status               1 (success)
(trimmed)
```

- **`cast send ... deposit()`:** sends a real transaction that calls `deposit()` with 1 ETH attached. It is mined, and the receipt says `status 1` and shows the {{< term "gas" "gas" >}} used: 69,752. The receipt's `logs` field contains one {{< term "event-log" "log" >}}: its first topic is the Keccak-256 hash of `Deposited(address,uint256)`, which I checked with `cast keccak`.
- **`cast call ... totalDeposits()`:** this is not a transaction. It asks the node to run the function locally and return the answer; nothing is written and nothing costs gas. The answer is one ETH, in wei.
- **`cast send ... move`:** moves 0.25 ETH from account 0's balance to account 1's balance inside the vault. No ETH leaves the contract.

Now let's read the storage directly, bypassing all functions. `cast index` computes the slot of a mapping entry for us:

```
$ cast storage $V 2
0x0000000000000000000000000000000000000000000000000de0b6b3a7640000
$ cast storage $V $(cast index address $A1 1)
0x00000000000000000000000000000000000000000000000003782dace9d90000
```

Slot 2 is `totalDeposits`: `0xde0b6b3a7640000` is 10^18, one ETH in wei. The second command reads the slot of `balanceOf[A1]`, and `0x3782dace9d90000` is 0.25 * 10^18. These are exactly the 32-byte words that an `SLOAD` on those slots would return. What we saw in the Rust interpreter is what is really on the chain.

## A revert and its gas

Now the failure from the beginning of the post. Account 1 has 0.25 ETH in the vault and asks to withdraw 5:

```
$ cast send $V "withdraw(uint256)" 5ether --unlocked --from $A1
Error: Failed to estimate gas: ... execution reverted: custom error 0xcf479181: ...
InsufficientBalance(250000000000000000 [2.5e17], 5000000000000000000 [5e18])
(trimmed)
```

The error is decoded for us: the contract refused, and our custom error carries both numbers, what is available and what was asked. But look at the first words, "Failed to estimate gas". Before sending, `cast` asks the node how much gas the transaction would need, and that dry run already reverted. So the {{< term "revert" "revert" >}} happened before anything was sent. To see a failed transaction really mined, I give it a fixed gas limit so there is no estimate:

```
$ cast send $V "withdraw(uint256)" 5ether --gas-limit 100000 --unlocked --from $A1
gasUsed              24220
status               0 (failed)
```

This is the sentence I opened with. The transaction is in a block, its receipt says `status 0`, the sender paid for 24,220 gas, and no storage changed. A successful withdraw of 0.1 ETH, for comparison, used 41,006.

Why did the deposit use more gas than the move? The deposit wrote two storage slots that were empty before, the sender's balance and `totalDeposits`. According to the docs, setting a slot from zero to non-zero is the most expensive kind of write. The move wrote only one such slot (the receiver's balance), plus one that was already non-zero.

One last look at storage. Pausing changes only the byte at offset 20 of slot 0:

```
$ cast send $V "setPaused(bool)" true --unlocked --from $A0
$ cast storage $V 0
0x000000000000000000000001f39fd6e51aad88f6f4ce6ab8827279cfffb92266
```

The last 40 hex digits (20 bytes) are the owner's address, account 0. Right before them, the `01` is `paused = true`. Two variables, one slot, just like the layout table said.

## First-contract traps

- **Storage layout is the contract's on-disk format.** If you reorder state variables, a different variable lands in each slot. That is harmless in a fresh deployment and dangerous once a contract is upgraded through proxies, which come later in the series.
- **`cast call` is not proof that a transaction will work.** A read call can succeed where a real transaction would fail; the `status` in the receipt is the truth.
- **Gas estimation hides reverts.** That is friendly for users, but if you want to study a revert, or have the failed transaction in a block, you need a fixed gas limit.
- **This vault is a teaching contract, not an audited one.** For production code, the usual route is a well-audited library such as OpenZeppelin.

## Exercise

1. Add `uint64 public lastDeposit` right after `paused`, rebuild, and look at `storageLayout` again. Does it share slot 0 with the owner?
2. Add the `whenNotPaused` modifier to `withdraw` and think about who that hurts.
3. Compute the slot for `$A0` with `cast keccak` and `cast abi-encode` instead of `cast index`, and check that you get the same slot.

## What's next

The next post is "Testing, fuzzing and invariants with Foundry". We have only tried this vault by hand; next we make the machine try thousands of inputs for us.
