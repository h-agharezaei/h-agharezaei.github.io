+++
title = "Hinted handoff"
summary = "وقتی یک replica از کار افتاده، node دیگری نوشتن‌های آن را با یک hint نگه می‌دارد و بعد از برگشتنش تحویل می‌دهد."
category = "Distributed"
fa_title = "hinted handoff"
related = ["quorum", "replication"]
posts = ["ds-replication-quorum"]
+++

نوشتن‌ها را در قطعی کوتاه موفق نگه می‌دارد. node دارای hint یکی از replicaهای واقعی کلید نیست، پس به آن sloppy quorum می‌گویند و تضمین هم‌پوشانی [quorum](/fa/glossary/quorum/) را ضعیف می‌کند.
