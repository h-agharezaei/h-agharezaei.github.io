+++
date = '2026-11-26T18:00:00+03:30'
draft = false
title = 'بهینه‌سازی gas و قرارداد قابل ارتقا با proxy'
description = 'بهینه‌سازی gas و قرارداد قابل ارتقا در Solidity: صرفه‌جویی اندازه‌گیری‌شده با storage packing و calldata، بعد یک proxy با EIP-1967 و storage collision.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "gas", "proxy", "foundry", "evm"]
cover = { image = "/images/covers/bc-gas-optimization-proxies.fa.png", alt = "بهینه‌سازی gas و قرارداد قابل ارتقا با proxy", hiddenInSingle = true }
+++

هر عملیات روی قرارداد هوشمند هزینه دارد، و اسم این هزینه {{< term "gas" "gas" >}} است. گران‌ترین بخشش نوشتن در storage است ([EVM از درون](/fa/posts/bc-evm-internals-rust/)). استخر AMM من هفت slot storage مصرف می‌کرد، در حالی که پنج‌تا کافی بود. مشکل دوم بدتر است: کدی که روی زنجیره دیپلوی شد دیگر تغییر نمی‌کند. اگر باگی در آن پیدا شود، نمی‌توان آن را وصله کرد.

[امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی](/fa/posts/bc-contract-security/) قراردادهایم را امن‌تر کرد. این پست دو کار دیگر می‌کند: ارزان‌ترشان می‌کند و راهی برای ارتقایشان می‌سازد.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64)، روی کپی پروژه‌ی پست قبل. gas برای کد و تنظیمات یکسان قطعی است. کد آموزشی است، audit نشده.

## اول اندازه بگیرید

بهینه‌سازی بدون اندازه‌گیری حدس زدن است. `forge snapshot` gas هر تست را ذخیره می‌کند و `--diff` وضعیت جدید را با آن مقایسه می‌کند. من از تست یک swap و یک واریز نقدینگی روی `SimplePool` snapshot گرفتم و بعد استخر را عوض کردم.

اول یک توضیح درباره‌ی storage. هر متغیر state در یک «slot» سی‌ودوبایتی ذخیره می‌شود و هر slot که نوشته شود هزینه‌ی سنگینی دارد. اگر چند متغیر کوچک باشند، می‌شود چندتا را کنار هم در یک slot جا داد. استخر من برای هر مقدار یک slot داشت، حتی برای timestamp که چند بایت بیشتر نیست. مثل Uniswap v2، موجودی‌ها و timestamp را در یک slot گذاشتم. این کار {{< term "storage-packing" "storage packing" >}} نام دارد:

```solidity
uint112 private _reserve0; // 112 + 112 + 32 bits = one slot
uint112 private _reserve1;
uint32 public lastUpdate;
```

۱۱۲ بیت و ۱۱۲ بیت و ۳۲ بیت روی هم ۲۵۶ بیت می‌شود، یعنی دقیقاً یک slot. خروجی کوتاه‌شده‌ی `forge inspect SimplePool storageLayout` نشان می‌دهد چطور جا گرفته‌اند:

```
 Name               Type        Slot   Offset   Bytes
 _locked            uint256     0      0        32
 _reserve0          uint112     1      0        14
 _reserve1          uint112     1      14       14
 lastUpdate         uint32      1      28       4
 price0Cumulative   uint256     2      0        32
```

هر سه متغیر slot شماره‌ی ۱ هستند. ستون `Offset` می‌گوید هر کدام از کدام بایت slot شروع می‌شود و `Bytes` اندازه‌شان است. هفت slot شد پنج تا.

دو تغییر دیگر هم دادم. تابع `swap` و تابع‌های نقدینگی حالا موجودی‌ها را یک بار در متغیر محلی می‌خوانند و با یک `_update` می‌نویسند. و چون تبدیل به نوع کوچک‌تر بی‌صدا عدد را می‌بُرد (پست قبل نشان داد)، `_update` بالای `type(uint112).max` revert می‌کند. `forge lint` هم هر cast را گزارش کرد، تا برای هرکدام دلیل امن بودنش را نوشتم.

نتیجه:

```
$ forge snapshot --mt test_gas_ --diff
↓ GasTest::test_gas_swap() (gas: 138482 → 129251 | -9231 -6.666%)
↓ GasTest::test_gas_addLiquidity() (gas: 130272 → 120741 | -9531 -7.316%)
(trimmed)
```

هر خط gas قبل و بعد از تغییر را نشان می‌دهد. `swap` حدود ۹٬۲۰۰ gas و ۶٫۷ درصد ارزان‌تر شد و واریز نقدینگی حدود ۹٬۵۰۰ و ۷٫۳ درصد. این عددها با optimizer خاموش است، که پیش‌فرض Foundry است. با `FOUNDRY_OPTIMIZER=true` هزینه‌ی swap از ۱۳۱٬۶۰۵ به ۱۲۱٬۵۵۷ رسید.

## الگوهای کوچک‌تر، اندازه‌گیری‌شده

چند توصیه‌ی معروف برای کم کردن gas هست. به‌جای باور کردن‌شان، هر کدام را اندازه گرفتم. برای هر کدام دو قرارداد کوچک نوشتم که فقط در یک چیز فرق دارند (`test/gas/Micro.sol`) و gas هر فراخوانی را از `forge test --gas-report` خواندم:

| تغییر | optimizer خاموش | optimizer روشن |
|---|---|---|
| رشته‌ی `require` → custom error (revert) | 701 → 434 | 338 → 260 |
| متغیر storage → `immutable` / `constant` | 3,118 → 1,019 / 1,019 | 2,522 → 417 / 417 |
| سه بار خواندن storage → cache | 4,875 → 4,689 | 3,236 → 3,026 |
| `uint256[] memory` → `calldata` (۱۰۰ عضو) | 53,784 → 31,176 | 26,806 → 18,153 |
| `i++` → `unchecked { ++i; }` (۱۰۰ عضو) | 31,176 → 30,676 | 18,153 → 18,153 |

هر سطر یعنی:

- **custom error:** به‌جای نوشتن یک رشته‌ی طولانی در revert، یک خطای نام‌دار تعریف کنید. داده‌ی revert فقط یک شناسه‌ی چهاربایتی می‌شود.
- **`immutable` و `constant`:** مقدار ثابتی مثل کارمزد را در storage نگه ندارید. `immutable` در زمان دیپلوی در خود کد قرارداد گذاشته می‌شود و `constant` هنگام کامپایل. خواندنشان دیگر یک خواندن storage نیست.
- **cache:** اگر یک متغیر storage را سه بار می‌خوانید، یک بار در متغیر محلی بگذارید.
- **`calldata`:** پارامتر آرایه‌ی تابع external را از `memory` به `calldata` ببرید تا کپی نشود.
- **`unchecked`:** شمارنده‌ی حلقه را بدون چک overflow بالا ببرید.

ترفند معروف `unchecked` با optimizer روشن هیچ سودی نداشت. تا جایی که از release note نسخه‌ی 0.8.22 می‌فهمم، کامپایلر خودش این چک را برای شمارنده‌ی ساده حذف می‌کند. پس درس این جدول این است: gas بیشتر در storage و کپی خرج می‌شود؛ بقیه کوچک است و ارزش ریسک یک باگ را ندارد. خوانایی و امنیت اول‌اند.

## چرا proxy

حالا سراغ مشکل دوم می‌رویم. کد هر آدرس قابل ویرایش نیست. اگر باگی پیدا شود، قرارداد جدید آدرس جدید دارد، ولی کاربرها و موجودی‌هایشان روی آدرس قبلی است.

راه حل مثل یک شماره‌تلفن ثابت برای یک فروشگاه است. مشتری همیشه به همان شماره زنگ می‌زند، ولی کارمندی که پشت خط جواب می‌دهد را می‌شود عوض کرد. دفتر حساب‌ها هم همیشه در همان فروشگاه می‌ماند. در قرارداد، این الگو {{< term "proxy-pattern" "proxy" >}} نام دارد. کاربر با قرارداد کوچکی حرف می‌زند که وضعیت (state و ETH) را نگه می‌دارد و هر فراخوانی را به یک قرارداد دیگر، یعنی implementation، می‌فرستد. با عوض کردن آدرس implementation، منطق عوض می‌شود و داده سر جایش می‌ماند.

این فرستادن با {{< term "delegatecall" "delegatecall" >}} انجام می‌شود. یک فراخوانی عادی کد قرارداد B را روی storage خود B اجرا می‌کند. `delegatecall` کد B را روی storage قرارداد A اجرا می‌کند و `msg.sender` و `msg.value` هم همان فراخوانی اصلی می‌مانند. انگار A کد B را قرض گرفته.

```solidity
fallback() external payable {
    bytes32 slot = IMPLEMENTATION_SLOT;
    assembly {
        let impl := sload(slot)
        calldatacopy(0, 0, calldatasize())
        let ok := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
        returndatacopy(0, 0, returndatasize())
        switch ok
        case 0 { revert(0, returndatasize()) }
        default { return(0, returndatasize()) }
    }
}
```

`fallback` تابعی است که وقتی هیچ تابع دیگری با فراخوانی جور نباشد اجرا می‌شود، یعنی عملاً هر فراخوانی. این کد آدرس implementation را از storage می‌خواند، ورودی فراخوانی را کپی می‌کند، `delegatecall` می‌زند، و نتیجه یا خطا را عیناً به صدازننده برمی‌گرداند.

آزمایش: Alice و Bob از راه proxy جمعاً ۸ ETH واریز می‌کنند و بعد به شکل زیر نگاه می‌کنیم:

```
$ forge test --mt test_DelegatecallContext -vv
  msg.sender seen by V1 code is alice: true
  address(this) is the proxy:          true
  proxy totalDeposits: 8000000000000000000
  impl  totalDeposits: 0
  ETH held by proxy:   8000000000000000000
```

- **`msg.sender seen by V1 code is alice`:** کد implementation فرستنده را Alice می‌بیند، نه proxy.
- **`address(this) is the proxy`:** ولی «خودم» برای آن کد، proxy است.
- **`proxy totalDeposits` و `impl totalDeposits`:** داده در proxy نوشته شد (۸ ETH) و implementation دست‌نخورده ماند (صفر).
- **`ETH held by proxy`:** ETH هم در proxy است.

یک جزئیات: خود proxy هم باید آدرس implementation را در یک slot نگه دارد. اگر این slot با slotی که Solidity به یک متغیر عادی می‌دهد یکی باشد، آن متغیر آدرس را خراب می‌کند. برای همین {{< term "eip-1967" "EIP-1967" >}} یک slot دور از دسترس تعیین کرده: hash یک رشته، منهای یک.

```
$ cast keccak "eip1967.proxy.implementation"
0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbd
```

منهای یک می‌شود `...382bbc`، همان ثابت proxy من (در تست با `vm.load` هم چک شده).

## ارتقا و storage collision

ارتقا یعنی `upgradeTo` که آدرس implementation را عوض می‌کند. نسخه‌ی ۲ از نسخه‌ی ۱ ارث می‌برد و فقط متغیر `withdrawCount` را به آخر می‌افزاید. Alice ۱ ETH برداشت می‌کند و می‌بینیم همه‌چیز سالم است:

```
$ forge test --mt test_UpgradeKeepsState -vv
  version       v2
  owner is admin true
  alice         4000000000000000000
  bob           3000000000000000000
  total         7000000000000000000
  withdrawCount 1
```

نسخه ۲ شده، owner همان است، موجودی‌ها (۵ منهای ۱ برای Alice و ۳ برای Bob) حفظ شده و `withdrawCount` یک است.

خطر کجاست؟ قرارداد با نام متغیر کار نمی‌کند، با شماره‌ی slot. نسخه‌ی ۱ می‌گوید `owner` در slot ۰ و `balanceOf` در slot ۱ و `totalDeposits` در slot ۲ است. اگر نسخه‌ی جدید همان متغیرها را «مرتب‌تر» و با ترتیب دیگری تعریف کند، داده‌ی قدیمی همان جا می‌ماند ولی هر اسم از slot دیگری می‌خواند. `VaultV2Reordered` همین کار را می‌کند. به این مشکل {{< term "storage-collision" "storage collision" >}} می‌گویند:

```
$ forge test --mt test_ReorderedUpgradeCorruptsState -vv
  version       v2-reordered
  owner         0x0000000000000000000000000000000000000000
  totalDeposits 970899903996907561841885952119535521295492554447
  alice         0
  admin as uint 970899903996907561841885952119535521295492554447
  after fix, alice 5000000000000000000
```

- **`owner`:** صفر شد، چون حالا از slotی می‌خواند که قبلاً به mapping تعلق داشت.
- **`totalDeposits`:** عدد عجیبی است، و خط `admin as uint` نشان می‌دهد همان آدرس admin است که به‌صورت عدد خوانده شده. چون `totalDeposits` حالا در slot ۰ است که قبلاً `owner` بود.
- **`alice`:** موجودی‌اش صفر دیده می‌شود.
- **`after fix`:** این نسخه فقط می‌خواند و چیزی نمی‌نویسد، پس برگشتن به چیدمان درست ۵ ETH Alice را برگرداند. اگر یک نوشتن هم انجام شده بود، داده برای همیشه خراب می‌شد.

قاعده این است: بین نسخه‌ها متغیر state را جابه‌جا، حذف یا عوض نکنید و فقط به آخر بیفزایید. و قبل از هر ارتقا خروجی `forge inspect ... storageLayout` دو نسخه را کنار هم بگذارید.

## Initializer

یک نکته‌ی دیگر: proxy هرگز constructor پیاده‌سازی را اجرا نمی‌کند، چون constructor فقط یک بار در زمان دیپلوی خود implementation اجرا می‌شود و روی storage خودش می‌نویسد. پس state اولیه‌ی proxy باید با تابعی به اسم `initialize()` پر شود. باگ `InitFeed` در پست قبل نشان داد اگر کسی بتواند آن را دوباره صدا بزند چه می‌شود. proxy من `initialize` را در همان تراکنش دیپلوی صدا می‌زند و آن شکاف بسته می‌شود.

خود implementation هم یک قرارداد معمولی است و می‌شود مستقیم صدایش زد. برای همین constructor در `VaultV1` آن را قفل می‌کند و `impl.initialize(mallory)` revert می‌شود. بدون قفل، Mallory مالک implementation می‌شود. تا جایی که می‌بینم این‌جا بی‌خطر است، چون state آن قرارداد به کسی مربوط نیست، ولی اگر منطق ارتقا همان‌جا بود مهم می‌شد.

دو سبک رایج proxy هم هست: transparent و UUPS. تفاوتشان، تا جایی که از مستندات OpenZeppelin می‌فهمم، در جای منطق ارتقاست. در transparent منطق ارتقا در proxy می‌ماند و فراخوانی admin به implementation نمی‌رود، تا تداخلی پیش نیاید؛ `upgradeTo` در proxy من هم هر تابع implementation با همان {{< term "function-selector" "selector" >}} را می‌پوشاند. UUPS منطق ارتقا را در implementation می‌گذارد: proxy ارزان‌تر می‌شود، ولی نسخه‌ای که آن را نداشته باشد یعنی پایان ارتقاها.

## دام‌های بهینه‌سازی و ارتقا

- **با `forge snapshot --diff` اندازه بگیرید، نه افسانه.** چند ترفند معروف، مثل `unchecked`، سودی نداشتند.
- **فقط متغیرهای پرمصرف را pack کنید و هر cast کوچک‌کننده را چک کنید.** pack کردن بی‌دقت همان باگ برش بی‌صدا را می‌آورد.
- **بین نسخه‌ها متغیر state را جابه‌جا، حذف یا عوض نکنید.** فقط به آخر بیفزایید.
- **در تراکنش دیپلوی initialize کنید و implementation را قفل کنید.**

## تمرین

۱. `borrowIndex` و `lastAccrual` را در `LendingMarket` pack کنید و `borrow` را اندازه بگیرید.
۲. در کپی `VaultV1` متغیری قبل از `owner` بگذارید و به آن ارتقا دهید. چه خراب می‌شود؟

## قدم بعدی

**MEV و ترتیب تراکنش‌ها**: از هزینه‌ی تراکنش به زمان اجرای آن.
