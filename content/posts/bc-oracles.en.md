+++
date = '2026-11-24T18:00:00+03:30'
draft = false
title = 'Oracles and price manipulation'
description = 'Oracles and price manipulation in Solidity: a one-transaction attack on my own AMM-priced lending market, then a TWAP oracle with a staleness check.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "oracle", "security", "foundry"]
cover = { image = "/images/covers/bc-oracles.png", alt = "Oracles and price manipulation", hiddenInSingle = true }
+++

Picture a judge in a locked room who has to give a ruling but can only use the papers that are already inside. He cannot phone anyone, read a newspaper or ask a question. A smart contract is in exactly that position. It cannot visit a website and look up the price of a token. Any number it uses must already be on-chain: either someone put it there, or it was computed from something that is.

The source that delivers such a number to a contract is called an {{< term "oracle" "oracle" >}}. [Lending, collateral and liquidation](/posts/bc-lending-liquidation/) computed everything from one price: the borrow limit, the health factor and the liquidation. There, the owner typed that price in by hand. That is fine for a test and wrong for real money, because whoever controls the price controls the market.

A tempting replacement is already deployed. The pool from [AMMs and the constant-product formula](/posts/bc-amm-constant-product/) has a price of its own. If it holds 1,000 DEMO and 100,000 USDX, one DEMO is worth 100 USDX: that is `reserve1 / reserve0`. Why not use it? Because that price changes with every trade, and anyone is free to trade.

In this post I wire the lending market to the pool's spot price, attack it in one transaction, and then fix it. The attack runs only against my own contracts, in a local Foundry test.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project, added a cumulative price to `SimplePool` and `src/Oracles.sol` with two oracles. The attacker contract lives in `test/`. Teaching code, not audited.

## The attack

First the idea, without code. Whenever the lending market wants to know what your collateral is worth, it reads the pool's current price. If, right before that reading, I make the pool's price several times higher, the market believes my collateral is worth far more than it is and lends me a lot. Then I bring the price back. My real collateral is cheap, and the big loan stays with me.

The starting state: the pool holds 1,000 DEMO and 100,000 USDX, so the price is 100. The market lends up to 75% of the collateral's value and reads the price from `SpotOracle`, which only returns `pool.spotPrice0()`. The attacker owns 100 DEMO (worth 10,000 USDX at the fair price) and, for the length of one transaction, 100,000 USDX.

Where would those 100,000 USDX come from? On mainnet, from a {{< term "flash-loan" "flash loan" >}}. It is a loan that must be repaid inside the same transaction that took it. If it is not repaid by the end, the whole transaction reverts as if nothing happened. So the lender takes no risk, and the attacker needs no capital of their own. In the test, a mint stands in for it.

The attack has four steps:

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

1. It buys DEMO in the pool with all 100,000 USDX. The pool has less DEMO, so DEMO gets more expensive.
2. It deposits its own 100 DEMO into the lending market as collateral. The market asks the pool for the price, gets the inflated one, and lends USDX up to its limit.
3. It sells the DEMO it bought back to the pool. The price returns to roughly 100.
4. It repays the 100,000 USDX flash loan. Whatever USDX is left belongs to the attacker.

The test run:

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

Line by line:

- **`price the market saw`:** the market saw 399.4, not 100. The reason is the constant-product formula: when the pool's USDX roughly doubles, its DEMO roughly halves, and the price (the ratio of the two) roughly quadruples. This is what the price impact table in the AMM post showed.
- **`borrowed`:** the market valued 100 DEMO at 39,940 and lent 75% of that, 29,955 USDX.
- **`USDX kept`:** after repaying the flash loan the attacker has 29,654.55 USDX left. About 300 of the 29,955 went to swap fees on the round trip.
- **`profit`:** the attacker abandons collateral worth 10,000, so the net profit is 29,654.55 minus 10,000: 19,654.55.
- **`pool price after`:** the pool is back at 100.3. The attack left no trace on the price.
- **`market health`:** the market now holds a 29,955 loan backed by 100 DEMO worth about 10,000. Health is 0.27 and no liquidation can fix it, because the collateral cannot cover the debt.

That is {{< term "price-manipulation" "price manipulation" >}}. Nothing in the pool or the market had a bug. The design trusted a number that anyone can move for the price of the swap fees.

As far as I know from public post-mortems, several real lending protocols lost money in this exact shape. I am not naming any, because I cannot check the details here.

## The fix: a time-weighted average

Why did the attack work? A spot price is a single instant, and inside their own transaction the attacker owns that instant. A price averaged over a period of time is different. To move it, you must hold the price high for a long time, and that costs money.

Think of a car's speedometer versus the average speed of a trip. You can push the speedometer to 200 for a moment. You cannot do that to the trip average. A made-up example: the price was 100 for 20 minutes and 150 for 10 minutes. The time-weighted average is (100 × 20 + 150 × 10) / 30 ≈ 116.7.

To build such an average, the pool keeps a running sum: the price multiplied by the seconds that price was in effect. It is similar to Uniswap v2's cumulative price, as I understand it:

```solidity
function _accumulate() internal {
    uint256 dt = block.timestamp - lastUpdate;
    if (dt > 0 && reserve0 != 0) price0Cumulative += reserve1 * 1e18 / reserve0 * dt;
    lastUpdate = block.timestamp;
}
```

This runs at the start of every swap and liquidity change and works with the reserves from before it. So a price created inside a block only counts in the sum once time passes. If the attacker raises the price and restores it in one transaction, the pumped price was in effect for zero seconds, and zero seconds add nothing.

The {{< term "twap" "TWAP" >}} (time-weighted average price) is the difference of two readings of this sum, divided by the seconds between them:

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

Anyone (a keeper, say) can call `update()`, but only after a full `window`, here 30 minutes, has passed since the previous reading. `price()` returns the average of the last window. If the last `update()` is more than two windows old, `price()` reverts instead of answering with an old price. That is the staleness check.

Same attacker, same numbers, but the market now reads a 30-minute TWAP:

```
$ forge test --mt test_TwapOracleResists -vv
  price the market saw 100000000000000000000
  borrowed             7500000000000000000000
  USDX kept            7199550002031084112432
  profit (USDX)        -2800449997968915887568
  market health        1066666666666666666
(trimmed)
```

- **`price the market saw`:** 100 this time, because the TWAP still shows the average of the quiet half hour before.
- **`borrowed`:** the attacker gets an ordinary loan, 7,500 against collateral worth 10,000.
- **`profit`:** negative. They paid about 300 in round-trip fees and must abandon the 10,000 collateral, so they lose about 2,800.
- **`market health`:** 1.067, a healthy loan.

(I left out the `pool price after` line to keep it short.)

Even calling `update()` right after the pump changes nothing, because the pumped price had been in effect for zero seconds:

```
$ forge test --mt test_TwapIgnoresSameBlockPump -vv
  spot after pump 399399999999999999999
  twap            100000000000000000000
```

## What a TWAP costs

A TWAP is not free: it lags. Suppose a real buy moves the spot price to 146.33, ten minutes before the end of a 30-minute window:

```
$ forge test --mt test_TwapFollowsALastingMove -vv
  spot after a real buy 146333769999999999999
  twap over 30 minutes  115444589999999999999
```

The price was 100 for twenty minutes and 146.33 for ten, so the average is 115.4, and the market still sees a price below the real one. In a sudden crash the same lag works the other way and liquidations arrive late.

There is another attack too: holding a manipulated price for several blocks in a row. Against a TWAP this is harder and costlier because of arbitrage (traders who push the price back to normal), but on a thin pool it is not impossible. So the window length trades safety against freshness.

If nobody calls `update()`, `price()` reverts (`test_StalePriceRefused`). Borrowing stops instead of continuing on an old price.

The other common design is a push oracle: independent reporters publish a price on-chain. Chainlink-style feeds, according to their docs, expose the answer together with an `updatedAt` timestamp. A consumer should reject old answers and sudden jumps beyond a set deviation. I did not build one here; the staleness rule above is the same idea.

## Where an oracle gets fooled

- **Do not price collateral with the spot price of a pool that can be traded in the same transaction.** That is exactly what the attack above used.
- **Flash loans give anyone large capital for one transaction.** "The attack would need a lot of money" is not a defence.
- **Check freshness.** An oracle that has not been updated should stop borrowing, not answer quietly.
- **Pick the TWAP window to match the pool's depth.** A thin pool needs a longer window or another source.

## Exercise

1. Find the smallest loan that still makes the spot-oracle attack profitable.
2. Move the attacker's `update()` call one block after the pump (`vm.roll`, `vm.warp` by 12 s). How far does the TWAP move?
3. Write a guard that refuses to borrow while spot and TWAP differ by more than 5%.

## What's next

**Contract security: reentrancy, access control and real incidents**: this attack needed no bug; the next ones do.
