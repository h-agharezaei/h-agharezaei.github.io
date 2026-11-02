+++
title = "delegatecall"
summary = "فراخوانی‌ای در EVM که کد قرارداد دیگری را روی storage صدازننده اجرا می‌کند و msg.sender و msg.value را نگه می‌دارد."
category = "Blockchain"
fa_title = "delegatecall"
related = ["proxy-pattern", "evm", "storage-collision"]
posts = ["bc-gas-optimization-proxies"]
+++

همین است که [proxy](/fa/glossary/proxy-pattern/) را ممکن می‌کند. چون کد در slotهای صدازننده می‌نویسد، دو طرف باید سر چیدمان storage توافق داشته باشند.
