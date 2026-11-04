+++
date = '2027-03-27T10:00:00+03:30'
draft = false
title = 'The filesystem and permissions'
description = 'Linux filesystem and permissions with real runs: inodes, hard and symbolic links, chmod, umask, directory bits and setuid, tested on macOS.'
contentType = 'tutorial'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "filesystem", "permissions", "chmod", "umask", "inode"]
cover = { image = "/images/covers/linux-filesystem-permissions.png", alt = "The filesystem and permissions", hiddenInSingle = true }
+++

Picture this. A file clearly exists: you can see it in the listing, and `ls -l` shows that your user is allowed to read it. Yet `cat` answers `Permission denied`. Or the other way round: you can read a file perfectly well, but you cannot delete it, even though the file is set to be writable by everybody. Both situations look like contradictions until you learn where the check really happens. Most "permission denied" surprises come from a few rules: a directory needs `x` to be entered, and creating or deleting a file needs `w` and `x` on the *directory*, not on the file.

[The practical shell](/posts/linux-shell-practical/) was about commands and what flows between them. Every script also touches files, so in this post we go through these rules in small runs: what a file name really is, what the permission letters mean, why files and directories read them differently, and the three special bits that surprise people.

> Honest disclaimer: everything here ran on **macOS** in a throwaway directory (BSD userland, no Linux kernel, no sudo). I did not run anything on Linux. `/proc` and `/sys` (kernel state shown as files) exist only on Linux, so I did not touch them, and Linux ACLs (`getfacl`) were not run either. User names, ids and home paths are redacted, and where I show output I cut the date column.

## Names, inodes and links

Before permissions, one idea about what a "file" is. The data of a file and its details (size, owner, permission bits, times) are stored together in a structure called an {{< term "inode" "inode" >}}, which has a number. A name like `report.txt` is *not* part of the file. It is just an entry in a directory that says "this name points to inode number N". Once you see that, links become easy to understand.

```sh
echo hello > a.txt; ln a.txt hard.txt; ln -s a.txt soft.txt
ls -li a.txt hard.txt soft.txt
```

The first command creates a file and then two more names for it: `ln` makes a hard link and `ln -s` makes a symbolic link. `ls -li` adds the inode number as the first column:

```
318683082 -rw-r--r--@ 2 <user>  wheel  6 ... a.txt
318683082 -rw-r--r--@ 2 <user>  wheel  6 ... hard.txt
318683085 lrwxr-xr-x@ 1 <user>  wheel  5 ... soft.txt -> a.txt
```

A {{< term "hard-link" "hard link" >}} is a second name for the same inode. `a.txt` and `hard.txt` show the same inode number and a link count of 2 (the number after the permission string). A {{< term "symbolic-link" "symbolic link" >}} is different: it is a small file of its own, with its own inode, that stores a *path*. `soft.txt` has a different inode and a size of 5, which is the length of the text `a.txt`; `readlink soft.txt` printed that text.

The difference shows up when the original name disappears. After `rm a.txt`, `cat hard.txt` still printed `hello` and the link count dropped to 1, because the data lives as long as some name points at the inode. `cat soft.txt` failed with `No such file or directory`: the symbolic link now points at a path that no longer exists, and we call it dangling. (`find . -type l` still lists `./soft.txt`.)

To look at inode details on macOS I used `stat -f '%i %l %Lp %z %N' hard.txt`, which printed `318683082 2 644 6 hard.txt`: inode, link count, mode, size and name. GNU `stat` uses `-c` instead of `-f` for formats; I know that only from the man page and did not run it. (Inode numbers vary from run to run.)

## Permission bits

Now to the permissions themselves. Every file has an owner and a group, and {{< term "file-permissions" "permissions" >}} come in three triplets: what the *owner* (user) may do, what the *group* may do, and what everyone *else* (other) may do. Each triplet has three letters: `r` (read), `w` (write) and `x` (execute). You write them as nine characters in `ls -l`, like `rw-r-----`. In the numeric (octal) form each triplet becomes one digit, adding 4 for `r`, 2 for `w` and 1 for `x`. So `rw-` is 4+2 = 6, `r--` is 4 and `---` is 0: `640` means "owner reads and writes, group reads, others nothing".

```sh
chmod 640 f            # -rw-r----- 
chmod u+x,g-r,o+r f    # -rwx---r--
chmod 755 f            # -rwxr-xr-x
```

The first command sets all nine bits at once with octal. The second is *symbolic*: it adds `x` for the user (`u+x`), removes `r` from the group (`g-r`) and adds `r` for others (`o+r`), changing only what you name. The comments are the `ls -l` strings I got after each command. (On macOS the trailing `@` marks an extended attribute, more on that at the end.)

## umask

When a program creates a file, it asks for some permission bits, but the process has a {{< term "umask" "umask" >}} that takes bits away from them. Files start from 666 (no execute by default, so a new file is never executable by accident) and directories from 777, and the umask is subtracted.

```sh
(umask 022; mkdir u022; touch u022/file)   # drwxr-xr-x  -rw-r--r--
(umask 077; mkdir u077; touch u077/file)   # drwx------  -rw-------
```

With `022` the group and others lose `w`, so you get the familiar 755 and 644. With `077` they lose everything. The parentheses start a subshell, and the umask belongs to the process, so it changes back when the subshell ends. The comments show the `ls -l` strings from my run.

## Directories: r and x are different

Here is the part that explains the opening puzzle. On a file, `r` means "read the content". On a directory, the letters mean something else: `r` lets you *list the names* inside, and `x` lets you *enter* the directory and reach entries by name. They are independent, and you can have one without the other. Let me test with a directory `d` that contains `in.txt`, whose content is `x`:

| mode of `d` | `ls d` | `cat d/in.txt` |
|---|---|---|
| 600 (r, no x) | `ls: fts_read: Permission denied`, then `in.txt` | `Permission denied` |
| 300 (w and x, no r) | `ls: d: Permission denied` | prints `x` |
| 500 (r and x, no w) | `touch d/new` fails: `Permission denied` | works |

Read the rows one by one:

- With `r` but no `x`, `ls` can read the names (it printed `in.txt`) but cannot look inside the entries, so it complains. Reading the file by its path fails, because getting to `d/in.txt` needs `x` on `d`.
- With `x` but no `r`, you cannot list the directory, yet `cat d/in.txt` works if you already know the name. It is like a building where you cannot see the directory board but can open a door whose number you know.
- With `r` and `x` but no `w`, you can look and read, but you cannot *change the directory*: `touch d/new` fails.

The last row leads to the rule I gave at the start. Creating, deleting or renaming a name is a change to the *directory*, so it needs `w` and `x` on the directory. It does not matter what the permissions of the file itself are. That is why a world-writable file can still be impossible to delete: you need `w` on the directory it lives in. The same rule explains the first puzzle: to read `/srv/app/config/app.conf`, you need `x` on `/srv`, on `/srv/app` and on `/srv/app/config`, and `r` on the file. One directory in the middle without `x` for you is enough to get `Permission denied` on a readable file. (The `ls` message text comes from BSD `ls`; GNU `ls` words its errors differently, and I did not run it.)

## setuid, setgid and sticky

Besides the nine bits there are three special bits, shown in octal as a fourth leading digit: 4 for setuid, 2 for setgid, 1 for sticky.

```sh
chmod 4755 f; chmod 2775 s; chmod 1777 t
```
```
-rwsr-xr-x   f
drwxrwsr-x   s
drwxrwxrwt   t
```

Each one replaces an `x` in the listing with a letter: `s` in the owner triplet (setuid), `s` in the group triplet (setgid), `t` in the other triplet (sticky). What they do, according to the documentation:

- A {{< term "setuid" "setuid" >}} executable runs with the user id of its *owner*, not of whoever started it. This is how a tool like `passwd` can edit a protected file. It is also why a setuid file owned by root is something to audit.
- Setgid on a directory makes new files inside it inherit the directory's group. (On an executable it works like setuid, with the group.)
- The {{< term "sticky-bit" "sticky bit" >}} `t` on a world-writable directory lets only a file's owner (or the directory's owner) delete or rename entries there. That is how `/tmp` can be writable by everyone without letting users delete each other's files.

I only showed the bits on a throwaway directory. I did not demonstrate the setuid effect, and I changed no system file. One thing I did see: `chmod 2775` on a directory whose group was `wheel` printed `drwxrwxr-x` with no `s`. My user is not in that group, and as far as I know the rule is that an unprivileged user cannot set setgid on a file whose group is not one of theirs, so the bit is silently dropped. After `chgrp` to my own group the same `chmod` showed `drwxrwsr-x`. The Linux `chmod(2)` man page describes a similar rule, but I did not run it on Linux.

## Ownership

`id` shows who you are: `uid=<uid>(<user>) gid=<gid>(<group>) groups=<list>`. Ownership checks use these numbers. As a normal user I tried `chown root f` and got `chown: f: Operation not permitted`. Only root can give a file away to someone else.

## Auditing world-writable files

A world-writable file means any user on the machine can change it, so it is worth searching for. `find . -type l` listed `./soft.txt`. `find . -perm -002 ! -type l` finds entries writable by others (`-perm -002` means "has at least these bits"; links are excluded because a link's own bits mean nothing), and `find . -perm -4000` finds setuid files. In my lab `find . -perm -4000 ! -type d` found `./f`. Here is a tiny audit script that combines this with the sticky check:

```sh
#!/bin/sh
dir=${1:?usage: audit.sh DIR}
find "$dir" ! -type l -perm -002 -print | while IFS= read -r p; do
  if [ -d "$p" ] && [ -k "$p" ]; then echo "ok(sticky)  $p"
  else echo "WRITABLE    $p"; fi
done
```

For every world-writable entry it prints `ok(sticky)` if it is a directory with the sticky bit (like `/tmp`) and `WRITABLE` otherwise. `${1:?...}` stops the script with a usage message if you forget the directory. On my lab, with `hard.txt` set to 666 and `t` set to 1777, it printed `ok(sticky)  lab/t` and `WRITABLE    lab/hard.txt`.

## macOS only: xattrs

The `@` at the end of the permission string in `ls -l` means extended attributes. `xattr` showed `com.apple.provenance` on my files. macOS also has ACLs (shown with `ls -le`) and a quarantine flag on downloaded files; I did not explore them. The Linux counterpart of ACLs is `getfacl` and `setfacl`, which I did not run.

## Permission mistakes

- Hard links cannot cross filesystems, because an inode number only means something inside one filesystem. Symlinks can cross, but they can dangle.
- A directory needs `x` to be entered, and `w` plus `x` to change what is in it. Every directory on the path counts, not only the last one.
- `chmod 777` is rarely the fix. Find which bit is actually missing, usually an `x` on a directory in the path.
- The umask belongs to the process, so a subshell `( umask 077; ... )` keeps the change local instead of surprising the rest of the script.
- `stat`, `sed -i` and `find` flags differ between BSD and GNU, as we saw in the last post; check the man page of the machine you deploy to.

## Exercise

Make a directory with a file in it, then try every mode from 000 to 700 on the directory and note which of `ls`, `cat` and `touch` work. Then extend the audit script so that it also lists setuid files.

## What's next

Next: “Processes and signals”, because a script that is killed in the middle of a run can leave its temp files behind, and that is a question about processes, not files.
