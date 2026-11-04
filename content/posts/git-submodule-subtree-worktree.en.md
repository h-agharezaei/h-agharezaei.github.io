+++
date = '2026-11-15T10:00:00+03:30'
draft = false
title = 'Submodules, subtrees and worktrees'
description = 'Git submodules, subtrees and worktrees compared with real runs: gitlinks, forgotten clones, unpushed pointers, subtree split and two branches at once.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "submodule", "subtree", "worktree"]
cover = { image = "/images/covers/git-submodule-subtree-worktree.png", alt = "Submodules, subtrees and worktrees", hiddenInSingle = true }
+++

Suppose your repository needs the code of another repository: a shared library, say, or a blog theme. Copying its folder into your project works, until the day the library fixes a bug and you cannot tell which version of it you have. Git has tools for this. And there is a related problem: you are in the middle of work on one branch, an urgent hotfix arrives, and you do not want to stash your half-finished work.

Three tools cover these cases, and they are easy to confuse: {{< term "submodule" "submodules" >}}, {{< term "subtree" "subtrees" >}} and {{< term "worktree" "worktrees" >}}. The first two are for when your repository needs another repository; the third is for when you want two branches on disk at once. After the [commit checks](/posts/git-hooks-commit-hygiene/), this is the other side of daily Git.

This blog already uses one. `.gitmodules` in its repo contains a single entry, `themes/PaperMod`, pointing at the PaperMod GitHub repository, and `git submodule status` prints `7d061d5... themes/PaperMod (v8.0-54-g7d061d5)`. That is a pinned commit of someone else's code. This post shows what is behind that one line and where it goes wrong.

> All commands were run with Git 2.39.2 in throwaway repositories, with local paths as remotes. Hashes differ on every run, so yours will not match. For the demo I set `protocol.file.allow=always` in the environment, because Git blocks submodules with a local path by default. That is only needed for a local demo.

## A submodule is just a pointer

The idea of a submodule is simple: the parent repository does not store the library's code. It only keeps a note that says "from that repository, take commit so-and-so". That is a pointer to one specific commit. To see it, I made two repos: `lib` (the library) and `app` (a program that uses it). Then I added the library to the program:

```bash
cd app
git submodule add ../lib lib
git commit -m "add lib submodule"
git ls-tree HEAD
```

The last command lists the contents of the commit, which is what Git really stored:

```text
100644 blob 008e8edaf3165b09395d7d5fe13cb3e657072b74	.gitmodules
100644 blob b80f0bd60822d4fa4893de455958ef32f6c521bf	README
160000 commit 390b441e850cdffb00b1fed3b0abb7551293e794	lib
```

The first two lines are ordinary files. `.gitmodules` is a small text file that holds the library repository's address. The last line is the interesting one: the `lib` entry is a {{< term "gitlink" "gitlink" >}}. Its mode is `160000`, and instead of a blob or tree it holds a commit id. `app` has no files from `lib`; it only says "take commit 390b441".

## Forgetting --recurse-submodules

A consequence of this design is the first trap. A plain clone brings the note, not the code. I cloned `app` and counted the files in `lib`:

```bash
git clone app app-plain
ls -A app-plain/lib | wc -l      # 0
git -C app-plain submodule status
```

```text
       0
-390b441e850cdffb00b1fed3b0abb7551293e794 lib
```

The `lib` folder exists but is empty (zero files). In the output of `submodule status`, the `-` at the start means "not initialised": Git has not fetched that commit yet. Fix it with `git submodule update --init`, or clone with `git clone --recurse-submodules` from the start.

Inside a submodule you notice something else: you are in {{< term "detached-head" "detached HEAD" >}} state, that is, standing on a commit rather than on a branch:

```text
HEAD detached at 390b441
```

This is on purpose, because the parent pins a commit, not a branch. But it has a trap: if you commit there and then switch away, the new commit has no branch pointing to it. To work on the library, create a branch first (or run `git switch main`).

## Moving the pointer

When `lib` gets a new commit, the parent does not notice, because it points at one fixed commit. You have to move the pointer yourself:

```bash
git submodule update --remote    # fetches lib and checks out the latest main
git status --short               #  M lib
git commit -am "bump lib to v2"
```

After `update --remote`, `git status` shows the `lib` folder as modified (`M lib`), because the commit it is now on differs from the one the parent recorded. Committing records the change. The change in `app` is a single line: the gitlink now points at a different commit.

## The classic mistake: a pointer to a commit nobody can fetch

Now the most common error with this tool. Inside `app/lib` I made a commit and committed the new pointer in `app`, but I did not push `lib`. Then a collaborator (another clone) ran `git pull`:

```text
Fetching submodule lib
fatal: git upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
fatal: remote error: upload-pack: not our ref fcc7862444cb18d7efe83c7f6a4628e8208d70a1
Errors during submodule fetch:
	lib
pull exit=1
```

The parent commit is valid, but it points at a commit that exists only on my disk. The `lib` server says "I have no such thing" (`not our ref`) and the pull fails. The rule: push the submodule first, then the parent. After I pushed `lib`, the same pull and `git submodule update` worked.

## subtree: just files

A submodule is a pointer; a {{< term "subtree" "subtree" >}} is the opposite, it brings the actual files into your repository. `git subtree` exists on this Git install (I checked that `git-subtree` is in the exec path; the command is part of contrib and may be missing in some builds). First we add the library under `vendor/lib`. `--squash` means the library's whole history is collapsed into one commit instead of coming commit by commit:

```bash
git subtree add --prefix=vendor/lib ../lib main --squash
```

```text
Added dir 'vendor/lib'
```

Then the library got a new version and I brought it in with `pull`; the output shows the file change:

```bash
git subtree pull --prefix=vendor/lib ../lib main --squash -m "pull lib"
```

```text
 vendor/lib/greet.txt | 2 +-
```

(I left out part of the output for brevity.) The files are now ordinary files inside `app`: a plain clone has them and needs no extra command. Then I edited `vendor/lib/greet.txt` in `app`, committed, and ran `split`. This command builds a history that contains only the changes under `vendor/lib` and puts it on a new branch called `lib-only`:

```bash
git subtree split --prefix=vendor/lib -b lib-only
git log --oneline lib-only
```

```text
861c90e app: tweak greet
e229a82 lib: v2
556dcb6 lib: first
```

The top commit is my edit made in `app`, and the two below came from `lib` itself. You could push `lib-only` back to `lib`. The cost of subtree is a busier history and commands that are harder to remember.

## worktree: two branches at once

The third tool solves a different problem: in the middle of work on one branch, you need to go to another. The usual answer is stash or a temporary commit. `git worktree` gives a third way: a second working folder from the same repository, on another branch, next to the first.

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

The first command creates a new branch `hotfix` and checks it out in `../app-hotfix`. `worktree list` shows the two folders with their branches. The third command tried to open the same branch in a third folder, and Git stopped it. Both folders share one object database, so no second clone is needed. The error is a safety rule: one branch, one worktree. Clean up with `git worktree remove ../app-hotfix`. (I replaced my long temp path with `<tmp>`.)

## Which one to pick?

| | submodule | subtree | worktree |
|---|---|---|---|
| What it is | A pinned commit of another repo | Another repo's files, copied in | An extra checkout of the same repo |
| Extra step for collaborators | Yes (`--recurse-submodules`) | No | Not applicable |
| History | Separate | Mixed into yours | The same |
| My take | Good for a few pinned dependencies | When you want zero ceremony | Great for hotfixes and reviews |

The last row is my personal opinion, not a measurement.

## Common traps

- **Always clone with `--recurse-submodules`**, or run `git submodule update --init` afterwards. Otherwise you get an empty folder.
- **Push the submodule first, then the parent.** Otherwise your collaborators get a pointer to a commit that is not on the server.
- **Do not commit inside a submodule on a detached HEAD** unless you create a branch first.
- **Do not copy subtree files by hand**; use `subtree pull` so the history can still be merged.
- **I did not test `git worktree prune` or locked worktrees.**

## Exercise

1. Reproduce the empty-folder clone and fix it with `git submodule update --init`.
2. Commit inside a submodule, advance the pointer, and trigger the "not our ref" error from a second clone.
3. Create a worktree for a hotfix branch, commit there, remove it, and merge the branch.

## What's next

The next post, "Team workflows and packfiles inside", is the last of the series: how teams work with branches and pull requests, and how objects are stored in a packfile.
