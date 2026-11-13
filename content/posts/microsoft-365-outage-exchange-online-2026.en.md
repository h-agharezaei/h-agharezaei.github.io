+++
date = '2026-11-13T10:00:00+03:30'
draft = false
title = 'The November 12 Microsoft 365 Outage: Why Exchange Online Fell Over and Recovery Would Not Hold'
seoTitle = 'Microsoft 365 Outage: EX1550543 and MO1550821'
description = 'Microsoft 365 outage of Nov 12, 2026 (EX1550543, MO1550821): timeline, what Microsoft said, why recovery stalled, CVE-2026-124194 and admin steps.'
contentType = 'analysis'
categories = ["Security"]
tags = ["microsoft-365", "exchange-online", "outlook", "outage", "incident", "cve"]
keywords = ["Microsoft 365 outage", "Outlook down", "Exchange Online outage", "EX1550543", "MO1550821", "CVE-2026-124194", "Outlook vulnerability", "health check", "cascading failure"]
cover = { image = "/images/m365-outage-cover.png", alt = "Microsoft 365 major outage, Exchange Online, EX1550543 and MO1550821, plus Outlook CVE-2026-124194", hiddenInSingle = true }
+++

On Thursday, November 12, 2026, Outlook stopped opening mailboxes for a lot of people. At first only users in the Americas reported it, but a couple of hours later Microsoft said the problem could affect users "in any region". Then it turned out Teams, SharePoint, Copilot and even parts of Defender were affected too. As I write this (the morning of November 13, around 07:00 UTC), nobody has declared it fixed.

What separates this outage from an ordinary "a server went down" story is something Microsoft said halfway through: traffic had not gone up. Servers were failing health checks and dropping out of service, and their load landed on the servers that were left. Then, every time servers were brought back, they fell over again as soon as traffic arrived. Anyone who runs a service behind a {{< term "load-balancer" "load balancer" >}} should recognise that pattern.

Two days earlier, on November Patch Tuesday, Microsoft had fixed an Outlook flaw, CVE-2026-124194, that attackers were already exploiting. Many people read the two stories side by side. So this post covers both and keeps them apart: what was said, what is my analysis, and what is still unknown. As in my post on the [Binance hack](/posts/binance-hack-hot-wallet-2026/), official statements come first and my reading comes after. The mechanism section is about {{< term "cascading-failure" "cascading failure" >}}. If you read [Retry and Dead-Letter Queues in JetStream](/posts/nats-jetstream-retry-dlq/), you already know how unbounded retries push on a system that is already hurting.

Everything below comes from the Microsoft 365 status page and @MSFT365Status account, as reported by SecurityWeek and several other outlets, and from the official CVE records at MSRC and NVD. I had no access to any tenant's admin center and did not read the full EX1550543 posts directly. The only program I ran is a small Go model, explained in the mechanism section.

## Two incident IDs and a status page

Microsoft logs each incident in **Service health** in the admin center under an ID. The two-letter prefix names the service: `EX` is Exchange Online, `MO` is Microsoft 365 in general, and `TM` is Teams. Three IDs matter here:

- **EX1550543**: the Exchange Online outage. Users could not connect to their mailboxes from web, desktop or mobile.
- **MO1550821**: the wider impact on the rest of Microsoft 365. Both were filed as service degradations.
- **TM1550488**: a separate, earlier Teams issue in the Americas (delayed or failed chat messages). According to azureblog its preliminary cause was "resource contention" and it was resolved before EX1550543 started. Sources disagree on its exact window.

One report (UC Today) also names a separate Power Platform advisory, PP1550869. No other source mentions it.

## Timeline

Times are UTC (add 3:30 for Tehran). Most come from azureblog's live log, which uses UK time, and UK time equals UTC in November. Where sources disagree, I note it after the table.

| Time (UTC) | What happened |
|---|---|
| Thu 16:17 | EX1550543 opens. Users cannot reach their mailboxes. |
| about 18:00 | Outlook reports on Downdetector peak around 130,000. That is a count of reports, not of affected users. |
| 18:07 to 18:19 | Microsoft says the problem may affect "any region" and mentions "elevated load across multiple regions". Server restarts begin. |
| 18:26 | MO1550821 opens for the rest of Microsoft 365. |
| 18:29 to 18:57 | Some US traffic is moved off the affected infrastructure and Outlook connections are redistributed worldwide. |
| about 19:06 | All deployments and configuration changes are paused. |
| about 19:18 | Microsoft says the elevated load is not driven by more traffic. |
| 19:43 | Affected servers fail health checks and are removed from service. |
| about 19:57 | "We've not identified any recent change correlated with the start of impact." Microsoft tests a way to bypass the component that processes health checks. |
| 20:56 | With an alternative health-check method, a subset of servers returns to service. |
| 22:00 | Reverting a few recent configuration updates has "not provided the anticipated relief". A "core process" is becoming overwhelmed. |
| Fri 00:00 | Returned servers become unresponsive again when they take traffic. Traffic limits go on in some locations, and some servers are rebuilt with "a previous software configuration". |
| before 01:50 | The process that establishes secure connections is overwhelmed. Microsoft begins reverting "a recent network configuration change that correlates with the start of impact". |
| 03:07 | The change is "not taking as expected". |
| 03:37 to 04:11 | Microsoft executive Charles Lamanna, then the status page, say there is no indication of malicious or cyber activity. |
| 04:22 | Partial recovery across regions, but it is not "resulting in sustained recovery". |
| 04:57 | The mitigations caused a "surge in outbound call volume" from routing services to backend servers. Some machines are "stuck in a bad state" and block a force-sync of the network change. More VMs are added. |
| 06:17 | Microsoft evaluates traffic throttling, protocol adjustments and failover routing. |
| 06:57 | "Marginal success" from patches applied after reboots. |

Where sources disagree: UC Today puts the "any region" statement at 18:07 and partial recovery at 04:10, while azureblog has the times above. A university status mirror quoted by WindowsForum shows EX1550543 starting at 17:46 UTC, not 16:17. For TM1550488, UC Today gives 15:40 to 17:09, while azureblog and BleepingComputer give 14:45 to 15:53. The primary source is the admin center, which I could not read.

## Which services were hit

Microsoft summed up the impact, as SecurityWeek reported: features of services that interact with Exchange Online were affected, and parts that do not depend on it kept working. That sentence is the key to the whole thing. The reported list, from UC Today and azureblog:

- **Exchange Online** in Outlook on the web, desktop and mobile. Inbound mail could be delayed. UC Today tells admins to assume mail is delayed, not lost.
- **Teams**: calendars, meeting scheduling, invites, Live and Virtual events, and creating or deleting private and shared channels. Calls, meetings, chat and standard channels largely worked.
- **Microsoft 365 Copilot** for mail and calendar work, and **SharePoint** features that rely on Exchange.
- **Microsoft Graph**: mail, calendar and contacts requests timed out. So any third-party app or connector that reads mail through Graph was affected too. According to UC Today, OpenAI and Anthropic reported impact on their connectors.
- **Security and compliance**: Defender for Office 365 (including Safe Links, which might fail to process rewritten URLs), Defender XDR, Purview (DLP, auto-labelling, data classification) and Intune.
- **The rest**: Planner, To Do, Universal Print, PDF export of labelled Power BI reports, and Power Apps sign-in.

Take the last point seriously: according to ZDNET, as quoted by WindowsForum, the public status page itself was unavailable for about 45 minutes. The tool meant to announce the outage depended on the system that was down.

## What Microsoft has said about the cause

No root cause has been published yet, and the root cause field is empty on both incidents. Microsoft has promised a {{< term "postmortem" "post-incident review" >}}. What it has said, in order:

1. Traffic did not increase. The extra load came from a large number of servers being unavailable, so the remaining servers had to carry their traffic too.
2. Servers were failing {{< term "health-check" "health checks" >}} and leaving service. Processor usage on the affected servers was high.
3. A process that establishes secure connections (in plain terms, the server side of {{< term "tls" "TLS" >}}) was becoming overwhelmed, and the servers stopped processing requests.
4. A recent network configuration change correlated with the start of impact, and Microsoft rolled it back. But a few hours earlier it had said it found no correlated change. The rollback did not fully take either, because some machines were stuck in a bad state.
5. The mitigations themselves caused a surge of calls from the routing layer to the backend.

So "reverting the network change" is for now a recovery step, not a confirmed cause. Cyber Security News says the same thing explicitly.

## My reading: how a health check becomes an amplifier

From here on it is my analysis, not something Microsoft said. I cannot see inside Exchange Online. I am only saying which known pattern these symptoms fit.

The core idea is simple. A health check is supposed to take a broken server out of the path so users do not hit it. But a health check cannot tell "this server is broken" from "this server is overloaded". If a server answers slowly because it is busy, it fails the check and is removed. Its load moves to the others, they slow down and get removed too. That is a cascading failure, and the incoming traffic stays flat the whole time. That is exactly what Microsoft said.

The second piece is the cost of connecting. When a server drops out, its clients have to connect to another one. A new connection means a full TLS handshake, and a handshake is much more expensive than a request on a connection that is already open. So the load that moves is heavier than the load it replaces. When Microsoft says "the process that establishes secure connections was overwhelmed", I think of exactly this: a wave of reconnects, a {{< term "thundering-herd" "thundering herd" >}} of Outlook clients from all over the world. That is my guess.

To see the mechanism, I wrote a small Go model and ran it on macOS. It is not Exchange, and every number in it is invented. It has 100 servers with slightly different capacities (90 to 110 units) and a fixed load of 7,000 units per tick. The health check removes any server whose load exceeds its capacity. The handshake cost parameter says how much more expensive a request is when it has to open a new connection. The core of the model is this function:

```go
// step spreads admitted load (plus handshake cost of the moved/new part) evenly over
// healthy servers. The health check then removes every server whose load exceeds its
// capacity.
func (p *pool) step(admitted, fresh float64) (load float64, failed int) {
	n, _ := p.healthy()
	if n == 0 {
		return 0, 0
	}
	load = (admitted + fresh*p.setup) / float64(n)
	for i, u := range p.up {
		if u && load > capacity(i) {
			p.up[i] = false
			failed++
		}
	}
	return
}
```

First we lose 20 servers at once, once with no reconnect cost and once with a 50% cost:

```text
lost 20 servers, handshake cost 0%
tick  healthy  load/server  failed-check
   1       80         87.5             0
   2       80         87.5             0

lost 20 servers, handshake cost 50%
tick  healthy  load/server  failed-check
   1       80         96.2            28
   2       52        160.5            52
```

In the first run each server carries 87.5 units. The weakest server has a capacity of 90, so nobody is removed and everything is stable. Losing 20% of capacity was not a problem on its own.

In the second run the same 20 servers are gone, but their 1,400 units of traffic have to open new connections. That one-off cost pushes the load to 96.2. The 28 weaker servers fail the check. Their traffic moves too, and on the second tick the load reaches 160.5 and all 52 remaining servers drop out. Traffic was flat, and the remaining capacity was enough in steady state. The cost of moving made the difference.

## Why recovery would not hold

Microsoft said several times that returned servers fell over again once traffic reached them. The model shows that as well. All servers are down, and 10 are restarted per tick. In the first run all traffic goes straight to the healthy servers:

```text
recovery, throttle=false
tick  healthy  admitted  load/server  failed-check
   1       10      7000       1050.0            10
   2       10      7000       1050.0            10
   3       10      7000       1050.0            10
   4       10      7000       1050.0            10
   5       10      7000       1050.0            10
```

Every time 10 servers come up, the whole load plus the handshake cost of the new connections lands on them (1,050 units each, for servers with a capacity around 100), and they all fail the check. Restarting does not help, because there are never enough healthy servers at the same time to carry the load.

In the second run I added a simple admission control: accept only as much traffic as fits in 90% of the healthy servers' capacity, counting the handshake cost of newly admitted traffic. Everything else is rejected, so some users temporarily see errors. That is {{< term "load-shedding" "load shedding" >}}:

```text
recovery, throttle=true
tick  healthy  admitted  load/server  failed-check
   1       10       567         85.0             0
   2       20      1383         89.5             0
   3       30      2229         88.4             0
   4       40      3131         89.6             0
   5       50      4013         89.1             0
   6       60      4921         89.6             0
   7       70      5811         89.4             0
   8       80      6717         89.6             0
   9       90      7000         79.4             0
```

The admitted column climbs step by step and per-server load stays under 90. No server fails the check, and by tick nine all traffic is accepted. The price is that most users are turned away in the early ticks. Without it, nobody gets service at all.

In the later hours Microsoft reached for exactly these tools: traffic limits in some locations, throttling, more machines and failover routing. My model cannot say why it did not work at first. Perhaps it was the stuck machines, or the surge of calls in the routing layer that Microsoft itself reported.

## CVE-2026-124194: the Outlook flaw in the same news cycle

This vulnerability has nothing to do with the outage, and Microsoft has not linked them. But since it came up at the same time and both involve Outlook, I read the MSRC and NVD records:

- **Title:** Microsoft Outlook Spoofing Vulnerability, published November 10, 2026, on Patch Tuesday.
- **Severity:** Moderate, {{< term "cvss" "CVSS" >}} 3.1 score 6.5 with vector `AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N`. The weakness is CWE-356, "Product UI does not warn user of unsafe actions".
- **Exploitation:** Microsoft marks it Exploitation Detected, meaning it was exploited before the patch. It was not publicly disclosed. CISA added it to the {{< term "kev" "KEV" >}} catalog on November 10, and the deadline for US federal agencies is November 24.
- **Mechanism, per Microsoft's FAQ:** the attacker sends a crafted message file and convinces the user to open it in Outlook. Outlook connects to an attacker-controlled network location without showing the usual external-content warning, and the user's {{< term "ntlm" "NTLMv2" >}} hash leaks. The attacker can use that hash to impersonate the user. The Preview Pane is not an attack vector, so the user has to open the file.
- **Products and fixed builds:** Microsoft 365 Apps for Enterprise (32- and 64-bit, per the update channel release notes), Office LTSC 2024 before `16.0.17932.21140`, and Office LTSC 2021 before `16.0.14334.21048`.

According to SecurityWeek, this Patch Tuesday fixed 1,094 vulnerabilities in total. I did not check that number against another source.

The MSRC record lists no mitigation or workaround for this CVE, only the patch. For an older, similar bug, CVE-2023-23397, which also leaked NTLM hashes from Outlook, Microsoft recommended two things: put sensitive users in the Protected Users group, and block outbound SMB (TCP 445) to the internet. That is sensible here too, but it is my suggestion based on that older guidance, not guidance for this CVE.

### Why I keep the two side by side

This part is also my analysis. CVE-2026-124194 needs a user who opens a message file. An outage day is exactly the day users are ready to open anything titled "Restore your mailbox" or "New Outlook configuration file", and IT is busy. I have not seen reports of such a campaign. But if the November patch is not on every client yet, the days after the outage are a good time to finish it.

## What admins should do

1. **Follow the incident IDs, not social media.** In the admin center under Health > Service health, open EX1550543 and MO1550821 and check the Scope of impact field. If the admin center does not load, use status.cloud.microsoft and @MSFT365Status. According to the Microsoft Graph docs, the same data is available from `GET /admin/serviceAnnouncement/issues/EX1550543` with the `ServiceHealth.Read.All` permission. I did not run that request because I had no tenant.
2. **Send notifications to an address outside Microsoft 365.** If Service health alerts go to your own Exchange mailbox, you will not get them during an Exchange outage. That is the same lesson as the status page that went down.
3. **Do not add work.** azureblog and UC Today both say: do not reinstall Office, do not rebuild Outlook profiles, do not reset passwords. The problem is on Microsoft's side, and these steps only create support work after recovery. Freeze your own changes too, as Microsoft did, so that if something breaks you know where it came from.
4. **Assume delay, and tell users early**, over a channel that does not depend on Exchange. Teams calls and chat mostly worked. Do not count on calendars, invites or Copilot over mail.
5. **Expect gradual recovery.** Even after recovery is announced, some users may see problems for a while. That is the same step-by-step admission we saw in the model.
6. **Save the post-incident review.** According to azureblog, Service health keeps history for only 30 days.
7. **Finish rolling out the CVE-2026-124194 patch**, and if you have not already, block outbound SMB to the internet.

## Lessons for our own systems

- **A health check should not only ask "alive or not".** An overloaded server is not a dead server. If you remove both the same way, the health check spreads the failure. Many load balancers have a minimum healthy percentage: if most backends fail the check at once, they send traffic to all of them, because a broken check is more likely than every server being broken.
- **Count reconnect cost in your capacity.** Steady-state capacity is not enough. The right question is: if 20% of servers drop out and all their clients handshake at once, what happens? Clients also need {{< term "exponential-backoff" "exponential backoff" >}} with {{< term "jitter" "jitter" >}} so they do not create a {{< term "retry-storm" "retry storm" >}}.
- **Bringing servers back without admission control does not work.** A new server should take traffic gradually (slow start in the load balancer), and the system must be able to reject excess requests quickly instead of letting them queue and take the whole server down.
- **Measure {{< term "blast-radius" "blast radius" >}} by dependencies, not service names.** Teams, Copilot, Purview and Safe Links are not "email", but they all lean on Exchange. Know the hidden dependencies in your own system, and do not make your monitoring and status page depend on the system they monitor.
- **A {{< term "rollback" "rollback" >}} also needs a healthy system.** Microsoft reverted the network change, but stuck machines kept the change from syncing. The path that ships changes should not depend on the health of the thing you are trying to fix.

## What is known and what is not

- **From sources:** the IDs EX1550543 and MO1550821, the timeline, the list of affected services, Microsoft's statements about health checks, flat traffic, the secure-connection process and the network change rollback, the absence of signs of an attack, and every detail of CVE-2026-124194 from the MSRC and NVD records.
- **From me:** linking the symptoms to a cascading failure and a handshake wave, the Go model that only shows the logic and uses invented numbers, and the CVE mitigations taken from the CVE-2023-23397 guidance.
- **Not checked:** the original admin center posts, the Graph request, and anything about Exchange Online's internal architecture.
- **Open:** the root cause, the time of full recovery, and the post-incident review. If the review is published and contradicts anything here, I will update this post.

## Sources

- [SecurityWeek: Microsoft 365 Outage Disrupts Outlook, Exchange Online and Teams](https://www.securityweek.com/microsoft-365-outage-disrupts-outlook-exchange-online-and-teams/)
- [UC Today: Microsoft 365 Outage: Outlook Down, and the Fix Won't Hold](https://uctoday.com/microsoft-365-outage-outlook-exchange-teams-copilot)
- [azureblog: Microsoft 365 outage, 12 November 2026](https://azureblog.co.uk/posts/microsoft-365-outage-12-november-2026/)
- [Cyber Security News: Massive Microsoft 365 Outage](https://cybersecuritynews.com/massive-microsoft-365-outage/)
- [Microsoft 365 service status](https://status.cloud.microsoft/)
- [MSRC: CVE-2026-124194](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-124194)
- [NVD: CVE-2026-124194](https://nvd.nist.gov/vuln/detail/CVE-2026-124194)
- [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-124194)
- [Microsoft Graph: Get serviceHealthIssue](https://learn.microsoft.com/en-us/graph/api/servicehealthissue-get)
