+++
date = '2027-05-31T10:00:00+03:30'
draft = false
title = 'Logging, auditing and incident response'
description = 'Security logging in Go: audit fields, redaction tests, log injection, a hash-chained log, detection rules with precision and recall, and a runbook.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "logging", "audit", "incident-response", "go"]
cover = { image = "/images/covers/sec-logging-audit-incident-response.png", alt = "Logging, auditing and incident response", hiddenInSingle = true }
+++

Imagine you are on call and a customer writes: "someone cancelled my order 1042, and I did not do it." You open the logs and find one line: `order 1042 cancelled`. No user, no address, no time zone, no way to tell whether this was the customer, a support agent, or a stolen session. The log exists, but it cannot answer the only question that matters now: who did what to which object, and when?

This post is about making sure your logs can answer that question after a bug has got past everything else, such as the fuzzing in [Fuzzing to find security bugs](/posts/sec-fuzzing/). It also covers the other side of the same coin: what a log must never contain, how a log can be forged or edited, how you notice an attack from the log, and what you do in the first hour of an incident. For the mechanics of reading logs on a Linux machine, see [Logs and journalctl](/posts/linux-logs-journalctl/).

> Defensive only. This is my own Go code, with generated events, addresses from the documentation ranges and invented users. The original run used Go 1.26; for this rewrite I re-ran everything with Go 1.27.3 and the outputs were the same (the demo uses a fixed timestamp and a seeded generator, so it is repeatable). It is a local example.

## Three kinds of log

The word "log" covers three different things, and mixing them is how you end up with the line above.

- **Application logs** help developers debug: "cache miss", "retrying in 2s".
- **Security logs** record events that matter for defence, such as failed logins.
- An {{< term "audit-log" "audit log" >}} is the strictest. It answers one question: *who did what to which object, when, from where, and with what result.* It is meant for investigators and sometimes for legal use, not for debugging.

So every audit record needs a fixed set of fields: the **actor** (who), the **action** (what), the **resource** (which object), the **outcome** (allowed, denied, failed), a **request id** (so you can find the other logs of the same request), the **source IP**, and a **UTC timestamp**. With `log/slog` from the standard library (see [Config, structured logging and errors in Go](/posts/go-config-logging-errors/)) a record looks like this:

```
{"time":"2027-05-30T09:15:00Z","level":"INFO","msg":"audit","actor":"alice","action":"order.cancel","resource":"order/1042","outcome":"denied","request_id":"req-7f3a","source_ip":"198.51.100.23"}
```

Read it as a sentence: at that time, `alice` tried to `order.cancel` on `order/1042`, was `denied`, from `198.51.100.23`, in request `req-7f3a`. Everything you would need in the situation above is on one line. Note that the demo fixes the timestamp so that the output is repeatable; a real logger writes the current UTC time.

## What not to log

An audit log is only useful if you can keep it and share it, so it must not become a place where secrets live. Never log passwords, tokens, session ids (see [Sessions or JWT?](/posts/sec-sessions-vs-jwt/)), full card numbers, or personal data you do not need.

The obvious defence is to redact by key name: whenever a field is called `password` or `token`, write `[REDACTED]` instead of its value. That is not enough, because secrets also arrive inside free text. So I wrote a test that logs a request the way a careless handler might, and fails when any known secret value reaches the output. The careless `note` field carried a token and a card number. The test ran with the scanning turned off (the demo reads an environment variable for that), to show what the failure looks like:

```
--- FAIL: TestNoSecretsLeak (0.00s)
    secrets leaked into the log: [tok_9f8e7d6c5b4a3921 4111111111111111]
    {"level":"INFO","msg":"login","password":"[REDACTED]","token":"[REDACTED]"}
    {"level":"INFO","msg":"debug","note":"retry with tok_9f8e7d6c5b4a3921 card 4111111111111111"}
```

The first line lists the secrets that leaked: the token and the card number (a well-known test card number, not a real one). The two log lines show why. The `login` line is fine: the keys `password` and `token` were redacted by name. The `debug` line is not: the secrets sit inside the `note` text, where key-based redaction does not look. When I turn on the second layer, which scans every string value for token and card patterns, the test passes (it is the default in the demo, and `go test -v` shows `PASS`).

That scanner is only a safety net. Patterns will always miss something. The real fix is to keep secrets away from the logger in the first place; see [Managing secrets and keys](/posts/sec-secrets-management/).

## Log injection

The next risk is the opposite: not what you write, but what a user can make you write. If a text logger puts user input straight into a line, the user can end that line with a newline and write a second, fake one. This is {{< term "log-injection" "log injection" >}}, close in spirit to the injection bugs in [Injection and XSS](/posts/sec-injection-xss/) and [The OWASP Top 10 in real code](/posts/sec-owasp-top10-in-code/).

To see it, I log a login with the user name `bob result=fail`, a newline, and then a fake line saying that `admin` logged in. I do it twice: with a naive text logger, and with `slog` writing JSON:

```
-- naive text logger
2027-05-30T09:15:00Z INFO login user=bob result=fail
2027-05-30T09:15:01Z INFO login user=admin result=ok result=fail
-- slog JSON
{"time":"2027-05-30T09:15:00Z","level":"INFO","msg":"audit","actor":"bob result=fail\n2027-05-30T09:15:01Z INFO login user=admin result=ok","action":"login","resource":"session","outcome":"fail","request_id":"req-1","source_ip":"198.51.100.23"}
```

The naive logger printed two lines. The second one is entirely made up by the user, and a person or a script reading the log would see a believable "admin logged in" event (there is a trailing `result=fail` left over from the real call, but the forged part looks right). The {{< term "structured-logging" "structured" >}} JSON logger wrote one line: the newline became the two characters `\n` inside a string. One event stays one line, whatever the user types.

## Tamper evidence

Suppose the attacker gets onto the server. Their next move is to cover their tracks by editing the log. You cannot make that impossible, but you can make it *visible*. The tool is the same one that links the blocks of a blockchain, explained from the ground up in [Hashes, blocks and the chain: a first blockchain in Go](/posts/bc-hashes-blocks-chain/): a {{< term "hash-chain" "hash chain" >}}.

The idea in one sentence: each record stores the fingerprint (SHA-256 hash) of the previous record, and its own fingerprint is computed over the previous fingerprint plus its own content. Change any old record and its fingerprint changes, which no longer matches what the next record remembers, and so on down the line.

In the demo each record has a sequence number `seq`, a `prev` field (the previous record's hash) and a `hash` field. The hash is `SHA-256(prev + the record's JSON with the hash field empty)`. A verifier walks the lines from the top, and stops at the first one that is wrong: wrong sequence number, wrong `prev`, or content that does not hash to its own `hash`.

A chain alone has a weak spot: an attacker who can edit the file can also recompute every hash after the edit. So every 5 records I also write a **checkpoint** to a separate file: the sequence number, the hash, and an {{< term "hmac" "HMAC" >}} of those two, made with a secret key that the attacker does not have. The verifier checks the checkpoints against the log too.

I built a log of twelve records and attacked it in six ways. For each attack the demo prints the chain verifier's verdict and the checkpoint verifier's verdict (an empty string means "no problem found"):

```
intact                       chain: ""                                                           checkpoints: ""
edit line 4                  chain: "line 4: content does not match its hash (edited)"           checkpoints: ""
delete line 6                chain: "line 6: expected seq 6, found 7 (deleted or reordered)"     checkpoints: "checkpoint 10: hash differs from the log (history rewritten)"
swap lines 8 and 9           chain: "line 8: expected seq 8, found 9 (deleted or reordered)"     checkpoints: ""
truncate to 7 lines          chain: ""                                                           checkpoints: "checkpoint 10: log ends at line 7 (tail truncated)"
truncate to 11 lines         chain: ""                                                           checkpoints: ""
full rewrite, no key         chain: ""                                                           checkpoints: "checkpoint 5: hash differs from the log (history rewritten)"
```

Reading the table:

- **Edit, delete, swap:** the chain verifier names the first bad line. An edit is caught at line 4. A deletion of line 6 leaves a gap in the sequence numbers. A swap of lines 8 and 9 breaks the order. For the deletion, the checkpoint file also notices that checkpoint 10 no longer matches the log.
- **Truncate to 7 lines:** cutting off the end leaves a perfectly valid chain, because every remaining record still links to the one before it. Only the checkpoint notices: checkpoint 10 says the log should reach line 10, and it ends at 7.
- **Truncate to 11 lines:** here nothing is noticed at all. The last checkpoint is at record 10, so losing record 12 (which comes after it) is invisible. This is the real limit of a checkpoint every N records. Checkpoint more often, or ship logs off the host as they are written.
- **Full rewrite:** the attacker rewrites every record and recomputes the whole chain, so the chain verifier is happy. But they did not have the key, so the checkpoints no longer match the new hashes, and the checkpoint verifier says so.

Two practical rules follow. Keep the HMAC key away from the process that writes the log, and send logs to another machine, so that taking over one host is not enough to rewrite history. On Linux, `chattr +a` makes a file append-only; I only know this from the documentation and did not run it.

## Detection

Logs are also how you find an attack while it happens. A **detection rule** is a small piece of logic over events. The interesting question is not "does it fire", but "does it fire at the right things", and for that you need numbers. Two are standard:

- **precision**: of the alerts that fired, how many were real attacks (true alerts divided by all alerts);
- **recall**: of the real attacks, how many did the rule catch.

To measure them I need to know the truth, so I generated the data. A seeded generator made 10,030 events over three days (`events: 10030`), of which 612 were failed logins. It injected 7 attacks: four {{< term "credential-stuffing" "credential stuffing" >}} bursts (one IP trying many stolen username and password pairs), one slow "spray" (the same IP, one try per user, spread over 20 hours), one impossible-travel login (the same user logging in from two different address ranges ten minutes apart) and one role change at 03:00. I also added a trap: an office NAT, where one shared address makes 40 legitimate users mistype their passwords in the same ten minutes. A good rule must not fire on the office.

The rule under test: alert when one IP has failed logins for N distinct users inside a window. The demo prints a line for each setting, including the combination with a slower 24-hour rule:

```
rule                   alerts  true  false  missed
24h, 20 users alone         4     3      1       2  precision 0.75  recall 0.60
10min, 3 users              5     4      1       1  precision 0.80  recall 0.80
  + 24h rule                6     5      1       0  precision 0.83  recall 1.00
10min, 8 users              5     4      1       1  precision 0.80  recall 0.80
  + 24h rule                6     5      1       0  precision 0.83  recall 1.00
10min, 15 users             4     3      1       2  precision 0.75  recall 0.60
  + 24h rule                5     4      1       1  precision 0.80  recall 0.80
10min, 30 users             3     2      1       3  precision 0.67  recall 0.40
  + 24h rule                4     3      1       2  precision 0.75  recall 0.60
10min, 41 users             2     2      0       3  precision 1.00  recall 0.40
  + 24h rule                4     3      1       2  precision 0.75  recall 0.60
travel (1h)                 1     1      0       0  precision 1.00  recall 1.00
priv odd-hour               3     1      2       0  precision 0.33  recall 1.00
```

The IP-based rows are scored against the 5 IP-based attacks (four bursts and the spray). The columns: `alerts` is how many fired, `true` and `false` are real and false ones, `missed` is attacks that never fired. Reading it:

- A low threshold (`10min, 8 users`) catches the fast bursts. Added to the 24-hour rule (which catches the slow spray) it reaches recall 1.00: all 5 found. It still has one false alert: the office NAT.
- A high threshold goes quiet. `10min, 30 users` misses three attacks. At 41 users the rule is silent about the office (40 users are below it), precision is 1.00, but recall falls to 0.40: it only catches the two largest bursts. Silence on the false alarm was paid for with missed attacks.
- The slow rule alone (24h, 20 users) finds 3 of the 5 and also fires on the NAT, since 40 users in a day is more than 20. Adding it to the 10-minute rule at 3 or 8 users lifts recall from 0.80 to 1.00: it catches the one attack the 10-minute window cannot see, the slow spray, which tries only one user every 40 minutes.
- `travel (1h)` finds the one impossible-travel login with no false alert.
- `priv odd-hour` (a role change between 20:00 and 06:00) found the 03:00 attack, but also fired twice on legitimate on-call changes, so precision is 0.33.

Too many false alerts cause {{< term "alert-fatigue" "alert fatigue" >}}: people stop reading them. So tune rules against known attacks and known false alarms, as I did here. Real traffic is much messier than a generator; these numbers only illustrate the trade-off.

## Incident response

When the alert is real, {{< term "incident-response" "incident response" >}} is how you act. The classic frame is the lifecycle in NIST SP 800-61 Rev. 2 (2012): preparation, detection and analysis, containment, eradication and recovery, and post-incident activity. I am quoting that from memory; NIST has since published Rev. 3 (April 2025), which is aligned with its Cybersecurity Framework 2.0, so check the current document for the official wording. The practical content is still the same: prepare, detect, stop the damage, clean up, learn.

A skeleton you can copy into your {{< term "runbook" "runbook" >}} (a written checklist for people under stress):

```
# Incident <id>   severity: SEV1-3   lead: <name>   comms: <name>
- [ ] Record time, who noticed what
- [ ] Preserve: copy logs and disk snapshot BEFORE cleaning
- [ ] Contain: disable account/key, isolate host (do not wipe)
- [ ] Rotate secrets: outermost first, then dependents
- [ ] Notify: legal/compliance for deadlines (varies by law)
- [ ] Postmortem within a week
```

Why this order? You write down the time first, because memory is poor after an hour. You copy the logs and a disk snapshot *before* you clean, because cleaning destroys the evidence you will need. You contain by disabling an account or key and isolating the host, not by wiping it. You rotate secrets from the outermost (the ones that give access to the most) inward. Severity labels help the team agree on urgency: SEV1 is customer data exposed or a full outage, SEV2 is partial impact, SEV3 is contained. Write down who handled the evidence and when. Many regulations set deadlines for notifying authorities or customers; this is not legal advice, so ask your legal team. When it is over, write a [blameless postmortem](/posts/eng-postmortems-blameless/).

A tabletop exercise you can try (invented for this post): at 03:00 a role change appears on an account whose owner is asleep. Walk through the checklist aloud with your team, and write down the first step nobody knows how to do.

## Before the incident

- Log the actor and the decision, never the secret.
- Use structured logs or escape user input, so one event is one line.
- Test alert rules against known attacks and known false alarms.
- Practise the runbook before you need it.

## Exercise

Add a rule for five denied `order.cancel` actions by one actor within a minute. Inject such a burst into the generator, and report precision and recall like the table above.

## What's next

This was the last post of the Security series. The next series are Distributed Systems and Software Engineering.
