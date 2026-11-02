+++
date = '2027-07-03T10:00:00+03:30'
draft = false
title = 'AMM و فرمول constant product'
description = 'یک AMM با فرمول constant product در Solidity: x*y=k، سهم LP، کارمزد ۰٫۳ درصد، گرد کردن به نفع استخر، جدول price impact، حد slippage و تست invariant.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "amm", "foundry", "go"]
cover = { image = "/images/covers/bc-amm-constant-product.fa.png", alt = "AMM و فرمول constant product", hiddenInSingle = true }
+++

پست قبلی، [کیف‌پول HD: BIP-32، BIP-39 و BIP-44 با Rust](/fa/posts/bc-hd-wallets-rust/)، درباره‌ی کلیدها بود. حالا سری وارد DeFi می‌شود: قراردادهایی که توکن نگه می‌دارند و معامله می‌کنند.

صرافی معمولاً order book دارد و موتور تطبیق، خریدار و فروشنده را جفت می‌کند. روی زنجیره هر سفارش و لغو gas می‌خورد و منتظر بلاک می‌ماند. {{< term "amm" "AMM" >}} (بازارساز خودکار) order book را کنار می‌گذارد: یک قرارداد دو توکن نگه می‌دارد و یک فرمول قیمت را تعیین می‌کند. یک نسخه‌ی کوچک برای دو [توکن ERC-20](/fa/posts/bc-erc20-erc721/) می‌سازم، مثل [پست تست با Foundry](/fa/posts/bc-foundry-testing-fuzzing/) تستش می‌کنم و حسابش را با یک برنامه‌ی کوچک Go چک می‌کنم.

> اجرا با Foundry 1.8.7، solc 0.8.38 و Go 1.27.3 روی macOS (arm64). دمو یک پروژه‌ی محلی Foundry است که فقط forge-std دارد؛ `DemoToken` بدون تغییر از پست توکن‌ها کپی شده. طراحی، تا جایی که من می‌فهمم، ساده‌شده‌ی Uniswap v2 است. قرارداد آموزشی است و audit نشده.

## x * y = k

استخر موجودی `x` از token0 (DEMO) و `y` از token1 (USDX، یک توکن دلاری نمایشی) دارد. هر swap باید حاصل‌ضرب `x * y` را دست‌کم همان‌جا که بود نگه دارد. این قاعده‌ی {{< term "constant-product" "constant product" >}} است. `dx` بدهید و `dy` بگیرید:

```
(x + dx) * (y - dy) = x * y   =>   dy = y * dx / (x + dx)
```

قیمت همان `y / x` است و هر معامله تکانش می‌دهد: خرید DEMO از موجودی DEMO کم می‌کند، پس DEMO بعدی گران‌تر است. وقتی `x` به صفر نزدیک شود قیمت به بی‌نهایت می‌رود، پس استخر خالی نمی‌شود.

## استخر

تأمین‌کننده‌های نقدینگی هر دو توکن را در {{< term "liquidity-pool" "استخر نقدینگی" >}} می‌گذارند و سهم می‌گیرند:

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

۱۰۰۰ سهمی که در `address(0)` قفل می‌شود، تا جایی که من دلیل Uniswap v2 را می‌فهمم، باد کردن ارزش یک سهم را گران می‌کند تا سهم واریزکننده‌های بعدی به صفر گرد نشود. `removeLiquidity` مقدار `shares * reserve / totalShares` را با گرد کردن رو به پایین می‌پردازد.

swap:

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

کارمزد یعنی فرمول فقط با ۹۹٫۷ درصد ورودی حساب می‌شود؛ کل ورودی به موجودی اضافه می‌شود، پس ۰٫۳ درصد اضافه برای تأمین‌کننده‌ها می‌ماند. یک تست ۲۰ رفت‌وبرگشت ۱۰٬۰۰۰ USDX انجام می‌دهد؛ بعد alice به‌جای ۱۰۰٬۰۰۰ USDX که گذاشته بود، ۱۰۱٬۰۹۰٫۳۷ برمی‌دارد.

## گرد کردن به نفع استخر

تقسیم صحیح اعشار را می‌اندازد و جهتش اینجا درست است: معامله‌گر کمی کمتر می‌گیرد و `k` بزرگ می‌شود. گرد کردن رو به بالا یک wei می‌بخشد و با موجودی کم، `k` کوچک می‌شود:

```
$ forge test --mt test_RoundingUpWouldBreakK -vv
  out rounded down 2 k after 1000994
  out rounded up   3 k after 999991
```

قاعده‌ی همه‌ی حساب‌های DeFi: به ضرر کسی گرد کنید که چیزی بیرون می‌برد.

## price impact

استخر ۱٬۰۰۰ DEMO و ۱۰۰٬۰۰۰ USDX دارد، پس قیمت لحظه‌ای ۱۰۰ است. برنامه‌ی Go همان فرمول صحیح را با `math/big` حساب می‌کند، همان quoteی که یک backend قبل از فرستادن swap می‌سازد:

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

`test_PriceImpactTable` همین اندازه‌ها را روی استخر واقعی swap می‌کند و همین عددها را log می‌کند. ۰٫۳۰ درصد کارمزد است و بقیه اثر منحنی: خرج کردن کل USDX استخر، میانگین قیمت را دو برابر می‌کند.

## حد slippage و deadline

quote روی وضعیتی که دیدید ساخته می‌شود و swap روی وضعیت لحظه‌ی اجرا؛ در این فاصله تراکنش‌های دیگر می‌رسند. `minAmountOut` بدترین نتیجه‌ی قابل قبول را تعیین می‌کند (تحمل {{< term "slippage" "slippage" >}})، و `deadline` تراکنشی را که ساعت‌ها در [mempool](/fa/posts/bc-mempool-fees/) مانده متوقف می‌کند. در این تست Bob برای ۱۰٬۰۰۰ USDX با تحمل ۰٫۵ درصد quote می‌گیرد و بعد خرید ۲۰٬۰۰۰ USDXیِ eve زودتر اجرا می‌شود:

```
$ forge test --mt test_FrontRunHitsMinOut -vv
[PASS] test_FrontRunHitsMinOut() (gas: 177978)
Logs:
  bob quote  90661089388014913158
  bob would get 63956986828671189740
```

با `minAmountOut = 0` همان swap به‌جای ۹۰٫۶۶ فقط ۶۳٫۹۶ DEMO به Bob می‌داد. خریدن درست قبل از قربانی و فروختن درست بعد از او {{< term "sandwich-attack" "sandwich attack" >}} است؛ `minAmountOut: 0` یعنی دعوت‌نامه. MEV پست خودش را دارد.

## تست invariant

یک handler برای سه بازیگر در هر دو جهت swap می‌کند، نقدینگی اضافه و کم می‌کند و `k` را دور هر swap ثبت می‌کند ({{< term "invariant-testing" "تست invariant" >}}):

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

بعد باگ را عمداً کاشتم: `getAmountOut` رو به بالا گرد کند. runner invariant را شکست و با {{< term "shrinking" "shrinking" >}} دنباله را به یک فراخوانی رساند، یک swap به اندازه‌ی ۳ wei:

```
[FAIL: assertion failed: 1 != 0] invariant_KNeverDecreasesOnSwap
	[Sequence] (original: 4, shrunk: 1)
		sender=0xDD58...DF75 addr=[test/handlers/PoolHandler.sol:PoolHandler]0xD6Bb...FBfF calldata=swap(uint256,bool,uint256) args=[3, true, 3]
(addresses shortened)
```

## چند نکته‌ی مهم

- هیچ swapی را با `minAmountOut = 0` یا deadline دور نفرستید. حداقل را off-chain از یک quote تازه حساب کنید.
- price impact به عمق استخر بستگی دارد. استخر کم‌عمق یعنی معامله‌ی گران.
- هر تقسیم را به نفع استخر گرد کنید و با تست invariant مطمئن شوید.
- استخر موجودی را خودش نگه می‌دارد؛ توکن‌های کارمزد-روی-انتقال آن را خراب می‌کنند.
- قیمت لحظه‌ای `y / x` داخل یک تراکنش به‌راحتی جابه‌جا می‌شود؛ برای پست oracle یادتان بماند.

## تمرین

۱. `getAmountIn` (خروجی دقیق) را اضافه کنید و برای هر تقسیم تصمیم بگیرید به کدام سمت گرد شود.
۲. جدول price impact را روی استخری ده برابر عمیق‌تر اجرا کنید.
۳. در `removeLiquidity` باگ بکارید (گرد کردن رو به بالا) و invariantی بنویسید که آن را بگیرد.

## قدم بعدی

پست بعد: **وام‌دهی، وثیقه و liquidation**.
