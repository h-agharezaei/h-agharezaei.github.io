+++
title = "argparse"
summary = "The standard-library module that parses command-line arguments, generates --help and exits with code 2 on bad usage."
category = "Python"
related = ["exit-status"]
posts = ["py-cli-scripts"]
+++

`argparse` turns `sys.argv` into typed values. It supports subcommands, choices and mutually exclusive groups, builds the `--help` text for you, and on a usage error prints a message to stderr and exits with status 2.
