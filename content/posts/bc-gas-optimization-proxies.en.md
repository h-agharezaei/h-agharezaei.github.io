+++
date = '2026-11-26T18:00:00+03:30'
draft = false
title = 'Gas optimization and upgradeable proxies'
description = 'Gas optimization and upgradeable proxies in Solidity: measured savings from storage packing and calldata, then an EIP-1967 proxy and a storage collision.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "gas", "proxy", "foundry", "evm"]
cover = { image = "/images/covers/bc-gas-optimization-proxies.png", alt = "Gas optimization and upgradeable proxies", hiddenInSingle = true }
+++

[Contract security: reentrancy, access control and real incidents](/posts/bc-contract-security/) made my contracts safer. This post makes them cheaper, then deals with the fact that deployed code cannot change. Both rest on [Inside the EVM](/posts/bc-evm-internals-rust/): storage is the expensive part of {{< term "gas" "gas" >}}.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64), on a copy of the previous post's project. Gas is deterministic for the same code and compiler settings. Teaching code, not audited.

## Measure first

`forge snapshot` saves the gas of every test; `--diff` compares against it. I snapshotted tests for one swap and one deposit on `SimplePool`, then changed the pool.

The pool used one 32-byte slot per value. Like Uniswap v2, I packed the reserves and the timestamp into one slot, which is {{< term "storage-packing" "storage packing" >}}:

```solidity
uint112 private _reserve0; // 112 + 112 + 32 bits = one slot
uint112 private _reserve1;
uint32 public lastUpdate;
```

`forge inspect SimplePool storageLayout`, trimmed:

```
 Name               Type        Slot   Offset   Bytes
 _locked            uint256     0      0        32
 _reserve0          uint112     1      0        14
 _reserve1          uint112     1      14       14
 lastUpdate         uint32      1      28       4
 price0Cumulative   uint256     2      0        32
```

Seven slots became five. Also, `swap` and the liquidity functions now read both reserves once into locals and write them back in one `_update`. Narrowing casts truncate silently, as the previous post showed, so `_update` reverts above `type(uint112).max`, and `forge lint` flagged each cast until I documented why it is safe.

```
$ forge snapshot --mt test_gas_ --diff
↓ GasTest::test_gas_swap() (gas: 138482 → 129251 | -9231 -6.666%)
↓ GasTest::test_gas_addLiquidity() (gas: 130272 → 120741 | -9531 -7.316%)
(trimmed)
```

That is Foundry's default, optimizer off. With `FOUNDRY_OPTIMIZER=true` the swap went from 131,605 to 121,557.

## Smaller patterns, measured

Pairs that differ in one thing (`test/gas/Micro.sol`), gas per call from `forge test --gas-report`:

| Change | Optimizer off | Optimizer on |
|---|---|---|
| `require` string → custom error (failing call) | 701 → 434 | 338 → 260 |
| storage variable → `immutable` / `constant` | 3,118 → 1,019 / 1,019 | 2,522 → 417 / 417 |
| read a storage variable 3× → cache once | 4,875 → 4,689 | 3,236 → 3,026 |
| `uint256[] memory` → `calldata` (100 items) | 53,784 → 31,176 | 26,806 → 18,153 |
| `i++` → `unchecked { ++i; }` (100 items) | 31,176 → 30,676 | 18,153 → 18,153 |

The famous unchecked-loop trick saved nothing with the optimizer on; as I understand the 0.8.22 release notes, the compiler can drop that check for simple loop counters itself. Storage and copies are where gas goes; the rest is small, and none of it is worth a bug. Readability and safety come first.

## Why proxies exist

Code at an address cannot be edited; a fix means a new address, while users and balances stay at the old one. With a {{< term "proxy-pattern" "proxy" >}}, users talk to a small contract that keeps the state and forwards every call to a swappable implementation.

The forwarding uses {{< term "delegatecall" "delegatecall" >}}: run the code of B against the storage of A, keeping `msg.sender` and `msg.value`.

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

Alice and Bob deposit 8 ETH through the proxy:

```
$ forge test --mt test_DelegatecallContext -vv
  msg.sender seen by V1 code is alice: true
  address(this) is the proxy:          true
  proxy totalDeposits: 8000000000000000000
  impl  totalDeposits: 0
  ETH held by proxy:   8000000000000000000
```

The implementation address needs a slot no normal variable will use. {{< term "eip-1967" "EIP-1967" >}} picks a hash minus one:

```
$ cast keccak "eip1967.proxy.implementation"
0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbd
```

Minus one gives `...382bbc`, the constant in my proxy; `test_SlotsMatchEip1967` also checks it with `vm.load`.

## Upgrades and a storage collision

`VaultV2` inherits `VaultV1` and only appends a `withdrawCount`. After `upgradeTo`, everything survives:

```
$ forge test --mt test_UpgradeKeepsState -vv
  version       v2
  owner is admin true
  alice         4000000000000000000
  bob           3000000000000000000
  total         7000000000000000000
  withdrawCount 1
```

`VaultV2Reordered` declares the same variables in a "tidier" order. The slots did not move, so each name reads the wrong data, a {{< term "storage-collision" "storage collision" >}}:

```
$ forge test --mt test_ReorderedUpgradeCorruptsState -vv
  version       v2-reordered
  owner         0x0000000000000000000000000000000000000000
  totalDeposits 970899903996907561841885952119535521295492554447
  alice         0
  admin as uint 970899903996907561841885952119535521295492554447
  after fix, alice 5000000000000000000
```

`totalDeposits` is the admin's address read as a number, and Alice owns nothing. This version only read, so moving back recovered her 5 ETH; one write would have corrupted it for good. Compare `forge inspect ... storageLayout` of both versions before every upgrade.

## Initializers

A proxy never runs the implementation's constructor, so state is set by `initialize()`. My proxy calls it in the deploy transaction, closing the gap from the previous post. The implementation is a contract too: `VaultV1`'s constructor marks it initialized, so `impl.initialize(mallory)` reverts. Without that lock, Mallory can own the implementation: harmless here as far as I can tell, but it could matter if it held upgrade logic.

Where upgrade logic lives is the UUPS versus transparent split, as I understand OpenZeppelin's docs. A transparent proxy keeps it in the proxy and never forwards the admin's calls, avoiding clashes; my `upgradeTo` shadows any implementation function with the same {{< term "function-selector" "selector" >}}. UUPS puts it in the implementation: a cheaper proxy, but a version without it ends all upgrades.

## A few things to watch

- Measure with `forge snapshot --diff`, not folklore.
- Pack only hot variables, and check every narrowing cast.
- Never reorder, remove or retype state variables between versions; only append.
- Initialize in the deploy transaction and lock the implementation.

## Exercise

1. Pack `borrowIndex` and `lastAccrual` in `LendingMarket` and measure `borrow`.
2. Add a variable before `owner` in a copy of `VaultV1` and upgrade to it. What breaks?

## What's next

Next post: **MEV and transaction ordering**.
