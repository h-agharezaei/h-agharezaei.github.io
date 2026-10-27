+++
title = "Request ID"
summary = "شناسه‌ی یکتایی که به یک درخواست و همه‌ی لاگ‌هایش چسبانده می‌شود."
category = "Node.js"
fa_title = "شناسه‌ی درخواست"
related = ["structured-logging"]
posts = ["node-fastify-api"]
+++

با request ID می‌شود همه‌ی لاگ‌های یک درخواست را از میان لاگ شلوغ بیرون کشید. معمولاً از یک هدر ورودی (مثل `x-request-id`) گرفته و به کلاینت برگردانده می‌شود تا دو طرف بتوانند به آن ارجاع بدهند.
