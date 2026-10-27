+++
date = '2027-03-30T10:00:00+03:30'
draft = false
title = 'Topological sort and dependencies'
description = 'Topological sort in Go with Kahn and DFS: stable order, exact cycle paths, parallel waves, critical path and go list -deps, with operation counts.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "topological-sort", "dependencies", "go"]
cover = { image = "/images/covers/algo-topological-sort.png", alt = "Topological sort and dependencies", hiddenInSingle = true }
+++

In the previous post, [Shortest paths and Dijkstra](/posts/algo-shortest-paths-dijkstra/), edges carried a cost. Here they carry an order: "build `log` before `db`". Builds, imports and task runners all need this, and the tools are the [graph traversals](/posts/algo-graphs-bfs-dfs/) and a [queue](/posts/algo-stacks-queues-deques/) you already know.

> Go 1.26, local example, tests with `go test -race`. The load average was above 4, so I publish only counts, no timings.

## Why it must be a DAG

An edge `u -> v` means u comes before v. A {{< term "topological-sort" "topological order" >}} lists every vertex so all edges point forward. That is possible only for a {{< term "dag" "DAG" >}}: with `a -> b -> c -> a` each one must precede the next, so no order exists. My example is a small service start-up, with edges such as `log -> config`, `config -> db`, `store -> api`, ten in total.

## Kahn: the in-degree queue

The {{< term "in-degree" "in-degree" >}} of a vertex is how many prerequisites it still waits for. Put every vertex with in-degree 0 in a {{< term "queue" "queue" >}}. Pop one, output it, decrement its successors, and enqueue those that reach 0. If fewer than V vertices come out, there was a cycle.

## DFS: reverse postorder

With {{< term "dfs" "DFS" >}}, add a vertex to a list when all its successors are finished, then reverse the list. Both algorithms on the same graph:

```
kahn  : [log metrics config db http store api main] {8 20}
dfs   : [metrics log config http db store api main] {8 10}
```

Both orders are valid, and they differ. The pair is `{Visits, EdgeChecks}`: 8 vertices each. My Kahn counter counts each edge twice (once to compute in-degrees, once when relaxing), so 20 = 2E; DFS looks at each edge once, 10 = E. Both are O(V+E).

## A stable order

Order is not unique, which is annoying for reproducible builds. Replace the queue with a {{< term "binary-heap" "min-heap" >}} of names, so the smallest ready name goes first:

```
stable: [log config db http metrics store api main]
```

Same input, same output every run, regardless of map order.

## Cycles with the exact path

Three colours: white (unseen), grey (on the current DFS stack), black (done). An edge to a grey vertex closes a cycle, and the stack holds its path. I fed it `app -> lib -> util -> codec -> lib`:

```
error: cycle: lib -> util -> codec -> lib
kahn on cyclic: true
```

Kahn only knows that something is stuck (the last line is `o == nil`); DFS can name the loop. Note that `app` is not part of it.

## A property test

The test builds 300 random DAGs (seeds 0 to 299, 2 to 41 vertices) by only allowing edges from an earlier to a later vertex of a hidden order. For Kahn, DFS and the stable variant it checks that every edge `u -> v` has `pos[u] < pos[v]`, that all vertices appear, and that the counters are exactly V, 2E and so on. A second test checks the cycle message. Both pass with `-race`. It is a {{< term "property-based-testing" "property-style" >}} check: it does not know the right order, only the rule any order must obey.

## Waves and the critical path

Process vertices in topological order and set `depth[v] = max(depth[u] + 1)` over its prerequisites. Vertices with the same depth do not depend on each other, so they can run in parallel:

```
  0 [log metrics]
  1 [config]
  2 [db http]
  3 [store]
  4 [api]
  5 [main]
critical path length: 6
```

With unlimited workers the build takes 6 steps, because `log -> config -> db -> store -> api -> main` is a chain. That chain is the {{< term "critical-path" "critical path" >}}. Speeding up `metrics` changes nothing; speeding up `db` does. This counts tasks, not their durations; with durations you would sum weights along the path instead.

## A real tool: go list -deps

I made a tiny module `tiny` where `a` imports `b` and `c`, and `b` imports `c`. Then I ran `go list -deps .`:

```
tiny/c
tiny/b
tiny/a
internal/goarch
...
tiny
```

(I cut the standard library lines.) Each package appears after everything it imports, and `tiny` itself is last. That is a topological order, and the Go toolchain needs one to compile. I only checked this tiny case by eye, not the whole standard library.

## A few things to watch

- The order is not unique; if you need repeatability, add a tie-break.
- Check for cycles and report the path, not just "failed".
- Edge direction matters: decide whether `u -> v` means "u before v" or "u needs v".
- Waves assume unlimited workers.

## Exercise

Add task durations to `Waves` and compute the earliest finish time per task and the weighted critical path. Then change `KahnStable` to prefer the longest remaining chain first.

## What's next

Some problems have overlapping subproblems that a graph order can't help with. The next post is "Dynamic programming 1: the idea and memoization".
