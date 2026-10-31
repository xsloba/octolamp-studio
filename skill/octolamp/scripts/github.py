"""GitHub data for the lamp: latest Actions run status, and today's contributions.

Auth, in order: $GITHUB_TOKEN / $GH_TOKEN, then a signed-in `gh` CLI, then none
(public data only, 60 requests/hour, and no contribution calendar). Tokens are
never printed.
"""
import datetime, json, os, shutil, subprocess, urllib.parse, urllib.request

API = "https://api.github.com"


def _gh():
    return shutil.which("gh") or next((p for p in (os.path.expanduser("~/.local/bin/gh"), "/opt/homebrew/bin/gh",
                                                   "/usr/local/bin/gh") if os.path.exists(p)), None)


def _token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


_mode = []
def auth_mode():
    if _mode: return _mode[0]
    _mode.append(_auth_mode()); return _mode[0]


def _auth_mode():
    if _token(): return "token"
    gh = _gh()
    # `gh auth token` checks only the active account (`auth status` fails if any stored account is stale);
    # its output is captured and discarded, never printed
    if gh and subprocess.run([gh, "auth", "token"], capture_output=True).returncode == 0: return "gh"
    return "none"


def rest(path):
    """GET a REST path like /repos/o/r/actions/runs?per_page=1."""
    mode = auth_mode()
    if mode == "gh":
        r = subprocess.run([_gh(), "api", path.lstrip("/")], capture_output=True, text=True, timeout=30)
        if r.returncode: raise SystemExit(f"GitHub API {path}: {r.stderr.strip()[:200]}")
        return json.loads(r.stdout)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "octolamp"}
    if mode == "token": headers["Authorization"] = "Bearer " + _token()
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=20) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API {path}: HTTP {e.code} {e.reason}"
                         + (" (sign in with `gh auth login` or set GITHUB_TOKEN for private repos)" if e.code in (401, 403, 404) else ""))


def graphql(query, variables):
    mode = auth_mode()
    if mode == "none": return None
    if mode == "gh":
        args = [_gh(), "api", "graphql", "-f", f"query={query}"] + sum((["-f", f"{k}={v}"] for k, v in variables.items()), [])
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if r.returncode: raise SystemExit(f"GitHub GraphQL: {r.stderr.strip()[:200]}")
        return json.loads(r.stdout)["data"]
    req = urllib.request.Request(API + "/graphql", data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": "Bearer " + _token(), "User-Agent": "octolamp"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())["data"]


# ---------- Actions ----------

def latest_run(repo, branch=None, workflow=None):
    q = {"per_page": 1}
    if branch: q["branch"] = branch
    base = f"/repos/{repo}/actions/workflows/{urllib.parse.quote(workflow)}/runs" if workflow else f"/repos/{repo}/actions/runs"
    runs = rest(base + "?" + urllib.parse.urlencode(q)).get("workflow_runs", [])
    return runs[0] if runs else None


def run_state(run):
    """Map a workflow run to running / passed / failed / neutral."""
    if run is None: return "none"
    if run["status"] != "completed": return "running"            # queued, in_progress, waiting, requested, pending
    c = run.get("conclusion")
    if c == "success": return "passed"
    if c in ("failure", "timed_out", "startup_failure", "action_required"): return "failed"
    return "neutral"                                              # cancelled, skipped, neutral, stale


# ---------- contributions ----------

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

_CAL = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) { contributionsCollection(from: $from, to: $to) {
    contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } } } } }"""


def viewer_login():
    return rest("/user")["login"] if auth_mode() != "none" else None


def contributions_today(login):
    """-> (count, level 0-4, source). Uses GitHub's own calendar when signed in, else public events."""
    today = datetime.date.today()
    if auth_mode() != "none":
        start = datetime.datetime.combine(today - datetime.timedelta(days=1), datetime.time()).astimezone()
        end = datetime.datetime.now().astimezone()
        data = graphql(_CAL, {"login": login, "from": start.isoformat(), "to": end.isoformat()})
        days = [d for w in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
        day = next((d for d in days if d["date"] == today.isoformat()), None) or days[-1]
        return day["contributionCount"], LEVELS.get(day["contributionLevel"], 0), "contribution calendar"
    # unauthenticated fallback: public events today (rough: pushed commits + opened PRs/issues + reviews)
    n = 0
    for e in rest(f"/users/{login}/events/public?per_page=100"):
        if datetime.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone().date() != today: continue
        t, p = e["type"], e.get("payload", {})
        if t == "PushEvent": n += p.get("distinct_size", p.get("size", 1))
        elif t in ("PullRequestEvent", "IssuesEvent") and p.get("action") == "opened": n += 1
        elif t == "PullRequestReviewEvent": n += 1
    level = 0 if n == 0 else 1 if n <= 2 else 2 if n <= 5 else 3 if n <= 9 else 4
    return n, level, "public events (sign in for the exact calendar)"
