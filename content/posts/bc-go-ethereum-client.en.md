+++
date = '2026-11-18T18:00:00+03:30'
draft = false
title = 'Talking to Ethereum from Go with go-ethereum'
description = 'go-ethereum from Go: chain ID, balances in wei, a signed EIP-1559 transaction, abigen token calls, a decoded custom error and nonces for concurrent sends.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "go-ethereum", "erc20"]
cover = { image = "/images/covers/bc-go-ethereum-client.png", alt = "Talking to Ethereum from Go with go-ethereum", hiddenInSingle = true }
+++

In the last three posts I did everything by hand in a terminal with `cast`. That is fine for learning, but real systems do these things from code: a deposit watcher that notices incoming payments, a payout worker that sends them, an exchange back end. And code meets two problems the terminal hides. Many parts of the program may send at the same time, and the numbers are bigger than a `float64` can hold exactly.

This post does the same steps from Go with {{< term "go-ethereum" "go-ethereum" >}}, the library behind the geth client (one of the main programs that run an Ethereum node). We read balances, send a signed ETH transfer, call the token contract from [the tokens post](/posts/bc-erc20-erc721/), decode a failure and send transactions concurrently.

There is no magic underneath. Every call is {{< term "json-rpc" "JSON-RPC" >}} over HTTP, the same kind of API as the one in [the toy node](/posts/bc-toy-node-go/): a JSON request with a method name, a JSON answer. The nonces, which come back from [the account model post](/posts/bc-account-model-nonce/), now meet a real node.

> Everything below was run with Go 1.27 on macOS (arm64), go-ethereum v1.17.10 and Foundry 1.8.7. I used a fresh anvil on `127.0.0.1:8545` and the deploy script from the previous post, so the token is at the same address as there. The private keys in the code are anvil's public test keys: never use them anywhere real.

## Dial, chain ID, balance

First, the raw protocol, so we know what the library will wrap. One `curl` asks the node for its chain ID:

```
$ curl -s -X POST -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x7a69"}
```

Numbers in this API are hexadecimal strings. `0x7a69` is 31337. The package `ethclient` wraps each such call in a typed Go method:

```go
client, err := ethclient.DialContext(ctx, "http://127.0.0.1:8545")
chainID, err := client.ChainID(ctx)
head, err := client.BlockNumber(ctx)
bal, err := client.BalanceAt(ctx, addr0, nil) // nil = latest block
fmt.Println("balance ETH: ", formatUnits(bal, 18))
```

Balances are integers in {{< term "wei" "wei" >}}, 10^18 per ether, so they stop fitting in a `uint64` very quickly. go-ethereum uses `*big.Int` (Go's arbitrary-size integer). To show a balance in ETH I use integer division and a remainder, never `float64`:

```go
func formatUnits(v *big.Int, decimals int) string {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(decimals)), nil)
	q, r := new(big.Int).QuoRem(v, unit, new(big.Int))
	return fmt.Sprintf("%s.%0*s", q, decimals, r.String())
}
```

`go run ./cmd/ethdemo info` runs the dial, chain ID and balance code:

```
$ go run ./cmd/ethdemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

- **`chain id: 31337`:** that is `0x7a69` from the curl call, anvil's default {{< term "chain-id" "chain ID" >}}. The chain ID is a number that identifies a network, and it goes into every signed transaction so that one signed for a test network cannot be replayed on another.
- **`block number: 3`:** the three transactions of the deploy script (two contracts and one mint) made blocks 1 to 3.
- **The balance:** account 0 started with 10,000 ETH and paid gas for those three transactions, so it is a little under that. The `wei` line and the ETH line are the same number, once as an integer and once with the decimal point put in.

## An EIP-1559 transaction by hand

Now sending. A transaction carries a fee, and since {{< term "eip-1559" "EIP-1559" >}} the fee has two parts. Every block has a **base fee** per unit of gas, set automatically by the protocol, and it is burned (nobody receives it). On top of that you add a **tip** for the block producer, and you set a **cap**, the highest total price per gas you accept. As I understand it, the base fee can rise by at most 12.5% from one block to the next, so "twice the current base fee plus the tip" leaves room for a few full blocks. That is a common rule of thumb, not a rule.

This code builds the transaction by hand, signs it and sends it:

```go
nonce, err := c.PendingNonceAt(ctx, from)
head, err := c.HeaderByNumber(ctx, nil)
tip, err := c.SuggestGasTipCap(ctx)
feeCap := new(big.Int).Add(new(big.Int).Mul(head.BaseFee, big.NewInt(2)), tip)

tx := types.NewTx(&types.DynamicFeeTx{
	ChainID: chainID, Nonce: nonce, GasTipCap: tip, GasFeeCap: feeCap,
	Gas: 21000, To: &acct1, Value: value, // 1.5 ETH in wei
})
signed, err := types.SignTx(tx, types.LatestSignerForChainID(chainID), key)
err = c.SendTransaction(ctx, signed)
rcpt, err := bind.WaitMined(ctx, c, signed.Hash())
```

Step by step: the nonce is the account's next transaction number (the same replay protection from the account model post). The node tells us the latest base fee and a suggested tip. `Gas: 21000` is the fixed cost of a plain ETH transfer. `DynamicFeeTx` is the EIP-1559 transaction type (type 2). The key signs it, `SendTransaction` submits it, and `WaitMined` waits until it is in a block and returns the receipt.

```
$ go run ./cmd/ethdemo send
nonce: 3 base fee: 783421165 tip: 1000000000 fee cap: 2566842330
tx type: 2 hash: 0xecb131b439f7991150b056891e303b98c8539a0ce8c5e687564fe175c9c0cd4b
status: 1 block: 4 gas used: 21000 effective gas price: 1685976107
account 1 gained: 1.500000000000000000 ETH
```

- **`nonce: 3`:** account 0 already sent three transactions (the deploy).
- **`base fee`, `tip`, `fee cap`:** all in wei per gas. The cap 2566842330 is 2 * 783421165 + 1000000000, our rule of thumb. The tip is 1 gwei, which is 10^9 wei.
- **`effective gas price`:** what was really paid per gas: 1685976107. The cap is only a ceiling. Block 4's own base fee was 685976107 (I checked with `cast block 4 --field baseFeePerGas`), the base fee dropped from the 783421165 we saw in block 3, so the transaction paid that plus the 1 gwei tip.
- **`gas used: 21000`, `status: 1`:** the plain-transfer cost, and success.
- **The last line:** account 1's balance went up by exactly 1.5 ETH. The sender pays the 1.5 ETH plus gas; the receiver gets exactly the 1.5.

The chain ID is inside the signed data, as in the nonces post: a signature made for this chain is worthless on another.

## Calling the token with abigen

To call a contract, the Go program needs to know its functions: names, argument types and return types. That description is the {{< term "contract-abi" "contract ABI" >}}, a JSON file. The compiler produces it. I copied the previous post's Foundry project, ran `forge build`, took the ABI from `out/` and generated Go code from it with {{< term "abigen" "abigen" >}}:

```
$ go run github.com/ethereum/go-ethereum/cmd/abigen@v1.17.10 --v2 \
    --abi abi/DemoToken.abi --pkg token --type DemoToken --out token/token.go
```

I used `--v2` because in v1.17.10 the old `bind` package is marked deprecated in favour of `bind/v2`, and the source says so. The v2 generated code only packs arguments and unpacks results; the calls themselves go through the `bind` package:

```go
demo := token.NewDemoToken()
inst := demo.Instance(c, tokenAddr)
dec, err := bind.Call(inst, call, demo.PackDecimals(), demo.UnpackDecimals)
opts := bind.NewKeyedTransactor(key, chainID)
tx, err := bind.Transact(inst, opts, demo.PackTransfer(acct1, amount))
rcpt, err := bind.WaitMined(ctx, c, tx.Hash())
ev, err := demo.UnpackTransferEvent(rcpt.Logs[0])
```

`bind.Call` is a read, like `cast call`: pack the arguments, ask the node, unpack the answer. `bind.Transact` is a real transaction, like `cast send`. `UnpackTransferEvent` decodes the log from the receipt: the same topics and data we read by hand in the last post.

```
$ go run ./cmd/ethdemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO | account 1: 0.000000000000000000 DEMO
transfer tx type: 2 status: 1 gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 0: 999900.000000000000000000 DEMO | account 1: 100.000000000000000000 DEMO
```

- **Line 1:** `decimals` is read from the contract first (18), and used to format the balances. Account 0 holds the whole initial supply of 1,000,000 DEMO.
- **Line 2:** the transfer is a type-2 transaction (`bind.Transact` filled nonce, gas limit and fees itself and still built an EIP-1559 one). Gas used is 52383, the same as `cast send` in the previous post, and exactly one log was emitted.
- **Line 3:** the decoded `Transfer` event: from account 0 to account 1, 10^20 units.
- **Line 4:** the new balances: 999,900 and 100. That is 100 DEMO, because I sent `100 * 10^decimals`.

## Decoding a custom error

What does a failure look like to Go code? Account 2 has no DEMO, and tries to send 1 DEMO. `bind.Transact` first asks the node to estimate the gas, the simulated call {{< term "revert" "reverts" >}}, and nothing is sent. The Go error carries the raw revert data, which we decode with the ABI:

```go
var de rpc.DataError
if errors.As(err, &de) {
	data, _ := hexutil.Decode(fmt.Sprint(de.ErrorData()))
	decoded, err := demo.UnpackError(data)
	if e, ok := decoded.(*token.DemoTokenInsufficientBalance); ok { /* ... */ }
}
```

```
$ go run ./cmd/ethdemo revert
raw error: execution reverted: custom error 0xdb42144d: 0000000000000000000000003c44cdddb6a900fa2b585dd299e03d12fa4293bc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000de0b6b3a7640000
revert data: db42144d... (100 bytes)
InsufficientBalance: from 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC balance 0 needed 1000000000000000000
```

- **The raw error** is a string, useful to a human but not to a program.
- **The revert data** is 100 bytes: the first 4 are the error's selector (`0xdb42144d`), built just like a {{< term "function-selector" "function selector" >}} from `InsufficientBalance(address,uint256,uint256)`, followed by three 32-byte words, the arguments.
- **The decoded line:** `UnpackError` matched the selector with the ABI and gave back a typed Go value, so the program can show "from this address, balance 0, needed 10^18" instead of hex. Account 2's nonce stayed 0, since nothing was sent.

## Nonces with concurrent senders

The problem I mentioned at the start. Every transaction from an account needs the next nonce in order. If several goroutines send at once, and each of them asks the node for the nonce, they will all get the same number. In the demo five goroutines send from account 0. In the first round each one asks `PendingNonceAt`; in the second round a mutex-guarded counter hands out the {{< term "nonce" "nonces" >}}. To make the race show up every time, all the goroutines get their nonce before any of them sends:

```go
type nonceManager struct {
	mu   sync.Mutex
	next uint64
}

func (m *nonceManager) Next() uint64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	n := m.next
	m.next++
	return n
}
```

```
$ go run ./cmd/ethdemo nonces
PendingNonceAt in every goroutine:
   nonce 5: <nil>
   nonce 5: replacement transaction underpriced
   nonce 5: replacement transaction underpriced
   nonce 5: replacement transaction underpriced
   nonce 5: replacement transaction underpriced
local nonce manager:
   nonce 7: <nil>
   nonce 8: <nil>
   nonce 9: <nil>
   nonce 10: <nil>
   nonce 6: <nil>
mined: 6 txs; account 0 nonce now: 11
```

- **First round:** all five got nonce 5. Each has a different value, so each is a different transaction with the same nonce. One got in; the node answers the other four with `replacement transaction underpriced`: it sees an attempt to replace a waiting transaction without paying a higher fee. Which of the five wins varies from run to run.
- **Second round:** the nonces 6 to 10 are handed out without a gap or a repeat, and all five sends succeed. The order of goroutines is random (nonce 6 happened to go last here), and the node still mined all five in nonce order.
- **The last line:** 6 transactions mined (one from the first round, five from the second), and the account's nonce went from 5 to 11.

The manager is a fix only if it is the **only** sender for that key. If several processes send from one account, they need one shared place that hands out the nonces.

## Common client mistakes

- **Keep amounts as `*big.Int`** from the RPC call to the database. Account 0's balance above would become 9999997683290179895296 as a `float64`: already wrong in the last digits.
- **`PendingNonceAt` is a snapshot** of the node's view, not a reservation. Two callers can get the same number.
- **A transaction that never gets mined blocks every higher nonce** of that account. Plan to replace it with the same nonce and a higher fee.
- **Revert data can be decoded only if you have the ABI** that contains the error. Without it you see the hex.

## Exercise

1. Set `feeCap` below the base fee and send. What does anvil answer?
2. Run anvil with `--no-mining` and restart the program between two nonce-manager rounds. Where should `next` start?
3. Decode `NotMinter` by calling `mint` from account 1.

## What's next

The next post is "Talking to Ethereum from Rust with alloy". It does the same steps in Rust, so you can see the two libraries side by side.
