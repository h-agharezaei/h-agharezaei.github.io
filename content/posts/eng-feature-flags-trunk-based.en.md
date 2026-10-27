+++
date = '2027-04-27T10:00:00+03:30'
draft = false
title = 'Feature flags and trunk-based development'
description = 'Feature flags in Go: stable percentage rollout, kill switch, atomic reload, the cost of flags, and how they enable trunk-based development.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["feature-flags", "trunk-based-development", "software-engineering", "go", "release"]
cover = { image = "/images/covers/eng-feature-flags-trunk-based.png", alt = "Feature flags and trunk-based development", hiddenInSingle = true }
+++

The previous post, [ADRs and documenting decisions](/posts/eng-adr-documentation/), recorded why we choose things. This one is about a choice that changes how you ship: separating deploy from release. A {{< term "feature-flag" "feature flag" >}} lets unfinished code live in `main` while users cannot see it, and that is what makes {{< term "trunk-based-development" "trunk-based development" >}} workable. Flags also create {{< term "technical-debt" "debt" >}} ([Technical debt](/posts/eng-technical-debt/)), so I count that cost too. Related: [Testing in Go](/posts/go-testing-basics/), [Refactoring safely](/posts/eng-refactoring-safely/). Opinions are marked; the rest was run.

> Go 1.26, `go test -race`. The demo is a local example I wrote for this post: a flag package of about 80 lines, no vendor SDK.

## The evaluator

Each flag has a rule: a `kill` bool, a `percent` and per-user `overrides`. The order is fixed: unknown flag is off, then kill switch, then override, then percentage.

```go
func Bucket(name, user string) int {
	h := fnv.New32a()
	h.Write([]byte(name + user))
	return int(h.Sum32() % 100)
}
```

The same user and flag always land in the same bucket, so there is no state to store. The {{< term "kill-switch" "kill switch" >}} beats even an override, and an unknown flag returns false (fail-safe: a typo hides a feature instead of exposing one). Config is a JSON file; `Reload` parses it first and only then swaps it with `atomic.Pointer`, so a broken file keeps the old config.

## Does ramping flip anyone?

A {{< term "canary-release" "percentage rollout" >}} is only honest if ramping up never removes a user who was already in. The test ramps 10, 25, 50 over 10,000 synthetic ids and fails on any flip:

```text
percent=10 users_in=1017 of 10000
percent=25 users_in=2513 of 10000
percent=50 users_in=5020 of 10000
```

It passes. That follows from the rule `bucket < percent`: raising `percent` only adds buckets. The buckets are roughly even; users per block of ten buckets:

```text
[1017 990 1005 1003 1005 982 1006 1013 988 991]
```

Mixing the flag name into the hash matters: otherwise the same 10% of users would test every flag.

## Live reload

A tiny program reads the file, waits, I edit the file, and it reloads. Real output (time stamps removed):

```text
-- before first load
level=INFO msg=flag name=new-pricing user=alice on=false why=unknown
-- after load
level=INFO msg=flag name=new-pricing user=alice on=false why=override
-- after reload
level=INFO msg=flag name=new-pricing user=alice on=true why=percent
```

Same process, new behavior. A test reloads while eight goroutines evaluate, under `-race`, and passes. The log line answers "why did this user see it?".

## Both branches, and branch by abstraction

Every flag doubles a code path, and both halves need tests. My `shop` package puts old and new pricing behind a `Pricer` interface ({{< term "branch-by-abstraction" "branch by abstraction" >}}), switched by `new-pricing`. One test runs the same expectations with the flag at 0 and at 100 percent. A {{< term "characterization-test" "characterization test" >}} compares old and new on 8866 inputs and requires equal results. Merge the new code dark (flag off) daily; when the comparison holds, ramp.

## The cost

n independent boolean flags give 2^n configurations. The test printed:

```text
3 boolean flags -> 8 configurations
10 boolean flags -> 1024 configurations
20 boolean flags -> 1048576 configurations
```

You will not test them all. **In my experience** most flags do not interact, but the ones that do fail in production. Keep flags independent and few.

Old flags are debt. In a demo repo with three commits (fake author, fixed dates; the history is staged, not a real project), a script lists flags in `flag/flags.go`, references to them, and the first commit via `git log -S`:

```text
old-banner     refs=0 first_added=2026-01-10
fast-checkout  refs=1 first_added=2026-03-02
new-pricing    refs=2 first_added=2026-04-20
```

`old-banner` is defined, referenced nowhere, and the oldest. That is a removal candidate. My removal checklist: ramp to 100 and wait; delete the losing branch and the flag check; delete its tests; delete the config entry; delete the constant.

## Trunk-based in practice

Short-lived branches, merged to `main` at least daily, with unfinished work behind flags. Advice on branch lifetime varies; I aim for a day or two. Deploy puts code on servers; release is turning it on. A dark launch deploys code that runs but whose result users do not see; a canary exposes a small percentage.

| | GitFlow | Trunk-based |
|---|---|---|
| Branches | long-lived develop, release | short-lived, one `main` |
| Unfinished work | sits on a branch | merged behind a flag |
| Needs | merge discipline | fast CI, tests, flags |

**In my opinion** trunk-based fits a service deployed often; GitFlow suits software with versioned releases. Rollback becomes flipping the flag, then reverting at leisure. The pipeline that runs on every merge is the next post.

## A few things to watch

- Flags are not access control: do not decide authorization with them.
- Test the flag-off path too, because it is your rollback.
- Every flag needs an owner and a removal date.
- I did not run OpenFeature. As far as I know it is a vendor-neutral standard API for flag evaluation; check its docs before relying on that.

## Exercise

Add a flag to a function you own, merge it off, write both tests, ramp it in a test, then delete it using the checklist.

## What's next

The next post is "Designing a CI/CD pipeline".
