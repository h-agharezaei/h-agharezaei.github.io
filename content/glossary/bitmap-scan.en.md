+++
title = "Bitmap scan"
summary = "A plan that collects matching row locations from one or more indexes into a bitmap, then reads the table pages in order."
category = "Databases"
related = ["composite-index"]
posts = ["db-composite-partial-covering-indexes"]
+++

With several indexes the bitmaps can be combined with `BitmapAnd` or `BitmapOr`.
