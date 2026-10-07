#Requires -Version 5.1
<#
  把「北大青年纵横」网站推送到 GitHub，触发 GitHub Pages 自动发布

  用法（必须在 PowerShell 里执行，不是 CMD）：
      cd D:\demo
      .\tools\push-github.ps1

  如果你现在在 CMD（黑窗口，提示符是 C:\...>），先输入 powershell 回车，
  或者直接在开始菜单搜索 "PowerShell" 打开。

  脚本做四件事：
    1. 自动修正代理设置（你的机器有系统代理，但 git 默认不走，这是连不上的原因）
    2. 检查 SSH 与远端配置、本地是否有未推送提交
    3. 推送（会弹出浏览器让你登录 GitHub 授权，只需一次）
    4. 打印后续两步：开启 Pages、等待网址生效

  为什么必须你自己执行：
    · git push 需要 GitHub 账号认证，认证弹窗只能在你本机桌面出现；
    · 本对话所在沙箱禁止子进程使用管道，git 的网络操作在会话内会被中断。
#>

$ErrorActionPreference = 'Stop'

# ---------- 定位仓库根目录 ----------
$Root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $Root '.git'))) {
  Write-Host "在 $Root 下找不到 .git，请确认脚本放在项目的 tools\ 目录里。" -ForegroundColor Red
  exit 1
}
Set-Location $Root

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "  推送到 GitHub 并触发自动部署" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# ---------- 1. 代理设置 ----------
Write-Host "`n[1/4] 检查并修正代理设置" -ForegroundColor Cyan

# 从系统设置里读代理（git 不会自动使用它）
$proxy = $null
try {
  $ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
  if ($ie.ProxyEnable -eq 1 -and $ie.ProxyServer) {
    $srv = $ie.ProxyServer
    if ($srv -notmatch '^https?://') { $srv = "http://$srv" }
    $proxy = $srv
  }
} catch { }

$cur = & git config --get https.proxy
if ($proxy) {
  if ($cur -ne $proxy) {
    & git config https.proxy $proxy
    & git config http.proxy $proxy
    Write-Host "  已为当前仓库设置代理: $proxy" -ForegroundColor Green
  } else {
    Write-Host "  代理已配置: $proxy" -ForegroundColor Green
  }
} else {
  Write-Host "  未检测到系统代理，按直连处理" -ForegroundColor Yellow
}

# 代理对 HTTP/2 支持不佳，这是 fetch/push 报 SSL_ERROR_SYSCALL 的主因
if ((& git config --get http.version) -ne 'HTTP/1.1') {
  & git config http.version HTTP/1.1
  Write-Host "  已设置 http.version=HTTP/1.1（解决 SSL_ERROR_SYSCALL）" -ForegroundColor Green
}
& git config http.postBuffer 524288000

# ---------- 2. 检查状态 ----------
Write-Host "`n[2/4] 检查仓库状态" -ForegroundColor Cyan
$remote = & git remote get-url origin 2>$null
if (-not $remote) {
  Write-Host "  未配置远端 origin。请先执行：" -ForegroundColor Red
  Write-Host "    git remote add origin https://github.com/rundood5/pku-youth-db.git"
  exit 1
}
Write-Host "  远端      : $remote"

$branch = & git branch --show-current
Write-Host "  当前分支  : $branch"

& git fetch origin 2>&1 | Out-Null
$ahead  = (& git rev-list --count "origin/$branch..HEAD" 2>$null)
$behind = (& git rev-list --count "HEAD..origin/$branch" 2>$null)
Write-Host "  待推送    : $ahead 个提交"
Write-Host "  远端领先  : $behind 个提交"

if (-not (& git status --porcelain)) { Write-Host "  工作区    : 干净" -ForegroundColor Green }
else { Write-Host "  工作区    : 有未提交改动（本脚本不会提交它们，只推送已有提交）" -ForegroundColor Yellow }

if ($ahead -eq 0 -and $behind -eq 0) {
  Write-Host "`n  本地与远端完全一致，无需推送。" -ForegroundColor Green
  Write-Host "  如果你还没开启 Pages，请继续第 3 步。" -ForegroundColor Yellow
}

# ---------- 3. 推送 ----------
if ($ahead -gt 0) {
  Write-Host "`n[3/4] 推送 $ahead 个提交（首次会弹出浏览器，请登录 GitHub 并授权）" -ForegroundColor Cyan

  # 允许认证弹窗出现，否则会直接报 could not read Username
  $env:GIT_TERMINAL_PROMPT = '1'
  Remove-Item Env:\GCM_INTERACTIVE -ErrorAction SilentlyContinue

  $ok = $false
  for ($i = 1; $i -le 3; $i++) {
    if ($i -gt 1) { Write-Host "  第 $i 次尝试..." -ForegroundColor Yellow }
    & git push -u origin $branch
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    if ($i -lt 3) { Write-Host "  推送中断，5 秒后重试（代理偶发不稳，重试通常可成功）" -ForegroundColor Yellow; Start-Sleep -Seconds 5 }
  }

  if (-not $ok) {
    Write-Host "`n  推送失败。两种常见原因与处理：" -ForegroundColor Red
    Write-Host "   1) 代理不稳（报 SSL_ERROR_SYSCALL）→ 关掉代理软件后重跑本脚本"
    Write-Host "   2) 认证失败（报 could not read Username / 403）→ 改用令牌方式："
    Write-Host "      · 打开 https://github.com/settings/tokens 新建 Classic token，勾选 repo 权限"
    Write-Host "      · 然后执行（把 TOKEN 换成你的令牌）："
    Write-Host "        git remote set-url origin https://TOKEN@github.com/rundood5/pku-youth-db.git"
    Write-Host "        git push -u origin $branch"
    exit 1
  }
  Write-Host "`n  推送成功 ✓" -ForegroundColor Green
} else {
  Write-Host "`n[3/4] 无需推送，跳过" -ForegroundColor Cyan
}

# ---------- 4. 后续步骤 ----------
Write-Host "`n[4/4] 接下来两步" -ForegroundColor Cyan
Write-Host ""
Write-Host "  第 1 步（只做一次）：开启 Pages" -ForegroundColor Yellow
Write-Host "     打开 https://github.com/rundood5/pku-youth-db/settings/pages"
Write-Host "     把 Source 选为  GitHub Actions"
Write-Host "     ⚠ 不要选 'Deploy from a branch'，否则不会用我们的工作流" -ForegroundColor Red
Write-Host ""
Write-Host "  第 2 步：等 1-2 分钟，查看部署进度" -ForegroundColor Yellow
Write-Host "     https://github.com/rundood5/pku-youth-db/actions"
Write-Host "     看到 'Deploy site to GitHub Pages' 变成绿色对勾即成功"
Write-Host ""
Write-Host "  网站地址将是：" -ForegroundColor Green
Write-Host "     https://rundood5.github.io/pku-youth-db/" -ForegroundColor Yellow
Write-Host ""
Write-Host "  部署完成后可以自检：" -ForegroundColor Cyan
Write-Host "     python tools\verify_live.py"
Write-Host ""
