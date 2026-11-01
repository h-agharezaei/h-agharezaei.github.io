+++
title = "tx.origin"
summary = "حسابی که تراکنش را امضا کرده، برخلاف msg.sender که صدازننده‌ی مستقیم است؛ برای احراز هویت ناامن است."
category = "Blockchain"
fa_title = "tx.origin"
related = ["access-control", "smart-contract"]
posts = ["bc-contract-security"]
+++

اگر کیف‌پولی `tx.origin == owner` را چک کند، هر قراردادی که مالک فریب بخورد و صدایش بزند می‌تواند کیف‌پول را صدا بزند و از چک رد شود. از `msg.sender` استفاده کنید.
