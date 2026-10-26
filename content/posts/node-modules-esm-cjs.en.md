+++
date = '2026-11-21T10:00:00+03:30'
draft = false
title = 'Modules: ESM and CommonJS'
description = 'Node.js ESM and CommonJS compared with real runs: how Node picks a system, interop, ERR_REQUIRE_ESM, exports maps, caching and circular imports.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "modules", "esm", "commonjs", "javascript"]
cover = { image = "/images/covers/node-modules-esm-cjs.png", alt = "Modules: ESM and CommonJS", hiddenInSingle = true }
+++

Node.js has two module systems, and mixing them is where most "it works on my machine" import errors come from. In the [previous post](/posts/node-event-loop/) we looked at how code runs; here we look at how files load. If you come from Go, compare it with [packages and modules](/posts/go-packages-modules/) in Go, where there is only one system.

> Everything below was run with Node v20.13.1 in a temporary project. Newer Node versions changed some of this, but I only ran 20.13.1.

## Two systems, one decision

{{< term "commonjs" "CommonJS" >}} uses `require()` and `module.exports`. {{< term "esm" "ES modules" >}} (ESM) use `import` and `export`. Node picks per file: `.mjs` is ESM, `.cjs` is CommonJS, and `.js` follows the nearest `package.json`: `"type": "module"` means ESM, otherwise CommonJS. With the wrong choice you get errors like these (all real):

```text
SyntaxError: Cannot use import statement outside a module
ReferenceError: require is not defined in ES module scope, you can use import instead
```

The first came from `import` in a `.js` file with no `"type"`, the second from `require` in a `.js` file with `"type": "module"`.

## What each side has

```js
// main.cjs
console.log(typeof __dirname, typeof __filename, typeof require, typeof module);
```

prints `string string function object`. In an ES module the same `typeof` check on `__dirname`, `require` and `module` prints `undefined undefined undefined`. ESM has `import.meta` instead:

```text
import.meta.url      file:///.../basic/main.mjs
import.meta.dirname  /.../basic
import.meta.filename /.../basic/main.mjs
```

`import.meta.dirname` and `filename` printed fine on 20.13.1 (they are documented since 20.11). ESM also allows {{< term "top-level-await" "top-level await" >}}: `const v = await somePromise` at the top of an `.mjs` file printed `top-level await: resolved`. The same line in a `.cjs` file gave `SyntaxError: await is only valid in async functions and the top level bodies of modules`.

## Importing CommonJS from ESM

The default import is always `module.exports`. Named imports work only if Node can detect the names statically from the source:

```js
// static.cjs: exports.alpha = 1; exports.beta = () => 'beta';
import { alpha, beta } from './static.cjs';   // works

// dynamic.cjs: for (const n of ['gamma']) module.exports[n] = n;
import { gamma } from './dynamic.cjs';        // fails
```

```text
SyntaxError: Named export 'gamma' not found. The requested module './dynamic.cjs' is a CommonJS module, which may not support all module.exports as named exports.
```

The fix is the default import plus destructuring: `import whole from './dynamic.cjs'; const { gamma } = whole;` printed `gamma`.

## Requiring ESM from CommonJS

On 20.13.1 `require('./esm.mjs')` throws:

```text
Error [ERR_REQUIRE_ESM]: require() of ES Module .../esm.mjs not supported.
Instead change the require of .../esm.mjs to a dynamic import() which is available in all CommonJS modules.
```

The workaround is dynamic `import()`, which returns a promise: `import('./esm.mjs').then(m => console.log(m.x))` printed `1`. The reverse direction also exists: `createRequire(import.meta.url)` gives an ES module a working `require`.

## Packages: the exports map

A package can ship both builds and let Node choose, using {{< term "conditional-exports" "conditional exports" >}}. My tiny local package `dual`:

```json
"exports": {
  ".": { "import": "./lib/index.mjs", "require": "./lib/index.cjs" }
}
```

`import { kind } from 'dual'` printed `esm build`, and `require('dual').kind` printed `cjs build`. Files not listed are sealed: `require('dual/lib/internal.cjs')` threw `ERR_PACKAGE_PATH_NOT_EXPORTED`.

## Caching and circular imports

A CommonJS module runs once; the result sits in `require.cache`. My `math.cjs` printed `math.cjs evaluated` once although it was required twice, and `Object.keys(require.cache)` listed `main.cjs` and `math.cjs`. ESM caches too: `lib.mjs evaluated` appeared once for two imports.

Circular dependencies differ. In CommonJS, `a` requires `b`, and `b` requires `a`, receiving a **partial** `exports`:

```text
in b, a.done = false
in a, b.done = true
```

In ESM the same shape used `const` exports and failed with a {{< term "live-binding" "live-binding" >}} error, because `b` ran before `a` initialised:

```text
ReferenceError: Cannot access 'aval' before initialization
```

Live bindings also show up with `export let count`: the importer printed `0` then `1` after `inc()`. In CommonJS, `const { count } = require(...)` copied the value, and I got `0` then `0`.

## The node: prefix

`import fs from 'fs'` and `'node:fs'` are the same object (`true`). The prefix makes built-ins explicit, and for `node:test` it is required: `require('test')` gave `MODULE_NOT_FOUND`, `require('node:test')` worked.

## A few things to watch

- Pick one system per project and set `"type"` explicitly. This is my own judgment: new code in ESM, `.cjs` only where a tool demands it.
- Do not assume named imports from CommonJS; use the default import when unsure.
- Circular imports are a design smell; ESM turns them into loud errors, CommonJS into silent `undefined`.
- Libraries should define `exports`, otherwise every internal file is public API.

## Exercise

Make a package with `exports` for `import` and `require`, plus a `"./package.json"` entry. Consume it from `.mjs` and `.cjs`, then try a deep import and read the error.

## What's next

The next post is "npm, package.json and lockfiles".
