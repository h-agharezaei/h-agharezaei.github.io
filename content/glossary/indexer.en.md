+++
title = "Indexer"
summary = "A service that reads blocks or event logs from a node and stores them in a database that can be queried quickly."
category = "Blockchain"
related = ["event-log", "chain-reorganization", "confirmation"]
posts = ["bc-event-indexer-go"]
+++

A node answers "what happened in block N" well and "all transfers of address X" badly. An indexer keeps a cursor, must be safe to re-run, and must undo rows after a [reorg](/glossary/chain-reorganization/).
