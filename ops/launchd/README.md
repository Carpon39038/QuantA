# QuantA launchd Templates

These templates are local-host examples for macOS launchd.

They intentionally do not include the Tushare token. Put host-local runtime
configuration in `data/env/live.env` first:

```bash
mkdir -p data/env data/logs
cp ops/live.env.example data/env/live.env
chmod 600 data/env/live.env
```

Then edit `data/env/live.env` and set `QUANTA_TUSHARE_TOKEN`.
The example also keeps the live runtime in `data/live/` so it does not overwrite the default dev fixture database.

If launchd resolves `python3` to a runtime without project dependencies, set
`QUANTA_PYTHON_BIN` in `data/env/live.env`. The shared entrypoint also tries to
auto-detect a Python that can import `duckdb`.

The launchd backend path defaults to `QUANTA_BACKEND_SKIP_BOOTSTRAP=1` so the
read path does not compete with the pipeline writer during restart.

## Manual foreground check

```bash
bash scripts/ops_entrypoint.sh pipeline
bash scripts/ops_entrypoint.sh backend
bash scripts/ops_entrypoint.sh frontend
```

## Install the examples

```bash
mkdir -p ~/Library/LaunchAgents
cp ops/launchd/com.quanta.*.plist.example ~/Library/LaunchAgents/

PROJECT_ROOT="$(pwd)"
for file in ~/Library/LaunchAgents/com.quanta.*.plist.example; do
  perl -0pi -e "s#__PROJECT_ROOT__#$PROJECT_ROOT#g" "$file"
done

for file in ~/Library/LaunchAgents/com.quanta.*.plist.example; do
  target="${file%.example}"
  mv "$file" "$target"
  launchctl bootstrap "gui/$(id -u)" "$target"
done
```

The launchd stdout / stderr files are in `data/logs/launchd-*.log`.
The resident scheduler JSONL stream is under the configured runtime data
directory. With `ops/live.env.example`, that path is
`data/live/logs/pipeline-daemon.jsonl`.

## Stop

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.quanta.pipeline.plist
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.quanta.backend.plist
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.quanta.frontend.plist
```
