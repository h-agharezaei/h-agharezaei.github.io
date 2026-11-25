+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = 'The $6.3B Binance Hack: From a Fake Job Interview to Signed Withdrawals'
seoTitle = 'Binance Hack: Fake Interview to Signed Withdrawals'
description = 'The Binance hack, from its own report: malware from a fake job interview, access to wallet infrastructure, 50 EIP-7702 signings, and lessons for signers.'
contentType = 'analysis'
categories = ["Security"]
tags = ["security", "binance", "crypto", "hot-wallet", "incident"]
keywords = ["Binance hack", "Binance hacked", "fake job interview", "hot wallet security", "EIP-7702", "TraderTraitor", "Lazarus", "crypto exchange security", "withdrawal signing"]
cover = { image = "/images/binance-hack-cover.png", alt = "Binance security breach, 29 October 2026", hiddenInSingle = true }
+++

On the evening of 29 October 2026 about $6.3 billion left Binance's hot wallets. Five days later Binance published its [initial findings](https://www.binance.com/en/blog/community/3229153443759566763). According to them, this did not start with a flaw in a blockchain. It started on engineers' computers, and one way in was a fake job interview.

> **Update:** this post first went up on 30 October, based on that day's news. It is now rewritten around Binance's report of 3 November and [The Register's coverage](https://www.theregister.com/security/2026/11/03/north-korean-fake-job-interview-led-to-63b-binance-heist/5307398). Binance calls the findings initial and says some technical details will stay confidential. The Go code is my own local example, not Binance's design.

## Three concepts first

A **{{< term "hot-wallet" "hot wallet" >}}** is a wallet whose ability to sign is connected to the network, so an exchange can sign customer withdrawals without a human. That makes it fast, and for the same reason it is the main target.

With **{{< term "mpc" "multi-party computation" >}}** (MPC) the private key never exists in one place. Several parties each hold a share and produce a signature together, so stealing one file or one server does not give you the key.

**{{< term "eip-7702" "EIP-7702" >}}** is an Ethereum feature. An ordinary wallet can sign an "authorization" that delegates some execution rights to a smart contract, without exposing the private key. Each authorization is valid only at the wallet's current nonce, a counter that goes up as the wallet sends transactions.

## The attack chain

Binance describes it as a multi-stage campaign, not a single breach or a simple phishing incident.

### June: a tampered Homebrew

Engineer A from wallet DevOps wanted to install an AI coding tool and downloaded a tampered Homebrew installation found through a search engine. Binance's security team spotted the anomaly, replaced the device and rotated the related credentials. But, the report says, the role of Engineer A and colleagues on the wallet infrastructure team had been exposed to the attacker.

The incident was contained, but the attacker had learned whom to go after.

### September: the fake job interview

This is the {{< term "social-engineering" "social engineering" >}} part:

- Someone posing as a project director contacted Engineer B through a job-hunting platform.
- Round one was a live video interview with a purported HR representative, who shared a social media account with personal photos and videos to build trust.
- Round two was with someone claiming to be the CEO of a fictitious company.
- At the end Engineer B was asked to download an "assignment", a code repository, and ran it on his **work computer**.

Malicious code ran during project setup. According to Binance, it replaced a legitimate development tool component with a malicious one. The published file operations concern `pyenv`, the Python version manager: the real file was deleted, the malicious copy took its name, and the symlink in `/opt/homebrew/bin` was recreated. From then on, running `pyenv` could run the attacker's code. Binance's endpoint tools did not immediately detect it.

### 20 to 29 October: from a laptop to wallet infrastructure

- **20 October:** using Engineer B's compromised computer and an **internal AI tool**, the attacker took control of the computers of Engineer A and Engineer C, a wallet software developer. On A's computer they found a container deployment permission token. The report does not explain how the AI tool was abused.
- **29 October, between 17:15 and 19:56** (no time zone given): the attacker logged onto Engineer C's computer, used credentials stolen from A to deploy a {{< term "container" "container" >}}, and triggered a malicious script.

Binance's first statement on the day, [as quoted by CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets), spoke only of "a compromised DevOps engineer's laptop" and said it had found no evidence of a private key leak. The fuller picture has three engineers and months of preparation.

## The night itself

Times in UTC:

- **20:05 to 20:09:** five hot wallets sent 233.46 million XRP to an attacker address.
- Solana and Optimism hot wallets sent about 970,500 SOL and 44.2 million OP.
- Binance received an internal alert about large transfers and began investigating. The alert time is not given.
- A hot wallet sent 18,270 BTC to an attacker address.
- On Ethereum, the attacker used the **signing service** to exploit EIP-7702: 50 signing transactions to manipulate the account nonce and establish malicious delegation. The attacker's contract gained partial execution rights over a Binance hot wallet.
- **23:56:** the last unauthorized transfer, 2,961.9 ETH, finalized. It had been broadcast earlier and was pending.
- **00:10 on 30 October:** Binance cleared the delegation with a new authorization to the zero address.

[TRM Labs' report of 30 October](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history), built from on-chain data, had seen the same pattern: ten blockchains, 50 authorizations on Ethereum, and 167,464 ETH plus 1.615 billion USDT leaving the delegated wallet.

## Two technical points I find most important

This section is my reading of the report.

**First: MPC protects the key, not the decision to sign.** The affected wallet used MPC. There was no single key to steal, yet the signing service did what it was asked. If an attacker can get a request to the system that looks legitimate, splitting the key does not stop them. What stops them is a policy that checks *what* is being signed.

**Second: pausing withdrawals does not revoke a delegation.** Binance suspended withdrawals, but the authorization stayed on chain and worked independently of the withdrawal infrastructure. Revoking it was not simple either: per the report, because the wallet used MPC there was no single private key to revoke it with immediately, and a special procedure was needed. "How do we take access back" has to be designed and rehearsed before the incident.

## What a signer should enforce

The principle is simple: a signer of money movements **must not trust its caller.** Policy sits next to the signature, is checked independently of the requesting service, and fails closed, meaning that when unsure it refuses to sign.

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

It has four rules: accept only plain transfers, require two approvals from people other than the requester, send only to allowlisted addresses, and cap the amount per time window. When the cap is crossed, stop everything.

To see the effect I simulated an attacker who controls the withdrawal-submitting service, with a $50M hourly cap. The real run with Go 1.27:

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
- In `w4` I assumed the attacker also controls approvers and an allowlisted address, so a $30M withdrawal passes. These rules do not stop every attack; they limit the damage.
- `w5` hits the cap and the signer stops everything, like a {{< term "kill-switch" "kill switch" >}}.
- `w6`, a small legitimate transfer, waits for a human.

One important limit: in this attack the intruder could deploy a new container into wallet infrastructure. Whoever can change the signer, or the environment around it, can get around a rule written in code. *Who can deploy the signer* matters as much as the rules.

## The Hacker News discussion

The [Hacker News thread](https://news.ycombinator.com/item?id=50365755) was long. These are readers' opinions, not findings, but there are good questions in it:

- Why was a deploy token on a laptop? Several argue deploys should go only through CI with secrets kept off laptops. Others answer that CI does not stop someone triggering the wrong pipeline.
- Dual approval and separation of duties for any access that reaches funds.
- Interview "assignment" code should only ever run in an isolated environment.

## Controls this incident argues for

- Never run unknown code, interview assignments included, on a work machine. A developer's tools are a {{< term "software-supply-chain" "supply chain" >}} too: don't get installers from search results or ads.
- {{< term "least-privilege" "Least privilege" >}}: a wallet deploy token should not be long-lived and sitting on a laptop.
- Manage internal AI tools like any other high-privilege service. Here one was part of the attacker's path.
- Reject unexpected EIP-7702 authorizations and alert on any delegation on a treasury wallet.
- Prepare and rehearse the procedure for revoking a delegation.
- Separate signing by chain and wallet tier, so the {{< term "blast-radius" "blast radius" >}} of one compromise is not every chain.
- Prepare {{< term "incident-response" "incident response" >}} with {{< term "stablecoin" "stablecoin" >}} issuers in advance. Per TRM, Tether's first freeze came 37 minutes after the main outflow.

## Losses and aftermath

- About $6.34 billion in digital assets were affected.
- About $2.85 billion has been frozen or intercepted, subject to reconciliation and market prices.
- Binance says it absorbs the loss and had replenished 98% of the affected assets as of 31 October.
- The FBI [attributed the theft](https://www.theregister.com/security/2026/11/02/fbi-pins-63b-binance-crypto-heist-on-north-korean-hackers/5306889) to TraderTraitor, a North Korean operation linked to Lazarus. TRM had reached the same conclusion earlier.
- Binance says it rebuilt the wallet system and the AI tool, replaced devices and decommissioned the affected engineers' credentials.

## What is still not known

- How exactly the internal AI tool opened the way to other computers.
- How the container and script got the signing service to sign.
- What limits and policies the signing service had, and why they did not stop this volume. Binance only says it is reviewing signing policy coverage and hot wallet controls.

## Sources

- [Binance: Initial Findings and Response Update](https://www.binance.com/en/blog/community/3229153443759566763), 3 Nov
- [The Register: North Korean fake job interview led to $6.3B Binance heist](https://www.theregister.com/security/2026/11/03/north-korean-fake-job-interview-led-to-63b-binance-heist/5307398), 3 Nov
- [The Register: FBI pins $6.3B Binance crypto heist on North Korean hackers](https://www.theregister.com/security/2026/11/02/fbi-pins-63b-binance-crypto-heist-on-north-korean-hackers/5306889), 2 Nov
- [SANS ISC: Malicious Ad for Homebrew](https://isc.sans.edu/diary/32942); Binance cites it for the tampered Homebrew, though the diary itself does not mention Binance
- [TRM Labs](https://www.trmlabs.com/resources/blog/north-korea-steals-usd-6-36-billion-from-binance-in-the-largest-hack-in-history), 30 Oct
- [CoinDesk](https://www.coindesk.com/business/2026/10/29/potential-multi-billion-binance-hack-hitting-crypto-markets), 29-30 Oct
- [Hacker News](https://news.ycombinator.com/item?id=50365755)
