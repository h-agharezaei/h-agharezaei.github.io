+++
date = '2027-03-30T10:00:00+03:30'
draft = false
title = 'Topological sort and dependencies'
description = 'Topological sort in Go with Kahn and DFS: stable order, exact cycle paths, parallel waves, critical path and go list -deps, with operation counts.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "topological-sort", "dependencies", "go"]
cover = { image = "/images/covers/algo-topological-sort.png", alt = "Topological sort and dependencies", hiddenInSingle = true }
+++

When you get dressed in the morning, there is an order you never think about but always follow: socks before shoes, trousers before belt, shirt before jacket. Some things have no order between them (socks and watch), and some do. Programs are full of the same thing. `go list -deps` prints each package after the packages it imports, because compiling needs exactly that order. A build system or a job runner needs it too: "build `log` before `db`".

In the [previous post](/posts/algo-shortest-paths-dijkstra/) the edges of the graph had costs. Here the edges give order: `u -> v` means "u must come before v". The tools are the same [graph traversal](/posts/algo-graphs-bfs-dfs/) and a [queue](/posts/algo-stacks-queues-deques/) you already know. In this post we look at two algorithms that find such an order, then at how to find and report cycles (which make an order impossible), and finally at how to use the same order to split the work into parallel steps.

> I re-ran every output with Go 1.27. It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish no timings; you will only see counts, which are the same on every run.

## What is a topological order?

Suppose we have three tasks: `a` before `b`, and `b` before `c`. Only one order is correct: `a, b, c`. Now suppose `a` comes before `b` and `a` comes before `c`, and there is no relation between `b` and `c`. Both `a, b, c` and `a, c, b` are correct. So the order is not necessarily unique.

A {{< term "topological-sort" "topological order" >}} puts all the vertices of a directed graph in a list so that every edge `u -> v` points forward in the list, meaning u comes before v. It is not always possible, though. If we have `a -> b -> c -> a`, each must come before the next and it never ends: no order exists. A topological order exists only for a graph with no cycle; such a graph is called a {{< term "dag" "DAG" >}} (directed acyclic graph).

Our example is starting a small service. Each edge says "this must come up before that":

```
log -> config    log -> db       log -> http
config -> db     config -> http
db -> store      store -> api    http -> api
metrics -> api   api -> main
```

Eight vertices (`log config db http store api main metrics`) and ten edges.

## Kahn's algorithm: whatever has no prerequisite can go

The first idea is very natural. What can we do right now? A task that has no unfinished prerequisite. We do it, cross it off from the prerequisites of the others, and ask again which task has become free.

To count "prerequisites left" we give every vertex a number: its {{< term "in-degree" "in-degree" >}}, the number of edges coming into it. The algorithm:

1. Compute the in-degree of every vertex.
2. Put the vertices with in-degree 0 into a {{< term "queue" "queue" >}}.
3. While the queue is not empty: take the first vertex and write it to the output. For each of its outgoing edges, decrease the target's in-degree by one; if it reaches 0, add the target to the queue.
4. If the output has fewer than V vertices at the end, some vertices never reached in-degree 0: there is a cycle.

On our example the in-degrees are: `log` 0, `metrics` 0, `config` 1, `db` 2, `http` 2, `store` 1, `api` 3, `main` 1. The queue starts as `[log, metrics]`.

| taken | what became free | queue afterwards | output so far |
|---|---|---|---|
| log | config (now 0); db and http still have one prerequisite | [metrics, config] | log |
| metrics | (api still has two prerequisites) | [config] | log metrics |
| config | db and http both became 0 | [db, http] | log metrics config |
| db | store | [http, store] | log metrics config db |
| http | (api still needs store) | [store] | log metrics config db http |
| store | api | [api] | log metrics config db http store |
| api | main | [main] | log metrics config db http store api |
| main | | [] | log metrics config db http store api main |

The output is `log metrics config db http store api main`. Every prerequisite came before the thing that depends on it.

## DFS: the last to finish goes first

The second idea looks at the problem from the opposite end. Take the simple example `a -> b -> c`. If we start a {{< term "dfs" "DFS" >}} at `a`, we reach `c` first and it finishes (it has nowhere to go), then `b`, then `a`. The finishing order is `c, b, a`. A vertex only finishes when everything that depends on it has finished. So if we reverse this order, we get `a, b, c`, which is the right order.

The algorithm: run DFS from every unseen vertex, append each vertex to a list when it finishes (after all its successors), and reverse the list at the end. That list is called the "reverse postorder".

The demo runs both algorithms on this graph:

```
kahn  : [log metrics config db http store api main] {8 20}
dfs   : [metrics log config http db store api main] {8 10}
```

The Kahn line is the one we got by hand. Both orders are valid but they differ: for example DFS put `http` before `db`, which is fine because there is no edge between them. The pairs `{8 20}` and `{8 10}` are the counters `{Visits, EdgeChecks}`: each algorithm saw 8 vertices. In my code Kahn's counter counts every edge twice, once while computing in-degrees and once while decrementing them, so 20 = 2E. DFS sees each edge once, so 10 = E. Both are O(V+E).

## When the order must always be the same

We saw that the order is not unique. But for a reproducible build or a test, getting a different order each time is annoying. The fix is to have a fixed rule for when several vertices are ready at once. In Kahn's algorithm we replace the queue with a {{< term "binary-heap" "min-heap" >}} of names, so that among the ready tasks the smallest name (alphabetically) goes first:

```
stable: [log config db http metrics store api main]
```

Here `metrics` waits until the last moment, because `config`, `db` and `http` are alphabetically smaller and went first whenever they were ready. The same input always gives the same output, independent of insertion order or map iteration order.

## Cycles: do not just fail, show the cycle

If the input has a cycle, the message "no order exists" is not helpful; the user wants to know which tasks go around in a circle. Kahn only learns that it got stuck (fewer than V vertices came out). DFS can name the cycle itself. It uses the same three colors as in the previous post: white (unseen), grey (on the current DFS path) and black (finished). If an edge reaches a grey vertex, a cycle has closed, and the current DFS path (which I keep in a stack) holds exactly the cycle. The input: `app -> lib -> util -> codec -> lib`.

```
error: cycle: lib -> util -> codec -> lib
kahn on cyclic: true
```

The first line is the DFS message: `app` is not in the cycle, it only leads into it, and the message shows exactly the three vertices of the cycle. The second line says Kahn returned `nil` on this input (`o == nil`); it knows there is no order but not which vertices are to blame.

## How do we know it is right?

We cannot know the correct order in advance (it is not unique), but there is a rule every correct order must follow: for every edge `u -> v`, u's position in the list is smaller than v's. A test builds 300 random DAGs (2 to 41 vertices) by choosing a hidden random order and only adding edges from earlier to later vertices (so no cycle can appear). For Kahn, DFS and the stable version it checks that the rule holds for every edge and that all vertices are present, and that Kahn's counters are exactly V and 2E. A second test checks the cycle message. This check is {{< term "property-based-testing" "property-based" >}} in style: it does not know the right answer, only the rule that every right answer must obey.

## Waves and the critical path

A topological order gives us something else too. Suppose every task takes one unit of time and you have as many workers as you like. Which tasks can run at the same time? We process the vertices in topological order and set `depth[v] = max(depth[u] + 1)` over its prerequisites, which is the longest chain leading to it. Vertices at the same depth do not depend on each other and can run in parallel:

```
  0 [log metrics]
  1 [config]
  2 [db http]
  3 [store]
  4 [api]
  5 [main]
critical path length: 6
```

Each line is a "wave". In wave 0 both `log` and `metrics` can start; in wave 2 both `db` and `http`. With unlimited workers the whole build finishes in 6 steps, because `log -> config -> db -> store -> api -> main` is a chain of six vertices and none of its links can be run in parallel. That longest chain is the {{< term "critical-path" "critical path" >}}. Making `metrics` faster changes nothing, because it is not on the critical path; making `db` faster does. Note that this counts tasks, not durations; for real durations you would add up each task's duration instead of 1.

## A real tool: go list -deps

To see that Go does the same thing, I made a tiny module called `tiny`: package `a` imports `b` and `c`, and `b` also imports `c`. Then I ran `go list -deps .`:

```
tiny/c
tiny/b
tiny/a
internal/goarch
...
tiny
```

(I removed the rest of the standard library packages that `main` needs to run; the full output was 32 lines.) `tiny/c` is first because it imports nothing, then `tiny/b`, which needs `c`, then `tiny/a`, which needs both, and `tiny`, which imports `a`, is last. According to `go help list`, `-deps` visits packages in a depth-first post-order traversal so that a package is listed only after all its dependencies; that is the DFS algorithm above. Because the edges here mean "imports", we do not need to reverse the list. I only checked this one small case by eye, not the whole standard library.

## Traps when ordering

- **The order is not unique.** If your output must always be the same, as the input of a build or a test, add a fixed tie-break (such as sorting by name).
- **Do not report a cycle as just "failed".** Give the user the exact path of the cycle; finding it with DFS is cheap.
- **Define the edge direction at the start.** Does `u -> v` mean "u before v" or "u needs v"? These are opposites, and mixing the conventions gives you a reversed order.
- **Waves assume unlimited workers.** With a limited number of workers, the real schedule takes longer.

## Exercise

Add durations to `Waves` and compute each task's earliest finish time and the weighted critical path. Then change `KahnStable` so that among the ready tasks it takes the one with the longest remaining chain first.

## What's next

"Dynamic programming 1: the idea and memoization". Until now every problem was a graph we could walk. The next problems do not look like graphs, and their trouble is different: the same subproblems get solved over and over.
