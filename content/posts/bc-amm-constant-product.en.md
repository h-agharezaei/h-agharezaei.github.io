+++
date = '2026-11-22T18:00:00+03:30'
draft = false
title = 'AMMs and the constant-product formula'
description = 'A constant-product AMM in Solidity: x*y=k, LP shares, a 0.3% fee, rounding in favour of the pool, price impact, slippage limits and invariant tests.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "amm", "foundry", "go"]
cover = { image = "/images/covers/bc-amm-constant-product.png", alt = "AMMs and the constant-product formula", hiddenInSingle = true }
+++

When you buy a stock or a currency on an ordinary exchange, there is an order book behind the scenes: a list of "I will buy at this price" and "I will sell at that price". A matching engine pairs buyers and sellers. On a blockchain this is awkward: placing an order and cancelling it are each a transaction, they cost gas and they wait for a block.

An {{< term "amm" "AMM" >}} (automated market maker) goes another way. Instead of pairing buyers and sellers, it removes the counterparty altogether. A contract holds two kinds of tokens in a kind of "warehouse", and a simple formula sets the price. Anyone can come, put one token into the warehouse and take the other out. No counterparty is needed, and no order sits waiting.

In this post I build a small version of this idea for two [ERC-20 tokens](/posts/bc-erc20-erc721/). After [the wallets post](/posts/bc-hd-wallets-rust/) the series enters DeFi, financial programs that run only on smart contracts. I test the contract as in [the testing post](/posts/bc-foundry-testing-fuzzing/) and double-check its arithmetic with a small Go program.

> Run with Foundry 1.8.7, solc 0.8.38 and Go 1.27.3 on macOS (arm64). The demo is a local Foundry project with only forge-std; `DemoToken` is copied unchanged from the tokens post. The design is, as far as I understand it, a simplified Uniswap v2. The contract is for teaching and is not audited. This post is not financial advice.

## The core idea with a small example

First, with no formula. Suppose our warehouse holds 10 DEMO and 1000 USDX (a demo dollar token). The price comes from the ratio of the two: 1000 divided by 10, so each DEMO costs 100 USDX. (These numbers are made up for illustration and are not from the demo.)

The AMM's rule is: **the product of the two balances must never decrease.** Right now the product is 10 × 1000 = 10,000. Suppose someone wants 1 DEMO. After the purchase 9 DEMO is left. For the product to stay at 10,000, the USDX balance must become at least 10,000 ÷ 9 ≈ 1111.11. So the buyer must pay 111.11 USDX, not 100. If they want 5 DEMO, the DEMO balance falls to 5 and USDX must become 2000: 1000 USDX for 5 DEMO, an average of 200 per DEMO.

Two things become clear from this example:

- The more you buy, the more expensive each unit is. Buying DEMO lowers the DEMO balance, and the next DEMO costs more.
- The warehouse never runs out of DEMO. As the DEMO balance approaches zero, the price goes to infinity.

The gap between the price you expected (100) and the price you actually pay (111.11) has a name: {{< term "slippage" "slippage" >}}. The larger the trade compared with the warehouse, the larger the gap. Later we will put a limit on it.

This rule is called {{< term "constant-product" "constant product" >}}. If we call the balance of token0 `x` and the balance of token1 `y`, the rule is `x * y = k`. Someone gives `dx` to the warehouse and takes out `dy`:

```
(x + dx) * (y - dy) = x * y   =>   dy = y * dx / (x + dx)
```

The spot price is simply `y / x`. Let us test the formula on our small example. There we gave USDX and received DEMO, so the role of `x` belongs to USDX: `x = 1000`, `y = 10` and `dx = 1000/9 ≈ 111.11`. The result is `dy = 10 × 111.11 / (1000 + 111.11) = 1`, the same 1 DEMO. The formula is the same for both directions of a trade; only the roles of `x` and `y` swap.

## The warehouse and its providers

Where does the warehouse get filled? By people who put both tokens into it. They are called liquidity providers, and the warehouse is a {{< term "liquidity-pool" "liquidity pool" >}}. In return for what they deposit, they get a receipt called a **share**. Whenever they want, they hand the shares back and take a proportional part of the warehouse. Their incentive is the fee that each trade leaves in the pool (we see it in the swap section).

This is how the contract hands out shares:

```solidity
if (totalShares == 0) {
    // First deposit: shares = sqrt(x * y), independent of which token is "price".
    shares = sqrt(amount0 * amount1) - MINIMUM_SHARES;
    sharesOf[address(0)] = MINIMUM_SHARES;
    totalShares = MINIMUM_SHARES;
} else {
    // Later deposits: proportional to the smaller side, so an unbalanced deposit is not rewarded.
    shares = min(amount0 * totalShares / reserve0, amount1 * totalShares / reserve1);
}
```

- **The first deposit:** shares equal the square root of the product of the two amounts. Whatever price the first provider sets with the ratio of their deposit becomes the starting price.
- **The 1000 locked shares:** 1000 units are subtracted from the first provider's shares and locked forever at `address(0)`. As far as I understand Uniswap v2's reason, this makes inflating the value of one share expensive, so that later depositors' shares do not round down to zero.
- **Later deposits:** shares are proportional to the smaller side. So if someone deposits unevenly (a lot of one token and little of the other), they get nothing for the excess.

`removeLiquidity` returns both tokens in proportion, `shares * reserve / totalShares`, and rounds the division down.

## Swap and the fee

Now the trade itself, with the fee. Look at these two functions:

```solidity
function getAmountOut(uint256 amountIn, uint256 reserveIn, uint256 reserveOut) public pure returns (uint256) {
    uint256 inWithFee = amountIn * (10_000 - FEE_BPS); // FEE_BPS = 30, i.e. 0.3%
    return inWithFee * reserveOut / (reserveIn * 10_000 + inWithFee);
}

function swap(address tokenIn, uint256 amountIn, uint256 minAmountOut, address to, uint256 deadline)
    external returns (uint256 amountOut)
{
    if (block.timestamp > deadline) revert Expired();
    // ... pick the direction, read (rIn, rOut)
    amountOut = getAmountOut(amountIn, rIn, rOut);
    if (amountOut < minAmountOut) revert SlippageExceeded(amountOut, minAmountOut);
    // transferFrom tokenIn, update both reserves, transfer amountOut to `to`
}
```

`getAmountOut` is the formula from the previous section with one difference: it puts only 99.7 percent of the input into the formula (`FEE_BPS = 30` means 30 "basis points", each a hundredth of a percent, so 0.3 percent). But the whole input is added to the pool's balance. The 0.3 percent that was not counted in the formula stays in the pool, to the providers' benefit. As a result `x * y` grows slightly with every trade.

Get to know the two other inputs of `swap` now: `minAmountOut` (the minimum output you accept) and `deadline` (the latest time). The slippage-limit section shows what they are for.

To see the fee's effect, I wrote a test: bob turns 10,000 USDX into DEMO and immediately turns that DEMO back into USDX, twenty times. Then alice, the pool's provider, takes back all her shares:

```
$ forge test --mt test_FeesGoToProviders -vv
alice DEMO back 999999999999999999900
alice USDX back 101090373314923143288739
```

alice started with 1,000 DEMO and 100,000 USDX. Her DEMO is now almost the same (999.999999999999999900 DEMO, only 100 wei less, a leftover of rounding). But her USDX has become 101,090.37. The difference is the fees bob left in the pool with each round trip.

## Rounding in the pool's favour

Solidity has no floating point, and integer division drops the fraction. So we must decide: when a trade's output has a fraction, do we round up or down? The right answer is down. The trader gets slightly less and `k` grows. Rounding up gives the trader one extra wei, and with small balances `k` shrinks. A test with tiny balances (1000 wei on each side, 3 wei in) shows it:

```
$ forge test --mt test_RoundingUpWouldBreakK -vv
  out rounded down 2 k after 1000994
  out rounded up   3 k after 999991
```

Before the trade `k` is 1,000 × 1,000 = 1,000,000. Rounded down, the output is 2 and `k` becomes 1,000,994, so it grew. Rounded up, the output is 3 and `k` becomes 999,991, smaller than before. The pool has lost value.

This is the rule of all DeFi arithmetic: round against whoever takes something out.

## Trade size and price impact

Back to the first example, now with the demo's numbers. Our pool holds 1,000 DEMO and 100,000 USDX, so the spot price is 100. A small Go program computes the same integer formula with `math/big`. This is what a backend does before sending a swap: it builds a "quote", a price estimate in advance. For six input sizes of USDX it asks: how many DEMO do I get?

```
$ go run .
USDX in | DEMO out               | avg price | vs spot | min out (0.5%)
    100 | 996006981039903216     |    100.40 |  +0.40% | 991026946134703699
   1000 | 9871580343970612988    |    101.30 |  +1.30% | 9822222442250759923
   5000 | 47482973758155927037   |    105.30 |  +5.30% | 47245558889365147401
  10000 | 90661089388014913158   |    110.30 | +10.30% | 90207783941074838592
  50000 | 332665999332665999332  |    150.30 | +50.30% | 331002669336002669335
 100000 | 499248873309964947421  |    200.30 | +100.30% | 496752628943415122683
```

The columns:

- **`USDX in`:** how many USDX we give.
- **`DEMO out`:** how many DEMO we get, in wei (18 decimals). For example 996006981039903216 is about 0.996 DEMO.
- **`avg price`:** the average USDX per DEMO.
- **`vs spot`:** how many percent more expensive than the spot price of 100. This is the price impact.
- **`min out (0.5%)`:** 99.5 percent of the output, that is, we are happy even if we get 0.5 percent less. It will be useful in a moment.

Read the first row: 100 USDX, that is 0.1 percent of the pool. The average price is 100.40, 0.40 percent higher. 0.30 percent of it is the fee and 0.10 percent is the effect of the curve. In the lower rows, as the trade grows, the fee's share stays constant while the curve's effect gets bigger and bigger: with 10,000 USDX the price is 10 percent higher, and if you spend all of the pool's USDX (100,000), the average price doubles and you get only about half of the pool's DEMO (499.25).

The test `test_PriceImpactTable` swaps these same sizes on the real pool (restoring the state each time) and logs the same numbers. The two computations agree: the `DEMO out` column is identical in both.

## Slippage limit and deadline

You build a quote from the state you see now. But your swap runs on the state at the moment it executes in a block, and other transactions may have arrived in between. So `swap` has two guards:

- **`minAmountOut`:** the worst result you accept. If the output is smaller, the transaction reverts. This is the slippage tolerance. The last column of the table above, `min out (0.5%)`, was for this.
- **`deadline`:** if a transaction sits in the [mempool](/posts/bc-mempool-fees/) for hours and then runs, the price may have changed completely. With `deadline` such a transaction is rejected.

The next test shows the first case. Bob gets a quote for 10,000 USDX and sets a 0.5 percent tolerance. But before his transaction executes, eve buys with 20,000 USDX in the same direction and pushes the price up:

```
$ forge test --mt test_FrontRunHitsMinOut -vv
[PASS] test_FrontRunHitsMinOut() (gas: 177978)
Logs:
  bob quote  90661089388014913158
  bob would get 63956986828671189740
```

Bob's first quote was 90.66 DEMO. After eve's purchase, the same swap would give only 63.96 DEMO. Bob's minimum was 90.21 (99.5 percent of 90.66), so this is far below it. Bob's transaction therefore reverts with `SlippageExceeded` (the test expects exactly that, and `[PASS]` means exactly that happened). Had Bob set `minAmountOut = 0`, the swap would have gone through and given him 63.96.

Buying right before the victim and selling right after is called a {{< term "sandwich-attack" "sandwich attack" >}}, and our test shows only its first half. `minAmountOut: 0` is an invitation to the attacker. MEV has a post of its own.

## Invariant testing

The tests above try a few specific situations. But the rule "`k` never decreases on a swap" must hold in **every** situation. For that we have {{< term "invariant-testing" "invariant testing" >}}: we write a "handler" that randomly calls swap in both directions, add liquidity and remove liquidity for three actors, and records `k` around each swap. Then the tool repeats such sequences 256 times with 500 calls each, and after every call it checks that two rules hold: `k` has not decreased on a swap, and the pool's recorded balances equal the tokens' real balances:

```
$ forge test
[PASS] test_DeadlinePassed() (gas: 39237)
[PASS] test_FeesGoToProviders() (gas: 3206792)
[PASS] test_FirstDepositIsSqrt() (gas: 46202)
[PASS] test_FrontRunHitsMinOut() (gas: 177978)
[PASS] test_PriceImpactTable() (gas: 572851)
[PASS] test_RoundingUpWouldBreakK() (gas: 19117)
[PASS] test_SwapGrowsK() (gas: 122349)
[PASS] invariant_KNeverDecreasesOnSwap
[PASS] invariant_ReservesMatchBalances
 SimplePoolInvariantTest invariants (runs: 256, calls: 128000, reverts: 0)
Ran 2 test suites in 16.23s (16.23s CPU time): 8 tests passed, 0 failed, 0 skipped (8 total tests)
(trimmed)
```

All seven ordinary tests and both invariants pass: 256 runs, 128,000 calls and zero reverts. (The run time differs from run to run; 16.23 s is from my run.)

But a test that has never failed may not be working at all. So I planted a bug on purpose: I made `getAmountOut` round up, the same thing we saw is bad in the rounding section. The invariant runner failed, and with {{< term "shrinking" "shrinking" >}} it reduced the failing sequence to its smallest form: a single swap of a few wei.

```
[FAIL: assertion failed: 1 != 0] invariant_KNeverDecreasesOnSwap
	[Sequence] (original: 4, shrunk: 1)
		sender=0xDD58...DF75 addr=[test/handlers/PoolHandler.sol:PoolHandler]0xD6Bb...FBfF calldata=swap(uint256,bool,uint256) args=[3, true, 3]
(addresses shortened)
```

`original: 4, shrunk: 1` means the first failing sequence was 4 calls and was reduced to 1. The handler's `swap` arguments are the actor number, the direction and the amount. These numbers differ every time you run the test; when I tried the same bug again, it ended at `args=[3966, false, 1]` (a swap of 1 wei in the other direction). The point is the same in both: a tiny, harmless-looking swap that still makes `k` smaller, and without invariant testing it might have been found months later.

## Where to be careful

- **Never send a swap with `minAmountOut = 0` or without a deadline.** Compute the minimum off-chain from a fresh quote.
- **Price impact depends on the depth of the pool.** A shallow pool means expensive trades.
- **Round every division in the pool's favour** and make sure of it with invariant testing.
- **The pool tracks its balances itself; fee-on-transfer tokens break it.** This contract assumes every transfer moves exactly the stated amount.
- **The spot price `y / x` can easily be moved inside one transaction.** Remember this for the oracle post.

## Exercise

1. Add `getAmountIn` (exact output) and decide, for each division, which way to round.
2. Run the price-impact table on a pool ten times deeper.
3. Plant a bug in `removeLiquidity` (round up) and write an invariant that catches it.

## What's next

The next post is "Lending, collateral and liquidation": an AMM makes the market work without an intermediary, and there we see a contract take the place of the loan officer too.
