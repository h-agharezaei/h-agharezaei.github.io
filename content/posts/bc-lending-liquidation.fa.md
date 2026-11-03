+++
date = '2026-11-23T18:00:00+03:30'
draft = false
title = 'وام‌دهی، وثیقه و liquidation'
description = 'یک بازار وام با وثیقه‌ی بیشتر از وام در Solidity: سقف وام، بهره با index ثانیه‌ای، health factor و liquidation با پاداش، تست‌شده با Foundry.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "lending", "foundry"]
cover = { image = "/images/covers/bc-lending-liquidation.fa.png", alt = "وام‌دهی، وثیقه و liquidation", hiddenInSingle = true }
+++

قرارداد نمی‌تواند هویت کسی را بررسی کند یا به دادگاه برود. فقط می‌تواند چیزی باارزش‌تر از وام نگه دارد و پیش از آن‌که وام از وثیقه بیشتر بیرزد، آن را بفروشد. [AMM](/fa/posts/bc-amm-constant-product/) جای order book را گرفت؛ این‌جا نوبت کارمند وام است.

اسم این کار {{< term "overcollateralization" "overcollateralization" >}} است. یک بازار کوچک در همان پروژه‌ی Foundry می‌سازم: DEMO را وثیقه بگذارید، USDX قرض بگیرید (هر دو [DemoToken](/fa/posts/bc-erc20-erc721/))، بهره بدهید و liquidate شوید. تست‌ها از `vm.warp` و fuzz [پست تست](/fa/posts/bc-foundry-testing-fuzzing/) استفاده می‌کنند.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل را در یک پوشه‌ی محلی تازه کپی کردم و `src/PriceFeed.sol`، `src/LendingMarket.sol` و تستشان را اضافه کردم. سمت وام‌دهنده‌ها (سهم سپرده، نرخ وابسته به میزان استفاده) حذف شده و تست USDX را مستقیم در بازار mint می‌کند. قرارداد آموزشی است و audit نشده.

## سه عدد

```solidity
uint256 public constant COLLATERAL_FACTOR = 0.75e18; // borrow up to 75% of collateral value
uint256 public constant LIQUIDATION_THRESHOLD = 0.8e18; // liquidatable once debt > 80% of value
uint256 public constant CLOSE_FACTOR = 0.5e18; // at most 50% of a debt repaid per liquidation
uint256 public constant LIQUIDATION_BONUS = 1.05e18; // liquidator gets 5% extra collateral
```

با ۱۰ DEMO به قیمت ۱۰۰ USDX، وثیقه ۱٬۰۰۰ می‌ارزد و سقف وام ۷۵۰ است. فاصله‌ی ۷۵ تا ۸۰ درصد عمدی است: وام تازه نباید با یک تکان کوچک قیمت یا یک ثانیه بهره، در بلاک بعد قابل liquidation باشد.

{{< term "health-factor" "health factor" >}} وضعیت یک وام را خلاصه می‌کند:

```solidity
function healthFactor(address user) public view returns (uint256) {
    uint256 debt = debtOf(user);
    if (debt == 0) return type(uint256).max;
    return collateralValue(user) * LIQUIDATION_THRESHOLD / debt;
}
```

بالای 1e18 امن است و پایین آن هر کسی می‌تواند liquidate کند. قرض گرفتن دقیقاً ۷۵۰ یعنی ۱٬۰۰۰ × ۰٫۸ / ۷۵۰:

```
$ forge test --mt test_BorrowLimit -vv
  health at the limit 1066666666666666666
```

۷۵۱ با `ExceedsBorrowLimit(751e18, 750e18)` برمی‌گردد.

## بهره با index

به‌روز کردن همه‌ی وام‌گیرنده‌ها در هر ثانیه روی زنجیره ممکن نیست؛ بازار یک عدد سراسری نگه می‌دارد:

```solidity
function currentIndex() public view returns (uint256) {
    uint256 dt = block.timestamp - lastAccrual;
    return borrowIndex + borrowIndex * ratePerSecond * dt / WAD;
}

function debtOf(address user) public view returns (uint256) {
    return ceilDiv(scaledDebtOf[user] * currentIndex(), WAD); // debt rounds up
}
```

{{< term "borrow-index" "borrowIndex" >}} از 1e18 شروع می‌شود و می‌گوید یک واحدِ قرض‌گرفته‌شده در ابتدا الان چقدر می‌ارزد. قرض گرفتن ۵۰۰ وقتی index برابر ۱٫۰۲ است، `500 / 1.02` را به‌عنوان بدهی scaled ذخیره می‌کند؛ بعداً بدهی برابر بدهی scaled ضرب در index فعلی است. هر فراخوانی `accrue()` با O(1) index را برای همه جلو می‌برد. همان ایده‌ی سهم LP است: سهمی از چیزی که رشد می‌کند را نگه دارید، نه مقدار را.

Alice با بهره‌ی سالانه‌ی ۱۰ درصد، ۵۰۰ USDX قرض می‌گیرد و ساعت یک سال جلو می‌رود؛ یک بار بی‌آن‌که کسی به بازار دست بزند، یک بار با `accrue()` هر روز:

```
$ forge test --mt test_InterestAccrues -vv
  debt, 1 accrual   549999999994064000000
  debt, 365 accruals 552577890801573687000
  index              1105155781603147374
```

یک accrual یعنی بهره‌ی ساده؛ ۳۶۵ accrual یعنی بهره‌ی مرکب روزانه. نرخ ثانیه‌ای `0.1e18 / 365 days` است که به 3170979198 بریده می‌شود؛ برای همین عدد اول 0.000000005936 کمتر از ۵۵۰ است. بازارهای واقعی دقیق‌تر حساب می‌کنند و نرخ را از میزان استفاده می‌گیرند، ولی الگوی index همین است.

## liquidation

{{< term "liquidation" "liquidation" >}} به هر کسی اجازه می‌دهد بخشی از یک وام ناسالم را بپردازد و وثیقه را با تخفیف بردارد:

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

Alice ۱۰ DEMO دارد و ۷۰۰ USDX بدهکار است. DEMO از ۱۰۰ به ۸۵ می‌افتد:

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

liquidator ۳۵۰ USDX (حداکثرِ close factor) پرداخت و ۴٫۳۲ DEMO به ارزش ۳۶۷٫۵۰ گرفت: پاداش ۵ درصدی دلیل این است که کسی زحمتش را بکشد. Alice با ۱٫۱۰ دوباره سالم است و ۵٫۶۸ DEMO برایش می‌ماند. close factor نمی‌گذارد یک liquidator وقتی پرداخت کمتر کافی است همه چیز را با تخفیف ببرد.

وقتی ارزش وثیقه از بدهی کمتر شود، هیچ liquidationی وام را کامل نمی‌کند و باقی‌اش bad debt است: ضرر وام‌دهنده‌ها. برای همین قیمت باید تازه باشد و liquidator باید وجود داشته باشد.

## مجموعه‌ی تست

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

fuzz اول مقدار وثیقه و وام تصادفی امتحان می‌کند: وام بالای سقف باید revert شود و هر وامی که رد شد باید با health دست‌کم ۱ شروع کند. دومی یک قیمت تصادفی بین ۱ و ۲۰۰ می‌گذارد و چک می‌کند liquidation دقیقاً وقتی موفق است که health زیر ۱ باشد (اینجا قیمت زیر ۸۷٫۵).

## قیمت فعلاً موقت است

همه‌ی این‌ها به {{< term "oracle" "oracle" >}}، یعنی `oracle.price()`، اعتماد دارد. در این پست قیمت از `PriceFeed` می‌آید، قراردادی که مالکش عدد را دستی وارد می‌کند. برای تست خوب است و برای پول واقعی غلط: هر کس قیمت را کنترل کند، liquidationها و سقف وام را کنترل می‌کند. پست بعد آن را عوض می‌کند و اول نشان می‌دهد جایگزینِ بدیهی چطور خراب می‌شود.

## قاعده‌های طراحی

- بین سقف وام و آستانه‌ی liquidation فاصله بگذارید.
- بدهی را رو به بالا و ارزش وثیقه را رو به پایین گرد کنید. گرد کردن باید به نفع پروتکل باشد، نه وام‌گیرنده.
- بدهی scaled و یک index ذخیره کنید. هرگز روی وام‌گیرنده‌ها حلقه نزنید.
- liquidation باید بعد از gas هم سود بدهد، وگرنه کسی اجرایش نمی‌کند و bad debt بزرگ می‌شود.
- oracle مورد اعتمادترین ورودی کل قرارداد است.

## تمرین

۱. تستی بنویسید که فقط بهره، بدون تغییر قیمت، Alice را زیر ۱ ببرد. چقدر طول می‌کشد؟
۲. قیمت را به ۷۰ برسانید و bad debtی را که می‌ماند نشان دهید.
۳. برای وام‌دهنده‌ها `supply` با سهم بهره‌دار اضافه کنید، با همان ایده‌ی index.

## قدم بعدی

پست بعد: **Oracle و دستکاری قیمت**.
