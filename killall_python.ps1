Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
$listening = Get-NetTCPConnection -LocalPort 1246 -ErrorAction SilentlyContinue | Where-Object {$_.State -eq 'Listen'}
if ($listening) {
    Write-Host "Port 1246 still in use by PIDs:"
    $listening | ForEach-Object { Write-Host $_.OwningProcessId }
} else {
    Write-Host "Port 1246 is now FREE"
}
