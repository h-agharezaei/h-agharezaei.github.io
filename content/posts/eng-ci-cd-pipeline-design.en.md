+++
date = '2027-05-03T10:00:00+03:30'
draft = false
title = 'Designing a CI/CD pipeline'
description = 'CI/CD pipeline design in Go: ordered stages, a coverage gate, reproducible builds, blue/green deploy with rollback, and a linted Actions workflow.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ci-cd", "pipeline", "github-actions", "software-engineering", "go", "deployment"]
cover = { image = "/images/covers/eng-ci-cd-pipeline-design.png", alt = "Designing a CI/CD pipeline", hiddenInSingle = true }
+++

The previous post, [Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/), ended with "the pipeline that runs on every merge". This is that pipeline. {{< term "ci" "CI" >}} merges and checks every change; continuous delivery keeps `main` always releasable; continuous deployment also ships it without a human. Related: [Testing in Go](/posts/go-testing-basics/), [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/), [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/). Opinions are marked; the rest was run.

> Go 1.26. The demo is a local example: a tiny service, `scripts/ci.sh` and `scripts/deploy.sh`, in a git repo with a fake author. The GitHub Actions workflow was **not** run on GitHub.

## Stages, cheapest first

Order by cost and signal: format, vet, tests, coverage gate, build, checksum, smoke test. A failure should stop the run early. The script is the pipeline; the CI server only calls it, so I can run the same thing on my laptop. **My opinion:** keep the PR pipeline short (minutes, not tens of minutes), because slow feedback gets worked around.

```text
== 1 format
== 2 vet
== 3 test
ok  	example.com/cidemo/internal/greet	1.224s	coverage: 80.0% of statements
```

Tests run with `-race -count=1`: the race detector on, and no cached result. A {{< term "flaky-test" "flaky test" >}} that passes on retry is a bug to fix, not a retry setting.

## A coverage gate

The gate fails when {{< term "code-coverage" "coverage" >}} is below a threshold. One function was left untested on purpose, giving 80.0%. With the limit at 90:

```text
== 4 coverage gate (min 90%)
total coverage: 80.0%
FAIL: coverage below 90%
```

With a limit of 75 the run continued and ended with `pipeline ok`. I count coverage on `./internal/...` only: counting `main` pulled the total to 23.5%, which measured my layout, not my tests. **In my opinion** a gate is a floor against decay, not a goal; high coverage does not prove good tests.

## Build, version, checksum

```text
== 5 build
cidemo 0.1.0 (8874951)
== 6 checksum
1e236e486199babaee49164bc168dfc768fe7732b2a173d16c7b94e6503be4f9  cidemo
```

The build uses `-trimpath -ldflags "-X main.version=... -X main.commit=..."`, so the binary reports what it is.

## Is the build reproducible?

I built twice into different directories and compared hashes. The first attempt differed:

```text
1e236e48...3be4f9  dist-a/cidemo
b5d744f5...956d08  dist-b/cidemo
```

`go version -m` showed why: Go stamped `vcs.modified=false` in one and `true` in the other, because the first build had created untracked `dist-a/` before the second. After adding `dist/` to `.gitignore` and building into it, both hashes were identical (`1e236e48...`). So a {{< term "reproducible-build" "reproducible build" >}} needs a clean tree, not just `-trimpath`. Without `-trimpath`, paths enter the binary; I did not test cross-machine builds.

## Dependencies and vulnerabilities

`go list -m all` printed only `example.com/cidemo`, so there is nothing to audit here. I tried `govulncheck@v1.1.4`; it failed:

```text
govulncheck: fetching vulnerabilities: HTTP GET https://vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden
```

So the vulnerability step did **not** run on this machine. In a real pipeline, keep it as its own step.

## Deploy: blue/green with a health gate

`deploy.sh` treats a root directory like a server: `releases/blue`, `releases/green` and a `current` symlink. It copies the binary to the idle slot, starts it on loopback, waits for `/healthz`, and only then flips the symlink. Real output of three runs, the last with a deliberately broken listen address:

```text
deploy: health ok, current -> releases/blue
deploy: health ok, current -> releases/green
deploy: health check FAILED on blue, rollback: current stays -> releases/green
```

Strictly this is "never switched" rather than a restored state, and the script exits 1 so the pipeline goes red. That is the cheap {{< term "blue-green-deployment" "blue/green" >}} property. A {{< term "canary-release" "canary" >}} sends a small share first, as in the flags post. {{< term "rollback" "Rollback" >}} versus roll-forward: code rolls back easily, data does not, so use {{< term "expand-contract" "expand/contract" >}} migrations ([Refactoring safely](/posts/eng-refactoring-safely/)).

## The workflow file

`ci.yml` has a `test` job with a Go version matrix and `actions/setup-go@v5` caching, `permissions: contents: read`, a `concurrency` group that cancels old runs, and a `deploy` job with `needs: test` in an `environment: production` (where required reviewers can be configured) using `secrets.DEPLOY_TOKEN`. `actionlint` v1.7.7 passed it; changing `needs` to a typo made it report `job "deploy" needs job "tset" which does not exist`. The deploy job is a sketch: it would also need to pass the built binary between jobs. According to GitHub's security advice, pin third-party actions to a full commit SHA; I used major tags here for readability.

## A few things to watch

- Secrets belong in the CI secret store, never in the repo or logs.
- Keep the deploy step idempotent so a re-run is safe.
- Do not skip the {{< term "smoke-test" "smoke test" >}}; green unit tests can still ship a binary that does not start.
- Pipeline definitions are code: review them.

## Exercise

Add a stage that fails if `gofmt -l` lists a file, then break it on purpose and watch the pipeline stop.

## What's next

The next post is "SLIs, SLOs and error budgets".
