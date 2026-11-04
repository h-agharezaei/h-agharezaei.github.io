+++
date = '2026-11-13T10:00:00+03:30'
draft = false
title = 'Hooks and clean commit messages'
description = 'Git hooks in practice: pre-commit, commit-msg and pre-push scripts, sharing them with core.hooksPath, and writing clean commit messages with fixup.'
contentType = 'tutorial'
categories = ["Git"]
series = ["Git"]
tags = ["git", "hooks", "commit-messages", "beginner"]
cover = { image = "/images/covers/git-hooks-commit-hygiene.png", alt = "Hooks and clean commit messages", hiddenInSingle = true }
+++

You leave a `print("here")` in a commit while debugging, and two weeks later someone finds it in the production logs. Or a commit titled "fix stuff" that nobody can later explain. Neither comes from carelessness exactly; people get tired, and good intentions do not last forever.

Hunting a bug with [`git bisect`](/posts/git-bisect/) only works well when history is readable: small commits with messages that say why. The fix is to hand part of that discipline to the machine, and a {{< term "git-hook" "hook" >}} does exactly that. A hook is a script Git runs on an event (for example, right before a commit), and if the script exits non-zero, Git stops the operation. The rest of this post is a few habits for the messages themselves and a way to fix an older commit.

> Everything below ran in a local demo repo with Git 2.39 and Python 3. Outputs are copied from those runs. The hashes belong to that run and will differ on your machine.

## A hook is just a script

The mechanism is simple. Git looks for executable files named after an event (`pre-commit` for "before a commit", for example). If such a file exists, Git runs it; if it exits non-zero, the operation stops. By default these files live in `.git/hooks`, and that folder is not versioned, so it does not travel with the repo.

First, a `pre-commit` hook. When I write temporary code that "must be deleted before commit", I put the marker `TODO-REMOVE` next to it. This hook blocks any commit whose staged changes contain that marker:

```sh
#!/bin/sh
if git diff --cached -U0 | grep -q 'TODO-REMOVE'; then
  echo "pre-commit: found TODO-REMOVE in staged changes" >&2
  exit 1
fi
```

`git diff --cached -U0` prints the staged changes without surrounding lines, `grep -q` only checks whether the marker is in there, and `exit 1` stops the operation. The result:

```text
$ git commit -m "add debug"
pre-commit: found TODO-REMOVE in staged changes
$ echo $?
1
```

Our message was printed and the exit code is 1. The commit did not happen and the change is still staged. After removing the line, the commit went through.

## Share hooks with core.hooksPath

The problem is that `.git/hooks` is not versioned, so your teammates never get these hooks. The way out is to put the hooks in an ordinary folder inside the repo (which gets committed) and tell Git to look there:

```text
$ git config core.hooksPath .githooks
```

Each person runs that once per clone (a setup script or the README can remind them). Now here is a more serious `pre-commit` that compiles staged Python files, so a syntax error cannot get into a commit:

```sh
#!/bin/sh
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
[ -z "$files" ] && exit 0
for f in $files; do
  python3 -m py_compile "$f" || { echo "pre-commit: $f does not compile" >&2; exit 1; }
done
```

The first line collects the names of staged `.py` files (`--diff-filter=ACM` means only added, copied and modified files). If there are none, the hook succeeds silently. Otherwise it tries each file with `py_compile`. I tried to commit a `bad.py` containing `print(`:

```text
  File "bad.py", line 1
    print(
         ^
SyntaxError: '(' was never closed
pre-commit: bad.py does not compile
```

The first lines are Python's own error report and the last line is our hook's message. For Go you would use `gofmt -l` the same way; I only ran the Python version here.

## Enforce message style with commit-msg

Another hook works on the message: `commit-msg`. Before recording a commit, Git writes the message to a temporary file and passes its path to the hook as `$1`. The hook below requires a {{< term "conventional-commits" "Conventional Commits" >}}-style prefix, so the subject must look like `type: summary`, for example `fix: handle empty input`:

```sh
#!/bin/sh
subject=$(head -n 1 "$1")
if ! echo "$subject" | grep -Eq '^((fixup! |squash! )?)(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?: .+'; then
  echo "commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)" >&2
  echo "got: $subject" >&2
  exit 1
fi
```

The first line takes the subject (the first line of the message) and `grep` matches it against the pattern. I tried two messages; the first was rejected and the second accepted:

```text
$ git commit -m "added hooks"
commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)
got: added hooks
$ git commit -m "chore: add shared hooks"
[main 785e41e] chore: add shared hooks
```

Notice the `fixup! |squash! ` part of the pattern. My first version of the regex lacked it and rejected `fixup! feat: add greet`, which broke the workflow in the last section. Hooks can get in your own way too.

## pre-push runs the tests

The third hook runs before `git push`. It is a good place for tests, because it only stops code at the moment it wants to leave your machine:

```sh
#!/bin/sh
python3 -m unittest discover -s tests -q || { echo "pre-push: tests failed, push blocked" >&2; exit 1; }
```

I tried a push with a deliberately wrong test (`assertEqual(1 + 1, 3)`):

```text
AssertionError: 2 != 3
FAILED (failures=1)
pre-push: tests failed, push blocked
error: failed to push some refs to '../remote.git'
```

The first two lines come from the test itself, the third is our hook's message, and the last is Git complaining that the push did not happen. (The remote was just another local repo.) After fixing the test the push succeeded. Keep this hook fast, or people will bypass it.

## Hooks are guard rails, not security

Skipping a hook is easy:

```text
$ git commit --no-verify -m "whatever"
[main d172ea1] whatever
```

`--no-verify` skips `pre-commit` and `commit-msg`, and my commit with a bad message went in. A hook also only exists if the person installed it. So think of hooks as a guard rail on a road, not a wall: they stop accidents, not intent. Anything you truly rely on must run again in {{< term "ci" "CI" >}}. Tools such as Husky or pre-commit manage hook installation for you; I only mention them and did not try them here.

## A good commit message

Now the message itself. A common convention (not a Git rule): a subject line of about 50 characters, a blank line, then a body wrapped near 72 characters explaining why. The diff already says what changed; the message should say why.

```text
feat: add retry

Retry up to 3 times because the upstream
returns 503 during deploys.
```

`git commit -v` shows the staged diff in the editor so you can describe what you really changed. `git config commit.template <file>` pre-fills the editor with the contents of a file. I made a template that contained only comment lines, and `git commit` opened the editor showing exactly those lines. Lines starting with `#` are dropped from the final message.

## Fixing an older commit with fixup

Now suppose you find a typo in an older commit (not the latest one). Stage the fix and run `git commit --fixup` naming the target commit. Git creates a new commit whose message is `fixup! ` plus the target's subject:

```text
$ git commit --fixup 2f84e0a
$ git log --oneline -4
5cc2712 fixup! feat: add greet
7e55bd8 fix: let fixup commits through
e9528aa feat: add bye
2f84e0a feat: add greet
```

The top line is the fix, still sitting apart. A rebase with a {{< term "fixup-commit" "fixup" >}} folds it into the target. The `--autosquash` option moves `fixup!` commits under their targets by itself, and `GIT_SEQUENCE_EDITOR=true` accepts the generated todo list without opening an editor:

```text
$ GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash HEAD~4
Successfully rebased and updated refs/heads/main.
b10a5cf fix: let fixup commits through
82e5be5 feat: add bye
be3de2d feat: add greet
```

(The last three lines are `git log --oneline` after the rebase.) The fixup line is gone and the fix lives inside `feat: add greet`. The index and working tree must be clean first; my first attempt failed with "Your index contains uncommitted changes". Rewriting history is only safe for commits you have not shared.

## Where hooks trip you up

- **Hooks in `.git/hooks` are local.** Use `core.hooksPath` with a tracked directory to share them.
- **Make the script executable (`chmod +x`).** Otherwise Git does not run it; when I tried, Git only printed a hint that the hook was ignored, and the commit went through unchecked.
- **Keep `pre-commit` quick and only check staged files.** People bypass a slow hook with `--no-verify`.
- **Never treat hooks as security.** `--no-verify` exists, so repeat the checks in CI.
- **Do not autosquash commits that are already pushed and shared.** Other people have their history.

## Exercise

In a scratch repo, add a `commit-msg` hook in `.githooks/` that rejects subjects longer than 72 characters, set `core.hooksPath`, and check that a long message is rejected and a short one accepted. Then make two commits, add a fixup for the first, and squash it with autosquash.

## What's next

The next post is "Submodules, subtrees and worktrees", for when your repository needs another repository or you want two branches on disk at once.
