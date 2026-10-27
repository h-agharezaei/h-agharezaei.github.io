+++
date = '2027-03-27T10:00:00+03:30'
draft = false
title = 'The filesystem and permissions'
description = 'Linux filesystem and permissions with real runs: inodes, hard and symbolic links, chmod, umask, directory bits and setuid, tested on macOS.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "filesystem", "permissions", "chmod", "umask", "inode"]
cover = { image = "/images/covers/linux-filesystem-permissions.png", alt = "The filesystem and permissions", hiddenInSingle = true }
+++

After [the practical shell](/posts/linux-shell-practical/), the next thing every script touches is files, and most "permission denied" surprises come from a few rules. This post goes through them with small runs.

> Honest disclaimer: everything here ran on **macOS** in a throwaway directory (BSD userland, no Linux kernel, no sudo). I did not run anything on Linux. `/proc` and `/sys` (kernel state shown as files) exist only on Linux, so I did not touch them; Linux ACLs (`getfacl`) were not run either. Usernames, ids and home paths are redacted.

## Names, inodes and links

A file's data and metadata live in an {{< term "inode" "inode" >}}; a directory entry is just a name pointing at an inode number.

```sh
echo hello > a.txt; ln a.txt hard.txt; ln -s a.txt soft.txt
ls -li a.txt hard.txt soft.txt
```
```
307806620 -rw-r--r--@ 2 <user>  staff  6 ... a.txt
307806620 -rw-r--r--@ 2 <user>  staff  6 ... hard.txt
307806623 lrwxr-xr-x@ 1 <user>  staff  5 ... soft.txt -> a.txt
```

A {{< term "hard-link" "hard link" >}} shares the inode (same number, link count 2). A {{< term "symbolic-link" "symbolic link" >}} has its own inode and stores the path `a.txt`; `readlink soft.txt` printed `a.txt`. After `rm a.txt` the hard link still printed `hello` with count 1, while `cat soft.txt` failed with `No such file or directory`: the symlink dangles.

On macOS `stat -f '%i %l %Lp %z %N' hard.txt` gave `307806620 1 644 6 hard.txt` (inode, links, mode, size, name). GNU `stat` uses `-c`; I only know that from the man page and did not run it.

## Permission bits

{{< term "file-permissions" "Permissions" >}} are three triplets, r/w/x for user, group and other. Octal adds 4, 2, 1 per triplet.

```sh
chmod 640 f            # -rw-r----- 
chmod u+x,g-r,o+r f    # -rwx---r--
chmod 755 f            # -rwxr-xr-x
```

The comments are the `ls -l` strings I got (the trailing `@` on macOS marks an extended attribute, see below).

## umask

The {{< term "umask" "umask" >}} removes bits from new files and directories.

```sh
(umask 022; mkdir u022; touch u022/file)   # drwxr-xr-x  -rw-r--r--
(umask 077; mkdir u077; touch u077/file)   # drwx------  -rw-------
```

Files start from 666 and directories from 777, minus the mask.

## Directories: r and x are different

On a directory, `r` lets you list names and `x` lets you enter and reach entries by name. With `d/in.txt` inside:

| mode of `d` | `ls d` | `cat d/in.txt` |
|---|---|---|
| 600 (r, no x) | `ls: fts_read: Permission denied`, then `in.txt` | `Permission denied` |
| 300 (w and x, no r) | `ls: d: Permission denied` | prints `x` |
| 500 (r and x, no w) | `touch d/new` fails: `Permission denied` | works |

Creating or deleting a file needs `w` and `x` on the directory, not on the file.

## setuid, setgid and sticky

```sh
chmod 4755 f; chmod 2775 s; chmod 1777 t
```
```
-rwsr-xr-x   f
drwxrwsr-x   s
drwxrwxrwt   t
```

A {{< term "setuid" "setuid" >}} executable runs as its owner, and setgid on a directory makes new files inherit its group. The {{< term "sticky-bit" "sticky bit" >}} `t` on a world-writable directory lets only owners delete their own entries, as `/tmp` does. I only showed the bits in a throwaway directory; I did not demonstrate the setuid effect and changed no system file.

## Ownership

`id` showed `uid=<uid>(<user>) gid=<gid>(<group>) groups=<list>`. As a normal user, `chown root f` failed: `chown: f: Operation not permitted`. Only root can give files away.

## Auditing world-writable files

`find . -type l` listed `./soft.txt`; `find . -perm -002 ! -type l` found world-writable entries; `-perm -4000` finds setuid files. A tiny audit script:

```sh
#!/bin/sh
dir=${1:?usage: audit.sh DIR}
find "$dir" ! -type l -perm -002 -print | while IFS= read -r p; do
  if [ -d "$p" ] && [ -k "$p" ]; then echo "ok(sticky)  $p"
  else echo "WRITABLE    $p"; fi
done
```

On my lab (`hard.txt` set to 666, `t` to 1777) it printed `ok(sticky)  ./t` and `WRITABLE    ./hard.txt`.

## macOS only: xattrs

The `@` in `ls -l` means extended attributes. `xattr` showed `com.apple.provenance` on my files. macOS also has ACLs shown with `ls -le` and a quarantine flag on downloads; I did not explore them. The Linux counterpart is `getfacl`/`setfacl`, which I did not run.

## A few things to watch

- Hard links cannot cross filesystems; symlinks can dangle.
- A directory needs `x` to be entered, `w`+`x` to change.
- `chmod 777` is rarely the fix; find which bit is missing.
- The umask belongs to the process, so a subshell `( umask 077; ... )` keeps it local.
- `stat`, `sed -i` and `find` flags differ between BSD and GNU; check the man page.

## Exercise

Make a directory with a file, then try every mode from 000 to 700 on the directory and note which of `ls`, `cat` and `touch` work. Then write an audit that also lists setuid files.

## What's next

The next post is “Processes and signals”.
