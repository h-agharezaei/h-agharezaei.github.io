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

A failed transaction still lands in a block and its sender still pays; seeing that needs a real contract, not the hand-written bytecode of [the previous post](/posts/bc-evm-internals-rust/). This post writes a {{< term "smart-contract" "smart contract" >}} in {{< term "solidity" "Solidity" >}}, compiles it, inspects the compiler output and runs it on a local chain.

The tool is {{< term "foundry" "Foundry" >}}: `forge` builds and tests, `anvil` is a local Ethereum node, `cast` talks to it from the shell. Its tests are written in Solidity too, which matters for the next post. If you read [the account model post](/posts/bc-account-model-nonce/), a contract is one more kind of account: one with code and its own storage.

> Foundry 1.8.7 on macOS (arm64); `forge` picked and downloaded solc 0.8.38 for `pragma ^0.8.24`. Local example code, anvil on `127.0.0.1` only. Addresses below are anvil's public test accounts, known to everyone and never funded on a real network.

## The project

```
$ forge init --no-git --shallow bc-solidity-foundry
$ rm src/Counter.sol test/Counter.t.sol script/Counter.s.sol
```

`forge init` creates `src/`, `test/`, `script/`, `foundry.toml` and puts `forge-std` (1.3 MB here) under `lib/`. I replaced the template counter with a vault: people deposit ETH, move balances to each other inside the vault, and withdraw.

## The contract

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

The constructor runs once, at deploy. `msg.sender` is whoever called this function, `msg.value` the wei sent with it, and only `payable` functions accept wei. `public` state variables get free getters. Custom errors like `InsufficientBalance` cost less than revert strings, as I understand it, and carry typed data. Withdrawals are never paused: users can always leave. And `withdraw` updates storage before sending ETH; the reason gets its own post on contract security.

## What the compiler produced

```
$ forge build --sizes
| Contract | Runtime Size (B) | Initcode Size (B) | Runtime Margin (B) | Initcode Margin (B) |
| Vault    | 2,931            | 3,022             | 21,645             | 46,130              |
```

The first bytes of the runtime code are the dispatcher, made of the opcodes from the previous post:

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

It loads the first 32 bytes of calldata, shifts right by 224 bits to keep 4 bytes, and compares them with each {{< term "function-selector" "function selector" >}}. `0x7d882097` is `totalDeposits()`:

```
$ forge inspect Vault methodIdentifiers
| balanceOf(address)    | 70a08231   |
| deposit()             | d0e30db0   |
| move(address,uint256) | 987ff31c   |
| totalDeposits()       | 7d882097   |
| withdraw(uint256)     | 2e1a7d4d   |
(trimmed)
```

And the {{< term "storage-layout" "storage layout" >}}, which decides what each `SLOAD`/`SSTORE` touches:

```
$ forge inspect Vault storageLayout
| Name          | Type                        | Slot | Offset | Bytes |
| owner         | address                     | 0    | 0      | 20    |
| paused        | bool                        | 0    | 20     | 1     |
| balanceOf     | mapping(address => uint256) | 1    | 0      | 32    |
| totalDeposits | uint256                     | 2    | 0      | 32    |
(Contract column trimmed)
```

`owner` and `paused` share slot 0. The mapping itself stores nothing in slot 1; according to the Solidity docs, the entry for key `k` lives at `keccak256(k . 1)`.

## Deploy to anvil and talk to it

`anvil --host 127.0.0.1 --port 8545` in another terminal. Its accounts are unlocked, so `--unlocked --from` needs no key:

```
$ export ETH_RPC_URL=http://127.0.0.1:8545
$ A0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266   # anvil test account 0
$ A1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8   # anvil test account 1
$ forge create src/Vault.sol:Vault --unlocked --from $A0 --broadcast
Deployer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
(transaction hash trimmed)

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

`cast send` makes a transaction; `cast call` runs a read locally and costs nothing. The `logs` field of the deposit receipt held one {{< term "event-log" "log" >}} whose first topic is `keccak256("Deposited(address,uint256)")`.

Now read storage directly. `cast index` computes the mapping slot:

```
$ cast storage $V 2
0x0000000000000000000000000000000000000000000000000de0b6b3a7640000
$ cast storage $V $(cast index address $A1 1)
0x00000000000000000000000000000000000000000000000003782dace9d90000
```

`0xde0b6b3a7640000` is 1e18 wei and `0x3782dace9d90000` is 0.25e18: exactly the 32-byte words an `SLOAD` on those slots returns.

## A revert and its gas

Account 1 has 0.25 ETH in the vault and asks for 5:

```
$ cast send $V "withdraw(uint256)" 5ether --unlocked --from $A1
Error: Failed to estimate gas: ... execution reverted: custom error 0xcf479181: ...
InsufficientBalance(250000000000000000 [2.5e17], 5000000000000000000 [5e18])
(trimmed)
```

The {{< term "revert" "revert" >}} happened during gas estimation, so nothing was sent. With a fixed gas limit it is mined anyway:

```
$ cast send $V "withdraw(uint256)" 5ether --gas-limit 100000 --unlocked --from $A1
gasUsed              24220
status               0 (failed)
```

A failed transaction is still in a block, the sender still paid for 24,220 {{< term "gas" "gas" >}}, and no storage changed. A successful 0.1 ETH withdraw used 41,006. Deposit cost more than move because the first deposit turns zero slots into non-zero ones, which the docs price highest.

Pausing changes only the byte at offset 20 of slot 0:

```
$ cast send $V "setPaused(bool)" true --unlocked --from $A0
$ cast storage $V 0
0x000000000000000000000001f39fd6e51aad88f6f4ce6ab8827279cfffb92266
```

## First-contract traps

- Storage layout is the contract's on-disk format. Reordering state variables changes which slot is which; it matters once proxies enter the picture.
- A view call through `cast call` can succeed where a transaction would fail; the receipt `status` is the truth.
- Estimation hides reverts before sending. Good for users, but the revert you want to study needs a fixed gas limit.
- This vault is a teaching contract, not audited. For production, the usual route is an audited library such as OpenZeppelin.

## Exercise

1. Add `uint64 public lastDeposit` after `paused`, rebuild, and check `storageLayout`: does it share slot 0?
2. Give `withdraw` a `whenNotPaused` modifier and think about who that hurts.
3. Compute the slot for `$A0` with `cast keccak` and `cast abi-encode` instead of `cast index`.

## What's next

Next post: **Testing, fuzzing and invariants with Foundry**.
