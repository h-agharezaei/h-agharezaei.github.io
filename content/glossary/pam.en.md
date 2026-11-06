+++
title = "PAM"
summary = "Pluggable Authentication Modules: the Linux layer that programs like sshd call to check who a user is."
category = "Security"
related = ["password-hashing"]
posts = ["openssh-musl-password-bypass-cve-2026-123158"]
+++

PAM lets a program such as `sshd` hand the question "is this password valid?" to a configurable set of modules instead of checking it itself. A system can add rules, lockouts or other factors without changing `sshd`. When `sshd` is built or run without PAM, it falls back to its own check with `crypt()`, which is where CVE-2026-123158 lives.
