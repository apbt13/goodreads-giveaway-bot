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
# (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED = 0x80000003)
Add-Type -Name Power -Namespace Win32 -MemberDefinition @'
[DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
[Win32.Power]::SetThreadExecutionState([uint32]0x80000003) | Out-Null

while ($true) {
    "===== sweep started $(Get-Date) =====" | Tee-Object -FilePath sweep.log -Append
    python -u giveaways.py run --live *>> sweep.log
    "===== sweep done $(Get-Date); sleeping $Interval s =====" | Tee-Object -FilePath sweep.log -Append
    Start-Sleep -Seconds $Interval
}
