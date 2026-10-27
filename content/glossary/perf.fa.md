+++
title = "perf"
fa_title = "perf"
summary = "ابزار کارایی Linux که رویدادهای سخت‌افزاری را می‌شمارد و نمونه‌برداری می‌کند که زمان CPU کجا می‌رود."
category = "Linux"
related = ["cpu-profile", "flame-graph", "linux-capabilities"]
posts = ["linux-strace-perf"]
+++

**perf** دستور `perf stat` را برای شمارش رویدادها (cycles، instructions، context switch) و `perf record` با `perf report` را برای نمونه‌برداری از stackها در طول زمان دارد. نمونه‌برداری از ردیابی تک‌تک فراخوان‌ها ارزان‌تر است و نمونه‌ها را می‌شود به شکل [flame-graph](/fa/glossary/flame-graph/) کشید.
