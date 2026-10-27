+++
title = "Deny by default"
summary = "A route or action is forbidden until a rule explicitly allows it."
category = "Security"
related = ["authorization", "rbac"]
posts = ["sec-authorization-rbac-idor"]
+++

Instead of remembering to protect each new route, every route requires authentication and a permission unless it is explicitly listed as public. Forgetting then fails closed, not open.
