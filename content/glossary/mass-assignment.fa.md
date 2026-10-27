+++
title = "Mass assignment"
summary = "باگی که در آن سرور همه‌ی فیلدهای درخواست کلاینت را در یک شیء داخلی کپی می‌کند و کلاینت فیلدهایی را تعیین می‌کند که نباید (قیمت، وضعیت، نقش)."
category = "Security"
fa_title = "Mass assignment"
related = ["stride"]
posts = ["sec-threat-modeling-stride", "sec-authorization-rbac-idor"]
+++

راه‌حل یک نوع ورودی allow-list است که فقط فیلدهای مجاز را دارد و بقیه را سرور حساب یا مقداردهی می‌کند.
