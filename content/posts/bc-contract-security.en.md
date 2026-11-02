+++
date = '2026-11-25T18:00:00+03:30'
draft = false
title = 'Contract security: reentrancy, access control and real incidents'
seoTitle = 'Contract security: reentrancy and access control'
description = 'Contract security in Solidity: reentrancy, token callbacks, open initializers, tx.origin and unchecked transfers, attacked in local tests and fixed.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "security", "reentrancy", "foundry", "defi"]
cover = { image = "/images/covers/bc-contract-security.png", alt = "Contract security: reentrancy, access control and real incidents", hiddenInSingle = true }
+++

[Oracles and price manipulation](/posts/bc-oracles/) broke a lending market without a bug in the code. This post is about the bugs, each attacked in a local Foundry test against my own code, then fixed. It also answers why `withdraw` in [A first contract with Solidity and Foundry](/posts/bc-solidity-first-contract/) updates storage before sending ETH. [Authorization: RBAC and IDOR](/posts/sec-authorization-rbac-idor/) is the web version of the access control part.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project. Deliberately vulnerable contracts live in `test/vulnerable/`, attackers in `test/helpers/`. Teaching code, not audited.

## Reentrancy: the vault that pays twice

```solidity
function withdraw() external {
    uint256 bal = balanceOf[msg.sender];
    (bool ok,) = msg.sender.call{value: bal}(""); // interaction first...
    if (!ok) revert TransferFailed();
    balanceOf[msg.sender] = 0; // ...effect too late
}
```

Sending ETH runs the recipient's `receive()`, which calls `withdraw()` again while the balance is not yet zero. That is {{< term "reentrancy" "reentrancy" >}}. Alice and Bob deposit 5 ETH each, the attacker 1:

```
$ forge test --mt test_VulnerableVaultIsDrained -vv
  vault before    10000000000000000000
  vault after     0
  attacker has    11000000000000000000
  extra rounds    10
```

The fix is an order called {{< term "checks-effects-interactions" "checks-effects-interactions" >}}: validate, write state, only then call out.

```solidity
function withdraw() external nonReentrant {
    uint256 bal = balanceOf[msg.sender]; // checks
    if (bal == 0) revert NothingToWithdraw();
    balanceOf[msg.sender] = 0; // effects
    (bool ok,) = msg.sender.call{value: bal}(""); // interactions
    if (!ok) revert TransferFailed();
}
```

`nonReentrant` is a small lock in `src/Security.sol`: a storage flag set on entry and cleared on exit.

## A lock is not the whole fix

`GuardedVault` keeps the bad order and locks only `withdraw`. Reentering `withdraw` fails, but during the callback the attacker calls the unlocked `move()` and shifts the not-yet-zeroed balance to an accomplice:

```
$ forge test --mt test_GuardMissesCrossFunction -vv
  deposited       1000000000000000000
  got back        2000000000000000000
  vault after     9000000000000000000
```

That is cross-function reentrancy. `SafeVault` uses the right order and locks every state-changing function; both attackers revert. In read-only reentrancy, another contract reads your `view` function mid-callback and sees half-updated state; I did not build that one.

## Callbacks inside tokens

ERC-721's `safeTransferFrom` ([Tokens: ERC-20 and ERC-721](/posts/bc-erc20-erc721/)) calls `onERC721Received` on the recipient. A "one free NFT per address" mint that marks the claim after that callback:

```
$ forge test --mt test_CallbackReentersMint -vv
  NFTs for one address: 5
```

Moving `claimed[msg.sender] = true` above the mint fixes it. As I understand it, ERC-777 tokens call hooks even on ordinary transfers.

## Access control

{{< term "access-control" "Access control" >}} bugs are often one missing line. `InitFeed`, a price feed for the lending market, sets its owner in an `initialize()` anyone can call again:

```
$ forge test --mt test_OpenInitializerDrainsMarket -vv
  feed owner is mallory: true
  USDX borrowed against 1 DEMO: 50000000000000000000000
  USDX left in market: 0
```

Mallory made herself owner, priced DEMO at a million and borrowed everything. The fix: `if (owner != address(0)) revert AlreadyInitialized();`, and initialize in the deploy transaction.

Authenticating with {{< term "tx-origin" "tx.origin" >}} is the other classic. It is the account that signed the transaction, not the caller, so a fake airdrop the owner calls can empty the wallet:

```
$ forge test --mt test_TxOriginPhished -vv
  wallet   0
  airdrop  10000000000000000000
```

## Return values and integers

`FalseToken` returns `false` instead of reverting, as some tokens do. `NaiveEscrow` ignores the result, so Mallory, holding nothing, deposits 100 and withdraws Alice's 100:

```
$ forge test --mt test_FalseTokenNaiveEscrow -vv
  mallory balance 100000000000000000000
  escrow balance  0
  alice credit    100000000000000000000
```

`SafeTransfer` makes a low-level call and reverts unless the token returns true or nothing. As far as I know, some well-known older tokens return nothing, so `require(token.transfer(...))` is not enough.

Since 0.8, arithmetic reverts on {{< term "integer-overflow" "overflow" >}}. `unchecked` blocks and narrowing casts still wrap:

```
$ forge test --mt test_IntegerEdges -vv
  uint128(2**128 + 5) = 5
  uint8(300)          = 44
  unchecked 0 - 1     = 115792089237316195423570985008687907853269984665640564039457584007913129639935
```

## What the linter said about my code

`forge lint` is {{< term "static-analysis" "static analysis" >}} built into Foundry. On the pool, market and oracles from the last three posts:

```
$ forge lint src | grep -E '^(warning|note|error)\[' | sort | uniq -c
   5 warning[block-timestamp]: usage of `block.timestamp` in a comparison may be manipulated by validators
   2 warning[divide-before-multiply]: division before multiplication may lose precision
  13 warning[erc20-unchecked-transfer]: ERC20 `transfer` or `transferFrom` call does not check the return value
   6 warning[reentrancy-events]: event emitted after an external call; reentrancy can reorder or fabricate logs ...
   3 warning[reentrancy-no-eth]: external call can be reentered before `reserve0` is updated
   1 warning[uninitialized-local]: local variable is read before being initialized
(one line trimmed)
```

`DemoToken` has no callbacks, so as far as I can tell none was exploitable yet. I moved state updates and events before transfers, used `SafeTransfer`, added `nonReentrant`, fixed the precision loss in the cumulative price and suppressed the reviewed timestamp uses with a reason. Now `forge lint src` prints nothing and all 33 tests pass.

Copied into `src/`, the vulnerable contracts were flagged too (`reentrancy-eth`, `tx-origin`...), except the open initializer. My fixed `SafeVault` was also flagged, because the lock is written after the call: a false positive.

## Real incidents, in classes

- **Reentrancy**: The DAO (2016), whose drain led to the hard fork that split off Ethereum Classic.
- **Oracle manipulation**: the previous post's attack, seen in public post-mortems of lending protocols.
- **Key compromise**: as I understand them, several large bridge losses came from stolen validator keys, not contract bugs; see also [the Binance hack](/posts/binance-hack-hot-wallet-2026/).

## A few things to watch

My checklist before a deploy:

- Checks, effects, interactions in every function, then a lock.
- Any external call, including a token transfer, can call you back.
- A test that a stranger cannot call each privileged function or initializer.
- Token calls through a checked helper; every `unchecked` and narrowing cast reviewed; no `tx.origin`.
- Lint clean or explained, invariant tests as in [Testing, fuzzing and invariants with Foundry](/posts/bc-foundry-testing-fuzzing/), an outside review for real money.

## Exercise

1. Write the vulnerable withdraw with `balanceOf[msg.sender] -= bal` after the call. Does checked arithmetic stop the attack?
2. Add a `totalDeposits` counter to `GuardedVault` and read it from inside the attacker's callback.

## What's next

Next post: **Gas optimization and upgradeable proxies**.
