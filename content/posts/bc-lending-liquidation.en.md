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

A contract cannot check identity, call a court or send a letter. All it can do is hold something worth more than the loan, and sell it before the loan is worth more than the collateral. After [the AMM](/posts/bc-amm-constant-product/) replaced the order book, this post replaces the loan officer.

That is {{< term "overcollateralization" "overcollateralization" >}}. I build a minimal market in the same Foundry project: deposit DEMO, borrow USDX (both [DemoTokens](/posts/bc-erc20-erc721/)), pay interest, get liquidated. Tests use `vm.warp` and fuzzing from [the Foundry testing post](/posts/bc-foundry-testing-fuzzing/).

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project into a new local folder and added `src/PriceFeed.sol`, `src/LendingMarket.sol` and their test. The lenders' side (supply shares, a rate that follows utilization) is left out: the test mints the USDX straight into the market. A teaching contract, not audited.

## Three numbers

```solidity
uint256 public constant COLLATERAL_FACTOR = 0.75e18; // borrow up to 75% of collateral value
uint256 public constant LIQUIDATION_THRESHOLD = 0.8e18; // liquidatable once debt > 80% of value
uint256 public constant CLOSE_FACTOR = 0.5e18; // at most 50% of a debt repaid per liquidation
uint256 public constant LIQUIDATION_BONUS = 1.05e18; // liquidator gets 5% extra collateral
```

With 10 DEMO at 100 USDX each, the collateral is worth 1,000 and the borrow limit is 750. The gap between 75% and 80% is deliberate: a new loan cannot be liquidatable on the next block because of a small price move or one second of interest.

The {{< term "health-factor" "health factor" >}} summarizes a position:

```solidity
function healthFactor(address user) public view returns (uint256) {
    uint256 debt = debtOf(user);
    if (debt == 0) return type(uint256).max;
    return collateralValue(user) * LIQUIDATION_THRESHOLD / debt;
}
```

Above 1e18 the position is safe, below it anyone may liquidate. Borrowing exactly 750 gives 1,000 × 0.8 / 750:

```
$ forge test --mt test_BorrowLimit -vv
  health at the limit 1066666666666666666
```

751 reverts with `ExceedsBorrowLimit(751e18, 750e18)`.

## Interest with an index

Updating every borrower every second is impossible on-chain. The market keeps one global number instead:

```solidity
function currentIndex() public view returns (uint256) {
    uint256 dt = block.timestamp - lastAccrual;
    return borrowIndex + borrowIndex * ratePerSecond * dt / WAD;
}

function debtOf(address user) public view returns (uint256) {
    return ceilDiv(scaledDebtOf[user] * currentIndex(), WAD); // debt rounds up
}
```

{{< term "borrow-index" "borrowIndex" >}} starts at 1e18 and says what one unit borrowed at the start is worth now. Borrowing 500 when the index is 1.02 stores `500 / 1.02` as scaled debt; later debt is scaled debt times the current index. Any call to `accrue()` moves the index for everybody in O(1). It is the same idea as LP shares: store a share of something growing, not an amount.

Alice borrows 500 USDX at 10% a year, then the clock jumps a year. Once with nobody touching the market, once with an `accrue()` every day:

```
$ forge test --mt test_InterestAccrues -vv
  debt, 1 accrual   549999999994064000000
  debt, 365 accruals 552577890801573687000
  index              1105155781603147374
```

One accrual is simple interest; 365 accruals compound daily. The rate per second is `0.1e18 / 365 days`, truncated to 3170979198, which is why the first number is 0.000000005936 short of 550. Real markets compound more carefully and pick rates from utilization; the index pattern stays the same.

## Liquidation

A {{< term "liquidation" "liquidation" >}} lets anyone repay part of an unhealthy loan and take collateral at a discount:

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

Alice holds 10 DEMO and owes 700 USDX. DEMO drops from 100 to 85:

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

The liquidator paid 350 USDX (the close factor's maximum) and got 4.32 DEMO worth 367.50: the 5% bonus is the reason anyone bothers. Alice is healthy again at 1.10 and keeps 5.68 DEMO. The close factor stops one liquidator from taking everything at a discount when a smaller repayment is enough.

Once the collateral is worth less than the debt, no liquidation can make the loan whole and the rest is bad debt: the lenders' loss. That is why prices must be fresh and liquidators must exist.

## The test suite

```
$ forge test --mc LendingMarketTest
[PASS] testFuzz_BorrowRespectsLimit(uint256,uint256) (runs: 256, μ: 207880, ~: 205742)
[PASS] testFuzz_LiquidationOnlyWhenUnhealthy(uint256) (runs: 256, μ: 311712, ~: 295585)
[PASS] test_BorrowLimit() (gas: 276538)
[PASS] test_CloseFactor() (gas: 270084)
[PASS] test_HealthyCannotBeLiquidated() (gas: 263768)
[PASS] test_InterestAccrues() (gas: 12671712)
[PASS] test_PriceDropLiquidation() (gas: 490707)
Ran 1 test suite in 71.65ms (52.37ms CPU time): 7 tests passed, 0 failed, 0 skipped (7 total tests)
(trimmed)
```

The first fuzz test tries random collateral and borrow amounts: a borrow over the limit must revert, and anything that went through must start with health ≥ 1. The second sets a random price between 1 and 200 and checks that liquidation succeeds exactly when health is below 1 (here, below 87.5).

## The price is a placeholder

Everything above trusts the {{< term "oracle" "oracle" >}}, `oracle.price()`. In this post it comes from `PriceFeed`, a contract where the owner types the number in. That is fine for tests and wrong for real money: whoever controls the price controls every liquidation and every borrow limit. The next post replaces it, and first shows what goes wrong with the obvious replacement.

## Design rules

- Keep a gap between the borrow limit and the liquidation threshold.
- Round debt up and collateral value down. Rounding must favour the protocol, never the borrower.
- Store scaled debt and one index. Never loop over borrowers.
- Liquidation must stay profitable after gas, or nobody runs it and bad debt grows.
- The oracle is the most trusted input in the whole contract.

## Exercise

1. Add a test where only interest, with no price change, pushes Alice below 1. How long does it take?
2. Make the price fall to 70 and show the bad debt that remains.
3. Add `supply` with interest-bearing shares for lenders, using the same index idea.

## What's next

Next post: **Oracles and price manipulation**.
