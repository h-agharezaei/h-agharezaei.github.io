+++
title = "X.509 certificate"
summary = "گواهی X.509: سندی امضاشده که یک کلید عمومی را به یک نام وصل می‌کند."
category = "Networking"
fa_title = "گواهی X.509"
related = ["certificate-authority", "subject-alt-name", "tls"]
posts = ["net-tls-openssl"]
+++

گواهی X.509 شامل کلید عمومی، صاحب گواهی (subject)، صادرکننده‌ی امضاکننده، بازه‌ی اعتبار و افزونه‌هایی مثل SubjectAltName است. دستور `openssl x509 -text` همه‌ی اینها را چاپ می‌کند.
