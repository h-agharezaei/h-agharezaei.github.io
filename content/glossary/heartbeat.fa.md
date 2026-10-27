+++
title = "Heartbeat"
summary = "پیام کوچک و دوره‌ای (مثل ping) برای فهمیدن اینکه طرف مقابل هنوز زنده است."
category = "Networking"
fa_title = "Heartbeat"
related = ["websocket", "deadline"]
posts = ["net-websocket", "ds-why-distributed-is-hard"]
+++

یک اتصال TCP نیمه‌مرده می‌تواند مدت‌ها باز به نظر برسد. اگر ping تا پیش از deadline pong نگیرد، طرف مقابل رفته حساب می‌شود و اتصال بسته می‌شود.
