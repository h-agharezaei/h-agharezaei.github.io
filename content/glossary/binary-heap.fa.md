+++
title = "Binary heap"
fa_title = "هیپ دودویی"
summary = "یک درخت دودویی کامل که در slice ذخیره می‌شود و هر والد از فرزندانش بزرگ‌تر نیست؛ کمینه همیشه در اندیس ۰ است."
category = "Algorithms"
related = ["priority-queue", "heapify", "dynamic-array", "big-o"]
posts = ["algo-heaps-priority-queues"]
+++

در min-heap که در slice ذخیره شده، فرزندان اندیس `i` برابر `2i+1` و `2i+2` هستند و والد برابر `(i-1)/2` است. `Push` در انتها اضافه می‌کند و بالا می‌برد (sift up)؛ `Pop` آخرین عنصر را به ریشه می‌آورد و پایین می‌برد (sift down). هر دو O(log n) هستند و `Peek` برابر O(1) است. فرزندان هم‌سطح مرتب نیستند، پس heap لیست مرتب نیست.
