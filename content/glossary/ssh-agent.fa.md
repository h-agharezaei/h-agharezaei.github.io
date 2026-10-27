+++
title = "ssh-agent"
summary = "فرایندی که کلیدهای خصوصی باز‌شده را در حافظه نگه می‌دارد و از طرف ssh امضا می‌کند."
category = "Linux"
fa_title = "ssh-agent"
related = ["ssh-key-pair"]
posts = ["linux-ssh-keys"]
+++

passphrase را یک بار می‌زنید و ssh از طریق یک سوکت از agent می‌خواهد امضا کند. هر کس به آن سوکت دسترسی داشته باشد می‌تواند به نام شما امضا کند؛ برای همین forward کردن agent به میزبان نامطمئن خطرناک است.
