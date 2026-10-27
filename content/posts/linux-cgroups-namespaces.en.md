+++
date = '2027-04-26T10:00:00+03:30'
draft = false
title = 'cgroups and namespaces: the base of containers'
seoTitle = 'cgroups and namespaces: how containers work'
description = 'Linux cgroups and namespaces explained from the man pages: how a container is a restricted process, plus two Go programs I only cross-compiled.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "cgroups", "namespaces", "containers", "go", "macos"]
cover = { image = "/images/covers/linux-cgroups-namespaces.png", alt = "cgroups and namespaces: the base of containers", hiddenInSingle = true }
+++

I wrote this on a Mac; nothing here ran on Linux. This is the sixth post of the Linux series, after [systemd: units and timers](/posts/linux-systemd-units-timers/). The question: what is a container, really? The answer comes from the man pages and kernel docs, plus two Go programs that I compiled for Linux and **never ran**. Anything Linux-like below is labelled "illustrative, not captured".

> Honest disclaimer: this Mac has no Linux kernel, no VM, and I kept the Docker daemon off. As far as I know, Docker Desktop on a Mac runs containers inside a Linux virtual machine, which is why I could test nothing. The earlier [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/) also admitted that it did no real Docker build.

## A restricted view and restricted resources

A container is a normal process with two restrictions. A {{< term "namespace" "namespace" >}} limits what the process can see. A {{< term "cgroup" "cgroup" >}} (control group) limits what it can use. Together with a root filesystem, that is a {{< term "container" "container" >}}; the kernel has no "container" object.

According to namespaces(7), the types are:

| Isolates | Flag | Illustrative, not captured |
|---|---|---|
| Hostname | `CLONE_NEWUTS` | `hostname` inside shows a different name |
| Process IDs | `CLONE_NEWPID` | the first process sees itself as PID 1 |
| Mount points | `CLONE_NEWNS` | its mounts do not change the host |
| Network | `CLONE_NEWNET` | its own interfaces and ports |
| IPC | `CLONE_NEWIPC` | its own System V IPC |
| User and group IDs | `CLONE_NEWUSER` | root inside, unprivileged outside |
| Cgroup root | `CLONE_NEWCGROUP` | a different cgroup root |
| Clocks | `CLONE_NEWTIME` | boot and monotonic clocks |

You enter them with `clone(2)`, `unshare(2)` or `setns(2)`, and the command-line tools are `unshare(1)` and `nsenter(1)`. Each process has links in `/proc/<pid>/ns/`; two processes in the same namespace show the same identifier, such as `uts:[...]`. The page says creating most namespaces needs `CAP_SYS_ADMIN`, but a user namespace needs no privilege since Linux 3.8. That is the documented basis of rootless containers.

## Limits with cgroups v2

According to the kernel docs, cgroup v2 is a single unified hierarchy, normally mounted at `/sys/fs/cgroup`. A group is a directory:

| Goal | File | Illustrative, not captured |
|---|---|---|
| Move a process in | `cgroup.procs` (write a PID) | PID appears in the file |
| Cap memory | `memory.max` | the OOM killer acts at the cap |
| Cap process count | `pids.max` | fork fails beyond it |
| Cap CPU | `cpu.max` (`$MAX $PERIOD`) | at most MAX per PERIOD |
| Count OOM kills | `memory.events`, field `oom_kill` | counter grows |

The docs say that when usage reaches `memory.max` and cannot be reduced, the {{< term "oom-killer" "OOM killer" >}} is invoked in that cgroup. A controller is enabled for children through the parent's `cgroup.subtree_control`.

## Two programs, compiled but not run

In `~/Documents/work/blog-series/linux-cgroups-namespaces` I wrote one module. `ns` mode starts a command with `syscall.SysProcAttr{Cloneflags: CLONE_NEWUTS | CLONE_NEWPID | CLONE_NEWNS}`, the classic demo. `cg` mode creates `/sys/fs/cgroup/blogdemo`, enables `+memory +pids` in the parent, writes `memory.max` (64 MiB) and `pids.max` (32), starts the command and writes its PID to `cgroup.procs`. Both check for root and cgroup v2 first. Weakness: the child runs briefly before joining the cgroup.

```go
//go:build linux
cmd.SysProcAttr = &syscall.SysProcAttr{
	Cloneflags: syscall.CLONE_NEWUTS | syscall.CLONE_NEWPID | syscall.CLONE_NEWNS,
}
```

A {{< term "build-tag" "build tag" >}} keeps this off the Mac, as in [/proc and observing the system](/posts/linux-proc-observability/). On Linux I only did `GOOS=linux GOARCH=arm64 go vet ./... && go build`; both passed, and **I never ran the binary**. On the Mac, `go run . ns /bin/sh` used the stub and printed:

```
Linux only: namespaces and cgroups do not exist on this OS
```

## What a runtime adds

Hedged, from documentation: an image is a stack of layers, commonly mounted with {{< term "overlayfs" "overlayfs" >}}, and the runtime switches the process to that root with `pivot_root`. Tools such as Docker, containerd and runc add images, layers and a runtime configuration; as I understand it, the OCI runtime specification defines that configuration. I did not run any of them.

## A few things to watch

- A container is not a VM: it shares the host kernel.
- Namespaces hide; cgroups limit. You need both.
- Both programs need root on Linux; use a throwaway machine.
- A hit on `memory.max` ends in an OOM kill inside the group, not a polite error.

## Exercise

On a disposable Linux machine, read `unshare(1)` and try `unshare --uts --pid --fork --mount-proc /bin/sh`. Compare `readlink /proc/self/ns/uts` before and after, then run the `cg` mode and read `memory.events`.

## What's next

The next post is “Memory, the page cache and the OOM killer”.
