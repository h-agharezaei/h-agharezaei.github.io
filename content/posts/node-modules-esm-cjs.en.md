+++
date = '2026-11-21T10:00:00+03:30'
draft = false
title = 'Modules: ESM and CommonJS'
description = 'Node.js ESM and CommonJS compared with real runs: how Node picks a system, interop, ERR_REQUIRE_ESM, exports maps, caching and circular imports.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "modules", "esm", "commonjs", "javascript"]
cover = { image = "/images/covers/node-modules-esm-cjs.png", alt = "Modules: ESM and CommonJS", hiddenInSingle = true }
+++

You copy a small example from a tutorial, run `node app.js`, and Node answers `SyntaxError: Cannot use import statement outside a module`. You change `import` to `require`, run another file, and now you get `require is not defined`. Nothing is wrong with the code in either case. You are meeting the fact that Node.js has **two module systems**, and mixing them is where most "it works on my machine" import errors come from.

A **module** is just a file that keeps its own variables private and chooses what to share with other files. Every language has some version of this. If you come from Go, think of [packages and modules](/posts/go-packages-modules/), where there is exactly one system. Node has two, for historical reasons: the older one was built into Node from the start, and the newer one was added to JavaScript itself later. Once you know how Node decides between them, the errors stop being mysterious. In [the post about the event loop](/posts/node-event-loop/) we looked at how code runs; here we look at how files find and load each other.

> Everything below was run with Node v20.13.1 in a temporary project, and the paths in the outputs were replaced with `<tmp>`. Newer Node versions changed some of this (for example, they can `require()` an ES module in some cases; check the Node.js docs for your version), but I only ran 20.13.1.

## Two systems, one small example

{{< term "commonjs" "CommonJS" >}} is the older system. A file shares things with `module.exports`, and another file loads them with `require()`:

```js
// math.cjs
module.exports = { add: (a, b) => a + b };

// main.cjs
const { add } = require('./math.cjs');
```

{{< term "esm" "ES modules" >}} (ESM) is the newer, standard system. The same idea is written with `export` and `import`:

```js
// math.mjs
export const add = (a, b) => a + b;

// main.mjs
import { add } from './math.mjs';
```

Now the important question: when Node opens a file, how does it know which system the file uses? It decides per file:

- `.mjs` is always ESM.
- `.cjs` is always CommonJS.
- `.js` follows the nearest `package.json` going up the folders: `"type": "module"` means ESM, anything else (including no `"type"`) means CommonJS.

If your file and the decision disagree, you get the two errors from the opening. Both are real outputs:

```text
SyntaxError: Cannot use import statement outside a module
ReferenceError: require is not defined in ES module scope, you can use import instead
```

The first came from `import` in a `.js` file with no `"type"` (CommonJS by default). The second came from `require` in a `.js` file with `"type": "module"`. The first I reproduced in a scratch folder without a `package.json`; the second is the demo folder's own `basic/y.js`. Modern Node even adds a line explaining why the file was treated as an ES module and suggests renaming it to `.cjs`.

## What each side has

The two systems do not only look different, they give your code different built-in names. This `main.cjs` checks which names exist:

```js
// main.cjs
console.log(typeof __dirname, typeof __filename, typeof require, typeof module);
```

It prints `string string function object`. In an ES module the same `typeof` check on `__dirname`, `require` and `module` prints `undefined undefined undefined`. Those names simply do not exist there. ESM has `import.meta` instead:

```text
import.meta.url      file:///<tmp>/basic/main.mjs
import.meta.dirname  <tmp>/basic
import.meta.filename <tmp>/basic/main.mjs
```

`import.meta.dirname` and `import.meta.filename` printed fine on 20.13.1. According to the docs they were added in 20.11, so on older Node 20 releases they would be missing (`import.meta.url` works everywhere).

ESM also allows {{< term "top-level-await" "top-level await" >}}: you can write `await` outside of any function. This line at the top of an `.mjs` file printed `top-level await: resolved`:

```js
const v = await new Promise(r => setTimeout(() => r('resolved'), 20));
console.log('top-level await:', v);
```

The same kind of line in a `.cjs` file fails with `SyntaxError: await is only valid in async functions and the top level bodies of modules`. A CommonJS file is wrapped in a function by Node and runs as ordinary code, so it cannot wait at the top.

## Importing CommonJS from ESM

In real projects you will often have both kinds side by side, so let's see how they talk to each other. First direction: an ES module imports a CommonJS file. The **default** import always works and gives you whatever `module.exports` is. **Named** imports (`import { alpha }`) work only when Node can work out the names by reading the source without running it. Two small CommonJS files show the difference:

```js
// static.cjs: exports.alpha = 1; exports.beta = () => 'beta';
import { alpha, beta } from './static.cjs';   // works

// dynamic.cjs: for (const n of ['gamma', 'delta']) module.exports[n] = n;
import { gamma } from './dynamic.cjs';        // fails
```

In `static.cjs` the names are written out plainly. In `dynamic.cjs` they are created in a loop, which Node cannot see before running the code. The failing import prints:

```text
SyntaxError: Named export 'gamma' not found. The requested module './dynamic.cjs' is a CommonJS module, which may not support all module.exports as named exports.
```

Node also prints the fix below that line. Import the default and take the names out yourself: `import whole from './dynamic.cjs'; const { gamma } = whole;` printed `gamma`.

## Requiring ESM from CommonJS

The other direction is harder. On 20.13.1 a `require('./esm.mjs')` throws:

```text
Error [ERR_REQUIRE_ESM]: require() of ES Module <tmp>/interop/esm.mjs not supported.
Instead change the require of <tmp>/interop/esm.mjs to a dynamic import() which is available in all CommonJS modules.
```

The reason is that loading an ES module can be asynchronous (remember top-level await), while `require()` must return a value right away. The workaround is the dynamic `import()`, a function that returns a {{< term "promise" "promise" >}}: `import('./esm.mjs').then(m => console.log(m.x))` printed `1`. The reverse trick also exists: `createRequire(import.meta.url)` gives an ES module a working `require`, and `require('./static.cjs').alpha` through it printed `1`.

## Packages: the exports map

So far these were our own files. A published package has an extra problem: it may ship both a CommonJS build and an ESM build, and it needs to tell Node which to use. It does that with the `exports` field in its `package.json`, using {{< term "conditional-exports" "conditional exports" >}}. Here is my tiny local package named `dual`:

```json
"exports": {
  ".": { "import": "./lib/index.mjs", "require": "./lib/index.cjs" }
}
```

The `"."` entry is what you get from `import 'dual'`, and the condition names choose the file by how it is loaded. `import { kind } from 'dual'` printed `esm build`, and `require('dual').kind` printed `cjs build`.

The map has a second job: files that are not listed are sealed. `require('dual/lib/internal.cjs')` threw `ERR_PACKAGE_PATH_NOT_EXPORTED`, even though the file is really there:

```text
Error [ERR_PACKAGE_PATH_NOT_EXPORTED]: Package subpath './lib/internal.cjs' is not defined by "exports" in <tmp>/exports/node_modules/dual/package.json
```

## Caching and circular imports

When two files load the same module, does its code run twice? No. A CommonJS module runs once and its result is stored in `require.cache`. My `math.cjs` prints `math.cjs evaluated` when it runs. It was required twice and printed that line only once, and `Object.keys(require.cache)` listed `main.cjs` and `math.cjs`. ESM caches too: `lib.mjs evaluated` appeared once for two imports.

Caching leads to an interesting case: **circular dependencies**, where `a` needs `b` and `b` needs `a`. Node cannot finish either one first. In CommonJS, `a` starts, sets `exports.done = false`, and requires `b`. When `b` requires `a`, it receives `a`'s **partial** `exports`: whatever `a` had set so far.

```text
in b, a.done = false
in a, b.done = true
```

`b` saw `a.done = false` because `a` had not finished yet. Nothing failed, but `b` worked with an unfinished module, which is easy to miss.

ESM handles the same shape differently. With `const` exports, the code failed with an error about {{< term "live-binding" "live bindings" >}}. In ESM, an import is not a copy but a live view of the other module's variable, and here `b` ran before `a` had set it:

```text
ReferenceError: Cannot access 'aval' before initialization
```

Live bindings also show up without circles. With `export let count` in an ES module, the importer printed `0` and then `1` after calling `inc()`: it sees the current value. In CommonJS, `const { count } = require(...)` copied the number once, and I got `0` and then `0`.

## The node: prefix

One last detail. Built-in modules can be written with a `node:` prefix. `import fs from 'fs'` and `import nfs from 'node:fs'` give the same object (the check printed `true`). The prefix makes it clear that you mean the built-in and not a package from npm, and for `node:test` it is required: in a scratch file, `require('test')` gave `MODULE_NOT_FOUND`, while `require('node:test')` worked.

## Where interop breaks

- **Mixing systems by accident.** Pick one per project and set `"type"` explicitly in `package.json`. This is my own judgment, not a rule: write new code as ESM and use `.cjs` only where a tool demands it.
- **Assuming named imports from CommonJS.** They depend on Node being able to read the names statically. When unsure, use the default import and destructure it.
- **Circular imports.** They are a design smell either way. ESM turns them into loud errors, CommonJS into silently incomplete objects.
- **Publishing a package without `exports`.** Then every internal file is public API, and you cannot move any of them without breaking someone.

## Exercise

Make a package with `exports` for `import` and `require`, plus a `"./package.json"` entry. Consume it from an `.mjs` and a `.cjs` file, then try a deep import of a file you did not export and read the error.

## What's next

"npm, package.json and lockfiles": we have seen our own modules, and next come the packages that arrive from outside and whose versions need pinning.
