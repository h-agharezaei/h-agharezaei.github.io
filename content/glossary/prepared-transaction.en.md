+++
title = "Prepared transaction"
summary = "In PostgreSQL, a transaction detached from its session by PREPARE TRANSACTION, stored on disk and finished later by COMMIT PREPARED or ROLLBACK PREPARED."
category = "Distributed"
related = ["two-phase-commit", "lock"]
posts = ["ds-saga-vs-2pc"]
+++

It survives a restart and keeps its locks until someone finishes it. It is the building block for two-phase commit managed by an external transaction manager.
