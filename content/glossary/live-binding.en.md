+++
title = "Live binding"
summary = "an ES module import that points at the exporting module's variable itself, not at a copy of its value."
category = "Node.js"
related = ["esm"]
posts = ["node-modules-esm-cjs"]
+++

An ES module import that points at the exporting module's variable itself, not at a copy of its value. If the exporter changes `export let count`, every importer sees the new value. Importers cannot assign to it.
