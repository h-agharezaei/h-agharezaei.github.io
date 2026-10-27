+++
title = "Secret scanning"
summary = "Searching code and git history for credentials by pattern and entropy."
category = "Security"
related = ["git-hook"]
posts = ["sec-secrets-management"]
+++

A scanner matches known formats (like cloud key prefixes) and flags random-looking strings by Shannon entropy. It trades false positives for coverage. Real tools include gitleaks and trufflehog.
