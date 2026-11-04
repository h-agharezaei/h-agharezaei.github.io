+++
date = '2026-11-26T18:00:00+03:30'
draft = false
title = 'Gas optimization and upgradeable proxies'
description = 'Gas optimization and upgradeable proxies in Solidity: measured savings from storage packing and calldata, then an EIP-1967 proxy and a storage collision.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "gas", "proxy", "foundry", "evm"]
cover = { image = "/images/covers/bc-gas-optimization-proxies.png", alt = "Gas optimization and upgradeable proxies", hiddenInSingle = true }
+++

Every operation on a smart contract costs something, and the name of that cost is {{< term "gas" "gas" >}}. The most expensive part is writing to storage ([Inside the EVM](/posts/bc-evm-internals-rust/)). My AMM pool used seven storage slots where five would do. The second problem is worse: code that has been deployed on-chain does not change any more. If a bug turns up, you cannot patch it.

[Contract security: reentrancy, access control and real incidents](/posts/bc-contract-security/) made my contracts safer. This post does two more things: it makes them cheaper, and it builds a way to upgrade them.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64), on a copy of the previous post's project. Gas is deterministic for the same code and compiler settings. Teaching code, not audited.

## Measure first

Optimizing without measuring is guessing. `forge snapshot` saves the gas of every test, and `--diff` compares the new state with it. I snapshotted tests for one swap and one liquidity deposit on `SimplePool`, then changed the pool.

First, a word about storage. Each state variable lives in a 32-byte "slot", and every slot written costs a lot. When variables are small, several can share one slot. My pool used one slot per value, even for the timestamp, which is only a few bytes. Like Uniswap v2, I put the reserves and the timestamp into one slot. This is called {{< term "storage-packing" "storage packing" >}}:

```solidity
uint112 private _reserve0; // 112 + 112 + 32 bits = one slot
uint112 private _reserve1;
uint32 public lastUpdate;
```

112 + 112 + 32 bits is 256 bits, exactly one slot. The trimmed output of `forge inspect SimplePool storageLayout` shows how they fit:

```
 Name               Type        Slot   Offset   Bytes
 _locked            uint256     0      0        32
 _reserve0          uint112     1      0        14
 _reserve1          uint112     1      14       14
 lastUpdate         uint32      1      28       4
 price0Cumulative   uint256     2      0        32
```

All three variables are in slot 1. The `Offset` column says at which byte of the slot each one starts, and `Bytes` is its size. Seven slots became five.

I made two other changes. `swap` and the liquidity functions now read both reserves once into locals and write them back with a single `_update`. And since a cast to a smaller type silently cuts the number (the previous post showed it), `_update` reverts above `type(uint112).max`. `forge lint` also flagged every cast, until I documented why each one is safe.

The result:

```
$ forge snapshot --mt test_gas_ --diff
↓ GasTest::test_gas_swap() (gas: 138482 → 129251 | -9231 -6.666%)
↓ GasTest::test_gas_addLiquidity() (gas: 130272 → 120741 | -9531 -7.316%)
(trimmed)
```

Each line shows the gas before and after the change. `swap` got about 9,200 gas (6.7%) cheaper, and the liquidity deposit about 9,500 (7.3%). These numbers are with the optimizer off, which is Foundry's default. With `FOUNDRY_OPTIMIZER=true` the swap went from 131,605 to 121,557.

## Smaller patterns, measured

There is a list of well-known tips for saving gas. Instead of believing them, I measured each one. For each I wrote two tiny contracts that differ in one thing only (`test/gas/Micro.sol`) and read the gas of one call from `forge test --gas-report`:

| Change | optimizer off | optimizer on |
|---|---|---|
| `require` string → custom error (revert) | 701 → 434 | 338 → 260 |
| storage variable → `immutable` / `constant` | 3,118 → 1,019 / 1,019 | 2,522 → 417 / 417 |
| three storage reads → cache | 4,875 → 4,689 | 3,236 → 3,026 |
| `uint256[] memory` → `calldata` (100 items) | 53,784 → 31,176 | 26,806 → 18,153 |
| `i++` → `unchecked { ++i; }` (100 items) | 31,176 → 30,676 | 18,153 → 18,153 |

What each row means:

- **Custom error:** instead of a long string in the revert, define a named error. The revert data is only a four-byte identifier.
- **`immutable` and `constant`:** do not keep a fixed value like a fee in storage. An `immutable` is placed into the contract's code at deploy time, a `constant` at compile time. Reading them is no longer a storage read.
- **Cache:** if you read a storage variable three times, read it once into a local variable.
- **`calldata`:** for an array parameter of an external function, use `calldata` instead of `memory` so it is not copied.
- **`unchecked`:** increment the loop counter without the overflow check.

The famous `unchecked` trick gained nothing with the optimizer on. As I understand the 0.8.22 release notes, the compiler already drops that check for a simple loop counter. So the lesson of this table: most gas is spent on storage and copying; the rest is small and not worth the risk of a bug. Readability and safety come first.

## Why a proxy

Now to the second problem. The code at an address cannot be edited. If a bug turns up, the new contract gets a new address, but the users and their balances are at the old one.

The fix works like a fixed phone number for a shop. Customers always call the same number, but the person answering can be replaced. The ledger of accounts always stays in the shop. In contracts this pattern is called a {{< term "proxy-pattern" "proxy" >}}. The user talks to a small contract that holds the state (and the ETH) and forwards every call to another contract, the implementation. Change the implementation's address and the logic changes, while the data stays where it was.

The forwarding is done with {{< term "delegatecall" "delegatecall" >}}. An ordinary call runs contract B's code on B's own storage. `delegatecall` runs B's code on contract A's storage, and `msg.sender` and `msg.value` stay those of the original call. It is as if A borrowed B's code.

```solidity
fallback() external payable {
    bytes32 slot = IMPLEMENTATION_SLOT;
    assembly {
        let impl := sload(slot)
        calldatacopy(0, 0, calldatasize())
        let ok := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
        returndatacopy(0, 0, returndatasize())
        switch ok
        case 0 { revert(0, returndatasize()) }
        default { return(0, returndatasize()) }
    }
}
```

`fallback` is the function that runs when no other function matches the call, which here means practically every call. This code reads the implementation's address from storage, copies the call's input, does the `delegatecall`, and hands the result or the error back to the caller unchanged.

The experiment: Alice and Bob deposit 8 ETH in total through the proxy, and then we look at this:

```
$ forge test --mt test_DelegatecallContext -vv
  msg.sender seen by V1 code is alice: true
  address(this) is the proxy:          true
  proxy totalDeposits: 8000000000000000000
  impl  totalDeposits: 0
  ETH held by proxy:   8000000000000000000
```

- **`msg.sender seen by V1 code is alice`:** the implementation's code sees Alice as the sender, not the proxy.
- **`address(this) is the proxy`:** but "myself", for that code, is the proxy.
- **`proxy totalDeposits` and `impl totalDeposits`:** the data was written in the proxy (8 ETH) and the implementation stayed untouched (zero).
- **`ETH held by proxy`:** the ETH is in the proxy too.

One detail: the proxy itself must also keep the implementation's address in some slot. If that slot is the same one Solidity assigns to an ordinary variable, that variable would corrupt the address. So {{< term "eip-1967" "EIP-1967" >}} fixes an out-of-the-way slot: the hash of a string, minus one.

```
$ cast keccak "eip1967.proxy.implementation"
0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbd
```

Minus one gives `...382bbc`, the constant in my proxy (also checked in a test with `vm.load`).

## Upgrades and storage collision

An upgrade is `upgradeTo` changing the implementation's address. Version 2 inherits from version 1 and only appends the variable `withdrawCount`. Alice withdraws 1 ETH and we see everything is intact:

```
$ forge test --mt test_UpgradeKeepsState -vv
  version       v2
  owner is admin true
  alice         4000000000000000000
  bob           3000000000000000000
  total         7000000000000000000
  withdrawCount 1
```

The version is v2, the owner is unchanged, the balances survived (5 minus 1 for Alice, 3 for Bob), and `withdrawCount` is one.

Where is the danger? A contract does not work with variable names; it works with slot numbers. Version 1 says `owner` is in slot 0, `balanceOf` in slot 1 and `totalDeposits` in slot 2. If a new version declares the same variables in a different, "tidier" order, the old data stays where it was but each name now reads a different slot. `VaultV2Reordered` does exactly that. The problem is called {{< term "storage-collision" "storage collision" >}}:

```
$ forge test --mt test_ReorderedUpgradeCorruptsState -vv
  version       v2-reordered
  owner         0x0000000000000000000000000000000000000000
  totalDeposits 970899903996907561841885952119535521295492554447
  alice         0
  admin as uint 970899903996907561841885952119535521295492554447
  after fix, alice 5000000000000000000
```

- **`owner`:** zero, because it now reads a slot that used to belong to the mapping.
- **`totalDeposits`:** a strange number, and the `admin as uint` line shows it is the admin address read as a number. `totalDeposits` is now in slot 0, which used to hold `owner`.
- **`alice`:** her balance reads as zero.
- **`after fix`:** this version only reads and writes nothing, so going back to the right layout brought Alice's 5 ETH back. If a single write had happened, the data would have been corrupted for good.

The rule: between versions, never move, delete or change the type of a state variable; only append to the end. And before every upgrade, put the `forge inspect ... storageLayout` output of the two versions side by side.

## Initializer

One more point: the proxy never runs the implementation's constructor, because a constructor runs only once, when the implementation itself is deployed, and writes to its own storage. So the proxy's initial state has to be filled by a function called `initialize()`. The `InitFeed` bug in the previous post showed what happens if anyone can call it again. My proxy calls `initialize` in the deploy transaction, which closes that gap.

The implementation is also an ordinary contract that can be called directly. So the constructor in `VaultV1` locks it, and `impl.initialize(mallory)` reverts. Without the lock, Mallory would become the implementation's owner. As far as I can tell that is harmless here, since that contract's state belongs to nobody, but it would matter if the upgrade logic lived there.

There are two common proxy styles, transparent and UUPS. As I understand the OpenZeppelin docs, the difference is where the upgrade logic lives. In transparent, the upgrade logic stays in the proxy and the admin's calls are not forwarded to the implementation, to avoid clashes; my proxy's `upgradeTo` also shadows any implementation function with the same {{< term "function-selector" "selector" >}}. UUPS puts the upgrade logic in the implementation: the proxy gets cheaper, but a version without it means the end of upgrades.

## Traps in optimization and upgrades

- **Measure with `forge snapshot --diff`, not folklore.** Some well-known tricks, such as `unchecked`, gained nothing.
- **Pack only the hot variables, and check every narrowing cast.** Careless packing brings back the silent truncation bug.
- **Between versions, never move, delete or retype a state variable.** Only append to the end.
- **Initialize in the deploy transaction and lock the implementation.**

## Exercise

1. Pack `borrowIndex` and `lastAccrual` in `LendingMarket` and measure `borrow`.
2. In a copy of `VaultV1`, put a variable before `owner` and upgrade to it. What breaks?

## What's next

**MEV and transaction ordering**: from the cost of a transaction to when it runs.
