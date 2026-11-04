+++
date = '2027-05-03T10:00:00+03:30'
draft = false
title = 'Designing a CI/CD pipeline'
contentType = 'engineering'
description = 'CI/CD pipeline design in Go: ordered stages, a coverage gate, reproducible builds, blue/green deploy with rollback, and a linted Actions workflow.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ci-cd", "pipeline", "github-actions", "software-engineering", "go", "deployment"]
cover = { image = "/images/covers/eng-ci-cd-pipeline-design.png", alt = "Designing a CI/CD pipeline", hiddenInSingle = true }
+++

Picture two deploys of the same small service. In the first, the new release has a broken listen address. The pipeline starts it, asks it "are you healthy?", gets no answer, leaves the old release running, and goes red. Nobody is paged and no user notices. In the second, someone copies a binary to a server by hand on a Friday evening, and finds out about the broken address from the support inbox. A pipeline exists to make the first story the boring, normal one. The first story is also one of the demos below.

The trunk-based workflow from [Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/) depends on a pipeline like this running on every merge. Three terms are often mixed up here. {{< term "ci" "CI" >}} (continuous integration) means every change is merged and checked automatically. Continuous delivery means `main` is always in a state that could be released. Continuous deployment goes one step further: every passing change is also shipped, without a human pressing a button. Related posts: [Testing in Go](/posts/go-testing-basics/), [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/) and [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/). I mark my opinions. The rest was run.

> The original run used Go 1.26. I re-ran the pipeline, the reproducibility check and the deploy with Go 1.27.3 for this edit. The demo is a local example: a tiny service, `scripts/ci.sh` and `scripts/deploy.sh`, in a git repo with a fake author. The GitHub Actions workflow was **not** run on GitHub. The checksums and the commit hash in the outputs depend on the Go version and on the commit, so they are different from the ones in the first version of this post. They would be different on your machine too.

## Stages, cheapest first

A pipeline is a list of stages, and the order matters. Put the cheap checks that fail often first, and the expensive ones last, so that a failure stops the run early and the developer hears about it quickly. My order is: format, vet, tests, coverage gate, build, checksum, smoke test.

One more idea: the script is the pipeline, and the CI server only calls it. So I can run exactly the same thing on my laptop, and I do not have to push a commit to find out what CI would say. **My opinion:** keep the pipeline for a pull request short, minutes and not tens of minutes, because slow feedback gets worked around.

The first stages print this:

```text
== 1 format
== 2 vet
== 3 test
ok  	example.com/cidemo/internal/greet	2.426s	coverage: 80.0% of statements
```

Formatting and vet print nothing when they are happy. The tests run with `-race -count=1`: the race detector is on, and the result is never taken from the cache. A {{< term "flaky-test" "flaky test" >}}, one that sometimes fails for no reason, which then passes on retry, is a bug to fix. It is not something to hide behind a retry setting. (The run time is different on every run.)

## A coverage gate

A gate is a stage that can say no. This one fails when {{< term "code-coverage" "coverage" >}}, the share of statements that tests execute, is below a threshold. I left one function untested on purpose, which gives 80.0%. With the limit at 90, the pipeline stops:

```text
== 4 coverage gate (min 90%)
total coverage: 80.0%
FAIL: coverage below 90%
```

With a limit of 75, the run continued through the build and the smoke test and ended with `pipeline ok`. The default limit in the script is 80.

I count coverage on `./internal/...` only. Counting `main` too pulled the total down to 23.5%, because `main` has no tests, so the number measured my project layout and not my tests. **In my opinion** a gate is a floor against decay, not a goal. High coverage does not prove the tests are good.

## Build, version, checksum

Next the pipeline builds the binary once, stamps it with a version, and records a checksum:

```text
== 5 build
cidemo 0.1.0 (5572165)
== 6 checksum
24dfd3de06b004a6871320fa543045c505ede3a97f577068fca88e6c555daed5  cidemo
```

The build uses `-trimpath -ldflags "-X main.version=... -X main.commit=..."`. The first line is the binary itself answering `-version`: it reports the version and the git commit it was built from, so when something runs in production you can tell what it is. The checksum is a fingerprint of the file. If two builds have the same checksum, they are the same bytes.

## Is the build reproducible?

A {{< term "reproducible-build" "reproducible build" >}} gives the same bytes from the same source. It is useful because you can then trust that the binary you tested is the binary you ship. I tested it the simple way: build twice into different directories and compare the hashes. The first attempt differed:

```text
24dfd3de06b004a6871320fa543045c505ede3a97f577068fca88e6c555daed5  dist-a/cidemo
753b835cfbe71a575683684f11a31c9e8f4f3ed7c568f3b5f412051a2d7b6e8e  dist-b/cidemo
```

I used `go version -m` to see why. Go stamps `vcs.modified` into the binary: `false` in the first and `true` in the second. The first build had created an untracked directory, `dist-a/`, so by the time of the second build git saw a "modified" tree. After I added `dist/` to `.gitignore` and built into it both times, the hashes were identical (`24dfd3de...`). So a reproducible build needs a clean tree, not just `-trimpath`. Without `-trimpath`, local paths end up inside the binary. I did not test builds across different machines.

## Dependencies and vulnerabilities

`go list -m all` prints only `example.com/cidemo`, so there is nothing to audit in this demo. I also tried `govulncheck@v1.1.4`, and in the original run it failed:

```text
govulncheck: fetching vulnerabilities: HTTP GET https://vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden
```

So the vulnerability step did **not** run on this machine. In a real pipeline, keep it as its own step.

## Deploy: blue/green with a health gate

Now the deploy. `deploy.sh` treats a root directory like a server. It has two slots, `releases/blue` and `releases/green`, and a symlink `current` that says which one is live. The script copies the binary into the idle slot, starts it on loopback, waits for `/healthz` to answer, and only then moves the `current` symlink. That is {{< term "blue-green-deployment" "blue/green" >}} in a nutshell: the new version is proven healthy before any traffic goes to it.

Here are three runs. The first two succeed and alternate between the slots. For the third I pass a deliberately broken listen address:

```text
deploy: health ok, current -> releases/blue
deploy: health ok, current -> releases/green
deploy: health check FAILED on blue, rollback: current stays -> releases/green
```

In the third run, the new version never answers, `current` is not touched, and the script exits with status 1, so the pipeline goes red. Strictly speaking this is "never switched" rather than "restored", but the effect for users is the same. This is the cheap blue/green property.

Other words you will meet: a {{< term "canary-release" "canary" >}} sends a small share of traffic to the new version first, as in the flags post. {{< term "rollback" "Rollback" >}} versus roll-forward: code rolls back easily, data does not. If a release changed the database shape, going back may not be possible, so use {{< term "expand-contract" "expand/contract" >}} migrations, where you add the new shape first and remove the old one later ([Refactoring safely](/posts/eng-refactoring-safely/)).

## The workflow file

The same stages go into a GitHub Actions workflow, `ci.yml`. It has a `test` job with a matrix of Go versions and `actions/setup-go@v5` caching, `permissions: contents: read`, and a `concurrency` group that cancels older runs of the same branch. A `deploy` job has `needs: test`, so it only starts after the tests pass, and it runs in `environment: production`, where required reviewers can be configured. It uses `secrets.DEPLOY_TOKEN`.

I checked it with `actionlint` v1.7.7 in the original run, and it passed. When I changed `needs` to a typo, it reported `job "deploy" needs job "tset" which does not exist`. I could not re-run `actionlint` for this edit, so that result is from the original run. The deploy job is only a sketch: in a real workflow it would also have to pass the built binary from one job to the other. According to GitHub's security advice, third-party actions should be pinned to a full commit SHA. I used major version tags here for readability.

## What a pipeline must not skip

- Secrets belong in the CI secret store, never in the repo or in logs.
- Keep the deploy step idempotent, so that running it again is safe.
- Do not skip the {{< term "smoke-test" "smoke test" >}}. Green unit tests can still ship a binary that does not start.
- Pipeline definitions are code. Review them.

## What's next

The next post is "SLIs, SLOs and error budgets". A green pipeline tells you that a release started. The next question is whether users are actually being served well.
