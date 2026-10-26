+++
date = '2026-11-17T10:00:00+03:30'
draft = false
title = 'Team workflows and packfiles inside'
description = 'Git workflows and packfiles: trunk-based, GitHub flow and Gitflow compared, then git gc, verify-pack, shallow, partial and sparse clones in real runs.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "workflows", "packfiles"]
cover = { image = "/images/covers/git-workflows-packfiles.png", alt = "Team workflows and packfiles inside", hiddenInSingle = true }
+++

This is the last Git post. In the [previous post](/posts/git-submodule-subtree-worktree/) we looked at submodules, subtrees and worktrees. Here we close with how teams organize branches, and what Git does to keep a repository small, which explains the clone options for big repositories.

> The demos were run with Git 2.39.2 on macOS in throwaway directories, and the numbers are copied from those runs. I ran no hosting service, so branch protection is only a concept here.

## Team workflows in short

A workflow is an agreement about where work happens and what may reach `main`. The table is my opinion, not a standard:

| Workflow | Idea | Good fit | Cost |
|---|---|---|---|
| {{< term "trunk-based-development" "Trunk-based" >}} | Tiny daily changes to `main`, flags hide unfinished work | Strong CI, frequent deploys | Needs discipline |
| GitHub flow | Short branch, pull request, review, merge, deploy | Most backend teams | Long branches hurt |
| Gitflow | `main`, `develop`, feature, release, hotfix branches | Versioned products | Many branches |
| Release branches | Cut `release/1.4`, fix only bugs there | Mobile apps, libraries | Manual backports |

My default is GitHub flow; I use release branches only to patch an old version. Branch protection is a server-side rule: `main` accepts changes only through a reviewed pull request with passing checks. This blog works that way:

```bash
git log --oneline --merges -5
```

```text
53c9acd Merge pull request #6 from h-agharezaei/add-glossary
fdb74d6 Merge pull request #5 from h-agharezaei/add-glossary
c848814 Merge pull request #4 from h-agharezaei/update-cover-domain
51d90ac Merge pull request #3 from h-agharezaei/add-go-cve-2026-111943-post
9e6f4d7 Merge pull request #2 from h-agharezaei/add-go-cve-2026-111943-post
```

## Loose objects and the packfile

Every object starts as a separate "loose" file. I made a repo with one 2000-line file and 40 small edits, one commit each:

```bash
git count-objects -v
du -sk .git
```

```text
count: 123
size: 3280
in-pack: 0
packs: 0
...
3384	.git
```

123 loose objects, about 3.3 MB, because each file version is stored in full. Now run garbage collection:

```bash
git gc -q
git count-objects -v
du -sk .git
ls .git/objects/pack
```

```text
count: 0
in-pack: 123
packs: 1
size-pack: 148
268	.git
pack-8ba0db77...idx
pack-8ba0db77...pack
```

From 3384 KB to 268 KB. A {{< term "packfile" "packfile" >}} holds many objects in one file, and the `.idx` file is its index. Packs are smaller mostly thanks to {{< term "delta-compression" "delta compression" >}}: an object is stored as a small diff against a similar one. `git verify-pack -v` shows it:

```text
8dc7cd65... blob 143281 69145 5386
48db3cc6... blob     43    48 144494 1 8dc7cd65...
36070a34... blob     43    45 144661 5 80839e73...
non delta: 84 objects
chain length = 1: 5 objects
chain length = 5: 4 objects
chain length = 12: 1 object
```

Columns: id, type, size, size in pack, offset, and for deltas the chain depth and base. One 143 KB blob is stored in full; another version is 43 bytes on top of its base. 39 of the 41 blobs were deltas, with chains up to depth 12. `git repack -a -d` rewrites everything into one pack; here it changed nothing, since `gc` had done the job.

## Big repositories: shallow, partial, sparse

I built a small server repo with 7 commits, 5 documents and one source file (70 objects), with `uploadpack.allowFilter` enabled. Objects per clone:

| Clone | Command | Objects |
|---|---|---|
| Full | `git clone file://...` | 70 |
| {{< term "shallow-clone" "Shallow" >}} | `--depth 1` | 10 (1 commit, 3 trees, 6 blobs) |
| {{< term "partial-clone" "Partial" >}} | `--filter=blob:none` | 34 (7 commits, 21 trees, 6 blobs) |

A shallow clone has one commit, so `git log` shows 1 line; `git fetch --unshallow` later restored all 7 commits and 42 blobs. A partial clone keeps full history but downloads file contents on demand: `git show HEAD~3:docs/doc1.txt` fetched one missing blob (7 blobs afterwards). Git calls the remote a "promisor remote", so you need the network later.

{{< term "sparse-checkout" "Sparse checkout" >}} limits which directories appear in the working tree:

```bash
git clone --filter=blob:none --sparse file://... sp
git sparse-checkout set app
ls
```

```text
app
```

The `--sparse` clone started with 0 blobs; after `set app` one blob was downloaded and only `app/` was on disk. Partial clone plus sparse checkout is the usual combination for large monorepos.

`git maintenance` can run `gc`-style housekeeping in the background; I did not run it.

## A few things to watch

- A shallow clone has no history, so `git log` and `git blame` see little.
- A partial clone needs its remote later; offline, a missing blob is an error.
- `gc` can drop unreachable objects after a grace period, so unreferenced commits are not a backup.
- Branch protection belongs on the server; local hooks can be skipped.

## Wrapping up the series

Git stores immutable objects, branch names are pointers to them, and most commands add objects or move pointers. The nine earlier posts, in order:

- [How Git thinks: objects and hashes](/posts/git-how-git-thinks/)
- [The index and staging: Git's three areas](/posts/git-index-staging/)
- [Branches, HEAD and refs: just pointers](/posts/git-branches-head-refs/)
- [Merge or rebase? Two real histories](/posts/git-merge-vs-rebase/)
- [Resolving conflicts and rerere](/posts/git-resolve-conflicts/)
- [Undoing work: reflog, revert and cherry-pick](/posts/git-undo-reflog-revert/)
- [Finding a bug with git bisect](/posts/git-bisect/)
- [Hooks and clean commit messages](/posts/git-hooks-commit-hygiene/)
- [Submodules, subtrees and worktrees](/posts/git-submodule-subtree-worktree/)

## Exercise

Create a repo with a 1000-line file and 20 commits, each changing one line. Record `count-objects -v` and `du -sk .git`, run `git gc`, and compare. Find the longest delta chain with `verify-pack -v`. Then clone it with `--depth 1` and count objects with `git cat-file --batch-all-objects --batch-check`.

## What's next

This was the last Git post. The next post in the calendar starts the Databases series: The relational model and essential SQL.
