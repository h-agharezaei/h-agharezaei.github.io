+++
title = "Roll forward"
summary = "fixing a bad release with a new release instead of reverting."
category = "Distributed"
related = ["rollback"]
posts = ["ds-deployment-strategies"]
+++

Rolling forward means shipping a fix as a new version rather than going back to the previous one. It is the usual answer when a rollback is unsafe, for example after data was written in a new format.
