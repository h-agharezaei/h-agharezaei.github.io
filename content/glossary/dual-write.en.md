+++
title = "Dual write"
summary = "writing the old and new form of data at once."
category = "Distributed"
related = ["expand-contract", "backfill"]
posts = ["ds-deployment-strategies"]
+++

During a migration the new code writes both the old column and the new one, so old and new versions can read the same rows. Dual writing to two different systems is a different, riskier thing because there is no shared transaction.
