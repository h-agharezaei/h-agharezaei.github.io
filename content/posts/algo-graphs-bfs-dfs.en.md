+++
date = '2027-03-05T10:00:00+03:30'
draft = false
title = 'Graphs: BFS and DFS'
description = 'Graphs in Go: adjacency list, matrix and edge list with real byte counts, BFS shortest paths, DFS, components, cycles, grids, and O(V+E) proved by counts.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "graphs", "bfs", "dfs", "go"]
cover = { image = "/images/covers/algo-graphs-bfs-dfs.png", alt = "Graphs: BFS and DFS", hiddenInSingle = true }
+++

Suppose you are stuck in a maze and want the shortest way out. Or you have a social network and someone asks, "how many friends away is this person from me?" Or you have a project with dozens of modules that depend on each other, and you want to know whether the dependencies form a loop. These three problems look unrelated, but they have the same shape: some things, and relationships between them. That shape is called a {{< term "graph" "graph" >}}.

In the [previous post](/posts/algo-tries-union-find/), union-find could only answer "are these two things connected?" It could not tell us by which route, or in how many steps. Walking a graph answers exactly those questions. In this post we first see how to store a graph in memory, then learn the two ways to walk it (BFS and DFS), and finally see what we can solve with them. Walking a graph uses a [queue or a stack](/posts/algo-stacks-queues-deques/), and we will measure its cost by counting, the way we did in [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> I re-ran every output in this post with Go 1.27 (the example's `go.mod` still declares `go 1.26`). It is a local example and its tests pass with `go test -race`. I publish no timings because the machine was busy; you will only see counts and byte sizes, which are the same on every run.

## What is a graph?

A graph is just two things: a set of **vertices** and a set of **edges**. The vertices are our "things" (a person, a city, a cell of the maze, a module). Each edge is a relationship between two vertices (friendship, a road, "no wall between them", a dependency). If the relationship goes both ways, like friendship or a two-way road, the edge is **undirected**. If it goes one way, like "module A depends on B", the edge is **directed**.

Here is the graph used in most examples below: eight vertices numbered 0 to 7 and eight edges.

```
        3
        |
    0 — 1 — 4
    |       |
    2       6 — 7
    |       |
    5 ——————+
```

The edges are 0-1, 0-2, 1-3, 1-4, 2-5, 4-6, 5-6 and 6-7. The graph is undirected, so 0-1 means you can go from 0 to 1 and from 1 to 0.

## How do we store a graph?

There are three common ways. To see the difference in numbers, I built a random undirected graph with 1000 vertices and 5000 edges (seed 42, so it is the same graph every time) and computed the size of each structure on a 64-bit machine:

```
adjacency list: 104000 bytes (exact elements), 132640 bytes (with append capacity)
adjacency matrix [][]bool: 1024000 bytes; as bits: 125000 bytes
edge list [][2]int: 80000 bytes; with int32: 40000 bytes
```

First, the **edge list**: just a list of pairs, `[][2]int`. It is the smallest (80,000 bytes), but to find the neighbors of one vertex you have to scan the whole list.

Second, the **adjacency matrix**: a V×V table where cell `[u][v]` says "is there an edge u-v?" The answer comes in constant time, but the table always takes V squared cells, whether there are 5000 edges or one. Here that is about a megabyte (even at one bit per cell it is 125,000 bytes). So it only pays off for dense graphs, or when you ask "is this edge there?" very often.

Third, the {{< term "adjacency-list" "adjacency list" >}}: for each vertex, a list of its neighbors. In Go that is a `[][]int`. For this graph it stores about V + 2E numbers, so 104,000 bytes for the elements themselves. (Each undirected edge appears in the lists of both its ends, hence the 2E.) If we also count the spare capacity `append` reserved, it is 132,640 bytes. Walking a graph constantly asks "who are the neighbors of this vertex?", and the adjacency list answers exactly that, quickly. So the rest of the post uses an adjacency list:

```go
type Graph struct {
	adj      [][]int // adj[u] = the neighbours of u
	directed bool
}

func (g *Graph) AddEdge(u, v int) {
	g.adj[u] = append(g.adj[u], v)
	if !g.directed {
		g.adj[v] = append(g.adj[v], u)
	}
}
```

For an undirected graph, `AddEdge` writes the edge into both lists. For a directed graph, only into the source's list.

## BFS: nearest first

Now the first question: the shortest way from vertex 0 to all the others. Think of dropping a stone in water. The first ripple reaches only the nearest points, then the second ripple, then the third. {{< term "bfs" "Breadth-first search" >}} (BFS) is that ripple. First all neighbors of the start, then the neighbors of those neighbors, and so on.

To keep that order it uses a {{< term "queue" "queue" >}}: whoever enters first leaves first. The algorithm is: put the start in the queue with distance 0. While the queue is not empty, take the first vertex and add every neighbor you have not seen yet to the back of the queue, with distance "this vertex's distance + 1".

Let's do it by hand on our graph:

| vertex taken | new neighbors | queue afterwards | distances recorded |
|---|---|---|---|
| (start) | | [0] | 0 ← 0 |
| 0 | 1, 2 | [1, 2] | 1 ← 1, 2 ← 1 |
| 1 | 3, 4 | [2, 3, 4] | 3 ← 2, 4 ← 2 |
| 2 | 5 | [3, 4, 5] | 5 ← 2 |
| 3 | none | [4, 5] | |
| 4 | 6 | [5, 6] | 6 ← 3 |
| 5 | none (6 is already seen) | [6] | |
| 6 | 7 | [7] | 7 ← 4 |
| 7 | none | [] | |

Notice that the queue always holds the distance-1 vertices first, then distance 2, then distance 3. That is why the first time we reach a vertex, we have reached it by a shortest route (counted in edges). This is the core idea of BFS. The code says the same thing:

```go
dist[src] = 0
queue := []int{src}
for len(queue) > 0 {
	u := queue[0]; queue = queue[1:]
	for _, v := range g.adj[u] {
		if dist[v] == -1 { // not seen yet
			dist[v], parent[v] = dist[u]+1, u
			queue = append(queue, v)
		}
	}
}
```

`dist` is the distance, and `-1` means "not seen yet". `parent[v]` records which vertex we came from when we reached `v`. The demo's output on the same graph:

```
BFS dist from 0: [0 1 1 2 2 2 3 4]
path 0 -> 7: [0 1 4 6 7]
```

The first line is exactly the last column of the table: vertex 0 at distance 0, vertices 1 and 2 at distance 1, vertices 3, 4 and 5 at distance 2, vertex 6 at distance 3, vertex 7 at distance 4. The second line is the route itself. To build it we start at the destination and walk back through `parent`: the parent of 7 is 6, of 6 is 4, of 4 is 1, of 1 is 0. We reverse that and get `0 → 1 → 4 → 6 → 7`.

To check correctness, one test compares BFS distances with the Floyd-Warshall algorithm on 300 small random graphs (directed and undirected, with unreachable vertices) and also checks path lengths. It passes. (Floyd-Warshall is a slow but simple way to compute the distance between all pairs; I used it only as a reference.)

## DFS: as deep as possible

The second way is the opposite of a ripple. Imagine you pick one corridor in the maze and follow it to a dead end, then go back to the nearest fork and try the next corridor. {{< term "dfs" "Depth-first search" >}} (DFS) does exactly this. Instead of a queue it uses a {{< term "stack" "stack" >}}: the last thing in is the first thing out. The recursive version needs no separate stack, because the nested function calls are the stack, and it is short:

```go
visit = func(u int) {
	seen[u] = true
	order = append(order, u)
	for _, v := range g.adj[u] {
		if !seen[v] {
			visit(v)
		}
	}
}
```

On our graph, starting at 0: first neighbor is 1. From 1 we go to 3 first, which is a dead end (its only neighbor is 1), so we return. Then 4, from there 6, from 6 first 5, and from 5 to 2, whose neighbors (0 and 5) we have already seen. We return up to 6 and then visit 7. The visiting order is `0 1 3 4 6 5 2 7`.

The iterative version has an explicit stack. The order in which we push neighbors matters, because a stack pops the last one first. The demo tries both:

```
DFS recursive : [0 1 3 4 6 5 2 7]
DFS iterative (pushed in order)  : [0 2 5 6 7 4 1 3]
DFS iterative (pushed reversed)  : [0 1 3 4 6 5 2 7]
```

Line one is the order we just traced by hand. In line two I pushed the neighbors in order, so after 0 it pops 2, not 1, and a different order comes out. That is still a valid DFS (it just visits neighbors from last to first). In line three I pushed them reversed and got exactly the recursive order. A test checks this equality on 200 random graphs.

One note about depth: the recursive version keeps one frame per vertex on the current path. In Go a goroutine's stack grows on demand, and a test in this example runs recursive DFS on a path graph with 1,000,000 vertices and finishes fine. Python is different: the default recursion limit is 1000 frames, and a simple recursive function with depth 5000 fails on this machine with `RecursionError: maximum recursion depth exceeded` (I re-ran it). In Python, use an explicit stack.

## BFS or DFS?

Both see every reachable vertex exactly once, so their cost is the same. The difference is what you want. If you need "the shortest route counted in edges", use BFS. If you only want to "see everything" and discover structure (components, cycles, dependency order), DFS is usually simpler, because its way back (the recursion) comes for free. Below we use both.

## What can walking a graph solve?

**Connected components.** Sometimes a graph consists of several separate pieces, like friend groups that never meet. Each piece is a {{< term "connected-component" "connected component" >}}. To count them, start a walk from every vertex we have not seen yet; each walk labels one whole component. On 9 vertices with edges 0-1, 1-2, 3-4, 5-6, 6-7 and 7-5 (vertex 8 is alone), the demo prints:

```
components: 4 [0 0 0 1 1 2 2 2 3]
```

Four components: {0, 1, 2}, {3, 4}, {5, 6, 7} and {8}. The number at position i is the component label of vertex i. A test compares these labels with a small union-find of my own on 200 random graphs, and both give the same grouping.

**Finding a cycle.** In an undirected graph, if during the walk we reach a vertex we have already seen, and it is not the parent we just came from, we have a cycle. In a directed graph that is not enough: two different routes can reach one vertex without any cycle (for example 0→1→2 and 0→2). The right tool is DFS with three colors. A new vertex is **white**, a vertex that is on the current DFS path right now is **grey**, and a vertex that is completely finished is **black**. There is a cycle exactly when we reach a grey vertex, because that means we came back to a place we were still in the middle of leaving:

```
directed  0->1->2, 0->2, 2->3 has cycle: false
directed  0->1->2->0 has cycle: true
undirected path 0-1-2 has cycle: false
undirected triangle has cycle: true
```

Line one is the two-routes example: we reach 2 by two routes, but we never meet a grey vertex, so there is no cycle. In line two the edge from 2 goes back to 0, which is still grey, so there is a cycle. The last two lines ask the same question for undirected graphs: a path has no cycle, a triangle has one. The tests compare the directed version with Kahn's topological sort (a directed graph has no cycle if and only if Kahn's algorithm removes every vertex) and the undirected version with the rule that a cycle-free undirected graph has at most V minus the number of components edges. (We reach topological sort in a later post.)

**Bipartite graphs.** Sometimes we want to split the vertices into two groups so that every edge has its two ends in different groups (say "users" and "products"). We do it with BFS by coloring: the start gets 0, its neighbors get 1, their neighbors get 0 again, and so on. If we ever find an edge whose two ends have the same color, no such split exists, and the graph is not {{< term "bipartite-graph" "bipartite" >}}.

```
square bipartite: true [0 1 0 1]
triangle bipartite: false
```

The square (0-1-2-3-0) splits into `{0, 2}` and `{1, 3}`. The triangle does not: three vertices that are all connected to each other cannot be colored with two colors so that no two neighbors share a color.

## A grid is a graph too

You do not always have to build a graph explicitly. In a grid, each cell is a vertex and its four neighbors (up, down, left, right) are its edges. Here are two classic problems.

First, counting "islands": groups of `#` cells that touch each other. From every unseen `#` we start a DFS, find all connected `#` cells and label them with a letter (this is called flood fill, like the paint-bucket tool in a drawing program). The demo's input grid is:

```
##..#..
#...#..
..#...#
..##.##
```

and the output, with each island labelled:

```
islands: 4
aa..b..
a...b..
..c...d
..cc.dd
```

Island `a` is the three cells at the top left, `b` the two cells in the upper column, `c` the three cells in the lower middle and `d` the three cells at the lower right. (Diagonal cells do not count as connected; only the four directions do.)

Second, the maze itself. Since every step costs the same, BFS gives the shortest route. In the input `S` is the start, `E` the exit and `#` a wall:

```
S.#.....
.##.###.
....#...
###.#.#.
....#.#E
```

The demo's output marks the route BFS found to `E` with `*`:

```
maze shortest path: 15 steps
S.#*****
*##*###*
****#..*
###.#.#*
....#.#E
```

That is 15 steps: from `S` down and right to the third row, up to the first row, right to the last column and down to `E`. No shorter route exists, because BFS goes level by level, so the first time it reaches `E` is by a shortest route.

## Why is the cost O(V+E)?

So far I have said "every vertex is seen once". Now let's count. I built random graphs with three times as many edges as vertices (seed 7), ran BFS from every unseen vertex so the whole graph is covered, and counted how many vertices left the queue and how many times an edge was checked:

```
   V       E   vertices  edge checks  2E   V+2E
   1000    3000      1000         6000      6000      7000
  10000   30000     10000        60000     60000     70000
 100000  300000    100000       600000    600000    700000
1000000 3000000   1000000      6000000   6000000   7000000
```

The "vertices" column equals V exactly: every vertex leaves the queue once. The "edge checks" column equals 2E exactly: each undirected edge is looked at once from each of its ends. So the total work is V + 2E, which is O(V+E) (the factor 2 does not appear in Big-O). A graph ten times bigger means ten times the work. The same count holds for DFS; a separate test confirms it.

## Where walking a graph goes wrong

- **Mark a vertex when you put it in the queue, not when you take it out.** Otherwise a vertex whose turn has not come yet can be seen from several neighbors and enter the queue several times. The queue grows for no reason and you do extra work. (The check `dist[v] == -1` does this: a recorded distance means "marked".)
- **BFS distance is only a number of edges.** If edges have weights (a 5 km road and a 50 km road), the route with the fewest edges is not necessarily the shortest. That problem needs a different answer.
- **Iterative DFS matches the recursive order only if you push in reverse.** If order matters to you (in a test, for example), keep this in mind.
- **Cycles in a directed graph need three colors, not two.** With a plain seen/not-seen mark you would wrongly report the 0→1→2 and 0→2 example as a cycle.
- **An adjacency matrix wastes memory on a sparse graph.** For the same 1000 vertices and 5000 edges it was about a megabyte, against 104 KB for the adjacency list.

## Exercise

Add topological sort: use the three-color DFS, append each vertex to a list when it turns black, and reverse the list at the end. Check that all edges point forward, and that a graph with a cycle returns an error.

## What's next

"Shortest paths and Dijkstra". BFS counts distance in edges; once edges have weights, that count breaks and we need another algorithm.
