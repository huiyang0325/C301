Get-Process | Where-Object {
    $_.MainWindowTitle -like "*uvicorn*" -or
    $_.MainWindowTitle -like "*ArcReel*" -or
    $_.Name -eq "python" -or
    $_.Name -eq "python3"
} | Format-Table Id,ProcessName,MainWindowTitle -AutoSize
