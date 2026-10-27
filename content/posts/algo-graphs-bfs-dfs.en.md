+++
date = '2027-03-05T10:00:00+03:30'
draft = false
title = 'Graphs: BFS and DFS'
description = 'Graphs in Go: adjacency list, matrix and edge list with real byte counts, BFS shortest paths, DFS, components, cycles, grids, and O(V+E) proved by counts.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "bfs", "dfs", "go"]
cover = { image = "/images/covers/algo-graphs-bfs-dfs.png", alt = "Graphs: BFS and DFS", hiddenInSingle = true }
+++

In the previous post, [Tries and union-find](/posts/algo-tries-union-find/), we asked "are these two things connected?" without ever looking at the path. A {{< term "graph" "graph" >}} lets us ask the harder questions: how far, by which route, is there a loop? Traversal needs a [queue](/posts/algo-stacks-queues-deques/) or a stack, and its cost has two variables, which we measure in the [Big-O](/posts/algo-big-o-measured/) way.

> Go 1.26, local example, tests with `go test -race`. The machine load was above 4 when I checked, so I publish no timings, only counts and bytes.

## Three ways to store a graph

I built a random undirected graph with V=1,000 vertices and E=5,000 edges (seed 42) and computed the bytes from the real structures on a 64-bit machine:

```
adjacency list: 104000 bytes (exact elements), 132640 bytes (with append capacity)
adjacency matrix [][]bool: 1024000 bytes; as bits: 125000 bytes
edge list [][2]int: 80000 bytes; with int32: 40000 bytes
```

An {{< term "adjacency-list" "adjacency list" >}} (`[][]int`) costs about V + 2E ints, and the extra 28 KB is slice capacity left by `append`. The matrix costs V squared whatever E is, which only pays off for dense graphs or when you need "is there an edge u-v?" in O(1). The edge list is smallest but finding the neighbours of a vertex means scanning everything. Traversals need neighbours, so I use the list.

## BFS: nearest first

{{< term "bfs" "Breadth-first search" >}} keeps a queue; the first time it reaches a vertex is by a shortest route (in edges), so one array gives distances and another gives the parent:

```go
dist[src] = 0
queue := []int{src}
for len(queue) > 0 {
	u := queue[0]; queue = queue[1:]
	for _, v := range g.adj[u] {
		if dist[v] == -1 {
			dist[v], parent[v] = dist[u]+1, u
			queue = append(queue, v)
		}
	}
}
```

On a small 8-vertex graph (edges 0-1 0-2 1-3 1-4 2-5 4-6 5-6 6-7):

```
BFS dist from 0: [0 1 1 2 2 2 3 4]
path 0 -> 7: [0 1 4 6 7]
```

The path follows `parent` from 7 back to 0, reversed. A test compares BFS distances with Floyd-Warshall on 300 random small graphs (directed and undirected, unreachable vertices included) and the path lengths. It passes.

## DFS: as deep as possible

{{< term "dfs" "Depth-first search" >}} goes down one branch until it is stuck, then backs up. Recursively it is five lines; iteratively it uses an explicit stack. The orders on the same graph:

```
DFS recursive : [0 1 3 4 6 5 2 7]
DFS iterative (pushed in order)  : [0 2 5 6 7 4 1 3]
DFS iterative (pushed reversed)  : [0 1 3 4 6 5 2 7]
```

Pushing neighbours in order makes the stack pop the last one first, so the visit order differs. Both are valid; pushing in reverse reproduces the recursive order, checked by a test on 200 random graphs. Go grows goroutine stacks, so a test recurses 1,000,000 deep on a path graph without trouble. In Python the default limit is 1000 frames; I ran a recursive function with n=5000 there and got `RecursionError: maximum recursion depth exceeded`. In Python you would use the explicit stack.

## What the traversals give you

**Components.** A traversal from every unvisited vertex labels each {{< term "connected-component" "connected component" >}}. On 9 vertices with edges 0-1 1-2 3-4 5-6 6-7 7-5 the output is `components: 4 [0 0 0 1 1 2 2 2 3]`. A test compares the labels with my own small union-find on 200 random graphs, and they agree.

**Cycles.** In an undirected graph, meeting a visited vertex that is not the parent edge means a cycle. In a directed graph that is not enough, so DFS uses three colours: white (new), grey (on the current path), black (finished). A cycle exists exactly when an edge reaches a grey vertex.

```
directed  0->1->2, 0->2, 2->3 has cycle: false
directed  0->1->2->0 has cycle: true
undirected path 0-1-2 has cycle: false
undirected triangle has cycle: true
```

Tests check the directed version against Kahn's topological sort and the undirected one against "edges > V minus components".

**Bipartite.** Colour with BFS, alternating 0 and 1; if an edge joins two equal colours, the graph is not {{< term "bipartite-graph" "bipartite" >}}. A square gives `true [0 1 0 1]`, a triangle gives `false`.

## A grid is a graph

Cells are vertices and the four neighbours are edges. Flood fill counts islands of `#`:

```
aa..b..
a...b..
..c...d
..cc.dd
```

That is 4 islands. A maze is BFS on the same grid, so the first arrival at `E` is a shortest path (15 steps, `*` marks it):

```
S.#*****
*##*###*
****#..*
###.#.#*
....#.#E
```

## Proving O(V+E)

I made random graphs with E=3V (seed 7), ran BFS from every unvisited vertex and counted dequeued vertices and edge checks:

```
   V       E   vertices  edge checks  2E   V+2E
   1000    3000      1000         6000      6000      7000
  10000   30000     10000        60000     60000     70000
 100000  300000    100000       600000    600000    700000
1000000 3000000   1000000      6000000   6000000   7000000
```

Each vertex is dequeued once and each edge checked from both ends: exactly V + 2E, so O(V+E). Ten times the graph, ten times the work.

## A few things to watch

- Mark a vertex visited when you enqueue it, not when you dequeue it, or it can enter the queue many times.
- BFS distances count edges; with weights it is wrong.
- Iterative DFS matches the recursive order only with reversed pushes.
- Directed cycle detection needs three colours, not two.
- A matrix for a sparse graph wastes memory: about 1 MB for 5,000 edges.

## Exercise

Add a topological sort: use the three-colour DFS, append each vertex when it turns black, and reverse the result. Check that every edge goes forward, and that a cycle gives an error.

## What's next

Edges with weights break BFS. The next post is "Shortest paths and Dijkstra".
