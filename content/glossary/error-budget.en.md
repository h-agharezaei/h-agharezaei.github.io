+++
title = "Error budget"
summary = "The amount of failure an SLO allows in a window; spending it is how reliability is traded against change."
category = "Engineering"
related = ["slo", "postmortem"]
posts = ["eng-postmortems-blameless", "eng-sli-slo-error-budgets"]
+++

With a 99.5% SLO, 0.5% of requests may fail in the window. An incident burns part of the budget; burning it all is a signal to slow risky changes.
