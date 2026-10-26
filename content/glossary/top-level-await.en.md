+++
title = "Top-level await"
summary = "using `await` directly at the top of an ES module, outside any async function."
category = "Node.js"
related = ["esm"]
posts = ["node-modules-esm-cjs"]
+++

Using `await` directly at the top of an ES module, outside any async function. It works only in ES modules; modules that import this one wait until it finishes.
