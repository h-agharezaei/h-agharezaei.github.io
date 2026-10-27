+++
title = 'Zombie process'
summary = 'فرزندی که تمام شده اما والدش هنوز `wait` نزده، پس ردیفش در جدول پروسه‌ها مانده است.'
category = 'Linux'
fa_title = 'پروسه‌ی zombie'
related = ["process", "signal"]
posts = ["linux-processes-signals"]
+++

فرزندی که تمام شده اما والدش هنوز `wait` نزده، پس ردیفش در جدول پروسه‌ها مانده است. در `ps` وضعیت `Z` دارد. کشته نمی‌شود؛ وقتی والد آن را جمع کند یا خارج شود، از بین می‌رود.
