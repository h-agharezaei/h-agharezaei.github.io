+++
title = "Live binding"
summary = "importی در ES module که به خودِ متغیرِ ماژول صادرکننده اشاره می‌کند، نه به یک کپی از مقدارش."
category = "Node.js"
fa_title = "اتصال زنده"
related = ["esm"]
posts = ["node-modules-esm-cjs"]
+++

importی در ES module که به خودِ متغیرِ ماژول صادرکننده اشاره می‌کند، نه به یک کپی از مقدارش. اگر ماژول صادرکننده `export let count` را تغییر دهد، همه‌ی importکننده‌ها مقدار جدید را می‌بینند. importکننده نمی‌تواند به آن مقدار بدهد.
