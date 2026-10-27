+++
title = "RBAC"
summary = "Role-based access control: users get roles, roles map to permissions."
category = "Security"
related = ["authorization", "deny-by-default"]
posts = ["sec-authorization-rbac-idor"]
+++

In RBAC a user has a role (viewer, editor, admin) and each role maps to a set of permissions such as `doc:delete`. Code checks permissions, not role names, so roles can change without touching handlers.
