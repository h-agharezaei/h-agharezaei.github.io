+++
title = "A*"
fa_title = "الگوریتم A*"
summary = "Dijkstra که با یک برآورد از هزینه‌ی باقی‌مانده هدایت می‌شود و گره‌های کمتری گسترش می‌دهد."
category = "Algorithms"
related = ["dijkstra", "priority-queue"]
posts = ["algo-shortest-paths-dijkstra"]
+++

Dijkstra که با یک برآورد از هزینه‌ی باقی‌مانده هدایت می‌شود و گره‌های کمتری گسترش می‌دهد.

heap بر اساس هزینه تا اینجا به‌علاوه‌ی برآورد مرتب می‌شود. اگر برآورد هیچ‌وقت بیشتر از واقعیت نباشد (admissible)، مسیر پیدا شده همچنان بهینه است.
