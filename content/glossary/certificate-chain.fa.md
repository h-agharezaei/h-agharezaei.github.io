+++
title = "Certificate chain"
summary = "فهرست leaf، intermediate و root که گواهی سرور را به یک root مورد اعتماد وصل می‌کند."
category = "Security"
fa_title = "زنجیره‌ی گواهی"
related = ["certificate-authority", "x509-certificate"]
posts = ["sec-tls-x509-certificates"]
+++

گواهی سرور معمولاً با یک CA میانی (intermediate) امضا می‌شود و آن CA را rootای امضا کرده که کلاینت به آن اعتماد دارد. سرور باید leaf و intermediateها را بفرستد؛ root از trust store کلاینت می‌آید. نبودن intermediate باعث شکست اعتبارسنجی می‌شود.

نگاه کنید به [certificate authority](/fa/glossary/certificate-authority/).
