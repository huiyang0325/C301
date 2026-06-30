$conns = Get-NetTCPConnection -LocalPort 1246 | Where-Object {$_.State -eq 'Listen'}
foreach ($c in $conns) {
    $procId = $c.OwningProcessId
    Write-Host "PID: $procId"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
$remaining = Get-NetTCPConnection -LocalPort 1246 | Where-Object {$_.State -eq 'Listen'}
if ($remaining) {
    Write-Host "Still listening:"
    $remaining | ForEach-Object { Write-Host $_.OwningProcessId }
} else {
    Write-Host "Port 1246 is free"
}
