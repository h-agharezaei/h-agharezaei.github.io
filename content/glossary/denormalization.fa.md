+++
title = "Denormalization"
summary = "ذخیره‌ی عمدی یک واقعیت در چند جا برای ارزان‌تر شدن خواندن."
category = "Databases"
fa_title = "دنرمال‌سازی"
related = ["normalization"]
posts = ["db-schema-design-normalization"]
+++

دنرمال‌سازی یعنی عمداً یک داده را در بیش از یک جا نگه داریم، مثلاً جمع کل سفارش را ذخیره کنیم، تا join یا aggregate سنگین لازم نشود. هزینه‌اش این است که باید نسخه‌ها را هماهنگ نگه داریم. این تصمیم بعد از [نرمال‌سازی](/fa/glossary/normalization/) می‌آید، نه به‌جای آن.
