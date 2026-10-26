+++
date = '2026-11-13T10:00:00+03:30'
draft = false
title = 'Hooks and clean commit messages'
description = 'Git hooks in practice: pre-commit, commit-msg and pre-push scripts, sharing them with core.hooksPath, and writing clean commit messages with fixup.'
categories = ["Git"]
series = ["Git"]
tags = ["git", "hooks", "commit-messages", "beginner"]
cover = { image = "/images/covers/git-hooks-commit-hygiene.png", alt = "Hooks and clean commit messages", hiddenInSingle = true }
+++

In the [previous post](/posts/git-bisect/) we hunted a bug through history with `git bisect`. That only works well when history is readable: small commits with messages that say why. This post is about keeping it that way automatically with {{< term "git-hook" "hooks" >}}, plus a few habits for the messages themselves.

> Everything below ran in a local demo repo with Git 2.39 and Python 3. Outputs are copied from those runs.

## A hook is just a script

Git looks for executable files named after an event. If the script exits non-zero, Git stops. By default they live in `.git/hooks`, which is not versioned. A `pre-commit` hook that blocks a marker I use for "must delete before commit":

```sh
#!/bin/sh
if git diff --cached -U0 | grep -q 'TODO-REMOVE'; then
  echo "pre-commit: found TODO-REMOVE in staged changes" >&2
  exit 1
fi
```

```text
$ git commit -m "add debug"
pre-commit: found TODO-REMOVE in staged changes
$ echo $?
1
```

The commit did not happen and the change is still staged. After removing the line, the commit went through.

## Share hooks with core.hooksPath

Since `.git/hooks` is not versioned, teammates would never get your hooks. Put them in a tracked directory and point Git at it:

```text
$ git config core.hooksPath .githooks
```

Each person runs that once per clone (a setup script or the README can say so). Now `pre-commit` compiles staged Python files:

```sh
#!/bin/sh
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
[ -z "$files" ] && exit 0
for f in $files; do
  python3 -m py_compile "$f" || { echo "pre-commit: $f does not compile" >&2; exit 1; }
done
```

```text
  File "bad.py", line 1
    print(
         ^
SyntaxError: '(' was never closed
pre-commit: bad.py does not compile
```

For Go you would use `gofmt -l` the same way; I only ran the Python version here.

## Enforce message style with commit-msg

Git passes the path of the message file as `$1`. This hook requires a {{< term "conventional-commits" "Conventional Commits" >}}-style prefix:

```sh
#!/bin/sh
subject=$(head -n 1 "$1")
if ! echo "$subject" | grep -Eq '^((fixup! |squash! )?)(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?: .+'; then
  echo "commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)" >&2
  echo "got: $subject" >&2
  exit 1
fi
```

```text
$ git commit -m "added hooks"
commit-msg: subject must look like 'type: summary' (feat, fix, docs, refactor, test, chore)
got: added hooks
$ git commit -m "chore: add shared hooks"
[main 785e41e] chore: add shared hooks
```

Notice the `fixup! |squash! ` part. My first version of the regex lacked it and rejected `fixup! feat: add greet`, which broke the workflow in the last section. Hooks can get in your own way too.

## pre-push runs the tests

```sh
#!/bin/sh
python3 -m unittest discover -s tests -q || { echo "pre-push: tests failed, push blocked" >&2; exit 1; }
```

With a deliberately wrong test (`assertEqual(1 + 1, 3)`):

```text
AssertionError: 2 != 3
FAILED (failures=1)
pre-push: tests failed, push blocked
error: failed to push some refs to '../remote.git'
```

After fixing the test the push succeeded. Keep this hook fast, or people will bypass it.

## Hooks are guard rails, not security

```text
$ git commit --no-verify -m "whatever"
[main d172ea1] whatever
```

`--no-verify` skips `pre-commit` and `commit-msg`, and my commit with a bad message went in. A hook also only exists if the person installed it. Anything you truly rely on must run again in {{< term "ci" "CI" >}}. Tools such as Husky or pre-commit manage hook installation for you; I only mention them and did not try them here.

## A good commit message

A common convention (not a Git rule): a subject line of about 50 characters, a blank line, then a body wrapped near 72 characters explaining why.

```text
feat: add retry

Retry up to 3 times because the upstream
returns 503 during deploys.
```

`git commit -v` shows the staged diff in the editor so you can describe what you really changed. `git config commit.template <file>` pre-fills the editor; with a template of comment lines, `git commit` opened the editor showing exactly those lines, and lines starting with `#` are dropped from the final message.

## Fixing a commit with fixup

Found a typo in an older commit? Stage the fix and name the target:

```text
$ git commit --fixup 2f84e0a
$ git log --oneline -4
5cc2712 fixup! feat: add greet
7e55bd8 fix: let fixup commits through
e9528aa feat: add bye
2f84e0a feat: add greet
```

Then a {{< term "fixup-commit" "fixup" >}} rebase folds it in. `GIT_SEQUENCE_EDITOR=true` accepts the generated todo list without opening an editor:

```text
$ GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash HEAD~4
Successfully rebased and updated refs/heads/main.
b10a5cf fix: let fixup commits through
82e5be5 feat: add bye
be3de2d feat: add greet
```

The fixup line is gone and the fix lives inside `feat: add greet`. The tree must be clean first; my first attempt failed with "Your index contains uncommitted changes". Rewriting history is only safe for commits you have not shared.

## A few things to watch

- Hooks in `.git/hooks` are local; use `core.hooksPath` with a tracked directory to share them.
- Make the script executable (`chmod +x`), otherwise Git ignores it.
- Keep `pre-commit` quick and only check staged files.
- Never treat hooks as security: `--no-verify` exists, so repeat checks in CI.
- Do not autosquash commits that are already pushed and shared.

## Exercise

In a scratch repo, add a `commit-msg` hook in `.githooks/` that rejects subjects longer than 72 characters, set `core.hooksPath`, and check that a long message is rejected and a short one accepted. Then make two commits, add a fixup for the first, and squash it with autosquash.

## What's next

The next post is "Submodules, subtrees and worktrees".
