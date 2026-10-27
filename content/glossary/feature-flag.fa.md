+++
title = "Feature flag"
summary = "کلیدی در زمان اجرا که مسیرهای کد را بدون deploy روشن یا خاموش می‌کند."
category = "Engineering"
fa_title = "پرچم ویژگی"
related = ["kill-switch","canary-release","trunk-based-development"]
posts = ["eng-feature-flags-trunk-based"]
+++

feature flag (یا toggle) شرطی در کد است که مقدارش از پیکربندی می‌آید، نه از build. با آن می‌شود کار نیمه‌تمام را merge کرد، کم‌کم منتشر کرد و ویژگی را سریع خاموش کرد. هزینه‌اش مسیرهای بیشتر برای تست و پرچم‌هایی است که باید بعداً حذف شوند.
