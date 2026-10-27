+++
date = '2027-05-20T10:00:00+03:30'
draft = false
title = 'SSH and keys'
description = 'SSH and keys in a throwaway directory: ed25519 vs RSA, fingerprints, the 0600 rule, authorized_keys, known_hosts, ssh_config, agents, certificates.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "ssh", "openssh", "keys", "security", "sshd", "macos"]
cover = { image = "/images/covers/linux-ssh-keys.png", alt = "SSH and keys", hiddenInSingle = true }
+++

This is the tenth post of the Linux series, after [Linux networking: ip, ss and nftables](/posts/linux-networking-ip-ss-nftables/), where I warned that a wrong firewall rule over SSH locks you out. Everything here ran on a Mac with OpenSSH 10.3 (`ssh -V` says `OpenSSH_10.3p1, LibreSSL 3.3.6`), not on Linux. I worked only in a throwaway directory, `<tmp>`, with explicit paths and `-F /dev/null -o IdentityAgent=none`, and never touched my real keys or any remote host. Where Linux may differ I say "per the man page". Private keys are secrets, see [Managing secrets and keys](/posts/sec-secrets-management/).

## Key pairs

An {{< term "ssh-key-pair" "SSH key pair" >}} is a private file you keep and a public line you share. I generated three with `ssh-keygen -t ... -N '' -C demo@example` (no passphrase, throwaway):

```
$ ls -l id_*    (mode, bytes)
-rw-------  505 id_ecdsa       -rw-r--r--  174 id_ecdsa.pub
-rw-------  399 id_ed25519     -rw-r--r--   94 id_ed25519.pub
-rw-------  2602 id_rsa        -rw-r--r--  566 id_rsa.pub
$ ssh-keygen -lf id_ed25519.pub
256 SHA256:RGPI0NPYYwFmf2tRXHk7GKof9bSBEuj/v7XD9bHqaxc demo@example (ED25519)
```

The public file is one line: type, base64, comment (`ssh-ed25519 AAAAC3Nz... demo@example`). The private file starts with `-----BEGIN OPENSSH PRIVATE KEY-----`; I print only that line. ed25519 is the smallest here; RSA 3072 is about six times bigger as a public line. The fingerprint is a hash of the public key; `ssh-keygen -lvf` also draws a "randomart" picture, a visual aid for comparing keys.

## The 0600 rule

SSH refuses private keys others can read. I made one 0644 and asked for its public part:

```
$ ssh-keygen -y -f id_ed25519
WARNING: UNPROTECTED PRIVATE KEY FILE!
Permissions 0644 for 'id_ed25519' are too open.
This private key will be ignored.
Load key "id_ed25519": bad permissions
```

Fix with `chmod 600`, see [The filesystem and permissions](/posts/linux-filesystem-permissions/). `ssh-keygen -p -f key` changes the passphrase; adding `-m PEM` rewrote my RSA key to a `-----BEGIN RSA PRIVATE KEY-----` file (old format). I recommend a passphrase on real keys.

## authorized_keys

On the server, the {{< term "authorized-keys" "authorized_keys" >}} file lists public keys that may log in, each line optionally prefixed with options: `restrict` (turns off forwarding, pty and more), `from="..."`, `command="..."`. I wrote a tiny Python linter, a line-based check and not sshd's parser, and ran it on an invented file:

```
line 2: WARN no options: key can run anything, forward anything
line 3: OK ssh-ed25519
line 4: WARN options without 'restrict'
line 5: FAIL no key type found
```

## known_hosts and TOFU

The client keeps the servers' *host* keys in {{< term "known-hosts" "known_hosts" >}}; these identify servers and are different from your *user* key. The first connection is trust on first use (TOFU): you accept the fingerprint, later changes are suspicious. `ssh-keygen -H` hashes the host names; `-F` looks one up:

```
$ ssh-keygen -F 127.0.0.1 -f known_hosts
# Host 127.0.0.1 found: line 1
|1|ONhPF46cjlIWMhhj+xun8mOwJlQ=|muhnCYY1... ssh-ed25519 ...
```

## A real login, and a changed host key

I started `sshd` as my own user on `127.0.0.1:22922`, config in `<tmp>` (`PasswordAuthentication no`, `UsePAM no`, my authorized_keys). It accepted the throwaway key:

```
$ ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i id_ed25519 -p 22922 127.0.0.1 echo ok
Warning: Permanently added '[127.0.0.1]:22922' (ED25519) to the list of known hosts.
ok
```

Then I restarted it with a different host key and connected again:

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
Host key for [127.0.0.1]:22922 has changed and you have requested strict checking.
Host key verification failed.
```

On a real server this means a reinstall or an attack: verify out of band before deleting the old line. I then killed sshd and checked with `ps` that none remained.

## ssh_config and agents

`ssh -G alias` prints the resolved config without connecting. With a config using invented addresses (`Host web`, `ProxyJump jump`, `ControlMaster auto`):

```
user deploy
hostname 192.0.2.10
port 22
controlmaster auto
identityfile <tmp>/id_ed25519
controlpersist 60
proxyjump jump
```

An {{< term "ssh-agent" "ssh-agent" >}} holds decrypted keys in memory. I ran a private one (`ssh-agent -a <tmp>/agent.sock`), added the demo key, saw it in `ssh-add -l`, and killed it. Agent forwarding (`-A`) lets the remote host use your agent while you are connected; per the man page, root there can abuse it, so prefer `ProxyJump`.

## Certificates

An {{< term "ssh-certificate" "SSH certificate" >}} is a public key signed by a CA key (`ssh-keygen -s ca -I demo-cert -n deploy -V +1d key.pub`). `ssh-keygen -L` showed type `ssh-ed25519-cert-v01@openssh.com`, key ID, principal `deploy` and validity. Unlike an [x509 certificate](/posts/sec-tls-x509-certificates/), it has no chain: one CA signs directly, and servers trust it via `TrustedUserCAKeys`.

## Hardening a Linux server

From the OpenSSH man page on macOS, not run on Linux: `PasswordAuthentication no` (default yes), `PermitRootLogin no` (default `prohibit-password`), `MaxAuthTries` (default 6), `LoginGraceTime` (default 120 s), plus `KbdInteractiveAuthentication no` and `AllowUsers`/`AllowGroups`. fail2ban exists to ban repeated failures; I did not try it. Port knocking I do not recommend, it is obscurity.

## A few things to watch

- Never paste a private key into chats, tickets or git.
- Use a passphrase and rotate keys of people who leave.
- Keep a second session open when changing `sshd_config`.
- Do not forward your agent to hosts you do not control.
- Don't blindly accept a changed host key.

## Exercise

In a temp directory, generate an ed25519 key, start your own sshd on a high port, log in, then change the host key and read the warning.

## What's next

The next post is “Users, sudo and capabilities”.
