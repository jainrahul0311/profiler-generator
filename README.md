# profiler-generator

Generates a CAST Profiler result (`.json`) for a set of demo applications every
day using the CAST Profiler CLI, and stores each one as a GitHub Actions
artifact.

## How it works

[`.github/workflows/profiler-scan.yml`](.github/workflows/profiler-scan.yml)
runs **at 9 PM IST (15:30 UTC) every day** and can also be started
manually. For each project in the matrix, in its own parallel job, it:

1. clones the repo (shallow),
2. runs `castimaging/profiler-cli:latest --name <app> /source -ci`,
3. finds the generated `<app>.json`
   (`results/<app>/<app>.json`),
4. uploads it as an artifact named `<app>.json`.

`fail-fast: false`, so one project failing does not cancel the others.

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

Open the latest **Scheduled Profiler scan** run under the **Actions** tab and
download the `<app>.json` artifacts. They use a stable name and a 1-day
retention, so each day's run refreshes them.

The **Collect profiler result URLs** job at the end of every run prints all the
`https://profiler.castsoftware.io/v2/results?at=<id>` links in one place (job log
and run summary). If any scan job fails, that job still runs but is flagged with a
warning.

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
