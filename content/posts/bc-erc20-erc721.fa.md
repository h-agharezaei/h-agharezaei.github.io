+++
date = '2026-11-17T18:00:00+03:30'
draft = false
title = 'توکن‌ها: ERC-20 و ERC-721'
description = 'ERC-20 و ERC-721 دست‌نویس با Solidity: موجودی به شکل mapping، allowance، انتقال امن NFT، تست با Foundry و خواندن رویدادهای Transfer با cast روی anvil.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "erc20", "erc721", "foundry"]
cover = { image = "/images/covers/bc-erc20-erc721.fa.png", alt = "توکن‌ها: ERC-20 و ERC-721", hiddenInSingle = true }
+++

وقتی برای دوستتان «یک توکن می‌فرستید»، دقیقاً چه چیزی جابه‌جا می‌شود؟ نه سکه‌ای هست، نه فایلی، نه چیزی که از جایی به جای دیگر برود. و کیف‌پول دوستتان از کجا می‌فهمد چیزی رسیده؟

جواب از واژه‌هایی که دورش هست ساده‌تر است. توکن قابلیت ویژه‌ی اتریوم نیست. یک smart contract معمولی است که یک دفتر نگه می‌دارد، مثل vault دو مقاله‌ی قبل، و از یک توافق عمومی پیروی می‌کند که می‌گوید چه تابع‌ها و eventهایی باید داشته باشد. اگر همه‌ی توکن‌ها از یک توافق پیروی کنند، هر کیف‌پول و صرافی می‌تواند با هر توکنی حرف بزند، بدون اینکه چیز خاصی درباره‌اش بداند. به این توافق‌ها استانداردهای ERC می‌گویند (ERC یعنی Ethereum Request for Comments و هرکدام شماره‌ای دارد).

در این مقاله دو استاندارد رایج را دستی می‌سازم: توکن **مثلی** (fungible) {{< term "erc-20" "ERC-20" >}}، که هر واحدش با واحد دیگر یکی است (مثل پول: یکی از ۱۰ DEMO من با یکی از مال شما فرقی ندارد)، و {{< term "erc-721" "ERC-721" >}} یا **NFT**، که هر توکنش یکتاست و شناسه‌ی خودش را دارد (مثل بلیت شماره‌دار). از همان پروژه‌ی [مقاله‌ی تست](/fa/posts/bc-foundry-testing-fuzzing/) استفاده می‌کنم، پس vault و تست‌هایش هنوز آن‌جا هستند.

هر دو قرارداد را دستی نوشتم تا همه‌ی خط‌ها را ببینیم. قراردادهای آموزشی‌اند، نه ممیزی‌شده. در محیط واقعی انتخاب معمول یک کتابخانه‌ی ممیزی‌شده مثل OpenZeppelin است، نه کدی از یک وبلاگ.

> همه‌ی مثال‌ها را با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64) اجرا کرده‌ام. پروژه‌ی مقاله‌ی قبل (با vault و تست‌هایش) را در یک پوشه‌ی محلی جدید کپی کردم و `src/DemoToken.sol`، `src/DemoNFT.sol`، تست‌هایشان و `script/Deploy.s.sol` را اضافه کردم. anvil روی `127.0.0.1` اجرا می‌شود و آدرس‌ها حساب‌های آزمایشی عمومی anvil هستند.

## ERC-20 یک mapping است

هسته‌ی توکن مثلی یک جدول است: برای هر آدرس، چند واحد دارد. در Solidity این یک `mapping` است. قرارداد این است، بدون constructor، تابع mint و تعریف خطاها:

```solidity
contract DemoToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18; // display hint only: balances are integers

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    address public immutable minter;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        if (spender == address(0)) revert ZeroAddress();
        allowance[msg.sender][spender] = value; // overwrites, see the post about the race
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) { // max means "unlimited", a common convention
            if (allowed < value) revert InsufficientAllowance(msg.sender, allowed, value);
            allowance[from][msg.sender] = allowed - value;
        }
        _transfer(from, to, value);
        return true;
    }

    function _transfer(address from, address to, uint256 value) internal {
        if (to == address(0)) revert ZeroAddress();
        uint256 bal = balanceOf[from];
        if (bal < value) revert InsufficientBalance(from, bal, value);
        balanceOf[from] = bal - value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }
    // constructor, mint, _mint and errors trimmed
}
```

(کامنت داخل `approve` به همان race اشاره می‌کند که پایین‌تر توضیح می‌دهم، نه به مقاله‌ای جدا.) بخش‌های مهم را بخوانیم.

**انتقال یعنی دو ویرایش در یک جدول.** `_transfer` از یک عضو mapping کم می‌کند، به یکی دیگر اضافه می‌کند و event به نام `Transfer` را emit می‌کند. هیچ سکه‌ای جایی نمی‌رود؛ «توکن» فقط یک عدد در storage همین قرارداد است. یعنی اگر قرارداد غلط باشد، پول غلط است، چون چیز دیگری وجود ندارد. ساخت توکن تازه (mint) هم به شکل یک `Transfer` از آدرس صفر گزارش می‌شود. تا جایی که می‌دانم، ردکردن انتقال به `address(0)` انتخاب خودم است و استاندارد آن را لازم نمی‌داند.

**`decimals` فقط برای نمایش است.** قرارداد فقط عدد صحیح می‌شناسد. `decimals = 18` به کیف‌پول‌ها می‌گوید `1000000000000000000` را به شکل `1` نشان بدهند، درست مثل wei و ETH. توکنی با `decimals = 6` و توکنی با ۱۸ می‌توانند یک عدد صحیح را نگه دارند و مقدارهای خیلی متفاوتی نشان بدهند. پس کدی که توکن را بین سیستم‌ها جابه‌جا می‌کند باید `decimals()` را بخواند و هیچ‌وقت فرضش نکند.

**`approve` و `transferFrom` اجازه می‌دهند کس دیگری توکن شما را خرج کند.** `transfer` فقط توکن خودتان را جابه‌جا می‌کند و فقط خودتان می‌توانید صدایش بزنید. ولی اگر یک قرارداد، مثلاً یک صرافی، باید از شما توکن بردارد چه؟ اول `approve(exchange, 100)` را صدا می‌زنید: «این خرج‌کننده تا ۱۰۰ تا از مال من را می‌تواند بردارد». بعداً صرافی `transferFrom(you, somewhere, 60)` را صدا می‌زند که **allowance** را چک و کم می‌کند و بعد توکن را جابه‌جا می‌کند. allowance همان mapping تو در تو است: صاحب، بعد خرج‌کننده، بعد مقدار. مقدار `type(uint256).max` طبق قرارداد رایج یعنی «نامحدود» و هیچ‌وقت کم نمی‌شود.

**`approve` یک دام شناخته‌شده دارد.** مقدار قبلی را بازنویسی می‌کند. فرض کنید Alice به Bob اجازه‌ی ۱۰۰ داده و حالا می‌خواهد آن را به ۵۰ کم کند. تا جایی که از این مشکل شناخته‌شده می‌دانم، Bob می‌تواند {{< term "mempool" "mempool" >}} (فهرست تراکنش‌های منتظر) را ببیند، آمدن تغییر او را بفهمد، سریع ۱۰۰ را قبل از رسیدن آن خرج کند و بعد ۵۰ جدید را هم خرج کند. یعنی ۱۵۰ به‌جای حداکثر ۱۰۰. راه‌حل‌های رایج این است که اول allowance را صفر کنید، یا از تابع‌های افزایش allowance که بعضی کتابخانه‌ها دارند استفاده کنید. این یک {{< term "race-condition" "race" >}} روی ترتیب تراکنش‌هاست، نه باگ حساب.

## یک ERC-721 کمینه

NFT به آن معنا برای هر آدرس موجودی نگه نمی‌دارد؛ برای **هر شناسه‌ی توکن یک صاحب** نگه می‌دارد. هر شناسه یک چیز یکتاست. بخش جالب این است که چه کسی می‌تواند توکن را جابه‌جا کند، و انتقال «امن»:

```solidity
function transferFrom(address from, address to, uint256 tokenId) public {
    address owner = ownerOf(tokenId);
    if (from != owner) revert WrongFrom();
    if (to == address(0)) revert ZeroAddress();
    if (msg.sender != owner && msg.sender != getApproved[tokenId] && !isApprovedForAll[owner][msg.sender]) {
        revert NotAuthorized();
    }
    balanceOf[from] -= 1;
    balanceOf[to] += 1;
    _owners[tokenId] = to;
    delete getApproved[tokenId]; // an approval is for one transfer by the current owner
    emit Transfer(from, to, tokenId);
}

function safeTransferFrom(address from, address to, uint256 tokenId, bytes memory data) public {
    transferFrom(from, to, tokenId);
    if (to.code.length > 0) {
        try IERC721Receiver(to).onERC721Received(msg.sender, from, tokenId, data) returns (bytes4 ret) {
            if (ret != IERC721Receiver.onERC721Received.selector) revert UnsafeRecipient(to);
        } catch {
            revert UnsafeRecipient(to);
        }
    }
}
```

`transferFrom` در سه حالت اجازه‌ی جابه‌جایی می‌دهد: فراخواننده صاحب است، یا برای همین یک توکن تأیید شده (`getApproved`)، یا صاحب او را برای همه‌ی توکن‌ها تأیید کرده (`isApprovedForAll`). بعد از جابه‌جایی، تأیید تک‌توکنی پاک می‌شود، پس فقط یک بار کار می‌کند.

حالا بخش «امن». قراردادی که از NFT چیزی نمی‌داند می‌تواند یکی را دریافت کند و بعد هیچ تابعی برای فرستادنش نداشته باشد: NFT برای همیشه همان‌جا گیر می‌کند. `safeTransferFrom` جلوی این را می‌گیرد. اگر گیرنده قرارداد باشد (`to.code.length > 0`)، `onERC721Received` را روی آن صدا می‌زند و گیرنده باید با selector خود همین تابع جواب بدهد، که یعنی «بله، می‌دانم با این چه کنم». اگر چیز دیگری جواب بدهد یا چنین تابعی نداشته باشد، کل انتقال revert می‌شود و هیچ چیز جابه‌جا نمی‌شود.

تست‌ها هر دو طرف را ثابت می‌کنند. `transferFrom` به یک قرارداد ساده موفق می‌شود و NFT همان‌جا گیر می‌کند؛ `safeTransferFrom` به همان قرارداد revert می‌شود؛ و گیرنده‌ای که درست جواب بدهد توکن شماره ۲ را می‌گیرد. تست دیگری چک می‌کند که شناسه‌ی رابط `IERC721` برابر `0x80ac58cd` است. این همان مقداری است که قرارداد از `supportsInterface` (مکانیزم ERC-165) برمی‌گرداند تا قراردادهای دیگر بتوانند بپرسند «آیا ERC-721 بلدی؟».

## تست‌ها

طبیعی‌ترین ویژگی برای یک ERC-20 همان {{< term "invariant-testing" "invariant" >}} کلاسیک است: `totalSupply` همیشه با مجموع همه‌ی موجودی‌ها برابر است. مثل مقاله‌ی قبل، یک handler بین سه دارنده فراخوانی معتبر می‌سازد: انتقال ساده، approve و بعد `transferFrom`، و mint. پروژه حالا همه‌ی تست‌ها، از جمله مال vault، را اجرا می‌کند:

```
$ forge test
[PASS] testFuzz_TransferConservesSupply(address,uint256) (runs: 256, μ: 102037, ~: 102401)
[PASS] test_TransferFromSpendsAllowance() (gas: 165724)
[PASS] testFuzz_MintedIdsHaveOneOwner(uint8) (runs: 256, μ: 2987908, ~: 650912)
[PASS] test_InterfaceId() (gas: 248)
[PASS] test_SafeTransferChecksReceiver() (gas: 608315)
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
[PASS] invariant_TotalSupplyEqualsSumOfBalances() (runs: 256, calls: 128000, reverts: 0)
Ran 5 test suites in 13.33s (26.17s CPU time): 19 tests passed, 0 failed, 0 skipped (19 total tests)
(trimmed)
```

۱۹ تست در ۵ suite پاس شدند: ۹ تای vault (خط `invariant_SolventAndConserved` invariant آن است)، ۴ تا برای توکن به‌علاوه‌ی invariant آن، و ۵ تا برای NFT. مقدارهای `μ` و `~` از ورودی تصادفی می‌آیند و در هر اجرا کمی فرق می‌کنند.

## deploy و انتقال روی anvil

`script/Deploy.s.sol` یک اسکریپت Foundry است: کد Solidity که تراکنش می‌فرستد. هر دو قرارداد را deploy می‌کند، ۱٬۰۰۰٬۰۰۰ DEMO به deploy‌کننده می‌دهد و NFT شماره ۱ را برایش mint می‌کند. با anvil که در ترمینال دیگری اجرا شده:

```
$ anvil --host 127.0.0.1 --port 8545          # another terminal
$ forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 \
    --broadcast --unlocked --sender 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
== Logs ==
  DemoToken 0x5FbDB2315678afecb367f032d93F642f64180aa3
  DemoNFT   0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
ONCHAIN EXECUTION COMPLETE & SUCCESSFUL.
(trimmed)
```

روی یک anvil تازه، آدرس قرارداد فقط به deploy‌کننده و nonce او بستگی دارد، پس همین آدرس‌های مرا می‌گیرید و مقاله‌های بعدی هم از آن‌ها استفاده می‌کنند. حالا ۲۵۰ DEMO و NFT شماره ۱ را به حساب ۱ می‌فرستم و نتیجه را به سه شکل چک می‌کنم:

```
$ T=0x5FbDB2315678afecb367f032d93F642f64180aa3; N=0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
$ A0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266; A1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
$ export ETH_RPC_URL=http://127.0.0.1:8545
$ cast send $T "transfer(address,uint256)(bool)" $A1 250ether --unlocked --from $A0
gasUsed              52383
status               1 (success)
$ cast call $T "balanceOf(address)(uint256)" $A1
250000000000000000000 [2.5e20]
$ cast storage $T $(cast index address $A1 3)
0x00000000000000000000000000000000000000000000000d8d726b7177a80000
$ cast balance $A1 --ether
10000.000000000000000000
$ cast send $N "transferFrom(address,address,uint256)" $A0 $A1 1 --unlocked --from $A0
gasUsed              55569
status               1 (success)
(trimmed)
```

- **`transfer`:** `250ether` فقط عدد ۲۵۰ × ۱۰^۱۸ است، چون `cast` «ether» را به ۱۸ رقم اعشار تبدیل می‌کند؛ این‌جا ربطی به ETH ندارد و فقط اتفاقاً با `decimals = 18` جور است.
- **`balanceOf`:** قرارداد تأیید می‌کند حساب ۱ مقدار 2.5e20 واحد دارد، یعنی ۲۵۰ توکن.
- **`cast storage`:** خواندن مستقیم خانه‌ی storage هم همین را می‌گوید. `balanceOf` در چیدمان این قرارداد خانه‌ی ۳ است (`name`، `symbol` و `totalSupply` جلوترند؛ `decimals` ثابت است و `minter` immutable، پس خانه نمی‌گیرند) و عضو حساب ۱ مقدار `0xd8d726b7177a80000` دارد که ۲۵۰ × ۱۰^۱۸ است.
- **`cast balance`:** ETH حساب ۱ دست‌نخورده است، همان ۱۰٬۰۰۰ اولیه‌ی anvil. انتقال توکن هیچ ETH جابه‌جا نکرد.
- **`transferFrom` برای NFT:** تراکنشی مشابه با کمی gas بیشتر، چون storage بیشتری را لمس می‌کند: mapping صاحب و تأیید.

## eventها راهی هستند که همه با آن می‌فهمند

برگردیم به سؤال اول: کیف‌پول از کجا می‌فهمد چیزی رسیده؟ نمی‌تواند از توکن بپرسد «کدام آدرس‌ها چیزی دارند»، چون روی mapping نمی‌شود پیمایش کرد. چیزی که می‌تواند بکند خواندن {{< term "event-log" "logها" >}} است، یعنی eventهای `Transfer` که هر انتقال emit کرده. کیف‌پول‌ها و block explorerها همین‌ها را دنبال می‌کنند. این logهای هر قرارداد است:

```
$ cast logs --from-block 0 --address $T "Transfer(address indexed,address indexed,uint256)"
  blockNumber: 4
  data: 0x00000000000000000000000000000000000000000000000d8d726b7177a80000
  topics: [
  	0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
  	0x000000000000000000000000f39fd6e51aad88f6f4ce6ab8827279cfffb92266
  	0x00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8
  ]
$ cast logs --from-block 0 --address $N "Transfer(address indexed from,address indexed to,uint256 indexed tokenId)"
  blockNumber: 5
  data: 0x
  topics: [
  	0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
  	0x000000000000000000000000f39fd6e51aad88f6f4ce6ab8827279cfffb92266
  	0x00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8
  	0x0000000000000000000000000000000000000000000000000000000000000001
  ]
(other fields, and the mint logs from blocks 1 and 3, trimmed)
```

هر log **topic** دارد (تا چهار مقدار ۳۲ بایتی قابل‌جست‌وجو که اولی نوع event را مشخص می‌کند) و **data** (بقیه‌ی چیزها). بخوانیمشان:

- **topic اول در هر دو log یکی است:** `keccak256("Transfer(address,address,uint256)")`. ERC-20 و ERC-721 اسم و نوع‌های event را یکی انتخاب کرده‌اند، پس hash یکی است.
- **log مربوط به ERC-20 سه topic دارد:** نوع event، فرستنده و گیرنده (آدرس‌ها تا ۳۲ بایت پر شده‌اند). مقدار در `data` است: `0xd8d726b7177a80000`، همان ۲۵۰ × ۱۰^۱۸ ما.
- **log مربوط به ERC-721 چهار topic دارد:** همان سه تا به‌علاوه‌ی شناسه‌ی توکن (`...01`، توکن شماره ۱)، چون `Transfer` در NFT شناسه را هم index می‌کند. `data`ش خالی است.

پس indexer این دو را از روی تعداد topicها جدا می‌کند، یا از روی اینکه می‌داند کدام قرارداد را می‌خواند. (logهای mint در بلاک‌های ۱ و ۳ را حذف کرده‌ام.) خواندن و decode این logها از داخل کد، با Go و Rust، در مقاله‌های بعد می‌آید.

## دام‌های یکپارچه‌سازی با توکن

- **هیچ‌وقت ۱۸ رقم اعشار را فرض نکنید.** `decimals()` را بخوانید و مقدارها را از اول تا آخر عدد صحیح نگه دارید.
- **بعضی توکن‌های واقعی استاندارد را می‌شکنند،** تا جایی که می‌دانم: مقدار برگشتی `bool` ندارند، موقع انتقال کارمزد برمی‌دارند. کتابخانه‌ها برای همین فراخوانی توکن را بسته‌بندی می‌کنند، و نباید فرض کنید «گیرنده دقیقاً `value` را می‌گیرد».
- **`transferFrom` برای NFT به یک قرارداد می‌تواند آن را گیر بیندازد.** `safeTransferFrom` را ترجیح بدهید، و یادتان باشد گیرنده را صدا می‌زند، که کدی است که کنترلش دست شما نیست.
- **موجودی‌ها در storage‌اند و تاریخچه در logها.** قراردادها نمی‌توانند log بخوانند، پس هر قاعده‌ای که قرارداد لازم دارد باید در storage نگه داشته شود.

## تمرین

۱. `decreaseAllowance` را اضافه کنید و ترتیب front-running را در یک تست دوباره اجرا کنید: حالا Bob چقدر می‌تواند بردارد؟
۲. `DemoToken` را طوری عوض کنید که ۱٪ از هر انتقال کارمزد بگیرد و ببینید کدام تست اول خراب می‌شود. این درباره‌ی کسانی که مقدار دقیق را فرض می‌کنند چه می‌گوید؟
۳. با `cast logs` و فیلتر topic فقط انتقال‌هایی را فهرست کنید که مقصدشان `$A1` است.

## قدم بعدی

مقاله‌ی بعد «کار با اتریوم از Go با go-ethereum» است. تا این‌جا هر قدم را با `cast` در ترمینال رفتیم؛ آن‌جا همین کارها را از داخل کد انجام می‌دهیم، با همان Go که از بخش اول می‌شناسیم.
