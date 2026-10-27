+++
title = "Prototype pollution"
summary = "A JavaScript bug where attacker-controlled keys like __proto__ change the prototype of objects, so unrelated objects suddenly get extra properties."
category = "Node.js"
related = ["schema-validation", "mass-assignment"]
posts = ["node-validation-zod"]
+++

It usually comes from recursive merge or copy code that trusts keys from JSON. Validating input into a fresh object with a known shape removes the keys you did not declare.
