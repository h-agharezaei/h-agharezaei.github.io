+++
date = '2026-11-25T18:00:00+03:30'
draft = false
title = 'امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی'
seoTitle = 'امنیت قرارداد: reentrancy و access control'
description = 'امنیت قرارداد در Solidity: reentrancy، callback توکن‌ها، initializer باز، tx.origin و transfer چک‌نشده، با حمله در تست محلی و رفع هر کدام.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "security", "reentrancy", "foundry", "defi"]
cover = { image = "/images/covers/bc-contract-security.fa.png", alt = "امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی", hiddenInSingle = true }
+++

چرا `withdraw` در [اولین قرارداد با Solidity و Foundry](/fa/posts/bc-solidity-first-contract/) موجودی را قبل از فرستادن ETH به‌روز می‌کند؟ شاید فکر کنید ترتیب مهم نیست، چون هر دو خط در یک تراکنش اجرا می‌شوند. ولی مهم است. فرستادن ETH به یک قرارداد، کد آن قرارداد را اجرا می‌کند، و آن کد می‌تواند وسط کار دوباره `withdraw` را صدا بزند، پیش از آنکه موجودی صفر شده باشد.

[Oracle و دستکاری قیمت](/fa/posts/bc-oracles/) یک بازار وام را بدون هیچ باگی شکست داد. این پست درباره‌ی خود باگ‌هاست. چند اشتباه کلاسیک را روی کد خودم، در یک تست محلی Foundry، حمله می‌کنم و هر کدام را درست می‌کنم. [مجوزدهی: RBAC و IDOR](/fa/posts/sec-authorization-rbac-idor/) نسخه‌ی وب بخش access control همین پست است.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل را کپی کردم. قراردادهای عمداً آسیب‌پذیر در `test/vulnerable/` و مهاجم‌ها در `test/helpers/` هستند. کد آموزشی است و audit نشده.

## Reentrancy: صندوقی که دو بار پول می‌دهد

یک مثال از دنیای واقعی: به باجه‌ی بانک می‌روید و می‌گویید «همه‌ی موجودی‌ام را می‌خواهم». صندوقدار شروع می‌کند به شمردن پول. اگر او دفتر را بعد از دادن پول به‌روز کند و شما وسط شمردن دوباره بگویید «همه‌ی موجودی‌ام را می‌خواهم»، دفتر هنوز موجودی کامل را نشان می‌دهد و دوباره پول می‌دهد.

قرارداد زیر دقیقاً همین کار را می‌کند. یک صندوق ساده است که ETH نگه می‌دارد و موجودی هر نفر را در `balanceOf` ثبت می‌کند:

```solidity
function withdraw() external {
    uint256 bal = balanceOf[msg.sender];
    (bool ok,) = msg.sender.call{value: bal}(""); // interaction first...
    if (!ok) revert TransferFailed();
    balanceOf[msg.sender] = 0; // ...effect too late
}
```

اول ETH را می‌فرستد و بعد موجودی را صفر می‌کند. وقتی گیرنده یک قرارداد باشد، فرستادن ETH تابع `receive()` او را اجرا می‌کند. مهاجم در `receive()` دوباره `withdraw()` را صدا می‌زند. موجودی هنوز صفر نشده، پس صندوق دوباره پول می‌دهد، و این بارها تکرار می‌شود. اسم این حمله {{< term "reentrancy" "reentrancy" >}} است، یعنی ورود دوباره به قرارداد پیش از آنکه اولین اجرا تمام شده باشد.

در تست، Alice و Bob هر کدام ۵ ETH واریز می‌کنند و مهاجم ۱ ETH:

```
$ forge test --mt test_VulnerableVaultIsDrained -vv
  vault before    10000000000000000000
  vault after     0
  attacker has    11000000000000000000
  extra rounds    10
```

- **`vault before`:** صندوق ۱۰ ETH از Alice و Bob دارد (اعداد به wei است، یعنی ۱۰ با ۱۸ صفر).
- **`attacker has`:** مهاجم ۱ ETH واریز کرد و ۱۱ ETH بیرون آورد، یعنی کل صندوق، شامل ۱۰ ETH مردم.
- **`extra rounds`:** ده بار از داخل `receive()` دوباره `withdraw` صدا زده شد. هر دور ۱ ETH، چون موجودی مهاجم صفر نمی‌شد.

راه درست ترتیب است. به این ترتیب {{< term "checks-effects-interactions" "checks-effects-interactions" >}} می‌گویند: اول بررسی‌ها، بعد نوشتن state، و فقط در آخر صدا زدن بیرون. وقتی بیرون را صدا می‌زنیم، موجودی از قبل صفر است و ورود دوباره چیزی نمی‌گیرد.

```solidity
function withdraw() external nonReentrant {
    uint256 bal = balanceOf[msg.sender]; // checks
    if (bal == 0) revert NothingToWithdraw();
    balanceOf[msg.sender] = 0; // effects
    (bool ok,) = msg.sender.call{value: bal}(""); // interactions
    if (!ok) revert TransferFailed();
}
```

`nonReentrant` در `src/Security.sol` یک قفل کوچک است: پرچمی در storage که هنگام ورود به تابع ست می‌شود و هنگام خروج پاک می‌شود. تا پرچم ست است، هر ورود دوباره revert می‌کند.

## قفل به‌تنهایی کافی نیست

شاید فکر کنید با قفل دیگر لازم نیست به ترتیب فکر کنیم. این هم درست نیست. `GuardedVault` همان ترتیب غلط را نگه می‌دارد و فقط `withdraw` را قفل می‌کند. ورود دوباره به `withdraw` حالا شکست می‌خورد. ولی صندوق تابع دیگری هم دارد: `move()` که موجودی را به آدرس دیگری منتقل می‌کند و قفل ندارد. مهاجم وسط callback موجودی صفرنشده‌اش را با `move()` به همدستش می‌دهد:

```
$ forge test --mt test_GuardMissesCrossFunction -vv
  deposited       1000000000000000000
  got back        2000000000000000000
  vault after     9000000000000000000
```

مهاجم ۱ ETH گذاشت. خودش در همان `withdraw` یک ETH گرفت، و موجودی که به همدست منتقل کرده بود را همدست هم جداگانه برداشت. جمعاً ۲ ETH برگشت و صندوق به ۹ رسید (۱۱ منهای ۲).

این reentrancy بین‌تابعی است: ورود دوباره نه به همان تابع، بلکه به تابع دیگری که state مشترک دارد. `SafeVault` ترتیب درست دارد و همه‌ی تابع‌های تغییردهنده را قفل می‌کند؛ هر دو مهاجم revert می‌شوند.

نوع سومی هم هست: reentrancy فقط‌خواندنی. قراردادی دیگر وسط callback یک تابع `view` از قرارداد شما را می‌خواند و state نیمه‌کاره می‌بیند. این را نساختم.

## callback داخل توکن‌ها

لازم نیست خودتان ETH بفرستید تا کسی شما را دوباره صدا بزند. `safeTransferFrom` در ERC-721 ([توکن‌ها: ERC-20 و ERC-721](/fa/posts/bc-erc20-erc721/)) روی گیرنده‌ی قرارداد `onERC721Received` را صدا می‌زند تا گیرنده تأیید کند توکن را می‌پذیرد. این هم یک فراخوانی بیرونی است.

یک mint با قاعده‌ی «هر آدرس یک NFT رایگان» را در نظر بگیرید که `claimed` را بعد از این callback ثبت می‌کند. گیرنده داخل callback دوباره claim می‌کند، و از آنجا که هنوز `claimed` ثبت نشده، قبول می‌شود:

```
$ forge test --mt test_CallbackReentersMint -vv
  NFTs for one address: 5
```

یک آدرس به‌جای یک NFT، پنج تا گرفت (مهاجم تست خودش را روی پنج متوقف کرده). رفع، بردن `claimed[msg.sender] = true` به بالای mint است، یعنی همان checks-effects-interactions. تا جایی که می‌دانم توکن‌های ERC-777 حتی در transfer معمولی hook صدا می‌زنند.

## Access control

تا اینجا حمله‌ها پیچیده بودند. نوع بعدی ساده‌تر و شرم‌آورتر است. باگ‌های {{< term "access-control" "access control" >}}، یعنی کنترل اینکه چه کسی اجازه‌ی چه کاری دارد، اغلب یک خط جاافتاده‌اند.

`InitFeed` یک price feed برای بازار وام است. مالکش را در تابع `initialize()` تعیین می‌کند، ولی این تابع بررسی نمی‌کند که قبلاً صدا زده شده یا نه. پس هر کسی هر وقت بخواهد دوباره صدایش می‌زند:

```
$ forge test --mt test_OpenInitializerDrainsMarket -vv
  feed owner is mallory: true
  USDX borrowed against 1 DEMO: 50000000000000000000000
  USDX left in market: 0
```

Mallory خودش را مالک کرد، قیمت DEMO را یک میلیون گذاشت، با یک DEMO وثیقه کل ۵۰٬۰۰۰ USDX بازار را قرض گرفت و بازار خالی شد. رفع یک خط است: `if (owner != address(0)) revert AlreadyInitialized();`. و بهتر آن است که initialize در همان تراکنش دیپلوی صدا زده شود، که هیچ پنجره‌ای برای غریبه نماند.

یک خطای کلاسیک دیگر، احراز هویت با {{< term "tx-origin" "tx.origin" >}} است. `msg.sender` کسی است که تابع را مستقیم صدا زده. `tx.origin` حسابی است که کل تراکنش را امضا کرده، هرچند چند قرارداد بین‌شان باشد. اگر کیف‌پول فقط به `tx.origin` نگاه کند، مالک را می‌شود فریب داد که یک قرارداد دیگر را صدا بزند («airdrop‌ات را بگیر»)، و آن قرارداد از داخل، کیف‌پول را خالی می‌کند:

```
$ forge test --mt test_TxOriginPhished -vv
  wallet   0
  airdrop  10000000000000000000
```

کیف‌پول ۱۰ ETH داشت. مالک فقط `claim` را روی airdrop جعلی صدا زد. کیف‌پول دید `tx.origin` خود مالک است و ETH را به airdrop داد. رفعش استفاده از `msg.sender` است.

## مقدار برگشتی و عدد صحیح

دو جای دیگر هم هست که کد بی‌صدا غلط کار می‌کند.

اول، مقدار برگشتی. بعضی توکن‌ها در شکست revert نمی‌کنند و فقط `false` برمی‌گردانند. `FalseToken` همین‌طور است و `NaiveEscrow` نتیجه را نگاه نمی‌کند. پس Mallory که هیچ توکنی ندارد ۱۰۰ واریز می‌کند (`transferFrom` بی‌صدا false برمی‌گرداند، ولی قرارداد برایش ۱۰۰ اعتبار ثبت می‌کند) و بعد ۱۰۰ برداشت می‌کند، با توکن‌های Alice:

```
$ forge test --mt test_FalseTokenNaiveEscrow -vv
  mallory balance 100000000000000000000
  escrow balance  0
  alice credit    100000000000000000000
```

Mallory حالا ۱۰۰ توکن دارد، escrow صفر دارد و Alice هنوز فکر می‌کند ۱۰۰ طلب دارد.

`SafeTransfer` با یک فراخوانی سطح پایین کار می‌کند و revert می‌کند مگر توکن `true` یا هیچ‌چیز برگرداند. تا جایی که می‌دانم بعضی توکن‌های قدیمیِ معروف هیچ‌چیز برنمی‌گردانند، پس `require(token.transfer(...))` هم کافی نیست.

دوم، عدد صحیح. از Solidity نسخه‌ی 0.8 به بعد عملیات حسابی روی {{< term "integer-overflow" "overflow" >}} revert می‌کند. ولی بلوک‌های `unchecked` و تبدیل (cast) به نوع کوچک‌تر هنوز دور می‌زنند، بی‌صدا:

```
$ forge test --mt test_IntegerEdges -vv
  uint128(2**128 + 5) = 5
  uint8(300)          = 44
  unchecked 0 - 1     = 115792089237316195423570985008687907853269984665640564039457584007913129639935
```

هر خط یک نمونه است. عدد ۲^۱۲۸+۵ را به `uint128` تبدیل کنید، فقط ۵ می‌ماند. ۳۰۰ را به `uint8` ببرید، ۴۴ می‌شود (۳۰۰ منهای ۲۵۶). و `0 - 1` داخل `unchecked` به بزرگ‌ترین عدد `uint256` می‌رسد. هیچ‌کدام خطا نمی‌دهند.

## linter درباره‌ی کد خودم چه گفت

نیازی نیست همه‌ی این الگوها را فقط با چشم پیدا کنید. `forge lint` ابزار {{< term "static-analysis" "static analysis" >}} داخل Foundry است: کد را بدون اجرا می‌خواند و الگوهای مشکوک را گزارش می‌دهد. روی استخر، بازار و oracleهای سه پست قبل:

```
$ forge lint src | grep -E '^(warning|note|error)\[' | sort | uniq -c
   5 warning[block-timestamp]: usage of `block.timestamp` in a comparison may be manipulated by validators
   2 warning[divide-before-multiply]: division before multiplication may lose precision
  13 warning[erc20-unchecked-transfer]: ERC20 `transfer` or `transferFrom` call does not check the return value
   6 warning[reentrancy-events]: event emitted after an external call; reentrancy can reorder or fabricate logs ...
   3 warning[reentrancy-no-eth]: external call can be reentered before `reserve0` is updated
   1 warning[uninitialized-local]: local variable is read before being initialized
(one line trimmed)
```

`DemoToken` callback ندارد، پس تا جایی که می‌بینم هنوز هیچ‌کدام قابل سوءاستفاده نبود. ولی بیشتر هشدارها عادت‌هایی را نشان می‌دادند که بهتر است ترک شوند. state و eventها را قبل از transfer بردم، `SafeTransfer` و `nonReentrant` اضافه کردم، افت دقت قیمت تجمعی را درست کردم و timestampهای بررسی‌شده را با ذکر دلیل خاموش کردم. حالا `forge lint src` چیزی چاپ نمی‌کند و ۳۳ تست پاس می‌شوند.

قراردادهای آسیب‌پذیر هم وقتی به `src/` کپی شدند گزارش شدند (`reentrancy-eth`، `tx-origin`...)، جز initializer باز. یعنی linter همه‌چیز را نمی‌گیرد. `SafeVault` درست‌شده هم گزارش شد، چون قفل بعد از call نوشته می‌شود: این false positive است. ابزار جای فکر کردن را نمی‌گیرد.

## حادثه‌های واقعی، به تفکیک دسته

- **Reentrancy:** The DAO در ۲۰۱۶، که خالی شدنش به hard forkی رسید که Ethereum Classic را جدا کرد.
- **دستکاری oracle:** حمله‌ی پست قبل، که در گزارش‌های عمومی پروتکل‌های وام آمده.
- **لو رفتن کلید:** تا جایی که می‌فهمم چند ضرر بزرگ bridge از دزدی کلید validatorها بوده، نه باگ قرارداد؛ [هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) را هم ببینید.

## چک‌لیست پیش از دیپلوی

- **در هر تابع اول checks، بعد effects، بعد interactions، و بعد قفل.**
- **هر فراخوانی بیرونی، حتی transfer توکن، ممکن است شما را دوباره صدا بزند.**
- **برای هر تابع ویژه و هر initializer تستی بنویسید که غریبه نتواند صدایش بزند.**
- **فراخوانی توکن را از راه یک helper چک‌شده انجام دهید.** هر `unchecked` و cast کوچک‌کننده را بررسی کنید و از `tx.origin` استفاده نکنید.
- **lint تمیز یا توضیح‌داده‌شده، تست invariant** مثل [تست، fuzz و invariant با Foundry](/fa/posts/bc-foundry-testing-fuzzing/)، و برای پول واقعی بازبینی بیرونی.

## تمرین

۱. withdraw آسیب‌پذیر را با `balanceOf[msg.sender] -= bal` بعد از call بنویسید. حساب چک‌شده جلوی حمله را می‌گیرد؟
۲. یک شمارنده‌ی `totalDeposits` به `GuardedVault` اضافه کنید و آن را از داخل callback مهاجم بخوانید.

## قدم بعدی

**بهینه‌سازی gas و قرارداد قابل ارتقا با proxy**: کد امن هم gas می‌خورد و کد دیپلوی‌شده وصله‌پذیر نیست.
