+++
date = '2027-04-26T10:00:00+03:30'
draft = false
title = 'cgroups and namespaces: the base of containers'
seoTitle = 'cgroups and namespaces: how containers work'
description = 'Linux cgroups and namespaces explained from the man pages: how a container is a restricted process, plus two Go programs I only cross-compiled.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "cgroups", "namespaces", "containers", "go", "macos"]
cover = { image = "/images/covers/linux-cgroups-namespaces.png", alt = "cgroups and namespaces: the base of containers", hiddenInSingle = true }
+++

Picture a service in a container that was given 2 CPUs and 512 MB. Inside it, `nproc` can still print 64, because that is what the host has. The service sizes its worker pool from that number, starts too many workers, and a few minutes later something kills it with no error message at all. Nothing is wrong with the program. It just does not know what kind of box it is living in.

To understand why, we need to answer a plainer question: what is a container, really? The Linux kernel has no "container" object. A container is an ordinary process that the kernel treats in two special ways. One decides what the process can **see**, the other decides how much it can **use**. This post takes those two features one at a time, then shows two small Go programs that use them. It builds on [systemd: units and timers](/posts/linux-systemd-units-timers/), where we saw a service as just a process that something else starts and watches.

> Honest disclaimer: this Mac has no Linux kernel and no virtual machine, and I kept the Docker daemon off. As far as I know, Docker Desktop on a Mac runs containers inside a Linux virtual machine, which is one more reason I could run nothing here. So the facts below come from the man pages and the kernel documentation, and I say so each time. The Go programs I only compiled for Linux, **I never ran them**. The earlier [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/) also admitted that it did no real Docker build.

## Two questions, two features

Think of a hotel room. The walls decide what you can see and reach: you cannot see into the next room, and the corridor looks different from inside. The electricity and water meters decide how much you can use before someone steps in. Walls and meters are separate things, and a container needs both.

- A {{< term "namespace" "namespace" >}} is the walls. It gives a process its own private view of one kind of system resource, for example its own list of processes, its own hostname or its own network interfaces. The resource is still the host's. The process just cannot see the rest.
- A {{< term "cgroup" "cgroup" >}} (short for **control group**) is the meters. It puts processes into a group and limits or counts what the group uses: CPU time, memory, number of processes.

Add a separate root filesystem (the files the process sees as `/`) and you have what everybody calls a {{< term "container" "container" >}}. Neither feature alone is enough. A namespace-only process sees a small world but can still eat all the memory of the host. A cgroup-only process is limited but can see every other process on the machine.

## Namespaces: what the process can see

There are several kinds of namespace, one for each kind of resource. According to namespaces(7), these are the types:

| What it isolates | Flag | What you would notice (illustrative, not captured) |
|---|---|---|
| Hostname | `CLONE_NEWUTS` | `hostname` inside shows a different name |
| Process IDs | `CLONE_NEWPID` | the first process sees itself as PID 1 |
| Mount points | `CLONE_NEWNS` | its mounts do not change the host |
| Network | `CLONE_NEWNET` | its own interfaces and ports |
| IPC | `CLONE_NEWIPC` | its own System V IPC objects |
| User and group IDs | `CLONE_NEWUSER` | root inside, unprivileged outside |
| Cgroup root | `CLONE_NEWCGROUP` | it sees a different cgroup as the root |
| Clocks | `CLONE_NEWTIME` | its own boot and monotonic clocks |

The last column is what the man page leads us to expect. I did not capture any of it.

A small example makes the PID row concrete. On the host, your shell may be process 4102. If you start a new shell in a new PID namespace, that shell sees itself as process 1, and it sees only its own children. The host still sees it as 4102. It is the same process with two numbers, one per view.

A process enters a namespace in one of three ways: `clone(2)` creates a new process in new namespaces, `unshare(2)` moves the calling process into new ones, and `setns(2)` joins a namespace that already exists. On the command line the matching tools are `unshare(1)` and `nsenter(1)`.

You can also see namespaces from outside. Every process has links in `/proc/<pid>/ns/`, and two processes that share a namespace show the same identifier there, something like `uts:[...]`. Comparing those identifiers is the simplest way to answer "are these two processes in the same namespace?".

One more documented detail matters a lot. Creating most namespaces needs the `CAP_SYS_ADMIN` capability, but the man page says a **user namespace** needs no privilege at all (since Linux 3.8). Inside it you can be root, while outside you are still an ordinary user. That is the documented basis of rootless containers. Some distributions restrict this by default, so it may not work everywhere.

## cgroups: how much the process can use

Namespaces only hide things. To actually stop a process from using too much, we need cgroups. According to the kernel docs, cgroup v2 is a single tree, normally mounted at `/sys/fs/cgroup`, and a group is simply a directory in it. You control the group by reading and writing files inside that directory:

| Goal | File | What you would notice (illustrative, not captured) |
|---|---|---|
| Move a process in | `cgroup.procs` (write a PID) | the PID appears in the file |
| Cap memory | `memory.max` | the OOM killer acts at the cap |
| Cap process count | `pids.max` | `fork` fails beyond it |
| Cap CPU | `cpu.max` (`$MAX $PERIOD`) | at most MAX of CPU time per PERIOD |
| Count OOM kills | `memory.events`, field `oom_kill` | the counter grows |

Back to our opening problem. `cpu.max` holds two numbers: how much CPU time the group may use, and over what period. According to the docs, a value like `200000 100000` means "up to 200000 microseconds in every 100000", which is two CPUs' worth. Notice what this is: a time budget. It does not remove any CPU from the process's view, which is why the program in the opening can still see 64. A program that wants to size itself correctly has to read this file, or use a runtime that does.

The memory limit works differently. The docs say that when the group reaches `memory.max` and the kernel cannot reduce the usage, the {{< term "oom-killer" "OOM killer" >}} is invoked inside that cgroup. In plain words, the process does not get a polite "out of memory" error. The kernel picks a victim and kills it. That is the silent death from the opening. We look at how memory is counted, and who gets picked, in the next post.

One more rule from the docs: a controller (the part of the kernel that manages one resource, like `memory`) must be switched on for children in the parent's `cgroup.subtree_control` before the child directory can use it.

## Two programs, compiled but never run

To connect the two features to real code, I wrote one small Go module with two modes. The first, `ns`, starts a command inside new namespaces. The second, `cg`, starts a command inside a new cgroup with limits. Both check first that they run as root, and `cg` also checks that cgroup v2 is mounted.

The core of the `ns` mode is a single field of `SysProcAttr`, which tells Go to pass these flags to `clone(2)` when it starts the child:

```go
//go:build linux
cmd.SysProcAttr = &syscall.SysProcAttr{
	Cloneflags: syscall.CLONE_NEWUTS | syscall.CLONE_NEWPID | syscall.CLONE_NEWNS,
}
```

That gives the child its own hostname, its own process numbering and its own mount table. This is the classic demo of what a container does at its core.

The `cg` mode does these steps in order:

1. It creates the directory `/sys/fs/cgroup/blogdemo`. That is the new group.
2. It writes `+memory +pids` into the parent's `cgroup.subtree_control`, so the child group is allowed to use those two controllers.
3. It writes `67108864` (64 MiB) into `memory.max` and `32` into `pids.max`.
4. It starts the command, then writes the command's PID into `cgroup.procs`, which moves it into the group.

There is a weakness in step 4, and I want to be upfront about it: the child is already running for a short moment before it joins the cgroup, so it is briefly unlimited. A careful runtime closes that gap. This demo does not.

The `//go:build linux` line is a {{< term "build-tag" "build tag" >}}: it tells Go to compile that file only for Linux. A second file with the opposite tag provides a stub for every other system, which is how the module still builds on this Mac, the same trick as in [/proc and observing the system](/posts/linux-proc-observability/).

Here is exactly what I did. I cross-compiled for Linux (`go vet` for `linux/arm64`, `go build` for `linux/amd64`) and both passed. That only proves the code is valid Go that type-checks against the Linux system-call API. **I never ran the binary.** On the Mac, `go run . ns /bin/sh` uses the stub and prints:

```
Linux only: namespaces and cgroups do not exist on this OS
```

That line is the whole output. It proves the stub is selected on macOS and nothing else.

## What a container runtime adds

What follows is from documentation and my understanding, not from a run. A container image is a stack of read-only layers, commonly combined with {{< term "overlayfs" "overlayfs" >}}, and the runtime switches the process to that combined filesystem as its root with `pivot_root`. Tools such as Docker, containerd and runc add images, layers and a configuration on top of the two kernel features above; as I understand it, the OCI runtime specification defines that configuration, and flags like Docker's `--memory` end up as cgroup settings. I did not run any of them.

## Where the picture breaks

- **A container is not a virtual machine.** It shares the host's kernel, so a kernel bug or a mistake in the isolation affects the host too.
- **Namespaces hide, cgroups limit.** Using only one leaves a gap: either the process can use everything, or it can see everything.
- **Both programs need root on Linux.** If you try them, use a throwaway machine, not your laptop or a server you care about.
- **Hitting `memory.max` ends in an OOM kill inside the group**, not a polite error the program can handle. Treat the limit as a hard wall when you size a service.
- **A CPU limit does not change what the program sees.** A runtime that reads the host's CPU count will still size itself for the host. Check that the runtime or library you use understands cgroup limits.

## Exercise

On a disposable Linux machine, read `unshare(1)` and run `unshare --uts --pid --fork --mount-proc /bin/sh`. Before and after, compare the output of `readlink /proc/self/ns/uts`: if the man pages are right, the identifier differs inside. Then try the `cg` mode and read `memory.events` afterwards.

## What's next

The next post is "Memory, the page cache and the OOM killer". We just saw that reaching `memory.max` ends in an OOM kill, and it explains what counts toward that limit and how the kernel picks the victim.
