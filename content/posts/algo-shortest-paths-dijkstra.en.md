+++
date = '2027-03-21T10:00:00+03:30'
draft = false
title = 'Shortest paths and Dijkstra'
description = 'Dijkstra in Go with container/heap: lazy deletion vs heap.Fix, why negative edges break it, Bellman-Ford, Floyd-Warshall, and A* on a grid, with counts.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "dijkstra", "shortest-path", "go"]
cover = { image = "/images/covers/algo-shortest-paths-dijkstra.png", alt = "Shortest paths and Dijkstra", hiddenInSingle = true }
+++

In the previous post, [Graphs: BFS and DFS](/posts/algo-graphs-bfs-dfs/), {{< term "bfs" "BFS" >}} found shortest paths by counting edges. That works only when every edge costs the same. Roads, network links and prices have weights, and then the route with fewest edges is not the cheapest. The fix needs a [priority queue](/posts/algo-heaps-priority-queues/), the {{< term "binary-heap" "heap" >}} from earlier, to always take the closest unfinished vertex next.

> Go 1.26, local example, tests with `go test -race`. The load average was above 3 when I ran it, so I publish only counts, no timings.

## Dijkstra on a small graph

{{< term "dijkstra" "Dijkstra's algorithm" >}} keeps a tentative distance for every vertex. It pops the smallest one, then tries every edge out of it: if `dist[u] + w` beats `dist[v]`, we found a better route and update it. That update is called {{< term "relaxation" "relaxation" >}}. With `container/heap` the core is short:

```go
h := &minHeap{{src, 0}}
for h.Len() > 0 {
	it := heap.Pop(h).(item)
	if it.d > dist[it.v] { continue } // stale entry
	for _, e := range g.Adj[it.v] {
		if nd := it.d + e.W; nd < dist[e.To] {
			dist[e.To], parent[e.To] = nd, it.v
			heap.Push(h, item{e.To, nd})
		}
	}
}
```

I used six vertices and these undirected edges:

```
A-B:7 A-C:9 A-F:14 B-C:10 B-D:15 C-D:11 C-F:2 D-E:6 E-F:9
A dist= 0 path=A
B dist= 7 path=A>B
C dist= 9 path=A>C
D dist=20 path=A>C>D
E dist=20 path=A>C>F>E
F dist=11 path=A>C>F
lazy: {Pops:8 Stale:2 Checks:18 Relax:7 Fixes:0}
```

Note that `A-F` costs 14 but the route through C costs 11. Each of the 9 edges is checked from both ends, hence 18 checks.

## Lazy deletion or decrease-key

The code above never changes an entry inside the heap. It pushes a new one and skips the old one when it pops, which is called {{< term "lazy-deletion" "lazy deletion" >}}: 8 pops for 6 vertices, 2 of them stale. The alternative is decrease-key: keep one entry per vertex, remember its position and call `heap.Fix` after lowering the distance. The same graph gave 6 pops and 2 `Fix` calls. On random directed graphs with 4V edges and weights 1 to 100 (seed 11):

```
V      E       lazyPops stale relax | fixPops fixes
1000   4000    1296     309   1295  | 987     309   same=true
10000  40000   12895    3087  12894 | 9808    3094  same=true
100000 400000  128790   30793 128789 | 97997   30781 same=true
```

Both versions return identical distances. Lazy pops about 30% more, but the code is simpler and needs no position bookkeeping. I did not measure which is faster; the heap holds more entries in one and does extra `Fix` work in the other. The cost is O((V+E) log V) either way.

## Why negative edges break it

Dijkstra's {{< term "invariant" "invariant" >}}: once a vertex is popped, its distance is final, because any other route must pass through something at least as far away. A negative edge breaks that "at least". Directed edges S->A 2, S->B 3, B->A -2:

```
settled Dijkstra: [0 2 3]  lazy-skip Dijkstra: [0 1 3]  Bellman-Ford: [0 1 3] false
```

The textbook version finalises A at 2 before it learns that S->B->A costs 1. That is a real wrong answer. Interesting detail: the lazy version above happened to get it right here, because it never finalises anything. I would not rely on that, since it can redo exponential work on bigger graphs; I did not test that.

{{< term "bellman-ford" "Bellman-Ford" >}} simply relaxes every edge, repeatedly, up to V rounds: O(V·E). If a V-th round still improves something, there is a {{< term "negative-cycle" "negative cycle" >}} and no shortest path exists. With edges 1->2 of -3 and 2->1 of 1 it reports `negative cycle: true`.

## Checking by comparison

A test builds 300 random graphs (seeds 0 to 299, 2 to 13 vertices, weights 0 to 20, half directed) and compares both Dijkstra versions, Bellman-Ford and Floyd-Warshall (all pairs, O(V³)). It also rebuilds each path from `parent` and checks that the edge weights sum to the distance. It passes with `-race`. This is {{< term "property-based-testing" "property-style" >}} testing: independent algorithms must agree.

## A grid with obstacles

Each open cell is a vertex, each move costs 1. Dijkstra gave cost 33 and expanded 38 cells (`*` marks the path):

```
S****#******
.###*#*####*
.#***#*#****
.#*###*#*###
.#*****#***E
```

## A* in one section

{{< term "a-star" "A*" >}} orders the heap by `cost so far + estimate to goal`. If the estimate never exceeds the true remaining cost (Manhattan distance on a 4-direction grid), the answer stays optimal. On a 60x60 grid with a wall, same cost 159:

```
60x60 wall: dijkstra cost 159 expanded 3550 | A* cost 159 expanded 1969
no wall in the way: dijkstra expanded 216 | A* cost 20 expanded 21
```

With a clear straight line A* expanded 21 cells, Dijkstra 216. The wall shrank the gain, because the estimate does not see walls. The generic `Search[N comparable]` function is the same code for both; Dijkstra is A* with estimate 0. A test checks equal costs on 100 random grids.

## A few things to watch

- Dijkstra needs non-negative weights; otherwise use Bellman-Ford.
- A zero weight is fine; a negative one is not.
- With lazy deletion, always skip stale entries or you redo work.
- Use a large but safe "infinity" so `Inf + w` cannot overflow.
- A bad A* estimate (one that overestimates) can return a non-shortest path.

## Exercise

Add a path-reconstruction check to `DijkstraFix`, then make a graph where all edges are 1 and confirm Dijkstra's distances equal the BFS distances.

## What's next

Some graphs are about order, not distance: build steps, imports, tasks. The next post is "Topological sort and dependencies".
