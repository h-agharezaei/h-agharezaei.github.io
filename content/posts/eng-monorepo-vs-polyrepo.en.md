+++
date = '2027-06-02T10:00:00+03:30'
draft = false
title = 'Monorepo or polyrepo?'
description = 'Monorepo or polyrepo in Go: one cross-cutting change done both ways, affected-module CI, CODEOWNERS, sparse and partial clones, and a decision matrix.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["monorepo", "polyrepo", "go-workspaces", "ci", "git", "software-engineering"]
cover = { image = "/images/covers/eng-monorepo-vs-polyrepo.png", alt = "Monorepo or polyrepo?", hiddenInSingle = true }
+++

The previous post, [Domain-driven design basics](/posts/eng-ddd-basics/), drew boundaries inside a system. The next question is where the code behind those boundaries lives. A {{< term "monorepo" "monorepo" >}} keeps several services in one repository; a {{< term "polyrepo" "polyrepo" >}} gives each its own. Related: [Packages and modules](/posts/go-packages-modules/), [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/), [Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/), [Branches, HEAD and refs](/posts/git-branches-head-refs/).

I built the same toy system twice: `orders`, `payments` and `shared` (a `Format` function), as one repo and as three. Throwaway local repos (Go 1.26, Git 2.39). **Numbers are counts and bytes, never timings.** Opinions are labelled.

## 1. One change, two ways

I changed `Format(cents)` into `Format(cents, cur)`. In the monorepo the three modules are joined by a {{< term "go-workspace" "go.work" >}} file. With only `shared` edited, one command shows every broken caller:

```text
$ go build ./orders/... ./payments/... ./shared/...   # output trimmed
orders/orders.go:14:23: not enough arguments in call to shared.Format
payments/payments.go:9:67: not enough arguments in call to shared.Format
```

I fixed both callers and committed once. `go test -race` then passed in all three modules, and `git show --stat` listed 6 files in one commit.

In the polyrepo, `orders` and `payments` depend on `shared` by version. To simulate releases without a network I served tagged zips from a local file-based module proxy (demo plumbing only). Result: three pull requests in three repos, one tag, and this state after the second one:

```text
orders:   example.com/poly/shared v0.2.0
orders total: 30.00 EUR
payments: example.com/poly/shared v0.1.0
payments: paid 12.50
```

Everything compiles and passes, yet two services format money differently until the third PR lands.

| | monorepo | polyrepo |
|---|---|---|
| repos / commits / PRs | 1 / 1 / 1 | 3 / 3 / 3 (+1 tag) |
| mixed-version states | 0 | 1 |

**My opinion:** atomic change is the strongest argument for a monorepo. The polyrepo's pinning is also a feature: payments was never forced to move.

## 2. CI should not run everything

A monorepo without selective CI gets slow. My script reads `git diff --name-only`, parses each `go.mod` and walks the dependency edges:

```text
diff 1: orders/orders.go    run tests for: ['orders']
diff 2: payments/payments.go    run tests for: ['payments']
diff 3: shared/money.go     run tests for: ['orders', 'payments', 'shared']
diff 4: docs/README.md      run tests for: (nothing)
```

Tools like Bazel, Nx, Turborepo, Pants and Buck2 exist for this; I did not use them and make no claims about them.

## 3. Ownership and access

A {{< term "codeowners" "CODEOWNERS" >}} file maps paths to teams. My 11-line matcher (last match wins) gave `payments/payments.go -> @team-payments @team-security` and `orders/README.md -> @team-docs`. As far as I know, GitHub has no per-directory read permission, so "only team X may read this" is naturally per repo. Check your host's docs; I did not test that.

## 4. Scale

I generated a repo with `git fast-import`: 3,000 commits, 3,000 files, 1,000 per service. `git count-objects -vH` said 2.11 MiB packed. Three tools help when it grows:

- `git log -- orders` counted 1,000 commits for each directory: history can be asked per path.
- {{< term "sparse-checkout" "Sparse checkout" >}} (cone mode, `orders` only): 1,000 files on disk, 3,000 tracked.
- {{< term "partial-clone" "Partial clone" >}} (`--filter=blob:none`, `--no-checkout`): 1.22 MiB, 3,000 blobs missing; reading one file fetched it, leaving 2,999 missing.

Scoped commit messages (`fix(shared): ...`, see {{< term "conventional-commits" "Conventional Commits" >}}) keep the shared log readable.

## 5. Versions and releases

A monorepo can use one version for everything: simple, but upgrades move together. Polyrepo gives each library its own {{< term "semver" "semantic version" >}}. A monorepo with several Go modules can still tag them separately: according to the Go modules reference, the module subdirectory is also a prefix for version tags (so something like `orders/v1.2.0`). I did not run a tagged multi-module resolve.

## My decision matrix (opinion)

| factor | leans monorepo | leans polyrepo |
|---|---|---|
| team size | small to mid, shared on-call | many independent teams |
| shared code | changes often | stable, versioned API |
| release cadence | together | independent |
| build tooling | you have or will build selective CI | each repo trivial |
| access control | open internally | strict per project |
| onboarding | one clone, one search | smaller, focused repos |

My middle path: one repo per product area, and truly shared libraries as separate versioned repos.

## A few things to watch

- `go.work` is for local work; releases must still use real versions.
- At a workspace root `go test ./...` fails ("directory prefix . does not contain modules"); name the module directories.
- A "shared" folder that everyone edits becomes the coupling point; have owners.
- Pinning hides drift: schedule bumps.

## Exercise

Add a fourth module `reports` that depends on `shared` and extend `affected.py` so a change to `shared` also selects it. Then change `reports/` only and confirm that it runs alone.

## What's next

The next post is "Estimation and planning".
