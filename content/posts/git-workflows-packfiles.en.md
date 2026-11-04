+++
date = '2026-11-17T10:00:00+03:30'
draft = false
title = 'Team workflows and packfiles inside'
description = 'Git workflows and packfiles: trunk-based, GitHub flow and Gitflow compared, then git gc, verify-pack, shallow, partial and sparse clones in real runs.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "workflows", "packfiles"]
cover = { image = "/images/covers/git-workflows-packfiles.png", alt = "Team workflows and packfiles inside", hiddenInSingle = true }
+++

A 2000-line file that has been edited 40 times with small changes takes 3384 KB on disk. After one `git gc` the same repository is 268 KB. Where does that gap of about 12x come from? The answer also explains why Git has options like shallow and partial clones for big repositories.

This is the last post of the series and it has two parts. First, a short look at how teams organise their work on branches (their workflow). Then a look inside `.git` to see exactly how objects are stored on disk. From the [first post](/posts/git-how-git-thinks/) you know that Git keeps everything as immutable objects; now we see how those objects get packed tightly. The previous post was about [submodules, subtrees and worktrees](/posts/git-submodule-subtree-worktree/).

> The demos were run with Git 2.39.2 on macOS in throwaway directories, and the numbers are copied from those runs. Hashes and the pack size differ by a few characters or a few KB from run to run. I ran no hosting service, so branch protection is only a concept here.

## Team workflows in short

When several people work on one repository, they have to agree on a few things: which branch does new work go on? What may reach `main`? When and how does it get deployed? That agreement is the workflow. There are a few common patterns. The table is my opinion, not a standard:

| Workflow | Idea | Good fit | Cost |
|---|---|---|---|
| {{< term "trunk-based-development" "Trunk-based" >}} | Tiny daily changes to `main`, {{< term "feature-flag" "flags" >}} hide unfinished work | Strong CI, frequent deploys | Needs discipline |
| GitHub flow | Short branch, pull request, review, merge, deploy | Most backend teams | Long branches hurt |
| Gitflow | `main`, `develop`, feature, release, hotfix branches | Versioned products | Many branches |
| Release branches | Cut `release/1.4`, fix only bugs there | Mobile apps, libraries | Manual backports |

A few words on the "Idea" column. In trunk-based development everyone works directly on `main` (or on branches that live a day), and unfinished work stays switched off behind a flag: the code is there, but users cannot see it. In GitHub flow you make a short branch for each piece of work, open a pull request, someone reviews it, and then it is merged and deployed. Gitflow is for products that ship named versions on a schedule. A release branch means that once version 1.4 ships, you keep a branch for it so you can fix bugs in that version only, and bring those fixes to `main` too (with cherry-pick).

My default is GitHub flow; I use release branches only to patch an old version. One tool helps in all of these: {{< term "branch-protection" "branch protection" >}}, a server-side rule that says `main` changes only through a reviewed pull request with passing checks. This blog works that way. Its latest five merges, at the time of writing:

```bash
git log --oneline --merges -5
```

```text
3d46fe0 Merge pull request #14 from h-agharezaei/post-binance-hack
e199ee2 Merge pull request #13 from h-agharezaei/switch-domain-justroham
3235020 Merge pull request #12 from h-agharezaei/switch-domain-justroham
677819c Merge pull request #11 from h-agharezaei/switch-domain-justroham
5831598 Merge pull request #10 from h-agharezaei/switch-domain-justroham
```

Each line is a merge commit that brought a pull request into `main`. (On your machine, in another repository, you will see something else; and for this blog the list moves on with every new pull request.)

## Loose objects and the packfile

Now let us look inside `.git`. When an object (commit, tree, blob) is created, it first lands on disk as a separate file. This is called "loose". It is simple and fast, but when a big file changes many times, every version becomes a full file, even if only one line differs.

To see the effect I made a repo with one 2000-line file and 40 small edits, one commit each. Then I took the object count and the size of `.git`:

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

`count` is the number of loose objects and `size` their size in KB. `in-pack: 0` and `packs: 0` mean nothing has been packed yet. (The dots stand for a few more lines that do not matter here.) So we have 123 loose objects and `.git` is about 3.3 MB, because each file version is stored in full. Now run garbage collection:

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

This time `count: 0`: no loose objects are left. All 123 are in one pack (`in-pack: 123`, `packs: 1`) and the size of `.git` went from 3384 KB to 268 KB. A {{< term "packfile" "packfile" >}} is one file that holds many objects, and the `.idx` file next to it is an index that says where each object is inside the pack.

Most of the shrinkage comes from {{< term "delta-compression" "delta compression" >}}. The idea is simple: when versions 20 and 21 of a file are nearly identical, there is no need to keep both in full. Store one in full and the other only as a small diff against it (a delta). `git verify-pack -v` shows this. The full output is long; here are a few lines of it and the summary at the end (offsets differ from run to run):

```text
8dc7cd65... blob 143281 69145 5295
48db3cc6... blob     43    48 74531 1 8dc7cd65...
36070a34... blob     43    45 74698 5 80839e73...
non delta: 84 objects
chain length = 1: 5 objects
chain length = 2: 3 objects
chain length = 3: 4 objects
chain length = 4: 2 objects
chain length = 5: 4 objects
chain length = 6: 4 objects
chain length = 7: 3 objects
chain length = 8: 2 objects
chain length = 9: 5 objects
chain length = 10: 3 objects
chain length = 11: 3 objects
chain length = 12: 1 object
```

The columns on each line are: id, type, original size, size inside the pack, offset in the file, and, for deltas, the chain depth and the id of the base. The first line is a 143 KB blob that is kept whole (with ordinary compression it takes 69 KB in the pack). The second line is another version that is only 43 bytes: a set of instructions on top of that first blob, at depth 1. The third has depth 5, meaning five deltas must be applied one after another on a base to rebuild it.

The `chain length` lines at the bottom say how many objects sit at each depth, and `non delta: 84 objects` means 84 objects (commits, trees and base blobs) are stored whole. Of this repository's 41 blobs, 39 were deltas, with chains up to depth 12. `git repack -a -d` rewrites everything into one pack; here it changed nothing, since `gc` had already done the job.

## Big repositories: shallow, partial, sparse

Now a practical question. You have a repository with ten years of history and thousands of files, and you want to make one small change. Why download everything? There are three options that skip part of it.

For comparison I built a small server repository: 7 commits, 5 documents and one source file, where every commit changes all six files (70 objects in total), and I enabled `uploadpack.allowFilter` on it so the server accepts filters. Object counts per kind of clone:

| Clone | Command | Objects |
|---|---|---|
| Full | `git clone file://...` | 70 |
| {{< term "shallow-clone" "Shallow" >}} | `--depth 1` | 10 (1 commit, 3 trees, 6 blobs) |
| {{< term "partial-clone" "Partial" >}} | `--filter=blob:none` | 34 (7 commits, 21 trees, 6 blobs) |

A shallow clone takes only the latest commit, so `git log` shows 1 line. `git fetch --unshallow` later restored all 7 commits and 42 blobs. A partial clone keeps the full history but downloads blobs, the file contents, only when needed: for example `git show HEAD~3:docs/doc1.txt` fetched one missing blob from the server (7 blobs afterwards). Git calls that server a "promisor remote", because it promised to supply the missing objects later; so you need the network later.

The third one, {{< term "sparse-checkout" "sparse checkout" >}}, does not change object counts by itself. It controls which directories appear on disk (in the working tree). Combined with a partial clone, only the blobs of those directories are downloaded:

```bash
git clone --filter=blob:none --sparse file://... sp
git sparse-checkout set app
ls
```

```text
app
```

The `--sparse` clone started with 0 blobs and no directories on disk. After `set app` one blob was downloaded (the source file) and only `app/` appeared on disk. Partial clone plus sparse checkout is the usual combination for large monorepos.

`git maintenance` can run `gc`-style housekeeping in the background; I did not run it.

## The price of the shortcuts

- **A shallow clone has no history.** So `git log` and `git blame` see little.
- **A partial clone needs its remote later.** Offline, a missing blob is an error.
- **`gc` can drop unreachable objects after a grace period.** According to the Git docs the default is about two weeks (`gc.pruneExpire`; I did not test it). So unreferenced commits are not a backup.
- **Branch protection belongs on the server.** Local hooks can be skipped, as we saw in the hooks post.

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

Next on the calendar is "The relational model and essential SQL", which opens the Databases series.
