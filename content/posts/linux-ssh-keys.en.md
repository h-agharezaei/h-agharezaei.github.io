+++
date = '2027-05-20T10:00:00+03:30'
draft = false
title = 'SSH and keys'
description = 'SSH and keys in a throwaway directory: ed25519 vs RSA, fingerprints, the 0600 rule, authorized_keys, known_hosts, ssh_config, agents, certificates.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "ssh", "openssh", "keys", "security", "sshd", "macos"]
cover = { image = "/images/covers/linux-ssh-keys.png", alt = "SSH and keys", hiddenInSingle = true }
+++

You have logged in to a server with your key for months. One morning it suddenly asks for a password. Nothing changed, as far as you know. In most cases like this, SSH quietly decided not to use your key, usually because of a file permission, and it gave you no loud error. To debug it you need a clear picture of what the key does, which files are involved and what each side checks.

This post builds that picture in a throwaway directory, so nothing real is at risk. It follows [Linux networking: ip, ss and nftables](/posts/linux-networking-ip-ss-nftables/), which warned that a wrong firewall rule over SSH locks you out: SSH is how most of us reach Linux servers at all, and what it checks is worth knowing.

Here is how I worked, and what is what. The key, config and certificate commands below I ran for this rewrite on a Mac with `OpenSSH_10.5p1, LibreSSL 3.3.6` (the output of `ssh -V`), not on Linux. I worked only in a throwaway directory, written `<tmp>` in the text, with explicit paths for every key, and never touched my real keys or connected to any remote host. The local `sshd` login and the agent demo are from my original run of this post, on OpenSSH 10.3; I did not repeat them, and I label them below. Where Linux may differ, I say "per the man page". Private keys are secrets, see [Managing secrets and keys](/posts/sec-secrets-management/).

## How a key proves who you are

The core idea is simple. A password is a secret that you send to the server, so anyone who sees it or the server's copy can reuse it. A key pair avoids that: you keep a **private key** that never leaves your machine, and you give the server the matching **public key**. When you log in, the server needs proof that you hold the private key, and the client provides it without sending the key. According to the ssh man page, the client "proves that it has access to the private key" and the server checks that the corresponding public key is authorized. In outline, the proof is a signature that only the private key can make and that the public key can verify.

Two files carry this. On your machine is the private key (and the public one beside it). On the server, the file `authorized_keys` in your account lists the public keys allowed to log in. There is a second, separate pair in the other direction: the server has its own **host key**, so you can check that you are talking to the right server. We will meet both.

## Key pairs

An {< term "ssh-key-pair" "SSH key pair" >} is a private file you keep and a public line you share. I generated three with `ssh-keygen -t ... -N '' -C demo@example` (no passphrase, because they are throwaway):

```
$ ls -l id_*    (mode, bytes, name)
-rw-------  505 id_ecdsa
-rw-r--r--  174 id_ecdsa.pub
-rw-------  399 id_ed25519
-rw-r--r--   94 id_ed25519.pub
-rw-------  2602 id_rsa
-rw-r--r--  566 id_rsa.pub
$ ssh-keygen -lf id_ed25519.pub
256 SHA256:BzSjfCOBGiFN6UNphueQRIsUkRuaehQIOE4B4H7eLOA demo@example (ED25519)
$ ssh-keygen -lf id_rsa.pub
3072 SHA256:bJ4zqQZTFCOTwftUw0tVUWUqeD7xkcMF+Pi13jHxpzs demo@example (RSA)
```

The listing shows the modes and sizes in bytes. Both private files are mode `-rw-------` (only I can read them), and the public ones are `-rw-r--r--`. The `.pub` file for ed25519 is 94 bytes, the RSA one 566: ed25519 is about six times smaller as a public line, one reason it is the usual choice today. The fingerprint is a hash of the public key, a short label for it. `ssh-keygen -lf` prints the size, the hash, the comment and the type.

The public file is one line: type, base64 data, comment. This is the whole thing for my throwaway ed25519 key, and it is safe to show because it is public by design:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGhhy5BvlctXsN8LdQo5qCL07JV2OHuoLIJw1H9nFyzz demo@example
```

The private file starts with `-----BEGIN OPENSSH PRIVATE KEY-----`; I print only that line and nothing else of it, ever. `ssh-keygen -lvf` also draws a "randomart" picture, a small ASCII image of the key that makes two fingerprints easier to compare by eye.

## The 0600 rule

Back to the opening mystery. SSH refuses private keys that other users can read. To see this, I copied a private key, made the copy mode 0644 and asked for its public part:

```
$ ssh-keygen -y -f bad_key
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for 'bad_key' are too open.
It is required that your private key files are NOT accessible by others.
This private key will be ignored.
Load key "bad_key": bad permissions
```

SSH does not try to use the key, it only prints that the permissions are too open and that the key "will be ignored". When this happens during a login, the client silently moves on to the next method, and that is how you end up at a password prompt. The fix is `chmod 600`, see [The filesystem and permissions](/posts/linux-filesystem-permissions/).

The server side has a similar check. According to the sshd_config man page, `StrictModes` (default `yes`) makes sshd check the modes and ownership of the user's files and home directory before accepting a login. So a world-writable home directory or `authorized_keys` can also break key login, and on the server you will only see it in the log.

Two more things I tried. `ssh-keygen -p -f key` changes the passphrase of a key. Adding `-m PEM` rewrote my RSA key into a file that starts with `-----BEGIN RSA PRIVATE KEY-----`, the old format. I recommend a passphrase on real keys.

## authorized_keys

On the server, the {< term "authorized-keys" "authorized_keys" >} file lists the public keys that may log in. Each line can start with options that restrict what that key may do: `restrict` turns off forwarding, the pseudo-terminal and more; `from="..."` limits where the key may be used from; `command="..."` forces one command. A key with no options can run anything and forward anything.

To make this concrete I wrote a tiny Python checker. It is a line-based check, not sshd's parser. I ran it on an invented file in which the keys are shortened placeholders:

```
# invented example
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE...EXAMPLE ci@example
restrict,from="198.51.100.0/24",command="/usr/bin/true" ssh-ed25519 AAAA...EXAMPLE backup@example
from="203.0.113.5" ssh-rsa AAAAB3NzaC1yc2EAAAADAQABEXAMPLE old@example
nonsense line
```

and it printed:

```
line 2: WARN no options: key can run anything, forward anything
line 3: OK ssh-ed25519
line 4: WARN options without 'restrict'
line 5: FAIL no key type found
```

Line 2 has no options, so the checker warns that this key can run anything and forward anything. Line 3 starts with `restrict`, so it is fine. Line 4 has options but no `restrict`, so something is still allowed by default. Line 5 is not a key at all. (Line 1 is a comment and is skipped.)

## known_hosts and TOFU

Now the other direction. The client keeps the servers' *host* keys in {< term "known-hosts" "known_hosts" >}. These identify servers and are different from your *user* key. The first connection to a server is trust on first use (TOFU): ssh shows the server's fingerprint and you accept it. After that, ssh compares, and a change is suspicious. `ssh-keygen -H` hashes the host names in the file, so the file does not reveal which servers you use, and `-F` looks one up. Here I used a throwaway key as a fake host key for `127.0.0.1`:

```
$ ssh-keygen -F 127.0.0.1 -f known_hosts
# Host 127.0.0.1 found: line 1
|1|98zxhnZ1VcQcFbxydmTLPNBypR0=|s9N2l/8OTKzirkt2xrXUBmfZcnE= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfogGkj1mTYg3MbVhLA0iJ68wBo3k4qTMI1q9jDzWGW
```

The first line of the result says it found the host on line 1. The second line is the entry: `|1|...|...` is the hashed name (salt and hash), then the key type and key. You cannot read the host name from it, but ssh can still match it.

## A real login, and a changed host key

This part is from the original run of this post (OpenSSH 10.3), which I did not repeat for this rewrite. I started `sshd` as my own user on `127.0.0.1:22922`, with its config in `<tmp>`: `PasswordAuthentication no`, `UsePAM no` and my throwaway `authorized_keys`. It accepted the throwaway key:

```
$ ssh -F /dev/null -o IdentityAgent=none -o IdentitiesOnly=yes -i id_ed25519 -p 22922 127.0.0.1 echo ok
Warning: Permanently added '[127.0.0.1]:22922' (ED25519) to the list of known hosts.
ok
```

The warning line is the TOFU step: the server's host key was added to `known_hosts`. Then `ok` is the output of the remote command. Then I restarted `sshd` with a different host key and connected again:

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
Host key for [127.0.0.1]:22922 has changed and you have requested strict checking.
Host key verification failed.
```

The client refuses to continue, because the key it remembers no longer matches. On a real server this means either a reinstall or an attack, so verify the new fingerprint some other way (a console, a person you trust) before deleting the old line. After the experiment I killed that `sshd` and checked with `ps` that none remained.

## ssh_config and agents

Typing long options gets old, so ssh reads a config file. `ssh -G alias` prints the resolved configuration without connecting, which makes it a safe way to see what a config means. This is the invented config I used (documentation addresses only):

```
Host jump
    HostName 198.51.100.2
    User deploy
Host web
    HostName 192.0.2.10
    User deploy
    ProxyJump jump
    ControlMaster auto
    ControlPersist 60
    IdentityFile <tmp>/id_ed25519
```

And I picked these lines from the output of `ssh -F cfg -G web` (the full output is longer):

```
user deploy
hostname 192.0.2.10
port 22
controlmaster auto
identityfile <tmp>/id_ed25519
controlpersist 60
proxyjump jump
```

`web` inherited `User deploy`, the address `192.0.2.10`, the multiplexing options and the jump host, and got the default port 22. `ProxyJump jump` means "reach `web` through `jump`".

An {< term "ssh-agent" "ssh-agent" >} holds decrypted keys in memory so you type the passphrase once. In the original run I started a private one (`ssh-agent -a <tmp>/agent.sock`), added the demo key, saw it in `ssh-add -l` and killed it. For this rewrite I did not touch any agent. Agent forwarding (`-A`) lets the remote host use your agent while you are connected; per the man page, root on that host can abuse it, so prefer `ProxyJump`.

## Certificates

An {< term "ssh-certificate" "SSH certificate" >} is a public key signed by a CA key. Instead of copying a user's key to every server, you sign it once with a CA, and servers that trust the CA accept it. I made a throwaway CA key and signed my throwaway key for the user `deploy`, valid for one day, then inspected it (trimmed to the main lines):

```
$ ssh-keygen -s ca -I demo-cert -n deploy -V +1d id_ed25519.pub
$ ssh-keygen -L -f id_ed25519-cert.pub
        Type: ssh-ed25519-cert-v01@openssh.com user certificate
        Key ID: "demo-cert"
        Principals:
                deploy
        Critical Options: (none)
```

`Type` says it is an ed25519 user certificate, `Key ID` is the label I gave it, and `Principals` lists the user names it may log in as. Unlike an [x509 certificate](/posts/sec-tls-x509-certificates/), it has no chain: one CA signs directly, and servers trust it via `TrustedUserCAKeys` in `sshd_config`.

## Hardening a Linux server

These settings come from the OpenSSH man pages on this Mac (the sshd_config page, which I read for this rewrite) and were not run on Linux: `PasswordAuthentication no` (the default is yes), `PermitRootLogin no` (the default is `prohibit-password`), `MaxAuthTries` (default 6), `LoginGraceTime` (default 120 seconds), plus `KbdInteractiveAuthentication no` and `AllowUsers` or `AllowGroups`. Tools like fail2ban exist to ban repeated failures; I did not try it. I do not recommend port knocking: it is security by obscurity.

## Keeping keys safe

- **Never paste a private key into chats, tickets or git.** Treat anything that holds one as a secret store.
- **Use a passphrase, and rotate keys when people leave.** Removing a person's line from `authorized_keys` is the work that gets forgotten.
- **Keep a second session open when you change `sshd_config`.** A mistake in the config can lock you out, just like a firewall rule.
- **Do not forward your agent to hosts you do not control.**
- **Do not accept a changed host key blindly.** The warning is the whole point of `known_hosts`.

## Exercise

In a temporary directory, generate an ed25519 key with `ssh-keygen -t ed25519 -f ./key`. Check its fingerprint with `ssh-keygen -lf key.pub`. On a throwaway Linux machine, start your own `sshd` on a high port with its own config, log in with the key, then change the host key and read the warning.

## What's next

The next post is "Users, sudo and capabilities". Logging in is only the beginning: it explains what a login is allowed to do once it works, and how to give a process only the privileges it needs.
