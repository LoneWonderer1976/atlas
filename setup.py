"""setup.py -- put Atlas on GitHub: the repository, the page, the variables, the first run.

    gh auth login --web        # once, in a terminal: opens the browser, you approve -- the ONE step that is yours
    python setup.py            # then this does the rest; safe to re-run, every step skips what is done

What it does, in order:
  1. checks `gh` is logged in (else tells you the command above and stops)
  2. creates the private repository <you>/atlas from this folder and pushes it (or just pushes)
  3. switches on GitHub Pages from main:/docs and records the page's address as the PAGE_URL variable
  4. tells you whether the GARMINTOKENS secret is set -- `python -m atlas.login` sets it -- and, if it
     is, runs the first sync so the page fills straight away
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = "atlas"


def gh_path() -> str:
    found = shutil.which("gh") or next((p for p in (r"C:\Program Files\GitHub CLI\gh.exe",) if os.path.exists(p)), None)
    if not found:
        sys.exit("gh (the GitHub CLI) is not installed -- `winget install GitHub.cli`, open a new terminal, try again")
    return found


GH = None


def gh(*args, check=True, capture=True, quiet=False):
    cmd = [GH, *args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=capture, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        if quiet:
            return r
        sys.exit(f"gh {' '.join(args)} failed:\n{(r.stderr or r.stdout).strip()}")
    return r


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r


def main() -> None:
    global GH
    GH = gh_path()
    if gh("auth", "status", check=False).returncode != 0:
        print("You are not logged into GitHub yet. In a terminal:\n\n    gh auth login --web\n\n"
              "(GitHub.com, HTTPS, log in with a web browser -- approve the code it shows), then run this again.")
        sys.exit(1)
    login = gh("api", "user", "--jq", ".login").stdout.strip()
    full = f"{login}/{REPO}"
    print(f"logged in as {login}")

    # --- 2. the repository ---------------------------------------------------------------------
    if git("remote", "get-url", "origin", check=False).returncode != 0:
        if gh("repo", "view", full, check=False).returncode == 0:
            git("remote", "add", "origin", f"https://github.com/{full}.git")
            print(f"repository {full} exists; remote added")
        else:
            gh("repo", "create", REPO, "--public", "--source", str(ROOT), "--remote", "origin", "--push",
               "--description", "Joe's training, measured: Garmin -> records, rankings, progress")
            print(f"created public repository {full} and pushed")
    r = git("push", "-u", "origin", "main", check=False)
    print("pushed" if r.returncode == 0 else f"push: {r.stderr.strip().splitlines()[-1]}")

    # --- 3. the page ---------------------------------------------------------------------------
    page_url = f"https://{login}.github.io/{REPO}/"
    r = gh("api", "-X", "POST", f"repos/{full}/pages", "-f", "source[branch]=main", "-f", "source[path]=/docs",
           "-f", "build_type=legacy", check=False)
    if r.returncode == 0:
        print(f"GitHub Pages switched on: {page_url}")
    elif "already" in (r.stderr + r.stdout).lower() or '"status":"409"' in (r.stderr + r.stdout).replace(" ", ""):
        print(f"GitHub Pages already on: {page_url}")
    else:
        print(f"could not switch Pages on automatically ({(r.stderr or r.stdout).strip()[:200]});\n"
              f"  do it once by hand: Settings -> Pages -> Deploy from a branch -> main, /docs")
    gh("variable", "set", "PAGE_URL", "--body", page_url, "-R", full)
    print("PAGE_URL variable set")

    # --- 4. the Garmin secret and the first run ------------------------------------------------
    secrets = gh("secret", "list", "-R", full, "--json", "name", "--jq", ".[].name", check=False).stdout.split()
    if "GARMINTOKENS" in secrets:
        gh("workflow", "run", "sync.yml", "-R", full, check=False)
        print("GARMINTOKENS is set; the first sync is running -- the page fills in a few minutes")
    else:
        print("\nOne thing left, and it needs the Garmin password typed by you:\n\n    python -m atlas.login\n")
    print(f"\nhis page: {page_url}\nthe repo: https://github.com/{full}")
    print(json.dumps({"login": login, "repo": full, "page": page_url}))


if __name__ == "__main__":
    main()
