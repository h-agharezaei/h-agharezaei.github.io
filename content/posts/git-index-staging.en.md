+++
date = '2026-10-30T10:00:00+03:30'
draft = false
title = "The index and staging: Git's three areas"
description = 'The Git index and staging explained with real runs: working tree, index and HEAD, status codes, diff variants, git add -p, restore, .gitignore and stash.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "beginner", "staging", "index"]
cover = { image = "/images/covers/git-index-staging.png", alt = "The index and staging: Git's three areas", hiddenInSingle = true }
+++

You edit a file and run `git add`. Then you remember one more line to change and edit the file again. Now `git status -s` shows `MM` next to the file, and `git diff` shows only that last line, as if the first change had never happened. Or a simpler case: right after `git add`, `git diff` prints nothing, and you think your change got lost.

All of these come from one question that newcomers always ask: why `git add` first and then `git commit`? The answer is that Git does not have two places for your files, it has three. Underneath them are the objects named by their content hash that the [previous post](/posts/git-how-git-thinks/) showed. In this post we look at the three places one by one, and then at what they make possible: staging part of a file, undoing a change, `.gitignore` and `git stash`.

> Everything below was run with Git 2.39.2 in throwaway repositories, and the outputs are copied from those runs. Commit hashes differ on every run because they depend on name and time; when you see a commit hash in an output, only its shape matters.

## The three areas

The main idea: between the files you edit on disk and a commit, Git has a middle step. The three places are:

1. The **{{< term "working-tree" "working tree" >}}**: the files on disk, the ones you open in your editor.
2. The **{{< term "staging-area" "index" >}}** (also called the staging area): the snapshot the next commit will contain.
3. **{{< term "head" "HEAD" >}}**: the last commit, the last recorded snapshot.

A simple analogy: you are taking a group photo. The working tree is the real scene, which keeps changing. The index is where you arrange people into place. The commit is the moment you press the shutter. Until the arrangement is done, not everything on the scene has to end up in the photo.

Three commands move things between these places. `git add` takes a file's content from the working tree into the index. `git commit` builds a commit from the index. And editing a file never changes the index by itself; you have to `git add` again.

## Reading `git status -s`

Now that we have three places, we can understand what the short output of `git status -s` says. Each line has two columns. The first column compares the **index with HEAD** (what is staged). The second compares the **working tree with the index** (what is not staged yet). Here are the states of one file in order:

```text
?? app.txt          # new file, untracked
A  app.txt          # after git add: staged as a new file
 M app.txt          # after commit and an edit: modified, not staged
MM app.txt          # staged, then edited again
```

- `??` means Git does not know the file (untracked).
- `A ` (a space in the second column) means the new file is staged and unchanged since.
- ` M` (a space in the first column) means the file was committed, then edited, and the edit is not staged.
- `MM` means both: part of the change is staged, and the file was edited again after that.

Remember `MM`: the file differs in both places, so two different versions of it exist at the same time.

## Three kinds of diff

How do we see these two versions? Depending on its arguments, `git diff` compares different pairs of the three places. To try it, I committed a file with three lines, added `line 4` and staged it, then added `line 5` without staging. Now the file has three versions: in HEAD (three lines), in the index (four lines) and on disk (five lines). I ran all three diff commands:

```text
$ git diff            # working tree vs index
+line 5
$ git diff --staged   # index vs HEAD
+line 4
$ git diff HEAD       # working tree vs HEAD
+line 4
+line 5
```

(I removed the diff headers and line numbers so only the changed lines remain.) In order:

- Plain `git diff` compares disk with the index, so it shows only `line 5`: what is not staged yet.
- `git diff --staged` compares the index with HEAD, that is what would go in if you committed right now: `line 4`.
- `git diff HEAD` compares disk directly with the last commit and sees both changes.

That is why plain `git diff` is empty right after `git add`: all the changes are in the index too, and nothing differs between disk and index.

## What the index really holds

We said the index is a "photo". What exactly is written in it? `git ls-files -s` lists it. This output is for the same example file, when `line 4` was staged:

```text
$ git ls-files -s
100644 9c2a7090627d0fffa9ed001bf7be98f86c2c8068 0	app.txt
```

Each entry has four things: the file mode (`100644` is a normal file), the id of a **{{< term "blob" "blob" >}}**, the stage number (zero means no conflict) and the path. The blob is the object from the previous post: the file's content, named by its hash. It was written to the object database at the moment of `git add`. If we run `git cat-file -p 9c2a709…`, it prints `line 1` to `line 4`, without `line 5`.

So `git add` stores the file's content right away, and commit only turns the list in the index into a tree and a commit. That is why, if you change a file after `add`, the commit records the earlier version.

## Staging part of a file with `git add -p`

This separation of index and disk has one very useful application: you can put only some of a file's changes into a commit. Git splits a diff into pieces called **{{< term "hunk" "hunks" >}}**, and `git add -p` asks for each one whether to stage it.

To try it, I committed a 20-line file and changed line 2 and line 19. Because the two changes are far apart, Git makes two hunks (`@@ -1,5 +1,5 @@` and `@@ -16,5 +16,5 @@`). We answer `y` (yes) to the first hunk and `n` (no) to the second, and then commit:

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

After `add -p` the file is `MM`: the change to line 2 is in the index and the change to line 19 is only on disk. After the first commit, `git diff` shows only the change to line 19, which means what we did not stage was still on disk. The second commit records that too (`-a` means all tracked files, `-q` means quiet).

The result: two independent changes, two commits. In `git log --stat` each has `1 insertion(+), 1 deletion(-)`. This is how commits stay small and about one thing each, even when you edited two things at once.

## Undoing: `restore`

Now the reverse: how do you take back a change you do not want? `git restore` has two forms:

```text
$ git restore --staged f.txt   # index back to HEAD, edits stay on disk
$ git restore f.txt            # disk back to the index
```

I ran both, in this order, on a file with one staged line and one unstaged line. The first (`--staged`) only returns the index to HEAD. The file became ` M` and both lines were still on disk, so nothing of your work was lost, it just came out of staging. The second printed nothing, exited with code 0, and returned the disk to the index. Because the index equalled HEAD at that point, both extra lines disappeared.

Look at the second one: Git asked no question. A change that is neither staged nor committed exists nowhere else. So `git restore <file>` cannot be undone.

## `.gitignore` and `git rm --cached`

A common mistake: you commit a file that should never have gone into the repository, and then you want to ignore it. In a test repository I deliberately committed `.env` and `build/out`, edited `.env` a little, and then created a {{< term "gitignore" ".gitignore" >}} with three lines: `.env`, `build/` and `*.log`.

I expected `.env` to disappear from view, but it still showed ` M .env`. And `git check-ignore -v .env` printed nothing. The reason is that ignore rules only affect untracked files, files Git does not know yet. A file that was committed once is tracked, and ignoring has no effect on it.

To make Git stop following a file but keep it on disk, we use `--cached`, meaning only remove it from the index:

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

`D ` in the first column means "removed from the index" (in the next commit the file leaves the repository), and `.gitignore` is still untracked. Now `git check-ignore -v` shows, for each ignored file, the rule file, the line number and the matching pattern: line 1 for `.env`, and the `*.log` pattern on line 3 for `a.log`. `a.log` was untracked from the start, so the `*.log` rule applied to it from the beginning. After these commands both `.env` and `build/out` were still on disk.

One warning: this removes the file from future commits, not from history. If `.env` held a real secret, it is still in the old commits; change that secret.

## Setting work aside with `git stash`

Sometimes you must switch to something else in the middle of your work and do not want to commit half-finished changes. `git stash` sets tracked changes aside and cleans the working tree, and `git stash pop` brings them back. In the same repository I edited `main.go` and created a new file `scratch.txt`:

```text
$ git stash
Saved working directory and index state WIP on main: 34282f1 stop tracking
$ git status -s
?? scratch.txt
$ git stash pop
```

A plain {{< term "stash" "stash" >}} took the edited `main.go` but left `scratch.txt` behind because it was untracked. The `-u` option includes untracked files: with `git stash -u` both were taken and the tree became clean, `git stash list` showed one entry, and `pop` restored everything. (The commit id in the message differs on every run.)

## Staging surprises

- **`git commit -a` works only for tracked files.** It skips the staging step only for files Git already knows; a new file still needs `git add`.
- **`git add -p` does not offer untracked files.** `add` them normally.
- **`git restore` on unstaged changes is permanent.** If you are not sure, run `git stash` first.
- **Adding a path to `.gitignore` does not untrack it.** For files that are already tracked you need `git rm --cached`.
- **`git stash pop` can conflict.** According to the Git docs, the stash entry is then kept so your work is not lost.

## Exercise

1. Create a repo, commit a 10-line file, change line 1 and line 10, and make two commits with `git add -p`.
2. Get to `MM` on purpose and look at the three kinds of `git diff`. Before running each, guess what it will show.
3. Commit a `.log` file, ignore `*.log`, and untrack it with `git rm --cached`.

## What's next

Next is "Branches, HEAD and refs: just pointers". So far we have seen HEAD only as "the last commit"; there we see what these names really are for Git.
