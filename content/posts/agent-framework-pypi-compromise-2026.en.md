+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = "Microsoft's agent-framework Package Compromised on PyPI to Steal Cloud Credentials"
seoTitle = 'Compromised agent-framework on PyPI: What to Do'
description = 'Compromised agent-framework on PyPI (1.26.1 and 1.26.2) stole cloud credentials through a .pth file: who is affected, how it works, what to do.'
contentType = 'analysis'
categories = ["Security"]
tags = ["pypi", "python", "supply-chain", "azure", "ci-cd", "security"]
keywords = ["agent-framework", "Microsoft Agent Framework", "PyPI compromise", "malicious PyPI package", ".pth file", "Python supply chain attack", "Azure credentials theft", "GitHub Actions OIDC"]
cover = { image = "/images/agent-framework-cover.png", alt = "agent-framework PyPI package compromised, malicious versions 1.26.1 and 1.26.2, supply chain attack of November 17, 2026", hiddenInSingle = true }
+++

Imagine you never import a package. You only run `pip` to install something else. And at that moment, without you knowing, a program starts collecting your passwords and tokens.

On 17 November 2026 that was possible with the bad releases of `agent-framework` on {{< term "pypi" "PyPI" >}}. It is the main package of Microsoft Agent Framework, an open-source Python framework for building AI agents. According to [The Hacker News](https://thehackernews.com/2026/11/attackers-compromise-microsofts-agent.html), two versions, 1.26.1 and 1.26.2, were published 33 minutes apart and were later quarantined. The article says the package is downloaded about 190,000 times a month.

This is a {{< term "software-supply-chain" "software supply chain" >}} attack. Nobody touched your code. Someone changed a package you trusted. If you want to know why this kind of attack works so well, read [the supply chain post](/posts/sec-supply-chain-vulns/) first. Here I only talk about this one incident.

Everything below comes from that article. I did not download the bad package and I did not run the malware. The only thing I tried myself is a harmless demo of the Python feature the attack used. I show it in the middle of the post.

## What happened

The article says:

- Versions 1.26.1 and 1.26.2 were bad. It calls 1.26.0 "the most recent safe version". It names no fixed release and only says to go back to 1.26.0.
- The risk was for anyone who installed those versions between 8:35 and about 9:20 p.m. UTC on 17 November.
- There is no CVE and no CVSS score. There was no bug in the framework's code. The package itself was compromised.
- The attacker is unknown. The article mentions the group TeamPCP only because of an earlier compromise of another Microsoft package, `durabletask`, in May 2026. It does not blame them for this one.
- It is still unclear how the attacker got permission to publish. OX Security guesses that they tampered with the step that builds the wheel instead of creating a new package.

## Why it ran without being imported

Both bad versions put one extra file next to the others in `site-packages`: a {{< term "pth-file" ".pth file" >}}. In 1.26.1 it was called `agent_framework_meta.pth`. In 1.26.2 it was `af_runtime_diag.pth`, together with a new module, `af_runtime_diag.py`. These files were inside the {{< term "wheel" "wheel" >}}, the file that `pip` downloads and installs.

A `.pth` file is made for something harmless: it tells Python which extra folders to search for imports. But it has one rule. The [Python documentation](https://docs.python.org/3/library/site.html) says that any line in it that starts with `import` is executed. That was the whole attack: one line, like `import agent_framework_meta`, and the bad code ran every time Python started. Endor Labs, quoted in the article, says it ran on every Python launch, "including pip itself, whether or not anything imports Agent Framework."

To see this for myself, I made a throwaway virtual environment and put a harmless `.pth` file in it that only prints one line. Then I started Python in a few ways. I replaced the paths with `<tmp>`.

```text
$ cat <tmp>/venv/lib/python3.14/site-packages/demo_hook.pth
import sys; print("[demo.pth] ran at startup, argv =", sys.argv)

$ venv/bin/python -c "print(1+1)"
[demo.pth] ran at startup, argv = ['-c']
[demo.pth] ran at startup, argv = ['-c']
2

$ venv/bin/python -S -c "print(1+1)"
2

$ venv/bin/python -I -c "print(1+1)"
[demo.pth] ran at startup, argv = ['-c']
[demo.pth] ran at startup, argv = ['-c']
2

$ venv/bin/pip --version
[demo.pth] ran at startup, argv = ['venv/bin/pip', '--version']
[demo.pth] ran at startup, argv = ['venv/bin/pip', '--version']
pip 25.2 from <tmp>/venv/lib/python3.14/site-packages/pip (python 3.14)
```

Read the output like this. The `[demo.pth]` line prints before the `2`, so the hook runs before the program's own code. It also runs for `pip --version`, which imports nothing of mine. `pip` is itself a Python program, so once a bad package is installed, the next `pip` run triggers the hook. Isolated mode (`python -I`) does not stop it. Only `python -S`, which skips the `site` module completely, does.

In my run the hook printed twice each time. I did not find out why and did not look into it. It does not change the point, but I do not want to pretend I know the reason. The test used Python 3.14.0 on macOS and did not include any of the real malware.

## What the malware collected

According to the article, the malware did two things. First, it read what was already on the machine. Second, it asked the cloud platform for new things.

What it read:

- environment variables whose names look like credentials (version 1.26.2 widened the search pattern)
- Azure CLI files and the config files `.npmrc`, `pip.conf`, `.netrc`, `.git-credentials` and `.docker/config.json`
- Hugging Face and Azure DevOps agent credentials, plus `.env` and JSON files

What it asked for:

- In Azure DevOps it used `SYSTEM_ACCESSTOKEN` and `SYSTEM_OIDCREQUESTURI` to get an identity token for `api://AzureADTokenExchange`. Version 1.26.2 also collected GitHub Actions {{< term "oidc" "OIDC" >}} tokens.
- On Azure machines it asked the {{< term "managed-identity" "managed identity" >}} for tokens. On App Service and Functions it used `IDENTITY_ENDPOINT` or `MSI_ENDPOINT`, and elsewhere the address `169.254.169.254`. It also read the {{< term "imds" "machine metadata" >}} and kept the first 8,000 characters of the answer.

All of it was put in one JSON, compressed, and sent over HTTPS to a fixed address on `webhook.site`.

The second group is the more dangerous one. SafeDep sums it up well: the malware does not only read existing credentials, it asks the platform to issue new ones. The result is that if you only change the secrets you had stored, the tokens created during the attack are still in the attacker's hands.

## Am I affected, and what to do

If your machine or CI runner installed `agent-framework` 1.26.1 or 1.26.2 in that time window, you were exposed. Here is the article's advice, in the order I would follow it:

1. **Find out first.** Look for those two versions in your lock files, `pip freeze` output and build logs, around 8:35 to 9:20 p.m. UTC on 17 November. If a machine installed `agent-framework` without a fixed version in that window, assume it is affected.
2. **Isolate and rebuild.** Cut the affected machines and runners off the network. Do not clean the old environment. Rebuild from a clean one and keep the version at 1.26.0.
3. **Check whether anything left.** In your proxy and DNS logs, look for requests to this address: `webhook[.]site/d381fd80-ec62-42ad-8f5c-d1b15103c9bb`. I put brackets around the dot on purpose so nobody clicks it. Remove the brackets when you search the logs.
4. **Change the credentials.** Rotate every credential that machine could see, and do it from a clean machine.
5. **Check Azure.** Look at the identities, sign-in logs and activity logs. Remember that new tokens may have been issued, not only copied.
6. **Check your deploy pipelines.** Look at GitHub Actions workflows that deploy to Azure. A job's OIDC token can be as powerful as a stored secret.

## What this teaches

- **Pin your versions.** According to the article the bad versions were live for under an hour. If your build picks "the latest version" in that exact minute, it gets them. A {{< term "lockfile" "lock file" >}} with hashes means "exactly what I checked", not "whatever is newest". The [packaging post](/posts/py-packaging-publishing/) and the [uv post](/posts/py-environment-uv-venv/) show how.
- **Installing is running code.** The danger was not the framework itself. It was a file installed next to it. A wheel can place a file that runs every time Python starts, so "but I never imported it" is not a defence.
- **Short-lived tokens are not enough if the job can ask for them.** Managed identity and OIDC remove fixed passwords, which is good. But any code running inside the job can ask for the same tokens. So CI jobs should only have the permissions they really need. The [secrets management post](/posts/sec-secrets-management/) is about exactly this.
- **Do not install unknown things where cloud access exists.** If you can, build in an environment that has no cloud credentials, and give only the deploy step the access it needs.

## What we do not know

All of the information above comes from The Hacker News article. I have not read the separate reports from the companies it links to, such as Wiz, OX Security, Endor Labs and Socket. I have not seen the malware or run it. What I tried myself is only the harmless `.pth` demo, which shows that these files run when Python starts. It proves nothing about what the real malware did.

A few things are also still unknown: who the attacker is, how they got permission to publish, and whether 1.26.0 will stay the right version to pin. The article was published on 18 November, so details may change.

## References

- [The Hacker News: Attackers Compromise Microsoft's Agent Framework PyPI Package to Steal Cloud Credentials](https://thehackernews.com/2026/11/attackers-compromise-microsofts-agent.html)
- [Python documentation: the site module and .pth files](https://docs.python.org/3/library/site.html)
