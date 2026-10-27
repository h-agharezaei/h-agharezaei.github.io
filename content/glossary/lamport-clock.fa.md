+++
title = "Lamport clock"
summary = "یک شمارنده برای هر process که با هر رویداد زیاد می‌شود و هنگام receive با max ادغام می‌شود، تا «a پیش از b» یعنی timestamp کوچک‌تر."
category = "Distributed"
fa_title = "ساعت Lamport"
related = ["happens-before", "vector-clock"]
posts = ["ds-logical-clocks"]
+++

عکسش درست نیست: timestamp کوچک‌تر یعنی happens-before نیست، پس ساعت Lamport هم‌زمانی را تشخیص نمی‌دهد. برای ترتیب کلی معمولاً تساوی با شناسه‌ی process شکسته می‌شود.
