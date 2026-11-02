+++
date = '2026-11-15T18:00:00+03:30'
draft = false
title = 'اولین قرارداد با Solidity و Foundry'
description = 'اولین قرارداد Solidity با Foundry: یک خزانه‌ی کوچک ETH، چیدمان storage آن، دیپلوی روی زنجیره‌ی محلی anvil، فراخوانی با cast، یک revert و gas مصرفی.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "ethereum", "solidity", "foundry", "evm"]
cover = { image = "/images/covers/bc-solidity-first-contract.fa.png", alt = "اولین قرارداد با Solidity و Foundry", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/bc-evm-internals-rust/) bytecode دست‌نویس اجرا کردیم. کسی قرارداد را این‌طور نمی‌نویسد. در این پست یک {{< term "smart-contract" "قرارداد هوشمند" >}} واقعی با {{< term "solidity" "Solidity" >}} می‌نویسم، کامپایلش می‌کنم، خروجی کامپایلر را نگاه می‌کنم و روی یک زنجیره‌ی محلی اجرایش می‌کنم.

ابزار {{< term "foundry" "Foundry" >}} است: `forge` می‌سازد و تست می‌کند، `anvil` یک نود محلی اتریوم است و `cast` از ترمینال با آن حرف می‌زند. تست‌هایش هم با Solidity نوشته می‌شوند و این برای پست بعد مهم است. اگر [مدل حساب، nonce و جلوگیری از replay](/fa/posts/bc-account-model-nonce/) را خوانده باشید، قرارداد فقط یک نوع دیگر حساب است: حسابی که کد و storage خودش را دارد.

> اجرا با Foundry 1.8.7 روی macOS (arm64)؛ `forge` برای `pragma ^0.8.24` نسخه‌ی solc 0.8.38 را انتخاب و دانلود کرد. کد مثال محلی است و anvil فقط روی `127.0.0.1`. آدرس‌های پایین حساب‌های تست عمومی anvil هستند: همه آن‌ها را می‌شناسند و روی هیچ شبکه‌ی واقعی پولی ندارند.

## پروژه

```
$ forge init --no-git --shallow bc-solidity-foundry
$ rm src/Counter.sol test/Counter.t.sol script/Counter.s.sol
```

`forge init` پوشه‌های `src/`، `test/`، `script/` و فایل `foundry.toml` را می‌سازد و `forge-std` را (اینجا ۱.۳ مگابایت) زیر `lib/` می‌گذارد. شمارنده‌ی قالب را با یک خزانه (vault) عوض کردم: هر کس ETH واریز می‌کند، داخل خزانه موجودی‌اش را به دیگری منتقل می‌کند و برداشت می‌کند.

## قرارداد

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

constructor فقط یک بار، موقع دیپلوی، اجرا می‌شود. `msg.sender` کسی است که همین تابع را صدا زده، `msg.value` مقدار wei همراهش، و فقط تابع‌های `payable` wei قبول می‌کنند. متغیرهای `public` خودشان getter می‌گیرند. تا جایی که می‌دانم خطای سفارشی مثل `InsufficientBalance` از رشته‌ی revert ارزان‌تر است و داده‌ی نوع‌دار هم دارد. برداشت هیچ‌وقت متوقف نمی‌شود: کاربر همیشه می‌تواند خارج شود. و `withdraw` اول storage را عوض می‌کند و بعد ETH می‌فرستد؛ دلیلش پست جدایی درباره‌ی امنیت قرارداد دارد.

## کامپایلر چه ساخت

```
$ forge build --sizes
| Contract | Runtime Size (B) | Initcode Size (B) | Runtime Margin (B) | Initcode Margin (B) |
| Vault    | 2,931            | 3,022             | 21,645             | 46,130              |
```

اولین بایت‌های کد runtime همان dispatcher است، ساخته‌شده از opcodeهای پست قبل:

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

۳۲ بایت اول calldata را می‌خواند، ۲۲۴ بیت به راست شیفت می‌دهد تا ۴ بایت بماند و آن را با هر {{< term "function-selector" "function selector" >}} مقایسه می‌کند. `0x7d882097` همان `totalDeposits()` است:

```
$ forge inspect Vault methodIdentifiers
| balanceOf(address)    | 70a08231   |
| deposit()             | d0e30db0   |
| move(address,uint256) | 987ff31c   |
| totalDeposits()       | 7d882097   |
| withdraw(uint256)     | 2e1a7d4d   |
(trimmed)
```

و {{< term "storage-layout" "چیدمان storage" >}}، که تعیین می‌کند هر `SLOAD`/`SSTORE` به کجا دست می‌زند:

```
$ forge inspect Vault storageLayout
| Name          | Type                        | Slot | Offset | Bytes |
| owner         | address                     | 0    | 0      | 20    |
| paused        | bool                        | 0    | 20     | 1     |
| balanceOf     | mapping(address => uint256) | 1    | 0      | 32    |
| totalDeposits | uint256                     | 2    | 0      | 32    |
(Contract column trimmed)
```

`owner` و `paused` در اسلات صفر شریک‌اند. خود mapping چیزی در اسلات ۱ نمی‌نویسد؛ طبق مستندات Solidity مقدار کلید `k` در `keccak256(k . 1)` است.

## دیپلوی روی anvil و صحبت با آن

در یک ترمینال دیگر `anvil --host 127.0.0.1 --port 8545`. حساب‌هایش قفل نیستند، پس `--unlocked --from` کلیدی لازم ندارد:

```
$ export ETH_RPC_URL=http://127.0.0.1:8545
$ A0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266   # anvil test account 0
$ A1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8   # anvil test account 1
$ forge create src/Vault.sol:Vault --unlocked --from $A0 --broadcast
Deployer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
(transaction hash trimmed)

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

`cast send` تراکنش می‌سازد؛ `cast call` خواندن را محلی اجرا می‌کند و هزینه‌ای ندارد. فیلد `logs` در رسید واریز یک {{< term "event-log" "log" >}} داشت که topic اولش `keccak256("Deposited(address,uint256)")` است.

حالا storage را مستقیم بخوانیم. `cast index` اسلات mapping را حساب می‌کند:

```
$ cast storage $V 2
0x0000000000000000000000000000000000000000000000000de0b6b3a7640000
$ cast storage $V $(cast index address $A1 1)
0x00000000000000000000000000000000000000000000000003782dace9d90000
```

`0xde0b6b3a7640000` یعنی 1e18 wei و `0x3782dace9d90000` یعنی 0.25e18: دقیقاً همان کلمه‌های ۳۲ بایتی که `SLOAD` روی این اسلات‌ها برمی‌گرداند.

## یک revert و gas آن

حساب ۱ در خزانه ۰.۲۵ ETH دارد و ۵ تا می‌خواهد:

```
$ cast send $V "withdraw(uint256)" 5ether --unlocked --from $A1
Error: Failed to estimate gas: ... execution reverted: custom error 0xcf479181: ...
InsufficientBalance(250000000000000000 [2.5e17], 5000000000000000000 [5e18])
(trimmed)
```

{{< term "revert" "revert" >}} موقع تخمین gas اتفاق افتاد، پس چیزی فرستاده نشد. با سقف gas ثابت، تراکنش به‌هرحال در بلاک می‌رود:

```
$ cast send $V "withdraw(uint256)" 5ether --gas-limit 100000 --unlocked --from $A1
gasUsed              24220
status               0 (failed)
```

تراکنش شکست‌خورده هم در بلاک هست، فرستنده هزینه‌ی ۲۴٬۲۲۰ واحد {{< term "gas" "gas" >}} را داده و هیچ storageی عوض نشده. یک برداشت موفق ۰.۱ ETH، ۴۱٬۰۰۶ gas مصرف کرد. واریز از move گران‌تر بود، چون اولین واریز اسلات‌های صفر را غیرصفر می‌کند و طبق مستندات این گران‌ترین نوشتن است.

توقف فقط بایت offset بیست در اسلات صفر را عوض می‌کند:

```
$ cast send $V "setPaused(bool)" true --unlocked --from $A0
$ cast storage $V 0
0x000000000000000000000001f39fd6e51aad88f6f4ce6ab8827279cfffb92266
```

## چند نکته‌ی مهم

- چیدمان storage فرمت ذخیره‌ی قرارداد است. جابه‌جا کردن متغیرها معنای اسلات‌ها را عوض می‌کند؛ وقتی پای proxy وسط بیاید این مهم می‌شود.
- فراخوانی view با `cast call` ممکن است موفق شود در حالی که تراکنش شکست می‌خورد؛ حقیقت `status` رسید است.
- تخمین gas revert را قبل از ارسال پنهان می‌کند. برای کاربر خوب است، ولی برای دیدن خود revert سقف gas ثابت لازم است.
- این خزانه قرارداد آموزشی است و audit نشده. در production راه معمول یک کتاب‌خانه‌ی audit‌شده مثل OpenZeppelin است.

## تمرین

۱. بعد از `paused` یک `uint64 public lastDeposit` اضافه کنید، دوباره build کنید و `storageLayout` را ببینید: در اسلات صفر جا می‌شود؟
۲. به `withdraw` هم `whenNotPaused` بدهید و فکر کنید به چه کسی ضرر می‌زند.
۳. اسلات `$A0` را به‌جای `cast index` با `cast keccak` و `cast abi-encode` حساب کنید.

## قدم بعدی

پست بعد: **تست، fuzz و invariant با Foundry**.
