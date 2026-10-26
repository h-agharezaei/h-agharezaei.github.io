+++
title = "Dead tuple"
summary = "A row version that no current or future transaction can see any more, but that still occupies space until VACUUM removes it."
category = "Databases"
related = ["mvcc", "vacuum", "table-bloat"]
posts = ["db-mvcc-vacuum"]
+++

Updates and deletes create dead tuples. While an old transaction could still see a version, it is dead but not yet removable.
