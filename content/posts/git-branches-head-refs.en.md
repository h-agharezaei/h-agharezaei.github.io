+++
date = '2026-11-01T10:00:00+03:30'
draft = false
title = 'Branches, HEAD and refs: just pointers'
description = 'Git branches explained: a branch is a 41-byte file, HEAD is a pointer, tags and remote-tracking branches are refs. Real runs, detached HEAD and recovery.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "branches", "refs", "head"]
cover = { image = "/images/covers/git-branches-head-refs.png", alt = "Branches, HEAD and refs: just pointers", hiddenInSingle = true }
+++

In the [previous post](/posts/git-index-staging/) we followed a change through the working tree, the index and the repository. Now the question is where all those {{< term "commit" "commits" >}} hang from. Branches feel heavy because we say "switch to a branch" and "copy a branch", but in Git a {{< term "git-branch" "branch" >}} is only a name that points at one commit.

> Everything below was run with Git 2.39.2 in a throwaway directory. The commit ids are from that run and will differ on your machine.

## A branch is a file

```text
$ git log --oneline
33cf254 second
7d52f5a first
$ cat .git/refs/heads/main
33cf25487ec218f465e614aa03dfb60f2827492f
$ wc -c < .git/refs/heads/main
      41
```

That is the whole branch: 40 hex characters plus a newline. Making a commit on `main` writes a new id into this file. A name that points at an object like this is called a {{< term "git-ref" "ref" >}}.

## HEAD says where you are

```text
$ cat .git/HEAD
ref: refs/heads/main
$ git symbolic-ref HEAD
refs/heads/main
```

{{< term "head" "HEAD" >}} is a file too. Normally it contains the name of a branch (a symbolic ref), so "the current branch" simply means "the branch HEAD names".

## Creating a branch writes a file

```text
$ git branch feature
$ cat .git/refs/heads/feature
33cf25487ec218f465e614aa03dfb60f2827492f
$ git update-ref refs/heads/other HEAD
$ git branch
  feature
* main
  other
```

`git branch feature` and the low-level `git update-ref` produce the same thing. Nothing is copied, so branches are free. `git switch -c work` creates a branch and moves HEAD to it:

```text
$ git switch -c work
Switched to a new branch 'work'
$ cat .git/HEAD
ref: refs/heads/work
$ git branch -vv
  feature 33cf254 second
  main    33cf254 second
  other   33cf254 second
* work    b9cdb9f third on work
```

## Fast-forward

I committed once on `work`, then went back and merged it:

```text
$ git switch main
$ git merge work
Updating 33cf254..b9cdb9f
Fast-forward
 a.txt | 1 +
 1 file changed, 1 insertion(+)
```

`main` had nothing `work` lacked, so Git only moved the `main` pointer. This is a {{< term "fast-forward" "fast-forward" >}}; no merge commit was created. The next post covers what happens when both sides have new commits.

## Detached HEAD and getting a commit back

If HEAD holds a commit id instead of a branch name, you are in {{< term "detached-head" "detached HEAD" >}} state:

```text
$ git switch -q --detach HEAD~1
$ cat .git/HEAD
33cf25487ec218f465e614aa03dfb60f2827492f
```

I made a commit here ("experiment") and switched back to `main`. Git warned me:

```text
$ git switch main
Warning: you are leaving 1 commit behind, not connected to
any of your branches:

  936605f experiment
```

No branch points at it now, but the {{< term "reflog" "reflog" >}} remembers:

```text
$ git reflog -3
b9cdb9f HEAD@{0}: checkout: moving from 936605f9f7b2665e474a43782d150fd05721086d to main
936605f HEAD@{1}: commit: experiment
33cf254 HEAD@{2}: checkout: moving from main to HEAD~1
$ git branch rescue HEAD@{1}
$ git log --oneline -2 rescue
936605f experiment
33cf254 second
```

A new ref is all it takes to make the commit reachable again. According to the Git docs, unreachable commits are eventually removed by garbage collection, so do this soon.

## Tags are refs too

```text
$ cat .git/refs/tags/v1
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
$ cat .git/refs/tags/v2
676128add498eaa876a334d3006c831472d72d40
$ git cat-file -t v1
commit
$ git cat-file -t v2
tag
$ git rev-parse v2^{commit}
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

`v1` was made with `git tag v1` and is a lightweight tag: a ref straight to the commit. `v2` was made with `git tag -a v2 -m "release two"`; it is an {{< term "annotated-tag" "annotated tag" >}}, a separate {{< term "git-object" "object" >}} that points at the commit. Unlike a branch, a tag does not move when you commit.

## Remote-tracking branches

I created a bare repository next to the demo (`git init --bare -b main remote.git`), added it as `origin` and pushed. A second clone pushed a `topic` branch to it.

```text
$ git push -u origin main
To ../remote.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
$ git fetch
From ../remote
 * [new branch]      topic      -> origin/topic
$ git branch -r
  origin/main
  origin/topic
$ cat .git/refs/remotes/origin/main
b9cdb9f4f45a9b29b0212c54f49b83a17ec79149
```

`origin/main` is a {{< term "remote-tracking-branch" "remote-tracking branch" >}}: a local ref that records where the remote was the last time we talked. `git for-each-ref` lists every ref in one go: `refs/heads/...`, `refs/tags/...` and `refs/remotes/...`.

## Deleting a branch

I made a `wip` branch with one commit that exists nowhere else:

```text
$ git branch -d wip
error: The branch 'wip' is not fully merged.
If you are sure you want to delete it, run 'git branch -D wip'.
$ git branch -D wip
Deleted branch wip (was 75edf86).
```

`-d` refuses because deleting the pointer would orphan the commit. `-D` forces it, and the id it prints is your way back (`git branch wip 75edf86`).

## A few things to watch

- Deleting a branch deletes a pointer, not commits, but unreachable commits do not live forever.
- Do not commit in detached HEAD without giving the work a branch name.
- `origin/main` can be stale: run `git fetch` before reasoning about it.
- Never edit files under `.git/refs/` by hand in a real repo; use `git branch` or `git update-ref`.

## Exercise

In a new repo, make three commits. Create a branch on the first one with `git branch old HEAD~2` and read the file it created. Then switch to `old`, force-delete `main` with `git branch -D main`, and bring it back using only the id Git printed or the reflog.

## What's next

The next post is "Merge or rebase? Two real histories", where both branches have new commits and Git has to decide how to join them.
