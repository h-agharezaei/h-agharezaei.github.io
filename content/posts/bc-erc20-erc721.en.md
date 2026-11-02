+++
date = '2027-06-28T10:00:00+03:30'
draft = false
title = 'Tokens: ERC-20 and ERC-721'
description = 'ERC-20 and ERC-721 written by hand in Solidity: balances as a mapping, allowances, safe NFT transfers, Foundry tests, and Transfer events read with cast.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "erc20", "erc721", "foundry"]
cover = { image = "/images/covers/bc-erc20-erc721.png", alt = "Tokens: ERC-20 and ERC-721", hiddenInSingle = true }
+++

In [Testing, fuzzing and invariants with Foundry](/posts/bc-foundry-testing-fuzzing/) the vault got unit, fuzz and invariant tests. This post uses the same project and the same tools for the two contracts most people mean when they say "token": an {{< term "erc-20" "ERC-20" >}} fungible token and an {{< term "erc-721" "ERC-721" >}} NFT.

I wrote both by hand to see every line. They are teaching contracts, not audited. In production the usual choice is an audited library such as OpenZeppelin, not code from a blog post.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project (vault and its tests included) into a new local folder and added `src/DemoToken.sol`, `src/DemoNFT.sol`, their tests and `script/Deploy.s.sol`. anvil runs on `127.0.0.1`; the addresses are anvil's public test accounts.

## An ERC-20 is a mapping

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

A "transfer" subtracts in one mapping entry and adds in another, inside one contract's storage. No coin moves anywhere. Minting emits `Transfer` from the zero address; refusing transfers to `address(0)` is my choice, not the standard's.

`decimals` changes nothing in the logic. The contract only knows integers; 18 tells wallets to show `1000000000000000000` as `1`. A token with `decimals = 6` and one with 18 can hold the same integer and display different amounts, so code that moves tokens between systems must read `decimals`, never assume it.

`approve` plus `transferFrom` lets a contract, say an exchange, pull your tokens. `approve` overwrites. If Alice lowers Bob's allowance from 100 to 50, Bob can, as I understand the known issue, watch the mempool, spend the 100 before her change lands, then spend the new 50 too. Common mitigations are setting the allowance to zero first, or allowance-increase functions some libraries offer. It is a {{< term "race-condition" "race" >}} on the transaction order, not a bug in the arithmetic.

## A minimal ERC-721

An NFT keeps an owner per id instead of a balance per address. The interesting part is authorization and the safe transfer:

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

A contract that does not know about NFTs could receive one and never move it again. `safeTransferFrom` asks a contract recipient to answer with the `onERC721Received` selector; if it does not, the whole transfer reverts. The test proves both sides: `transferFrom` to a bare contract succeeds and the NFT is stuck there, `safeTransferFrom` to it reverts, and a receiver that answers correctly gets token #2. Another test checks that the `IERC721` interface ID is `0x80ac58cd`, the value `supportsInterface` returns.

## Tests

The ERC-20 {{< term "invariant-testing" "invariant" >}} is the classic one: `totalSupply` equals the sum of balances. A handler does transfers, approve-then-`transferFrom` and mints between three holders:

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

## Deploy and transfer on anvil

`script/Deploy.s.sol` deploys both contracts, gives the deployer 1,000,000 DEMO and mints NFT #1 to it:

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

On a fresh anvil the addresses come only from the deployer and its nonce, so the next posts get the same ones. Send 250 DEMO and NFT #1 to account 1:

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

`balanceOf` is slot 3 in this layout, and account 1's entry holds the 250e18. Its ETH balance is untouched: still anvil's starting 10,000.

## Events are how anyone finds out

A wallet cannot list "all my tokens" by reading storage; mappings cannot be iterated. It reads {{< term "event-log" "logs" >}}:

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

Both events have the same first topic, `keccak256("Transfer(address,address,uint256)")`. The ERC-20 one has three topics and the amount in `data`; the ERC-721 one indexes the token id too, so it has four topics and empty data. An indexer must tell them apart by that, or by knowing the contract.

## A few things to watch

- Never assume 18 decimals. Read `decimals()` and keep amounts as integers end to end.
- Some real tokens break the standard, as I understand it (no `bool` return, fees on transfer). Libraries wrap calls for that reason.
- `transferFrom` to a contract can strand an NFT; prefer `safeTransferFrom`, and remember it calls into the recipient.
- Balances live in storage, history lives in logs. Logs are not readable by contracts.

## Exercise

1. Add `decreaseAllowance` and replay the front-running order in a test: how much can Bob take now?
2. Make `DemoToken` charge 1% on transfers and watch which test breaks.
3. Use `cast logs` with a topic filter to list only transfers to `$A1`.

## What's next

Next post: **Talking to Ethereum from Go with go-ethereum**.
