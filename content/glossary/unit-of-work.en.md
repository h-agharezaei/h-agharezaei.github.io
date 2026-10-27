+++
title = "Unit of work"
summary = "A pattern where an object tracks changes and writes them together in one transaction."
category = "Python"
related = ["orm", "transaction"]
posts = ["py-sqlalchemy-postgres"]
+++

SQLAlchemy's Session is a unit of work: you add and modify objects, and it emits the INSERT/UPDATE statements when it flushes, in dependency order. Commit makes them permanent; rollback discards them.
