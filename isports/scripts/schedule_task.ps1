$ScriptPath = "d:\LCC\iSports\isports\scripts\update_fixtures.ps1"

$Action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -Weekly -At 3am -DaysOfWeek Sunday
$Principal = New-ScheduledTaskPrincipal -UserId (Get-Item env:\USERNAME).Value -LogonType Interactive

$TaskName = "iSportsWeeklyFixtureUpdate"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -Action $Action -Trigger $Trigger -Principal $Principal -TaskName $TaskName -Description "Automatically update iSports football fixtures every week."

Write-Host "Successfully scheduled weekly fixture updates for Sunday at 3:00 AM." -ForegroundColor Green
Write-Host "Task Name: $TaskName"
