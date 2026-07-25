# Running on Windows

The code is identical to the macOS/Linux version — only the environment-setup and
activation commands differ. Full setup flow (including the genre question) is in
[README.md](README.md) and [AGENTS.md](AGENTS.md); this file is just the Windows syntax.

## One-time setup (PowerShell)
```powershell
# 1. Install Python 3.10+ from https://python.org  (tick "Add Python to PATH")
# 2. Clone the repo and go into it:
git clone <this-repo-url>
cd <repo-folder>

# 3. Create + activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
#    If activation is blocked:
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Install dependencies + the browser
pip install -r requirements.txt
python -m playwright install chromium

# 5. Configure, then log in
python giveaways.py setup        # pick genres and how many per session
python giveaways.py login        # a browser opens; sign in to Goodreads, then press Enter
```

`config.yaml`, `entered.json`, and `browser-profile\` are per-machine and NOT in the
repo — you create them in the steps above.

## Test, then run
```powershell
python giveaways.py scan                      # preview matches (clicks nothing)
python giveaways.py run --live --limit 3      # confirm 3 real entries, no errors
powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1   # overnight loop
```

## Monitor / stop
```powershell
# total entered
python -c "import json;print(len(json.load(open('entered.json'))))"
# live activity
Get-Content .\sweep.log -Wait -Tail 30
# stop: close the sweep_loop window, or:
Get-Process python | Stop-Process
```

## Notes
- `sweep_loop.ps1` keeps Windows awake on its own (no `caffeinate` needed). Keep the
  laptop plugged in; a closed lid may still sleep depending on your power settings.
- **Only run one machine per Goodreads account at a time** — each machine keeps its own
  `entered.json` and two at once would double-enter. Stop one before starting another.
