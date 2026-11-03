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

با فرستادن توکن چه چیزی جابه‌جا می‌شود و کیف‌پول گیرنده از کجا خبردار می‌شود؟ جواب در دو قراردادی است که بیشتر آدم‌ها از «توکن» منظورشان است: توکن تعویض‌پذیر {{< term "erc-20" "ERC-20" >}} و NFT {{< term "erc-721" "ERC-721" >}}، در همان پروژه‌ی [پست تست](/fa/posts/bc-foundry-testing-fuzzing/).

هر دو را دستی نوشتم تا تک‌تک خط‌ها را ببینم. قرارداد آموزشی‌اند و audit نشده‌اند. در production انتخاب معمول یک کتاب‌خانه‌ی audit‌شده مثل OpenZeppelin است، نه کد یک پست وبلاگ.

> اجرا با Foundry 1.8.7 و solc 0.8.38 روی macOS (arm64). پروژه‌ی پست قبل (با خزانه و تست‌هایش) را در یک پوشه‌ی محلی تازه کپی کردم و `src/DemoToken.sol`، `src/DemoNFT.sol`، تست‌هایشان و `script/Deploy.s.sol` را اضافه کردم. anvil روی `127.0.0.1` اجرا می‌شود و آدرس‌ها حساب‌های تست عمومی anvil هستند.

## ERC-20 یعنی یک mapping

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

«انتقال» یعنی کم کردن از یک خانه‌ی mapping و اضافه کردن به خانه‌ی دیگر، داخل storage یک قرارداد. هیچ سکه‌ای جایی نمی‌رود. mint یک `Transfer` از آدرس صفر منتشر می‌کند؛ رد کردن انتقال به `address(0)` انتخاب من است، نه الزام استاندارد.

`decimals` هیچ چیزی در منطق قرارداد عوض نمی‌کند. قرارداد فقط عدد صحیح می‌شناسد؛ ۱۸ به کیف پول می‌گوید `1000000000000000000` را `1` نشان بده. توکنی با `decimals = 6` و توکنی با ۱۸ می‌توانند همان عدد صحیح را نگه دارند و مقدار متفاوتی نمایش دهند، پس کدی که توکن را بین سیستم‌ها جابه‌جا می‌کند باید `decimals` را بخواند و هرگز فرضش نکند.

`approve` همراه `transferFrom` اجازه می‌دهد یک قرارداد، مثلاً صرافی، توکن شما را بکشد. `approve` مقدار قبلی را بازنویسی می‌کند. اگر Alice سقف Bob را از ۱۰۰ به ۵۰ کم کند، تا جایی که من این مشکل شناخته‌شده را می‌فهمم Bob می‌تواند mempool را ببیند، ۱۰۰ را قبل از رسیدن تغییر خرج کند و بعد ۵۰ جدید را هم خرج کند. راه‌های رایج: اول سقف را صفر کنید، یا از تابع‌های افزایش سقف که بعضی کتاب‌خانه‌ها دارند استفاده کنید. این یک {{< term "race-condition" "race" >}} روی ترتیب تراکنش‌هاست، نه باگ در حساب.

## یک ERC-721 کوچک

NFT به‌جای موجودی برای هر آدرس، برای هر شناسه یک مالک نگه می‌دارد. بخش جالب، مجوز و انتقال امن است:

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

قراردادی که NFT نمی‌شناسد ممکن است یکی بگیرد و دیگر هرگز نتواند جابه‌جایش کند. `safeTransferFrom` از گیرنده‌ی قراردادی می‌خواهد با selector تابع `onERC721Received` جواب بدهد؛ اگر نداد، کل انتقال revert می‌شود. تست هر دو طرف را نشان می‌دهد: `transferFrom` به یک قرارداد خالی موفق می‌شود و NFT آنجا گیر می‌کند، `safeTransferFrom` به همان قرارداد revert می‌شود، و گیرنده‌ای که درست جواب می‌دهد توکن شماره‌ی ۲ را می‌گیرد. یک تست دیگر چک می‌کند شناسه‌ی رابط `IERC721` برابر `0x80ac58cd` است، همان مقداری که `supportsInterface` برمی‌گرداند.

## تست‌ها

{{< term "invariant-testing" "invariant" >}} ERC-20 همان کلاسیک است: `totalSupply` برابر جمع موجودی‌هاست. یک handler بین سه دارنده انتقال، approve و بعد `transferFrom`، و mint انجام می‌دهد:

```
$ forge test
[PASS] testFuzz_TransferConservesSupply(address,uint256) (runs: 256, μ: 102062, ~: 103692)
[PASS] test_TransferFromSpendsAllowance() (gas: 165724)
[PASS] testFuzz_MintedIdsHaveOneOwner(uint8) (runs: 256, μ: 2693677, ~: 476603)
[PASS] test_InterfaceId() (gas: 248)
[PASS] test_SafeTransferChecksReceiver() (gas: 608315)
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
[PASS] invariant_TotalSupplyEqualsSumOfBalances() (runs: 256, calls: 128000, reverts: 0)
Ran 5 test suites in 13.17s (25.79s CPU time): 19 tests passed, 0 failed, 0 skipped (19 total tests)
(trimmed)
```

## دیپلوی و انتقال روی anvil

`script/Deploy.s.sol` هر دو قرارداد را دیپلوی می‌کند، ۱٬۰۰۰٬۰۰۰ DEMO به دیپلوی‌کننده می‌دهد و NFT شماره‌ی ۱ را برایش mint می‌کند:

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

روی anvil تازه آدرس‌ها فقط به دیپلوی‌کننده و nonce آن بستگی دارند، پس پست‌های بعدی همین آدرس‌ها را می‌گیرند. ۲۵۰ DEMO و NFT شماره‌ی ۱ را به حساب ۱ می‌فرستیم:

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

در این چیدمان `balanceOf` اسلات ۳ است و خانه‌ی حساب ۱ همان 250e18 را دارد. موجودی ETH آن دست نخورده: هنوز همان ۱۰٬۰۰۰ اولیه‌ی anvil.

## رویدادها راه خبردار شدن همه‌اند

کیف پول نمی‌تواند با خواندن storage «همه‌ی توکن‌های من» را فهرست کند؛ روی mapping نمی‌شود پیمایش کرد. کیف پول {{< term "event-log" "log" >}}ها را می‌خواند:

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

هر دو رویداد topic اول یکسانی دارند، `keccak256("Transfer(address,address,uint256)")`. رویداد ERC-20 سه topic دارد و مقدار در `data` است؛ ERC-721 شناسه‌ی توکن را هم index می‌کند، پس چهار topic و data خالی دارد. indexer باید از همین، یا از شناختن قرارداد، آن‌ها را از هم جدا کند.

## دام‌های کار با توکن

- هرگز ۱۸ رقم اعشار را فرض نکنید. `decimals()` را بخوانید و مقدارها را از اول تا آخر عدد صحیح نگه دارید.
- تا جایی که می‌دانم بعضی توکن‌های واقعی استاندارد را رعایت نمی‌کنند (بدون خروجی `bool`، کارمزد روی انتقال). کتاب‌خانه‌ها برای همین فراخوانی‌ها را wrap می‌کنند.
- `transferFrom` به یک قرارداد می‌تواند NFT را گیر بیندازد؛ `safeTransferFrom` را ترجیح دهید و یادتان باشد که گیرنده را صدا می‌زند.
- موجودی در storage است و تاریخچه در logها. قراردادها نمی‌توانند log بخوانند.

## تمرین

۱. `decreaseAllowance` را اضافه کنید و ترتیب front-running را در یک تست بازسازی کنید: حالا Bob چقدر می‌تواند بردارد؟
۲. برای `DemoToken` کارمزد ۱ درصد روی انتقال بگذارید و ببینید کدام تست می‌شکند.
۳. با `cast logs` و فیلتر topic فقط انتقال‌های به `$A1` را فهرست کنید.

## قدم بعدی

پست بعد: **کار با اتریوم از Go با go-ethereum**؛ همین کارها با کد.
