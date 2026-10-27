+++
title = "SSH certificate"
summary = "کلید عمومی امضا‌شده با کلید CA، همراه principal و بازه‌ی اعتبار، به‌جای فهرستی از کلیدهای خام."
category = "Linux"
fa_title = "گواهی SSH"
related = ["ssh-key-pair", "certificate-authority", "x509-certificate"]
posts = ["linux-ssh-keys"]
+++

با ssh-keygen -s ساخته و با ssh-keygen -L خوانده می‌شود. سرورها با TrustedUserCAKeys به CA اعتماد می‌کنند. برخلاف [x509](/fa/glossary/x509-certificate/) زنجیره‌ای وجود ندارد.
