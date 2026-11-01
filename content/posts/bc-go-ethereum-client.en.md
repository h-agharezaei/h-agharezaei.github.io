+++
date = '2027-06-29T10:00:00+03:30'
draft = false
title = 'Talking to Ethereum from Go with go-ethereum'
description = 'go-ethereum from Go: chain ID, balances in wei, a signed EIP-1559 transaction, abigen token calls, a decoded custom error and nonces for concurrent sends.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "go-ethereum", "erc20"]
cover = { image = "/images/covers/bc-go-ethereum-client.png", alt = "Talking to Ethereum from Go with go-ethereum", hiddenInSingle = true }
+++

In [Tokens: ERC-20 and ERC-721](/posts/bc-erc20-erc721/) I deployed `DemoToken` to anvil and moved it with `cast`. A backend does the same from code: a deposit watcher, a payout worker, an exchange. This post does it from Go with {{< term "go-ethereum" "go-ethereum" >}}, the library behind the geth client.

Under the hood every call is {{< term "json-rpc" "JSON-RPC" >}} over HTTP, like the API of the toy node in [Part one wrap-up: a small full node in Go](/posts/bc-toy-node-go/). Nonces come back from [The account model, nonces and replay protection](/posts/bc-account-model-nonce/), now with a real node.

> Go 1.27 on macOS (arm64), go-ethereum v1.17.10, Foundry 1.8.7. A fresh anvil on `127.0.0.1:8545` with the deploy script from the previous post, so the token is at the same address. The private keys in the code are anvil's public test keys: never use them anywhere real.

## Dial, chain ID, balance

```
$ curl -s -X POST -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x7a69"}
```

`ethclient` wraps these calls in typed methods:

```go
client, err := ethclient.DialContext(ctx, "http://127.0.0.1:8545")
chainID, err := client.ChainID(ctx)
head, err := client.BlockNumber(ctx)
bal, err := client.BalanceAt(ctx, addr0, nil) // nil = latest block
fmt.Println("balance ETH: ", formatUnits(bal, 18))
```

Balances are integers in {{< term "wei" "wei" >}}, 10^18 per ether, so they do not fit in a `uint64` for long. go-ethereum uses `*big.Int`, and I format with integer division, never `float64`:

```go
func formatUnits(v *big.Int, decimals int) string {
	unit := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(decimals)), nil)
	q, r := new(big.Int).QuoRem(v, unit, new(big.Int))
	return fmt.Sprintf("%s.%0*s", q, decimals, r.String())
}
```

```
$ go run ./cmd/ethdemo info
chain id:     31337
block number: 3
account 0:    0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
balance wei:  9999997683290180192033
balance ETH:  9999.997683290180192033
```

`0x7a69` is 31337, anvil's default {{< term "chain-id" "chain ID" >}}. Account 0 paid gas for the three deploy transactions, so it is a little under 10,000.

## An EIP-1559 transaction by hand

Since {{< term "eip-1559" "EIP-1559" >}}, each block has a base fee set by the protocol and burned; a transaction adds a tip for the block producer and a cap on the total. As I understand it, the base fee can rise at most 12.5% per block, so "twice the current base fee plus the tip" leaves room for a few full blocks. That is a common rule of thumb, not a rule.

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

```
$ go run ./cmd/ethdemo send
nonce: 3 base fee: 783421165 tip: 1000000000 fee cap: 2566842330
tx type: 2 hash: 0xecb131b439f7991150b056891e303b98c8539a0ce8c5e687564fe175c9c0cd4b
status: 1 block: 4 gas used: 21000 effective gas price: 1685976107
account 1 gained: 1.500000000000000000 ETH
```

The cap is only a ceiling. Block 4's base fee was 685976107 (`cast block 4 --field baseFeePerGas`), so the transaction paid that plus the 1 gwei tip per gas. The chain ID is inside the signed data, as in the nonces post.

## Calling the token with abigen

The {{< term "contract-abi" "ABI" >}} is the contract's JSON interface. I copied the previous post's Foundry project, ran `forge build`, took the ABI from `out/` and generated bindings with {{< term "abigen" "abigen" >}}:

```
$ go run github.com/ethereum/go-ethereum/cmd/abigen@v1.17.10 --v2 \
    --abi abi/DemoToken.abi --pkg token --type DemoToken --out token/token.go
```

I used `--v2` because in v1.17.10 the old `bind` package is marked deprecated in favour of `bind/v2`. The v2 code only packs and unpacks; calls go through `bind`:

```go
demo := token.NewDemoToken()
inst := demo.Instance(c, tokenAddr)
dec, err := bind.Call(inst, call, demo.PackDecimals(), demo.UnpackDecimals)
opts := bind.NewKeyedTransactor(key, chainID)
tx, err := bind.Transact(inst, opts, demo.PackTransfer(acct1, amount))
rcpt, err := bind.WaitMined(ctx, c, tx.Hash())
ev, err := demo.UnpackTransferEvent(rcpt.Logs[0])
```

```
$ go run ./cmd/ethdemo token
decimals: 18 | account 0: 1000000.000000000000000000 DEMO | account 1: 0.000000000000000000 DEMO
transfer tx type: 2 status: 1 gas used: 52383 logs: 1
event Transfer: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 -> 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 100000000000000000000
account 0: 999900.000000000000000000 DEMO | account 1: 100.000000000000000000 DEMO
```

`bind.Transact` filled nonce, gas limit and fees itself and still built a type-2 transaction. Gas used is 52383, the same as `cast send` in the previous post.

## Decoding a custom error

Account 2 has no DEMO. When it tries to send 1 DEMO, `bind.Transact` first asks the node to estimate gas, the simulated call {{< term "revert" "reverts" >}}, and nothing is sent. The error carries the revert data:

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

The first 4 bytes are the error's selector, built like a {{< term "function-selector" "function selector" >}}; three 32-byte words follow. Account 2's nonce stayed 0.

## Nonces with concurrent senders

Five goroutines send from account 0 at once. In the first round each asks `PendingNonceAt`; in the second a mutex-guarded counter hands out the {{< term "nonce" "nonces" >}}. To make the race show up every time, all goroutines get their nonce before any of them sends:

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
   nonce 5: replacement transaction underpriced
   nonce 5: <nil>
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

Same nonce, different value: the node sees four attempts to replace one transaction without a higher fee. With the manager, nonce 6 arrived last and the node still mined all five in order. The manager only works if it is the only sender for that key; several processes need one place to hand out nonces.

## A few things to watch

- Keep amounts as `*big.Int` from RPC to database. Account 0's balance above becomes 9999997683290179895296 as a `float64`.
- `PendingNonceAt` is a snapshot of the node's view, not a reservation.
- A transaction that is never mined blocks every higher nonce. Plan to replace it with a higher fee.
- Revert data can be decoded only if you have the ABI with the error.

## Exercise

1. Set `feeCap` below the base fee and send. What does anvil answer?
2. Run anvil with `--no-mining` and restart the program between two nonce-manager rounds. Where should `next` start?
3. Decode `NotMinter` by calling `mint` from account 1.

## What's next

Next post: **Talking to Ethereum from Rust with alloy**.
