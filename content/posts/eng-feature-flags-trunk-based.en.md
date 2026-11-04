+++
date = '2027-04-27T10:00:00+03:30'
draft = false
title = 'Feature flags and trunk-based development'
contentType = 'engineering'
description = 'Feature flags in Go: stable percentage rollout, kill switch, atomic reload, the cost of flags, and how they enable trunk-based development.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["feature-flags", "trunk-based-development", "software-engineering", "go", "release"]
cover = { image = "/images/covers/eng-feature-flags-trunk-based.png", alt = "Feature flags and trunk-based development", hiddenInSingle = true }
+++

Suppose a feature takes three weeks to build. If it lives on its own branch for those three weeks, `main` keeps moving without it, and on the day you merge, the branch and `main` have drifted far apart. The merge is large, painful and risky, and the release waits for it. Meanwhile nobody else has seen your code run.

The usual answer is to merge the unfinished code into `main` every day and hide it, so that users cannot see it yet. A {{< term "feature-flag" "feature flag" >}} is the switch that hides it: an `if` in the code that asks a configuration, not a deploy, whether a feature is on. With flags, unfinished code can live in `main` safely, and that is what makes {{< term "trunk-based-development" "trunk-based development" >}} (everyone merging small changes to one main branch, often) workable. The idea is to separate **deploy** (putting code on the servers) from **release** (letting users use it). That is a decision worth recording, as in [ADRs and documenting decisions](/posts/eng-adr-documentation/), because it changes how a team ships.

Flags are not free. Twenty independent boolean flags give 1,048,576 possible configurations, and nobody tests them all. Old flags also turn into {{< term "technical-debt" "debt" >}}, the subject of [Technical debt](/posts/eng-technical-debt/), so I count that cost too. Related posts: [Testing in Go](/posts/go-testing-basics/) and [Refactoring safely](/posts/eng-refactoring-safely/). Opinions are marked as such. The rest was run.

> The original run used Go 1.26, and I re-ran everything below with Go 1.27.3 (`go test -race`). The demo is a local example I wrote for this post: a flag package of about 80 lines, with no vendor SDK.

## The evaluator

The core of a flag system is a function that answers one question: is flag X on for user Y? In my demo, each flag has a rule with three parts: a `kill` bool, a `percent` (how many users should see it) and per-user `overrides`. The order of checks is fixed:

1. an unknown flag is off;
2. then the kill switch: if it is set, the flag is off;
3. then a per-user override, if there is one;
4. then the percentage.

The percentage needs a way to decide, for each user, whether they are inside the 10% or outside. The answer is a hash. It maps a flag name and a user id to a number from 0 to 99 (a bucket), and the user is in if their bucket is below the percentage:

```go
func Bucket(name, user string) int {
	h := fnv.New32a()
	h.Write([]byte(name + user))
	return int(h.Sum32() % 100)
}
```

The same user and flag always land in the same bucket, so there is no state to store, and the user does not flip in and out between requests. The {{< term "kill-switch" "kill switch" >}} beats even an override, because its job is to turn a feature off right now, whatever else is configured. An unknown flag returns false. That is fail-safe: a typo in a flag name hides a feature instead of exposing one.

The config is a JSON file. `Reload` parses the file first and only then swaps it in with an `atomic.Pointer`, so readers never see half a config, and a broken file leaves the old config in place.

## Does ramping flip anyone?

A {{< term "canary-release" "percentage rollout" >}} releases a feature to 10% of users, then 25%, then 50%, and so on. It is only honest if ramping up never removes a user who was already in. Imagine a user who sees the new checkout and then, after you ramp up, sees the old one again. The test ramps through 10, 25 and 50 over 10,000 synthetic user ids and fails if any user ever flips out:

```text
percent=10 users_in=1017 of 10000
percent=25 users_in=2513 of 10000
percent=50 users_in=5020 of 10000
```

Each line is one step of the ramp: how many of the 10,000 users were in at that percentage. The test passes. That follows directly from the rule `bucket < percent`: raising `percent` only adds buckets and never removes any. The numbers are close to 10%, 25% and 50%, which means the hash spreads users fairly evenly. Another test counts users per block of ten buckets, and each block should hold about 1,000:

```text
[1017 990 1005 1003 1005 982 1006 1013 988 991]
```

Mixing the flag name into the hash matters. Without it, the same 10% of users would be the test group for every flag, and those users would get all the experiments while the other 90% got none.

## Live reload

The point of a flag is that behavior changes without a deploy. To show this, a tiny program reads a config file, checks two flags for the user `alice` (the real `new-pricing` flag and a flag name that does not exist, `typo-flag`), and waits. I edit the file, press Enter, and it reloads and checks again. The first config gives `alice` an override of false with 0 percent. I changed it to 100 percent with no override. The output, with time stamps removed:

```text
-- before first load
level=INFO msg=flag name=new-pricing user=alice on=false why=unknown
level=INFO msg=flag name=typo-flag user=alice on=false why=unknown
-- after load
level=INFO msg=flag name=new-pricing user=alice on=false why=override
level=INFO msg=flag name=typo-flag user=alice on=false why=unknown
press enter after editing the file
-- after reload
level=INFO msg=flag name=new-pricing user=alice on=true why=percent
level=INFO msg=flag name=typo-flag user=alice on=false why=unknown
```

Before the first load the store is empty, so both flags are unknown and off. After the load, `new-pricing` is still off, but now for a different reason: the override. After I edited the file and reloaded, it is on, because the percentage now decides. The `typo-flag` line is the fail-safe: it is off every time. This is the same process with new behavior, and no restart. A test also reloads while eight goroutines are evaluating flags, under `-race`, and passes. The `why` field is worth keeping in real systems. It answers the support question "why did this user see it?".

## Both branches, and branch by abstraction

Every flag doubles a code path: the code runs the old way or the new way, and both need tests. A technique that keeps this manageable is {{< term "branch-by-abstraction" "branch by abstraction" >}}: put the old and the new implementation behind one interface, and let the flag choose which to use. My `shop` package does this with a `Pricer` interface, switched by `new-pricing`. One test runs the same expectations with the flag at 0 and at 100 percent, so both paths are tested.

How do I know the new code is correct before I ramp? A {{< term "characterization-test" "characterization test" >}} compares the old and the new implementation on many inputs and requires equal results. Mine compares them on 8866 inputs, and they agree. The working method is: merge the new code dark (flag off) every day, and when the comparison holds, ramp.

## The cost

The cost of flags is mostly in combinations. n independent boolean flags give 2^n configurations. The test printed:

```text
3 boolean flags -> 8 configurations
10 boolean flags -> 1024 configurations
20 boolean flags -> 1048576 configurations
```

You will not test them all. **In my experience** most flags do not interact with each other, but the ones that do will fail in production. So keep flags independent and few.

Old flags are debt. The demo repo for this check has three commits, with a fake author and fixed dates. The history is staged for the demo, not a real project. A script lists the flags defined in `flag/flags.go`, counts the references to each outside that file, and finds the first commit that mentioned the name with `git log -S`:

```text
old-banner     refs=0 first_added=2026-01-10
fast-checkout  refs=1 first_added=2026-03-02
new-pricing    refs=2 first_added=2026-04-20
```

`old-banner` is defined, referenced nowhere, and the oldest. That makes it a removal candidate. My removal checklist: ramp to 100 percent and wait; delete the losing branch and the flag check; delete its tests; delete the config entry; delete the constant.

## Trunk-based in practice

Trunk-based development means short-lived branches, merged to `main` at least daily, with unfinished work hidden behind flags. Advice on how long a branch may live varies; I aim for a day or two. A few words you will meet around this: a **dark launch** deploys code that runs but whose result users do not see, and a canary exposes a small percentage of users, as in the percentage rollout above. Compared with GitFlow, the older model with long-lived `develop` and release branches, the differences are these:

| | GitFlow | Trunk-based |
|---|---|---|
| Branches | long-lived develop, release | short-lived, one `main` |
| Unfinished work | sits on a branch | merged behind a flag |
| Needs | merge discipline | fast CI, tests, flags |

**In my opinion** trunk-based fits a service that is deployed often, and GitFlow suits software with versioned releases. With flags, rollback also becomes simple: flip the flag first, and revert the code later, at leisure.

## Where flags bite

- Flags are not access control. Do not decide authorization with them: a flag is a rollout tool, not a permission system.
- Test the flag-off path too, because it is your rollback. If it is broken, your rollback does not work.
- Every flag needs an owner and a removal date, or it will stay forever.
- I did not run OpenFeature. As far as I know it is a vendor-neutral standard API for flag evaluation; check its docs before relying on that.

## What's next

The next post is "Designing a CI/CD pipeline". Trunk-based development only works if every merge is checked quickly and automatically, and that check is the pipeline.
