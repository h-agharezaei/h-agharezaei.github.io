+++
date = '2027-01-26T10:00:00+03:30'
draft = false
title = 'Project structure and config in Node.js'
description = 'Node.js project structure and config: a layered layout, subpath imports, validated env config, --env-file, parseArgs, secret redaction and a node:test.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "config", "project-structure", "environment-variables", "parseargs"]
cover = { image = "/images/covers/node-project-structure-config.png", alt = "Project structure and config in Node.js", hiddenInSingle = true }
+++

Here is a bug that every Node.js developer meets sooner or later. You set `DEBUG=false` in the environment to turn debugging off, and the debug logs keep coming. The reason is that `if (process.env.DEBUG)` is true for the text `"false"`: every environment value is a string, and any non-empty string is truthy. A bug like this does not crash anything. The program just runs with the wrong setting, maybe in production, until someone notices.

So this post has two questions. How should a project be laid out so that it stays easy to change and easy to test as it grows? And how should configuration be read so that a wrong value stops the program at startup, with a clear message, instead of causing strange behaviour later? [Testing in Node.js with node:test](/posts/node-testing-builtin/) covered small functions; here I want a project shape where testing stays easy.

This is the Node counterpart of [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/) and [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). It builds on the [HTTP server](/posts/node-http-server/) and [ESM modules](/posts/node-modules-esm-cjs/).

> Node v20.13.1. The code is a local example (an ESM project with no dependencies); outputs are copied from real runs on loopback with a random free port, so the port numbers you see differ from run to run. I took no timings.

## A layout and a composition root

The idea is to give each kind of work its own place, and to let the layers only know about the layer below them:

```text
src/config.js        loadConfig, redact
src/routes/orders.js HTTP only: parse request, call service, write response
src/services/orders.js  business rules
src/repos/orders.js  storage (in memory here)
src/main.js          wires everything
```

Routes know services, services know repos, and nobody imports `main.js`. Why does this help? Suppose the route handler contained the business rules and the storage code. To test a rule you would have to start an HTTP server, and to change the database you would have to edit the handler. With layers, each part can be tested alone.

To make that possible, each layer is a *factory*: a function that receives what it needs as arguments instead of importing it. Then something must create the real pieces and connect them. That is `main.js`, which is called the {{< term "composition-root" "composition root" >}}: the only place that knows every concrete piece.

```js
const repo = newOrdersRepo();
const service = newOrdersService({ repo, newId: () => randomUUID().slice(0, 8) });
const server = http.createServer(ordersRoutes(service));
```

Read it from the top: create the storage, give it to the service (together with a function that makes ids), and give the service to the routes. This technique is called {{< term "dependency-injection" "dependency injection" >}}; here it is nothing more than function arguments, with no framework. A test can pass a fake repo, or a fixed `newId` so that the ids are predictable.

## Subpath imports

As the tree grows, paths like `../../services/orders.js` get ugly and break when you move a file. The `imports` field of `package.json` lets you define short private aliases, called {{< term "subpath-imports" "subpath imports" >}}:

```json
"imports": { "#config": "./src/config.js", "#services/*": "./src/services/*.js" }
```

(The demo's `package.json` also has `#repos/*` and `#routes/*` in the same way.) To check it, I resolved one alias for real and one that is not defined:

```text
import.meta.resolve("#services/orders") -> <demo>/src/services/orders.js
import("#nope/x")                       -> ERR_PACKAGE_IMPORT_NOT_DEFINED
```

The first line shows the alias becoming a real file path (I replaced the machine's directory with `<demo>`). The second shows that an alias that is not in the list fails with a clear error code. Alias names must start with `#`, and they work only inside your own package.

## Environment values are strings

Now back to configuration. {{< term "environment-variable" "Environment variables" >}} are named values that a process inherits from the program that started it, and they are the usual way to give a server its port, keys and settings. The catch is that they are always strings. This is what happened when I assigned other types:

```text
typeof process.env.N  -> string      (I assigned the number 8080)
process.env.F = false -> "false"     truthy!  process.env.N + 1 -> 80801
process.env.U = undefined -> "undefined"
```

I assigned the number 8080 and got back a string. `false` became the text `"false"`, which is truthy. Because `N` is a string, `process.env.N + 1` joined two strings into `80801` instead of adding. Even `undefined` became the text `"undefined"`. So you must parse every value yourself, and decide what counts as valid.

## loadConfig: all problems at once

The plan is one function, `loadConfig({ env, file, argv })`, that turns raw inputs into a clean config object. It is a pure function: it never touches `process.env` itself, so tests pass in their own inputs. It layers the sources from weakest to strongest: defaults, then a file object, then environment variables, then command-line flags. Each value is parsed, every problem is collected, and the function throws once with all of them. That is the same "report everything at once" idea as in the Go post. If you fix one error only to find the next on the next run, you lose time; here you see them all.

`main.js` catches the error, prints it and exits with code 2. (The `file` argument is there in `loadConfig`, but `main.js` does not read a config file; it passes only `process.env` and the command-line flags.) These are real runs. The first has no API key. The second has three wrong values and no key:

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

Each problem is one line that names the setting and says what is wrong. Note that `APP_DEBUG=yes` is rejected on purpose: only `true`/`false` (and `1`/`0`) are accepted, so there is no guessing.

Command-line flags come from `util.parseArgs` in the standard library, with `--port`, `--host` and `--log-level` declared as string options. I parse the port myself, so `--port abc` is reported in the same list, as `--port: "abc" is not an integer`. A port above 65535 is also caught: `port: 99999 is out of range 0-65535`.

## .env files

Typing many variables on the command line is tiring, so people keep them in a `.env` file. Node 20.6 and later can load one by itself with `--env-file`, without any package. I made a `.env` that holds `APP_API_KEY=from-file`, `APP_PORT=4100` and `APP_LOG_LEVEL=debug`, and ran three checks:

```text
node --env-file=.env -e '...'               -> from-file 4100
APP_PORT=5200 node --env-file=.env -e '...' -> 5200 from-file
node --env-file=nope.env -e '1'             -> node: nope.env: not found   (exit=9)
```

The `'...'` stands for a one-line script that prints `APP_API_KEY` and `APP_PORT`. The first run reads both values from the file. In the second I set `APP_PORT=5200` in the real environment, and it won over the file (4100), while the key still came from the file. So a real environment variable beats the file. The third shows that a missing file is an error, not silently ignored. On 20.13.1 `process.loadEnvFile` exists too (`typeof` printed `function`), and loading the same file gave `APP_PORT` 4100. I saw no warning, but both are newer features, so re-check them when you upgrade Node.

## Never log secrets

The startup line is a good place to print the config, because it tells you which settings the process really got. It is also a classic place to leak a password into the logs. `redact(cfg)` replaces `apiKey` and `dbUrl` with `***` when they are set. This is a real run with an API key, a database URL, a random port and `APP_LOG_LEVEL=debug`; I sent a `curl -XPOST` that created an order, then `SIGTERM`:

```text
{"level":"info","msg":"config loaded","config":{"port":61944,"host":"127.0.0.1","logLevel":"debug","dbUrl":"***","apiKey":"***","debug":false}}
{"level":"info","msg":"listening","addr":"127.0.0.1:61944"}
{"level":"info","msg":"shutting down","signal":"SIGTERM"}
```

Both secrets are hidden and the other settings are visible. (Without `APP_DB_URL` the line shows `"dbUrl":""`, because an empty value has nothing to hide.) The shutdown wiring in `main.js` is the same as in the HTTP server post: on a signal, `server.close()` and `closeIdleConnections()`, then exit.

## Testing loadConfig

Because the function takes its inputs as arguments, the test is short. `npm test` ran four tests and all passed. They check the defaults, the order file < env < flags, that one bad input reports all four problems together, and that `redact` hides the key. The precedence test looks like this:

```js
const cfg = loadConfig({ file: { port: 1111 }, env: { ...base, APP_PORT: '2222' }, argv: ['--port', '3333'] });
assert.equal(cfg.port, 3333);
```

The same port is given three times, 1111 in the file, 2222 in the environment and 3333 as a flag, and the flag wins.

## Config that is silently wrong

- **`NODE_ENV` only sets a string.** Node itself does nothing with it; according to the docs, some libraries (Express, for example) change behavior. I printed `undefined` without it and `production` with it. Do not branch your own logic on it; use explicit settings.
- **Keep `.env` out of git.** Never commit real secrets.
- **Do not read `process.env` all over the code.** Read it once in `loadConfig`, so there is one place that parses and validates.
- **Hand-written validation does not scale.** It is fine for a few variables; for request bodies and bigger schemas see [Input validation with Zod](/posts/node-validation-zod/) later in the series.

## Exercise

Add `APP_TIMEOUT_MS` (integer, default 5000, must be above 0) and a `--timeout-ms` flag. Add tests for the new range error and for precedence, and check that a bad value is reported together with the others.

## What's next

"Postgres from Node.js with pg" is the next post. There, the `dbUrl` from this config connects to a real database.
