+++
date = '2027-01-26T10:00:00+03:30'
draft = false
title = 'Project structure and config in Node.js'
description = 'Node.js project structure and config: a layered layout, subpath imports, validated env config, --env-file, parseArgs, secret redaction and a node:test.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "config", "project-structure", "environment-variables", "parseargs"]
cover = { image = "/images/covers/node-project-structure-config.png", alt = "Project structure and config in Node.js", hiddenInSingle = true }
+++

In the previous post, [Testing in Node.js with node:test](/posts/node-testing-builtin/), I tested small functions. Now I want a project shape that stays testable as it grows, and configuration that fails loudly. This is the Node counterpart of [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/) and [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). It builds on the [HTTP server](/posts/node-http-server/) and [ESM modules](/posts/node-modules-esm-cjs/).

> Node v20.13.1. The code is a local example (an ESM project, no dependencies); all outputs are copied from real runs on loopback. I took no timings because the machine was busy.

## A layout and a composition root

```text
src/config.js        loadConfig, redact
src/routes/orders.js HTTP only: parse request, call service, write response
src/services/orders.js  business rules
src/repos/orders.js  storage (in memory here)
src/main.js          wires everything
```

Routes know services, services know repos, nobody imports `main.js`. Each layer is a factory that receives what it needs, and `main.js` is the {{< term "composition-root" "composition root" >}}, the only place that knows every concrete piece:

```js
const repo = newOrdersRepo();
const service = newOrdersService({ repo, newId: () => randomUUID().slice(0, 8) });
const server = http.createServer(ordersRoutes(service));
```

This is plain {{< term "dependency-injection" "dependency injection" >}} with arguments, no framework. A test passes a fake repo or a fixed `newId`.

## Subpath imports

Deep `../../services/orders.js` paths get ugly. The `imports` field of `package.json` defines {{< term "subpath-imports" "subpath imports" >}}:

```json
"imports": { "#config": "./src/config.js", "#services/*": "./src/services/*.js" }
```

I resolved one for real, and one that is not defined:

```text
import.meta.resolve("#services/orders") -> <demo>/src/services/orders.js
import("#nope/x")                       -> ERR_PACKAGE_IMPORT_NOT_DEFINED
```

Names must start with `#`, and they work only inside your own package.

## Environment values are strings

{{< term "environment-variable" "Environment variables" >}} are always strings:

```text
typeof process.env.N  -> string      (I assigned the number 8080)
process.env.F = false -> "false"     truthy!  process.env.N + 1 -> 80801
process.env.U = undefined -> "undefined"
```

So `if (process.env.DEBUG)` is true for `DEBUG=false`, and `PORT + 1` concatenates. You must parse every value.

## loadConfig: all problems at once

`loadConfig({ env, file, argv })` is a pure function: no `process.env` inside, so tests pass their own. It layers defaults, then a file object, then env, then flags, parses each value, collects every problem and throws once (the same "report everything" idea as the Go post). `main.js` prints it and exits with code 2. Real runs:

```text
$ node src/main.js
invalid config:
  - APP_API_KEY: required
exit=2

$ APP_PORT=abc APP_DEBUG=yes APP_LOG_LEVEL=loud node src/main.js
invalid config:
  - APP_PORT: "abc" is not an integer
  - APP_DEBUG: "yes" is not a boolean (use true/false)
  - logLevel: "loud" must be one of debug, info, warn, error
  - APP_API_KEY: required
exit=2
```

Command-line flags come from `util.parseArgs`, with `--port`, `--host` and `--log-level` declared as string options. I parse the port myself, so `--port abc` is reported in the same list, as `--port: "abc" is not an integer`.

## .env files

Node 20.6+ has `--env-file`. With a `.env` holding `APP_API_KEY`, `APP_PORT=4100` and `APP_LOG_LEVEL`:

```text
node --env-file=.env -e '...'               -> from-file 4100
APP_PORT=5200 node --env-file=.env -e '...' -> 5200 from-file
node --env-file=nope.env -e '1'             -> node: nope.env: not found   (exit=9)
```

A real environment variable beats the file, and a missing file is an error. On 20.13.1 `process.loadEnvFile` exists too (`typeof` printed `function`) and loading the same file gave `APP_PORT` 4100. I saw no warning, but both are newer features, so re-check them when you upgrade Node.

## Never log secrets

`redact(cfg)` replaces `apiKey` and `dbUrl` with `***`. This is the real startup line, then a `curl -XPOST` created an order, then `SIGTERM`:

```text
{"level":"info","msg":"config loaded","config":{"port":4300,"host":"127.0.0.1","logLevel":"debug","dbUrl":"","apiKey":"***","debug":false}}
{"level":"info","msg":"listening","addr":"127.0.0.1:4300"}
{"level":"info","msg":"shutting down","signal":"SIGTERM"}
```

The shutdown wiring in `main.js` is the same as in the HTTP server post: on a signal, `server.close()` and `closeIdleConnections()`, then exit.

## Testing loadConfig

Because the function takes its inputs, the test is short (`npm test`, four tests, all passing). It checks defaults, the file < env < flags order, that one bad input reports all four problems, and that `redact` hides the key:

```js
const cfg = loadConfig({ file: { port: 1111 }, env: { ...base, APP_PORT: '2222' }, argv: ['--port', '3333'] });
assert.equal(cfg.port, 3333);
```

## A few things to watch

- `NODE_ENV` only sets a string. Node itself does nothing with it; according to the docs, some libraries (Express, for example) change behavior. I printed `undefined` without it and `production` with it. Do not branch your own logic on it; use explicit settings.
- Keep `.env` out of git and never commit real secrets.
- Do not read `process.env` all over the code; read it once in `loadConfig`.
- Validate hand-written config like this for a few variables; for request bodies and bigger schemas see Input validation with Zod later in the series.

## Exercise

Add `APP_TIMEOUT_MS` (integer, default 5000, must be above 0) and a `--timeout-ms` flag. Add tests for the new range error and for precedence, and check that a bad value is reported together with the others.

## What's next

The next post is Postgres from Node.js with pg: connecting this config's `dbUrl` to a real database.
