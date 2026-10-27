+++
title = 'overlayfs'
summary = 'A Linux filesystem that stacks a writable layer over read-only layers; container images use it for their layers.'
category = 'Linux'
related = ["container"]
posts = ["linux-cgroups-namespaces"]
+++

Reads fall through to the lower layers and writes go to the upper one. Runtimes commonly use it so many containers can share one image.
