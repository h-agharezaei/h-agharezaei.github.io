+++
date = '2026-11-27T10:00:00+03:30'
draft = false
title = 'npm, package.json and lockfiles'
description = 'npm and package.json explained with real runs: dependency types, semver ranges, package-lock.json, npm ci failures, audit and what npm pack publishes.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "npm", "package-json", "semver", "lockfile"]
cover = { image = "/images/covers/node-npm-package-json.png", alt = "npm, package.json and lockfiles", hiddenInSingle = true }
+++

Picture two machines, the same `package.json`, and the same command: `npm install`. On your laptop the app works. In CI it breaks, because CI installed a newer minor version of one library that was released in between. Nobody changed any file, and still the two machines ended up with different code. This is the kind of surprise that comes from not knowing exactly what {{< term "npm" "npm" >}} and `package.json` promise you, and what they do not.

The core idea fits in two sentences. `package.json` says **what you are willing to accept**: a name and a *range* of versions for every library. The {{< term "lockfile" "lockfile" >}} (`package-lock.json`) records **what was actually installed**, down to the exact version. A range is a wish, a lockfile is a receipt.

[Modules: ESM and CommonJS](/posts/node-modules-esm-cjs/) showed how Node loads code once it is on disk; here we see how other people's code gets there. If you want to know why the series starts from the loop, that is the [event loop](/posts/node-event-loop/) post.

> Run with Node v20.13.1 and npm 10.5.2 in a fresh local demo folder, against the real npm registry (the public server where packages are published). The commands were first run in the original session, and I re-ran them for this version in a scratch copy of the demo with `npm ci --ignore-scripts`. Registry results (latest versions, `npm audit`) are "as of the day I ran them" and will change.

## package.json, field by field

A **package** is a folder with a `package.json` file that describes it. `npm init -y` writes a skeleton, and I then added a few fields with `npm pkg set`. The ones that matter most:

- `name` and `version`: the identity of the package. `private: true` makes `npm publish` refuse to publish it, which protects an application from being published by accident.
- `type`: `commonjs` or `module`. It decides how `.js` files in the package are loaded (see the previous post).
- `engines`: the Node versions you support. According to the npm docs this is only advisory: npm warns, unless you set `engine-strict`.
- `scripts`: named commands you run with `npm run <name>`.
- `main` and `exports`: which file someone gets when they `require` or `import` your package.
- `files`: which files go into the published package. More on that at the end, because a missing `files` can leak a secret.

Scripts are the easiest to try. Here is a script with two helper scripts named `pre...` and `post...`:

```json
"scripts": { "hello": "node -e \"console.log('hello')\"", "prehello": "echo pre", "posthello": "echo post" }
```

npm runs the `pre` and `post` versions automatically around the script with the same name. `npm run hello` printed `pre`, `hello`, `post`, in that order. And `npx <tool>` runs a program that a package provides, using the copy in the local `node_modules` first.

## Four kinds of dependencies

A **dependency** is a package that yours needs. In the demo I installed `semver` and `ms` as ordinary dependencies and `prettier` (a code formatter) with `npm install -D`, which puts it in a different list. Where a package is listed tells npm when it is needed:

- `dependencies`: needed when the program runs.
- `devDependencies`: tools for development and tests only, such as a formatter.
- `peerDependencies`: "the project that uses me must provide this", typical for plugins. A plugin for a framework should use the framework the host project already has, not bring its own.
- `optionalDependencies`: if installing it fails, npm carries on.

This is what the runtime dependencies looked like:

```text
$ npm ls --omit=dev
├── ms@2.1.3
└── semver@7.6.0
```

Plain `npm ls` also lists `prettier@3.2.5`. In a production image you do not want the dev tools, so you install with `npm ci --omit=dev` (or `npm install --omit=dev`).

## Semver ranges

Why does the version have three numbers? {{< term "semver" "Semantic versioning" >}} gives them a meaning: **MAJOR.MINOR.PATCH**. A patch (1.2.3 to 1.2.4) is a bug fix, a minor (1.2.3 to 1.3.0) adds features without breaking anything, and a major (1.x to 2.0) may break your code. That is the promise a library author makes, and ranges in `package.json` build on it.

To see what each range really accepts, I asked the `semver` package itself. The script checks four ranges against six versions:

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

Each line shows a range and the versions from the list that it accepts:

- `^1.2.3` (caret) accepts new minor and patch versions, but not 2.0.0.
- `~1.2.3` (tilde) accepts only new patch versions.
- `1.2.3` without a symbol means exactly that version.
- `^0.2.3` is much stricter: below 1.0.0 everything may still change, so the caret only lets the last number move. That is why only `0.2.9` matched, not `0.3.0`.

The command-line form is `npx semver -r '^1.2.3' 1.9.0 2.0.0`, which printed only `1.9.0`.

## The lockfile

Now back to the opening. A range such as `^7.6.0` allows many versions, and which one you get depends on the day you install. The lockfile removes that luck. This is the entry for `semver` in `package-lock.json`, shortened a bit (I cut the hash and a `bin` field):

```json
"node_modules/semver": {
  "version": "7.6.0",
  "resolved": "https://registry.npmjs.org/semver/-/semver-7.6.0.tgz",
  "integrity": "sha512-EnwXhrlwXMk9gKu5/...",
  "dependencies": { "lru-cache": "^6.0.0" }
}
```

It stores the exact `version`, the `resolved` address to download it from, and an `integrity` hash that npm checks after downloading, so a changed file is noticed. For applications, commit the lockfile: then laptops and CI install the same tree.

`npm ls --all` shows something else: `semver` itself needs other packages. These are its {{< term "transitive-dependency" "transitive dependencies" >}}, the dependencies of your dependencies: `lru-cache@6.0.0`, which needs `yallist@4.0.0`. npm placed them flat in the top-level `node_modules`, next to `ms` and `prettier`. I did not produce a case with two versions of one package, so I show no deduplication example.

## npm install and npm ci

There are two ways to install, and they treat the lockfile differently. `npm install` is allowed to change the lockfile. `npm ci` ("clean install") deletes `node_modules`, installs exactly what the lockfile says, and fails if `package.json` and the lockfile disagree. To see that failure I changed `ms` in `package.json` to the exact version `1.0.0` without touching the lockfile and ran `npm ci`:

```text
npm ERR! code EUSAGE
npm ERR! 
npm ERR! `npm ci` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with `npm install` before continuing.
npm ERR! 
npm ERR! Invalid: lock file's ms@2.1.3 does not satisfy ms@1.0.0
```

npm printed a usage help after this, which I left out. The last line is the important one: the lockfile has `ms@2.1.3` and `package.json` now wants `1.0.0`. In CI that failure is exactly what you want: it stops you from shipping something other than what you tested.

## Outdated, view and audit

Three read-only commands help you keep up with the registry. In my re-run (as of that day):

```text
$ npm outdated
Package   Current  Wanted  Latest  Location               Depended by
prettier    3.2.5  3.9.10  3.9.10  node_modules/prettier  demo
semver      7.6.0   7.8.6   7.8.6  node_modules/semver    demo
```

`Current` is what is installed, `Wanted` is the highest version your range allows, and `Latest` is the newest version in the registry. Here they match, because both ranges are caret ranges and the newest releases are still inside them.

`npm view ms dist-tags` printed `latest: '2.1.3'` plus beta, canary and nightly tags, and `npm view semver@7 version` lists every 7.x version. `npm audit` printed `found 0 vulnerabilities`. It queries the registry, so it needs network access and its answer changes over time: a clean result today proves nothing about next week.

## What gets published

In a second folder I had `lib/index.js`, `test/t.js`, a `.env` file with a fake secret and `NOTES.md`, with `"files": ["lib"]`. `npm pack --dry-run` shows what would go into the package without publishing anything, and it listed only `lib/index.js` and `package.json`.

Then I removed the `files` field in a scratch copy and ran the dry run again. This time it listed all five files, including `.env`. So without `files`, nothing stops a secret from being published; npm falls back to ignore-file rules such as `.npmignore` or `.gitignore`, and my folder had neither. Always check with a dry run before you publish. Other tools such as pnpm and yarn exist, and `.npmrc` holds registry settings; I did not use them here.

## Where dependencies surprise you

- **Editing `package-lock.json` by hand.** Commit it, but let npm write it. A hand-edited hash or version is a bug nobody will find.
- **Using `npm install` in CI or Docker builds.** Use `npm ci`, so the build fails when the files disagree instead of quietly installing something new.
- **Trusting `^` too much.** A caret trusts every maintainer to follow semver perfectly. The lockfile is your real safety net.
- **Adding dependencies without looking.** Install scripts of a dependency run code on your machine during install (that is why I used `--ignore-scripts` for my re-run). Review what you add.
- **Treating `npm audit` as a guarantee.** It is a snapshot of what is known today.

## Exercise

Create a project, install `ms`, then edit its range in `package.json` to something the lockfile cannot satisfy and read the `npm ci` error. Then add a `files` field and check it with `npm pack --dry-run`.

## What's next

"Promises and async/await in Node.js": with packages in place, the series returns to async code itself.
