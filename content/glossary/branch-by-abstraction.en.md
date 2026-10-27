+++
title = "Branch by abstraction"
summary = "replace code in small steps by hiding old and new behind one interface."
category = "Engineering"
related = ["feature-flag","trunk-based-development","characterization-test"]
posts = ["eng-feature-flags-trunk-based", "eng-legacy-code"]
+++

Branch by abstraction puts an interface in front of the old implementation, adds the new one beside it, and switches between them (often with a feature flag). The rewrite is merged to the main branch in small steps instead of living on a long branch.
