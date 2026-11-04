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

On the evening of 29 October 2026 about $6.3 billion left the Binance exchange. According to the reports, it is the largest crypto theft on record. In this post I want to say plainly what happened, why this kind of attack is so dangerous, and which rules a signing service should enforce to limit it.

The core point first. Binance says it found no evidence that any wallet private key leaked. Yet unauthorized withdrawals were signed anyway. So the attacker did not need to steal a key; it was enough to reach something that is allowed to *ask* the signer for signatures. I explain that difference below.

I keep three things apart in this post: what Binance said, what blockchain analytics firms saw on chain, and my own reading, which is analysis and not a reported fact.

> Based on public reporting up to 30 October 2026; Binance's promised post-mortem is not out yet. The Go code is my own local example, not Binance's design.

## Two concepts first

A **{< term "hot-wallet" "hot wallet" >}** is a wallet whose signing key is connected to the network, so an exchange can sign customer withdrawals without a human. That makes it fast, and for the same reason it is the main target. Exchanges usually keep only a small share of funds hot and the rest offline.

For a hot wallet, whoever can ask it to sign is almost as dangerous as whoever holds the key.

**{< term "eip-7702" "EIP-7702" >}** is an Ethereum feature. With it an ordinary wallet can sign an "authorization" that hands its behavior over to a smart contract. From then on the contract's code runs on the wallet. If a hot wallet signs such an authorization for an attacker's contract, the attacker effectively controls it. Each authorization is valid only at the wallet's current nonce, a counter that goes up by one with every transaction the wallet sends.

## What Binance has said

- **Loss and response.** Binance estimates about $6.3 billion. According to [BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/) it suspended deposits and withdrawals and said it "will cover all losses from the SAFU fund and the company's funds".
- **First explanation, 29 October.** Quoted by [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets): "initial investigation suggests that the security incident may involve a compromised DevOps engineer's laptop, which allowed an attacker to gain access to a service container and submit unauthorized withdrawal transactions. We have found no evidence of any wallet private key leak."

In plain words: the early finding was that an engineer's laptop was compromised, the attacker used it to reach a service container and submit withdrawals, and Binance found no sign of a leaked private key.

- **Update, 30 October.** Binance said it had "uncovered additional points of breach"; co-CEO Richard Teng wrote that "the attacker did not simply use one engineer's permissions" ([The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor)).

So the laptop is a preliminary, partial explanation, not a confirmed root cause. Binance has not named an attacker.

## What analytics firms saw on chain

Next, the third-party findings, mostly from [TRM Labs' report](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history) of 30 October. (When I tried to open the TRM page again to re-check, the server answered 403, so this part is as the earlier version of this post had it and I did not re-verify it.)

- From 20:05 UTC about $6.36B left across ten blockchains, mostly within 20 minutes. Per CoinDesk, Chainalysis put its own estimate at about $5.9B.
- On Ethereum, one transaction carried **50 EIP-7702 authorizations** signed by Binance's hot wallet, delegating it to the attacker's "sweeper" contract. It moved 167,464 ETH and 1.615 billion USDT. Follow-up sweeps ran until 23:56.
- Other chains saw ordinary signed transfers. TRM reads this as a compromise of the signing infrastructure.
- TRM attributes the attack to North Korea's TraderTraitor group "with high confidence"; Chainalysis agrees. Binance itself has not named an attacker.
- TRM counts about $2.7B frozen by token issuers and the Arbitrum Security Council; Binance said about $3B ([Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue)). Tether's first freeze, 971 million USDT, came 37 minutes after the main sweep.
- About 325 million USDT was sold through UniswapX at over 10% discount. The attacker still holds about $2.4B in ETH and BTC that cannot be frozen.

On attribution: [Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/) wrote on 30 October that the FBI was only engaged with partners and had not attributed the theft. When I re-read that page for this rewrite, an editor's note said the story had been updated to reflect the FBI's attribution of the hack to North Korea. So that part of my first version is out of date.

## My reading: the signer signed what it was asked

This is my analysis, not a reported finding. If "no evidence of a key leak" holds, the attacker reached something that was allowed to ask for signatures.

The number 50 also seems logical to me. Each authorization is valid only at the wallet's current nonce, and a busy hot wallet's nonce keeps moving. So if the attacker gets signatures for a whole range of nonces, one of them lands exactly on the nonce at execution time.

If a signer produced those authorizations, and signed transfers on ten chains too, I think the policy checks next to the key were missing or bypassed. I found no source saying whether {< term "multisig" "multisig" >} or MPC was involved, so I say nothing about that.

## What a signer should enforce

One principle follows from this: a signer of money movements must not trust its caller. The policy sits next to the key, is checked independently of the requesting service, and fails closed, meaning that when unsure it refuses to sign.

Here is the core of a small local Go example. Approvals are plain strings; a real signer verifies the approvers' signatures:

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

It has four rules: accept only plain transfers, require two approvals from people other than the requester, send only to allowlisted addresses, and keep a cap on the amount per time window. When the cap is crossed, stop everything.

To see the effect I simulated an attacker who controls the withdrawal-submitting service, with a $50M hourly cap. I re-ran it for this rewrite with Go 1.27 and got the same output:

```
20:05 w0 $0           REJECTED: EIP-7702 authorization not expected, refusing to sign
20:06 w1 $30000000    REJECTED: need 2 approvals from people other than the requester
20:07 w2 $30000000    REJECTED: need 2 approvals from people other than the requester
20:08 w3 $30000000    REJECTED: destination not on allowlist
20:09 w4 $30000000    SIGNED
20:10 w5 $30000000    REJECTED: window cap exceeded, halting signer
20:11 w6 $1000        REJECTED: signer halted, manual review required
```

Line by line:

- `w0` is an authorization request and is refused even with two approvals, because its kind is not "transfer".
- In `w1` and `w2` the service cannot approve itself.
- `w3` targets an unknown address.
- In `w4` I assumed the attacker also controls approvers and an allowlisted address, so a $30M withdrawal passes. This matters: these rules do not stop every attack, they limit the damage.
- `w5` hits the cap and the signer stops everything, like a {< term "kill-switch" "kill switch" >}.
- `w6`, a small legitimate transfer, waits for a human.

## Hot wallet controls this incident argues for

From the reports and this example, this is my list:

- {< term "least-privilege" "Least privilege" >}: an engineer's everyday laptop should have no standing path to a service that can obtain signatures.
- TRM's advice: reject unexpected EIP-7702 authorizations, treat many across a nonce range as an indicator of compromise, and alert on any treasury wallet delegation.
- My suggestion: separate signing by chain and wallet tier, so the {< term "blast-radius" "blast radius" >} of one compromise is not ten chains.
- Prepare {< term "incident-response" "incident response" >} with {< term "stablecoin" "stablecoin" >} issuers in advance. Tether's first freeze came 37 minutes after the sweep, and every minute counts.

## What is still not known

- The root cause: Binance itself said the breach points were more than one laptop, and the post-mortem is not out.
- Whether multisig or MPC was in use.
- The exact figures: the estimates ($5.9B, $6.3B, $6.36B, and $2.7B or about $3B frozen) differ between sources.

## Sources

- [TRM Labs report](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history), 30 Oct
- [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets), 29-30 Oct
- [The Next Web](https://thenextweb.com/news/binance-hack-6-3bn-north-korea-tradertraitor), 30 Oct
- [BleepingComputer](https://www.bleepingcomputer.com/news/security/binance-links-63-billion-crypto-theft-to-compromised-devops-laptop/), 30 Oct
- [Nextgov](https://www.nextgov.com/cybersecurity/2026/10/fbi-involved-response-63-billion-binance-hack-linked-north-korea/416946/), 30 Oct
- [Al Jazeera](https://www.aljazeera.com/economy/2026/10/30/binance-says-2-54bn-in-crypto-funds-frozen-amid-potential-security-issue), 30 Oct
