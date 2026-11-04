+++
date = '2026-11-15T18:00:00+03:30'
draft = false
title = 'اولین قرارداد با Solidity و Foundry'
description = 'اولین قرارداد Solidity با Foundry: یک خزانه‌ی کوچک ETH، چیدمان storage آن، دیپلوی روی زنجیره‌ی محلی anvil، فراخوانی با cast، یک revert و gas مصرفی.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "ethereum", "solidity", "foundry", "evm"]
cover = { image = "/images/covers/bc-solidity-first-contract.fa.png", alt = "اولین قرارداد با Solidity و Foundry", hiddenInSingle = true }
+++

چیزی در اتریوم برایم غافلگیرکننده بود: تراکنشی که شکست بخورد هم در بلاک می‌نشیند و فرستنده‌اش هم باید هزینه‌اش را بدهد. برای اینکه این را با چشم خودتان ببینید یک قرارداد واقعی لازم است، نه bytecodeی که در [مقاله‌ی قبل](/fa/posts/bc-evm-internals-rust/) دستی نوشتیم و روی یک مفسر اسباب‌بازی اجرا کردیم.

هیچ‌کس bytecode را دستی نمی‌نویسد. آدم‌ها به یک زبان برنامه‌نویسی می‌نویسند و کامپایلر آن را به bytecode تبدیل می‌کند. زبان اصلی اتریوم {{< term "solidity" "Solidity" >}} است. در این مقاله یک {{< term "smart-contract" "smart contract" >}} کوچک با Solidity می‌نویسم (یک vault که ETH آدم‌ها را نگه می‌دارد)، کامپایلش می‌کنم، نگاه می‌کنم کامپایلر چه ساخته، آن را روی زنجیره‌ای که روی لپ‌تاپ خودم اجرا می‌شود deploy می‌کنم و با آن حرف می‌زنم.

ابزار همه‌ی این کارها {{< term "foundry" "Foundry" >}} است که در واقع سه برنامه است:

- `forge` قراردادها را می‌سازد و تست می‌کند.
- `anvil` یک نود اتریوم محلی است: یک زنجیره‌ی آزمایشی خصوصی با چند حساب پول‌دار، که روی همین کامپیوتر اجرا می‌شود.
- `cast` یک کلاینت خط فرمان است که با نود حرف می‌زند: تراکنش می‌فرستد، مقدار می‌خواند و نتیجه را decode می‌کند.

تست‌های Foundry هم با Solidity نوشته می‌شوند، که برای مقاله‌ی بعد مهم است. اگر [مدل حساب](/fa/posts/bc-account-model-nonce/) را خوانده باشید، قرارداد فقط یک نوع حساب دیگر است: حسابی که کد و storage خودش را دارد.

> همه‌ی مثال‌ها را با Foundry 1.8.7 روی macOS (arm64) اجرا کرده‌ام. برای `pragma ^0.8.24` (پایین‌تر توضیح می‌دهم) `forge` خودش solc 0.8.38 را انتخاب و دانلود کرد. کد یک مثال محلی است و anvil فقط روی `127.0.0.1` گوش می‌دهد. آدرس‌های زیر حساب‌های آزمایشی عمومی anvil هستند: کلیدشان را همه می‌دانند، پس روی هیچ شبکه‌ی واقعی پولی در آن‌ها نیست.

## پروژه

```
$ forge init --no-git --shallow bc-solidity-foundry
$ rm src/Counter.sol test/Counter.t.sol script/Counter.s.sol
```

`forge init` یک پروژه می‌سازد: `src/` برای قراردادها، `test/` برای تست‌ها، `script/` برای اسکریپت‌های deploy، فایل تنظیمات `foundry.toml` و یک نسخه از کتابخانه‌ی کمکی `forge-std` زیر `lib/`. یک قرارداد شمارنده‌ی نمونه هم می‌گذارد که پاکش کردم و به‌جایش یک vault نوشتم: آدم‌ها ETH واریز می‌کنند، موجودی را داخل vault به هم منتقل می‌کنند و برداشت می‌کنند.

## قرارداد

قبل از کد، دو کلمه. ETH سکه‌ی اتریوم است. کوچک‌ترین واحدش {{< term "wei" "wei" >}} است: یک ETH برابر ۱۰^۱۸ wei است، پس قراردادها همیشه با wei و با عدد صحیح حساب می‌کنند. و کل قرارداد فهرستی بلند از قاعده‌هاست که هیچ‌کس نمی‌تواند خمشان کند، چون هر نود همان کد را اجرا می‌کند.

```solidity
contract Vault {
    address public owner;   // slot 0 (20 bytes)
    bool public paused;     // slot 0 too (1 byte, packed after owner)
    mapping(address => uint256) public balanceOf; // slot 1
    uint256 public totalDeposits;                 // slot 2

    error ZeroAmount();
    error NotOwner();
    error IsPaused();
    error InsufficientBalance(uint256 available, uint256 requested);
    error TransferFailed();

    event Deposited(address indexed account, uint256 amount);
    event Withdrawn(address indexed account, uint256 amount);
    event Moved(address indexed from, address indexed to, uint256 amount);
    event PausedSet(bool paused);

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert IsPaused();
        _;
    }

    function deposit() external payable whenNotPaused {
        if (msg.value == 0) revert ZeroAmount();
        balanceOf[msg.sender] += msg.value;
        totalDeposits += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external {
        uint256 bal = balanceOf[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (amount > bal) revert InsufficientBalance(bal, amount);
        // effects before the external call
        balanceOf[msg.sender] = bal - amount;
        totalDeposits -= amount;
        emit Withdrawn(msg.sender, amount);
        (bool ok, ) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function move(address to, uint256 amount) external whenNotPaused {
        uint256 bal = balanceOf[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (amount > bal) revert InsufficientBalance(bal, amount);
        balanceOf[msg.sender] = bal - amount;
        balanceOf[to] += amount;
        emit Moved(msg.sender, to, amount);
    }

    function setPaused(bool p) external onlyOwner {
        paused = p;
        emit PausedSet(p);
    }
}
```

(فایل با یک کامنت مجوز و `pragma solidity ^0.8.24;` هم شروع می‌شود، که به کامپایلر می‌گوید هر نسخه‌ی 0.8.x از 0.8.24 به بعد قبول است. این دو را بالا نیاورده‌ام.)

اگر Go یا Rust بلد باشید، بیشتر این کد خودبه‌خود خوانا است. این‌ها چیزهای تازه‌اند:

- **متغیرهای state** در بالا (`owner`، `paused`، `balanceOf`، `totalDeposits`) در storage قرارداد زندگی می‌کنند، همان دفترچه‌ی دائمی مقاله‌ی قبل. `mapping` نقشه‌ی کلید-مقدار Solidity است. `public` باعث می‌شود کامپایلر برای آن متغیر یک تابع خواندن مجانی بسازد، پس `balanceOf(address)` بدون اینکه ننوشته باشیمش وجود دارد.
- **سازنده (constructor)** دقیقاً یک بار اجرا می‌شود، وقتی قرارداد deploy می‌شود. این‌جا ثبت می‌کند چه کسی deploy کرده تا `owner` باشد.
- **`msg.sender`** حسابی است که این تابع را صدا زده و **`msg.value`** مقدار wei است که همراه فراخوانی فرستاده شده. فقط تابع‌هایی که `payable` باشند wei قبول می‌کنند؛ فراخوانی‌ای که پول همراهش باشد و تابعش payable نباشد شکست می‌خورد.
- **`external`** یعنی «از بیرون قرارداد قابل صدا زدن».
- **`modifier`** یک چک قابل‌استفاده‌ی مجدد است که دور یک تابع پیچیده می‌شود. در `onlyOwner` خط `_;` جایی است که بدنه‌ی تابع اجرا می‌شود. پس `setPaused` اول فرستنده را چک می‌کند و بعد کارش را می‌کند.
- **خطاهای سفارشی** مثل `InsufficientBalance(available, requested)` چیزی هستند که `revert` پرتاب می‌کند. داده‌ی تایپ‌دار حمل می‌کنند و تا جایی که می‌دانم gas کمتری از revert قدیمی با پیام متنی می‌گیرند.
- **رویدادها (event)** (`emit Deposited(...)`) یک رکورد در log تراکنش می‌نویسند. قراردادها نمی‌توانند log خودشان را بخوانند؛ رویدادها برای این‌اند که برنامه‌های بیرونی، مثل یک سایت یا indexer، ارزان بفهمند چه اتفاقی افتاده.

دو تصمیم طراحی هم هرکدام یک جمله می‌ارزد. برداشت هیچ‌وقت متوقف نمی‌شود، پس کاربر همیشه می‌تواند برود. و `withdraw` storage را **قبل از** فرستادن ETH به‌روز می‌کند و فراخوانی بیرونی را آخر می‌گذارد. دلیلش یک حمله‌ی کلاسیک است و بعداً مقاله‌ی جداگانه‌ی امنیت قرارداد دارد.

## کامپایلر چه ساخت

`forge build --sizes` کامپایل می‌کند و اندازه‌ی کد را نشان می‌دهد:

```
$ forge build --sizes
| Contract | Runtime Size (B) | Initcode Size (B) | Runtime Margin (B) | Initcode Margin (B) |
| Vault    | 2,931            | 3,022             | 21,645             | 46,130              |
```

«Runtime» کدی است که روی زنجیره می‌ماند و در هر فراخوانی اجرا می‌شود: ۲٬۹۳۱ بایت. «Initcode» کدی است که یک بار موقع deploy اجرا می‌شود، constructor را اجرا می‌کند و کد runtime را برمی‌گرداند تا ذخیره شود. ستون‌های margin نشان می‌دهند تا سقف اندازه چقدر جا مانده: ۲٬۹۳۱ + ۲۱٬۶۴۵ = ۲۴٬۵۷۶ بایت برای کد runtime و ۳٬۰۲۲ + ۴۶٬۱۳۰ = ۴۹٬۱۵۲ برای initcode.

حالا ارتباط با مقاله‌ی قبل. اولین بایت‌های کد runtime یک **dispatcher** است: برنامه‌ی کوچکی که تصمیم می‌گیرد کدام تابع صدا زده شده. از همان opcodeهایی ساخته شده که آن‌جا دیدیم. `cast disassemble` بایت‌کد را به opcodeهای خوانا برمی‌گرداند (این‌جا چند بایت اول کد runtime قرارداد Vault):

```
$ cast disassemble 0x60806040526004361061007a575f3560e01c80637d882097
00000000: PUSH1 0x80
00000002: PUSH1 0x40
00000004: MSTORE
00000005: PUSH1 0x04
00000007: CALLDATASIZE
00000008: LT
00000009: PUSH2 0x007a
0000000c: JUMPI
0000000d: PUSH0
0000000e: CALLDATALOAD
0000000f: PUSH1 0xe0
00000011: SHR
00000012: DUP1
00000013: PUSH4 0x7d882097
```

بخوانیمش:

- `PUSH1 0x80, PUSH1 0x40, MSTORE` مقدار 0x80 را در جای 0x40 memory می‌نویسد، یک مقدار حسابداری («free memory pointer») که هر برنامه‌ی Solidity اول از همه آماده می‌کند.
- `PUSH1 0x04, CALLDATASIZE, LT, PUSH2 0x007a, JUMPI` یعنی: اگر ورودی کوتاه‌تر از ۴ بایت است به جای 0x7a بپر، که جایی برای فراخوانی‌هایی است که با هیچ تابعی نمی‌خوانند.
- `PUSH0, CALLDATALOAD, PUSH1 0xe0, SHR` ۳۲ بایت اول ورودی را می‌خواند و ۲۲۴ بیت (0xe0) به راست می‌برد، که فقط ۴ بایت اول را باقی می‌گذارد.
- این ۴ بایت یکی‌یکی با {{< term "function-selector" "function selector" >}} هر تابع مقایسه می‌شود. `PUSH4 0x7d882097` اولین کاندیدا است و selector تابع `totalDeposits()` است.

selector هر تابع، ۴ بایت اول hash {{< term "keccak-256" "Keccak-256" >}} از امضای تابع است، مثل `totalDeposits()`. فراخواننده با همین می‌گوید کدام تابع را می‌خواهد: ۴ بایت اول calldata. کامپایلر می‌تواند همه را فهرست کند:

```
$ forge inspect Vault methodIdentifiers
| balanceOf(address)    | 70a08231   |
| deposit()             | d0e30db0   |
| move(address,uint256) | 987ff31c   |
| totalDeposits()       | 7d882097   |
| withdraw(uint256)     | 2e1a7d4d   |
(trimmed)
```

(`owner()`، `paused()` و `setPaused(bool)` را حذف کرده‌ام.) قالب این calldata، یعنی selector ۴ بایتی و بعد آرگومان‌ها، بخشی از {{< term "abi" "ABI" >}} قرارداد است.

کامپایلر تصمیم می‌گیرد هر متغیر state کجا بنشیند. این {{< term "storage-layout" "چیدمان storage" >}} است و مشخص می‌کند هر `SLOAD` و `SSTORE` به کدام خانه دست می‌زند:

```
$ forge inspect Vault storageLayout
| Name          | Type                        | Slot | Offset | Bytes |
| owner         | address                     | 0    | 0      | 20    |
| paused        | bool                        | 0    | 20     | 1     |
| balanceOf     | mapping(address => uint256) | 1    | 0      | 32    |
| totalDeposits | uint256                     | 2    | 0      | 32    |
(Contract column trimmed)
```

هر خانه (slot) ۳۲ بایت است. `owner` ۲۰ تا از آن را می‌گیرد، پس کامپایلر `paused` (۱ بایت) را در همان خانه‌ی ۰ و از بایت ۲۰ می‌گذارد. این یک خانه‌ی storage صرفه‌جویی می‌کند و در نتیجه gas. mapping حالت خاصی است: خودش در خانه‌ی ۱ چیزی ذخیره نمی‌کند. طبق مستندات Solidity، مقدار کلید `k` در خانه‌ی `keccak256(k . 1)` است، یعنی کلید و عدد ۱ را کنار هم می‌گذارند و hash می‌گیرند. mapping یک جدول hash است که روی کل فضای 2^256 خانه پخش شده.

## deploy روی anvil و صحبت با آن

در ترمینال دیگری زنجیره‌ی محلی را با `anvil --host 127.0.0.1 --port 8545` راه می‌اندازم. فهرستی از حساب‌های آزمایشی پول‌دار چاپ می‌کند. کلیدهایشان داخل anvil باز است، پس می‌توانم به ابزارها بگویم `--unlocked --from <address>` و با هیچ کلید خصوصی‌ای کار نکنم:

```
$ export ETH_RPC_URL=http://127.0.0.1:8545
$ A0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266   # anvil test account 0
$ A1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8   # anvil test account 1
$ forge create src/Vault.sol:Vault --unlocked --from $A0 --broadcast
Deployer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
(transaction hash trimmed)
```

`ETH_RPC_URL` به همه‌ی ابزارها می‌گوید نود کجاست. `forge create` قرارداد را کامپایل می‌کند و تراکنش deploy را می‌فرستد، و حالا قرارداد یک آدرس دارد. این آدرس از آدرس و nonce کسی که deploy کرده ساخته می‌شود، پس روی یک anvil تازه همیشه همین است. حالا ازش استفاده می‌کنم:

```
$ V=0x5FbDB2315678afecb367f032d93F642f64180aa3
$ cast send $V "deposit()" --value 1ether --unlocked --from $A0
gasUsed              69752
status               1 (success)
(trimmed)
$ cast call $V "totalDeposits()(uint256)"
1000000000000000000 [1e18]
$ cast send $V "move(address,uint256)" $A1 0.25ether --unlocked --from $A0
gasUsed              54287
status               1 (success)
(trimmed)
```

- **`cast send ... deposit()`:** یک تراکنش واقعی می‌فرستد که `deposit()` را با ۱ ETH همراه صدا می‌زند. در بلاک می‌نشیند و رسید می‌گوید `status 1` و {{< term "gas" "gas" >}} مصرفی را نشان می‌دهد: ۶۹٬۷۵۲. فیلد `logs` رسید یک {{< term "event-log" "log" >}} دارد که topic اولش hash Keccak-256 از `Deposited(address,uint256)` است؛ با `cast keccak` چکش کردم.
- **`cast call ... totalDeposits()`:** این تراکنش نیست. از نود می‌خواهد تابع را محلی اجرا کند و جواب را برگرداند؛ چیزی نوشته نمی‌شود و gas هم خرج نمی‌شود. جواب یک ETH است، به wei.
- **`cast send ... move`:** ۰٫۲۵ ETH را از موجودی حساب ۰ به موجودی حساب ۱ داخل vault منتقل می‌کند. هیچ ETH از قرارداد بیرون نمی‌رود.

حالا storage را مستقیم بخوانیم، بدون هیچ تابعی. `cast index` خانه‌ی یک عضو mapping را برایمان حساب می‌کند:

```
$ cast storage $V 2
0x0000000000000000000000000000000000000000000000000de0b6b3a7640000
$ cast storage $V $(cast index address $A1 1)
0x00000000000000000000000000000000000000000000000003782dace9d90000
```

خانه‌ی ۲ همان `totalDeposits` است: `0xde0b6b3a7640000` برابر ۱۰^۱۸ است، یعنی یک ETH به wei. دستور دوم خانه‌ی `balanceOf[A1]` را می‌خواند و `0x3782dace9d90000` برابر ۰٫۲۵ × ۱۰^۱۸ است. این‌ها دقیقاً همان کلمه‌های ۳۲ بایتی‌اند که یک `SLOAD` روی آن خانه‌ها برمی‌گرداند. چیزی که در مفسر Rust دیدیم همان است که واقعاً روی زنجیره هست.

## یک revert و gas آن

حالا شکستی که اول مقاله گفتم. حساب ۱ در vault ۰٫۲۵ ETH دارد و می‌خواهد ۵ برداشت کند:

```
$ cast send $V "withdraw(uint256)" 5ether --unlocked --from $A1
Error: Failed to estimate gas: ... execution reverted: custom error 0xcf479181: ...
InsufficientBalance(250000000000000000 [2.5e17], 5000000000000000000 [5e18])
(trimmed)
```

خطا برایمان decode شده: قرارداد رد کرد و خطای سفارشی ما هر دو عدد را حمل می‌کند، چقدر موجود است و چقدر خواسته شد. ولی به اولین کلمه‌ها نگاه کنید، «Failed to estimate gas». `cast` قبل از فرستادن از نود می‌پرسد این تراکنش چقدر gas می‌خواهد، و همان اجرای آزمایشی revert شد. یعنی {{< term "revert" "revert" >}} قبل از فرستادن اتفاق افتاد. برای اینکه یک تراکنش شکست‌خورده را واقعاً در بلاک ببینیم، سقف gas را ثابت می‌دهم تا تخمینی در کار نباشد:

```
$ cast send $V "withdraw(uint256)" 5ether --gas-limit 100000 --unlocked --from $A1
gasUsed              24220
status               0 (failed)
```

این همان جمله‌ی اول مقاله است. تراکنش در بلاک است، رسیدش `status 0` دارد، فرستنده برای ۲۴٬۲۲۰ gas پول داد و هیچ storage‌ای عوض نشد. برای مقایسه، یک برداشت موفق ۰٫۱ ETH، ۴۱٬۰۰۶ gas مصرف کرد.

چرا deposit از move بیشتر gas گرفت؟ deposit دو خانه‌ی storage را نوشت که قبلاً خالی بودند: موجودی فرستنده و `totalDeposits`. طبق مستندات، تبدیل یک خانه از صفر به غیرصفر گران‌ترین نوع نوشتن است. move فقط یک خانه از این نوع نوشت (موجودی گیرنده)، به‌علاوه‌ی یک خانه که از قبل غیرصفر بود.

آخرین نگاه به storage. pause کردن فقط بایت جای ۲۰ از خانه‌ی ۰ را عوض می‌کند:

```
$ cast send $V "setPaused(bool)" true --unlocked --from $A0
$ cast storage $V 0
0x000000000000000000000001f39fd6e51aad88f6f4ce6ab8827279cfffb92266
```

۴۰ رقم هگز آخر (۲۰ بایت) آدرس owner است، یعنی حساب ۰. درست پیش از آن، `01` یعنی `paused = true`. دو متغیر در یک خانه، همان‌طور که جدول چیدمان گفته بود.

## دام‌های اولین قرارداد

- **چیدمان storage قالب ذخیره‌ی قرارداد است.** اگر ترتیب متغیرهای state را عوض کنید، در هر خانه متغیر دیگری می‌نشیند. در یک deploy تازه بی‌ضرر است، ولی وقتی قرارداد با proxy ارتقا پیدا می‌کند خطرناک می‌شود؛ proxyها بعداً در مجموعه می‌آیند.
- **`cast call` ثابت نمی‌کند تراکنش کار می‌کند.** فراخوانی خواندنی می‌تواند جایی موفق شود که تراکنش واقعی شکست می‌خورد؛ `status` در رسید حقیقت است.
- **تخمین gas revertها را قایم می‌کند.** برای کاربر مهربان است، ولی اگر می‌خواهید revert را مطالعه کنید یا تراکنش شکست‌خورده در بلاک باشد، سقف gas ثابت لازم دارید.
- **این vault قرارداد آموزشی است، نه ممیزی‌شده.** برای کد واقعی، راه معمول کتابخانه‌ی ممیزی‌شده‌ای مثل OpenZeppelin است.

## تمرین

۱. فیلد `uint64 public lastDeposit` را درست بعد از `paused` اضافه کنید، دوباره build کنید و `storageLayout` را نگاه کنید. آیا خانه‌ی ۰ را با owner شریک می‌شود؟
۲. modifier به نام `whenNotPaused` را به `withdraw` اضافه کنید و فکر کنید این به چه کسی ضرر می‌زند.
۳. خانه‌ی `$A0` را به‌جای `cast index` با `cast keccak` و `cast abi-encode` حساب کنید و ببینید همان خانه را می‌گیرید.

## قدم بعدی

مقاله‌ی بعد «تست، fuzz و invariant با Foundry» است. این vault را فقط دستی امتحان کردیم؛ بعد از این می‌گذاریم خود ماشین هزاران ورودی را برایمان امتحان کند.
