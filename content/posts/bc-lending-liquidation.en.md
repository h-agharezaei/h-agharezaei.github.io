+++
date = '2026-11-23T18:00:00+03:30'
draft = false
title = 'Lending, collateral and liquidation'
description = 'An overcollateralized lending market in Solidity: borrow limits, a per-second interest index, health factor and liquidation with a bonus, in Foundry.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "lending", "foundry"]
cover = { image = "/images/covers/bc-lending-liquidation.png", alt = "Lending, collateral and liquidation", hiddenInSingle = true }
+++

If you go to a pawnshop and leave your phone as a pledge, the pawnbroker does not ask who you are. A phone worth more than the money he hands over is enough. If you do not pay back, he sells the phone and takes what he is owed.

A smart contract is in the pawnbroker's position, with one difference: it cannot check identity, call a court or send a letter. All it can do is hold something worth more than the loan, and sell it before the loan is worth more than the collateral. [The AMM in the previous post](/posts/bc-amm-constant-product/) replaced the order book; this post replaces the loan officer.

That is called {{< term "overcollateralization" "overcollateralization" >}}: more collateral than loan. In this post I build a minimal lending market in the same Foundry project: you put up DEMO as collateral, borrow USDX (both [DemoTokens](/posts/bc-erc20-erc721/)), pay interest, and get liquidated if the price falls. The tests use `vm.warp` and fuzzing from [the Foundry testing post](/posts/bc-foundry-testing-fuzzing/).

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project into a new local folder and added `src/PriceFeed.sol`, `src/LendingMarket.sol` and their test. The lenders' side (supply shares, a rate that follows utilization) is left out: the test mints the USDX straight into the market. A teaching contract, not audited. This post is not financial advice.

## Collateral, borrow limit and health factor

First a simple example, without code. These numbers are made up for the example, but they match the demo we run below. You have 10 DEMO and each DEMO is worth 100 USDX, so your collateral is worth 1,000 USDX. The market does not let you borrow all of it: only 75 percent, which is 750 USDX. In the contract this ratio is one of four constants:

```solidity
uint256 public constant COLLATERAL_FACTOR = 0.75e18; // borrow up to 75% of collateral value
uint256 public constant LIQUIDATION_THRESHOLD = 0.8e18; // liquidatable once debt > 80% of value
uint256 public constant CLOSE_FACTOR = 0.5e18; // at most 50% of a debt repaid per liquidation
uint256 public constant LIQUIDATION_BONUS = 1.05e18; // liquidator gets 5% extra collateral
```

- **`COLLATERAL_FACTOR`:** the borrow limit: 75 percent of the collateral's value.
- **`LIQUIDATION_THRESHOLD`:** if the debt grows above 80 percent of the collateral's value, anyone may liquidate the loan, that is, repay part of it and take collateral in return.
- **`CLOSE_FACTOR`:** one liquidation may repay at most half of the debt.
- **`LIQUIDATION_BONUS`:** whoever liquidates gets 5 percent more collateral than the value they paid. That bonus is their incentive.

The gap between 75 and 80 percent is deliberate: a new loan must not become liquidatable on the next block because of a small price move or one second of interest.

To see how healthy a loan is, we need a single number. The {{< term "health-factor" "health factor" >}} summarizes it:

```solidity
function healthFactor(address user) public view returns (uint256) {
    uint256 debt = debtOf(user);
    if (debt == 0) return type(uint256).max;
    return collateralValue(user) * LIQUIDATION_THRESHOLD / debt;
}
```

That is the collateral's value times 0.8, divided by the debt. If the number is above 1 (in code `1e18`, because numbers are stored with 18 decimals) the loan is safe, and below it anyone may liquidate. For 10 DEMO and a loan of exactly 750:

```
$ forge test --mt test_BorrowLimit -vv
  health at the limit 1066666666666666666
```

This 1.0666 is 1,000 × 0.8 / 750. A loan taken right at the limit is still above 1, which is the safety margin mentioned above. 751 USDX is not given at all: the transaction reverts with `ExceedsBorrowLimit(751e18, 750e18)`.

## Interest with an index

A loan carries interest: every second the debt grows a little. But the contract cannot visit every borrower every second and update each debt; that is impossible (and expensive) on-chain. The solution is a simple idea: all debts grow by the same factor, so we keep only that factor.

An example (made-up numbers): suppose the factor is now 1.02 and you borrow 500 USDX. The contract stores `500 / 1.02 ≈ 490.2`, called the "scaled debt". Later, when the factor reaches 1.10, your debt is 490.2 × 1.10 ≈ 539.2. Nothing had to change for any borrower; only the factor moved forward.

In code:

```solidity
function currentIndex() public view returns (uint256) {
    uint256 dt = block.timestamp - lastAccrual;
    return borrowIndex + borrowIndex * ratePerSecond * dt / WAD;
}

function debtOf(address user) public view returns (uint256) {
    return ceilDiv(scaledDebtOf[user] * currentIndex(), WAD); // debt rounds up
}
```

{{< term "borrow-index" "borrowIndex" >}} starts at 1e18 and says what one unit borrowed at the start is worth now. `currentIndex` adds the per-second interest from the last update until now. Any call to `accrue()` moves the factor forward for everybody, at a constant cost (O(1)) and with no loop over borrowers. It is the same idea as the LP shares in the previous post: store a share of something that grows, not the amount itself.

To try it, Alice borrows 500 USDX at 10 percent a year and the clock jumps forward a year. Once with nobody touching the market, and once with an `accrue()` every day:

```
$ forge test --mt test_InterestAccrues -vv
  debt, 1 accrual   549999999994064000000
  debt, 365 accruals 552577890801573687000
  index              1105155781603147374
```

- **`1 accrual`:** the debt is 549.9999999994, that is 500 plus 10 percent, simple interest.
- **`365 accruals`:** 552.58. Because the interest was added to the factor every day, and the next day earned interest on top of that, the interest compounded and came out higher.
- **`index`:** the factor after a year, 1.105155.

The rate per second is `0.1e18 / 365 days`, truncated to 3170979198, which is why the first number is 0.000000005936 short of 550. Real markets compute more carefully and take the rate from utilization, but the index pattern is the same.

## Liquidation

Now the heart of it. Suppose Alice holds 10 DEMO and has borrowed 700 USDX. At a price of 100 the collateral is worth 1,000 and the loan is healthy. Then DEMO falls 15 percent to 85. Now the collateral is worth 850, and 700 is more than 80 percent of 850 (which is 680): the loan is unhealthy. The market lets anyone repay part of the debt and take the collateral at a discount. That is called a {{< term "liquidation" "liquidation" >}}. Without it, if the price kept falling, the debt would exceed all the collateral and the lenders would take the loss.

```solidity
function liquidate(address user, uint256 repayAmount) external returns (uint256 seized) {
    accrue();
    uint256 hf = healthFactor(user);
    if (hf >= WAD) revert PositionHealthy(hf);
    uint256 debt = debtOf(user);
    uint256 maxRepay = debt * CLOSE_FACTOR / WAD;
    if (repayAmount == 0) revert ZeroAmount();
    if (repayAmount > maxRepay) revert ExceedsCloseFactor(repayAmount, maxRepay);

    seized = repayAmount * LIQUIDATION_BONUS / oracle.price();
    if (seized > collateralOf[user]) seized = collateralOf[user]; // bad debt: nothing more to take

    _reduceDebt(user, repayAmount, debt);
    collateralOf[user] -= seized;
    debtToken.transferFrom(msg.sender, address(this), repayAmount);
    collateral.transfer(msg.sender, seized);
    emit Liquidate(msg.sender, user, repayAmount, seized);
}
```

Step by step: first the interest is brought up to date. If the health factor is not below 1, it reverts. Then it checks that the repayment is no more than half the debt (the close factor). The collateral the liquidator takes is `repayAmount × 1.05 / price`. If the remaining collateral is less than that, it takes whatever remains (we will see what that means). Then the debt is reduced, the collateral moves and the liquidator pays the USDX.

The result of that scenario in the test:

```
$ forge test --mt test_PriceDropLiquidation -vv
  health at 100 1142857142857142857
  health at 85  971428571428571428
  seized DEMO   4323529411764705882
  worth USDX    367499999999999999970
  debt left     350000000000000000000
  DEMO left     5676470588235294118
  health after  1102857142857142857
```

- **`health at 100` and `health at 85`:** 1.14 (healthy) and 0.97 (liquidatable). The same calculation as above: 1,000 × 0.8 / 700 and 850 × 0.8 / 700.
- **`seized DEMO`:** the liquidator paid 350 USDX (the close factor's maximum, half of 700) and took 4.32 DEMO.
- **`worth USDX`:** 4.32 DEMO at a price of 85 is worth 367.50 USDX. So the liquidator paid 350 and received 367.50: the 5 percent bonus, which is the reason anyone bothers. (The last digits are `…99970`, not exactly 367.50, because of rounding.)
- **`debt left`, `DEMO left`:** Alice owes 350 and has 5.68 DEMO left.
- **`health after`:** 1.10, so Alice is healthy again.

The close factor stops one liquidator from taking everything at a discount when a smaller repayment is enough.

There is one bad case. Once the collateral is worth less than the debt, no liquidation can make the loan whole, and the rest is **bad debt**: the lenders' loss. The line `if (seized > collateralOf[user])` in the code shows it: you cannot take more than there is. That is why prices must be fresh and liquidators must exist.

## The test suite

```
$ forge test --mc LendingMarketTest
[PASS] testFuzz_BorrowRespectsLimit(uint256,uint256) (runs: 256, μ: 207037, ~: 187636)
[PASS] testFuzz_LiquidationOnlyWhenUnhealthy(uint256) (runs: 256, μ: 315941, ~: 295585)
[PASS] test_BorrowLimit() (gas: 276538)
[PASS] test_CloseFactor() (gas: 270084)
[PASS] test_HealthyCannotBeLiquidated() (gas: 263768)
[PASS] test_InterestAccrues() (gas: 12671712)
[PASS] test_PriceDropLiquidation() (gas: 490707)
Ran 1 test suite in 69.27ms (52.28ms CPU time): 7 tests passed, 0 failed, 0 skipped (7 total tests)
(trimmed)
```

(The `μ` and `~` numbers and the run time differ a little on each fuzz run, because the inputs are random.)

The first fuzz test tries random collateral and borrow amounts: a borrow over the limit must revert, and anything that went through must start with health of at least 1. The second sets a random price between 1 and 200 and checks that liquidation succeeds exactly when health is below 1 (here, a price below 87.5).

## The price is a placeholder

Everything above trusts the {{< term "oracle" "oracle" >}}, `oracle.price()`: the source that tells the contract what DEMO costs. In this post the price comes from `PriceFeed`, a contract where the owner types the number in. That is fine for tests and wrong for real money: whoever controls the price controls every liquidation and every borrow limit. The next post replaces it, and first shows what goes wrong with the obvious replacement.

## Design rules

- **Keep a gap between the borrow limit and the liquidation threshold.**
- **Round debt up and collateral value down.** Rounding must favour the protocol, never the borrower.
- **Store scaled debt and one index.** Never loop over borrowers.
- **Liquidation must stay profitable after gas,** or nobody runs it and bad debt grows.
- **The oracle is the most trusted input in the whole contract.**

## Exercise

1. Add a test where only interest, with no price change, pushes Alice below 1. How long does it take?
2. Make the price fall to 70 and show the bad debt that remains.
3. Add `supply` with interest-bearing shares for lenders, using the same index idea.

## What's next

The next post is "Oracles and price manipulation": every liquidation rests on one number, and there we see what happens if someone moves it.
