+++
date = '2026-11-27T10:00:00+03:30'
draft = false
title = 'npm, package.json and lockfiles'
description = 'npm and package.json explained with real runs: dependency types, semver ranges, package-lock.json, npm ci failures, audit and what npm pack publishes.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "npm", "package-json", "semver", "lockfile"]
cover = { image = "/images/covers/node-npm-package-json.png", alt = "npm, package.json and lockfiles", hiddenInSingle = true }
+++

Every Node.js project starts with {{< term "npm" "npm" >}} and a `package.json`, and most production surprises ("it works on my machine") come from not understanding them. This is post 3 of the Node.js series. In the previous post, [Modules: ESM and CommonJS](/posts/node-modules-esm-cjs/), we saw how Node loads code; here we see how code from other people gets to your disk. The [event loop](/posts/node-event-loop/) post is the base for the series.

> Run with Node v20.13.1 and npm 10.5.2 in a fresh local demo folder, against the real registry. Outputs are copied from real runs; registry results are "as of the day I ran them".

## package.json, field by field

`npm init -y` writes a skeleton. I then added a few fields with `npm pkg set`:

- `name`, `version`: identity of the package. `private: true` makes `npm publish` refuse, which protects applications.
- `type`: `commonjs` or `module`, which decides how `.js` files load (previous post).
- `engines`: the Node versions you support. npm only warns unless `engine-strict` is set.
- `scripts`: named commands. `exports` and `main`: what `require`/`import` of your package resolves to. `files`: what gets published.

```json
"scripts": { "hello": "node -e \"console.log('hello')\"", "prehello": "echo pre", "posthello": "echo post" }
```

`npm run hello` runs `prehello`, then `hello`, then `posthello`, and the output order was `pre`, `hello`, `post`. `npx <tool>` runs a binary from a package, using the local `node_modules` first.

## Four kinds of dependencies

I installed `semver` and `ms` as dependencies and `prettier` as a dev dependency (`npm install -D`).

- `dependencies`: needed at runtime.
- `devDependencies`: tooling for development and tests.
- `peerDependencies`: "the host project must provide this", typical for plugins.
- `optionalDependencies`: install failure is tolerated.

```text
$ npm ls --omit=dev
├── ms@2.1.3
└── semver@7.6.0
```

Plain `npm ls` also lists `prettier@3.2.5`. `npm ci --omit=dev` (or `npm install --omit=dev`) is how a production image skips dev tools.

## Semver ranges

{{< term "semver" "Semantic versioning" >}} is MAJOR.MINOR.PATCH. I asked the `semver` package itself what each range accepts:

```js
const semver = require('semver');
const ranges = ['^1.2.3', '~1.2.3', '1.2.3', '^0.2.3'];
const vers = ['1.2.3', '1.2.9', '1.3.0', '2.0.0', '0.2.9', '0.3.0'];
for (const r of ranges) console.log(r.padEnd(7), vers.filter(v => semver.satisfies(v, r)).join(' '));
```

```text
^1.2.3  1.2.3 1.2.9 1.3.0
~1.2.3  1.2.3 1.2.9
1.2.3   1.2.3
^0.2.3  0.2.9
```

`^` allows minor and patch updates, `~` only patch, a bare version is exact, and below 1.0.0 `^` is much stricter. The command-line form is `npx semver -r '^1.2.3' 1.9.0 2.0.0`, which printed only `1.9.0`.

## The lockfile

A range says what is allowed; the {{< term "lockfile" "lockfile" >}} records what was chosen. This is the entry for `semver` in `package-lock.json`:

```json
"node_modules/semver": {
  "version": "7.6.0",
  "resolved": "https://registry.npmjs.org/semver/-/semver-7.6.0.tgz",
  "integrity": "sha512-EnwXhrlwXMk9gKu5/...",
  "dependencies": { "lru-cache": "^6.0.0" }
}
```

It stores the exact version, the download URL and an integrity hash that npm verifies. Commit it for applications, so laptops and CI install the same tree. `npm ls --all` shows that `semver` brought {{< term "transitive-dependency" "transitive dependencies" >}}: `lru-cache@6.0.0` and `yallist@4.0.0`. They sit flat in the top-level `node_modules`, next to `ms` and `prettier`. I did not produce a case with two versions of one package, so I show no deduplication example.

## npm install vs npm ci

`npm install` may change the lockfile. `npm ci` deletes `node_modules`, installs exactly what the lockfile says, and fails if the two files disagree. I changed `ms` in `package.json` to the exact version `1.0.0` without touching the lock:

```text
npm ERR! code EUSAGE
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json
 or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install`
 before continuing.
npm ERR! Invalid: lock file's ms@2.1.3 does not satisfy ms@1.0.0
```

(I joined one long line.) Use `npm ci` in CI: that failure is the point.

## Outdated, view and audit

As of the day I ran them:

```text
$ npm outdated
Package   Current  Wanted  Latest
prettier    3.2.5  3.9.10  3.9.10
semver      7.6.0   7.8.5   7.8.5
```

`npm view ms dist-tags` printed `latest: '2.1.3'` plus beta, canary and nightly tags; `npm view semver@7 version` lists every 7.x. `npm audit` printed `found 0 vulnerabilities`. It queries the registry, so it needs network access and the answer changes over time: a clean result today proves nothing about next week.

## What gets published

In a second folder I had `lib/index.js`, `test/t.js`, `.env` and `NOTES.md`, with `"files": ["lib"]`. `npm pack --dry-run` listed only `lib/index.js` and `package.json`. Without `files`, npm falls back to rules such as `.npmignore`, so always check with a dry run before publishing. Other tools (pnpm, yarn) and `.npmrc` for registry settings exist; I did not use them here.

## A few things to watch

- Commit `package-lock.json`; never edit it by hand.
- Use `npm ci` in CI and Docker builds.
- `^` trusts maintainers to follow semver; the lockfile is your real safety net.
- Install scripts of dependencies run code on your machine; review what you add.
- `npm audit` output is a snapshot, not a guarantee.

## Exercise

Create a project, install `ms`, then edit its range in `package.json` to something the lock cannot satisfy and read the `npm ci` error. Then add a `files` field and check it with `npm pack --dry-run`.

## What's next

Next: "Promises and async/await in Node.js".
