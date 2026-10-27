+++
title = "Replicated log"
summary = "فهرست مرتبی از فرمان‌ها که روی چند node کپی می‌شود؛ اگر همه log یکسان را به همان ترتیب اعمال کنند، state machineها یکسان می‌شوند."
category = "Distributed"
fa_title = "replicated log (log تکثیر‌شده)"
related = ["raft", "consensus"]
posts = ["ds-consensus-raft"]
+++

یک entry وقتی committed است که اکثریت آن را ذخیره کرده باشند (و در Raft قوانین term خود leader رعایت شده باشد). فقط entryهای committed اعمال می‌شوند.
