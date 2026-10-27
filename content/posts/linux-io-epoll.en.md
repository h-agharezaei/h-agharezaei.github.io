+++
date = '2027-05-09T10:00:00+03:30'
draft = false
title = 'I/O and epoll'
description = 'Linux I/O and epoll from the man pages: blocking vs non-blocking, select, poll, epoll, level vs edge triggering, and real kqueue demos on macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "epoll", "kqueue", "io", "go", "macos"]
cover = { image = "/images/covers/linux-io-epoll.png", alt = "I/O and epoll", hiddenInSingle = true }
+++

I wrote this on a Mac, where the equivalent is {{< term "kqueue" "kqueue" >}}; epoll itself did not run here. This is the eighth post of the Linux series, after [Memory, the page cache and the OOM killer](/posts/linux-memory-page-cache-oom/). The question: how can one thread serve thousands of connections? Facts about epoll come from the man pages (epoll(7), select(2)); everything marked "ran" was run on macOS with Go and Python, on loopback only.

## Blocking and non-blocking

By default `read` on a {{< term "socket" "socket" >}} blocks the calling {{< term "thread" "thread" >}} until data arrives. That is simple, but one slow client then costs one thread. With `O_NONBLOCK` (see fcntl(2)), calls return at once with `EAGAIN` when there is nothing to do. {{< term "non-blocking-io" "Non-blocking I/O" >}} alone would force you to retry in a busy loop; you need something that says when to try.

## select, poll, epoll

According to select(2), `select` works on bitmaps limited by `FD_SETSIZE` (1024), and you pass the whole set on each call. `poll` removes that limit but still passes an array of every descriptor on every call, which the kernel scans. This is the "C10K" problem: ten thousand connections made that cost visible.

epoll(7) splits the work. An interest list is built once with `epoll_ctl`, and `epoll_wait` returns items from a ready list the kernel fills as events happen. So the cost follows the number of ready {{< term "file-descriptor" "descriptors" >}}, not registered ones. I did not benchmark this.

| API | Per-call input | Limit |
|---|---|---|
| `select` | bitmaps of all fds | `FD_SETSIZE` |
| `poll` | array of all fds | none by design |
| {{< term "epoll" "epoll" >}} | nothing after registration | memory |

## Level or edge

{{< term "edge-level-triggered" "Level-triggered" >}} reports a descriptor ready on every wait while unread data remains. Edge-triggered reports it once per change; epoll(7) says you then read until `EAGAIN`. kqueue has the same idea: `EV_CLEAR` resets the state after retrieval, per `man kqueue`. I ran it on a Unix socketpair: write 10 bytes, call `kevent` three times without reading, read 4 bytes, then write one more:

```
level-like (EV_ADD): poll1=1 poll2=1 poll3=1 | after partial read: 1 | after new write: 1
edge-like  (EV_ADD|EV_CLEAR): poll1=1 poll2=0 poll3=0 | after partial read: 0 | after new write: 1
```

With the default the unread data keeps being reported, even after a partial read. With `EV_CLEAR` I got one event and then silence until new data arrived. Forget to drain an edge-triggered descriptor and it stalls.

## An event loop that ran

The Go demo is a single-threaded echo server: a listening socket and the accepted sockets, all non-blocking, all in one kqueue. Three clients connect, send a line and get it back. Output (counts only):

```
accepts=3 reads=3 eofs=3 goroutines_in_server_loop=1
```

The same shape in Python with `selectors.DefaultSelector`:

```
KqueueSelector
accepts=3 reads=3
```

On macOS the default is `KqueueSelector`. According to the docs it picks the most efficient implementation available, so on Linux I expect `EpollSelector`; I did not see that.

## Threads, goroutines and the netpoller

I opened 1000 idle loopback connections two ways and counted. With a goroutine per connection (`net` package), and with one kqueue loop:

```
goroutines connections=1000 goroutines=1002 os_threads_created=7
kqueue     connections=1000 goroutines=1 os_threads_created=5
```

1002 goroutines but only two more OS threads, because the Go runtime parks a goroutine on a network wait and polls with the platform API. In the Go tree, `runtime/netpoll_epoll.go` has `//go:build linux` and `netpoll_kqueue.go` covers darwin and the BSDs (I checked with `ls` and `head`). That is how [the Go scheduler](/posts/go-scheduler-gc-internals/) gives you blocking-style code on an event loop. {{< term "libuv" "libuv" >}} does the same for Node, per its docs using epoll on Linux and kqueue on macOS; see [the Node.js event loop](/posts/node-event-loop/). The counts are not timings; the machine was busy.

## epoll in code, never run

I wrote the epoll version with the `syscall` package behind `//go:build linux`: `EpollCreate1`, `EpollCtl`, `EpollWait`, `Accept4`. It was only checked with `GOOS=linux GOARCH=arm64 go vet . && go build`, and **never run**.

## Many waiters

If several processes wait on one listening socket, one connection may wake them all and only one wins: the {{< term "thundering-herd" "thundering herd" >}}. The epoll(7) page mentions `EPOLLEXCLUSIVE` for this, and `EPOLLONESHOT` to disarm a descriptor after one event; I did not test either.

## A few things to watch

- Not a Linux result: all output here is kqueue.
- A readiness API tells you to try, not that the call will succeed; handle `EAGAIN`.
- Edge-triggered needs non-blocking descriptors and draining to `EAGAIN`.
- One slow handler blocks the whole loop.

## Exercise

On a throwaway Linux box, port the kqueue demo to `epoll`, then run `strace -c` on it with 3 clients (not run by me).

## What's next

The next post is “Linux networking: ip, ss and nftables”.
