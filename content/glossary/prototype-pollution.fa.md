+++
title = "Prototype pollution"
summary = "باگی در جاوااسکریپت که در آن کلیدهای زیر کنترل مهاجم مثل __proto__ prototype شیءها را عوض می‌کنند و شیءهای نامرتبط ناگهان ویژگی اضافه پیدا می‌کنند."
category = "Node.js"
fa_title = "آلودگی prototype"
related = ["schema-validation", "mass-assignment"]
posts = ["node-validation-zod", "sec-supply-chain-vulns"]
+++

معمولاً از کد merge یا کپی بازگشتی می‌آید که به کلیدهای JSON اعتماد می‌کند. اعتبارسنجی ورودی به یک شیء تازه با شکل مشخص، کلیدهایی را که اعلام نکرده‌اید حذف می‌کند.
