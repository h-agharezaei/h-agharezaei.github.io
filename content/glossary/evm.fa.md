+++
title = "EVM"
summary = "ماشین مجازی اتریوم: یک ماشین stack با کلمه‌های ۲۵۶ بیتی که bytecode قرارداد را اجرا می‌کند و برای هر قدم gas می‌گیرد."
category = "Blockchain"
fa_title = "EVM"
related = ["bytecode", "opcode", "gas", "smart-contract"]
posts = ["bc-evm-internals-rust"]
+++

هر فراخوانی قرارداد یک [stack](/fa/glossary/stack/) و memory تازه می‌گیرد، ورودی را از calldata می‌خواند و می‌تواند storage دائمی قرارداد را بخواند و بنویسد. همه‌ی نودها همان کد را روی همان ورودی اجرا می‌کنند و باید به همان نتیجه برسند.
