+++
title = "Raft"
summary = "یک الگوریتم consensus از leader election، تکثیر log و قوانین safety که برای فهم آسان‌تر از Paxos طراحی شده است."
category = "Distributed"
fa_title = "Raft"
related = ["consensus", "leader-election", "replicated-log"]
posts = ["ds-consensus-raft"]
+++

Raft را Ongaro و Ousterhout توصیف کرده‌اند. زمان به termها تقسیم می‌شود؛ هر term حداکثر یک leader دارد و فقط leader به log اضافه می‌کند.
