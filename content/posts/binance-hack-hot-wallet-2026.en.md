+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'The $6.3B Binance Hack, Technically: No Key Leaked, Withdrawals Signed Anyway'
seoTitle = 'The $6.3B Binance Hack: A Technical Look'
description = 'The Binance hack of October 2026, technically: a compromised DevOps laptop, signed withdrawals with no key leak, and the rules a signer should enforce.'
categories = ["Security"]
tags = ["security", "binance", "crypto", "hot-wallet", "incident"]
keywords = ["Binance hack", "Binance hacked", "largest crypto hack", "hot wallet security", "EIP-7702", "TraderTraitor", "Lazarus", "crypto exchange security", "withdrawal signing"]
cover = { image = "/images/covers/binance-hack-hot-wallet-2026.png", alt = "The $6.3B Binance Hack, Technically: No Key Leaked, Withdrawals Signed Anyway", hiddenInSingle = true }
+++

On the evening of 29 October 2026 about $6.3 billion left Binance's wallets, the largest crypto theft on record. Here is what is reported, the attacker's trail on chain, and the lesson for anyone who builds systems that move money.

> Based on public reporting as of 30 October; numbers are still moving and Binance has promised a technical post-mortem. The Go code is my own local example, not Binance's design.

## What is reported

| | |
|---|---|
| When | from 20:05 UTC on 29 October, most of it within about 20 minutes (TRM) |
| Loss | about $6.36B across ten blockchains (TRM); Binance estimates about $6.3B |
| Frozen | about $2.7B: Tether, Circle, Ripple, World Liberty Financial and the Arbitrum Security Council (TRM) |
| Attribution | TRM: North Korea's TraderTraitor, "high confidence"; Binance has not attributed |
| Response | withdrawals suspended on multiple networks; losses covered from the SAFU fund and company funds |

## The sentence that matters

Binance's initial statement, as quoted by CoinDesk:

> "...may involve a compromised DevOps engineer's laptop, which allowed an attacker to gain access to a service container and submit unauthorized withdrawal transactions. We have found no evidence of any wallet private key leak."

The attacker did not need the keys. They reached a service that was *allowed to ask* for signatures.

## The on-chain trail: 50 pre-signed authorizations

On Ethereum, according to TRM Labs, the attacker used {{< term "eip-7702" "EIP-7702" >}}, which lets an ordinary wallet hand its behavior to a smart contract by signing an authorization. At 20:20 UTC one transaction carried **50 authorizations**, all signed by Binance's {{< term "hot-wallet" "hot wallet" >}}, each pointing it at a sweeper contract that only took orders from the attacker.

Why 50? An authorization is only valid at the wallet's current nonce, and a busy hot wallet keeps moving its nonce forward. Signatures for 50 consecutive nonces guaranteed one would match. Three minutes later the whole balance left: 167,464 ETH and 1.615 billion USDT. The delegation stayed in place, and new deposits were swept again until 23:56.

The bigger point: on nine other chains, with different key types and signing schemes, the transfers were **ordinary** signed transactions, all within about half an hour. TRM's assessment is that the attacker could make Binance's hot wallet signing system sign whatever it chose. That fits Binance's statement: no key leaked, but the signer signed what it was asked to. TRM saw the same pattern, signatures obtained in advance and executed in one burst, in the 2025 Bybit hack.

## What we don't know yet

- How the laptop reached a production container. Binance has not published a root cause.
- Why the signing layer signed for ten chains with no limit or approval in the way. TRM suggests the batch of 50 means access was time-limited or signatures had to be requested through a system. No report mentions {{< term "multisig" "multisig" >}} or MPC.

## The laundering path

Issuers can freeze {{< term "stablecoin" "stablecoins" >}}, so the attacker raced to convert. Per TRM, about 325 million USDT was sold to market makers through UniswapX at a loss of more than 10%, and 60 million USDT on Aave backed a loan of about 19,760 ETH. The attacker now holds about $2.4B in ETH and BTC that nobody can freeze.

## What a signer should enforce

If you run anything that signs money movements, the signer must not trust its caller. The policy belongs next to the key, is checked independently, and fails closed. The core of a small local Go example (approvals are plain strings here; in a real system they are signatures the signer verifies):

```go
func (s *Signer) Sign(w Withdrawal, now time.Time) error {
	if s.halted {
		return ErrHalted
	}
	if w.Kind != "transfer" {
		return ErrKind // e.g. an unexpected EIP-7702 authorization
	}
	seen := map[string]bool{}
	for _, a := range w.Approvals {
		if a != w.Requester {
			seen[a] = true
		}
	}
	if len(seen) < 2 {
		return ErrApprovals
	}
	if !s.AllowedTo[w.To] {
		return ErrDest
	}
	// sum what was signed inside the window (trimmed)
	if sum+w.AmountUSD > s.WindowCap {
		s.halted = true // fail closed: stop everything, page a human
		return ErrCap
	}
	s.signed = append(s.signed, entry{now, w.AmountUSD})
	return nil
}
```

I simulated an attacker who controls the service that submits withdrawals, with a $50M cap per hour. The real run with Go 1.27:

```
20:05 w0 $0           REJECTED: EIP-7702 authorization not expected, refusing to sign
20:06 w1 $30000000    REJECTED: need 2 approvals from people other than the requester
20:07 w2 $30000000    REJECTED: need 2 approvals from people other than the requester
20:08 w3 $30000000    REJECTED: destination not on allowlist
20:09 w4 $30000000    SIGNED
20:10 w5 $30000000    REJECTED: window cap exceeded, halting signer
20:11 w6 $1000        REJECTED: signer halted, manual review required
```

`w0` is an authorization request, refused even with two approvals. `w1` and `w2` show the service cannot approve itself, and `w3` goes to an unknown address. `w4` is the worst case: the attacker also controls the approvers and an allowlisted address, and one withdrawal gets through. `w5` hits the cap, so the signer stops everything, like a {{< term "kill-switch" "kill switch" >}}; `w6`, a small legitimate transfer, waits for a human.

## A few things to watch

- {{< term "least-privilege" "Least privilege" >}} for laptops: an engineer's everyday machine should not have a standing path to a service that can obtain signatures.
- TRM's advice: reject EIP-7702 authorizations unless expected, treat a request for many authorizations across a nonce range as an indicator of compromise, and alert immediately on any delegation on a treasury wallet.
- Separate signing infrastructure by chain and wallet tier, so the {{< term "blast-radius" "blast radius" >}} of one compromise is not ten chains.
- Prepare {{< term "incident-response" "incident response" >}} with stablecoin issuers in advance. Tether froze 971 million USDT in the receiving wallet 37 minutes after the main sweep.

## Sources

- [TRM Labs: North Korea Steals USD 6.36 Billion From Binance](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history)
- [CoinDesk: Binance loses over $6 billion in the largest crypto hack to date](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets)
- [Al Jazeera: Binance says $6.3bn stolen](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)
- [TechCrunch: Binance pauses withdrawals](https://techcrunch.com/2026/10/29/binance-pauses-withdrawals-as-hackers-suspected-of-stealing-billions-in-crypto/)
