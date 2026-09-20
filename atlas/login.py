"""login.py -- the ONE interactive step: log into Garmin Connect once, on Ben's PC.

    python -m atlas.login

Asks for the account's email and password (and the MFA code if the account has one), then:
  1. caches the tokens in .garmin_tokens/ (git-ignored) so `python -m atlas.sync` works locally;
  2. stores the token string as the repository secret GARMINTOKENS through `gh` (if setup.py has
     been run and gh is logged in) and starts the first sync -- or, failing that, prints the
     string to paste into the secret by hand;
  3. fetches everything since HISTORY_START locally as well, so `python -m atlas.stats --print`
     shows the numbers straight away.

Ben types the credentials; nothing stores them. The tokens last about a year -- when the Action
starts failing with an authentication error, run this again.
"""
import getpass
import os
import shutil
import subprocess
import sys

from . import store
from .sync import TOKEN_DIR


def _gh():
    return shutil.which("gh") or next((p for p in (r"C:\Program Files\GitHub CLI\gh.exe",) if os.path.exists(p)), None)


def _repo() -> str | None:
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=store.ROOT, capture_output=True, text=True)
    url = r.stdout.strip()
    if r.returncode != 0 or "github.com" not in url:
        return None
    return url.split("github.com")[-1].strip(":/").removesuffix(".git")


def set_secret(tokens: str) -> bool:
    gh, repo = _gh(), _repo()
    if not gh or not repo:
        return False
    r = subprocess.run([gh, "secret", "set", "GARMINTOKENS", "-R", repo], input=tokens, capture_output=True,
                       text=True, cwd=store.ROOT)
    if r.returncode != 0:
        print(f"  (gh could not set the secret: {(r.stderr or r.stdout).strip()[:200]})")
        return False
    print(f"GARMINTOKENS secret set on {repo}")
    r = subprocess.run([gh, "workflow", "run", "sync.yml", "-R", repo], capture_output=True, text=True, cwd=store.ROOT)
    print("first sync started on GitHub -- the page fills in a few minutes" if r.returncode == 0
          else f"  (could not start the sync workflow: {(r.stderr or r.stdout).strip()[:200]}; run it from the Actions tab)")
    return True


def main() -> None:
    try:
        from garminconnect import Garmin
    except ImportError:
        sys.exit("garminconnect is not installed:  pip install garminconnect")
    print("Garmin Connect login for Atlas (the account Joe's watch syncs to)")
    email = input("  email: ").strip()
    password = getpass.getpass("  password (hidden): ")
    api = Garmin(email, password, prompt_mfa=lambda: input("  MFA code: ").strip())
    TOKEN_DIR.mkdir(exist_ok=True)
    api.login(str(TOKEN_DIR))
    try:
        name = api.get_full_name()
    except Exception:
        name = "?"
    tokens = api.client.dumps()
    print(f"\nlogged in as {name}; tokens cached in {TOKEN_DIR}\n")
    if not set_secret(tokens):
        print("Paste EVERYTHING between the lines into the repository secret GARMINTOKENS")
        print("(GitHub -> the atlas repo -> Settings -> Secrets and variables -> Actions -> New secret):")
        print("-" * 78)
        print(tokens)
        print("-" * 78)
    print("\nfetching his activities here too ...")
    from . import sync
    sync.run()
    print("done -- `python -m atlas.stats --print` shows the numbers")


if __name__ == "__main__":
    main()
