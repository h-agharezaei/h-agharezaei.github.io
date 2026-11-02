+++
title = "Fiat-Shamir transform"
summary = "اثبات تعاملی را با ساختن challenge از hash روی transcript، غیرتعاملی می‌کند."
category = "Blockchain"
fa_title = "تبدیل Fiat-Shamir"
related = ["schnorr", "zero-knowledge-proof"]
posts = ["bc-zero-knowledge-rust"]
+++

hash باید همه چیز را بپوشاند: برچسب دامنه، کلید عمومی، تعهد و پیام. اگر تعهد جا بیفتد، هر کسی بدون راز می‌تواند اثبات جعل کند.
