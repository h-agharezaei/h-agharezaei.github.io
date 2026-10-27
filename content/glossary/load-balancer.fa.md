+++
title = "Load balancer"
summary = "پخش‌کننده‌ی ترافیک ورودی بین چند سرور backend."
category = "Networking"
fa_title = "load balancer"
related = ["reverse-proxy", "health-check"]
posts = ["net-load-balancer-l4-l7"]
+++

load balancer جلوی چند backend یکسان می‌نشیند و برای هر اتصال (لایه‌ی ۴) یا هر درخواست (لایه‌ی ۷) یکی را انتخاب می‌کند. backendهای خراب را هم از چرخه بیرون می‌برد.
