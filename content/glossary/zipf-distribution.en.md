+++
title = "Zipf distribution"
summary = "A skewed access pattern where a few keys get most requests and a long tail gets few."
category = "Distributed"
related = ["lru-cache", "hot-key"]
posts = ["ds-capacity-estimation"]
+++

The rank-r key is requested with probability proportional to 1/r^s. Real traffic is often skewed like this, which is why a small cache can have a high hit rate.
