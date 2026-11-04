+++
date = '2027-05-25T10:00:00+03:30'
draft = false
title = 'Users, sudo and capabilities'
description = 'Linux users, sudo and capabilities from the man pages: passwd and shadow, sudoers pitfalls, splitting root into capabilities, and a Go mask decoder.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "sudo", "capabilities", "security", "users", "least-privilege", "go", "macos"]
cover = { image = "/images/covers/linux-users-sudo-capabilities.png", alt = "Users, sudo and capabilities", hiddenInSingle = true }
+++

Suppose you want your web server to listen on port 80. On Linux, ports below 1024 are reserved, so the quick fix is to run the service as root. It works, and it is a bad deal: now a bug in that server, anywhere in it, can read every file on the machine, change any user and kill any process. You wanted one small permission and you handed over all of them.

This post is about how Linux lets you give less. It starts with who a "user" really is, then looks at `sudo`, the usual way to borrow root for one command, and then at {{< term "linux-capabilities" "capabilities" >}}, which cut root's power into small separate pieces. The earlier posts set the scene: [SSH and keys](/posts/linux-ssh-keys/) was about how you get in, and [The filesystem and permissions](/posts/linux-filesystem-permissions/) was about what the file permission bits mean. Here the question is what a login is allowed to do once it is inside.

A note on honesty first. I wrote this on a Mac, and a Mac has no Linux kernel, no `/proc` and no capabilities. So nothing about capabilities was run on a real Linux process. The facts come from the man pages (passwd(5), shadow(5), sudoers(5), capabilities(7)) and from the Go source code, and I say "according to the man page" only where I checked the page. The few commands I did run are marked as run on macOS.

## Users and groups are just numbers

To the kernel, a user is a number, the **UID**. Names such as `www-data` exist for humans, and a file in `/etc` maps one to the other. According to passwd(5), `/etc/passwd` has one line per account with seven fields separated by colons: login name, password field, UID, primary group id (GID), a comment, home directory and login shell. A line could look like this (an invented example):

```
deploy:x:1001:1001:Deploy user:/home/deploy:/bin/bash
```

The `x` in the second field means the password is not here. The man page says systems with shadow passwords keep the encrypted password in `/etc/shadow`, and that this file must not be readable by regular users. According to shadow(5), a password field that starts with `!` means the password is locked, so nobody can log in with it.

Every process carries the UID of the user who started it, a primary group, and often a list of extra (supplementary) groups. Every file check you saw in the permissions post compares those numbers with the numbers stored on the file.

The special number is **UID 0**, called root. The kernel does not look at the name "root"; it looks at the number. Historically, UID 0 simply skipped most permission checks. On modern Linux the kernel asks a finer question, which is whether the process holds the right capability, and root is the user who starts with all of them. We come back to this below.

Here is what I ran on the Mac, in a scratch directory. These are BSD tools, and the ids are replaced with placeholders:

```
$ [ "$(id -u)" -eq 0 ] && echo root || echo "not root"
not root
$ touch f && chmod 640 f && stat -f '%Sp %u %g' f
-rw-r----- <uid> <gid>
$ ls -l /usr/bin/sudo | awk '{print $1}'
-r-s--x--x
```

The first line is the classic way a script checks that it runs as root: `id -u` prints the numeric UID, and root is 0. The second shows a file with mode 640, so the owner can read and write and the group can read. The `stat -f` format is BSD syntax; GNU `stat` on Linux uses `-c` instead, and I did not run that one.

The third line is the interesting one. The `s` where you expect an `x` is the {{< term "setuid" "setuid" >}} bit. A setuid program runs with the identity of its file's owner, not of the person who started it. That is how `sudo` can work at all: it is owned by root, so it runs as root even when an ordinary user types it.

## sudo: borrowing root for one command

{{< term "sudo" "sudo" >}} runs one command as another user, usually root, if a policy file called {{< term "sudoers" "sudoers" >}} allows it. The idea is simple. Instead of logging in as root and staying root, you ask for root one command at a time, and the system can record each request.

From the sudo and sudoers manuals:

- Edit the policy with `visudo`. It locks the file against two people editing at once and checks the syntax before it saves, because a broken sudoers file can stop sudo from working at all. `visudo -c` only checks the file and exits without opening an editor.
- `sudo -l` lists what you are allowed to run.
- `sudoedit` (or `sudo -e`) edits a file by making a temporary copy owned by you, running your editor on that copy, and copying the result back. The editor itself is not started as root.
- `env_reset` is on by default, which means the command does not simply inherit your environment variables.
- `NOPASSWD` removes the password prompt for the commands it covers. That is convenient for automation, but then anyone who controls that account can run those commands as root without any check.

I did not read the sudoers file of this machine and I did not run sudo.

A rule in sudoers is a line like "this user may run these commands as that user". The principle of {{< term "least-privilege" "least privilege" >}} says to keep that list of commands short and specific, and never `ALL`. Two things make even a short list weaker than it looks, and both are mentioned in sudoers(5):

- **Wildcards in arguments.** The page says to use them with care and notes that a wildcard can match whitespace. A rule that allows `cat /var/log/app/*` may also allow `cat /var/log/app/x /etc/shadow`, because the `*` can swallow the space and the second path.
- **Programs that can start other programs.** Shells, editors and pagers (such as `less`) can run a command from inside themselves, a "shell escape". If you allow `sudo vim`, the user can type `:!sh` and has a root shell. The page describes the `NOEXEC` tag as a defence, but only when sudo was built with support and the operating system supports it, so do not rely on it. Simply do not put such programs in the list.

So `sudo bash` is not "a command". It is the whole of root, with a different name.

## Capabilities: root in pieces

Back to the web server on port 80. According to capabilities(7), the kernel divides the privileges of root into distinct units called capabilities, and a process can hold some and not others. A few of them, with their numbers from the kernel header `linux/capability.h`:

| Number | Name | What it allows (per the man page) |
|---|---|---|
| 0 | CAP_CHOWN | arbitrary changes of file owner and group |
| 1 | CAP_DAC_OVERRIDE | bypass file read, write and execute checks |
| 10 | CAP_NET_BIND_SERVICE | bind to ports below 1024 |
| 13 | CAP_NET_RAW | use raw and packet sockets |
| 21 | CAP_SYS_ADMIN | a very wide collection of powers |

Now the answer to the port 80 problem is clear. The server does not need to be root, it needs one capability: `CAP_NET_BIND_SERVICE`. Run it as a normal user, give it only that, and a bug in it can no longer read every file.

CAP_SYS_ADMIN is the one to avoid. The man page says it "can plausibly be called the new root", because it covers so many different powers. If a program asks for it, ask why.

Each thread holds five sets of capabilities: permitted, effective, inheritable, bounding and ambient (the ambient set exists since Linux 4.3). In short, "effective" is what is checked right now, "permitted" is what the thread may switch on, and "bounding" is a ceiling for what it can ever get. A file can also carry capabilities. A command such as `setcap cap_net_bind_service=+ep /path/to/bin` would let that binary bind port 80 without anyone being root. I did not run it, because I have no Linux here and it needs root.

There is also a related safety switch, {{< term "no-new-privs" "no_new_privs" >}}. According to the prctl man page, once a process sets it, `execve` will not grant privileges that the process could not have had without the call: in practice setuid and setgid bits and file capabilities stop working. It is inherited by child processes, and once set it cannot be unset.

## Dropping privileges, and doing it in systemd

The classic daemon solves the port problem in time rather than in space. It starts as root, binds port 80, and then switches to an ordinary user for the rest of its life. In Go this means calling `syscall.Setgroups`, `syscall.Setgid` and `syscall.Setuid`. I read the Go source for Linux: when the program is built without cgo, these calls go through `AllThreadsSyscall`, so the change reaches every thread of the process, and with cgo they go through libc. This matters because Go runs your code on many OS threads, and a change that reached only one of them would be useless.

The order matters, and this is my own reasoning, not a quote. Once you become a non-root user, you can no longer change your groups, so set the groups and the GID first and the UID last. And check the error of every call. A failed `Setuid` that you ignore leaves you running as root, which is exactly what you were trying to avoid.

On a modern server you often let systemd do this for you, which is safer than writing it yourself. In [systemd: units and timers](/posts/linux-systemd-units-timers/) a service file says it in a declarative way, using settings such as `CapabilityBoundingSet=`, `AmbientCapabilities=` and `NoNewPrivileges=` (all from the systemd.exec documentation). Containers use the same idea: they start from a reduced set of capabilities, as we will see in [cgroups and namespaces: the base of containers](/posts/linux-cgroups-namespaces/).

## A small decoder I could run

When you look at a running process, its capabilities appear in `/proc/<pid>/status` as lines like `CapEff: 00000000a80425fb`. That hex number is a **mask**: bit 0 stands for CAP_CHOWN, bit 1 for CAP_DAC_OVERRIDE, and so on, so a mask is a whole set of capabilities written as one number. Nobody reads these by eye, so I wrote a small Go program that turns a mask into names. Its table of names is copied from the kernel header.

The program has two commands that I could run on macOS: `mask <hex>` decodes one number, and `status <file>` reads a file in the `/proc/<pid>/status` format and decodes the capability lines. The input files are **samples I wrote in the documented format, not captured from a real process**. The Go tests pass with `go test -race`. First the "unprivileged" sample, which has empty permitted and effective sets and a full bounding set:

```
$ lx11 status testdata/status_unprivileged.txt
CapInh 0000000000000000: (none)
CapPrm 0000000000000000: (none)
CapEff 0000000000000000: (none)
CapBnd 000001ffffffffff: 41 capabilities (CAP_CHOWN ... CAP_CHECKPOINT_RESTORE)
CapAmb 0000000000000000: (none)
```

Line by line: this process has no capabilities it could use right now (`CapEff` is zero), even though its ceiling, `CapBnd`, still allows all 41 that the table knows. That is what an ordinary user's process looks like. Next, a mask that I made up to look like the set a container might get:

```
$ lx11 mask 00000000a80425fb
CAP_CHOWN
CAP_DAC_OVERRIDE
CAP_FOWNER
CAP_FSETID
CAP_KILL
CAP_SETGID
CAP_SETUID
CAP_SETPCAP
CAP_NET_BIND_SERVICE
CAP_NET_RAW
CAP_SYS_CHROOT
CAP_MKNOD
CAP_AUDIT_WRITE
CAP_SETFCAP
```

Fourteen names, one per line, in bit order. Notice what is missing: there is no CAP_SYS_ADMIN, and no CAP_NET_ADMIN. The mask is my invention of such a set; it is not a measurement of any real container.

There is a third command, `self`, which reads `/proc/self/status` of the program itself. It sits behind the build constraint `//go:build linux`. On this Mac it printed "Linux only: /proc/self/status does not exist here". For Linux I only cross-compiled: `GOOS=linux GOARCH=amd64 go vet ./...` passes, and the Linux binary was never run. So I can show you the decoder works, but not a real process's capabilities.

## Common privilege mistakes

- **`NOPASSWD: ALL`.** It turns your account into a root account with no password in between. Give a specific command list instead.
- **Wildcards and editors in the command list.** As above, a wildcard can match more than you meant, and an editor or pager is a way out of sudo's control.
- **Reaching for root when one capability would do.** Ask what the program really needs. And if the answer is CAP_SYS_ADMIN, look harder.
- **Staying privileged after the privileged step.** Drop the privilege as soon as the port is bound or the file is opened, and check every error from the call that drops it.
- **Believing this post tested it.** I did not run `sudo`, `setcap`, `getcap` or `capsh`. Try them yourself on a machine you can break.

## Exercise

On a throwaway Linux VM, run `grep Cap /proc/self/status` once as an ordinary user and once as root. Decode the `CapEff` value of each with `lx11 mask`, and compare the result with what you expected from this post.

## What's next

Next is "Logs and journalctl". Once a service runs with the right privileges, the next question is where its errors and messages end up, and how you find them.
