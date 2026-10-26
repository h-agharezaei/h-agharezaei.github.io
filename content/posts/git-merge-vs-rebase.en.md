+++
date = '2026-11-03T10:00:00+03:30'
draft = false
title = 'Merge or rebase? Two real histories'
description = 'Git merge vs rebase with real output: merge commits, fast-forward, changing hashes, the golden rule, force-with-lease, pull --rebase and squash.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge", "rebase", "beginner"]
cover = { image = "/images/covers/git-merge-vs-rebase.png", alt = "Merge or rebase? Two real histories", hiddenInSingle = true }
+++

In the [previous post](/posts/git-branches-head-refs/) we saw that a branch is only a pointer to a commit. That makes the next question easy to state: when two branches have gone separate ways, how do you bring them back together? Git gives two answers, {{< term "merge" "merge" >}} and {{< term "rebase" "rebase" >}}. Both end with the same files, but they leave different histories behind.

> Everything below ran with Git 2.39.2 in temp repos. I fixed the commit dates so the hashes are reproducible. Paths in the output are shortened.

## The starting point

`main` has two commits after the split (M1, M2) and `feature` has two (F1, F2), both branching from A:

```text
* da67a24 F2: feature two
* 9dfc2e3 F1: feature one
| * 028a1d9 M2: main two
| * 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

I built this twice, so each approach gets its own repo.

## Option 1: merge

`main` moved, so a {{< term "fast-forward" "fast-forward" >}} is impossible. Asking for one anyway fails:

```text
$ git merge --ff-only feature
fatal: Not possible to fast-forward, aborting.
```

A normal merge creates a {{< term "merge-commit" "merge commit" >}}:

```text
*   51bb97e Merge feature
|\
| * da67a24 F2: feature two
| * 9dfc2e3 F1: feature one
* | 028a1d9 M2: main two
* | 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

The old hashes survive. The history tells the truth: two lines of work existed and were joined. The cost is a busier graph.

## Option 2: rebase

In the second repo, from `feature` I ran `git rebase main`. Before, `feature` was `da67a24`, `9dfc2e3`. After:

```text
* 6b40805 F2: feature two
* c170ba7 F1: feature one
* 028a1d9 M2: main two
* 1c4c0d2 M1: main one
* 2cec988 A: first
```

The history is a straight line, but look at the ids: F1 was `9dfc2e3` and is now `c170ba7`, F2 went from `da67a24` to `6b40805`. Rebase does not move commits; it creates copies on a new base. Then `git merge --ff-only feature` on `main` is a pure fast-forward (`Updating 028a1d9..6b40805`, `Fast-forward`) and no merge commit appears.

If you want a merge commit even when a fast-forward is possible, use `--no-ff`. I tried it on a branch that could fast-forward and got `Merge made by the 'ort' strategy` plus a diamond in the graph.

## The golden rule

Never rebase commits that other people already have. I reproduced the problem with a bare repo and two clones, ali and sara, both on `feature` with F1. Ali rebases onto a newer `main`. A normal push is rejected (`! [rejected] feature -> feature (non-fast-forward)`), so Ali pushes with {{< term "force-push" "force push" >}}:

```text
 + 9e3e10c...2a3363a feature -> feature (forced update)
```

Meanwhile sara committed F2 on top of the old F1. Her `git pull` printed `(forced update)` for `origin/feature` and then made a merge commit. Her history now holds the same change twice:

```text
*   20db2d8 Merge branch 'feature' of origin into feature
|\
| * 2a3363a F1: feature one
| * 26aa3e9 M1: main one
* | 3569d28 F2: sara's work
* | 9e3e10c F1: feature one
|/
* f188366 A: first
```

`F1: feature one` appears twice, with different hashes. This is the mess the rule prevents.

## Protecting yourself

`--force-with-lease` only overwrites the remote if it is still where you last saw it. I ran it after sara had pushed F2 and Ali had not fetched:

```text
 ! [rejected]        feature -> feature (stale info)
```

Plain `--force` would have erased F2.

If you did not push your own work yet, `git pull --rebase` replays your local commits on top of the rewritten remote. In the same scenario it gave a clean line, where F1 is not duplicated:

```text
* b5645b5 F2: sara's work
* 2a3363a F1: feature one
* 26aa3e9 M1: main one
* f188366 A: first
```

## Squash

`git merge --squash feature` stages the combined changes (`A f1.txt`, `A f2.txt`) and stops; you commit once. The log is one commit on top of M2 (`b395ae0 Add feature (squashed)`). Note that `git branch --no-merged` still lists `feature`, because Git sees no link to its commits.

## Which one to use

This table is my opinion, not a rule:

| Situation | I choose |
|---|---|
| Updating my private feature branch from `main` | rebase |
| Joining a finished feature into `main` | merge (or squash if the commits are noise) |
| A branch others also push to | merge, never rebase |
| Fixing my last few local commits | rebase |

## A few things to watch

- Rebase rewrites history. After it, `git push` needs a force, so use `--force-with-lease`.
- A rebase conflict is solved per replayed commit, which can mean solving the same area several times.
- A squash loses the individual commits, and `git bisect` loses precision with them.
- I did not test rebase with conflicts here; that is the next post.

## Exercise

Make a repo with a diverged `main` and `feature`. Merge it, then `git reset --hard` back and rebase instead. Compare `git log --graph --oneline` and note which hashes changed.

## What's next

The next post is "Resolving conflicts and rerere".
