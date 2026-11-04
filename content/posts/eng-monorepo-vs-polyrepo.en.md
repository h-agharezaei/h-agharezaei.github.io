+++
date = '2027-06-02T10:00:00+03:30'
draft = false
title = 'Monorepo or polyrepo?'
contentType = 'engineering'
description = 'Monorepo or polyrepo in Go: one cross-cutting change done both ways, affected-module CI, CODEOWNERS, sparse and partial clones, and a decision matrix.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["monorepo", "polyrepo", "go-workspaces", "ci", "git", "software-engineering"]
cover = { image = "/images/covers/eng-monorepo-vs-polyrepo.png", alt = "Monorepo or polyrepo?", hiddenInSingle = true }
+++

Suppose a function in a shared package, `Format(cents)`, has to become `Format(cents, cur)`, so that it can print a currency. Everybody who calls it must change too. How painful this is depends on one decision made long ago: where the code lives.

In a {{< term "monorepo" "monorepo" >}} (several services in one repository) this is one commit: you change the function and all its callers together. In a {{< term "polyrepo" "polyrepo" >}} (each service in its own repository) it is three pull requests, one new version tag, and a window of time in which two services format money differently. Neither side is simply "right". This post runs the same change both ways so you can see exactly what differs, and then gives the criteria I would use to choose.

The previous post, [Domain-driven design basics](/posts/eng-ddd-basics/), drew boundaries inside a system. The question here is where the code behind those boundaries should live. Related reading: [Packages and modules](/posts/go-packages-modules/), [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/), [Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/) and [Branches, HEAD and refs](/posts/git-branches-head-refs/).

I built the same toy system twice: three Go modules named `orders`, `payments` and `shared` (which has the `Format` function), once as one repository and once as three. They are throwaway local repositories. I re-ran everything with Go 1.27.3 and Git 2.39.2 (the original run used Go 1.26) in a scratch copy of the demo. **The numbers in this post are counts and bytes, never timings.** Opinions are labelled.

## 1. One change, two ways

I changed `Format(cents)` into `Format(cents, cur)`. First the monorepo. Its three modules are tied together by a {{< term "go-workspace" "go.work" >}} file, which tells Go to resolve them to each other directly in the same checkout, with no published versions. When only `shared` is edited, one command shows every caller that broke:

```text
$ go build ./orders/... ./payments/... ./shared/...   # first five lines
# example.com/mono/orders
orders/orders.go:14:23: not enough arguments in call to shared.Format
	have (int64)
	want (int64, string)
# example.com/mono/payments
```

I cut the output to five lines. The `# example.com/mono/payments` header on the last line is followed by the same kind of error in `payments/payments.go`, and a `go test` run also prints the errors for the test builds. So the compiler points at `orders.go` and `payments.go`. I fixed both callers and committed once. Then `go test -race` passed in all three modules, and `git show --stat` listed 6 files changed in one commit: two source files and two tests in the callers, plus `shared` and its test.

Now the polyrepo. Here `orders` and `payments` depend on `shared` by **version**: each one's `go.mod` says which tag of `shared` it uses. To simulate releases without a network, I served tagged zip files from a local, file-based module proxy. That is demo plumbing only. The result was three pull requests in three repositories and one new tag (`v0.2.0`). After the second pull request, the state was:

```text
orders:   example.com/poly/shared v0.2.0
orders total: 30.00 EUR
payments: example.com/poly/shared v0.1.0
payments: paid 12.50
```

Look at the last two lines. `orders` already prints the currency, and `payments` does not. Everything compiles and every test passes, yet two services format money differently until the third pull request lands. Before the first pull request, both services were on `v0.1.0`, and after the third both are on `v0.2.0`. For a while, in between, the system is mixed.

| | monorepo | polyrepo |
|---|---|---|
| repos / commits / PRs | 1 / 1 / 1 | 3 / 3 / 3 (+1 tag) |
| mixed-version states | 0 | 1 |

My opinion: atomic change, the whole change at once, is the strongest argument for a monorepo. But the polyrepo's pinning is also a feature, not just a cost: `payments` was never forced to move. It stayed on `v0.1.0` until its team chose to upgrade.

## 2. CI should not run everything

A monorepo has an obvious risk: if every commit runs every test for every service, CI gets slow as the repository grows. The remedy is to run only what the change can affect.

My script does that for the three modules. It reads `git diff --name-only`, parses each `go.mod`, and walks the dependency edges: a change in a module affects that module and everything that depends on it. I ran it against four example changes:

```text
diff 1: orders/orders.go
changed: ['orders/orders.go']
run tests for: ['orders']

diff 2: payments/payments.go
changed: ['payments/payments.go']
run tests for: ['payments']

diff 3: shared/money.go
changed: ['shared/money.go']
run tests for: ['orders', 'payments', 'shared']

diff 4: docs/README.md
changed: ['docs/README.md']
run tests for: (nothing)
```

A change in `orders` runs only the `orders` tests. A change in `shared` runs everything, because both services depend on it. A change in a README runs nothing. (The script treats a change to `go.work` itself as "run all", to be safe.) Real build tools do this much better: Bazel, Nx, Turborepo, Pants and Buck2 exist for exactly this problem. I did not use them and make no claims about them.

## 3. Ownership and access

In one repository, "who must review changes to this folder?" needs an answer. A {{< term "codeowners" "CODEOWNERS" >}} file maps paths to teams. This is the one the demo used, where the last matching line wins:

```text
# last matching pattern wins
*            @team-platform
/shared/     @team-platform
/orders/     @team-orders
/payments/   @team-payments @team-security
*.md         @team-docs
```

My 11-line matcher script, run on five paths, printed:

```text
shared/money.go              -> @team-platform
orders/orders.go             -> @team-orders
payments/payments.go         -> @team-payments @team-security
orders/README.md             -> @team-docs
go.work                      -> @team-platform
```

Notice `orders/README.md`: the later `*.md` rule beats `/orders/`, so the docs team owns it. That is the "last match wins" rule at work.

That covers who reviews. Who may *read* is a different question. As far as I know, GitHub has no per-directory read permission, so "only team X may read this code" is naturally a per-repository rule. Check your own host's documentation; I did not test that.

## 4. Scale

The usual worry about a monorepo is size. To get a feel, I generated a repository with `git fast-import`: 3,000 commits and 3,000 files, 1,000 per service. `git count-objects -vH` said the packed repository is 2.11 MiB. That is small, because my files are small; the point is the three tools that help when a repository grows:

- **History per path.** `git log -- orders` counted 1,000 commits for `orders`, and the same for each of the other two directories. You can ask about one service's history even though the repository holds all of them.
- **Sparse checkout.** {{< term "sparse-checkout" "Sparse checkout" >}} in cone mode, set to `orders` only, left 1,000 files on disk while Git still tracks 3,000. A developer sees only the part they work on.
- **Partial clone.** {{< term "partial-clone" "Partial clone" >}} (`--filter=blob:none`, `--no-checkout`) skips file contents when cloning. The clone was 1.22 MiB, with all 3,000 file blobs missing. History commands still worked: counting the commits that touch `shared` gave 1,000. Reading one file fetched it, and afterwards 2,999 blobs were still missing.

One more habit helps in a shared log: scoped commit messages such as `fix(shared): ...`, in the style of {{< term "conventional-commits" "Conventional Commits" >}}, make it easy to see which part of the repository a commit touched.

## 5. Versions and releases

A monorepo can use one version number for everything. That is simple, but upgrades move together. A polyrepo gives each library its own {{< term "semver" "semantic version" >}}, so consumers upgrade when they choose. A monorepo with several Go modules can still tag them separately: according to the Go modules reference, the module's subdirectory is also a prefix for its version tags (so something like `orders/v1.2.0`). I did not run a tagged multi-module resolve, so treat that as documented, not tested.

## My decision matrix (opinion)

No single answer fits every team. These are the factors I would look at:

| factor | leans monorepo | leans polyrepo |
|---|---|---|
| team size | small to mid, shared on-call | many independent teams |
| shared code | changes often | stable, versioned API |
| release cadence | together | independent |
| build tooling | you have or will build selective CI | each repo trivial |
| access control | open internally | strict per project |
| onboarding | one clone, one search | smaller, focused repos |

My middle path: one repository per product area, and truly shared libraries as separate, versioned repositories.

## Traps on both sides

- **`go.work` is for local work.** Releases must still use real versions: whoever depends on your published module resolves versions from `go.mod`, not from your `go.work`.
- **At a workspace root, `go test ./...` fails.** Go says `pattern ./...: directory prefix . does not contain modules listed in go.work or their selected dependencies`. Name the module directories instead, as in `go test ./orders/... ./payments/... ./shared/...`.
- **A "shared" folder that everyone edits becomes the coupling point.** Give it owners, as in the CODEOWNERS file above.
- **Pinning hides drift.** In a polyrepo nobody forces an upgrade, so services can sit on old versions for a long time. Schedule version bumps.

## What's next

The next post is "Estimation and planning". The polyrepo change above needed three pull requests in sequence, and dependencies like that are exactly where estimates go wrong.
