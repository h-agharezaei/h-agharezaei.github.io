+++
title = "Value object"
summary = "An immutable object with no identity, compared by its values, such as money or an email address."
category = "Engineering"
related = ["aggregate", "domain-driven-design"]
posts = ["eng-ddd-basics"]
+++

Two `Money` values with the same amount and currency are equal. A constructor validates them, so an invalid value cannot exist.
