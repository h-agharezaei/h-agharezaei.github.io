+++
date = '2027-04-30T10:00:00+03:30'
draft = false
title = 'Managing secrets and keys'
description = 'Managing secrets in Go: leaks in git history, logs, env and ps, a scanner, fail-closed loading, AES-GCM nonce reuse and envelope encryption.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "secrets", "encryption", "key-management", "git", "go"]
cover = { image = "/images/covers/sec-secrets-management.png", alt = "Managing secrets and keys", hiddenInSingle = true }
+++

Commit a `config.env` with a password in it. Notice, and delete the file in the next commit. The working tree is clean now. Then run `git show HEAD~1:config.env`, and the password prints on your screen. Git never forgets: the working tree is clean, the history is not.

That is only one of the ways a secret escapes. It also leaks into logs, error messages, process listings and the environment of child processes. [TLS and x509 certificates in practice](/posts/sec-tls-x509-certificates/) ended with "keep keys out of repositories"; this post is about how secrets escape anyway, what to do after a leak, and how to load and use secrets so that they escape less. By a **secret** I mean anything that proves identity or unlocks data: a password, an API key, a signing key, a private key, a database connection string. It builds on [Config, structured logging and errors in Go](/posts/go-config-logging-errors/); password storage has its own post, [Storing passwords safely: argon2 and bcrypt](/posts/sec-password-hashing/), and signing keys come up in [Sessions or JWT?](/posts/sec-sessions-vs-jwt/).

> Defensive only. Every secret below is an obvious FAKE (`AKIAFAKEFAKEFAKE1234`, `tok_FAKE_0123456789abcdef` and similar), made up for the demo. Everything ran locally with Go 1.27.3 and git on macOS arm64 (the demo's `go.mod` says 1.26), in throwaway repos in a temporary directory that I deleted afterwards; the scanner never touched a real repository. I did not run gitleaks, trufflehog, `git filter-repo`, Vault or a cloud KMS; they are only described. Paths are shortened to `<tmp>`, and I masked the secret values in the output where noted.

## Git remembers

I built a throwaway repo, committed a fake `config.env` with two fake secrets, then deleted the file in the next commit. This is the history search, then the content of the old commit (I masked the values with `sed`, so only the first characters show):

```
$ git log --all --oneline --name-only -S AKIAFAKEFAKEFAKE1234
cf59da8 remove secrets from the repo
config.env
9ef7259 add config
config.env
$ git show HEAD~1:config.env      (masked by me)
AWS_ACCESS_KEY_ID=AKIA****
DB_PASSWORD=hunt****
```

`-S` asks git for the commits that added or removed that exact string. Both commits touched `config.env`: one added it, the next removed it. And `git show HEAD~1:config.env` prints the file as it was in the older commit. The commit ids differ on every run.

So what do you do after a real leak? In this order:

1. **Rotate first.** Assume the secret has already been copied, by a clone, a CI cache or a scraper. Issue a new one and revoke the old one.
2. Then rewrite history if you want it gone from the repository. Git's own documentation for `git filter-branch` recommends `git filter-repo` for this. It is not installed here, so I did not run it.
3. Then prevent the next one, with the habits in the rest of this post.

## Stopping the next commit

You may think `.gitignore` solves this. It does not help for a file that is already tracked. In the demo I added `*.env` to `.gitignore`: a new `other.env` was ignored, but `new.env`, which had been added before the rule, stayed in `git ls-files`.

```
.gitignore:1:*.env	other.env
new.env
```

The first line is `git check-ignore -v` explaining why `other.env` is ignored. The second is `git ls-files` still listing `new.env`.

A better guard is a {{< term "git-hook" "pre-commit hook" >}}: a script that git runs before every commit. Mine is a shell script that greps the staged diff for patterns that look like secrets. I staged a file with a fake token and tried to commit:

```
pre-commit: staged changes look like they contain a secret; commit blocked
exit status: 1
```

The commit did not happen. But `git commit --no-verify` skips the hook, so it is a guard, not a wall. It catches the honest mistake, which is the most common kind.

## A tiny scanner

The hook only looks at what you are about to commit. {{< term "secret-scanning" "Secret scanning" >}} is the same idea applied to a whole repository and its history. Mine is about 50 lines of Go with two ideas. First, two regular expressions: an AWS-style key id (`AKIA` followed by 16 characters) and an assignment such as `password = something`. Second, {{< term "shannon-entropy" "Shannon entropy" >}}: a measure of how unpredictable the characters of a string are. `aaaaaaaa` has an entropy of 0 bits per character; a random token has a lot. The scanner flags long tokens with more than 4.2 bits per character (my own threshold). I fed it the full history of the leaky repo (`git log -p --all`), and the matches are masked:

```
line 13  aws-access-key-id  AKIA****
line 14  assigned-secret    PASS****
line 28  aws-access-key-id  AKIA****
line 29  assigned-secret    PASS****
scanned 36 lines, 4 findings
```

Each secret is found twice, because `git log -p` shows the line once when the file was added and once when it was removed. The line numbers are positions in that text stream, not in a file.

Then a clean repo. It has a `go.sum` line, a README sentence about passwords, and a 40-character commit hash in the README:

```
line 22  high-entropy       Zk3k**** (5.24 bits/char)
scanned 22 lines, 1 findings
```

The finding is a false positive: it is a module checksum from the `go.sum` line, which looks random because it is a hash. The commit hash scored below the threshold, because hex digits only have 16 possible characters and so lower entropy per character. This is the trade-off of every scanner: lower the threshold and you drown in noise, raise it and you miss real keys.

## Logs and errors

Secrets leak most often not from the repository but from your own program. A JSON logger prints whatever you give it. The demo logs a login with the fake token four ways, and then prints the same token with `fmt`:

```
{"level":"INFO","msg":"login","user":"alice","token":"tok_FAKE_0123456789abcdef"}
{"level":"INFO","msg":"login","user":"alice","token":"[REDACTED]"}
{"level":"INFO","msg":"login","user":"alice","tok":"tok_FAKE_0123456789abcdef"}
{"level":"INFO","msg":"login","user":"alice","tok":"[REDACTED]"}
fmt %v plain string: tok_FAKE_0123456789abcdef
fmt %v Secret type:  [REDACTED]
```

Read it line by line. Line 1 is a plain logger: it prints the token. Line 2 uses a `ReplaceAttr` hook that hides any attribute named `token`, and it works. Line 3 shows its weakness: the same token under another key name (`tok`) goes straight through. Line 4 is the better design: a type `Secret` with a `LogValue` method, so the value hides itself wherever it is logged. The last two lines show the same for `fmt`: a plain string prints the token, while `Secret`, which also has a `String` method, prints `[REDACTED]`. This protects `slog` and `fmt`. A different encoder does not know about `LogValue`: when I put a `Secret` into `json.Marshal` in a scratch program, the token was printed in the clear. So redact by type, but also keep secrets out of structures you serialise.

Error messages leak the same way. The demo builds an error with the connection string in it, then the safer one:

```
error before: connect failed: dsn=postgres://app:FAKE-db-pass-123@127.0.0.1:5432/orders
error after:  connect failed: host=127.0.0.1:5432 user=app
```

An error travels up through several layers and ends up in logs and in front of users, so it must never carry the password.

## Environment variables and arguments

An {{< term "environment-variable" "environment variable" >}} is a string a process inherits from its parent. Convenient, but it means every child process gets all of it by default. Command-line arguments are even more public: they appear in the process list. The demo runs a child program four ways:

```
inherited: child sees FAKE_DEMO_SECRET = FAKE-env-value-123
explicit:  child sees FAKE_DEMO_SECRET = 
ps args:    ./demo wait --api-key=FAKE-cli-key-456
ps eww:     FAKE_DEMO_SECRET=FAKE-env-value-123
```

By default the child sees the parent's secret (`inherited`). With `cmd.Env` set explicitly to a minimal list, it does not (`explicit`, an empty value). The last two lines look at a long-running child of my own with `ps`: the secret `--api-key=...` argument is visible to anyone who can run `ps`, and `ps eww` printed the environment of the process (the demo shows only the fake variable from that output). I tested this only on macOS. On Linux, `/proc/<pid>/environ` is the analogue, which I did not run. So: set `cmd.Env` explicitly for children, and do not pass secrets as arguments.

## Loading secrets

The mistake I see most is a default value:

```
bad fallback:  key="dev-secret"
fail closed:   FAKE_SIGNING_KEY is not set
```

The first function falls back to `"dev-secret"` when the variable is missing, so a forgotten setting in production silently becomes a key that everybody who has read the code knows. The second one returns an error, and the program refuses to start. Always fail at startup instead of guessing.

A common alternative to environment variables is the `NAME_FILE` convention: the variable holds the path of a file, and the program reads the secret from the file. The loader also checks the file mode and refuses a file readable by other users:

```
mode 0644:     db_password has mode 0644, want 0600 or stricter
mode 0600:     value="FAKE-file-secret" err=<nil>
```

`0644` means the owner can read and write, everybody else can read. `0600` means only the owner. Secret managers (Vault, cloud KMS) add audit trails and rotation on top of this; I did not run one.

## Encryption with keys

Sometimes the secret is the key that protects other data. {{< term "aes-gcm" "AES-256-GCM" >}} is a standard way to encrypt, and it needs a unique {{< term "nonce" "nonce" >}} (a number used once) for every message under the same key. To show what happens when you break that rule, I encrypted two harmless fake messages with the same zero nonce, and compared:

```
same nonce: c1^c2 == p1^p2 ? true
knowing p1, p2 = "pay mallory 999 US"
```

The first line says that XOR of the two ciphertexts equals XOR of the two plaintexts: the key stream cancelled out. The second line shows the consequence: if you know one plaintext (here, a message starting `pay alice 0010 USD`), you can compute the other. Use `crypto/rand` for a fresh nonce every time; the demo's `seal` does, and a test checks that sealing the same input twice gives different output.

The second idea is {{< term "envelope-encryption" "envelope encryption" >}}. Each record is encrypted with its own random data key (DEK). That small data key is then encrypted ("wrapped") with a master key (KEK), and the id of the master key is stored next to the record. Why? Because of {{< term "key-rotation" "rotation" >}}: when you replace the master key, you only rewrap the small wrapped key, not all the data:

```
stored key id: kek-1  wrapped DEK bytes: 60  data bytes: 50
after rewrap:  kek-2  data unchanged: true
old record, kek-1 retired: unknown key id kek-1
rewrapped record: "card-last4=0000 (fake)" err=<nil>
wrong record id (AAD): cipher: message authentication failed
```

The record stores `kek-1` and a wrapped key of 60 bytes (12 nonce, 32 key, 16 tag). After the rewrap it says `kek-2` and the data bytes are identical. Then I retired `kek-1`: the old record cannot be opened any more (unknown key id), while the rewrapped one still can. That is why the key id must be stored with every ciphertext. The last line shows the record id used as additional authenticated data: decrypting the record under a different id (`order-8` instead of `order-7`) fails, which stops someone from swapping ciphertext between rows.

When you compare secrets such as tokens, use `subtle.ConstantTimeCompare` ({{< term "constant-time-comparison" "constant-time comparison" >}}), so the time taken does not reveal how many leading bytes were correct. The demo prints `constant-time equal: true` for that call. Wiping a secret from memory is another matter: Go gives no reliable way to do it (strings are immutable and the runtime can keep copies), so I make no promise there.

## Damage control

- After a leak, rotate first; deleting a commit is not enough.
- Never give a secret a default value; fail at startup.
- Redact by type, not by key name, and keep secrets out of errors.
- Prefer files with mode 0600 over environment variables, and both over arguments.
- Store a key id with every ciphertext, so that rotation is possible.

## Exercise

Add a `--history` flag to the scanner that prints the commit of each finding, and an allowlist so the `go.sum` false positive stops showing up.

## What's next

"The supply chain and vulnerable dependencies" turns from your own credentials to the code you did not write.
