+++
date = '2026-11-17T18:00:00+03:30'
draft = false
title = 'Tokens: ERC-20 and ERC-721'
description = 'ERC-20 and ERC-721 written by hand in Solidity: balances as a mapping, allowances, safe NFT transfers, Foundry tests, and Transfer events read with cast.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "erc20", "erc721", "foundry"]
cover = { image = "/images/covers/bc-erc20-erc721.png", alt = "Tokens: ERC-20 and ERC-721", hiddenInSingle = true }
+++

When you "send a token" to a friend, what actually moves? There is no coin, no file, nothing that travels from one place to another. And how does your friend's wallet find out that something arrived?

The answer is simpler than the vocabulary around it. A token is not a special feature of Ethereum. It is an ordinary smart contract that keeps a ledger, like the vault from the last two posts, and follows a public agreement about which functions and events it must have. If every token follows the same agreement, every wallet and exchange can talk to every token without knowing anything specific about it. These agreements are called ERC standards (ERC stands for Ethereum Request for Comments; each has a number).

In this post I build the two most common ones by hand: an {{< term "erc-20" "ERC-20" >}} **fungible** token, where every unit is identical to every other (like money: one of my 10 DEMO is as good as one of yours), and an {{< term "erc-721" "ERC-721" >}} **NFT**, where every token is unique and has its own id (like a numbered ticket). I use the same project as [the testing post](/posts/bc-foundry-testing-fuzzing/), so the vault and its tests are still there.

I wrote both contracts by hand so we can see every line. They are teaching contracts, not audited. In production the usual choice is an audited library such as OpenZeppelin, not code from a blog post.

> Everything below was run with Foundry 1.8.7 and solc 0.8.38 on macOS (arm64). I copied the previous post's project (the vault and its tests included) into a new local folder and added `src/DemoToken.sol`, `src/DemoNFT.sol`, their tests and `script/Deploy.s.sol`. anvil runs on `127.0.0.1`, and the addresses are anvil's public test accounts.

## An ERC-20 is a mapping

The core of a fungible token is one table: for each address, how many units it owns. In Solidity that is a `mapping`. Here is the contract with the constructor, mint function and error definitions left out:

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

(The comment in `approve` points at the race explained below, not at a separate post.) Let's read the important parts.

**A transfer is two edits to a table.** `_transfer` subtracts from one mapping entry, adds to another and emits a `Transfer` event. No coin moves anywhere; the "token" is only a number in this contract's storage. It also means that if the contract is wrong, the money is wrong, since there is nothing else. Creating new tokens (minting) is reported as a `Transfer` from the zero address. Refusing transfers to `address(0)` is my own choice, as far as I know, not something the standard requires.

**`decimals` is only for display.** The contract knows only integers. `decimals = 18` tells wallets to show `1000000000000000000` as `1`, exactly like wei and ETH. A token with `decimals = 6` and one with 18 can hold the same integer and display very different amounts. So code that moves tokens between systems must read `decimals()` and never assume it.

**`approve` and `transferFrom` let someone else spend your tokens.** `transfer` only moves your own tokens, and only you can call it. But what if a contract, say an exchange, must take tokens from you? You first call `approve(exchange, 100)`: "this spender may take up to 100 of mine". Later the exchange calls `transferFrom(you, somewhere, 60)`, which checks and reduces the **allowance** and then moves the tokens. The allowance is the second, nested mapping: owner, then spender, then amount. A value of `type(uint256).max` is used by convention as "unlimited" and is never reduced.

**`approve` has a known trap.** It overwrites. Suppose Alice approved Bob for 100 and now wants to lower it to 50. As I understand the known issue, Bob can watch the {{< term "mempool" "mempool" >}} of pending transactions, see her change coming, and quickly spend the 100 before it lands, then spend the new 50 as well. That is 150 instead of at most 100. Common mitigations are setting the allowance to zero first, or the allowance-increase functions some libraries offer. It is a {{< term "race-condition" "race" >}} on the order of transactions, not a bug in the arithmetic.

## A minimal ERC-721

An NFT does not keep a balance per address in the same sense; it keeps an **owner per token id**. Each id is one unique item. The interesting part is who may move a token, and the "safe" transfer:

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

`transferFrom` allows the move in three cases: the caller is the owner, or the caller was approved for this one token (`getApproved`), or the owner approved the caller for all tokens (`isApprovedForAll`). After the move the single-token approval is deleted, so it works only once.

Now the safe part. A contract that knows nothing about NFTs could receive one and then have no function to send it onward: the NFT is stuck there forever. `safeTransferFrom` prevents this. If the recipient is a contract (`to.code.length > 0`), it calls `onERC721Received` on it, and the recipient must answer with that function's own selector, which means "yes, I know what to do with this". If it answers anything else, or has no such function, the whole transfer reverts, and nothing moves.

The tests prove both sides. `transferFrom` to a bare contract succeeds, and the NFT is stuck there; `safeTransferFrom` to the same contract reverts; and a receiver that answers correctly gets token #2. Another test checks that the `IERC721` interface ID is `0x80ac58cd`. That is the value the contract returns from `supportsInterface` (the ERC-165 mechanism) so that other contracts can ask "do you speak ERC-721?".

## Tests

The most natural property for an ERC-20 is the classic {{< term "invariant-testing" "invariant" >}}: `totalSupply` always equals the sum of all balances. As in the last post, a handler makes valid calls between three holders: plain transfers, approve-then-`transferFrom`, and mints. The project now runs all tests, the vault's too:

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

19 tests passed in 5 suites: the vault's 9 (the `invariant_SolventAndConserved` line is its invariant), 4 for the token plus its invariant, and 5 for the NFT. The `μ` and `~` values come from random inputs and change a little in every run.

## Deploy and transfer on anvil

`script/Deploy.s.sol` is a Foundry script: Solidity code that sends transactions. It deploys both contracts, gives the deployer 1,000,000 DEMO, and mints NFT #1 to it. With anvil running in another terminal:

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

On a fresh anvil, a contract address depends only on the deployer and its nonce, so you get the same addresses as mine, and the next posts reuse them. Now let me send 250 DEMO and NFT #1 to account 1 and check the results in three ways:

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

- **`transfer`:** `250ether` is just the number 250 * 10^18, because `cast` converts "ether" to 18 decimals; it has nothing to do with ETH here, it happens to match `decimals = 18`.
- **`balanceOf`:** the contract confirms account 1 holds 2.5e20 units, that is 250 tokens.
- **`cast storage`:** reading the raw storage slot agrees. `balanceOf` is slot 3 in this contract's layout (`name`, `symbol` and `totalSupply` come first; `decimals` is a constant and `minter` is immutable, so they take no slots), and account 1's entry holds `0xd8d726b7177a80000`, which is 250 * 10^18.
- **`cast balance`:** account 1's ETH is untouched, still anvil's starting 10,000. The token transfer moved no ETH at all.
- **The NFT `transferFrom`:** a similar transaction, with a little more gas, as it touches more storage: the owner mapping and the approval.

## Events are how anyone finds out

Back to the opening question: how does a wallet know something arrived? It cannot ask the token "which addresses hold something", because a mapping cannot be iterated. What it can do is read the {{< term "event-log" "logs" >}}, the `Transfer` events that every transfer emitted. Wallets and block explorers watch those. Here are the logs for each contract:

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

A log has **topics** (up to four searchable 32-byte values, the first one identifying the event type) and **data** (everything else). Let's read them:

- **The first topic is the same in both logs:** `keccak256("Transfer(address,address,uint256)")`. ERC-20 and ERC-721 chose the same event name and the same types, so the hash is identical.
- **The ERC-20 log has three topics:** the event type, the sender, the receiver (addresses padded to 32 bytes). The amount is in `data`: `0xd8d726b7177a80000`, our 250 * 10^18.
- **The ERC-721 log has four topics:** the same three, plus the token id (`...01`, token #1), because the NFT's `Transfer` indexes the id too. Its `data` is empty.

An indexer therefore tells them apart by the number of topics, or by knowing which contract it is reading. Reading and decoding these logs from code, in Go and in Rust, is coming up in the next posts.

## Token integration traps

- **Never assume 18 decimals.** Read `decimals()` and keep amounts as integers from end to end.
- **Some real tokens break the standard,** as I understand it: no `bool` return value, fees taken on transfer. Libraries wrap token calls for that reason, and you should not assume that "receiver gets exactly `value`".
- **`transferFrom` of an NFT to a contract can strand it.** Prefer `safeTransferFrom`, and remember that it calls into the recipient, which is code you do not control.
- **Balances live in storage and history lives in logs.** Contracts cannot read logs, so any rule a contract needs must be kept in storage.

## Exercise

1. Add `decreaseAllowance` and replay the front-running order in a test: how much can Bob take now?
2. Make `DemoToken` charge 1% on transfers and see which test breaks first. What does that say about integrators who assume exact amounts?
3. Use `cast logs` with a topic filter to list only the transfers to `$A1`.

## What's next

The next post is "Talking to Ethereum from Go with go-ethereum". So far every step used `cast` in a terminal; there we do the same from code, with the Go we know from part one.
