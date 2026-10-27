+++
title = "Dependency injection"
summary = "دادن وابستگی‌ها (مثل زمان یا دیتابیس) از بیرون به‌جای ساختنشان داخل تابع."
category = "Node.js"
fa_title = "تزریق وابستگی"
related = ["test-double"]
posts = ["node-testing-builtin", "eng-testing-pyramid-tdd", "node-project-structure-config"]
+++

به‌جای اینکه تابع خودش `Date.now()` یا اتصال دیتابیس را بسازد، آن را پارامتر می‌گیرد. در تست یک نسخه‌ی ساختگی می‌دهید و نتیجه قطعی می‌شود.
