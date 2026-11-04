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

اگر به یک گروفروشی بروید و گوشی‌تان را گرو بگذارید، گروفروش هویت شما را نمی‌پرسد. گوشی‌ای که ارزشش بیشتر از پولی است که می‌دهد برایش کافی است. اگر پول را پس ندادید، گوشی را می‌فروشد و از آن حقش را برمی‌دارد.

یک قرارداد هوشمند در موقعیت گروفروش است، با یک فرق: نمی‌تواند هویت کسی را بررسی کند، به دادگاه برود یا نامه بفرستد. تنها کاری که از دستش برمی‌آید این است که چیزی با ارزش‌تر از وام نگه دارد، و پیش از آنکه وام از وثیقه بیشتر بیرزد، وثیقه را بفروشد. [AMM مقاله‌ی قبل](/fa/posts/bc-amm-constant-product/) جای order book را گرفت؛ این‌جا نوبت کارمند وام است.

اسم این کار {{< term "overcollateralization" "overcollateralization" >}} است، یعنی وثیقه‌ی بیشتر از وام. در این مقاله یک بازار کوچک وام در همان پروژه‌ی Foundry می‌سازم: DEMO را وثیقه می‌گذارید، USDX قرض می‌گیرید (هر دو [DemoToken](/fa/posts/bc-erc20-erc721/)‌اند)، بهره می‌دهید، و اگر قیمت بیفتد liquidate می‌شوید. تست‌ها از `vm.warp` و fuzz [مقاله‌ی تست](/fa/posts/bc-foundry-testing-fuzzing/) استفاده می‌کنند.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی مقاله‌ی قبل را در یک پوشه‌ی محلی تازه کپی کردم و `src/PriceFeed.sol`، `src/LendingMarket.sol` و تستشان را اضافه کردم. سمت وام‌دهنده‌ها (سهم سپرده، نرخ وابسته به میزان استفاده) حذف شده و تست USDX را مستقیم در بازار mint می‌کند. قرارداد آموزشی است و audit نشده. این مقاله توصیه‌ی مالی نیست.

## وثیقه، سقف وام و health factor

اول یک مثال ساده، بدون کد. این عددها برای مثال ساخته‌شده‌اند، ولی با دمویی که پایین‌تر اجرا می‌کنیم یکی‌اند. ده DEMO دارید و هر DEMO برابر ۱۰۰ USDX است، پس وثیقه‌ی شما ۱٬۰۰۰ USDX می‌ارزد. بازار اجازه نمی‌دهد همه‌اش را وام بگیرید: فقط ۷۵ درصد، یعنی ۷۵۰ USDX. این نسبت در قرارداد چهار عدد ثابت است:

```solidity
uint256 public constant COLLATERAL_FACTOR = 0.75e18; // borrow up to 75% of collateral value
uint256 public constant LIQUIDATION_THRESHOLD = 0.8e18; // liquidatable once debt > 80% of value
uint256 public constant CLOSE_FACTOR = 0.5e18; // at most 50% of a debt repaid per liquidation
uint256 public constant LIQUIDATION_BONUS = 1.05e18; // liquidator gets 5% extra collateral
```

- **`COLLATERAL_FACTOR`:** سقف وام: ۷۵ درصد ارزش وثیقه.
- **`LIQUIDATION_THRESHOLD`:** اگر بدهی از ۸۰ درصد ارزش وثیقه بیشتر شود، هر کسی می‌تواند وام را liquidate کند، یعنی بخشی از آن را بپردازد و در عوض وثیقه را بردارد.
- **`CLOSE_FACTOR`:** در هر liquidation حداکثر نیمی از بدهی را می‌شود پرداخت.
- **`LIQUIDATION_BONUS`:** کسی که liquidate می‌کند ۵ درصد بیشتر از آنچه پرداخته وثیقه می‌گیرد. این پاداش انگیزه‌ی او است.

فاصله‌ی ۷۵ تا ۸۰ درصد عمدی است: وام تازه نباید با یک تکان کوچک قیمت یا یک ثانیه بهره، در بلاک بعد قابل liquidation باشد.

برای اینکه ببینیم وضعیت یک وام چقدر سالم است، یک عدد لازم داریم. {{< term "health-factor" "health factor" >}} وضعیت را خلاصه می‌کند:

```solidity
function healthFactor(address user) public view returns (uint256) {
    uint256 debt = debtOf(user);
    if (debt == 0) return type(uint256).max;
    return collateralValue(user) * LIQUIDATION_THRESHOLD / debt;
}
```

یعنی ارزش وثیقه ضرب در ۰٫۸، تقسیم بر بدهی. اگر عدد بالای ۱ باشد (در کد `1e18`، چون عددها با ۱۸ رقم اعشار ذخیره می‌شوند) وام امن است و پایین آن هر کسی می‌تواند liquidate کند. برای ۱۰ DEMO و وام دقیقاً ۷۵۰:

```
$ forge test --mt test_BorrowLimit -vv
  health at the limit 1066666666666666666
```

این ۱٫۰۶۶۶ همان ۱٬۰۰۰ × ۰٫۸ / ۷۵۰ است. وامی که دقیقاً روی سقف گرفته شده هنوز از ۱ بالاتر است، و این همان حاشیه‌ی امنیتی بالاست. ۷۵۱ USDX هم اصلاً داده نمی‌شود: تراکنش با `ExceedsBorrowLimit(751e18, 750e18)` برمی‌گردد.

## بهره با یک index

وام بهره دارد: هر ثانیه بدهی کمی بیشتر می‌شود. ولی قرارداد نمی‌تواند هر ثانیه سراغ همه‌ی وام‌گیرنده‌ها برود و بدهی هرکدام را به‌روز کند؛ این روی زنجیره غیرممکن (و گران) است. راه حل یک ایده‌ی ساده است: همه‌ی بدهی‌ها با یک ضریب رشد می‌کنند، پس فقط همان ضریب را نگه می‌داریم.

مثال (عددهای ساختگی): فرض کنید ضریب الان ۱٫۰۲ است و شما ۵۰۰ USDX قرض می‌گیرید. قرارداد `500 / 1.02 ≈ 490.2` را ذخیره می‌کند؛ اسمش «بدهی scaled» است. بعداً که ضریب به ۱٫۱۰ رسید، بدهی شما ۴۹۰٫۲ × ۱٫۱۰ ≈ ۵۳۹٫۲ است. برای هیچ وام‌گیرنده‌ای لازم نبود چیزی عوض شود؛ فقط ضریب جلو رفت.

در کد:

```solidity
function currentIndex() public view returns (uint256) {
    uint256 dt = block.timestamp - lastAccrual;
    return borrowIndex + borrowIndex * ratePerSecond * dt / WAD;
}

function debtOf(address user) public view returns (uint256) {
    return ceilDiv(scaledDebtOf[user] * currentIndex(), WAD); // debt rounds up
}
```

{{< term "borrow-index" "borrowIndex" >}} از 1e18 شروع می‌شود و می‌گوید یک واحدِ قرض‌گرفته‌شده در ابتدا الان چقدر می‌ارزد. `currentIndex` از زمان آخرین به‌روزرسانی تا الان بهره‌ی ثانیه‌ای را به آن اضافه می‌کند. هر فراخوانی `accrue()` ضریب را برای همه جلو می‌برد، با هزینه‌ای ثابت (O(1)) و بدون حلقه روی وام‌گیرنده‌ها. این همان ایده‌ی سهم LP در مقاله‌ی قبل است: سهمی از چیزی که رشد می‌کند را نگه دارید، نه خود مقدار را.

برای امتحان، Alice با بهره‌ی سالانه‌ی ۱۰ درصد ۵۰۰ USDX قرض می‌گیرد و ساعت یک سال جلو می‌رود. یک بار بدون اینکه کسی به بازار دست بزند، و یک بار با `accrue()` در هر روز:

```
$ forge test --mt test_InterestAccrues -vv
  debt, 1 accrual   549999999994064000000
  debt, 365 accruals 552577890801573687000
  index              1105155781603147374
```

- **`1 accrual`:** بدهی ۵۴۹٫۹۹۹۹۹۹۹۹۹۴ است، یعنی ۵۰۰ به‌علاوه‌ی ۱۰ درصد، بهره‌ی ساده.
- **`365 accruals`:** ۵۵۲٫۵۸. چون هر روز بهره به ضریب اضافه شده و روز بعد روی آن هم بهره آمده، بهره مرکب شده و بیشتر درآمده.
- **`index`:** ضریب بعد از یک سال، ۱٫۱۰۵۱۵۵.

نرخ ثانیه‌ای `0.1e18 / 365 days` است که به 3170979198 بریده می‌شود؛ برای همین عدد اول به‌اندازه‌ی ۰٫۰۰۰۰۰۰۰۰۰۵۹۳۶ از ۵۵۰ کمتر است. بازارهای واقعی دقیق‌تر حساب می‌کنند و نرخ را از میزان استفاده می‌گیرند، ولی الگوی index همین است.

## liquidation

حالا قلب ماجرا. فرض کنید Alice ۱۰ DEMO دارد و ۷۰۰ USDX قرض گرفته است. با قیمت ۱۰۰، وثیقه ۱٬۰۰۰ می‌ارزد و وام سالم است. بعد DEMO ۱۵ درصد می‌افتد و می‌شود ۸۵. حالا وثیقه ۸۵۰ می‌ارزد، و ۷۰۰ از ۸۰ درصد ۸۵۰ (یعنی ۶۸۰) بیشتر است: وام ناسالم است. بازار اجازه می‌دهد هر کسی بخشی از بدهی را بپردازد و وثیقه را با تخفیف بردارد. به این کار {{< term "liquidation" "liquidation" >}} می‌گویند. بدون آن، اگر قیمت باز هم می‌افتاد، بدهی از کل وثیقه بیشتر می‌شد و ضررش به گردن وام‌دهنده‌ها می‌افتاد.

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

قدم‌به‌قدم: اول بهره به‌روز می‌شود. اگر health factor از ۱ کمتر نباشد، revert. بعد چک می‌کند مبلغ پرداختی از نصف بدهی بیشتر نباشد (close factor). مقدار وثیقه‌ای که liquidator می‌گیرد `repayAmount × 1.05 / قیمت` است. اگر وثیقه‌ی باقی‌مانده از این کمتر باشد، همان باقی‌مانده را می‌گیرد (بعداً می‌بینیم یعنی چه). بعد بدهی کم می‌شود، وثیقه جابه‌جا می‌شود و liquidator USDX را می‌دهد.

نتیجه‌ی آن سناریو در تست:

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

- **`health at 100` و `health at 85`:** ۱٫۱۴ (سالم) و ۰٫۹۷ (قابل liquidation). همان محاسبه‌ی بالا: ۱٬۰۰۰ × ۰٫۸ / ۷۰۰ و ۸۵۰ × ۰٫۸ / ۷۰۰.
- **`seized DEMO`:** liquidator ۳۵۰ USDX پرداخت (حداکثر close factor، نصف ۷۰۰) و ۴٫۳۲ DEMO گرفت.
- **`worth USDX`:** ۴٫۳۲ DEMO با قیمت ۸۵ برابر ۳۶۷٫۵۰ USDX است. یعنی liquidator ۳۵۰ داد و ۳۶۷٫۵۰ گرفت: همان ۵ درصد پاداش، دلیل اینکه کسی زحمتش را بکشد. (آخرین رقم‌ها `…99970` شد، نه دقیقاً ۳۶۷٫۵۰، به‌خاطر گرد کردن.)
- **`debt left`، `DEMO left`:** Alice ۳۵۰ بدهی دارد و ۵٫۶۸ DEMO برایش مانده.
- **`health after`:** ۱٫۱۰ است، پس Alice دوباره سالم است.

close factor نمی‌گذارد یک liquidator وقتی پرداخت کمتر کافی است همه‌چیز را با تخفیف ببرد.

یک حالت بد هم هست. وقتی ارزش وثیقه از بدهی کمتر شود، هیچ liquidationی وام را کامل نمی‌کند و باقی‌اش **bad debt** است: ضرر وام‌دهنده‌ها. همان خط `if (seized > collateralOf[user])` در کد این را نشان می‌دهد: چیزی بیشتر از آنچه هست نمی‌شود برداشت. برای همین قیمت باید تازه باشد و liquidator باید وجود داشته باشد.

## مجموعه‌ی تست

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

(عددهای `μ` و `~` و زمان اجرا در هر اجرای fuzz کمی فرق می‌کنند، چون ورودی‌ها تصادفی‌اند.)

fuzz اول مقدار وثیقه و وام تصادفی امتحان می‌کند: وام بالای سقف باید revert شود و هر وامی که رد شد باید با health دست‌کم ۱ شروع کند. دومی یک قیمت تصادفی بین ۱ و ۲۰۰ می‌گذارد و چک می‌کند liquidation دقیقاً وقتی موفق است که health زیر ۱ باشد (اینجا یعنی قیمت زیر ۸۷٫۵).

## قیمت فعلاً موقت است

همه‌ی این‌ها به {{< term "oracle" "oracle" >}}، یعنی `oracle.price()`، اعتماد دارد: منبعی که به قرارداد می‌گوید قیمت DEMO چند است. در این مقاله قیمت از `PriceFeed` می‌آید، قراردادی که مالکش عدد را دستی وارد می‌کند. برای تست خوب است و برای پول واقعی غلط: هر کس قیمت را کنترل کند، liquidationها و سقف وام را کنترل می‌کند. مقاله‌ی بعد آن را عوض می‌کند و اول نشان می‌دهد جایگزین بدیهی چطور خراب می‌شود.

## قاعده‌های طراحی

- **بین سقف وام و آستانه‌ی liquidation فاصله بگذارید.**
- **بدهی را رو به بالا و ارزش وثیقه را رو به پایین گرد کنید.** گرد کردن باید به نفع پروتکل باشد، نه وام‌گیرنده.
- **بدهی scaled و یک index ذخیره کنید.** هرگز روی وام‌گیرنده‌ها حلقه نزنید.
- **liquidation باید بعد از gas هم سود بدهد،** وگرنه کسی اجرایش نمی‌کند و bad debt بزرگ می‌شود.
- **oracle مورد اعتمادترین ورودی کل قرارداد است.**

## تمرین

۱. تستی بنویسید که فقط بهره، بدون تغییر قیمت، Alice را زیر ۱ ببرد. چقدر طول می‌کشد؟
۲. قیمت را به ۷۰ برسانید و bad debtی را که می‌ماند نشان دهید.
۳. برای وام‌دهنده‌ها `supply` با سهم بهره‌دار اضافه کنید، با همان ایده‌ی index.

## قدم بعدی

مقاله‌ی بعد «Oracle و دستکاری قیمت» است: همه‌ی liquidationها به یک عدد تکیه دارند، و آنجا می‌بینیم اگر کسی آن عدد را جابه‌جا کند چه می‌شود.
