+++
date = '2026-11-16T18:00:00+03:30'
draft = false
title = 'تست، fuzz و invariant با Foundry'
description = 'تست قرارداد Solidity با Foundry: تست واحد با cheatcode، fuzz با ورودی محدود، تست invariant با handler که باگ کاشته‌شده را پیدا می‌کند، gas و coverage.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "foundry", "testing", "fuzzing"]
cover = { image = "/images/covers/bc-foundry-testing-fuzzing.fa.png", alt = "تست، fuzz و invariant با Foundry", hiddenInSingle = true }
+++

در مقاله‌ی قبل vault را دستی امتحان کردم: یک واریز این‌جا، یک انتقال آن‌جا، و یک برداشت که شکست خورد. حس خوبی داشت، ولی تقریباً هیچ چیز را ثابت نمی‌کند. من شاید پنج حالت را امتحان کردم. یک قرارداد را هر کسی در دنیا می‌تواند با هر مبلغ، از هر آدرس و به هر ترتیب صدا بزند. و بعد از deploy نمی‌شود به همین راحتی وصله‌اش کرد: عوض‌کردن قرارداد بعد از deploy ساز و کار اضافه می‌خواهد، و در این فاصله پول آدم‌های دیگر دست آن است. برای همین تست این‌جا از یک سرویس بک‌اند معمولی مهم‌تر است.

در این مقاله vault مقاله‌ی [قبل](/fa/posts/bc-solidity-first-contract/) را با Foundry تست می‌کنم، و تست‌ها هم با خود Solidity نوشته می‌شوند. در سه قدم از «حالت‌هایی که خودم فکر کردم» می‌رسیم به «ماشین دنبال حالت‌هایی می‌گردد که به ذهنم نرسیده»: unit test، fuzz test و invariant test.

این ایده‌ها برای این وبلاگ تازه نیستند: [تست در Go: table-driven و benchmark](/fa/posts/go-testing-basics/)، [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/)، [Property-based testing](/fa/posts/eng-property-based-testing/) و [Fuzzing برای پیدا کردن باگ امنیتی](/fa/posts/sec-fuzzing/) آن‌ها را با زبان‌های دیگر گفته‌اند. چیز تازه این‌جا cheatcodeها و اجراکننده‌ی invariant است.

> همه‌ی مثال‌ها را با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64) اجرا کرده‌ام. پروژه‌ی مقاله‌ی قبل را بدون تغییر (همان `src/Vault.sol`) در یک پوشه‌ی محلی جدید کپی کردم و فقط تست اضافه کردم. اجرای fuzz تصادفی است، پس عددهای وابسته به آن و counterexampleی که شما می‌گیرید با مال من فرق می‌کند.

## unit test و cheatcode

تست یک قرارداد است. هر تابعی که اسمش با `test` شروع شود را `forge test` اجرا می‌کند و `setUp` پیش از هرکدام، روی حالت تازه، اجرا می‌شود. قرارداد تست نسخه‌ی خودش از vault را deploy می‌کند، پس owner آن است:

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

یک چیز عجیب است: تست خودش را جای `alice` جا می‌زند و ۱۰ ether را از هیچ به او می‌دهد. کار `vm` همین است. رابط {{< term "cheatcode" "cheatcode" >}} است: فراخوانی‌های ویژه‌ای که EVM تست خودش اجرا می‌کند و یک زنجیره‌ی واقعی هیچ‌وقت اجازه‌شان نمی‌دهد. این‌هایی که این‌جا استفاده شده‌اند:

- `vm.deal(alice, 10 ether)` موجودی ETH یک حساب را تعیین می‌کند.
- `vm.prank(alice)` باعث می‌شود فراخوانی **بعدی** طوری دیده شود که از `alice` آمده.
- `vm.expectRevert(...)` می‌گوید فراخوانی بعدی باید شکست بخورد، دقیقاً با همین خطا و همین آرگومان‌ها. اگر موفق شود یا جور دیگری شکست بخورد، تست رد می‌شود.
- `vm.expectEmit(...)` می‌گوید فراخوانی بعدی باید فلان event را emit کند. چهار boolean می‌گویند کدام بخش‌ها مقایسه شوند (سه topic و داده)، و آخرین آرگومان می‌گوید کدام قرارداد باید emit کند.

فایل تست‌های دیگری هم دارد، برای چک owner و برای «pause واریز را می‌بندد ولی برداشت را نه». این‌ها unit testهای معمولی‌اند: هرکدام یک حالت را چک می‌کند که از قبل به ذهنم رسیده بود.

## fuzz test

حالا سؤال این است: حالت‌هایی که به ذهنم نرسیده چه؟ به یک تست **پارامتر** بدهید تا یک تست {{< term "fuzzing" "fuzz" >}} شود. Foundry آن را بارها (به‌طور پیش‌فرض ۲۵۶ بار) با ورودی‌های تولیدشده صدا می‌زند تا assertionها را بشکند. ولی عددهای تصادفی معمولاً غول‌پیکرند و واریز 10^70 wei فقط revert می‌شود، بدون اینکه چیزی را تست کند. برای همین `bound` هر `uint256` را به بازه‌ای که ما می‌خواهیم می‌برد، تا اجراها مفید بمانند:

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

این تست یک قاعده را می‌گوید، نه یک حالت: «برای هر واریز و هر برداشتی که از آن بزرگ‌تر نباشد، موجودی vault، کیف‌پول Alice و ETH خود vault با هم جور درمی‌آید». تست `testFuzz_MoveKeepsTotal(address to, uint256 amount)` هم هست که واریز می‌کند و همه را به یک `to`ی تصادفی منتقل می‌کند، و چک می‌کند مجموع دو موجودی هنوز با `totalDeposits` برابر است.

## invariant test با handler

fuzz test هم هنوز یک شکل سناریو را تست می‌کند: واریز، بعد برداشت. باگ‌های واقعی اغلب دنباله‌ی بلندتری می‌خواهند: واریز، انتقال، انتقال، برداشت، به ترتیبی دلخواه. {{< term "invariant-testing" "invariant test" >}} این را پوشش می‌دهد. توابع تصادفی را به ترتیب تصادفی و بارها صدا می‌زند و بعد از هر فراخوانی یک ویژگی را چک می‌کند که همیشه باید درست باشد، یعنی {{< term "invariant" "invariant" >}}.

یک مشکل عملی هست. اگر fuzzer مستقیم vault را با فرستنده و مبلغ تصادفی صدا بزند، تقریباً همه‌ی فراخوانی‌ها revert می‌شوند (فرستنده موجودی ندارد، مبلغ زیاد است) و اتفاق جالبی نمی‌افتد. پس جلوی vault یک **handler** گذاشتم: قراردادی که تابع‌هایش ورودی تصادفی خام را به فراخوانی معتبر بین سه بازیگر ثابت (alice، bob، carol) تبدیل می‌کنند. این `move` آن است:

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

عددهای تصادفی دو بازیگر از سه تا را انتخاب می‌کنند و مبلغ با موجودی واقعی فرستنده محدود می‌شود. `deposit` و `withdraw` در handler هم همین شکل را دارند. بعد تست به Foundry می‌گوید **فقط** handler را صدا بزند و ویژگی را بیان می‌کند. یک vault سالم است اگر هر wei که نگه می‌دارد مال کسی باشد و کسی بیشتر از چیزی که vault دارد طلب نداشته باشد:

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

اجرای همه:

```
$ forge test
[PASS] testFuzz_DepositWithdrawRoundTrip(uint256,uint256) (runs: 256, μ: 147916, ~: 148416)
[PASS] testFuzz_MoveKeepsTotal(address,uint256) (runs: 256, μ: 160952, ~: 160766)
...
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
Ran 2 test suites in 12.55s (12.57s CPU time): 8 tests passed, 0 failed, 0 skipped (8 total tests)
(trimmed)
```

برای fuzz test، `runs: 256` تعداد ورودی‌های تولیدشده است، `μ` میانگین gas و `~` میانه. خط invariant می‌گوید forge ۱۲۸٬۰۰۰ فراخوانی انجام داده (۲۵۶ اجرا، هرکدام ۵۰۰ فراخوانی) و هیچ‌کدام revert نشده. عدد آخر مهم‌ترین است: نشان می‌دهد handler فراخوانی معتبر می‌سازد، پس fuzzer وقتش را صرف حالت‌های جالب می‌کند، نه ردشدن‌ها. (زمان و gas اجرای fuzz از هر اجرا تا اجرای بعد کمی فرق می‌کند.)

## یک باگ بکارید، بگذارید fuzzer پیدایش کند

همه سبز است. ولی سبز وقتی معنی دارد که تست بتواند قرمز هم بشود. پس عمداً یک باگ نوشتم، از نوعی که یک برنامه‌نویس خوش‌نیت موقع «صرفه‌جویی در یک SLOAD» (خواندن storage) در `move` می‌نویسد:

```solidity
uint256 toBal = balanceOf[to]; // "save an SLOAD" refactor (planted bug)
balanceOf[msg.sender] = bal - amount;
balanceOf[to] = toBal + amount;
```

اول موجودی گیرنده را می‌خواند، از فرستنده کم می‌کند و بعد موجودی قدیمی گیرنده به‌علاوه‌ی مبلغ را می‌نویسد. این درست است، مگر اینکه فرستنده و گیرنده یکی باشند: آن‌وقت نوشتن دوم از موجودی قدیمی استفاده می‌کند و کم‌کردن گم می‌شود. انتقال پول به خود شما پول می‌سازد. این را در یک نسخه‌ی موقت از پروژه کاشتم و تست‌ها را اجرا کردم:

```
$ forge test
Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 8.67ms (17.06ms CPU time)

[FAIL: sum of balances != totalDeposits: 15484560494319151770 != 15484560494319151755]
	[Sequence] (original: 15, shrunk: 2)
		sender=0x95Ff13e58c51Bc36a7cD2ba8CE27372e941BECd6 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=deposit(uint256,uint256) args=[687, 0]
		sender=0x00000000000000000000000000000000000008B9 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=move(uint256,uint256,uint256) args=[0, 0, 15]
 invariant_SolventAndConserved() (runs: 1, calls: 15, reverts: 0)
(trimmed)
```

- **`7 passed`:** همه‌ی unit و fuzz testها هنوز سبزند. حتی `testFuzz_MoveKeepsTotal` که پول را به یک `to`ی تصادفی می‌برد نفهمید: یک آدرس تصادفی عملاً هیچ‌وقت با `alice` برابر نمی‌شود، پس انتقال به خود هیچ‌وقت امتحان نشد.
- **`FAIL: sum of balances != totalDeposits`:** invariant در همان اجرای اول شکست. دو عدد ۱۵ با هم فرق دارند: دقیقاً مبلغی که منتقل شد.
- **`original: 15, shrunk: 2`:** دنباله‌ی شکست‌خورده ۱۵ فراخوانی داشت. بعد Foundry آن را {{< term "shrinking" "کوچک کرد" >}} (shrink)، یعنی فراخوانی‌های بی‌اهمیت را دور انداخت تا کوچک‌ترین دنباله‌ای که هنوز شکست می‌خورد بماند.
- **دو فراخوانی:** بازیگر ۰ واریز می‌کند، بعد بازیگر ۰ مبلغ ۱۵ را به بازیگر ۰ منتقل می‌کند (آرگومان‌های `move` برابر `[0, 0, 15]`: از ۰، به ۰، مبلغ ۱۵). باگ در دو خط. چون handler فقط از سه بازیگر انتخاب می‌کند، خیلی زود به انتقال به خود می‌رسد.

counterexample تصادفی است، پس مال شما عددهای دیگری خواهد داشت. وقتی باگ روشن شد، اصلاحش همان `balanceOf[to] += amount;` اصلی بعد از کم‌کردن است. عادتی که توصیه می‌کنم: اول counterexample را به یک unit test ساده تبدیل کنید و چک کنید با باگ شکست می‌خورد و بدون باگ پاس می‌شود. من این کار را با عددهای یک اجرای قبلی خودم کردم، و با وجود باگ شکست می‌خورد با `assertion failed: 6545 != 5659`:

```solidity
function test_MoveToSelfKeepsBalance() public {
    vm.startPrank(alice);
    vault.deposit{value: 5659}();
    vault.move(alice, 886);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), 5659);
}
```

۶۵۴۵ برابر ۵۶۵۹ + ۸۸۶ است: دقیقاً همان مبلغ ساخته‌شده. این تست برای همیشه در پروژه می‌ماند تا هیچ‌کس نتواند باگ را بی‌سروصدا برگرداند.

## گزارش gas و coverage

دو گزارش دیگر هم رایگان از forge می‌آید. اول `--gas-report` که نشان می‌دهد هر تابع در همه‌ی فراخوانی‌های تست‌ها چقدر gas خرج کرده:

```
$ forge test --match-contract VaultTest --gas-report
| Function Name                | Min             | Avg   | Median | Max   | # Calls |
| balanceOf                    |            2869 |  2869 |   2869 |  2869 |     773 |
| deposit                      |           23489 | 69663 |  69752 | 69752 |     520 |
| move                         |           32339 | 54103 |  54239 | 54311 |     258 |
| setPaused                    |           23813 | 25951 |  25951 | 28090 |       2 |
| totalDeposits                |            2425 |  2425 |   2425 |  2425 |     515 |
| withdraw                     |           24220 | 40922 |  40982 | 41030 |     259 |
(trimmed)
```

میانه‌ی deposit (۶۹٬۷۵۲) همان عددی است که رسید anvil در مقاله‌ی قبل نشان داد، و کمینه‌ی withdraw یعنی ۲۴٬۲۲۰ برابر gas همان برداشت revertشده‌ی آن‌جاست. این‌ها واحد gas هستند که قطعی است، نه زمان. میانگین توابعی که fuzz می‌شوند از اجرایی به اجرای دیگر کمی جابه‌جا می‌شود.

دوم `forge coverage` که نشان می‌دهد تست‌ها واقعاً کدام قسمت‌های کد را اجرا کرده‌اند:

```
$ forge coverage
| File                           | % Lines         | % Statements   | % Branches    | % Funcs        |
| src/Vault.sol                  | 100.00% (30/30) | 80.65% (25/31) | 25.00% (2/8)  | 100.00% (7/7)  |
| test/handlers/VaultHandler.sol | 92.86% (26/28)  | 96.30% (26/27) | 100.00% (2/2) | 80.00% (4/5)   |
(trimmed)
```

{{< term "code-coverage" "Coverage" >}} با forge کار می‌کند (هشدار داد که برای دقیق‌بودن اعداد، optimizer را خاموش می‌کند). همه‌ی خط‌های vault اجرا شدند، ولی فقط ۲ شاخه از ۸ شاخه. شاخه یعنی هر طرف یک `if`، و آن‌هایی که نیامده‌اند مسیرهای خطایند. `forge coverage --report debug` فهرستشان می‌کند: `revert ZeroAmount()` صفر بار اجرا شده، که درست است چون هیچ تستی مبلغ صفر نمی‌فرستد. `revert IsPaused()` را هم با صفر بار نشان می‌دهد، با اینکه یک تست درون `vm.expectRevert` به آن می‌رسد؛ نگشتم ببینم چرا گزارش آن را نمی‌شمارد. عدد شاخه را فهرستی از سؤال‌ها می‌خوانم که باید بپرسم، نه نمره.

## دام‌های fuzz و invariant

- **برای بازه‌ها `bound` را به `vm.assume` ترجیح دهید.** `assume` ورودی‌های نامناسب را دور می‌ریزد و اگر زیادی دور بریزد، تست از کمبود داده شکست می‌خورد. `bound` به‌جایش هر ورودی را در بازه می‌برد.
- **handlerی که بیشتر وقت‌ها revert می‌کند چیزی را تست نمی‌کند.** همیشه به عدد `reverts` نگاه کنید.
- **آدرس تصادفی تقریباً هیچ‌وقت با بازیگرهای شما یکی نمی‌شود.** حالت‌هایی مثل انتقال به خود یا فرستنده و گیرنده‌ی یکسان را باید عمداً بگذارید، همان‌طور که باگ کاشته‌شده نشان داد.
- **هر counterexample را قبل از رفع باگ به یک unit test تبدیل کنید.** وگرنه رفع فقط تا اجرای تصادفی بعدی کار می‌کند.

## تمرین

۱. `test_RevertWhen_ZeroDeposit` و `test_RevertWhen_ZeroWithdraw` را اضافه کنید و coverage را دوباره بگیرید. کدام شاخه‌ها سبز می‌شوند؟
۲. در `withdraw` باگ دیگری بکارید: `totalDeposits -= amount` را فراموش کنید. کدام assertion در invariant اول شکست می‌خورد؟
۳. بازیگر چهارمی اضافه کنید که یک قرارداد است و ETH را رد می‌کند، و برایش یک `withdraw` در handler بنویسید. invariant چه می‌گوید؟

## قدم بعدی

مقاله‌ی بعد «توکن‌ها: ERC-20 و ERC-721» است. vault موجودی‌ها را برای یک کار نگه می‌داشت؛ توکن «دفتر موجودی‌ها» را به استانداردی تبدیل می‌کند که هر کیف‌پول و صرافی می‌فهمد، و آن را با همین پروژه و همین ابزارها می‌سازیم.
