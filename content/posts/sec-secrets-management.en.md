+++
date = '2027-04-30T10:00:00+03:30'
draft = false
title = 'Managing secrets and keys'
description = 'Managing secrets in Go: leaks in git history, logs, env and ps, a scanner, fail-closed loading, AES-GCM nonce reuse and envelope encryption.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "secrets", "encryption", "key-management", "git", "go"]
cover = { image = "/images/covers/sec-secrets-management.png", alt = "Managing secrets and keys", hiddenInSingle = true }
+++

The previous post, [TLS and x509 certificates in practice](/posts/sec-tls-x509-certificates/), ended with "keep keys out of repositories". This post is about how secrets escape anyway and how to load and use them. It builds on [Config, structured logging and errors in Go](/posts/go-config-logging-errors/); password storage has its own post, [Storing passwords safely](/posts/sec-password-hashing/), and signing keys come up in [Sessions or JWT?](/posts/sec-sessions-vs-jwt/).

> Defensive only. Every secret below is an obvious FAKE, and everything ran locally with Go 1.26 and git. I did not run gitleaks, trufflehog, `git filter-repo`, Vault or a cloud KMS; they are only described. Paths are shortened to `<tmp>`.

## Git remembers

I built a throwaway repo, committed a fake `config.env`, then deleted it in the next commit:

```
$ git log --all --oneline --name-only -S AKIAFAKEFAKEFAKE1234
69a28b5 remove secrets from the repo
config.env
fefecea add config
config.env
$ git show HEAD~1:config.env      (masked by me)
AWS_ACCESS_KEY_ID=AKIA****
DB_PASSWORD=hunt****
```

The working tree is clean, the history is not. After a real leak: **rotate first**, because the secret is already copied; then rewrite history (`git filter-repo` is the usual tool, not installed here, so not run); then prevent.

`.gitignore` does nothing for an already tracked file (`new.env` stayed in `git ls-files` despite `*.env`). A {{< term "git-hook" "pre-commit hook" >}}, my shell script grepping the staged diff, blocks the rest:

```
pre-commit: staged changes look like they contain a secret; commit blocked
exit status: 1
```

`--no-verify` skips it, so it is a guard, not a wall.

## A tiny scanner

{{< term "secret-scanning" "Secret scanning" >}} is the same idea over history. Mine is about 50 lines: two regexes plus {{< term "shannon-entropy" "Shannon entropy" >}} above 4.2 bits per character on long tokens. On the leaky repo (matches masked):

```
line 13  aws-access-key-id  AKIA****
line 14  assigned-secret    PASS****
line 28  aws-access-key-id  AKIA****
line 29  assigned-secret    PASS****
scanned 36 lines, 4 findings
```

On a clean repo with a `go.sum` line, a commit hash and a README sentence about passwords:

```
line 22  high-entropy       Zk3k**** (5.24 bits/char)
scanned 22 lines, 1 findings
```

The module checksum is a false positive; the 40-hex commit hash scored below the threshold. Lower the threshold and you drown in noise, raise it and you miss real keys. 

## Logs, errors, environment, arguments

A JSON logger prints whatever you give it. Four variants:

```
{"token":"tok_FAKE_0123456789abcdef"}                  plain
{"token":"[REDACTED]"}                                 ReplaceAttr by key "token"
{"tok":"tok_FAKE_0123456789abcdef"}                    ReplaceAttr, key named "tok"
{"tok":"[REDACTED]"}                                   type Secret with LogValue
```

Redacting by key name misses any other name. A `Secret` type with a `LogValue` method (and `String`) redacts wherever it travels, including `fmt %v`. Errors leak the same way: `connect failed: dsn=postgres://app:FAKE-db-pass-123@...` became `connect failed: host=127.0.0.1:5432 user=app`.

An {{< term "environment-variable" "environment variable" >}} is inherited by children, and arguments are public:

```
inherited: child sees FAKE_DEMO_SECRET = FAKE-env-value-123
explicit:  child sees FAKE_DEMO_SECRET =
ps args:    <tmp>/demo wait --api-key=FAKE-cli-key-456
ps eww:     FAKE_DEMO_SECRET=FAKE-env-value-123
```

Set `cmd.Env` explicitly for children. `ps eww` showed the environment of my own child process on macOS; I did not test Linux, where `/proc/<pid>/environ` is the analogue.

## Loading secrets

The bug I see most is a default:

```
bad fallback:  key="dev-secret"
fail closed:   FAKE_SIGNING_KEY is not set
```

A missing variable silently became a known key. Fail at startup instead. The `NAME_FILE` convention reads the value from a file and I check its mode:

```
mode 0644:     db_password has mode 0644, want 0600 or stricter
mode 0600:     value="FAKE-file-secret" err=<nil>
```

Secret managers (Vault, cloud KMS) add audit and rotation; I did not run one.

## Encryption with keys

{{< term "aes-gcm" "AES-256-GCM" >}} needs a unique {{< term "nonce" "nonce" >}}. I reused a zero nonce on two harmless fake messages:

```
same nonce: c1^c2 == p1^p2 ? true
knowing p1, p2 = "pay mallory 999 US"
```

Knowing one plaintext reveals the other. Use `crypto/rand` every time.

For {{< term "envelope-encryption" "envelope encryption" >}} each record gets a random data key, wrapped by a master key, with the key id stored beside it. {{< term "key-rotation" "Rotation" >}} rewraps only the small wrapped key:

```
stored key id: kek-1  wrapped DEK bytes: 60  data bytes: 50
after rewrap:  kek-2  data unchanged: true
old record, kek-1 retired: unknown key id kek-1
rewrapped record: "card-last4=0000 (fake)" err=<nil>
wrong record id (AAD): cipher: message authentication failed
```

The record id as additional data stops ciphertext swapping between rows. Compare secrets with `subtle.ConstantTimeCompare` ({{< term "constant-time-comparison" "constant-time comparison" >}}). Wiping memory in Go is unreliable (the garbage collector may copy values), so I do not promise it.

## A few things to watch

- After a leak rotate first; deleting a commit is not enough.
- Never default a secret; fail at startup.
- Redact by type, not by key name.
- Prefer files with 0600 over variables and arguments.
- Store a key id with every ciphertext.

## Exercise

Add a `--history` flag to the scanner that prints the commit of each finding and an allowlist for the `go.sum` false positive.

## What's next

The next post is The supply chain and vulnerable dependencies.
