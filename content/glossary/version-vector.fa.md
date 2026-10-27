+++
title = "Version vector"
summary = "یک vector clock که به مقدار ذخیره‌شده وصل می‌شود تا replicaها بتوانند به‌روزرسانی را از تعارض تشخیص دهند."
category = "Distributed"
fa_title = "version vector"
related = ["vector-clock", "last-write-wins"]
posts = ["ds-logical-clocks"]
+++

اگر یک vector بر دیگری غلبه کند مقدار قدیمی‌تر کنار می‌رود؛ اگر هم‌زمان باشند هر دو به‌عنوان sibling نگه داشته می‌شوند تا برنامه ادغامشان کند.
