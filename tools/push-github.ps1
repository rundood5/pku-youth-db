#Requires -Version 5.1
<#
  把「北大青年纵横」推送到 GitHub，触发 GitHub Pages 自动发布

  用法（必须在 PowerShell 里执行，不是 CMD）：
      cd D:\demo
      .\tools\push-github.ps1

  如果当前在 CMD 黑窗口里，先在开始菜单搜索 PowerShell 打开，或输入 powershell 回车。

  脚本流程
    1. 自动探测可用通道：系统代理（若开启）-> 直连，逐个试 git ls-remote
    2. 把选中的通道写入本仓库配置（不影响你的 gitee 项目）
    3. 检查待推送提交数，然后 push（首次会让你登录 GitHub 授权）
    4. 打印后续两步与最终网址

  常见失败与对策（脚本会按情况提示）
    SSL_ERROR_SYSCALL / Connection was reset
        网络对 GitHub 的干扰。打开你的代理软件并开启"系统代理"，再重跑本脚本。
    could not read Username / 403
        没有 GitHub 凭据。用令牌方式（替换 TOKEN）：
            git remote set-url origin https://TOKEN@github.com/rundood5/pku-youth-db.git
            git push -u origin main
        令牌在 https://github.com/settings/tokens 新建 Classic token，勾选 repo 权限。
#>

$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $Root '.git'))) {
  Write-Host "在 $Root 下找不到 .git，请把脚本放在项目的 tools\ 目录里。" -ForegroundColor Red
  exit 1
}
Set-Location $Root

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  推送到 GitHub 并触发自动部署" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$REMOTE = 'https://github.com/rundood5/pku-youth-db.git'

# ---------- 1. 探测可用通道 ----------
Write-Host ""
Write-Host "[1/4] 探测可用网络通道" -ForegroundColor Cyan

$proxy = $null
try {
  $ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
  if ($ie.ProxyEnable -eq 1 -and $ie.ProxyServer) {
    $s = $ie.ProxyServer
    if ($s -notmatch '^https?://') { $s = "http://$s" }
    $proxy = $s
  }
} catch { }

$candidates = @()
if ($proxy) { $candidates += @{ name = "系统代理 $proxy"; cfg = $proxy } }
elseif (Test-NetConnection -ComputerName 127.0.0.1 -Port 17890 -InformationLevel Quiet -WarningAction SilentlyContinue) {
  # 系统代理没开，但本地代理端口在监听，也试一下
  $candidates += @{ name = "本地代理 127.0.0.1:17890（系统代理未开启）"; cfg = 'http://127.0.0.1:17890' }
}
$candidates += @{ name = "直连（不使用代理）"; cfg = '' }

$picked = $null
foreach ($c in $candidates) {
  Write-Host ("  试 {0} ..." -f $c.name) -NoNewline
  if ($c.cfg) {
    $out = & git -c "http.proxy=$($c.cfg)" -c "https.proxy=$($c.cfg)" `
                 -c http.version=HTTP/1.1 ls-remote $REMOTE 2>&1 | Out-String
  } else {
    $out = & git -c http.proxy= -c https.proxy= `
                 -c http.version=HTTP/1.1 ls-remote $REMOTE 2>&1 | Out-String
  }
  if ($LASTEXITCODE -eq 0) { Write-Host " 通了 ✓" -ForegroundColor Green; $picked = $c; break }
  Write-Host " 不通" -ForegroundColor Yellow
}

if (-not $picked) {
  Write-Host ""
  Write-Host "两种通道都连不上 GitHub。请按顺序处理：" -ForegroundColor Red
  Write-Host "  1) 打开你的代理软件，并确保开启「系统代理 / 全局模式」"
  Write-Host "  2) 关掉代理再试一次（有时直连反而通）"
  Write-Host "  3) 换个网络（手机热点）再试"
  Write-Host "  4) 仍然不行：用令牌方式推送（见本脚本头部说明）"
  exit 1
}

# 把选中的通道固化到本仓库
if ($picked.cfg) {
  & git config http.proxy $picked.cfg
  & git config https.proxy $picked.cfg
  Write-Host "  已设置本仓库代理: $($picked.cfg)" -ForegroundColor Green
} else {
  & git config --unset http.proxy 2>$null
  & git config --unset https.proxy 2>$null
  Write-Host "  已清除本仓库代理（走直连）" -ForegroundColor Green
}
& git config http.version HTTP/1.1
& git config http.postBuffer 524288000

# ---------- 2. 检查状态 ----------
Write-Host ""
Write-Host "[2/4] 检查仓库状态" -ForegroundColor Cyan
$branch = & git branch --show-current
Write-Host "  分支      : $branch"
Write-Host "  远端      : $(& git remote get-url origin)"

& git fetch origin 2>&1 | Out-Null
$ahead  = (& git rev-list --count "origin/$branch..HEAD" 2>$null)
$behind = (& git rev-list --count "HEAD..origin/$branch" 2>$null)
Write-Host "  待推送    : $ahead 个提交"
Write-Host "  远端领先  : $behind 个提交"
if (-not (& git status --porcelain)) { Write-Host "  工作区    : 干净 ✓" -ForegroundColor Green }
else { Write-Host "  工作区    : 有未提交改动（本脚本只推送已有提交）" -ForegroundColor Yellow }

# ---------- 3. 推送 ----------
if ($ahead -gt 0) {
  Write-Host ""
  Write-Host "[3/4] 推送 $ahead 个提交（首次会弹出浏览器，请登录 GitHub 并授权）" -ForegroundColor Cyan
  Remove-Item Env:\GCM_INTERACTIVE -ErrorAction SilentlyContinue
  $env:GIT_TERMINAL_PROMPT = '1'

  $ok = $false
  for ($i = 1; $i -le 3; $i++) {
    if ($i -gt 1) { Write-Host "  第 $i 次尝试…" -ForegroundColor Yellow }
    & git push -u origin $branch
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    if ($i -lt 3) { Start-Sleep -Seconds 5 }
  }
  if (-not $ok) {
    Write-Host ""
    Write-Host "推送失败。按报错对照处理：" -ForegroundColor Red
    Write-Host "  SSL_ERROR_SYSCALL / Connection was reset -> 代理不稳，重跑脚本或换网络"
    Write-Host "  could not read Username / 403            -> 用令牌方式推送（见脚本头部）"
    exit 1
  }
  Write-Host "  推送成功 ✓" -ForegroundColor Green
} else {
  Write-Host ""
  Write-Host "[3/4] 无需推送（本地与远端一致）" -ForegroundColor Cyan
}

# ---------- 4. 后续 ----------
Write-Host ""
Write-Host "[4/4] 接下来两步" -ForegroundColor Cyan
Write-Host ""
Write-Host "  第 1 步（只需做一次）：开启 Pages" -ForegroundColor Yellow
Write-Host "     打开 https://github.com/rundood5/pku-youth-db/settings/pages"
Write-Host "     Source 选  GitHub Actions"
Write-Host "     ⚠ 不要选 'Deploy from a branch'" -ForegroundColor Red
Write-Host ""
Write-Host "  第 2 步：等 1-2 分钟看部署进度" -ForegroundColor Yellow
Write-Host "     https://github.com/rundood5/pku-youth-db/actions"
Write-Host "     看到 'Deploy site to GitHub Pages' 变绿勾即成功"
Write-Host ""
Write-Host "  网址：" -ForegroundColor Green
Write-Host "     https://rundood5.github.io/pku-youth-db/" -ForegroundColor Yellow
Write-Host ""
Write-Host "  部署后自检：" -ForegroundColor Cyan
Write-Host "     python tools\verify_live.py"
Write-Host ""
