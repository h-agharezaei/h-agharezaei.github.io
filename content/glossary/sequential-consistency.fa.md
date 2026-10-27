+++
title = "Sequential consistency"
summary = "همه یک ترتیب واحد از عملیات می‌بینند که ترتیب هر client را حفظ می‌کند، ولی لازم نیست با زمان واقعی بخواند."
category = "Distributed"
fa_title = "سازگاری ترتیبی (sequential consistency)"
related = ["linearizability","causal-consistency"]
posts = ["ds-consistency-models"]
+++

ضعیف‌تر از linearizability: یک read می‌تواند مقداری قدیمی‌تر از write تمام‌شده‌ی client دیگر برگرداند، به شرط این‌که یک ترتیب سراسری معتبر وجود داشته باشد.
