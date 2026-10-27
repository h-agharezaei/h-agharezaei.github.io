+++
title = "Relaxation"
fa_title = "relaxation (آسان‌سازی یال)"
summary = "به‌روزرسانی فاصله‌ی یک رأس وقتی مسیر از یک یال کوتاه‌تر از بهترین مسیر شناخته‌شده است."
category = "Algorithms"
related = ["dijkstra", "bellman-ford"]
posts = ["algo-shortest-paths-dijkstra"]
+++

به‌روزرسانی فاصله‌ی یک رأس وقتی مسیر از یک یال کوتاه‌تر از بهترین مسیر شناخته‌شده است.

برای یال u به v با وزن w: اگر dist[u] + w کمتر از dist[v] بود، آن را در dist[v] می‌گذاریم. Dijkstra و Bellman-Ford هر دو روی همین گام ساخته شده‌اند.
