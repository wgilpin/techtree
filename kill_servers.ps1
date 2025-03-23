# kill_all_python.ps1 - Script to forcefully kill ALL Python processes

Write-Host "Finding and killing all Python processes..." -ForegroundColor Cyan

# Use taskkill directly with wildcards to kill all python processes
$killOutput = cmd /c "taskkill /F /IM python*.exe /T 2>&1"

Write-Host $killOutput -ForegroundColor Yellow

# Verify if any Python processes remain
Start-Sleep -Seconds 1
$remainingProcesses = cmd /c "tasklist | findstr python"

if ($remainingProcesses) {
    Write-Host "`nSome Python processes could not be terminated. Try running as Administrator." -ForegroundColor Red
    Write-Host "Remaining processes:" -ForegroundColor Red
    Write-Host $remainingProcesses -ForegroundColor Red

    # Try killing again with specific PIDs
    Write-Host "`nAttempting to kill remaining processes by PID..." -ForegroundColor Yellow

    # Extract PIDs and kill each one
    foreach ($line in $remainingProcesses.Split("`n")) {
        if ($line -match "python.*\s+(\d+)\s+") {
            $pid = $matches[1]
            $killPidOutput = cmd /c "taskkill /F /PID $pid /T 2>&1"
            Write-Host $killPidOutput -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "`nAll Python processes have been t