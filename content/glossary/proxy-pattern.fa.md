+++
title = "Proxy pattern"
summary = "قرارداد کوچکی که state را نگه می‌دارد و هر فراخوانی را به یک قرارداد implementation قابل تعویض می‌فرستد."
category = "Blockchain"
fa_title = "الگوی proxy"
related = ["delegatecall", "eip-1967", "storage-collision"]
posts = ["bc-gas-optimization-proxies"]
+++

کاربرها یک آدرس ثابت دارند و کد پشت آن ارتقا پیدا می‌کند. فرستادن با [delegatecall](/fa/glossary/delegatecall/) است. گونه‌هایش transparent و UUPS هستند که در جای منطق ارتقا فرق دارند.
