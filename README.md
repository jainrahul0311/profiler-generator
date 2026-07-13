# profiler-generator

Runs the CAST Profiler CLI over a set of demo applications every day and
publishes the results to a **GitHub Pages dashboard** with the full run history.

## Dashboard

Each run rebuilds a dashboard (served from the `gh-pages` branch) that lists, for
the selected run, every repository with its **dominant language**, **scan time**
(in your local time zone), a link to the interactive **CAST Profiler result**, a
link to the **job log**, and a **JSON download**. A dropdown switches between
past runs.

Old runs stay browsable forever; only their downloadable data ages out. JSON is
kept for `RETENTION_DAYS` (see below) then pruned — expired rows show a disabled
"Expired" chip instead of a dead link, and logs likewise show "No log" once
GitHub stops retaining them. The profiler links always stay live.

## How it works

[`.github/workflows/profiler-scan.yml`](.github/workflows/profiler-scan.yml)
runs **at 9 PM IST (15:30 UTC) every day** and can also be started
manually. For each project in the matrix, in its own parallel job, it:

1. clones the repo (shallow),
2. runs `castimaging/profiler-cli:latest --name <app> /source -ci`,
3. finds the generated `<app>.json` (`results/<app>/<app>.json`),
4. derives the dominant language from the result's `composition`, captures the
   profiler result URL from the CLI output, and uploads `<app>.json` +
   a small `meta.json` as one artifact named `<app>`.

`fail-fast: false`, so one project failing does not cancel the others.

A final **publish-page** job (runs even if some scans failed) downloads all the
result artifacts, reads each run's job metadata from the GitHub API (log links +
scan times), and runs [`page/build_site.py`](page/build_site.py) to update the
site on `gh-pages`:

- publishes this run's JSON under `data/run-<n>/`,
- appends the run to `index.json` (the history the dropdown reads),
- **prunes** JSON for runs older than `RETENTION_DAYS`, keying each row's
  availability off whether the file physically exists (so raising retention later
  never resurrects pruned data, and a download button never points at a 404).

### Retention

`RETENTION_DAYS` (a workflow-level `env`, default `1`) is the single source of
truth: it sets both the Actions artifact retention **and** how long the dashboard
keeps JSON downloadable. Change it in one place. Raising it only affects future
runs; lowering it prunes older JSON on the next run.

### Where the profiler writes its output

The CLI writes its results, **inside the container**, under
`/home/profiler/.local/share/CAST/CAST-Profiler/<app>/`:

| File | Description |
| ---- | ----------- |
| `<app>.json` | D3 evaluation results combined with telemetry data — **this is the artifact** |
| `<app>.json.zs` | compressed CAST Profiler report |
| `<app>-insight-report.html` | HTML insight report |

The workflow mounts a host folder onto that container path, so it can pick up
`<app>.json` after the run.

## Projects scanned

| App name           | Repository |
| ------------------ | ---------- |
| `intellij-community`  | https://github.com/jetbrains/intellij-community |
| `apache-netbeans`     | https://github.com/apache/netbeans |
| `keycloak`            | https://github.com/keycloak/keycloak |
| `jetbrains-android`   | https://github.com/JetBrains/android |
| `dotnet-roslyn`       | https://github.com/dotnet/roslyn |
| `elasticsearch`       | https://github.com/elastic/elasticsearch |
| `apache-camel`        | https://github.com/apache/camel |
| `dotnet-runtime`      | https://github.com/dotnet/runtime |
| `apache-beam`         | https://github.com/apache/beam |
| `apache-hadoop`       | https://github.com/apache/hadoop |
| `mono`                | https://github.com/mono/mono |

To add or remove a project, edit the `matrix.include` list in the workflow —
each entry is a `url` (public clone URL) and a `name` (the `--name` app name,
also the artifact name).

## Required secret

None. The CAST Profiler CLI runs without an analysis key.

## Getting the results

Open the **GitHub Pages dashboard** (Settings → Pages shows the URL) and pick a
run from the dropdown. Every row links to the profiler result, the job log, and
the JSON download.

The raw `<app>.json` files are also available as GitHub Actions artifacts on each
run (named `<app>`, containing `<app>.json` + `meta.json`) for `RETENTION_DAYS`.

## Running locally

```bash
docker run --rm --pull always \
  -v "$(pwd):/source" \
  castimaging/profiler-cli:latest --name <app_name> /source -ci
```

To also collect the JSON on your host, mount the profiler output folder:

```bash
docker run --rm --pull always \
  -v "$(pwd):/source" \
  -v "$(pwd)/results:/home/profiler/.local/share/CAST/CAST-Profiler" \
  castimaging/profiler-cli:latest --name <app_name> /source -ci
# result: results/<app_name>/<app_name>.json
```
