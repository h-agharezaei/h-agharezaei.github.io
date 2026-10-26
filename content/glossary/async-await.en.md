+++
title = "async/await"
summary = "Syntax that lets you write code on top of promises as if it were sequential."
category = "Node.js"
related = ["promise", "event-loop"]
posts = ["node-promises-async-await"]
+++

An `async` function always returns a [promise](/glossary/promise/). `await` pauses only that function until the promise settles; the thread stays free for the [event loop](/glossary/event-loop/).
