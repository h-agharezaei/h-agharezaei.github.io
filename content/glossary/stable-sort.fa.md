+++
title = "Stable sort"
fa_title = "مرتب‌سازی پایدار"
summary = "مرتب‌سازی‌ای که ترتیب نسبی عناصر برابر را حفظ می‌کند."
category = "Algorithms"
related = ["merge-sort", "quicksort"]
posts = ["algo-sorting"]
+++

اگر سفارش‌ها را بر اساس شهر مرتب کنید و دو سفارش شهر یکسان داشته باشند، مرتب‌سازی پایدار همان ترتیب ورود را نگه می‌دارد. به همین دلیل «اول بر اساس تاریخ، بعد شهر» کار می‌کند. merge sort پایدار است؛ quicksort ساده و heap sort نه. در Go، `sort.Stable` و `slices.SortStableFunc` این تضمین را می‌دهند.
