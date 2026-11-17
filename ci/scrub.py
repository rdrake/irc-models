#!/usr/bin/env python3
"""Refuse files that must not be published.

  ci/scrub.py [FILE ...]        (no files: every file git tracks)
  ci/scrub.py --staged          the index's copy of every staged file (pre-commit)
  ci/scrub.py --message FILE    a commit message (commit-msg hook)
  ci/scrub.py --log [RANGE]     every commit message in RANGE (default: all)

Two kinds of rule:
- built in, below: personal absolute paths, assistant attribution and
  session links;
- a deny list kept outside this repository, one entry per line (a literal,
  or `re:` and a regular expression; `#` starts a comment). It is read from
  the file named by SCRUB_DENYLIST, or from the text of the environment
  variable SCRUB_DENYLIST_TEXT (how CI passes it, from a repository secret).
  It names hosts, paths and findings that are not public yet, so it can
  never live here.

Exit status 1 if any line matches, with file:line and the rule for each.
Install the hooks with:
  ln -s ../../ci/pre-commit .git/hooks/pre-commit
  ln -s ../../ci/commit-msg .git/hooks/commit-msg
"""
import os, re, subprocess, sys

BUILTIN = [
    (r"/Users/[A-Za-z0-9._-]+/", "a personal home path"),
    (r"/home/(?!user/)[A-Za-z0-9._-]+/", "a personal home path"),
    (r"/private/tmp/", "a local temporary path"),
    (r"claude\.ai/", "a session or artifact link"),
    (r"(?i)co-authored-by:", "an attribution trailer"),
    (r"(?i)claude-session:", "an attribution trailer"),
    (r"(?i)generated with \[?claude", "an attribution line"),
]
SKIP_SUFFIXES = (".png", ".jpg", ".gif", ".jar", ".sif")


def deny_list():
    text = ""
    if os.environ.get("SCRUB_DENYLIST"):
        text = open(os.environ["SCRUB_DENYLIST"]).read()
    elif os.environ.get("SCRUB_DENYLIST_TEXT"):
        text = os.environ["SCRUB_DENYLIST_TEXT"]
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("re:"):
            rules.append((line[3:], "deny list"))
        else:
            rules.append(("(?i)" + re.escape(line), "deny list"))
    return rules


def sources(argv):
    """Yield (label, text) for what argv asks to scan."""
    me = os.path.relpath(__file__)
    if argv[:1] == ["--message"]:
        yield argv[1], open(argv[1], encoding="utf-8", errors="replace").read()
        return
    if argv[:1] == ["--log"]:
        rng = argv[1:2] or []
        out = subprocess.check_output(["git", "log", "--format=%H%x00%B%x01", *rng], text=True)
        for entry in out.split("\x01"):
            if "\x00" in entry:
                sha, body = entry.strip("\n").split("\x00", 1)
                yield f"commit {sha[:10]}", body
        return
    if argv[:1] == ["--staged"]:
        names = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z",
                                         "--diff-filter=ACMR"], text=True).split("\0")
        for f in names:
            if f and not f.endswith(SKIP_SUFFIXES) and os.path.relpath(f) != me:
                yield f, subprocess.check_output(["git", "show", ":" + f]).decode("utf-8", "replace")
        return
    files = argv or subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    for f in files:
        if not f or not os.path.isfile(f) or f.endswith(SKIP_SUFFIXES) or os.path.relpath(f) == me:
            continue
        try:
            yield f, open(f, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue


def main():
    rules = [(re.compile(p), why) for p, why in BUILTIN + deny_list()]
    if not any(why == "deny list" for _, why in rules):
        print("scrub: no deny list given (SCRUB_DENYLIST or SCRUB_DENYLIST_TEXT); built-in rules only",
              file=sys.stderr)
    bad = 0
    for label, text in sources(sys.argv[1:]):
        for n, line in enumerate(text.splitlines(), 1):
            for rx, why in rules:
                if rx.search(line):
                    # Never echo a deny-list match: the line may hold what is being kept private.
                    print(f"{label}:{n}: {why}" + ("" if why == "deny list" else f": {line.strip()[:120]}"))
                    bad += 1
                    break
    if bad:
        print(f"scrub: {bad} line(s) refused", file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
