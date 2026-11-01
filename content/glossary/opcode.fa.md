+++
title = "Opcode"
summary = "یک دستور ماشین مجازی که به‌شکل یک بایت encode می‌شود؛ مثلاً در EVM بایت 0x01 یعنی ADD و 0x55 یعنی SSTORE."
category = "Blockchain"
fa_title = "Opcode"
related = ["bytecode", "evm"]
posts = ["bc-evm-internals-rust"]
+++

بعضی opcodeها داده‌ی فوری پشت سرشان دارند: بعد از `PUSH1` (0x60) یک بایت می‌آید که push می‌شود. مفسر یک opcode می‌خواند، کارش را انجام می‌دهد و سراغ بعدی می‌رود.
