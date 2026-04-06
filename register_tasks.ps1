# WordPress Auto Posting - Task Scheduler Registration
# Run as Administrator

$dir = "C:\Users\hyun\wordpress_auto_poster\"

$tasks = @(
    @{ Name="WP_Post_0600"; Bat="run_06.bat"; Time="06:00"; Desc="Daily 06:00 - Living Economy" },
    @{ Name="WP_Post_0900"; Bat="run_09.bat"; Time="09:00"; Desc="Daily 09:00 - Living Health" },
    @{ Name="WP_Post_1300"; Bat="run_13.bat"; Time="13:00"; Desc="Daily 13:00 - Support Policy" },
    @{ Name="WP_Post_1800"; Bat="run_18.bat"; Time="18:00"; Desc="Daily 18:00 - Rotation" },
    @{ Name="WP_Post_2100"; Bat="run_21.bat"; Time="21:00"; Desc="Daily 21:00 - Trend Keywords" }
)

Write-Host "Registering WordPress auto-posting scheduler..." -ForegroundColor Cyan

foreach ($t in $tasks) {
    Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue

    $action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$($dir)$($t.Bat)`""
    $trigger  = New-ScheduledTaskTrigger -Daily -At $t.Time
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -StartWhenAvailable `
        -DontStopOnIdleEnd

    $result = Register-ScheduledTask `
        -TaskName $t.Name `
        -Description $t.Desc `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force `
        -ErrorAction SilentlyContinue

    if ($result) {
        Write-Host "[OK] $($t.Name) ($($t.Time)) registered" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($t.Name) failed - run as Administrator" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Registered Tasks ===" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like "WP_Post*" } | ForEach-Object {
    $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -ErrorAction SilentlyContinue
    Write-Host ("  {0,-20} State:{1,-10} Next:{2}" -f $_.TaskName, $_.State, $info.NextRunTime)
}
Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
