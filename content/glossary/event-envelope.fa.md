+++
title = "Event envelope"
summary = "یک پوشش ثابت دور هر رویداد با metadata (شناسه، نوع، زمان، منبع، نسخه‌ی schema، correlation id) جدا از payload."
category = "Distributed"
fa_title = "قالب رویداد"
related = ["idempotency", "tolerant-reader"]
posts = ["ds-messaging-event-driven"]
+++

CloudEvents یک مشخصه‌ی منتشرشده برای چنین envelope ای است. consumer فقط با خواندن envelope می‌تواند رویداد را مسیردهی، deduplicate و ردیابی کند.
