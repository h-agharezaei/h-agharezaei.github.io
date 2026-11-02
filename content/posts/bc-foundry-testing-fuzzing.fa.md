+++
date = '2026-11-16T18:00:00+03:30'
draft = false
title = 'تست، fuzz و invariant با Foundry'
description = 'تست قرارداد Solidity با Foundry: تست واحد با cheatcode، fuzz با ورودی محدود، تست invariant با handler که باگ کاشته‌شده را پیدا می‌کند، gas و coverage.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "foundry", "testing", "fuzzing"]
cover = { image = "/images/covers/bc-foundry-testing-fuzzing.fa.png", alt = "تست، fuzz و invariant با Foundry", hiddenInSingle = true }
+++

در [اولین قرارداد با Solidity و Foundry](/fa/posts/bc-solidity-first-contract/) یک خزانه‌ی کوچک ETH دیپلوی کردم و با `cast` امتحانش کردم. قرارداد را بعد از دیپلوی بدون سازوکار اضافه نمی‌شود وصله کرد و پول هم نگه می‌دارد، پس تست از یک سرویس بک‌اند مهم‌تر است. این پست همان خزانه را با Foundry و به زبان Solidity تست می‌کند.

ایده‌ها همان‌هایی است که در [تست در Go: table-driven و benchmark](/fa/posts/go-testing-basics/)، [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/)، [تست خاصیت‌محور](/fa/posts/eng-property-based-testing/) و [fuzzing برای پیدا کردن باگ امنیتی](/fa/posts/sec-fuzzing/) دیدیم. چیز تازه cheatcodeها و اجراکننده‌ی invariant است.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل را بدون تغییر (همان `src/Vault.sol`) در یک پوشه‌ی محلی تازه کپی کردم و فقط تست اضافه کردم. اجرای fuzz تصادفی است، پس مثال نقض شما فرق خواهد کرد.

## تست واحد و cheatcode

تست یک قرارداد است که `forge test` تابع‌های `test*` آن را صدا می‌زند. `setUp` قبل از هر تست روی state تازه اجرا می‌شود:

```solidity
contract VaultTest is Test {
    Vault vault;
    address alice = makeAddr("alice");

    event Deposited(address indexed account, uint256 amount);

    function setUp() public {
        vault = new Vault(); // this test contract is the owner
        vm.deal(alice, 10 ether);
    }

    function test_DepositEmitsEvent() public {
        vm.expectEmit(true, false, false, true, address(vault));
        emit Deposited(alice, 2 ether);
        vm.prank(alice);
        vault.deposit{value: 2 ether}();
    }

    function test_RevertWhen_WithdrawMoreThanBalance() public {
        vm.prank(alice);
        vault.deposit{value: 1 ether}();
        vm.expectRevert(abi.encodeWithSelector(Vault.InsufficientBalance.selector, 1 ether, 2 ether));
        vm.prank(alice);
        vault.withdraw(2 ether);
    }
}
```

`vm` رابط {{< term "cheatcode" "cheatcode" >}} است: فراخوانی‌هایی که خود EVM تست جوابشان را می‌دهد. `vm.deal` موجودی ETH را تنظیم می‌کند، `vm.prank` فراخوانی بعدی را از طرف `alice` می‌فرستد، `vm.expectRevert` انتظار دارد فراخوانی بعدی دقیقاً با همان خطا و آرگومان‌ها شکست بخورد و `vm.expectEmit` رویداد بعدی را چک می‌کند (booleanها می‌گویند کدام topicها و داده مقایسه شوند). در فایل تست‌های چک مالک و «توقف جلوی واریز را می‌گیرد نه برداشت» هم هست.

## تست fuzz

تستی که پارامتر دارد تست {{< term "fuzzing" "fuzz" >}} است: forge به‌طور پیش‌فرض ۲۵۶ بار با ورودی ساختگی صدایش می‌زند. `bound` هر `uint256` را به یک بازه می‌برد تا اجراها به‌جای revert به درد بخورند:

```solidity
function testFuzz_DepositWithdrawRoundTrip(uint256 amount, uint256 out) public {
    amount = bound(amount, 1, 10 ether);
    out = bound(out, 1, amount);
    vm.startPrank(alice);
    vault.deposit{value: amount}();
    vault.withdraw(out);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), amount - out);
    assertEq(alice.balance, 10 ether - amount + out);
    assertEq(address(vault).balance, vault.totalDeposits());
}
```

یک `testFuzz_MoveKeepsTotal(address to, uint256 amount)` هم هست که واریز می‌کند و همه را به یک `to` تصادفی منتقل می‌کند.

## تست invariant با handler

{{< term "invariant-testing" "تست invariant" >}} تابع‌های تصادفی را با ترتیب تصادفی صدا می‌زند و بعد از هر فراخوانی یک خاصیت را چک می‌کند. صدا زدن مستقیم خزانه با فرستنده و مقدار تصادفی بیشتر به revert می‌رسد، پس یک handler جلویش گذاشتم که ورودی خام را به فراخوانی معتبر بین سه بازیگر تبدیل می‌کند:

```solidity
function move(uint256 from, uint256 to, uint256 amount) external {
    address a = actors[from % actors.length];
    address b = actors[to % actors.length];
    uint256 bal = vault.balanceOf(a);
    if (bal == 0) return;
    amount = bound(amount, 1, bal);
    vm.prank(a);
    vault.move(b, amount);
}
```

`deposit` و `withdraw` هم همین شکل‌اند. تست فقط handler را هدف می‌گیرد و {{< term "invariant" "invariant" >}} خزانه را بیان می‌کند:

```solidity
function setUp() public {
    vault = new Vault();
    handler = new VaultHandler(vault);
    targetContract(address(handler)); // only the handler is called
}

function invariant_SolventAndConserved() public view {
    uint256 sum;
    for (uint256 i = 0; i < handler.actorCount(); i++) {
        sum += vault.balanceOf(handler.actors(i));
    }
    assertEq(sum, vault.totalDeposits(), "sum of balances != totalDeposits");
    assertEq(address(vault).balance, vault.totalDeposits(), "ETH held != totalDeposits");
}
```

```
$ forge test
[PASS] testFuzz_DepositWithdrawRoundTrip(uint256,uint256) (runs: 256, μ: 147559, ~: 148410)
[PASS] testFuzz_MoveKeepsTotal(address,uint256) (runs: 256, μ: 160902, ~: 160345)
...
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
Ran 2 test suites in 11.92s (11.95s CPU time): 8 tests passed, 0 failed, 0 skipped (8 total tests)
(trimmed)
```

۱۲۸ هزار فراخوانی و صفر revert: handler کارش را درست انجام می‌دهد.

## یک باگ بکاریم و fuzzer پیدایش کند

حالا یک بازنویسی «صرفه‌جویی در یک SLOAD» برای `move` که عمداً نوشتم:

```solidity
uint256 toBal = balanceOf[to]; // "save an SLOAD" refactor (planted bug)
balanceOf[msg.sender] = bal - amount;
balanceOf[to] = toBal + amount;
```

وقتی `to == msg.sender` است، نوشتن دوم از موجودی قدیمی استفاده می‌کند و تفریق گم می‌شود. انتقال به خودتان پول می‌سازد.

```
$ forge test
Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 8.59ms (16.11ms CPU time)

[FAIL: sum of balances != totalDeposits: 10263 != 9377]
	[Sequence] (original: 10, shrunk: 2)
		sender=0x00000000000000000000000000000000000000A3 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=deposit(uint256,uint256) args=[0, 5659]
		sender=0x00000000000000000000000000000000000022Ea addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=move(uint256,uint256,uint256) args=[0, 0, 886]
 invariant_SolventAndConserved() (runs: 1, calls: 10, reverts: 0)
(trimmed)
```

invariant در همان اجرای اول شکست و {{< term "shrinking" "shrinking" >}} ده فراخوانی را به دو تا رساند: بازیگر صفر واریز می‌کند و بعد ۸۸۶ به بازیگر صفر منتقل می‌کند. اختلاف، 10263 − 9377، دقیقاً ۸۸۶ است. مجموعه‌ی تست واحد بالا، از جمله تست fuzz که به یک `to` تصادفی منتقل می‌کند، پاس شد: در ۲۵۶ اجرا هیچ آدرس تصادفی با `alice` برابر نشد. handler که بین سه بازیگر انتخاب می‌کند فوراً به آن رسید.

رفع باگ همان `balanceOf[to] += amount;` اصلی بعد از تفریق است. مثال نقض را به یک تست واحد ساده تبدیل کردم و دیدم که با باگ شکست می‌خورد (`assertion failed: 6545 != 5659`) و بدون آن پاس می‌شود:

```solidity
function test_MoveToSelfKeepsBalance() public {
    vm.startPrank(alice);
    vault.deposit{value: 5659}();
    vault.move(alice, 886);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), 5659);
}
```

## گزارش gas و coverage

```
$ forge test --match-contract VaultTest --gas-report
| Function Name                | Min             | Avg   | Median | Max   | # Calls |
| balanceOf                    |            2869 |  2869 |   2869 |  2869 |     773 |
| deposit                      |           23489 | 69663 |  69752 | 69752 |     520 |
| move                         |           32339 | 54114 |  54299 | 54311 |     258 |
| setPaused                    |           23813 | 25951 |  25951 | 28090 |       2 |
| totalDeposits                |            2425 |  2425 |   2425 |  2425 |     515 |
| withdraw                     |           24220 | 40917 |  40958 | 41030 |     259 |
(trimmed)
```

میانه‌ی deposit با رسید anvil در پست قبل (۶۹٬۷۵۲) یکی است و کمینه‌ی withdraw، یعنی ۲۴٬۲۲۰، همان عدد برداشت revertشده‌ی آنجاست. این‌ها واحد gas و قطعی‌اند، نه زمان.

```
$ forge coverage
| File                           | % Lines         | % Statements   | % Branches    | % Funcs        |
| src/Vault.sol                  | 100.00% (30/30) | 80.65% (25/31) | 25.00% (2/8)  | 100.00% (7/7)  |
| test/handlers/VaultHandler.sol | 92.86% (26/28)  | 96.30% (26/27) | 100.00% (2/2) | 80.00% (4/5)   |
(trimmed)
```

{{< term "code-coverage" "Coverage" >}} کار کرد (forge هشدار داد که optimizer را خاموش می‌کند). صد درصد خط‌ها، ۲۵ درصد شاخه‌ها. `--report debug` خط `revert ZeroAmount()` را با صفر بار اجرا نشان می‌دهد: درست است، هیچ تستی صفر نمی‌فرستد. `revert IsPaused()` را هم صفر نشان می‌دهد، با این‌که یک تست زیر `vm.expectRevert` به آن می‌رسد؛ دنبال دلیلش نرفتم. عدد شاخه‌ها را فهرست سؤال می‌خوانم، نه نمره.

## چند نکته‌ی مهم

- برای بازه، `bound` از `vm.assume` بهتر است: assume ورودی را دور می‌ریزد و ردهای زیاد تست را شکست می‌دهد.
- handlerی که بیشتر وقت‌ها revert می‌کند چیزی را تست نمی‌کند. ستون `reverts` را نگاه کنید.
- آدرس تصادفی تقریباً هیچ‌وقت با بازیگرهای شما برابر نمی‌شود. حالت‌های هم‌نامی (انتقال به خود، فرستنده و گیرنده‌ی یکسان) را عمداً بگذارید.
- هر مثال نقض را قبل از رفع باگ به تست واحد تبدیل کنید.

## تمرین

۱. `test_RevertWhen_ZeroDeposit` و `test_RevertWhen_ZeroWithdraw` را اضافه کنید و coverage را دوباره بگیرید.
۲. در `withdraw` باگ بکارید: `totalDeposits -= amount` را جا بیندازید. اول کدام assertion شکست می‌خورد؟
۳. بازیگر چهارمی اضافه کنید که قراردادی است و ETH را رد می‌کند، و در handler برایش `withdraw` بگذارید. invariant چه می‌گوید؟

## قدم بعدی

پست بعد: **توکن‌ها: ERC-20 و ERC-721**.
