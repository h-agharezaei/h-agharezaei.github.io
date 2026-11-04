+++
date = '2026-11-25T18:00:00+03:30'
draft = false
title = 'Contract security: reentrancy, access control and real incidents'
seoTitle = 'Contract security: reentrancy and access control'
description = 'Contract security in Solidity: reentrancy, token callbacks, open initializers, tx.origin and unchecked transfers, attacked in local tests and fixed.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "security", "reentrancy", "foundry", "defi"]
cover = { image = "/images/covers/bc-contract-security.png", alt = "Contract security: reentrancy, access control and real incidents", hiddenInSingle = true }
+++

Why does `withdraw` in [A first contract with Solidity and Foundry](/posts/bc-solidity-first-contract/) update the balance before it sends ETH? You might think the order does not matter, since both lines run in one transaction. It does matter. Sending ETH to a contract runs that contract's code, and that code can call `withdraw` again in the middle, before the balance has been zeroed.

[Oracles and price manipulation](/posts/bc-oracles/) broke a lending market without any bug. This post is about the bugs themselves. I attack a few classic mistakes in my own code, in a local Foundry test, and fix each one. [Authorization: RBAC and IDOR](/posts/sec-authorization-rbac-idor/) is the web version of the access control part.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project. Deliberately vulnerable contracts live in `test/vulnerable/`, attackers in `test/helpers/`. Teaching code, not audited.

## Reentrancy: the vault that pays twice

A real-world picture first. You go to a bank counter and say "I want my whole balance". The teller starts counting out the cash. If the teller updates the ledger only after handing over the money, and you say "I want my whole balance" again halfway through, the ledger still shows the full amount and the teller pays again.

The contract below does exactly that. It is a simple vault that holds ETH and records each person's balance in `balanceOf`:

```solidity
function withdraw() external {
    uint256 bal = balanceOf[msg.sender];
    (bool ok,) = msg.sender.call{value: bal}(""); // interaction first...
    if (!ok) revert TransferFailed();
    balanceOf[msg.sender] = 0; // ...effect too late
}
```

It sends the ETH first and zeroes the balance afterwards. When the recipient is a contract, sending ETH runs its `receive()` function. The attacker calls `withdraw()` again from inside `receive()`. The balance is still not zero, so the vault pays again, and this repeats. The attack is called {{< term "reentrancy" "reentrancy" >}}: entering the contract again before the first execution has finished.

In the test, Alice and Bob deposit 5 ETH each and the attacker deposits 1 ETH:

```
$ forge test --mt test_VulnerableVaultIsDrained -vv
  vault before    10000000000000000000
  vault after     0
  attacker has    11000000000000000000
  extra rounds    10
```

- **`vault before`:** the vault holds 10 ETH from Alice and Bob (the numbers are in wei: 10 followed by 18 zeros).
- **`attacker has`:** the attacker put in 1 ETH and took out 11, the whole vault including the 10 ETH of other people.
- **`extra rounds`:** ten times, `withdraw` was called again from inside `receive()`. Each round paid 1 ETH, because the attacker's balance never reached zero.

The fix is the order. It is called {{< term "checks-effects-interactions" "checks-effects-interactions" >}}: first the checks, then writing state, and only at the end calling outside. By the time we call out, the balance is already zero, so re-entering gets nothing.

```solidity
function withdraw() external nonReentrant {
    uint256 bal = balanceOf[msg.sender]; // checks
    if (bal == 0) revert NothingToWithdraw();
    balanceOf[msg.sender] = 0; // effects
    (bool ok,) = msg.sender.call{value: bal}(""); // interactions
    if (!ok) revert TransferFailed();
}
```

`nonReentrant` is a small lock in `src/Security.sol`: a storage flag set when the function is entered and cleared when it exits. While the flag is set, any re-entry reverts.

## A lock is not the whole fix

You might think that with a lock we no longer need to care about order. That is wrong too. `GuardedVault` keeps the bad order and locks only `withdraw`. Re-entering `withdraw` now fails. But the vault has another function, `move()`, which transfers a balance to another address, and it has no lock. In the middle of the callback the attacker uses `move()` to hand its not-yet-zeroed balance to an accomplice:

```
$ forge test --mt test_GuardMissesCrossFunction -vv
  deposited       1000000000000000000
  got back        2000000000000000000
  vault after     9000000000000000000
```

The attacker put in 1 ETH. It received 1 ETH from its own `withdraw`, and the balance it moved to the accomplice was withdrawn separately by the accomplice. In total 2 ETH came back and the vault dropped to 9 (11 minus 2).

This is cross-function reentrancy: the re-entry goes not into the same function but into another one that shares the state. `SafeVault` uses the right order and locks every state-changing function; both attackers revert.

There is a third kind: read-only reentrancy. Another contract reads one of your `view` functions in the middle of a callback and sees half-updated state. I did not build that one.

## Callbacks inside tokens

You do not have to send ETH yourself for someone to call you back. ERC-721's `safeTransferFrom` ([Tokens: ERC-20 and ERC-721](/posts/bc-erc20-erc721/)) calls `onERC721Received` on a contract recipient, so the recipient can confirm it accepts the token. That is also an external call.

Take a "one free NFT per address" mint that records `claimed` after this callback. The recipient claims again from inside the callback, and since `claimed` is not yet recorded, it is accepted:

```
$ forge test --mt test_CallbackReentersMint -vv
  NFTs for one address: 5
```

One address got five NFTs instead of one (the test attacker stops itself at five). Moving `claimed[msg.sender] = true` above the mint fixes it, which is the same checks-effects-interactions rule. As I understand it, ERC-777 tokens call hooks even on ordinary transfers.

## Access control

So far the attacks were subtle. The next kind is simpler and more embarrassing. {{< term "access-control" "Access control" >}} bugs, that is, bugs in controlling who may do what, are often one missing line.

`InitFeed` is a price feed for the lending market. It sets its owner in `initialize()`, but that function does not check whether it has been called before. So anyone can call it again whenever they like:

```
$ forge test --mt test_OpenInitializerDrainsMarket -vv
  feed owner is mallory: true
  USDX borrowed against 1 DEMO: 50000000000000000000000
  USDX left in market: 0
```

Mallory made herself the owner, priced DEMO at a million, borrowed the market's entire 50,000 USDX against a single DEMO of collateral, and the market was empty. The fix is one line: `if (owner != address(0)) revert AlreadyInitialized();`. Even better, call initialize in the deploy transaction itself, so no window is left for a stranger.

Authenticating with {{< term "tx-origin" "tx.origin" >}} is another classic mistake. `msg.sender` is whoever called the function directly. `tx.origin` is the account that signed the whole transaction, however many contracts sit in between. If a wallet looks only at `tx.origin`, the owner can be tricked into calling some other contract ("claim your airdrop"), and that contract empties the wallet from the inside:

```
$ forge test --mt test_TxOriginPhished -vv
  wallet   0
  airdrop  10000000000000000000
```

The wallet held 10 ETH. The owner only called `claim` on the fake airdrop. The wallet saw that `tx.origin` was the owner and sent the ETH to the airdrop. The fix is to use `msg.sender`.

## Return values and integers

Two more places where code quietly goes wrong.

First, return values. Some tokens do not revert on failure; they just return `false`. `FalseToken` does this, and `NaiveEscrow` does not look at the result. So Mallory, who owns no tokens, deposits 100 (`transferFrom` silently returns false, but the contract records 100 credit for her) and then withdraws 100, paid with Alice's tokens:

```
$ forge test --mt test_FalseTokenNaiveEscrow -vv
  mallory balance 100000000000000000000
  escrow balance  0
  alice credit    100000000000000000000
```

Mallory now holds 100 tokens, the escrow holds none, and Alice still believes she is owed 100.

`SafeTransfer` makes a low-level call and reverts unless the token returns `true` or nothing. As far as I know, some well-known older tokens return nothing, so `require(token.transfer(...))` is not enough either.

Second, integers. Since Solidity 0.8, arithmetic reverts on {{< term "integer-overflow" "overflow" >}}. But `unchecked` blocks and casts to a smaller type still wrap around, silently:

```
$ forge test --mt test_IntegerEdges -vv
  uint128(2**128 + 5) = 5
  uint8(300)          = 44
  unchecked 0 - 1     = 115792089237316195423570985008687907853269984665640564039457584007913129639935
```

Each line is one example. Cast 2^128 + 5 to `uint128` and only 5 is left. Cast 300 to `uint8` and you get 44 (300 minus 256). And `0 - 1` inside `unchecked` becomes the largest `uint256`. None of them raises an error.

## What the linter said about my code

You do not have to find all these patterns by eye. `forge lint` is {{< term "static-analysis" "static analysis" >}} built into Foundry: it reads the code without running it and reports suspicious patterns. On the pool, market and oracles from the last three posts:

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

`DemoToken` has no callbacks, so as far as I can tell none of these was exploitable yet. But most of the warnings pointed at habits worth dropping. I moved state updates and events before transfers, used `SafeTransfer`, added `nonReentrant`, fixed the precision loss in the cumulative price and suppressed the reviewed timestamp uses with a reason. Now `forge lint src` prints nothing and all 33 tests pass.

Copied into `src/`, the vulnerable contracts were flagged too (`reentrancy-eth`, `tx-origin`...), except the open initializer. So a linter does not catch everything. My fixed `SafeVault` was also flagged, because the lock is written after the call: a false positive. A tool does not replace thinking.

## Real incidents, in classes

- **Reentrancy:** The DAO (2016), whose drain led to the hard fork that split off Ethereum Classic.
- **Oracle manipulation:** the previous post's attack, seen in public post-mortems of lending protocols.
- **Key compromise:** as I understand them, several large bridge losses came from stolen validator keys, not contract bugs; see also [the Binance hack](/posts/binance-hack-hot-wallet-2026/).

## A pre-deploy checklist

- **In every function: checks, then effects, then interactions, then a lock.**
- **Any external call, including a token transfer, can call you back.**
- **For each privileged function and each initializer, write a test that a stranger cannot call it.**
- **Call tokens through a checked helper.** Review every `unchecked` and narrowing cast, and do not use `tx.origin`.
- **Lint clean or explained, invariant tests** as in [Testing, fuzzing and invariants with Foundry](/posts/bc-foundry-testing-fuzzing/), and an outside review for real money.

## Exercise

1. Write the vulnerable withdraw with `balanceOf[msg.sender] -= bal` after the call. Does checked arithmetic stop the attack?
2. Add a `totalDeposits` counter to `GuardedVault` and read it from inside the attacker's callback.

## What's next

**Gas optimization and upgradeable proxies**: safe code still costs gas, and deployed code cannot be patched.
