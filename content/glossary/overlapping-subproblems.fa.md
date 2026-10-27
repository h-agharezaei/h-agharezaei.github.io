+++
title = "Overlapping subproblems"
fa_title = "زیرمسئله‌های تکراری"
summary = "یک زیرمسئله‌ی کوچک‌تر بارها و از شاخه‌های مختلف بازگشت لازم می‌شود."
category = "Algorithms"
related = ["dynamic-programming", "memoization"]
posts = ["algo-dynamic-programming-1"]
+++

یک زیرمسئله‌ی کوچک‌تر بارها و از شاخه‌های مختلف بازگشت لازم می‌شود.

در Fibonacci ساده، fib(30) هم برای fib(32) و هم برای fib(31) حساب می‌شود. ذخیره‌ی نتیجه کار تکراری را حذف می‌کند.
