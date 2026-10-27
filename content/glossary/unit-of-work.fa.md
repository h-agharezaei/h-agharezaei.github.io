+++
title = "Unit of work"
fa_title = "Unit of work"
summary = "الگویی که در آن یک شیء تغییرها را ردیابی می‌کند و همه را یک‌جا در یک transaction می‌نویسد."
category = "Python"
related = ["orm", "transaction"]
posts = ["py-sqlalchemy-postgres"]
+++

Session در SQLAlchemy یک unit of work است: شیءها را اضافه و ویرایش می‌کنید و هنگام flush دستورهای INSERT/UPDATE را به ترتیب وابستگی می‌فرستد. commit آن‌ها را ماندگار و rollback دور می‌ریزد.
