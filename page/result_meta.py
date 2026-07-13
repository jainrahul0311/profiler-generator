#!/usr/bin/env python3
"""
Write meta.json for one scan result, for the dashboard build to consume.

Usage:
  result_meta.py <out_meta_path> <app> <repo> <profiler_url> <result_json>

The dominant language is the top programming language by lines of code, taken
from the result's `composition` array.
"""
import json
import sys


def main():
    out_path, app, repo, url, result_json = sys.argv[1:6]
    result = json.load(open(result_json))
    comp = [c for c in result.get("composition", []) if c.get("type") == "programming"]
    tot = sum(c.get("nbLocs", 0) for c in comp)
    if tot > 0:
        top = max(comp, key=lambda c: c.get("nbLocs", 0))
        lang, pct = top.get("language", "-"), round(top.get("nbLocs", 0) * 100 / tot)
    else:
        lang, pct = "-", 0
    json.dump({"app": app, "repo": repo, "profilerUrl": url,
               "lang": lang, "langPct": pct}, open(out_path, "w"))
    print(f"{app}: dominant language {lang} ({pct}%)")


if __name__ == "__main__":
    main()
