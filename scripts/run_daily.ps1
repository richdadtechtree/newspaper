# 매일 아침 Windows 작업 스케줄러가 한 번 호출한다.
# 성공(오늘 신문 수집 완료)할 때까지, 또는 $Cutoff 시각이 지날 때까지
# $IntervalSeconds 간격으로 계속 재시도한 뒤 스스로 종료한다.
# (scripts/run_daily.sh의 Windows PowerShell 버전)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$Cutoff = "07:00"
$IntervalSeconds = 300

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Output "$ts $msg"
}

while ($true) {
    & $Python "app\main.py"
    if ($LASTEXITCODE -eq 0) {
        Log "성공, 종료합니다."
        exit 0
    }

    $now = Get-Date -Format "HH:mm"
    if ($now -gt $Cutoff) {
        Log "컷오프 시각(${Cutoff})을 지났습니다. 오늘은 포기하고 종료합니다."
        exit 1
    }

    Log "실패, ${IntervalSeconds}초 후 재시도합니다."
    Start-Sleep -Seconds $IntervalSeconds
}
