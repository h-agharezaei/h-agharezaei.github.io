+++
title = "Shallow clone"
summary = "A clone with truncated history, e.g. git clone --depth 1."
category = "Git"
related = ["partial-clone"]
posts = ["git-workflows-packfiles"]
+++

`git clone --depth 1` downloads only the latest commit. It is fast and small, but history commands see little. `git fetch --unshallow` restores the rest. See also [partial clone](/glossary/partial-clone/).
