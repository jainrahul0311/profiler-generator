#!/usr/bin/env python3
"""
Build the GitHub Pages site for profiler-generator.

Run by the workflow's publish-page job. It merges the current run's result
artifacts (each carrying a meta.json) with the run's jobs metadata (log links +
scan times from the GitHub API), publishes this run's JSON, refreshes the run
history, and prunes JSON older than the retention window.

Truth rules (see the design discussion):
  * jsonAvailable is keyed off whether data/run-<n>/<app>.json PHYSICALLY exists,
    never a recomputed age -> raising retention later never resurrects pruned
    data, and the download button never points at a 404.
  * The prune step deletes JSON for runs older than the CURRENT retention window,
    so lowering retention removes older JSON on the next deploy.

Environment:
  SITE                gh-pages checkout dir (site root, mutated in place)
  INCOMING            dir of downloaded artifacts (one subdir per app)
  JOBS_JSON           path to the run's jobs API response
  TEMPLATE            path to page/index.html to copy into the site
  REPO                owner/repo
  RUN_NUMBER          this run's number (github.run_number)
  RUN_ID              this run's id     (github.run_id)
  RUN_STATUS          aggregate scan result: 'success' or anything else
  RETENTION_DAYS      JSON-download retention window (mirrors artifact retention)
  LOG_RETENTION_DAYS  GitHub Actions log retention (default 90)
"""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and (v is None or v == ""):
        raise SystemExit(f"missing required env {name}")
    return v


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(finished, now):
    dt = parse_iso(finished)
    if dt is None:
        return 0.0
    return (now - dt).total_seconds() / 86400.0


def main():
    SITE = Path(env("SITE", required=True))
    INCOMING = Path(env("INCOMING", required=True))
    JOBS_JSON = Path(env("JOBS_JSON", required=True))
    TEMPLATE = Path(env("TEMPLATE", required=True))
    REPO = env("REPO", required=True)
    RUN_NUMBER = int(env("RUN_NUMBER", required=True))
    RUN_ID = env("RUN_ID", required=True)
    RUN_STATUS = env("RUN_STATUS", "success")
    RETENTION_DAYS = int(env("RETENTION_DAYS", "1"))
    LOG_RETENTION_DAYS = int(env("LOG_RETENTION_DAYS", "90"))
    MAX_RUNS = int(env("MAX_RUNS", "0"))  # 0 = keep all runs in the dropdown

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "success" if RUN_STATUS == "success" else "warning"

    (SITE / "runs").mkdir(parents=True, exist_ok=True)
    (SITE / "data").mkdir(parents=True, exist_ok=True)

    # --- map app -> {log, when} from the jobs API response ---------------------
    jobs = {}
    try:
        raw = json.loads(JOBS_JSON.read_text())
        for j in raw.get("jobs", []):
            name = j.get("name", "")
            if name.startswith("scan "):
                app = name[len("scan "):].strip()
                jobs[app] = {"log": j.get("html_url", ""), "when": j.get("completed_at") or now_iso}
    except (OSError, ValueError):
        pass

    # --- build this run's rows from the incoming artifacts ---------------------
    run_data_dir = SITE / "data" / f"run-{RUN_NUMBER}"
    run_data_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for sub in sorted(p for p in INCOMING.iterdir() if p.is_dir()) if INCOMING.exists() else []:
        meta_path = sub / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except ValueError:
            continue
        app = meta.get("app") or sub.name
        result_json = sub / f"{app}.json"
        if not result_json.exists():
            # fall back to the only *.json that isn't meta.json
            cands = [p for p in sub.glob("*.json") if p.name != "meta.json"]
            if not cands:
                continue
            result_json = cands[0]

        dest = run_data_dir / f"{app}.json"
        shutil.copyfile(result_json, dest)
        info = jobs.get(app, {})
        rows.append({
            "app": app,
            "repo": meta.get("repo", ""),
            "lang": meta.get("lang", "—"),
            "langPct": meta.get("langPct", 0),
            "profiler": meta.get("profilerUrl", ""),
            "log": info.get("log", ""),
            "when": info.get("when", now_iso),
            "bytes": dest.stat().st_size,
            "jsonAvailable": True,
            "logAvailable": True,
        })

    rows.sort(key=lambda r: r["bytes"], reverse=True)

    run_file = SITE / "runs" / f"run-{RUN_NUMBER}.json"
    run_file.write_text(json.dumps({
        "number": RUN_NUMBER, "runId": RUN_ID, "finished": now_iso,
        "status": status, "rows": rows,
    }, indent=2))

    # --- load / update the history index ---------------------------------------
    index_path = SITE / "index.json"
    index = {"repo": REPO, "retentionDays": RETENTION_DAYS, "runs": []}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
        except ValueError:
            pass

    runs = {r["number"]: r for r in index.get("runs", [])}
    runs[RUN_NUMBER] = {
        "number": RUN_NUMBER, "runId": RUN_ID, "finished": now_iso,
        "status": status, "repoCount": len(rows),
    }

    # --- optional hard cap on how many runs the dropdown keeps -----------------
    ordered = sorted(runs.values(), key=lambda r: r["number"], reverse=True)
    if MAX_RUNS > 0 and len(ordered) > MAX_RUNS:
        for entry in ordered[MAX_RUNS:]:
            n = entry["number"]
            (SITE / "runs" / f"run-{n}.json").unlink(missing_ok=True)
            shutil.rmtree(SITE / "data" / f"run-{n}", ignore_errors=True)
        ordered = ordered[:MAX_RUNS]
    runs = {r["number"]: r for r in ordered}

    # --- prune old JSON + recompute availability flags for every run -----------
    for num, entry in list(runs.items()):
        rf = SITE / "runs" / f"run-{num}.json"
        if not rf.exists():
            continue
        try:
            rd = json.loads(rf.read_text())
        except ValueError:
            continue
        a = age_days(rd.get("finished"), now)
        ddir = SITE / "data" / f"run-{num}"
        if a > RETENTION_DAYS and ddir.exists():
            shutil.rmtree(ddir, ignore_errors=True)
        log_ok = a <= LOG_RETENTION_DAYS
        for r in rd.get("rows", []):
            r["jsonAvailable"] = (ddir / f"{r['app']}.json").exists()
            r["logAvailable"] = bool(r.get("log")) and log_ok
        rf.write_text(json.dumps(rd, indent=2))
        entry["repoCount"] = len(rd.get("rows", []))
        entry["status"] = rd.get("status", entry.get("status"))

    index["repo"] = REPO
    index["retentionDays"] = RETENTION_DAYS
    index["generated"] = now_iso
    index["runs"] = sorted(runs.values(), key=lambda r: r["number"], reverse=True)
    index_path.write_text(json.dumps(index, indent=2))

    # --- copy the page template + disable Jekyll -------------------------------
    shutil.copyfile(TEMPLATE, SITE / "index.html")
    (SITE / ".nojekyll").write_text("")

    print(f"Published run #{RUN_NUMBER}: {len(rows)} repos, "
          f"{len(index['runs'])} runs in history, retention {RETENTION_DAYS}d.")


if __name__ == "__main__":
    main()
