+++
date = '2026-11-26T18:00:00+03:30'
draft = false
title = 'بهینه‌سازی gas و قرارداد قابل ارتقا با proxy'
description = 'بهینه‌سازی gas و قرارداد قابل ارتقا در Solidity: صرفه‌جویی اندازه‌گیری‌شده با storage packing و calldata، بعد یک proxy با EIP-1967 و storage collision.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "gas", "proxy", "foundry", "evm"]
cover = { image = "/images/covers/bc-gas-optimization-proxies.fa.png", alt = "بهینه‌سازی gas و قرارداد قابل ارتقا با proxy", hiddenInSingle = true }
+++

[امنیت قرارداد: reentrancy، access control و نمونه‌های واقعی](/fa/posts/bc-contract-security/) قراردادهایم را امن‌تر کرد. این پست ارزان‌ترشان می‌کند، بعد سراغ تغییرناپذیری کد دیپلوی‌شده می‌رود. پایه‌ی هر دو [EVM از درون](/fa/posts/bc-evm-internals-rust/) است: storage گران‌ترین بخش {{< term "gas" "gas" >}} است.

> Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64)، روی کپی پروژه‌ی پست قبل. gas برای کد و تنظیمات یکسان قطعی است. کد آموزشی است، audit نشده.

## اول اندازه بگیرید

`forge snapshot` gas هر تست را ذخیره و `--diff` مقایسه می‌کند. از تست یک swap و یک واریز روی `SimplePool` snapshot گرفتم و استخر را عوض کردم.

استخر برای هر مقدار یک slot سی‌ودوبایتی داشت. مثل Uniswap v2، موجودی‌ها و timestamp را در یک slot جا دادم؛ این {{< term "storage-packing" "storage packing" >}} است:

```solidity
uint112 private _reserve0; // 112 + 112 + 32 bits = one slot
uint112 private _reserve1;
uint32 public lastUpdate;
```

خروجی کوتاه‌شده‌ی `forge inspect SimplePool storageLayout`:

```
 Name               Type        Slot   Offset   Bytes
 _locked            uint256     0      0        32
 _reserve0          uint112     1      0        14
 _reserve1          uint112     1      14       14
 lastUpdate         uint32      1      28       4
 price0Cumulative   uint256     2      0        32
```

هفت slot شد پنج تا. تابع `swap` و تابع‌های نقدینگی موجودی‌ها را یک بار در متغیر محلی می‌خوانند و با یک `_update` می‌نویسند. cast به نوع کوچک‌تر بی‌صدا می‌بُرد (پست قبل)، پس `_update` بالای `type(uint112).max` revert می‌کند و `forge lint` هر cast را گزارش کرد تا دلیل امن بودنش را نوشتم.

```
$ forge snapshot --mt test_gas_ --diff
↓ GasTest::test_gas_swap() (gas: 138482 → 129251 | -9231 -6.666%)
↓ GasTest::test_gas_addLiquidity() (gas: 130272 → 120741 | -9531 -7.316%)
(trimmed)
```

این عددها با optimizer خاموش (پیش‌فرض Foundry) است. با `FOUNDRY_OPTIMIZER=true` هزینه‌ی swap از ۱۳۱٬۶۰۵ به ۱۲۱٬۵۵۷ رسید.

## الگوهای کوچک‌تر، اندازه‌گیری‌شده

جفت‌هایی با یک تفاوت (`test/gas/Micro.sol`)، gas هر فراخوانی از `forge test --gas-report`:

| تغییر | optimizer خاموش | optimizer روشن |
|---|---|---|
| رشته‌ی `require` → custom error (revert) | 701 → 434 | 338 → 260 |
| متغیر storage → `immutable` / `constant` | 3,118 → 1,019 / 1,019 | 2,522 → 417 / 417 |
| سه بار خواندن storage → cache | 4,875 → 4,689 | 3,236 → 3,026 |
| `uint256[] memory` → `calldata` (۱۰۰ عضو) | 53,784 → 31,176 | 26,806 → 18,153 |
| `i++` → `unchecked { ++i; }` (۱۰۰ عضو) | 31,176 → 30,676 | 18,153 → 18,153 |

ترفند معروف unchecked با optimizer روشن سودی نداشت؛ تا جایی که از release note نسخه‌ی 0.8.22 می‌فهمم، کامپایلر خودش این چک را برای شمارنده‌ی ساده حذف می‌کند. gas در storage و کپی خرج می‌شود؛ بقیه کوچک است و ارزش یک باگ را ندارد. خوانایی و امنیت اول‌اند.

## چرا proxy

کد یک آدرس ویرایش‌شدنی نیست؛ رفع باگ یعنی آدرس جدید، ولی کاربرها و موجودی‌ها روی آدرس قبلی‌اند. با {{< term "proxy-pattern" "proxy" >}} کاربر با قرارداد کوچکی حرف می‌زند که state را نگه می‌دارد و هر فراخوانی را به implementation قابل تعویض می‌فرستد.

فرستادن با {{< term "delegatecall" "delegatecall" >}} است: کد B روی storage قرارداد A اجرا می‌شود و `msg.sender` و `msg.value` همان می‌مانند.

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

Alice و Bob از راه proxy جمعاً ۸ ETH واریز می‌کنند:

```
$ forge test --mt test_DelegatecallContext -vv
  msg.sender seen by V1 code is alice: true
  address(this) is the proxy:          true
  proxy totalDeposits: 8000000000000000000
  impl  totalDeposits: 0
  ETH held by proxy:   8000000000000000000
```

آدرس implementation slotی می‌خواهد که هیچ متغیر عادی به آن نرسد. {{< term "eip-1967" "EIP-1967" >}} یک hash منهای یک را انتخاب می‌کند:

```
$ cast keccak "eip1967.proxy.implementation"
0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbd
```

منهای یک می‌شود `...382bbc`، همان ثابت proxy من (در تست با `vm.load` هم چک شده).

## ارتقا و storage collision

`VaultV2` از `VaultV1` ارث می‌برد و فقط `withdrawCount` را به آخر می‌افزاید. بعد از `upgradeTo` همه‌چیز سالم است:

```
$ forge test --mt test_UpgradeKeepsState -vv
  version       v2
  owner is admin true
  alice         4000000000000000000
  bob           3000000000000000000
  total         7000000000000000000
  withdrawCount 1
```

`VaultV2Reordered` همان متغیرها را «مرتب‌تر» تعریف می‌کند. slotها جابه‌جا نشده‌اند، پس هر اسم داده‌ی اشتباه می‌خواند؛ این {{< term "storage-collision" "storage collision" >}} است:

```
$ forge test --mt test_ReorderedUpgradeCorruptsState -vv
  version       v2-reordered
  owner         0x0000000000000000000000000000000000000000
  totalDeposits 970899903996907561841885952119535521295492554447
  alice         0
  admin as uint 970899903996907561841885952119535521295492554447
  after fix, alice 5000000000000000000
```

`totalDeposits` آدرس admin است که عدد خوانده شده و Alice موجودی ندارد. این نسخه فقط می‌خواند، پس برگشت به چیدمان درست ۵ ETH او را برگرداند؛ یک نوشتن داده را برای همیشه خراب می‌کرد. قبل از هر ارتقا `forge inspect ... storageLayout` دو نسخه را مقایسه کنید.

## Initializer

proxy هرگز constructor پیاده‌سازی را اجرا نمی‌کند، پس state با `initialize()` مقدار می‌گیرد. proxy من آن را در تراکنش دیپلوی صدا می‌زند و شکاف پست قبل بسته می‌شود. implementation هم قرارداد است و constructor در `VaultV1` قفلش می‌کند، پس `impl.initialize(mallory)` revert می‌شود. بدون قفل، Mallory مالک implementation می‌شود؛ تا جایی که می‌بینم اینجا بی‌خطر است، ولی اگر منطق ارتقا آنجا بود مهم می‌شد.

تفاوت UUPS و transparent، تا جایی که از مستندات OpenZeppelin می‌فهمم، در جای منطق ارتقاست. transparent آن را در proxy نگه می‌دارد و فراخوانی admin را جلو نمی‌فرستد تا تداخلی پیش نیاید؛ `upgradeTo` من هر تابع implementation با همان {{< term "function-selector" "selector" >}} را می‌پوشاند. UUPS آن را در implementation می‌گذارد: proxy ارزان‌تر، ولی نسخه‌ای بدون آن یعنی پایان ارتقاها.

## چند نکته‌ی مهم

- با `forge snapshot --diff` اندازه بگیرید، نه افسانه.
- فقط متغیرهای پرمصرف را pack کنید و هر cast کوچک‌کننده را چک کنید.
- بین نسخه‌ها متغیر state را جابه‌جا، حذف یا عوض نکنید؛ فقط به آخر بیفزایید.
- در تراکنش دیپلوی initialize کنید و implementation را قفل کنید.

## تمرین

۱. `borrowIndex` و `lastAccrual` را در `LendingMarket` pack کنید و `borrow` را اندازه بگیرید.
۲. در کپی `VaultV1` متغیری قبل از `owner` بگذارید و به آن ارتقا دهید. چه خراب می‌شود؟

## قدم بعدی

پست بعد: **MEV و ترتیب تراکنش‌ها**.
