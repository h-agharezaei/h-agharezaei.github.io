+++
date = '2027-05-30T10:00:00+03:30'
draft = false
title = 'Logs and journalctl'
description = 'Logs and journalctl from the docs: journal fields, priorities, filters, retention and rate limits, logrotate, plus Go slog, parser and linter demos.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "logging", "journalctl", "journald", "logrotate", "slog", "go", "macos"]
cover = { image = "/images/covers/linux-logs-journalctl.png", alt = "Logs and journalctl", hiddenInSingle = true }
+++

Your service crashed at 3am, and by the time you look the server has rebooted. You run `journalctl` and find nothing from before the reboot. The lines you needed were never written to disk. This happens more often than people expect, and it is much better to learn the reason before you need those lines.

This post is about where a service's messages go on a modern Linux machine, how to find the one line you want among millions, and how to stop logs from filling the disk or vanishing. The setting behind the story above is `Storage=auto`: with it, and without a directory called `/var/log/journal`, the journal lives in memory only. We will get there in a moment.

The previous post, [Users, sudo and capabilities](/posts/linux-users-sudo-capabilities/), was about running a service with the right privileges. Here we ask what that service tells us. It builds on [systemd: units and timers](/posts/linux-systemd-units-timers/), and it pairs with [Config, structured logging and errors in Go](/posts/go-config-logging-errors/), which covers the writing side in Go.

As in the last post, I wrote this on a Mac. There is no journald here, so I cannot show you real `journalctl` output. The facts come from the man pages for journalctl, journald.conf, systemd.journal-fields and logrotate (I checked each claim against them), and any Linux-looking text is labelled "illustrative, not captured". What I did run is Go code and the macOS logging tools, and those are marked.

## Text files and the journal

The classic way to log is simple: a program appends lines to a text file under `/var/log`. To find something you use `grep`. It works, but every program invents its own format, and a line is just a string.

{{< term "journald" "journald" >}} is the logging service of systemd. Instead of text lines it stores **records**, and each record is a set of named fields, indexed so that queries are fast. According to systemd.journal-fields, the fields you meet first are:

- `MESSAGE`, the human-readable text;
- `PRIORITY`, a number from 0 to 7;
- `SYSLOG_IDENTIFIER`, a short tag for the program;
- `_PID`, the id of the process that wrote it;
- `_SYSTEMD_UNIT`, the name of the systemd unit it belongs to.

The fields that start with an underscore are "trusted": the journal adds them itself and the program cannot forge them. The others are chosen by whoever writes the message. This matters when you filter. If you ask for `_SYSTEMD_UNIT=demo.service`, you can believe the answer.

A {{< term "systemd" "systemd" >}} service does not need any logging library to get into the journal. By default what it prints to stdout or stderr is collected by journald, so a service can simply print its log lines. (I believe this default is documented in the systemd.exec page, but I did not fetch it, so treat it as unverified.) Whether to do that is a matter of taste, and I prefer it: the program stays simple and the platform decides where the lines go.

The priority numbers follow {{< term "syslog-severity" "syslog(3)" >}}: emerg 0, alert 1, crit 2, err 3, warning 4, notice 5, info 6, debug 7. A smaller number is more serious. Syslog also has "facilities", which say what kind of program sent the message; journalctl has a `--facility` option for that.

## Finding the line you need

`journalctl` reads the journal. From its man page, the options you will use most:

- `-u UNIT` shows only messages of one unit, and `-b` only the current boot.
- `-p err` shows that level **and the more serious ones** (err, crit, alert, emerg). A range such as `-p warning..err` works too.
- `--since` and `--until` limit the time, and `-f` keeps following new entries, like `tail -f`.
- `-o json` prints one JSON object per entry, `-o json-pretty` the same object spread over several lines, and `-o cat` prints only the message text.
- `--disk-usage` shows how much space the journal files use, and `--vacuum-size=` and `--vacuum-time=` delete the oldest archived files until the journal is under the size or newer than the age you give.

Putting some of them together, the question "what errors did my demo service log since this boot?" looks like this. I could not run it here, so this is **illustrative, not captured**:

```
$ journalctl -u demo.service -p err -b -o cat
db timeout
```

Each option narrows the result: the unit, the severity, the boot. `-o cat` removes the timestamp and metadata, so only the message is left.

## What gets kept, and what gets dropped

Back to the 3am crash. The `Storage=` setting in journald.conf decides where the journal lives: `volatile` keeps it only in memory (under `/run/log/journal`), `persistent` writes it to disk, `none` stores nothing, and `auto`, the one many systems use, is persistent only if the directory `/var/log/journal` exists. If the directory is missing, `auto` quietly behaves like `volatile`, and a reboot erases everything. The fix is to create the directory (or set `Storage=persistent`) before you need it.

The second way to lose lines is rate limiting. According to journald.conf it works per service: if one service sends more than `RateLimitBurst` messages in `RateLimitIntervalSec`, the rest in that interval are dropped, and journald writes one message saying how many. The documented default is 10000 messages per 30 seconds, and setting either value to 0 turns the limit off. So a service that logs in a tight loop can lose lines, which is the worst moment to lose them.

## Logging from Go

Now the writing side, which I could run. Go has a standard structured logger, `log/slog`. I used its JSON handler and one hook, `ReplaceAttr`, which can rewrite every field before it is printed. My hook does two things: it replaces the value of fields named `password` or `token` with `[REDACTED]`, and it drops the time, only so that the output is the same on every run and I can show it. This is what the program printed when I ran it again for this post:

```
$ lx12 slog
{"level":"INFO","msg":"request","method":"GET","status":200,"token":"[REDACTED]"}
{"level":"ERROR","msg":"db failed","err":"timeout","attempt":3}
```

The program also called `Debug`, and nothing was printed for it: the logger's level is `info`, so debug messages are filtered out. The `token` field was `abc123` in the code and arrives as `[REDACTED]`. Every line is a JSON object with named fields. That is {{< term "structured-logging" "structured logging" >}}: a collector can filter on `status` or `err` without parsing English sentences. Redaction in the handler is a safety net, not a plan. The better plan is not to log secrets at all.

## Rotation: keeping files from growing forever

A plain log file only grows. {{< term "log-rotation" "Log rotation" >}} fixes that: when the file is big or old enough, it is renamed (`app.log` becomes `app.log.1`, and the older ones move up), a new empty file is started, and the oldest files are deleted.

To see the idea I wrote a tiny size-based rotator in Go. It rotates when the next write would pass 200 bytes and keeps 2 old files. I wrote 12 log events through it. This is the real output:

```
$ lx12 rotate <tmp>
app.log      76 bytes
app.log.1   186 bytes
app.log.2   185 bytes
```

Three files, and none of the 12 events is lost: `app.log.2` holds events 1 to 5, `app.log.1` holds 6 to 10, and `app.log` holds 11 and 12. To see something actually deleted I ran a throwaway copy with 20 events. Then the files hold events 6 to 10, 11 to 15 and 16 to 20, and events 1 to 5 have been dropped. That is what "keep 2" means: the third file does not exist, so the oldest events fall off the end.

On a real server you rarely write this yourself. The standard tool is `logrotate`, which reads a config file. According to its man page, `rotate N` keeps N old files, and the default is 0, which means old versions are removed and not kept. `size` rotates only when the file grows bigger than that, and `compress` gzips old files; `delaycompress` postpones compression until the next rotation, which helps when a program may still write to the old file for a while. {{< term "copytruncate" "copytruncate" >}} copies the file and then truncates the original in place. The man page warns that a very small amount of logging data might be lost between the copy and the truncation, and that `create` has no effect with it.

Those rules are easy to get wrong in a config, so I wrote a small linter in Go. It checks directive names against a subset of the man page, and then four things: a missing `rotate`, `delaycompress` without `compress`, `copytruncate` together with `create`, and one extra note about compressing without `delaycompress`. It is **not logrotate** and knows nothing beyond that subset. This is its real output on a good config and on a bad one that has a typo (`compres`):

```
$ lx12 lint testdata/good.conf
OK: no findings (this is not logrotate itself)
$ lx12 lint testdata/bad.conf
WARN: line 3: unknown directive "compres"
WARN: no 'rotate N': the man page says the default is 0, so old logs are removed, not kept
WARN: delaycompress without compress has no effect
WARN: copytruncate and create together: create has no effect (man page)
```

The third warning follows from the second thing the linter sees: because of the typo, there is no real `compress` directive, so `delaycompress` has nothing to delay. One typo produced two warnings, which is a good reminder that a config is only as correct as its spelling.

## Reading the journal's JSON

When you want to process journal entries in a program, `journalctl -o json` gives one JSON object per line. I wrote a parser for that shape in Go, and a filter that does the same job as `-u x -p err`: keep entries with a priority number at or below the limit, and optionally of one unit. According to the journal JSON format documentation, field values are mostly strings, but a field that repeats becomes an array, binary data becomes an array of numbers, and a value that was too large can be `null`. My parser reads the fields it needs as strings and treats anything else as missing, which is fine for a demo.

Its tests use **invented sample lines** in the documented format, and `go test -race` passes. I also cross-compiled it with `GOOS=linux GOARCH=arm64 go vet ./...`, which passes. It was never run against a real journal.

## What the Mac can show

The nearest real thing on this machine is the macOS unified log. I wrote one line with `logger` that contains a random marker, and queried only that marker with `log show`. The time, process id and thread id are replaced:

```
$ log show --last 1m --style compact --predicate 'eventMessage CONTAINS "<marker>"'
<time> Df logger[<pid>:<tid>] marker-RAND hello
```

(`log show` also printed one line about itself, because the predicate text contains the marker. I left that out.) Same job, different tools:

| | journald | macOS unified log |
|---|---|---|
| Read | `journalctl` | `log show`, `log stream` |
| Filter | field matches, `-p`, `-u` | `--predicate`, subsystem |
| Write | stdout, `logger`, syslog | `os_log`, `logger` |

## Logging traps

- **Checking `Storage=` too late.** With `auto` and no `/var/log/journal`, logs vanish at reboot. Look at it on a new server on day one.
- **Local time in logs.** My advice, not a documented rule: write log timestamps in UTC, so that logs from different machines and seasons line up.
- **Mixing audit and application logs.** They have different readers and different retention. The post on [Logging, auditing and incident response](/posts/sec-logging-audit-incident-response/) covers audit logs.
- **A full disk.** Logs are a way to fill a disk too. Writes then fail, and the service can fail with them. Cap the size with rotation or with vacuum.
- **Secrets in lines.** Redact before logging, and see [Managing secrets and keys](/posts/sec-secrets-management/).

## Exercise

On a throwaway Linux VM, run a service that logs one error. Find it with `journalctl -u <your-unit> -p err -o json-pretty`. Then lower `RateLimitBurst` and see what happens when the service logs a lot.

## What's next

Next is "strace and perf for troubleshooting". Logs only tell you what the program chose to say. When they do not explain why it hangs or is slow, you look at what it actually does.
