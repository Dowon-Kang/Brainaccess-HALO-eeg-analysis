<#
세션 한 번 실행: 1) 착용 신호 사전 점검 → 2) 자극(LabRecorder 녹화 확인 포함) → 3) XDF QC → 4) 압축 2개(원본 유지)
  둘 다 참가자별 폴더 data\<ID>\ 에 저장
  - <ID>_<mode>_<시각>_events.zip = events.csv + events.json + XDF
  - <Board 녹화 이름>_eeg.zip     = Documents\BrainAccessData\... 의 .db + .db-wal + .db-shm (자극 실행 시간과 가장 많이 겹치는 녹화)

사용 (프로젝트 폴더의 PowerShell에서)
  .\run_session.ps1 -Participant P003 -Session 2      # 본측정 (-Session 필수: 같은 참가자 반복 세션마다 seed·색 순서가 달라짐)
  .\run_session.ps1 -Participant P003 -Practice       # 연습 6시퀀스
  .\run_session.ps1 -Participant P003 -Practice -OneBlock
  .\run_session.ps1 -Participant T00 -Practice -NoPrecheck -NoBoardRecord   # 장비 미착용 시스템 시험(연습 전용)
  시작 전 자동 확인: 사전 점검 GO + BrainAccess Board Record 중(.db 파일이 커지는지)
  추가 인자는 -StimArgs '--start-block','3' 처럼 stim_rgb.py에 그대로 전달
  .\run_session.ps1 -Participant P003 -ZipOnly [-Events P003_main_..._events.json]   # 압축만 나중에 (QC 결과 다시 표시 후 확인)

수동으로 해야 하는 것: LabRecorder Update → 두 스트림 체크 → 파일명 → Start, 끝나면 Stop
기준값은 모두 config/protocol.json (이 파일에 숫자 없음. 아래 숫자는 화면 표시 폭뿐)
#>
param(
    [Parameter(Mandatory = $true)][string]$Participant,
    [int]$Session = 0,
    [switch]$Practice,
    [switch]$OneBlock,
    [switch]$NoPrecheck,
    [switch]$NoBoardRecord,
    [string[]]$StimArgs = @(),
    [switch]$ZipOnly,          # 자극 없이: 최근(또는 -Events) 실행의 QC 결과 표시 + 압축 여부 확인
    [string]$Events = ''      # -ZipOnly 대상 events.json 이름 (기본: 그 참가자의 최근 실행)
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'

# ================================================================ 출력 모양 (색·태그·한글 폭 정렬)
$LineW = 64
$ConW = 120
try { if ($Host.UI.RawUI.WindowSize.Width -gt 40) { $ConW = $Host.UI.RawUI.WindowSize.Width - 1 } } catch {}

function Get-DispWidth([string]$s) {
    <# 화면 폭: 한글·한자·전각 2칸 #>
    $w = 0
    foreach ($ch in $s.ToCharArray()) {
        $c = [int]$ch
        if (($c -ge 0x1100 -and $c -le 0x115F) -or ($c -ge 0x2E80 -and $c -le 0xA4CF) -or ($c -ge 0xAC00 -and $c -le 0xD7A3) -or
            ($c -ge 0xF900 -and $c -le 0xFAFF) -or ($c -ge 0xFE30 -and $c -le 0xFE4F) -or ($c -ge 0xFF00 -and $c -le 0xFF60) -or
            ($c -ge 0xFFE0 -and $c -le 0xFFE6)) { $w += 2 } else { $w += 1 }
    }
    $w
}
function Format-Cell([string]$s, [int]$w) { $s + (' ' * [math]::Max(0, $w - (Get-DispWidth $s))) }
function Split-Display([string]$s, [int]$w) {
    <# 화면 폭 w로 줄 나누기 (공백 기준, 너무 긴 단어는 글자 단위) #>
    $out = New-Object System.Collections.Generic.List[string]
    $cur = ''
    foreach ($tok in ($s -split ' ')) {
        $try = if ($cur) { "$cur $tok" } else { $tok }
        if ((Get-DispWidth $try) -le $w) { $cur = $try; continue }
        if ($cur) { $out.Add($cur); $cur = '' }
        while ((Get-DispWidth $tok) -gt $w) {
            $piece = ''
            foreach ($ch in $tok.ToCharArray()) { if ((Get-DispWidth ($piece + $ch)) -gt $w) { break }; $piece += $ch }
            $out.Add($piece); $tok = $tok.Substring($piece.Length)
        }
        $cur = $tok
    }
    if ($cur -or $out.Count -eq 0) { $out.Add($cur) }
    $out.ToArray()
}

$TagMap = @{
    ok = @('  OK  ', 'Green'); go = @('  GO  ', 'Green'); pass = @(' PASS ', 'Green')
    nogo = @('NO-GO ', 'Red'); fail = @(' FAIL ', 'Red'); deny = @(' 거부 ', 'Red'); stop = @(' 중단 ', 'Red')
    warn = @(' 주의 ', 'Yellow'); uv = @('미확인', 'Yellow')
    info = @(' 정보 ', 'Cyan'); wait = @(' 대기 ', 'Magenta'); todo = @(' 할일 ', 'Magenta'); next = @(' 다음 ', 'Magenta')
    skip = @(' 생략 ', 'DarkGray'); note = @(' 참고 ', 'DarkGray')
}
function Write-Tag([string]$Kind, [string]$Msg, [string[]]$More = @()) {
    <#  [ 라벨 ] 메시지 — 라벨은 모두 6칸, 추가 줄은 메시지 위치에 맞춰 들여씀 #>
    $t = $TagMap[$Kind]
    Write-Host '  [' -NoNewline; Write-Host $t[0] -ForegroundColor $t[1] -NoNewline; Write-Host "] $Msg"
    foreach ($m in $More) { if ($m) { Write-Host ((' ' * 11) + $m) } }
}
function Write-Step([string]$No, [string]$Title) {
    Write-Host ''
    Write-Host ('=' * $LineW) -ForegroundColor DarkCyan
    Write-Host (' {0}  {1}' -f $No, $Title) -ForegroundColor Cyan
    Write-Host ('=' * $LineW) -ForegroundColor DarkCyan
}
function Write-KV([string]$Key, [string]$Value, [string]$Color = '') {
    Write-Host ('  ' + (Format-Cell $Key 20)) -NoNewline
    if ($Color) { Write-Host $Value -ForegroundColor $Color } else { Write-Host $Value }
}
function Read-Answer([string]$Prompt) {
    Write-Host ''
    Write-Host "  >> $Prompt " -ForegroundColor Yellow -NoNewline
    Read-Host
}
function Write-Table($Rows, [string[]]$Cols) {
    <# 한글 폭을 맞춘 표 (Format-Table은 한글에서 줄이 어긋남) #>
    $w = @{}
    foreach ($c in $Cols) { $w[$c] = Get-DispWidth $c; foreach ($r in $Rows) { $w[$c] = [math]::Max($w[$c], (Get-DispWidth "$($r.$c)")) } }
    Write-Host ('  ' + (($Cols | ForEach-Object { Format-Cell $_ $w[$_] }) -join '  ')) -ForegroundColor Gray
    Write-Host ('  ' + (($Cols | ForEach-Object { '-' * $w[$_] }) -join '  ')) -ForegroundColor DarkGray
    foreach ($r in $Rows) { Write-Host ('  ' + (($Cols | ForEach-Object { Format-Cell "$($r.$_)" $w[$_] }) -join '  ')) }
}

# ================================================================ 시작
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$psyPath = if ($psy) { $psy } else { "$env:LOCALAPPDATA\Programs\PsychoPy\python.exe" }
foreach ($p in @($py, $psyPath)) {
    if (-not (Test-Path $p)) { Write-Tag fail "python 없음: $p"; exit 1 }
}
if (-not $ZipOnly) {
# ---------------------------------------------------------------- 0) 세션 번호 (변경3: 세션마다 seed 다름)
$pnum = if ($Participant -match '(\d+)$') { [int]$Matches[1] } else { -1 }
$prev = @(Get-ChildItem data -Filter "*_main_*_events.json" -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
    $m = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($m.participant -match '(\d+)$' -and [int]$Matches[1] -eq $pnum) {
        $when = if ($_.Name -match '_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})\d{2}_events') { "$($Matches[1])-$($Matches[2])-$($Matches[3]) $($Matches[4]):$($Matches[5])" } else { $_.Name }
        [pscustomobject]@{ 측정 = $when; 세션 = $(if ($m.session) { "$($m.session)" } else { '1(변경3 이전)' }); seed = $m.seed
                           시작블록 = $m.start_block
                           완료 = $(if ($null -eq $m.completed_sequences) { '기록 중/비정상 종료' } else { "$($m.completed_sequences)/$($m.n_sequences)" })
                           중단 = $(if ($m.aborted) { $r = "$($m.stop_reason)"; if ($r.Length -gt 22) { $r = $r.Substring(0, 22) + '…' }; "예 ($r)" } else { '-' }) }
    }
} | Sort-Object 측정)

$modeTxt = if ($Practice) { if ($OneBlock) { '연습(1블록)' } else { '연습' } } else { '본측정' }
$sbIdx = [array]::IndexOf($StimArgs, '--start-block')
$startTxt = if ($sbIdx -ge 0 -and $sbIdx + 1 -lt $StimArgs.Count) { "블록 $($StimArgs[$sbIdx + 1])부터 (이어 하기)" } else { '처음부터' }
Write-Host ''
Write-Host ('=' * $LineW) -ForegroundColor Cyan
Write-Host (" RGB EEG 세션   {0}  |  {1}  |  세션 {2}  |  {3}" -f $Participant, $modeTxt, $(if ($Session -ge 1) { $Session } elseif ($Practice) { 1 } else { '?' }), $startTxt) -ForegroundColor White
Write-Host ('=' * $LineW) -ForegroundColor Cyan
Write-Host '  순서: 1 사전 점검 → 1b Board 녹화 확인 → 2 자극 → 3 QC → 4 압축' -ForegroundColor DarkGray

if ($prev) {
    Write-Host ''
    Write-Host "  참가자 번호 $pnum 의 이전 본측정 기록" -ForegroundColor Cyan
    Write-Table $prev @('측정', '세션', 'seed', '시작블록', '완료', '중단')
}
if (-not $Practice) {
    if ($Session -lt 1) {
        $usedNums = @($prev | ForEach-Object { if ("$($_.세션)" -match '^(\d+)') { [int]$Matches[1] } })
        $next = if ($usedNums) { ($usedNums | Measure-Object -Maximum).Maximum + 1 } else { 1 }
        Write-Host ''
        Write-Tag deny '본측정은 -Session N 이 필요합니다' @('첫 세션 1, 다음 2 … / 이어 하기는 중단된 실행과 같은 번호 (위 기록 참고)')
        Write-Tag next '새 색 순서로 측정:' @(".\run_session.ps1 -Participant $Participant -Session $next")
        exit 1
    }
    $used = @($prev | Where-Object { "$($_.세션)" -eq "$Session" -or ($Session -eq 1 -and "$($_.세션)" -like '1(*') })
    $resume = $StimArgs -contains '--start-block'
    if ($used -and -not $resume) {
        Write-Host ''
        Write-Tag warn "세션 $Session 은 이미 기록 있음 → 같은 색 순서 반복" @("이어 하기라면 -StimArgs '--start-block','N' 추가")
        $ans = Read-Answer '그래도 계속하려면 y'
        if ($ans -ne 'y') { Write-Tag stop '종료'; exit 1 }
    }
}
if ($Session -ge 1) { $StimArgs = @('--session', "$Session") + $StimArgs }

}
if (($NoPrecheck -or $NoBoardRecord) -and -not $Practice) {
    Write-Tag deny '-NoPrecheck/-NoBoardRecord는 -Practice와 함께만' @('본측정은 사전 점검·Board 녹화 확인 필수'); exit 1
}

function Show-Checks([string]$CsvPath) {
    <# xdf_qc checks.csv → 점검 결과 표. FAIL·UNVERIFIED를 먼저, 그다음 PASS. 근거는 화면 폭에 맞춰 줄바꿈 #>
    $rows = @(Import-Csv $CsvPath -Encoding UTF8)
    $order = @{ FAIL = 0; UNVERIFIED = 1; PASS = 2 }
    $rows = @($rows | Sort-Object { if ($order.ContainsKey($_.status)) { $order[$_.status] } else { 3 } })
    $cnt = @{}; foreach ($r in $rows) { $cnt[$r.status] = 1 + [int]$cnt[$r.status] }
    Write-Host ''
    Write-Host '  합계  ' -NoNewline
    foreach ($s in @('FAIL', 'UNVERIFIED', 'PASS')) {
        $col = switch ($s) { 'FAIL' { 'Red' } 'UNVERIFIED' { 'Yellow' } default { 'Green' } }
        Write-Host ("{0} {1}   " -f $s, [int]$cnt[$s]) -ForegroundColor $(if ([int]$cnt[$s]) { $col } else { 'DarkGray' }) -NoNewline
    }
    Write-Host ''
    $cw = 10
    foreach ($r in $rows) { $cw = [math]::Max($cw, (Get-DispWidth $r.check)) }
    $cw = [math]::Min($cw, 28)
    $sw = 10
    $ew = [math]::Max(30, $ConW - 2 - $sw - 2 - $cw - 2)
    $pad = ' ' * (2 + $sw + 2 + $cw + 2)
    Write-Host ''
    Write-Host ('  ' + (Format-Cell '상태' $sw) + '  ' + (Format-Cell '점검 항목' $cw) + '  근거') -ForegroundColor Gray
    Write-Host ('  ' + ('-' * $sw) + '  ' + ('-' * $cw) + '  ' + ('-' * [math]::Min($ew, 40))) -ForegroundColor DarkGray
    $lastStatus = $null
    foreach ($r in $rows) {
        if ($lastStatus -and $r.status -ne $lastStatus) { Write-Host '' }   # 상태가 바뀌면 한 줄 띄움
        $lastStatus = $r.status
        $c = switch ($r.status) { 'FAIL' { 'Red' } 'UNVERIFIED' { 'Yellow' } 'PASS' { 'Green' } default { 'Gray' } }
        $chk = @(Split-Display $r.check $cw)
        $ev = @(Split-Display $r.evidence $ew)
        $n = [math]::Max($chk.Count, $ev.Count)
        for ($i = 0; $i -lt $n; $i++) {
            $st = if ($i -eq 0) { $r.status } else { '' }
            $ck = if ($i -lt $chk.Count) { $chk[$i] } else { '' }
            $e = if ($i -lt $ev.Count) { $ev[$i] } else { '' }
            Write-Host '  ' -NoNewline
            Write-Host (Format-Cell $st $sw) -ForegroundColor $c -NoNewline
            Write-Host ('  ' + (Format-Cell $ck $cw) + '  ') -NoNewline
            Write-Host $e -ForegroundColor $(if ($r.status -eq 'PASS') { 'Gray' } else { 'White' })
        }
    }
}

Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
function New-SessionZip([string]$ZipPath, [string[]]$Files) {
    <# 원본은 그대로 두고 zip 생성. 다른 프로그램이 열고 있는 파일(BrainAccess .db 등)도 공유 읽기로 담음.
       같은 이름 zip이 있으면 덮어쓰지 않음. 반환: 담은 파일 수 #>
    $Files = @($Files | Where-Object { $_ -and (Test-Path $_) })
    if (-not $Files) { Write-Tag skip "담을 파일 없음: $(Split-Path $ZipPath -Leaf)"; return 0 }
    if (Test-Path $ZipPath) { Write-Tag skip "이미 있음(덮어쓰지 않음): $(Split-Path $ZipPath -Leaf)"; return 0 }
    $zs = [IO.File]::Open($ZipPath, 'CreateNew')
    try {
        $zip = New-Object IO.Compression.ZipArchive($zs, [IO.Compression.ZipArchiveMode]::Create)
        foreach ($f in $Files) {
            $entry = $zip.CreateEntry((Split-Path $f -Leaf), [IO.Compression.CompressionLevel]::Optimal)
            $src = [IO.File]::Open($f, 'Open', 'Read', 'ReadWrite')
            $dst = $entry.Open()
            try { $src.CopyTo($dst) } finally { $dst.Dispose(); $src.Dispose() }
        }
        $zip.Dispose()
    } catch {
        $zs.Dispose(); Remove-Item $ZipPath -ErrorAction SilentlyContinue; throw
    }
    $zs.Dispose()
    # 검증: 항목 수·크기가 원본과 같은지
    $chk = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    $bad = @($Files | Where-Object { $n = Split-Path $_ -Leaf; $e = $chk.GetEntry($n); -not $e -or $e.Length -ne (Get-Item $_).Length })
    $chk.Dispose()
    if ($bad) { Write-Tag fail "압축 크기 불일치: $($bad -join ', ')"; return -1 }
    $mb = (Get-Item $ZipPath).Length / 1MB
    Write-Tag ok ("{0}  ({1:N1} MB)" -f (Split-Path $ZipPath -Leaf), $mb) @("담은 파일 $($Files.Count)개: " + (($Files | ForEach-Object { Split-Path $_ -Leaf }) -join ', '))
    return $Files.Count
}

function Get-BoardRecordingFile([string]$Root, [int]$WaitSec = 3) {
    <# BrainAccess Board가 지금 녹화 중인지: Root 아래 .db/.db-wal 중 WaitSec 동안 크기나 수정 시각이 늘어난 파일. 없으면 $null
       (Board는 Record 중에만 .db/.db-wal에 계속 씀. 스트리밍·View만으로는 파일이 커지지 않음) #>
    $snap = @{}
    Get-ChildItem $Root -Recurse -File -Include *.db, *.db-wal -ErrorAction SilentlyContinue |
        ForEach-Object { $snap[$_.FullName] = @($_.Length, $_.LastWriteTimeUtc) }
    Start-Sleep -Seconds $WaitSec
    foreach ($f in Get-ChildItem $Root -Recurse -File -Include *.db, *.db-wal -ErrorAction SilentlyContinue) {
        $old = $snap[$f.FullName]
        if (-not $old -or $f.Length -gt $old[0] -or $f.LastWriteTimeUtc -gt $old[1]) { return $f }
    }
    return $null
}

function Find-BrainAccessDb([datetime]$Start, [datetime]$End, [string]$Root) {
    <# 자극 실행 시간과 가장 많이 겹치는 BrainAccess Board 녹화(.db). 없으면 $null #>
    $best = $null; $bestSec = 0
    foreach ($db in Get-ChildItem $Root -Recurse -Filter *.db -File -ErrorAction SilentlyContinue) {
        $wal = "$($db.FullName)-wal"
        $last = $db.LastWriteTime
        if ((Test-Path $wal) -and (Get-Item $wal).LastWriteTime -gt $last) { $last = (Get-Item $wal).LastWriteTime }
        $s = if ($db.CreationTime -gt $Start) { $db.CreationTime } else { $Start }
        $e = if ($last -lt $End) { $last } else { $End }
        $sec = ($e - $s).TotalSeconds
        if ($sec -gt $bestSec) { $best = $db; $bestSec = $sec }
    }
    if ($best) {
        $cover = 100 * $bestSec / [math]::Max(1, ($End - $Start).TotalSeconds)
        if ($cover -lt 90) {
            Write-Tag warn ("Board 녹화 {0} — 자극 실행 시간의 {1:N0}%만 겹침" -f $best.Name, $cover) @('Board Record 시작/정지 시점 확인')
        } else {
            Write-Tag ok ("Board 녹화 {0} — 자극 실행 시간의 {1:N0}% 겹침" -f $best.Name, $cover)
        }
    }
    return $best
}

if (-not $ZipOnly) {
# ---------------------------------------------------------------- 1) 사전 점검
Write-Step '1/4' '착용 신호 사전 점검'
Write-Host '  참가자는 편히 앉아 가운데를 봅니다 (약 1분)' -ForegroundColor DarkGray
if ($NoPrecheck) {
    Write-Tag skip '-NoPrecheck (연습·장비 미착용 시험)'
} else {
    while ($true) {
        & $py scripts\eeg_precheck.py --once 60
        if ($LASTEXITCODE -eq 0) { break }
        Write-Host ''
        Write-Tag todo '신호 NO-GO → 전극(특히 O1·O2) 재조정  /  배터리 NO-GO → 충전'
        $ans = Read-Answer 'Enter = 다시 점검,  q = 종료'
        if ($ans -eq 'q') { Write-Tag stop '자극 실행 안 함'; exit 1 }
    }
}

# ---------------------------------------------------------------- 1b) BrainAccess Board 녹화 확인
$baRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'BrainAccessData'
Write-Step '1b' 'BrainAccess Board 녹화(Record) 확인'
if ($NoBoardRecord) {
    Write-Tag skip '-NoBoardRecord: Board 녹화 확인 안 함 (연습 전용)'
} else {
    Write-Host "  확인 위치: $baRoot" -ForegroundColor DarkGray
    while ($true) {
        $rec = Get-BoardRecordingFile $baRoot
        if ($rec) { Write-Tag ok "Board 녹화 중: $($rec.Name)"; break }
        Write-Tag nogo 'Board 녹화 파일이 커지지 않음' @("Board 화면 상단이 'NOT RECORDING'이면 왼쪽 메뉴 Record에서 녹화 시작")
        $ans = Read-Answer 'Record 시작 후 Enter = 다시 확인,  q = 종료'
        if ($ans -eq 'q') { Write-Tag stop '자극 실행 안 함'; exit 1 }
    }
}

# ---------------------------------------------------------------- 2) 자극
Write-Step '2/4' '자극 실행'
Write-Tag todo "LabRecorder (바탕 화면 'LabRecorder (RGB EEG)')" @(
    '1) 파일명 확인 (sub-<ID>_ses-main_run-<번호>.xdf, 새 번호)',
    '2) Update   3) EEG · RGB_Markers 체크   4) Start',
    '녹화(kb 증가)가 감지되면 자극 창이 자동으로 열립니다')
$t0 = Get-Date
$stim = @('scripts\stim_rgb.py', '--participant', $Participant)
if ($Practice) { $stim += '--practice' }
if ($OneBlock) { $stim += '--one-block' }
$stim += $StimArgs
& $psyPath @stim

$json = Get-ChildItem data -Filter "${Participant}_*_events.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $t0 -or $_.CreationTime -ge $t0 } |
    Sort-Object CreationTime -Descending | Select-Object -First 1
if (-not $json) {
    Write-Tag stop '이번 실행의 기록 파일 없음 (녹화 대기 중 취소 또는 실행 거부) → QC 생략'
    exit 1
}
$meta = Get-Content $json.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
$csv = $json.FullName -replace '_events\.json$', '_events.csv'

} else {
    # -ZipOnly: 자극 없이 기존 실행의 QC 결과 확인 + 압축
    $json = if ($Events) { Get-Item (Join-Path 'data' (Split-Path $Events -Leaf)) -ErrorAction SilentlyContinue }
            else { Get-ChildItem data -Filter "${Participant}_*_events.json" | Sort-Object CreationTime -Descending | Select-Object -First 1 }
    if (-not $json) { Write-Tag fail "events.json 없음 (참가자 $Participant, -Events $Events)"; exit 1 }
    Write-Tag info "ZipOnly 대상: $($json.Name)"
    $meta = Get-Content $json.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $csv = $json.FullName -replace '_events\.json$', '_events.csv'
}

# ---------------------------------------------------------------- 3) QC
Write-Step '3/4' 'XDF QC'
if (-not $ZipOnly) {
    Write-Tag todo 'LabRecorder Stop  +  BrainAccess Board Record 정지' @('녹화 중인 파일은 QC·압축할 수 없습니다')
    [void](Read-Answer '둘 다 정지했으면 Enter')
}
$xdf = $meta.xdf_file
$qc = 1
$qcDir = $null
if (-not $xdf) {
    Write-Tag uv '녹화 확인 생략 실행이라 XDF 경로 기록 없음 → QC 생략'
} elseif (-not (Test-Path $xdf)) {
    Write-Tag fail "XDF 없음: $xdf"
} else {
    Write-Tag wait "QC 실행 중… $(Split-Path $xdf -Leaf)  (크기에 따라 수십 초)"
    $qcDir = Join-Path (Split-Path (Resolve-Path $xdf).Path) ("qc_" + [IO.Path]::GetFileNameWithoutExtension($xdf))
    $qcOut = & $py scripts\xdf_qc.py $xdf --stim-csv $csv 2>&1 | ForEach-Object { "$_" }
    $qc = $LASTEXITCODE
    $checks = Join-Path $qcDir 'checks.csv'
    if (Test-Path $checks) {
        Show-Checks $checks
        $notes = @($qcOut | Where-Object { $_ -match '^\[참고\]|^PROVISIONAL|^유효 시행 0' })
        if ($notes) {
            Write-Host ''
            foreach ($l in $notes) { Write-Tag note ($l -replace '^\[참고\]\s*', '') }
        }
    } else {
        Write-Tag fail 'QC 결과 표(checks.csv) 없음 — QC 출력 마지막 25줄:'
        $qcOut | Select-Object -Last 25 | ForEach-Object { Write-Host "           $_" }
    }
}

# ---------------------------------------------------------------- 요약
Write-Step '요약' ''
$sess = if ($meta.session) { $meta.session } else { '1' }
$modeK = switch ($meta.mode) { 'main' { '본측정' } 'practice' { '연습' } default { $meta.mode } }
Write-KV '참가자' ("{0}   ({1}, 세션 {2}, seed {3})" -f $meta.participant, $modeK, $sess, $meta.seed)
Write-KV '시작 블록' "$($meta.start_block)"
$full = "$($meta.completed_sequences)" -eq "$($meta.n_sequences)"
Write-KV '완료 시퀀스' "$($meta.completed_sequences) / $($meta.n_sequences)" $(if ($meta.aborted) { 'Yellow' } elseif ($full) { 'Green' } else { '' })
if ($meta.aborted) { Write-KV '중단' "예  ($($meta.stop_reason))" 'Yellow' } else { Write-KV '중단' '없음' }
$drops = [int]$meta.dropped_frames_stim; $clk = [int]$meta.marker_timing.clock_mismatch
Write-KV '드롭 프레임' "$drops  (자극 단계)" $(if ($drops -eq 0) { 'Green' } else { 'Red' })
Write-KV '마커 시각 보정 실패' "$clk" $(if ($clk -eq 0) { 'Green' } else { 'Red' })
Write-KV '자극 기록' "$($json.Name)  /  $(Split-Path $csv -Leaf)"
Write-KV 'XDF' "$(if ($xdf) { Split-Path $xdf -Leaf } else { '없음' })"
$qcTxt = if ($qc -eq 0) { 'GO' } elseif (-not $qcDir) { 'UNVERIFIED' } else { 'NO-GO' }
Write-Host ''
Write-Host '  QC 판정   ' -NoNewline
Write-Host " $qcTxt " -ForegroundColor Black -BackgroundColor $(if ($qc -eq 0) { 'Green' } elseif (-not $qcDir) { 'Yellow' } else { 'Red' }) -NoNewline
Write-Host $(if ($qcDir) { "   상세: $qcDir\report.txt" } else { '' }) -ForegroundColor DarkGray

# ---------------------------------------------------------------- 4) 압축 (원본 유지, 확인 후)
Write-Step '4/4' '압축'
$zipDir = Join-Path $PSScriptRoot "data\$Participant"
$baRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'BrainAccessData'
$tEnd = if ($meta.ended) { [datetime]$meta.ended } else { $json.LastWriteTime }
$db = Find-BrainAccessDb ([datetime]$meta.started) $tEnd $baRoot
Write-Host ''
Write-Host "  저장 위치  $zipDir   (원본은 그대로 둠)" -ForegroundColor DarkGray
Write-Host "  1) $($json.Name -replace '\.json$', '.zip')" -NoNewline
Write-Host "   ← events.csv + events.json + $(if ($xdf) { Split-Path $xdf -Leaf } else { 'XDF 없음' })" -ForegroundColor DarkGray
if ($db) {
    Write-Host "  2) $($db.Name -replace '\.db$', '.zip')" -NoNewline
    Write-Host '   ← Board .db + .db-wal + .db-shm' -ForegroundColor DarkGray
} else {
    Write-Host '  2) Board 녹화 없음 → 생략' -ForegroundColor Yellow
}
$ans = Read-Answer '압축을 진행할까요? (y = 진행 / n = 건너뜀)'
$z1 = 0; $z2 = 0
if ($ans -eq 'y') {
    New-Item -ItemType Directory -Force $zipDir | Out-Null
    $z1 = New-SessionZip (Join-Path $zipDir ($json.Name -replace '\.json$', '.zip')) @($csv, $json.FullName, $(if ($xdf) { (Resolve-Path $xdf -ErrorAction SilentlyContinue).Path }))
    if ($db) {
        $z2 = New-SessionZip (Join-Path $zipDir ($db.Name -replace '\.db$', '.zip')) @($db.FullName, "$($db.FullName)-wal", "$($db.FullName)-shm")
    } else {
        Write-Tag skip "Board 녹화(.db) 없음 — $baRoot 에서 이번 실행 시간과 겹치는 녹화를 찾지 못함 (Board Record를 켰는지 확인)"
    }
    Write-Host ''
    Write-Tag info ("압축 끝: 자극·XDF {0}개, BrainAccess {1}개 파일 → {2}" -f $z1, $z2, $zipDir)
} else {
    Write-Tag skip '압축 건너뜀' @("나중에: .\run_session.ps1 -Participant $Participant -ZipOnly -Events $($json.Name)")
}
Write-Host ''
Write-Host ('=' * $LineW) -ForegroundColor DarkCyan
exit $qc
