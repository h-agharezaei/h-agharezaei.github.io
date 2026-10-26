+++
date = '2026-11-15T10:00:00+03:30'
draft = false
title = 'Submodules, subtrees and worktrees'
description = 'Git submodules, subtrees and worktrees compared with real runs: gitlinks, forgotten clones, unpushed pointers, subtree split and two branches at once.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "submodule", "subtree", "worktree"]
cover = { image = "/images/covers/git-submodule-subtree-worktree.png", alt = "Submodules, subtrees and worktrees", hiddenInSingle = true }
+++

In the [previous post](/posts/git-hooks-commit-hygiene/) we automated checks around commits. Now the other side of daily Git: what to do when your repository needs *another* repository, and what to do when you need two branches on disk at once. Git has three tools for this, and they are easy to confuse: {{< term "submodule" "submodules" >}}, {{< term "subtree" "subtrees" >}} and {{< term "worktree" "worktrees" >}}.

This blog already uses one. `.gitmodules` in its repo contains a single entry, `themes/PaperMod`, pointing at the PaperMod GitHub repository, and `git submodule status` prints `7d061d5... themes/PaperMod (v8.0-54-g7d061d5)`. That is a pinned commit of someone else's code.

> Everything below was run with Git 2.39.2 in throwaway repositories under a temp directory, using local repos as remotes. Hashes differ on every run, so yours will not match. I put `protocol.file.allow=always` in the environment of the demo, because Git blocks local-path submodules by default. That is only needed for local demos.

## A submodule is a pointer

Setup: a `lib` repo and an `app` repo. Then:

```bash
cd app
git submodule add ../lib lib
git commit -m "add lib submodule"
git ls-tree HEAD
```

```text
100644 blob 008e8edaf3165b09395d7d5fe13cb3e657072b74	.gitmodules
100644 blob b80f0bd60822d4fa4893de455958ef32f6c521bf	README
160000 commit 390b441e850cdffb00b1fed3b0abb7551293e794	lib
```

The `lib` entry is a {{< term "gitlink" "gitlink" >}}: mode `160000` and a commit id, not a tree. `app` stores no files of `lib`, only "use commit 390b441". The URL lives in `.gitmodules`.

## Forgetting --recurse-submodules

```bash
git clone app app-plain
ls -A app-plain/lib | wc -l      # 0
git -C app-plain submodule status
```

```text
       0
-390b441e850cdffb00b1fed3b0abb7551293e794 lib
```

The directory exists but is empty, and the leading `-` means "not initialized". Fix it with `git submodule update --init`, or clone with `git clone --recurse-submodules` in the first place. Inside the submodule you are on a {{< term "detached-head" "detached HEAD" >}}:

```text
HEAD detached at 390b441
```

That is by design: the parent pins a commit, not a branch. If you commit there and then switch away, the new commit has no branch pointing at it.

## Moving the pointer

When `lib` gets a new commit, the parent does not notice by itself:

```bash
git submodule update --remote    # fetch lib, check out its latest main
git status --short               #  M lib
git commit -am "bump lib to v2"
```

The change in `app` is one line: the gitlink now names a different commit.

## The classic mistake: pointer to a commit nobody can fetch

I committed inside `app/lib`, committed the new pointer in `app`, but never pushed `lib`. A collaborator then pulled:

```text
Fetching submodule lib
fatal: git upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
fatal: remote error: upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
Errors during submodule fetch:
	lib
pull exit=1
```

The parent's commit is valid, but it points at a commit that exists only on my disk. The rule: push the submodule first, then the parent. After I pushed `lib`, the same pull and `git submodule update` worked.

## Subtrees: just files

`git subtree` ships with this Git install (I checked that `git-subtree` is in the exec path; it is a contrib command, so some builds may lack it):

```bash
git subtree add --prefix=vendor/lib ../lib main --squash
git subtree pull --prefix=vendor/lib ../lib main --squash -m "pull lib"
git subtree split --prefix=vendor/lib -b lib-only
git log --oneline lib-only
```

```text
Added dir 'vendor/lib'
 vendor/lib/greet.txt | 2 +-
861c90e app: tweak greet
e229a82 lib: v2
556dcb6 lib: first
```

The files are now normal files in `app`: a plain clone has them, no extra command. `split` rebuilt a history containing only the changes under `vendor/lib`, which you could push back to `lib`. The cost is a noisier history and commands that are harder to remember.

## Worktrees: two branches at once

```bash
git worktree add -b hotfix ../app-hotfix
git worktree list
git worktree add ../app-again hotfix
```

```text
Preparing worktree (new branch 'hotfix')
HEAD is now at 8de0ccd app: tweak greet
<tmp>/app         8de0ccd [main]
<tmp>/app-hotfix  8de0ccd [hotfix]
fatal: 'hotfix' is already checked out at '<tmp>/app-hotfix'
```

Both directories share one object database, so there is no second clone. The error is the safety rule: one branch, one worktree. `git worktree remove ../app-hotfix` cleans up. (`<tmp>` replaces my long temp path.)

## Which one?

| | Submodule | Subtree | Worktree |
|---|---|---|---|
| What it is | Pinned commit of another repo | Another repo's files copied in | Extra checkout of the same repo |
| Collaborator extra step | Yes (`--recurse-submodules`) | No | n/a |
| History | Separate | Mixed into yours | Same |
| My judgment | Good for a few pinned dependencies | Good when you want zero ceremony | Great for hotfixes and reviews |

The last row is my opinion, not a measurement.

## A few things to watch

- Always clone with `--recurse-submodules`, or run `git submodule update --init` afterwards.
- Push the submodule before the parent.
- Do not commit on a detached HEAD in a submodule without making a branch first.
- Do not copy a subtree's files by hand; use `subtree pull` so history stays mergeable.
- I did not test `git worktree prune` or locked worktrees.

## Exercise

1. Reproduce the empty-directory clone, then fix it with `git submodule update --init`.
2. Make a commit in a submodule, bump the pointer, and trigger the "not our ref" error from a second clone.
3. Add a worktree for a hotfix branch, commit there, remove it and merge the branch.

## What's next

In the next post, Team workflows and packfiles inside, we will look at how teams use branches and pull requests day to day, and how Git stores objects in packfiles.
