+++
date = '2027-05-09T10:00:00+03:30'
draft = false
title = 'I/O and epoll'
description = 'Linux I/O and epoll from the man pages: blocking vs non-blocking, select, poll, epoll, level vs edge triggering, and real kqueue demos on macOS.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "epoll", "kqueue", "io", "go", "macos"]
cover = { image = "/images/covers/linux-io-epoll.png", alt = "I/O and epoll", hiddenInSingle = true }
+++

A chat server has 10,000 clients connected. Almost all of them are silent at any moment, and a few send a message every few seconds. If the server starts one thread for each client, it holds 10,000 threads that mostly sleep, and each thread costs memory. Is there a way for one thread to look after all of them? There is, and it is what Go's network poller, Node's event loop and most modern servers do underneath.

This post shows how: first the problem with plain blocking calls, then the three generations of Linux APIs for "tell me which connection has something to read" (`select`, `poll`, `epoll`), and then the one subtle difference you must know before using epoll, level versus edge triggering. It follows [Memory, the page cache and the OOM killer](/posts/linux-memory-page-cache-oom/): a thread per client is exactly how a server spends memory it did not need to.

One thing must be clear from the start. epoll exists only on Linux, and this machine is a Mac, where the equivalent is {{< term "kqueue" "kqueue" >}}. So everything about epoll below comes from the man pages (epoll(7), select(2)). Everything marked "ran" was run on macOS with Go and Python, on loopback only, and it shows kqueue, not epoll.

## Blocking and non-blocking

By default, `read` on a {{< term "socket" "socket" >}} blocks: the calling {{< term "thread" "thread" >}} sleeps until data arrives. That is simple, but it means one waiting client holds one thread.

The alternative is to mark the descriptor non-blocking (`O_NONBLOCK`, see fcntl(2)). Now `read` never sleeps. If there is nothing to read it returns at once with the error `EAGAIN`, which means "not now, try again later". That is {{< term "non-blocking-io" "non-blocking I/O" >}}. On its own it is not enough, though. If you call `read` on 10,000 sockets in a loop, you burn a CPU core asking "anything yet?" thousands of times. What you need is one call that sleeps until at least one socket is ready, and tells you which. That is what the next three APIs do.

## select, poll, epoll

Think of a waiter with 10,000 tables. `select` and `poll` are a waiter who walks to every table and asks "do you need anything?" each time. `epoll` is a waiter who stands at the counter while the tables ring a bell, and only goes to tables that rang.

In more exact terms. According to select(2), `select` works on bitmaps (one bit per descriptor) that are limited by `FD_SETSIZE`, which is 1024, and you pass the whole set again on every call. `poll` removes that limit, but it still takes an array of every descriptor on every call, and the kernel scans all of them each time. With a few hundred connections this is fine. With ten thousand the scan itself becomes the cost, a problem known as "C10K".

epoll(7) splits the work in two. You build a list of interest once, with `epoll_ctl`: "tell me about this descriptor". Then `epoll_wait` sleeps and returns only items from a ready list that the kernel fills as events happen. So the cost follows the number of {{< term "file-descriptor" "descriptors" >}} that are ready, not the number you registered. I did not benchmark this; it is the documented design.

| API | What you pass on each call | Limit |
|---|---|---|
| `select` | bitmaps of all descriptors | `FD_SETSIZE` |
| `poll` | an array of all descriptors | none by design |
| {{< term "epoll" "epoll" >}} | nothing after registration | memory |

## Level or edge

epoll can report readiness in two ways, and mixing them up causes real bugs.

- {{< term "edge-level-triggered" "Level-triggered" >}} (the default) means "this descriptor is ready" is reported on every wait, for as long as unread data remains. If you read only part of the data, the next wait reports it again.
- Edge-triggered means it is reported once, when the state changes, for example when new data arrives. epoll(7) says that with edge triggering you must read until you get `EAGAIN`, because nothing reminds you of the data you left behind.

kqueue has the same idea in different words: `EV_CLEAR` resets the state after the event is retrieved, per `man kqueue`. It is close to epoll's edge triggering, but I would not claim that the two behave identically in every detail.

I ran this on macOS with a Unix socketpair, which is a pair of connected sockets in one process. The program writes 10 bytes, calls `kevent` three times without reading, reads only 4 bytes, and finally writes one more byte. Each number is how many events `kevent` returned at that point:

```
level-like (EV_ADD): poll1=1 poll2=1 poll3=1 | after partial read: 1 | after new write: 1
edge-like  (EV_ADD|EV_CLEAR): poll1=1 poll2=0 poll3=0 | after partial read: 0 | after new write: 1
```

On the first line (the default) the unread data keeps being reported: three polls give 1 each, and after the partial read, 6 bytes are still waiting, so it reports 1 again. On the second line (`EV_CLEAR`) the first poll gives 1 and then there is silence. Even after the partial read, the 6 bytes left behind are not reported. Only when the new byte arrives does it say 1 again. That silence is the danger: if you forget to drain an edge-triggered descriptor, the connection looks dead while data sits in it.

## An event loop that ran

Now the original question. The Go demo is a single-threaded echo server. The listening socket and every accepted socket are non-blocking, and all are registered in one kqueue. The loop calls `kevent`, and for each ready descriptor either accepts a new client or reads and writes the data back. Three clients connect, send a line and get it back. The program prints counts:

```
accepts=3 reads=3 eofs=3 goroutines_in_server_loop=1
```

Three accepts, three reads, three end-of-file events when the clients closed, all handled by one loop.

The same shape in Python, with `selectors.DefaultSelector`:

```
KqueueSelector
accepts=3 reads=3
```

The first line is the name of the class Python picked. On macOS that is `KqueueSelector`. According to the docs, `DefaultSelector` picks the most efficient implementation available, so on Linux I would expect `EpollSelector`, but I did not see that.

## Threads, goroutines and the netpoller

To see the cost of "a thread per client" more directly, I opened 1000 idle loopback connections in two ways and counted. In the first, the `net` package serves each connection in its own goroutine. In the second, one kqueue loop serves them all. `os_threads_created` is the number of operating system threads the Go runtime had created by then. This is one run (the original run on this Mac printed 7 and 5, so the numbers move a little from run to run):

```
goroutines connections=1000 goroutines=1002 os_threads_created=6
kqueue     connections=1000 goroutines=1 os_threads_created=5
```

The first line has 1002 goroutines but only one more OS thread than the second. A goroutine is not an OS thread: when it waits on the network, the Go runtime parks it and checks readiness with the platform's API. In the Go source tree, `runtime/netpoll_epoll.go` carries `//go:build linux`, and `netpoll_kqueue.go` covers darwin and the BSDs (I checked the files here). That is how [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/) gives you code that looks blocking, on top of an event loop. {{< term "libuv" "libuv" >}} does the same for Node, using epoll on Linux and kqueue on macOS according to its docs; see [The Node.js event loop](/posts/node-event-loop/). The numbers are counts, not timings, and the machine was busy.

## epoll in code, never run

The same echo server with epoll is in the demo too, using the `syscall` package behind `//go:build linux`: `EpollCreate1` creates the epoll instance, `EpollCtl` registers a descriptor, `EpollWait` waits, and `Accept4` accepts a connection that is already non-blocking. I only cross-compiled it (`GOOS=linux go vet` and `go build`), and **never ran it**. It also ignores most errors, so treat it as a sketch, not a model.

## Many waiters

If several processes wait on the same listening socket, one new connection may wake all of them while only one gets it. This is the {{< term "thundering-herd" "thundering herd" >}}. The epoll(7) page mentions `EPOLLEXCLUSIVE` for this problem, and `EPOLLONESHOT` to disarm a descriptor after one event. I tested neither.

## Where event loops break

- **None of the output here is Linux output.** It all comes from kqueue on macOS. The shape of the API is the same idea, not the same calls.
- **"Ready" means "try now", not "this will succeed".** Always handle `EAGAIN`, because another thread or process may have taken the data first.
- **Edge-triggered needs non-blocking descriptors and draining to `EAGAIN`.** Otherwise you can stall exactly as the second line above shows.
- **One slow handler blocks the whole loop.** With one thread, a handler that computes for a second delays every other connection by a second.

## Exercise

On a throwaway Linux machine, port the kqueue demo to `epoll`, using `EPOLLET` for the edge-triggered part. Then run `strace -c` on it with 3 clients and see which system calls dominate. I have not run this myself.

## What's next

The next post is "Linux networking: ip, ss and nftables". Those sockets live in the kernel, and that post shows how to list them, inspect the interfaces under them and filter their traffic.
