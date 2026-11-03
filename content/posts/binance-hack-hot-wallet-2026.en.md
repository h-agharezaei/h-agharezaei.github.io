+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'The $6.3B Binance Hack, Technically: No Sign of a Leaked Key, Withdrawals Signed Anyway'
seoTitle = 'The $6.3B Binance Hack: A Technical Look'
description = 'The Binance hack of October 2026, technically: what Binance said, what TRM Labs and Chainalysis found on chain, and the rules a hot wallet signer should enforce.'
contentType = 'analysis'
categories = ["Security"]
tags = ["security", "binance", "crypto", "hot-wallet", "incident"]
keywords = ["Binance hack", "Binance hacked", "largest crypto hack", "hot wallet security", "EIP-7702", "TraderTraitor", "Lazarus", "crypto exchange security", "withdrawal signing"]
cover = { image = "/images/covers/binance-hack-hot-wallet-2026.png", alt = "The $6.3B Binance Hack, Technically: No Sign of a Leaked Key, Withdrawals Signed Anyway", hiddenInSingle = true }
+++

On 29 October 2026 Binance lost about $6.3 billion, the largest crypto theft on record. I separate what Binance said, what analytics firms report, and my own reading, which is analysis, not fact.

> Based on public reporting up to 30 October 2026; Binance's promised post-mortem is not out yet. The Go code is my own local example, not Binance's design.

## What Binance has said

- **Loss and response.** Binance estimates about $6.3 billion, suspended withdrawals and said it "will cover all losses from the SAFU fund and the company's funds" ([BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/)).
- **First explanation, 29 October.** Quoted by [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets): "initial investigation suggests that the security incident may involve a compromised DevOps engineer's laptop, which allowed an attacker to gain access to a service container and submit unauthorized withdrawal transactions. We have found no evidence of any wallet private key leak."
- **Update, 30 October.** Binance said it had "uncovered additional points of breach"; co-CEO Richard Teng wrote that "the attacker did not simply use one engineer's permissions" ([The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor)).

So the laptop is a preliminary, partial explanation, not a confirmed root cause. Binance has not named an attacker.

## What analytics firms report

Third-party on-chain findings, mostly from [TRM Labs' report](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history) of 30 October:

- From 20:05 UTC about $6.36B left across ten blockchains, mostly within 20 minutes. An early Chainalysis figure, per CoinDesk, was about $5.9B.
- On Ethereum, one transaction carried **50 {{< term "eip-7702" "EIP-7702" >}} authorizations** signed by Binance's {{< term "hot-wallet" "hot wallet" >}}, delegating it to the attacker's sweeper contract; it moved 167,464 ETH and 1.615 billion USDT. Follow-up sweeps ran until 23:56.
- Other chains saw ordinary signed transfers. TRM reads this as a compromise of the hot wallet signing infrastructure.
- TRM attributes the attack to North Korea's TraderTraitor "with high confidence"; Chainalysis agrees. The FBI has not attributed it ([Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/)).
- TRM counts about $2.7B frozen by issuers and the Arbitrum Security Council; Binance says about $3B ([Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)). Tether's first freeze, 971 million USDT, came 37 minutes after the main sweep.
- About 325 million USDT was sold through UniswapX at over 10% discount; the attacker still holds about $2.4B in unfreezable ETH and BTC.

## My reading: the signer signed what it was asked

This is my analysis, not a reported finding. If "no evidence of a key leak" holds, the attacker reached something allowed to *ask* for signatures. Fifty authorizations fit the protocol: each is valid only at the wallet's current nonce, which a busy hot wallet keeps moving, so signing a range makes one match. A signer that produced them, and signed on ten chains, suggests policy checks near the key were missing or bypassed. No source I found says whether {{< term "multisig" "multisig" >}} or MPC was involved.

## What a signer should enforce

A signer of money movements must not trust its caller: the policy sits next to the key, is checked independently, and fails closed. The core of a small local Go example (approvals are plain strings here; a real signer verifies signatures):

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

I simulated an attacker controlling the withdrawal-submitting service, with a $50M hourly cap. The real run with Go 1.27:

```
20:05 w0 $0           REJECTED: EIP-7702 authorization not expected, refusing to sign
20:06 w1 $30000000    REJECTED: need 2 approvals from people other than the requester
20:07 w2 $30000000    REJECTED: need 2 approvals from people other than the requester
20:08 w3 $30000000    REJECTED: destination not on allowlist
20:09 w4 $30000000    SIGNED
20:10 w5 $30000000    REJECTED: window cap exceeded, halting signer
20:11 w6 $1000        REJECTED: signer halted, manual review required
```

`w0`, an authorization request, is refused even with two approvals. In `w1` and `w2` the service cannot approve itself; `w3` targets an unknown address. In `w4` the attacker also controls approvers and an allowlisted address, so one withdrawal passes. `w5` hits the cap and the signer stops everything, like a {{< term "kill-switch" "kill switch" >}}; `w6`, a small legitimate transfer, waits for a human.

## Hot wallet controls this incident argues for

- {{< term "least-privilege" "Least privilege" >}}: an engineer's everyday laptop should have no standing path to a service that can obtain signatures.
- TRM's advice: reject unexpected EIP-7702 authorizations, treat many across a nonce range as an indicator of compromise, and alert on any treasury wallet delegation.
- My suggestion: separate signing by chain and wallet tier, so the {{< term "blast-radius" "blast radius" >}} of one compromise is not ten chains.
- Prepare {{< term "incident-response" "incident response" >}} with {{< term "stablecoin" "stablecoin" >}} issuers in advance.

## Sources

- [TRM Labs report](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history), 30 Oct
- [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets), 29-30 Oct
- [The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor), 30 Oct
- [BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/), 30 Oct
- [Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/), 30 Oct
- [Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue), 30 Oct
