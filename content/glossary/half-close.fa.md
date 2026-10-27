+++
title = "Half-close"
summary = "بستن فقط جهت ارسال یک اتصال TCP در حالی که هنوز می‌توان خواند."
category = "Networking"
fa_title = "نیم‌بستن اتصال"
related = ["tcp", "socket"]
posts = ["net-sockets-tcp-from-scratch", "net-tcp-handshake-states"]
+++

اتصال TCP دو جهت مستقل دارد. half-close (در Go: `CloseWrite`) به طرف مقابل می‌گوید «ارسال من تمام شد» (او EOF می‌بیند) ولی خودتان هنوز می‌توانید پاسخش را بخوانید.
