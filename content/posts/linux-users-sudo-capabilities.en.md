+++
date = '2027-05-25T10:00:00+03:30'
draft = false
title = 'Users, sudo and capabilities'
description = 'Linux users, sudo and capabilities from the man pages: passwd and shadow, sudoers pitfalls, splitting root into capabilities, and a Go mask decoder.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "sudo", "capabilities", "security", "users", "least-privilege", "go", "macos"]
cover = { image = "/images/covers/linux-users-sudo-capabilities.png", alt = "Users, sudo and capabilities", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. This is the eleventh post of the Linux series, after [SSH and keys](/posts/linux-ssh-keys/). Once you can log in, what may that login do? Facts come from man pages and the Go source; samples are labelled "not captured". File bits are in [The filesystem and permissions](/posts/linux-filesystem-permissions/).

## Users and groups

Per passwd(5), `/etc/passwd` has one line per account with seven colon-separated fields: name, password placeholder, UID, GID, comment, home, shell. The hash is not there. According to shadow(5), `/etc/shadow` holds the encrypted password, and an entry starting with `!` means the password is locked. I did not find a file mode in that page, so I only say the file is meant to be unreadable for ordinary users. Besides the primary group, a process carries supplementary groups.

Root is UID 0. The kernel now checks capabilities; root is just the user who starts with all of them.

What I ran on the Mac (BSD userland), ids replaced:

```
$ [ "$(id -u)" -eq 0 ] && echo root || echo "not root"
not root
$ stat -f '%Sp %u %g' file-i-created      # output: ids replaced
-rw-r----- <uid> <gid>
$ ls -l /usr/bin/sudo                      # owner and group replaced
-r-s--x--x <owner> <group> /usr/bin/sudo
```

The `s` is the {{< term "setuid" "setuid" >}} bit: sudo runs as its owner. `stat -f` is BSD; GNU stat uses `-c`, which I did not run.

## sudo and sudoers

{{< term "sudo" "sudo" >}} runs a command as another user if the {{< term "sudoers" "sudoers" >}} policy allows. From the man pages:

- Edit with `visudo`; `visudo -c` checks syntax. `sudoedit` edits a file without running the editor as root.
- `sudo -l` lists what you may run.
- `env_reset` is on by default, so the caller's environment is cleaned; the man page encourages keeping it.
- `NOPASSWD` removes the password prompt: anyone who gets your session gets root.

I did not read this machine's sudoers file or run sudo.

The core of {{< term "least-privilege" "least privilege" >}} is a short command list, not `ALL`. Two pitfalls are in sudoers(5). Wildcards in arguments can match anything, including spaces, and the page says to use them with care. Programs with shell escapes (shells, editors, pagers) let a user leave sudo's control; the page lists `NOEXEC` as one defence, depending on OS support. So `sudo bash` is simply a root shell. `su` switches user with the target's password, and `doas` is a smaller OpenBSD alternative to sudo; I show neither.

## Capabilities: root in pieces

According to capabilities(7), the kernel divides root's powers into {{< term "linux-capabilities" "capabilities" >}}. A few, numbered as in `linux/capability.h`:

| Number | Name | Allows |
|---|---|---|
| 0 | CAP_CHOWN | change file owners |
| 1 | CAP_DAC_OVERRIDE | bypass file permission checks |
| 10 | CAP_NET_BIND_SERVICE | bind ports below 1024 |
| 13 | CAP_NET_RAW | raw sockets |
| 21 | CAP_SYS_ADMIN | very broad |

The man page says CAP_SYS_ADMIN “can plausibly be called ‘the new root’”; avoid it. Each thread has five sets: permitted, effective, inheritable, bounding and ambient (ambient since Linux 4.3). Files can carry capabilities too: `setcap cap_net_bind_service=+ep /path/to/bin` would let a web server bind port 80 without being root. I did not run it. The {{< term "no-new-privs" "no_new_privs" >}} flag stops execve from gaining privilege via setuid or file capabilities.

## Dropping privileges and systemd

The classic daemon binds port 80 as root, then drops to a normal user. In Go, I read the source of `syscall.Setuid` for Linux: without cgo it calls `AllThreadsSyscall`, so the change reaches every thread; with cgo it goes through libc. Order matters: `Setgroups` and `Setgid` first, `Setuid` last, and check every error. In [systemd: units and timers](/posts/linux-systemd-units-timers/) the same idea is declarative: `CapabilityBoundingSet=`, `AmbientCapabilities=` and `NoNewPrivileges=` per the systemd.exec docs. Containers start from a reduced set, see [cgroups and namespaces](/posts/linux-cgroups-namespaces/).

## A decoder I could run

`/proc/<pid>/status` prints `CapInh`, `CapPrm`, `CapEff`, `CapBnd`, `CapAmb` as hex masks. My Go program maps bit numbers to names using a table copied from the kernel header. These are **samples in the documented format, not captured**; `go test -race` passed:

```
$ lx11 status testdata/status_unprivileged.txt
CapPrm 0000000000000000: (none)
CapEff 0000000000000000: (none)
CapBnd 000001ffffffffff: 41 capabilities (CAP_CHOWN ... CAP_CHECKPOINT_RESTORE)
$ lx11 mask 00000000a80425fb
CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER CAP_FSETID CAP_KILL CAP_SETGID CAP_SETUID
CAP_SETPCAP CAP_NET_BIND_SERVICE CAP_NET_RAW CAP_SYS_CHROOT CAP_MKNOD
CAP_AUDIT_WRITE CAP_SETFCAP
```

(Other lines trimmed, output wrapped.) The second mask is my invention of a container-like set. The `self` command reads `/proc/self/status` under `//go:build linux`; here it printed "Linux only". The Linux build passed `GOOS=linux GOARCH=arm64 go vet ./... && go build` and was never run.

## A few things to watch

- Never put `NOPASSWD: ALL` in a rule.
- Avoid wildcards and editors in sudoers command lists.
- Prefer one capability over root; avoid CAP_SYS_ADMIN.
- Drop privileges right after the privileged step.
- Not run by me: sudo, setcap, getcap, capsh.

## Exercise

On a throwaway VM, run `grep Cap /proc/self/status` as a normal user and as root, and decode both masks with `lx11 mask`.

## What's next

The next post is “Logs and journalctl”.
