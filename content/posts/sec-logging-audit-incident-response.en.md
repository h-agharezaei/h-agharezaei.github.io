+++
date = '2027-05-31T10:00:00+03:30'
draft = false
title = 'Logging, auditing and incident response'
description = 'Security logging in Go: audit fields, redaction tests, log injection, a hash-chained log, detection rules with precision and recall, and a runbook.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "logging", "audit", "incident-response", "go"]
cover = { image = "/images/covers/sec-logging-audit-incident-response.png", alt = "Logging, auditing and incident response", hiddenInSingle = true }
+++

The previous post, [Fuzzing to find security bugs](/posts/sec-fuzzing/), looked for bugs before an attacker does. Some get through anyway, and then what matters is whether you can tell what happened. For log mechanics see [Logs and journalctl](/posts/linux-logs-journalctl/).

> Defensive only. My own Go 1.26 code, generated events, documentation-range addresses, invented users. Local example.

## Three kinds of log

Application logs help developers; security logs record events like failed logins. An {{< term "audit-log" "audit log" >}} answers who did what to which object, when, from where, with what result. Fields: actor, action, resource, outcome, request id, source IP, UTC timestamp. With `log/slog` (see [Config, structured logging and errors in Go](/posts/go-config-logging-errors/)):

```
{"time":"2027-05-30T09:15:00Z","level":"INFO","msg":"audit","actor":"alice","action":"order.cancel","resource":"order/1042","outcome":"denied","request_id":"req-7f3a","source_ip":"198.51.100.23"}
```

## What not to log

Passwords, tokens, session ids ([Sessions or JWT?](/posts/sec-sessions-vs-jwt/)), full card numbers, surplus personal data. Redacting by key name is not enough, so a test fails when a secret slips through. A careless `note` field carried a token and a card number:

```
--- FAIL: TestNoSecretsLeak (0.00s)
    secrets leaked into the log: [tok_9f8e7d6c5b4a3921 4111111111111111]
    {"level":"INFO","msg":"login","password":"[REDACTED]","token":"[REDACTED]"}
    {"level":"INFO","msg":"debug","note":"retry with tok_9f8e7d6c5b4a3921 card 4111111111111111"}
```

Key-based redaction worked; free text did not. Scanning string values for token and card patterns fixed it. Patterns are a safety net: the real fix is keeping secrets away from the logger, see [Managing secrets and keys](/posts/sec-secrets-management/).

## Log injection

A text logger that trusts input lets a user forge entries ([Injection and XSS](/posts/sec-injection-xss/), [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/)). The user name was `bob result=fail` plus a newline and a fake line:

```
-- naive text logger
2027-05-30T09:15:00Z INFO login user=bob result=fail
2027-05-30T09:15:01Z INFO login user=admin result=ok result=fail
-- slog JSON
{"time":"...","msg":"audit","actor":"bob result=fail\n2027-05-30T09:15:01Z INFO login user=admin result=ok", ...}
```

The naive logger printed a believable "admin logged in" line. {{< term "structured-logging" "Structured" >}} JSON escapes the newline, so one event stays one line.

## Tamper evidence

Each record stores the SHA-256 of the previous hash plus its own content, a {{< term "hash-chain" "hash chain" >}}. A verifier reports the first bad line. Twelve records, a checkpoint every 5 signed with an {{< term "hmac" "HMAC" >}}:

```
edit line 4         chain: line 4: content does not match its hash (edited)
delete line 6       chain: line 6: expected seq 6, found 7 (deleted or reordered)
swap lines 8 and 9  chain: line 8: expected seq 8, found 9 (deleted or reordered)
truncate to 7       chain: ok   checkpoint 10: log ends at line 7 (tail truncated)
truncate to 11      chain: ok   checkpoints: ok
full rewrite        chain: ok   checkpoint 5: hash differs from the log
```

Limits, visible above: cutting the tail leaves a valid chain, only the checkpoint noticed, and losing records after the last checkpoint (line 11) went unnoticed. A full rewrite recomputes the chain, but without the key the checkpoints disagree. Keep the key away from the log writer, and ship logs off the host. On Linux `chattr +a` makes a file append-only (docs only; I did not run it).

## Detection

A seeded generator made 10,030 events over three days: 612 failed logins and 7 injected attacks (four {{< term "credential-stuffing" "credential stuffing" >}} bursts, one slow spray, one impossible-travel login, one 03:00 role change), plus a trap: an office NAT where 40 users fail at once. Rule: alert when one IP fails for N distinct users in a window.

| rule | alerts | true | false | precision | recall |
|---|---|---|---|---|---|
| 24h, 20 users | 4 | 3 | 1 | 0.75 | 0.60 |
| 10 min, 8 users + 24h | 6 | 5 | 1 | 0.83 | 1.00 |
| 10 min, 30 users + 24h | 4 | 3 | 1 | 0.75 | 0.60 |
| 10 min, 41 users + 24h | 4 | 3 | 1 | 0.75 | 0.60 |
| travel (1 h) | 1 | 1 | 0 | 1.00 | 1.00 |
| role change off-hours | 3 | 1 | 2 | 0.33 | 1.00 |

The first rows score the 5 IP-based attacks; the last two are scored separately. A low threshold catches small attacks but fires on the NAT; a high one is quiet and misses attacks. Two legitimate on-call changes explain the 0.33. False alerts cause {{< term "alert-fatigue" "alert fatigue" >}}, so tune against known cases. Real traffic is messier; these numbers only illustrate.

## Incident response

{{< term "incident-response" "Incident response" >}} follows the lifecycle in NIST SP 800-61: preparation, detection and analysis, containment, eradication and recovery, post-incident activity (from memory; check the document). A skeleton to copy into your {{< term "runbook" "runbook" >}}:

```
# Incident <id>   severity: SEV1-3   lead: <name>   comms: <name>
- [ ] Record time, who noticed what
- [ ] Preserve: copy logs and disk snapshot BEFORE cleaning
- [ ] Contain: disable account/key, isolate host (do not wipe)
- [ ] Rotate secrets: outermost first, then dependents
- [ ] Notify: legal/compliance for deadlines (varies by law)
- [ ] Postmortem within a week
```

Severity: SEV1 customer data or full outage, SEV2 partial impact, SEV3 contained. Note who handled evidence and when. Many regulations set notification deadlines; this is not legal advice, ask your legal team. After it ends, write a [blameless postmortem](/posts/eng-postmortems-blameless/).

Tabletop idea (invented): at 03:00 a role change appears on an account whose owner is asleep. Walk the checklist aloud; note the first step nobody knows.

## A few things to watch

- Log the actor and decision, never the secret.
- Structure or escape user input.
- Test alert rules against known attacks and known false alarms.
- Practise the runbook before you need it.

## Exercise

Add a rule for five denied `order.cancel` actions by one actor within a minute, inject it in the generator and report precision and recall.

## What's next

This was the last post of the Security series. The next series are Distributed Systems and Software Engineering.
