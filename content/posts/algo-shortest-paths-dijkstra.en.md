+++
date = '2027-03-21T10:00:00+03:30'
draft = false
title = 'Shortest paths and Dijkstra'
description = 'Dijkstra in Go with container/heap: lazy deletion vs heap.Fix, why negative edges break it, Bellman-Ford, Floyd-Warshall, and A* on a grid, with counts.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "dijkstra", "shortest-path", "go"]
cover = { image = "/images/covers/algo-shortest-paths-dijkstra.png", alt = "Shortest paths and Dijkstra", hiddenInSingle = true }
+++

Suppose you want to travel from city A to city F. The map has six cities. The direct road from A to F is 14 kilometers, but if you go from A to C (9 km) and then from C to F (just 2 km), you reach F after 11 km. The shortest way is not always the one with the fewest roads.

{{< term "bfs" "BFS" >}} from the [previous post](/posts/algo-graphs-bfs-dfs/) only counts edges, so here it would pick the direct 14 km road. That is right only when every edge costs the same. But roads, network links and prices each have a **weight**. A graph whose edges have weights is a **weighted graph**, and finding shortest paths in it needs another algorithm. That algorithm uses a [priority queue](/posts/algo-heaps-priority-queues/), the same {{< term "binary-heap" "heap" >}} we built earlier, so that each time we can pull out "the nearest vertex we have not finished yet".

> I re-ran every output with Go 1.27. It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish no timings; you will only see counts, which are the same on every run.

## The idea behind Dijkstra

{{< term "dijkstra" "Dijkstra's algorithm" >}} thinks like this. For every vertex it keeps "the best distance I have found so far". At the start the source's distance is 0 and everyone else's is infinity. Then it repeats: among the vertices that are not finished, take the one whose tentative distance is smallest. That distance will never change again. Then try all of its outgoing edges: if `dist[u] + w` is smaller than `dist[v]`, we have found a shorter way to `v` through `u`, and we update `dist[v]`. This update is called {{< term "relaxation" "relaxation" >}}.

Why is the smallest tentative distance final? Because any other route to this vertex must pass through some vertex that is not finished yet, and that vertex is at least as far away; if no weight is negative, the rest of the route cannot subtract anything. (This condition matters later.)

A hand-worked example makes it clear. Six cities and these two-way roads (the number is the weight):

```
A-B:7 A-C:9 A-F:14 B-C:10 B-D:15 C-D:11 C-F:2 D-E:6 E-F:9
```

We start from A:

| vertex taken | what changed | distances afterwards |
|---|---|---|
| A (0) | B←7, C←9, F←14 | B=7 C=9 F=14 |
| B (7) | D←22 (C via B would be 17, not better than 9) | D=22 |
| C (9) | D←20 (better than 22), F←11 (better than 14) | D=20 F=11 |
| F (11) | E←20 | E=20 |
| D (20) and E (20) | nothing gets better | |

In the end the distances from A are B=7, C=9, F=11, D=20, E=20. Interestingly, the shortest way from A to E goes through C and F (`A>C>F>E`): three edges, but 20 km. BFS would have picked the two-edge route `A>F>E`, which is 23 km.

Now the code. To get "the smallest vertex" we use `container/heap`:

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

One detail: when a vertex's distance improves, we do not remove its old entry from the heap; we just add a new one. Later, when the old entry (with the worse distance) comes out, the check `it.d > dist[it.v]` skips it. You could see this in the table above: F entered once with 14 and later with 11, and D once with 22 and once with 20. The demo's output for this graph:

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

Each `dist` line shows a distance and a path (built from `parent`, as in BFS). The last line holds the counters: 8 pops (6 vertices plus 2 stale entries that were skipped, namely `F=14` and `D=22`), 18 edge checks (each of the 9 edges from both ends), and 7 successful relaxations (B, C, F, D at 22, D at 20, F at 11, and E).

## Two ways to update the heap

What we just did, keeping the stale entry and skipping it later, is called {{< term "lazy-deletion" "lazy deletion" >}}. The other way is **decrease-key**: keep exactly one entry per vertex, remember where it sits in the heap, and when its distance drops call `heap.Fix` to put it in the right place. On the same six vertices this version made 6 pops and 2 `Fix` calls (`fix : {Pops:6 Stale:0 Checks:18 Relax:7 Fixes:2}`).

Which is better? I counted both on random directed graphs with 4 times V edges and weights 1 to 100 (seed 11):

```
V      E       lazyPops stale relax | fixPops fixes
1000   4000    1296     309   1295  | 987     309   same=true
10000  40000   12895    3087  12894 | 9808    3094  same=true
100000 400000  128790   30793 128789 | 97997   30781 same=true
```

`same=true` means the distances are exactly equal in both methods. The lazy method does about 30 percent more pops; and `lazyPops - stale` equals `fixPops` (for V=1000 that is 987, meaning 987 vertices were reachable from vertex 0). But the lazy method has simpler code and does not need us to track where entries sit. Which one is faster in practice, I did not measure. Both cost about O((V+E) log V).

## Why a negative edge breaks Dijkstra

The algorithm's correctness depends on the {{< term "invariant" "invariant" >}} we described: a vertex that has come out has its final distance, because continuing along any other route cannot subtract anything. A negative edge breaks exactly that. Take a tiny directed graph: S→A with weight 2, S→B with weight 3, and B→A with weight -2. The route S→B→A costs 3 + (-2) = 1, better than the direct edge's 2. But textbook Dijkstra finalizes A (distance 2) before B (distance 3) and never comes back. The demo's output:

```
S->A 2, S->B 3, B->A -2
settled Dijkstra: [0 2 3]  lazy-skip Dijkstra: [0 1 3]  Bellman-Ford: [0 1 3] false
```

Each array holds the distances of S, A and B. The finalizing version (`settled`) gives A the value 2, which is wrong. The other two give 1, which is right. (The lazy version above happened to be right here because it improves the distance of a vertex it has already seen. Still, I do not rely on it, and I have not tested it on larger graphs with negative edges.)

For negative edges we use {{< term "bellman-ford" "Bellman-Ford" >}}. The idea is simple: relax every edge, one by one, and repeat that round at most V times. If a round changes no distance, we are done. It costs O(V·E), which is slower than Dijkstra. If after V rounds something still improves, there is a {{< term "negative-cycle" "negative cycle" >}}: a cycle that makes the route shorter every time you go around it, so "the shortest path" has no meaning. With edges 0→1 of weight 1, 1→2 of weight -3 and 2→1 of weight 1, the cycle 1→2→1 totals -2, and the demo prints:

```
cycle 1->2 (-3), 2->1 (1) negative cycle: true
```

## How do we know it works?

A test generates 300 random graphs (2 to 13 vertices, weights 0 to 20, half of them directed) and compares both Dijkstra versions with Bellman-Ford and Floyd-Warshall. Floyd-Warshall computes the distance between all pairs with three nested loops, O(V³): slow but very simple, so a good reference. The test also builds the path of every vertex from `parent` and checks that the weights along the path add up to the distance. It is {{< term "property-based-testing" "property-based" >}} in style: several independent algorithms must agree on every random input.

## A grid of cells

The same idea works on a grid of cells: each open cell is a vertex and each move to a neighboring cell costs 1 (`#` is a wall). The input:

```
S....#......
.###.#.####.
.#...#.#....
.#.###.#.###
.#.....#...E
```

Dijkstra found cost 33 and expanded 38 cells before reaching `E` (`*` is the path):

```
S****#******
.###*#*####*
.#***#*#****
.#*###*#*###
.#*****#***E
```

The route winds around because the walls allow no shortcuts. "Expanding" a cell means taking it out of the heap and trying its edges; 38 is smaller than the number of all open cells because the search stops as soon as it reaches `E`.

## A*: look at the goal

Dijkstra spreads in all directions like a ripple, even in directions away from the goal. If we know where the goal is, we can be a bit smarter. {{< term "a-star" "A*" >}} orders the heap not only by "cost so far" but by "cost so far + an estimate of the cost to the goal". On a four-direction grid a good estimate is the "Manhattan distance": the row difference plus the column difference, which is the cost of walking if there were no walls. The result stays optimal as long as the estimate never exceeds the true remaining cost, which Manhattan satisfies. (This implementation finalizes a cell the first time it comes out of the heap; that is safe for an estimate that is also "consistent", meaning it never drops by more than the cost of a step, and Manhattan on a four-direction grid is.)

I built a 60 by 60 grid with a wall in column 30 that is open only at the bottom (rows 50 to 59). The start is at the top left and the goal at the top right, so the route has to go around the wall. The result:

```
60x60 wall: dijkstra cost 159 expanded 3550 | A* cost 159 expanded 1969
no wall in the way: dijkstra expanded 216 | A* cost 20 expanded 21
```

Line one: both found the same optimal cost, 159, but A* expanded 1969 cells and Dijkstra 3550. Line two: the goal is on the same row on the left side of the wall, so a direct route is open. A* with cost 20 looked at only 21 cells (basically just the path itself), and Dijkstra at 216. When a wall is in the way the gain is smaller, because the Manhattan estimate cannot see the wall and A* has to head toward it first.

In the code, one generic function `Search[N comparable]` does both: when the estimate is `nil` it is always zero, and A* becomes Dijkstra. A test on 100 random grids checks that A* and Dijkstra give the same cost.

## Where Dijkstra goes wrong

- **Dijkstra needs non-negative weights.** With a negative edge it gives a wrong answer, silently. Use Bellman-Ford there.
- **With lazy deletion, always skip stale entries.** Without the `it.d > dist[it.v]` check, every stale entry makes you examine all of the vertex's edges again, which is needless work.
- **Pick an "infinity" that is large but safe.** If you use the largest possible number, `Inf + w` overflows and becomes negative. In this example's code it is `math.MaxInt / 4`.
- **A bad estimate in A* ruins the answer.** If the estimate claims more than the true remaining cost, the path returned may not be the shortest.

## Exercise

Add the path-reconstruction check (the weights along the path add up to the distance) for `DijkstraFix` too. Then build a graph whose edges all have weight 1 and see that Dijkstra's distances equal BFS's distances.

## What's next

"Topological sort and dependencies". So far our graphs were about distance, but some graphs are about order: build steps, imports, tasks that must run one after another.
