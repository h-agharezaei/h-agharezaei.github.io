+++
title = "Correlated subquery"
fa_title = "correlated subquery (زیرپرس‌وجوی وابسته)"
summary = "زیرپرس‌وجویی که به ردیف بیرونی ارجاع می‌دهد و برای هر ردیف بیرونی یک بار اجرا می‌شود."
category = "Databases"
related = ["query-plan", "database-index"]
posts = ["db-slow-query-case-study"]
+++

`SELECT c.id, (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) FROM customers c` پرس‌وجوی داخلی را برای هر مشتری اجرا می‌کند. با ایندکس و ردیف کم مشکلی ندارد، وگرنه بسیار پرهزینه است. یک `JOIN` با `GROUP BY` معمولاً اجازه می‌دهد planner کار را در یک گذر انجام دهد.
