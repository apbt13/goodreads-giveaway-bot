# Running on Windows

The code is identical to the Mac version. You only redo the environment setup and
log in fresh. **Bring `entered.json` over** so it doesn't re-enter what's already done.

## What to copy from the Mac
Copy these into a folder on the PC (e.g. `C:\Users\<you>\goodreads-giveaways\`):
- `giveaways.py`, `config.yaml`, `requirements.txt`, `sweep_loop.ps1`, `WINDOWS.md`
- **`entered.json`**  <- important: the dedupe log, so it continues instead of restarting

Do NOT copy `browser-profile/` (re-login below) or `.venv/` (rebuilt below).

## One-time setup (PowerShell)
```powershell
# 1. Install Python 3.12 from https://python.org  (tick "Add Python to PATH")
# 2. Open PowerShell and go to the folder:
cd C:\Users\<you>\goodreads-giveaways

# 3. Create + activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
#    If activation is blocked:
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Install dependencies + the browser
pip install -r requirements.txt
python -m playwright install chromium

# 5. Log in once (a browser opens; sign in to Goodreads, then press Enter)
python giveaways.py login
```

## Test, then run
```powershell
python giveaways.py run --live --limit 3     # confirm 3 real entries, no errors
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
- **Don't run the Mac and the PC at the same time** — they keep separate `entered.json`
  files and would double-enter. Stop one before starting the other.
