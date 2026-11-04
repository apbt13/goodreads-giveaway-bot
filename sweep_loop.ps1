# sweep_loop.ps1 - Windows overnight runner for the Goodreads giveaway bot.
# The PowerShell equivalent of sweep_loop.sh (bash/caffeinate are macOS-only).
#
# Run it:
#   powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1
# Optional custom interval in seconds (default 30 min):
#   powershell -ExecutionPolicy Bypass -File .\sweep_loop.ps1 -Interval 1800
#
# Watch progress:  Get-Content .\sweep.log -Wait -Tail 30
# Stop it:         close this window, or press Ctrl+C

param([int]$Interval = 1800)

Set-Location $PSScriptRoot

# Activate the virtual environment
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

# Keep Windows awake while this runs
# The DISPLAY must stay on, not just the system: Playwright drives a headful
# Chromium (headless gets WAF-403'd by Goodreads), and once the monitor powers
# off Chromium stops compositing, so clicks hang forever instead of timing out.
#
# PowerShell 5.1 parses 0x80000003 as a NEGATIVE Int32, so [uint32]0x80000003
# throws "Value was either too large or too small for a UInt32" and the
# keep-awake silently never applies. Use decimal uint32 values instead.
$ES_CONTINUOUS       = [uint32]2147483648  # 0x80000000
$ES_SYSTEM_REQUIRED  = [uint32]1           # 0x00000001
$ES_DISPLAY_REQUIRED = [uint32]2           # 0x00000002
$ES_KEEP_AWAKE = [uint32]($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED)

Add-Type -Name Power -Namespace Win32 -MemberDefinition @'
[DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
# Returns the previous state, or 0 on failure. Say so loudly rather than letting
# a silent failure strand the sweep on a dark screen hours later.
if ([Win32.Power]::SetThreadExecutionState($ES_KEEP_AWAKE) -eq 0) {
    "WARNING: keep-awake request failed; display may sleep and hang this sweep" |
        Tee-Object -FilePath sweep.log -Append
}

while ($true) {
    "===== sweep started $(Get-Date) =====" | Tee-Object -FilePath sweep.log -Append
    python -u giveaways.py run --live *>> sweep.log
    "===== sweep done $(Get-Date); sleeping $Interval s =====" | Tee-Object -FilePath sweep.log -Append
    Start-Sleep -Seconds $Interval
}
