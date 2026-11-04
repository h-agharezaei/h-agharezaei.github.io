+++
title = "Type-state pattern"
summary = "Encoding the state of an object in its type, so calling a method that is not allowed in the current state does not compile."
category = "Rust"
related = ["newtype", "phantom-data", "ownership"]
posts = ["rust-typestate-patterns"]
+++

Instead of a field such as `status: Status` that you check at runtime, you make the state part of the type: `Order<Draft>`, `Order<Paid>`. Only the methods that make sense in a state are defined for that type, so `ship` exists on `Order<Paid>` and not on `Order<Draft>`. A method that moves from one state to the next takes `self` by value and returns the new type, so the old state cannot be used again.
