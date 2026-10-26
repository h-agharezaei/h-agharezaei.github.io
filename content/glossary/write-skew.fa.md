+++
title = "Write skew"
fa_title = "انحراف نوشتن"
summary = "دو تراکنش داده‌ی مشترکی را می‌خوانند، هر کدام ردیف متفاوتی را به‌روز می‌کند و با هم قاعده‌ای را می‌شکنند که هیچ‌کدام تنها نمی‌شکست."
category = "Databases"
related = ["snapshot-isolation", "lost-update", "isolation-level"]
posts = ["db-isolation-levels-anomalies"]
+++

مثال کلاسیک: دو پزشک کشیک هر کدام چک می‌کنند دیگری هنوز سر کار است و بعد هر دو می‌روند. snapshot isolation این را اجازه می‌دهد؛ SERIALIZABLE نه.
