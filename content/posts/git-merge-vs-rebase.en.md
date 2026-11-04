+++
date = '2026-11-03T10:00:00+03:30'
draft = false
title = 'Merge or rebase? Two real histories'
description = 'Git merge vs rebase with real output: merge commits, fast-forward, changing hashes, the golden rule, force-with-lease, pull --rebase and squash.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "merge", "rebase", "beginner"]
cover = { image = "/images/covers/git-merge-vs-rebase.png", alt = "Merge or rebase? Two real histories", hiddenInSingle = true }
+++

Suppose you branched off `main` for a feature and made two commits on it. In the meantime a teammate put two more commits on `main`. Now your branch is behind `main`, and `main` has commits you do not have. How do we put the two back together?

Git has two answers: **{{< term "merge" "merge" >}}** and **{{< term "rebase" "rebase" >}}**. Both end with the same files, but they leave different histories behind:

- **merge** creates a new commit that ties the work of both sides together. The old commits are untouched and their hashes stay the same.
- **rebase** takes your commits and rebuilds them on top of the latest commit of `main`. The result is a straight line, but the rebuilt commits have new hashes.

That difference decides whether rewriting history and force pushing will hurt your teammates. A branch is only a pointer to a commit ([previous post](/posts/git-branches-head-refs/)), so both methods are really answers to where the pointers should end up and which commits sit between them. In this post we see both on one real history.

> Everything below ran with Git 2.39.2 in temp repos. I fixed the commit dates so the hashes are reproducible. Paths in the output are shortened.

## The starting point

For a fair comparison I built a simple history. After the split, `main` has two commits (M1 and M2) and `feature` has two (F1 and F2), both branching from the first commit A:

```text
* da67a24 F2: feature two
* 9dfc2e3 F1: feature one
| * 028a1d9 M2: main two
| * 1c4c0d2 M1: main one
|/
* 2cec988 A: first
```

Each `*` is a commit. You can see two parallel lines that split from A. I built this twice, so each approach gets its own repo and cannot affect the other.

## Method one: merge

The simplest merge is the one from the previous post: if `main` has nothing that `feature` lacks, Git just moves the pointer forward (a **{{< term "fast-forward" "fast-forward" >}}**). But here `main` has moved on, so a fast-forward is impossible. If we insist with `--ff-only`, Git refuses:

```text
$ git merge --ff-only feature
fatal: Not possible to fast-forward, aborting.
```

Without that flag, Git creates a **{{< term "merge-commit" "merge commit" >}}**, a commit with two parents: the tip of `main` and the tip of `feature`.

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

At the top there is one new commit (`51bb97e`) that joins the two lines. The old hashes (`da67a24`, `9dfc2e3` and the rest) are all still there. The history tells the truth about what happened: there were two lines of work, and then they were joined. The cost is a busier graph, especially when merges pile up.

## Method two: rebase

In the second repo I ran `git rebase main` on `feature`. It means: "take my commits and place them as if they had started from the tip of `main`." Before that, `feature` had two commits with hashes `da67a24` and `9dfc2e3`. After the rebase (the first line is rebase's own message, the rest is `git log --graph --oneline`):

```text
Successfully rebased and updated refs/heads/feature.

* 6b40805 F2: feature two
* c170ba7 F1: feature one
* 028a1d9 M2: main two
* 1c4c0d2 M1: main one
* 2cec988 A: first
```

The history became a straight line with no merge commit. But look at the ids: F1 used to be `9dfc2e3` and is now `c170ba7`, and F2 went from `da67a24` to `6b40805`. Why? Remember from [the first post](/posts/git-how-git-thinks/) that every commit contains the hash of its parent. F1 now has a different parent (M2 instead of A), so even though the change it carries is the same, it is a different commit and gets a different hash. F2's parent changed too, so the same is true for it. So rebase does not move commits. It makes new versions of them on the new base and moves the `feature` pointer to the new versions.

To bring the work into `main`, we now run `git merge --ff-only feature` on `main`. Because `feature` continues exactly from the tip of `main`, this is a pure fast-forward (the output is `Updating 028a1d9..6b40805` and `Fast-forward`) and no merge commit is made.

If you want a merge commit even when a fast-forward is possible, give the `--no-ff` option. I tried it on a branch that could have fast-forwarded: the output was `Merge made by the 'ort' strategy` and the graph got a diamond (two lines meeting).

## The golden rule

Now the most important rule of rebase: **do not rebase commits that other people already have.** Why? Because rebase makes new commits with new hashes. If someone else kept working on the old version, you now have two incompatible histories.

To see the problem I recreated the scene with a bare repo and two clones, ali and sara. Both were on `feature` and had commit F1. Ali moved `main` forward and rebased `feature` onto it. Git rejects a normal push, because Ali's history no longer continues the version on the remote (`! [rejected] feature -> feature (non-fast-forward)`). So Ali uses a **{{< term "force-push" "force push" >}}**, which tells the remote to throw away its version and take this one:

```text
 + 9e3e10c...2a3363a feature -> feature (forced update)
```

The `+` and `(forced update)` mean the remote went from `9e3e10c` (the old F1) to `2a3363a` (the rebuilt F1).

Meanwhile Sara had made a commit called F2 on top of the old F1. When she runs `git pull`, the `fetch` part prints the same `(forced update)` for `origin/feature`, and then Git stops, because her history and the remote's have diverged and Git does not know how to combine them. The output ends with this line:

```text
fatal: Need to specify how to reconcile divergent branches.
```

(This is with default settings. If you have set `pull.rebase` in your config, Git runs that without asking.) Sara picks the first option from the hint and runs `git pull --no-rebase`, which means merge. Git creates a merge commit, and Sara's history now has one change twice:

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

`F1: feature one` appears twice, once with the old hash (`9e3e10c`) and once with the rebuilt hash (`2a3363a`). This is exactly the mess the golden rule prevents. (The hash of the merge commit itself differs in your run, because its message contains the remote's path; I shortened the path in the text.)

## Protecting yourself

Sometimes you really do need to force push, for example after rebasing a personal branch. Two tools reduce the damage.

**`--force-with-lease`.** A plain `--force` overwrites the remote without any check. `--force-with-lease` overwrites only if the remote is still where you last saw it. To try it, Sara had pushed F2 and Ali had not fetched yet. Ali ran this:

```text
 ! [rejected]        feature -> feature (stale info)
```

`stale info` means Ali's information about the remote is out of date and the remote has something he has not seen. Git rejected the push, and Sara's work was saved; a plain `--force` would have erased F2.

**`git pull --rebase`.** If your own work is not pushed yet, this replays your local commits on top of the rewritten remote instead of making a merge. In the same scenario (this time Sara had not pushed F2) the result was clean:

```text
* b5645b5 F2: sara's work
* 2a3363a F1: feature one
* 26aa3e9 M1: main one
* f188366 A: first
```

In the output I saw `Rebasing (1/1)`, which means only one commit was replayed (F2), and F1 was not duplicated. The history is a straight line.

## Squash

A third way is not to keep the commits of `feature` at all. `git merge --squash feature` stages the sum of the changes (`A f1.txt` and `A f2.txt`) and stops; you make one commit yourself. The log has only one commit on top of M2 (`b395ae0 Add feature (squashed)`), and F1 and F2 are not in it.

One note: after a squash, `git branch --no-merged` still lists `feature`. Git sees no link between the new commit and the commits of `feature`, so it thinks that branch is not merged yet.

## Which one to choose

This table is my opinion, not a rule:

| Situation | My choice |
|---|---|
| Updating my personal branch from `main` | rebase |
| Bringing a finished feature into `main` | merge (or squash if the commits are noise) |
| A branch others also push to | merge, never rebase |
| Tidying my last few local commits | rebase |

## The cost of rewriting history

- **Rebase rewrites history.** After it, `git push` needs force, so use `--force-with-lease`.
- **Conflicts in a rebase are resolved per commit.** The commits are replayed one by one, so you may resolve the same area several times.
- **Squash destroys the separate commits.** It also makes `git bisect` (finding the commit that broke something) less precise, because you have one big commit instead of several small ones.
- **I did not try a rebase with conflicts here.** That is the topic of the next post.

## Exercise

Create a repo with `main` and a diverged `feature`. Merge once, then go back to before the merge with `git reset --hard` and rebase this time. Compare the output of `git log --graph --oneline` and see which hashes changed.

## What's next

Next is "Resolving conflicts and rerere". Both methods can stop halfway on a conflict, and we did not try that case here.
