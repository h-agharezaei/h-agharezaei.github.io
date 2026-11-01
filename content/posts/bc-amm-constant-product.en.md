+++
date = '2027-07-03T10:00:00+03:30'
draft = false
title = 'AMMs and the constant-product formula'
description = 'A constant-product AMM in Solidity: x*y=k, LP shares, a 0.3% fee, rounding in favour of the pool, price impact, slippage limits and invariant tests.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "amm", "foundry", "go"]
cover = { image = "/images/covers/bc-amm-constant-product.png", alt = "AMMs and the constant-product formula", hiddenInSingle = true }
+++

The previous post, [HD wallets: BIP-32, BIP-39 and BIP-44 in Rust](/posts/bc-hd-wallets-rust/), was about keys. Now the series moves to DeFi: contracts that hold tokens and trade them.

An exchange usually runs an order book: buyers and sellers post prices and a matching engine pairs them. On a chain every order and cancel costs gas and waits for a block. An {{< term "amm" "AMM" >}} (automated market maker) drops the order book. A contract holds two tokens and a formula sets the price. I build a minimal one for two [ERC-20 tokens](/posts/bc-erc20-erc721/), test it the way [the Foundry testing post](/posts/bc-foundry-testing-fuzzing/) did, and check its math with a small Go program.

> Foundry 1.8.7, solc 0.8.38, Go 1.27.3, macOS (arm64). The demo is a local Foundry project with forge-std only; `DemoToken` is copied unchanged from the tokens post. The design follows Uniswap v2 as I understand it, much simplified. A teaching contract: not audited.

## x * y = k

The pool holds reserves `x` of token0 (DEMO) and `y` of token1 (USDX, a stand-in dollar token). A swap must keep the product `x * y` at least where it was. That is the {{< term "constant-product" "constant-product" >}} rule. Put `dx` in, take `dy` out:

```
(x + dx) * (y - dy) = x * y   =>   dy = y * dx / (x + dx)
```

The price is `y / x`, and every trade moves it: buying DEMO removes DEMO, so the next one costs more. As `x` approaches zero the price runs to infinity, so the pool cannot be emptied.

## The pool

Liquidity providers deposit both tokens into the {{< term "liquidity-pool" "liquidity pool" >}} and get shares:

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

The 1,000 shares locked at `address(0)`, as I understand Uniswap v2's reasoning, make it expensive to inflate one share's value until later depositors' shares round down to zero. `removeLiquidity` pays out `shares * reserve / totalShares`, rounded down.

Swapping:

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

The fee is the formula with only 99.7% of the input; the full input still lands in the reserves, so the extra 0.3% stays with the providers. A test does 20 round trips of 10,000 USDX; alice then withdraws 101,090.37 USDX instead of the 100,000 she put in.

## Rounding goes the pool's way

Integer division truncates, and here that is the right direction: the trader gets slightly less, `k` grows. Rounding up gives away one wei, and with tiny reserves you can see `k` shrink:

```
$ forge test --mt test_RoundingUpWouldBreakK -vv
  out rounded down 2 k after 1000994
  out rounded up   3 k after 999991
```

The rule for any DeFi math: round against whoever takes something out.

## Price impact

The pool holds 1,000 DEMO and 100,000 USDX, so spot is 100. The Go program uses the same integer formula with `math/big`, the kind of quote a backend computes before sending a swap:

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

`test_PriceImpactTable` swaps the same sizes on the real pool and logs the same integers. 0.30% is the fee, the rest is the curve: spending as much USDX as the pool holds doubles the average price.

## Slippage limits and deadlines

The quote is made against the state you saw; the swap runs against the state at execution. Between them, other transactions can land. `minAmountOut` sets the worst result you accept ({{< term "slippage" "slippage" >}} tolerance), `deadline` stops a transaction that waited in the [mempool](/posts/bc-mempool-fees/) for hours. In this test Bob quotes 10,000 USDX with 0.5% tolerance, then eve's 20,000 USDX buy lands first:

```
$ forge test --mt test_FrontRunHitsMinOut -vv
[PASS] test_FrontRunHitsMinOut() (gas: 177978)
Logs:
  bob quote  90661089388014913158
  bob would get 63956986828671189740
```

With `minAmountOut = 0` the same swap would pay Bob 63.96 DEMO instead of 90.66. Buying just before a victim and selling just after is a {{< term "sandwich-attack" "sandwich attack" >}}; `minAmountOut: 0` is an invitation. MEV gets its own post.

## The invariant test

A handler swaps both ways and adds and removes liquidity for three actors, recording `k` around every swap ({{< term "invariant-testing" "invariant test" >}}):

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

Then I planted the bug: `getAmountOut` rounding up. The runner broke the invariant and {{< term "shrinking" "shrank" >}} the sequence to one call, a 3-wei swap:

```
[FAIL: assertion failed: 1 != 0] invariant_KNeverDecreasesOnSwap
	[Sequence] (original: 4, shrunk: 1)
		sender=0xDD58...DF75 addr=[test/handlers/PoolHandler.sol:PoolHandler]0xD6Bb...FBfF calldata=swap(uint256,bool,uint256) args=[3, true, 3]
(addresses shortened)
```

## A few things to watch

- Never send a swap with `minAmountOut = 0` or a far deadline. Compute the minimum off-chain from a fresh quote.
- Price impact depends on pool depth. A thin pool is an expensive pool.
- Round every division in the pool's favour, and have an invariant test that would notice if you did not.
- The pool tracks reserves itself; fee-on-transfer tokens would break it.
- The spot price `y / x` is trivial to move inside one transaction. Remember that for the oracle post.

## Exercise

1. Add `getAmountIn` (exact output) and decide which way each division must round.
2. Run the price impact table on a pool ten times deeper.
3. Plant a bug in `removeLiquidity` (round up) and write the invariant that catches it.

## What's next

Next post: **Lending, collateral and liquidation**.
