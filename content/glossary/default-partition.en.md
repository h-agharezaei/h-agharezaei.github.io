+++
title = "Default partition"
summary = "A partition that receives rows that match no other partition of the table."
category = "Databases"
related = ["partitioning"]
posts = ["db-partitioning"]
+++

A partition that receives rows that match no other partition of the table. It avoids insert errors, but creating a new partition then has to scan the default one to prove no row belongs to the new range. See [partitioning](/glossary/partitioning/).
