+++
title = "Three-way handshake"
summary = "SYN، SYN-ACK، ACK: روش باز شدن اتصال TCP."
category = "Networking"
fa_title = "دست‌دادن سه‌مرحله‌ای"
related = ["tcp", "tcp-rst"]
posts = ["net-tcp-handshake-states"]
+++

کلاینت segment با flag برابر SYN می‌فرستد، سرور با SYN+ACK جواب می‌دهد و کلاینت با ACK تأیید می‌کند. حالا هر دو طرف شماره‌ی ترتیب اولیه‌ی دیگری را می‌دانند و اتصال در حالت ESTABLISHED است.
