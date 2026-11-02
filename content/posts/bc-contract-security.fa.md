+++
date = '2026-11-25T18:00:00+03:30'
draft = false
title = 'امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی'
seoTitle = 'امنیت قرارداد: reentrancy و access control'
description = 'امنیت قرارداد در Solidity: reentrancy، callback توکن‌ها، initializer باز، tx.origin و transfer چک‌نشده، با حمله در تست محلی و رفع هر کدام.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "security", "reentrancy", "foundry", "defi"]
cover = { image = "/images/covers/bc-contract-security.fa.png", alt = "امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی", hiddenInSingle = true }
+++

[Oracle و دستکاری قیمت](/fa/posts/bc-oracles/) بازار وام را بی‌هیچ باگی در کد شکست. این پست درباره‌ی خود باگ‌هاست، هر کدام حمله‌شده در تست محلی Foundry روی کد خودم و بعد رفع‌شده. این‌جا معلوم می‌شود چرا `withdraw` در [اولین قرارداد با Solidity و Foundry](/fa/posts/bc-solidity-first-contract/) قبل از فرستادن ETH حافظه را به‌روز می‌کند. [مجوزدهی: RBAC و IDOR](/fa/posts/sec-authorization-rbac-idor/) نسخه‌ی وبِ بخش access control است.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل را کپی کردم. قراردادهای عمداً آسیب‌پذیر در `test/vulnerable/` و مهاجم‌ها در `test/helpers/` هستند. کد آموزشی است و audit نشده.

## Reentrancy: صندوقی که دو بار پول می‌دهد

```solidity
function withdraw() external {
    uint256 bal = balanceOf[msg.sender];
    (bool ok,) = msg.sender.call{value: bal}(""); // interaction first...
    if (!ok) revert TransferFailed();
    balanceOf[msg.sender] = 0; // ...effect too late
}
```

فرستادن ETH تابع `receive()` گیرنده را اجرا می‌کند و آن، پیش از صفر شدن موجودی، دوباره `withdraw()` را صدا می‌زند. این {{< term "reentrancy" "reentrancy" >}} است. Alice و Bob هر کدام ۵ ETH واریز می‌کنند و مهاجم ۱:

```
$ forge test --mt test_VulnerableVaultIsDrained -vv
  vault before    10000000000000000000
  vault after     0
  attacker has    11000000000000000000
  extra rounds    10
```

رفعش ترتیبی است به اسم {{< term "checks-effects-interactions" "checks-effects-interactions" >}}: بررسی، نوشتن state، و در آخر صدا زدن بیرون.

```solidity
function withdraw() external nonReentrant {
    uint256 bal = balanceOf[msg.sender]; // checks
    if (bal == 0) revert NothingToWithdraw();
    balanceOf[msg.sender] = 0; // effects
    (bool ok,) = msg.sender.call{value: bal}(""); // interactions
    if (!ok) revert TransferFailed();
}
```

`nonReentrant` در `src/Security.sol` قفلی کوچک است: پرچمی در storage که هنگام ورود ست و هنگام خروج پاک می‌شود.

## قفل به‌تنهایی کافی نیست

`GuardedVault` همان ترتیب غلط را نگه می‌دارد و فقط `withdraw` را قفل می‌کند. ورود دوباره به `withdraw` شکست می‌خورد، ولی مهاجم وسط callback با `move()` قفل‌نشده موجودی را به همدستش منتقل می‌کند:

```
$ forge test --mt test_GuardMissesCrossFunction -vv
  deposited       1000000000000000000
  got back        2000000000000000000
  vault after     9000000000000000000
```

این reentrancy بین‌تابعی است. `SafeVault` ترتیب درست دارد و همه‌ی تابع‌های تغییردهنده را قفل می‌کند؛ هر دو مهاجم revert می‌شوند. در reentrancy فقط‌خواندنی، قراردادی دیگر وسط callback یک تابع `view` را می‌خواند و state نیمه‌کاره می‌بیند (این را نساختم).

## callback داخل توکن‌ها

`safeTransferFrom` در ERC-721 ([توکن‌ها: ERC-20 و ERC-721](/fa/posts/bc-erc20-erc721/)) روی گیرنده `onERC721Received` را صدا می‌زند. mintی با قاعده‌ی «هر آدرس یک NFT رایگان» که ادعا را بعد از callback ثبت می‌کند:

```
$ forge test --mt test_CallbackReentersMint -vv
  NFTs for one address: 5
```

بردن `claimed[msg.sender] = true` به بالای mint درستش می‌کند. تا جایی که می‌دانم توکن‌های ERC-777 حتی در transfer معمولی hook صدا می‌زنند.

## Access control

باگ‌های {{< term "access-control" "access control" >}} اغلب یک خط جاافتاده‌اند. `InitFeed`، price feed بازار وام، مالکش را در `initialize()` تعیین می‌کند که هر کسی دوباره صدایش می‌زند:

```
$ forge test --mt test_OpenInitializerDrainsMarket -vv
  feed owner is mallory: true
  USDX borrowed against 1 DEMO: 50000000000000000000000
  USDX left in market: 0
```

Mallory مالک شد، DEMO را یک میلیون قیمت گذاشت و همه را قرض گرفت. رفع: `if (owner != address(0)) revert AlreadyInitialized();` و initialize در همان تراکنش دیپلوی.

احراز هویت با {{< term "tx-origin" "tx.origin" >}} خطای کلاسیک دیگر است. این حسابِ امضاکننده‌ی تراکنش است، نه صدازننده، پس airdrop جعلی‌ای که مالک صدا بزند کیف‌پول را خالی می‌کند:

```
$ forge test --mt test_TxOriginPhished -vv
  wallet   0
  airdrop  10000000000000000000
```

## مقدار برگشتی و عدد صحیح

`FalseToken` مثل بعضی توکن‌ها به جای revert، `false` برمی‌گرداند. `NaiveEscrow` نتیجه را نادیده می‌گیرد، پس Mallory بی‌توکن ۱۰۰ واریز می‌کند و ۱۰۰ توکن Alice را برمی‌دارد:

```
$ forge test --mt test_FalseTokenNaiveEscrow -vv
  mallory balance 100000000000000000000
  escrow balance  0
  alice credit    100000000000000000000
```

`SafeTransfer` با فراخوانی سطح پایین revert می‌کند مگر توکن true یا هیچ‌چیز برگرداند. تا جایی که می‌دانم بعضی توکن‌های قدیمیِ معروف هیچ‌چیز برنمی‌گردانند، پس `require(token.transfer(...))` کافی نیست.

از 0.8 عملیات حسابی روی {{< term "integer-overflow" "overflow" >}} revert می‌کند. بلوک‌های `unchecked` و cast به نوع کوچک‌تر هنوز دور می‌زنند:

```
$ forge test --mt test_IntegerEdges -vv
  uint128(2**128 + 5) = 5
  uint8(300)          = 44
  unchecked 0 - 1     = 115792089237316195423570985008687907853269984665640564039457584007913129639935
```

## linter درباره‌ی کد خودم چه گفت

`forge lint` ابزار {{< term "static-analysis" "static analysis" >}} داخل Foundry است. روی استخر، بازار و oracleهای سه پست قبل:

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

`DemoToken` callback ندارد، پس تا جایی که می‌بینم هنوز هیچ‌کدام قابل سوءاستفاده نبود. state و eventها را قبل از transfer بردم، `SafeTransfer` و `nonReentrant` اضافه کردم، افت دقت قیمت تجمعی را درست کردم و timestampهای بررسی‌شده را با ذکر دلیل خاموش کردم. حالا `forge lint src` چیزی چاپ نمی‌کند و ۳۳ تست پاس می‌شوند.

قراردادهای آسیب‌پذیر هم وقتی به `src/` کپی شدند گزارش شدند (`reentrancy-eth`، `tx-origin`...)، جز initializer باز. `SafeVault` درست‌شده هم گزارش شد، چون قفل بعد از call نوشته می‌شود: false positive.

## حادثه‌های واقعی، به تفکیک دسته

- **Reentrancy**: The DAO در ۲۰۱۶، که خالی شدنش به hard forkی رسید که Ethereum Classic را جدا کرد.
- **دستکاری oracle**: حمله‌ی پست قبل، که در گزارش‌های عمومی پروتکل‌های وام آمده.
- **لو رفتن کلید**: تا جایی که می‌فهمم چند ضرر بزرگ bridge از دزدی کلید validatorها بوده، نه باگ قرارداد؛ [هک بایننس](/fa/posts/binance-hack-hot-wallet-2026/) را هم ببینید.

## چند نکته‌ی مهم

چک‌لیست من قبل از دیپلوی:

- در هر تابع اول checks، بعد effects، بعد interactions، و بعد قفل.
- هر فراخوانی بیرونی، حتی transfer توکن، ممکن است شما را دوباره صدا بزند.
- برای هر تابع ویژه و initializer تستی که غریبه نتواند صدایش بزند.
- فراخوانی توکن از راه یک helper چک‌شده؛ هر `unchecked` و cast کوچک‌کننده بررسی‌شده؛ بدون `tx.origin`.
- lint تمیز یا توضیح‌داده‌شده، تست invariant مثل [تست، fuzz و invariant با Foundry](/fa/posts/bc-foundry-testing-fuzzing/)، بازبینی بیرونی برای پول واقعی.

## تمرین

۱. withdraw آسیب‌پذیر را با `balanceOf[msg.sender] -= bal` بعد از call بنویسید. حساب چک‌شده جلوی حمله را می‌گیرد؟
۲. یک شمارنده‌ی `totalDeposits` به `GuardedVault` اضافه کنید و آن را از داخل callback مهاجم بخوانید.

## قدم بعدی

پست بعد: **بهینه‌سازی gas و قرارداد قابل ارتقا با proxy**.
