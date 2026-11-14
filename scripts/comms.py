#!/usr/bin/env python3
"""Shared agent channel (AGENT_COMMS.md on branch agent-comms).

  comms.py read [--tail N]
  comms.py open
  comms.py post --as claude-code@tuomas --type FYI [--to who] [--re id] "message"   (message '-' or omitted: stdin)

Works from any checkout of the repo (uses `git remote get-url origin`, or $COMMS_REMOTE) and keeps its
own disposable clone in ~/.cache/agent-comms. Needs git and Python 3 only.
"""
import argparse, datetime, os, random, re, subprocess, sys, time

BRANCH, FILE = "agent-comms", "AGENT_COMMS.md"
TYPES = ["FYI", "CLAIM", "RELEASE", "STATUS", "QUESTION", "PROBLEM", "NEEDS-DECISION", "ANSWER", "DECIDED", "RESOLVED"]
NEEDS_REPLY = {"QUESTION", "PROBLEM", "NEEDS-DECISION"}
CLOSERS = {"ANSWER", "DECIDED", "RESOLVED"}


def git(*a, cwd=None, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr.strip()}")
    return r


def clone_dir():
    url = os.environ.get("COMMS_REMOTE") or git("remote", "get-url", "origin").stdout.strip()
    base = os.environ.get("COMMS_DIR") or os.path.expanduser("~/.cache/agent-comms")
    return url, os.path.join(base, re.sub(r"[^A-Za-z0-9]+", "_", url))


def sync():
    url, d = clone_dir()
    if not os.path.isdir(os.path.join(d, ".git")):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        git("clone", "--quiet", "--branch", BRANCH, "--single-branch", url, d)
    else:
        git("fetch", "--quiet", "origin", BRANCH, cwd=d)
        git("reset", "--quiet", "--hard", f"origin/{BRANCH}", cwd=d)
    return d


def entries(text):
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"### \[([^\]]+)\] (\S+ \S+) · ([^·]+?) · ([A-Z-]+)(.*)$", line)
        if m:
            cur = dict(id=m[1], ts=m[2], who=m[3], type=m[4], to=None, re=None, head=line, body=[])
            for part in m[5].split(" · "):
                if part.startswith("to "): cur["to"] = part[3:].strip()
                if part.startswith("re "): cur["re"] = part[3:].strip()
            out.append(cur)
        elif cur is not None:
            cur["body"].append(line)
    return out


def cmd_read(a):
    text = open(os.path.join(sync(), FILE), encoding="utf-8").read()
    if a.tail:
        es = entries(text)[-a.tail:]
        print("\n".join(e["head"] + "\n" + "\n".join(e["body"]).rstrip() + "\n" for e in es) or "(no entries)")
    else:
        print(text)


def cmd_open(a):
    es = entries(open(os.path.join(sync(), FILE), encoding="utf-8").read())
    closed = {e["re"] for e in es if e["type"] in CLOSERS and e["re"]}
    released = {e["re"] for e in es if e["type"] == "RELEASE" and e["re"]}
    op = [e for e in es if e["type"] in NEEDS_REPLY and e["id"] not in closed]
    cl = [e for e in es if e["type"] == "CLAIM" and e["id"] not in released]
    print("OPEN QUESTIONS / PROBLEMS / DECISIONS" if op else "No open questions, problems or decisions.")
    for e in op: print("  " + e["head"][4:])
    print("\nACTIVE CLAIMS" if cl else "\nNo active claims.")
    for e in cl: print("  " + e["head"][4:] + "\n    " + " ".join(x.strip() for x in e["body"] if x.strip())[:240])


def cmd_post(a):
    if a.type not in TYPES: sys.exit(f"type must be one of {', '.join(TYPES)}")
    msg = a.message if a.message not in (None, "-") else sys.stdin.read()
    msg = msg.strip()
    if not msg: sys.exit("empty message")
    now = datetime.datetime.now(datetime.timezone.utc)
    slug = re.sub(r"[^a-z0-9]+", "-", a.who.lower()).strip("-")
    eid = f"{now:%m%d-%H%M%S}-{slug}"
    head = f"### [{eid}] {now:%Y-%m-%d %H:%M}Z · {a.who} · {a.type}" + (f" · to {a.to}" if a.to else "") + (f" · re {a.re}" if a.re else "")
    block = f"\n{head}\n{msg}\n"
    for attempt in range(8):
        d = sync()
        path = os.path.join(d, FILE)
        raw = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(raw.rstrip("\n") + "\n" + block)
        git("add", FILE, cwd=d)
        git("-c", f"user.name={a.who}", "-c", "user.email=agent-comms@invalid.example", "commit", "--quiet", "-m", f"comms: {a.type} {eid}", cwd=d)
        if git("push", "--quiet", "origin", BRANCH, cwd=d, check=False).returncode == 0:
            print(f"posted {eid}")
            return
        time.sleep(0.5 + random.random() * 1.5)
    sys.exit("could not push after 8 tries; try again, or ask your human")


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
s = p.add_subparsers(dest="cmd", required=True)
r = s.add_parser("read"); r.add_argument("--tail", type=int); r.set_defaults(f=cmd_read)
o = s.add_parser("open"); o.set_defaults(f=cmd_open)
w = s.add_parser("post")
w.add_argument("--as", dest="who", required=True); w.add_argument("--type", required=True)
w.add_argument("--to"); w.add_argument("--re"); w.add_argument("message", nargs="?")
w.set_defaults(f=cmd_post)
a = p.parse_args()
a.f(a)
