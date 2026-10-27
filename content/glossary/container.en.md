+++
title = 'Container'
summary = 'A normal Linux process (or group) started with its own namespaces and cgroup limits, usually from an image.'
category = 'Linux'
related = ["namespace", "cgroup", "overlayfs"]
posts = ["linux-cgroups-namespaces"]
+++

There is no container object in the kernel. A runtime combines namespaces, cgroups and a root filesystem, often following the OCI runtime specification.
