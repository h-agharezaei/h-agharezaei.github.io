+++
date = '2027-05-30T10:00:00+03:30'
draft = false
title = 'Logs and journalctl'
description = 'Logs and journalctl from the docs: journal fields, priorities, filters, retention and rate limits, logrotate, plus Go slog, parser and linter demos.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "logging", "journalctl", "journald", "logrotate", "slog", "go", "macos"]
cover = { image = "/images/covers/linux-logs-journalctl.png", alt = "Logs and journalctl", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. This is the twelfth post of the Linux series, after [Users, sudo and capabilities](/posts/linux-users-sudo-capabilities/). The facts below come from the journalctl, journald.conf, systemd.journal-fields, syslog(3) and logrotate man pages; Linux-looking text is labelled "illustrative, not captured". Related: [systemd: units and timers](/posts/linux-systemd-units-timers/) and [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).

## Text logs and the journal

Classic logs are text files under `/var/log`. {{< term "journald" "journald" >}} instead stores structured, indexed records, so a line is a set of fields. According to systemd.journal-fields, `MESSAGE` is the human-readable text, `PRIORITY` a value from 0 to 7, `SYSLOG_IDENTIFIER` the program tag, `_PID` the process and `_SYSTEMD_UNIT` the unit. Fields starting with an underscore are added by journald itself, not by the program. Anything a {{< term "systemd" "systemd" >}} service writes to stdout or stderr is captured, so a service can simply log to stdout. That is my opinion, not a rule.

Priorities follow {{< term "syslog-severity" "syslog(3)" >}}: emerg 0, alert 1, crit 2, err 3, warning 4, notice 5, info 6, debug 7. Syslog also has facilities; journalctl has `--facility`.

## journalctl

From the man page:

- `-u UNIT` limits output to one unit; `-b` to the current boot.
- `-p err` shows that level **and more important ones**; `-p warning..err` is a range.
- `--since` and `--until` take timestamps; `-f` follows new entries.
- `-o json` prints one JSON object per entry, `-o json-pretty` the same over several lines, `-o cat` only the message.
- `--vacuum-size=` and `--vacuum-time=` remove the oldest archived journal files; `--disk-usage` shows the size.

Illustrative, not captured:

```
$ journalctl -u demo.service -p err -b -o cat
db timeout
```

## Retention and rate limits

`Storage=` in journald.conf is `volatile`, `persistent`, `auto` or `none`. `auto` behaves as persistent only if `/var/log/journal` exists, otherwise logs live in memory and vanish at reboot. Rate limiting is per service: more than `RateLimitBurst` messages within `RateLimitIntervalSec` are dropped, and a message reports how many. The documented default is 10000 messages in 30s; 0 disables it. So a crash loop can lose lines.

## Logging from Go, for real

I ran `log/slog` with a JSON handler. `ReplaceAttr` redacts a field and drops the time (only to keep output stable):

```
$ lx12 slog
{"level":"INFO","msg":"request","method":"GET","status":200,"token":"[REDACTED]"}
{"level":"ERROR","msg":"db failed","err":"timeout","attempt":3}
```

The debug call is filtered out by the info level. This is the {{< term "structured-logging" "structured logging" >}} that lets a collector filter by field. Handler redaction is a safety net, not a plan.

## Rotation, written and linted

{{< term "log-rotation" "Rotation" >}} stops a file growing forever. I wrote a tiny size-based rotator (rotate when the next write would pass 200 bytes, keep 2 old files) and wrote 12 events:

```
app.log      76 bytes
app.log.1   186 bytes
app.log.2   185 bytes
```

The earliest events are gone, which is what `keep` means. Real `logrotate` uses a config; per the man page, `rotate N` keeps N old files (default 0, so old logs are removed), `size`, `compress` and `delaycompress` exist, and {{< term "copytruncate" "copytruncate" >}} copies then truncates in place, so a few lines can be lost, and `create` then has no effect. My linter checks directive names against a subset of the man page, `rotate`, the compress pairing and that conflict. It is **not logrotate**. Real output on a good config and on a bad one:

```
$ lx12 lint testdata/good.conf
OK: no findings (this is not logrotate itself)
$ lx12 lint testdata/bad.conf
WARN: line 3: unknown directive "compres"
WARN: no 'rotate N': the man page says the default is 0, so old logs are removed, not kept
WARN: delaycompress without compress has no effect
WARN: copytruncate and create together: create has no effect (man page)
```

## Reading journal JSON

I wrote a parser for the `-o json` shape (one object per line, values as strings) and a filter mimicking `-u x -p err`. Its tests use **invented** sample lines in the documented format, and `go test -race` passed. It also passed `GOOS=linux GOARCH=arm64 go vet` and a build, but was never run on Linux.

## What the Mac can show

The nearest real thing here is the macOS unified log. I wrote a line with `logger` and a random marker, then queried only that marker with `log show --style compact` (time and process IDs redacted):

```
<time> Df logger[<pid>:<tid>] marker-RAND hello
```

| | journald | macOS unified log |
|---|---|---|
| Read | `journalctl` | `log show`, `log stream` |
| Filter | field matches, `-p`, `-u` | `--predicate`, subsystem |
| Write | stdout, `logger`, syslog | `os_log`, `logger` |

## A few things to watch

- Check `Storage=`: `auto` without `/var/log/journal` loses logs at reboot.
- Log time in UTC.
- Audit logs are separate from app logs: different readers, different retention. See the security post on logging and audit.
- A full disk is a log problem too: writes fail with ENOSPC, so cap size with vacuum or rotation.
- Redact before logging, see [Managing secrets and keys](/posts/sec-secrets-management/).

## Exercise

On a throwaway VM, run a service that logs one error, find it with `journalctl -u ... -p err -o json-pretty`, then lower `RateLimitBurst` and see what happens.

## What's next

The next post is “strace and perf for troubleshooting”.
