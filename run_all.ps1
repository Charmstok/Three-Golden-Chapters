param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$InputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 一键运行全流程:
# - 第一阶段: EPUB -> 章节 JSONL(仅提取前三章)
# - 第二阶段: 章节 JSONL -> 大模型分析 JSON
# - 第三阶段: 分析 JSON -> Excel 报告

$Root = $PSScriptRoot
Set-Location $Root

# 如果缺少 llm.json, 但存在 llm.example.json, 则自动复制一份作为起点(仍需要你手动填写 API Key 等配置).
if (-not (Test-Path -LiteralPath "llm.json") -and (Test-Path -LiteralPath "llm.example.json")) {
  Copy-Item -LiteralPath "llm.example.json" -Destination "llm.json" -ErrorAction Stop
  Write-Host "[提示] 未找到 llm.json, 已从 llm.example.json 复制生成, 请检查并完善 provider/profile 等配置."
}

function Resolve-Input([string]$p) {
  $p = $p.Trim()
  if (($p.StartsWith('"') -and $p.EndsWith('"')) -or ($p.StartsWith("'") -and $p.EndsWith("'"))) {
    $p = $p.Substring(1, $p.Length - 2).Trim()
  }

  # 1) 传入的是 .epub 路径
  if ($p.ToLower().EndsWith(".epub")) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($p)
    return @{ Kind = "epub"; EpubPath = $p; NovelDir = (Join-Path "book" $name) }
  }

  # 2) 传入的是一个已存在的目录(例如 book/书名)
  if (Test-Path -LiteralPath $p -PathType Container) {
    return @{ Kind = "dir"; NovelDir = $p }
  }

  # 3) 传入的是书名(默认到 book/书名 目录)
  $candDir = Join-Path "book" $p
  if (Test-Path -LiteralPath $candDir -PathType Container) {
    return @{ Kind = "dir"; NovelDir = $candDir }
  }

  # 4) 传入的是书名, 且 book/书名.epub 存在
  $candEpub = Join-Path "book" ($p + ".epub")
  if (Test-Path -LiteralPath $candEpub -PathType Leaf) {
    return @{ Kind = "epub"; EpubPath = $candEpub; NovelDir = (Join-Path "book" $p) }
  }

  throw "输入不合法: $p`n请传入: book\书名.epub 或 book\书名 或 书名"
}

function Invoke-Python([string[]]$PyArgs) {
  & python @PyArgs
  if ($LASTEXITCODE -ne 0) {
    throw "python 执行失败(exit=$LASTEXITCODE): python $($PyArgs -join ' ')"
  }
}

$resolved = Resolve-Input $InputPath
$novelDir = $resolved.NovelDir

if ($resolved.Kind -eq "epub") {
  Write-Host "[第一阶段] 提取前三章: $($resolved.EpubPath)"
  Invoke-Python @("phase1_extract\extract_three_chapters.py", $resolved.EpubPath)
}

Write-Host "[第二阶段] 生成分析: $novelDir"
Invoke-Python @("phase2_analysis\run_phase2.py", $novelDir)

Write-Host "[第三阶段] 导出 Excel: $novelDir"
Invoke-Python @("phase3_excel\run_phase3.py", $novelDir)

Write-Host "[完成] 三个阶段均已完成."
