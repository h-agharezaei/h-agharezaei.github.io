+++
title = "Overlapping subproblems"
summary = "The same smaller problem is needed again and again by different branches of the recursion."
category = "Algorithms"
related = ["dynamic-programming", "memoization"]
posts = ["algo-dynamic-programming-1"]
+++

The same smaller problem is needed again and again by different branches of the recursion.

In naive Fibonacci, fib(30) is computed by both fib(32) and fib(31). Caching its result removes the repeated work.
