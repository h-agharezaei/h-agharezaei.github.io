+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = "The index and staging: Git's three areas"
description = 'The Git index and staging explained with real runs: working tree, index and HEAD, status codes, diff variants, git add -p, restore, .gitignore and stash.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "staging", "index"]
cover = { image = "/images/covers/git-index-staging.png", alt = "The index and staging: Git's three areas", hiddenInSingle = true }
+++

In the [previous post](/posts/git-how-git-thinks/) we saw that Git stores snapshots as objects named by their hash. This post is about the step before a commit exists, the one that confuses most newcomers: why do you `git add` and then `git commit`? The answer is that Git has three areas, not two.

> Everything below was run with Git 2.39.2 in throwaway repositories, and the outputs are copied from those runs.

## The three areas

1. The {{< term "working-tree" "working tree" >}}: the files on disk you edit.
2. The {{< term "staging-area" "index" >}} (also called the staging area): the snapshot the next commit will contain.
3. {{< term "head" "HEAD" >}}: the last commit.

`git add` copies from the working tree into the index. `git commit` turns the index into a commit. Editing a file never changes the index by itself.

## Reading `git status -s`

The short format has two columns: the first compares index with HEAD, the second compares working tree with index.

```text
?? app.txt          # new file, untracked
A  app.txt          # after git add: staged as a new file
 M app.txt          # after commit and an edit: modified, not staged
MM app.txt          # staged, then edited again
```

`MM` is the one worth remembering: the file differs in both places, with two different versions.

## Three kinds of diff

I staged `line 4` and then added `line 5` without staging it. The same file now has three versions (HEAD, index, disk):

```text
$ git diff            # working tree vs index
+line 5
$ git diff --staged   # index vs HEAD
+line 4
$ git diff HEAD       # working tree vs HEAD
+line 4
+line 5
```

(I trimmed the headers.) Plain `git diff` shows only the unstaged part, which is why it looks empty right after `git add`.

## What the index really holds

```text
$ git ls-files -s
100644 9c2a7090627d0fffa9ed001bf7be98f86c2c8068 0	app.txt
```

Each entry is the file mode, the id of a {{< term "blob" "blob" >}}, a stage number (0 means no merge conflict) and the path. The blob was already written to the object database at `git add` time, and `git cat-file -p 9c2a709...` prints `line 1` to `line 4`, without `line 5`. So adding a file stores its content immediately; the commit only records the index.

## Partial staging with `git add -p`

Git splits a diff into {{< term "hunk" "hunks" >}}. I changed line 2 and line 19 of a 20-line file, which gave two hunks (`@@ -1,5 +1,5 @@` and `@@ -16,5 +16,5 @@`). Answering `y` then `n` stages only the first:

```text
$ printf 'y\nn\n' | git add -p
$ git status -s
MM f.txt
$ git commit -qm "change line 2"
$ git diff | grep '^[+-]line'
-line 19
+line 19 CHANGED
$ git commit -qam "change line 19"
```

Two independent changes became two commits, each with `1 insertion(+), 1 deletion(-)` in `git log --stat`. This is how you keep commits small even when you worked on two things at once.

## Undoing: `restore`

```text
$ git restore --staged f.txt   # index back to HEAD, edits stay on disk
$ git restore f.txt            # disk back to the index
```

I ran both on a file with a staged line and an unstaged line. The first left ` M f.txt`; the second printed nothing, exited 0, and both added lines were gone. Git asked no question. Changes that were never staged or committed exist nowhere else, so `git restore <file>` cannot be undone.

## `.gitignore` and `git rm --cached`

I committed `.env` and `build/out` by mistake, then added a `.gitignore` containing `.env`, `build/` and `*.log`. `.env` still showed ` M` and `git check-ignore -v .env` printed nothing, because ignoring applies only to untracked files. To stop tracking while keeping the file on disk:

```text
$ git rm --cached -q .env
$ git rm -r --cached -q build
$ git status -s
D  .env
D  build/out
?? .gitignore
$ git check-ignore -v .env a.log
.gitignore:1:.env	.env
.gitignore:3:*.log	a.log
```

`check-ignore -v` names the file, line and pattern that matched. Both files were still on disk afterwards. Remember the secret remains in history; if it was real, rotate it.

## Shelving work with `git stash`

```text
$ git stash
Saved working directory and index state WIP on main: 34282f1 stop tracking
$ git status -s
?? scratch.txt
$ git stash pop
```

Plain {{< term "stash" "stash" >}} took the modified `main.go` but left the untracked `scratch.txt` behind. `git stash -u` took both and the tree became clean; `git stash list` showed one entry, and `pop` restored everything.

## A few things to watch

- `git commit -a` skips staging for tracked files only; new files still need `git add`.
- `git add -p` does not offer untracked files; add those normally.
- `git restore` on unstaged edits is permanent. Use `git stash` if you are unsure.
- Adding a path to `.gitignore` never untracks it.
- `git stash pop` can conflict; if so the entry is kept.

## Exercise

1. Create a repo, commit a 10-line file, change line 1 and line 10, and use `git add -p` to make two commits.
2. Reach `MM` on purpose, then look at the three `git diff` variants.
3. Commit a `.log` file, ignore `*.log`, and untrack it with `git rm --cached`.

## What's next

Next: Branches, HEAD and refs: just pointers.
