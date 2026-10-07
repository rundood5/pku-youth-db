#Requires -Version 5.1
<#
  仅用 IP 部署「北大青年纵横」网站到 39.107.65.84
  —— 不需要域名，不需要备案

  适用场景：先看效果 / 内部演示 / 临时给几个人看

  用法（在你自己的 PowerShell 窗口里执行，不要在本对话里执行）：
      cd D:\demo
      .\tools\deploy-by-ip.ps1
      按提示输入服务器密码（不回显、不写入任何文件）

  做四件事：
    1. 打印服务器环境（系统、nginx 是否已装、80/443 端口占用情况）
    2. 上传 site/ 的 18 个文件到 /var/www/pku-youth-db/
    3. 写好 nginx 配置（独立 conf 文件，不影响服务器上其他站点）
       —— 只监听 80；如果你要顺带开 443（自签名证书），加 -AlsoHttps 参数
    4. 上传一个临时索引页 /ls.txt，把服务器上的文件逐个列出来，
       再直接从你的电脑访问这些地址，确认外网能不能真的打开

  为什么必须你自己执行：本对话所在沙箱禁止子进程使用管道，
  而 Windows 自带 ssh 无法用参数传密码，两者叠加导致无法从会话内登录。
#>

[CmdletBinding()]
param(
  [switch]$AlsoHttps   # 顺带开启 443（自签名证书，浏览器会提示不受信任）
)

$ErrorActionPreference = 'Stop'

$Server    = '39.107.65.84'
$User      = 'root'
$Root      = Split-Path $PSScriptRoot -Parent
$LocalSite = Join-Path $Root 'site'
$RemoteDir = '/var/www/pku-youth-db'

if (-not (Test-Path $LocalSite)) { Write-Host "找不到 $LocalSite" -ForegroundColor Red; exit 1 }

# ---------- 密码 ----------
$pw = $env:SRV_PW
if (-not $pw) {
  $sec = Read-Host -Prompt "请输入 $User@$Server 的密码" -AsSecureString
  $pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
          [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
if (-not $pw) { Write-Host '未提供密码，退出。' -ForegroundColor Red; exit 1 }

$OPTS = @(
  '-o','StrictHostKeyChecking=no',
  '-o','UserKnownHostsFile=NUL',
  '-o','PreferredAuthentications=password',
  '-o','PubkeyAuthentication=no',
  '-o','NumberOfPasswordPrompts=1',
  '-o','ConnectTimeout=15',
  '-o','LogLevel=ERROR'
) -join ' '

function Invoke-Remote {
  param([string]$Command, [switch]$AllowFail)
  # ssh 从 stdin 读密码，必须用 cmd /c 做重定向
  $out = & cmd.exe /c "echo $pw| ssh $OPTS $User@$Server `"$Command`"" 2>&1
  if ($LASTEXITCODE -ne 0 -and -not $AllowFail) {
    throw "远程命令失败 (exit $LASTEXITCODE): $Command`n$out"
  }
  return $out
}

Write-Host "`n=== 1/4 服务器环境 ===" -ForegroundColor Cyan
Invoke-Remote 'cat /etc/os-release | grep PRETTY_NAME; uname -m; df -h / | tail -1; echo ---; (nginx -v 2>&1 || echo NO_NGINX); echo ---; (ss -lntp 2>/dev/null | grep -E ":(80|443)\b" || echo PORTS_80_443_FREE)' |
  ForEach-Object { "  $_" }

Write-Host "`n=== 2/4 安装 nginx（如未安装）===" -ForegroundColor Cyan
Invoke-Remote 'if ! command -v nginx >/dev/null 2>&1; then (apt-get update -qq && apt-get install -y -qq nginx) || (yum install -y nginx); fi; nginx -v' |
  ForEach-Object { "  $_" }

Write-Host "`n=== 3/4 上传网站文件 ===" -ForegroundColor Cyan
Invoke-Remote "mkdir -p $RemoteDir" | Out-Null
& cmd.exe /c "echo $pw| scp $OPTS -r `"$LocalSite\*`" $User@$Server`:$RemoteDir/"
if ($LASTEXITCODE -ne 0) { throw "上传失败 (exit $LASTEXITCODE)" }
# 隐藏文件单独补传
& cmd.exe /c "echo $pw| scp $OPTS `"$LocalSite\.nojekyll`" $User@$Server`:$RemoteDir/.nojekyll" 2>&1 | Out-Null
Invoke-Remote "du -sh $RemoteDir; find $RemoteDir -maxdepth 1 -type f | wc -l" | ForEach-Object { "  $_" }

Write-Host "`n=== 4/4 配置 nginx ===" -ForegroundColor Cyan
$listen = if ($AlsoHttps) { "    listen 443 ssl default_server;`n    listen [::]:443 ssl default_server;`n    ssl_certificate     /etc/nginx/ssl/pku.crt;`n    ssl_certificate_key /etc/nginx/ssl/pku.key;" } else { "" }
$conf = @"
server {
    listen 80 default_server;
    listen [::]:80 default_server;
$listen
    server_name _;
    root $RemoteDir;
    index index.html;
    charset utf-8;
    location / { try_files `$uri `$uri/ =404; }
    error_page 404 /404.html;
    location = /404.html { internal; }
    location ~* \.(html|js|json)`$ { add_header Cache-Control "no-cache"; }
    location ~* \.(css|png|ico|svg)`$ { add_header Cache-Control "public, max-age=604800"; }
    gzip on;
    gzip_types text/html text/css application/javascript application/json image/svg+xml;
}
"@
if ($AlsoHttps) {
  Invoke-Remote 'mkdir -p /etc/nginx/ssl; [ -f /etc/nginx/ssl/pku.key ] || openssl req -x509 -nodes -days 825 -newkey rsa:2048 -keyout /etc/nginx/ssl/pku.key -out /etc/nginx/ssl/pku.crt -subj "/CN=39.107.65.84" 2>/dev/null; ls -1 /etc/nginx/ssl' |
    ForEach-Object { "  证书: $_" }
}
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($conf))
Invoke-Remote "echo $b64 | base64 -d > /etc/nginx/conf.d/pku-youth-db.conf; nginx -t" | ForEach-Object { "  $_" }
Invoke-Remote 'systemctl enable nginx >/dev/null 2>&1; systemctl restart nginx; sleep 1; systemctl is-active nginx' |
  ForEach-Object { "  nginx: $_" }

Write-Host "`n=== 服务器本机自检 ===" -ForegroundColor Cyan
Invoke-Remote 'for p in / /database.html /leaders.html /search.html /about.html /assets/style.css /data/db.js; do printf "  %-22s %s\n" "$p" "$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1$p)"; done' |
  ForEach-Object { $_ }

# ---------- 外网可达性：把文件名列出来，从本机逐个请求 ----------
Write-Host "`n=== 从你的电脑测试外网访问 ===" -ForegroundColor Cyan
$paths = @('/index.html','/database.html','/leaders.html','/search.html','/about.html','/assets/style.css','/assets/app.js','/data/db.js','/assets/pku-logo-white.png')
Invoke-Remote ("printf '%s\n' " + ($paths -join ' ') + " > $RemoteDir/ls.txt") | Out-Null

$scheme = if ($AlsoHttps) { 'https' } else { 'http' }
foreach ($p in $paths) {
  $url = "${scheme}://$Server$p"
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15 -SkipCertificateCheck:$AlsoHttps -ErrorAction Stop
    "  {0,-4} {1,-28} {2} bytes" -f $r.StatusCode, $p, $r.RawContentLength
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    "  {0,-4} {1,-28} {2}" -f $(if($code){$code}else{'超时/拒绝'}), $p, $(if($code){'HTTP 错误'}else{$_.Exception.Message})
  }
}
Invoke-Remote "rm -f $RemoteDir/ls.txt" | Out-Null

Write-Host "`n================ 结果 ================" -ForegroundColor Green
Write-Host "  网站地址: ${scheme}://$Server/" -ForegroundColor Yellow
Write-Host "  （也可以直接用 http://$Server/ 或 https://$Server/）"
Write-Host ""
Write-Host "如果上面全部是 200，就能直接把这个地址发给别人了。" -ForegroundColor Green
Write-Host "如果不是 200，按顺序检查：" -ForegroundColor Yellow
Write-Host "  1. 阿里云控制台 -> ECS -> 该实例 -> 安全组 -> 入方向，放行 TCP 80（和 443）"
Write-Host "  2. 服务器防火墙: firewall-cmd --add-service=http --permanent (或 ufw allow 80)"
Write-Host "  3. 80 端口若是被运营商/云厂商拦截，就用 -AlsoHttps 参数走 443"
Write-Host ""
Write-Host "关于域名：现在用 IP 就能访问，不需要买域名。" -ForegroundColor Cyan
Write-Host "  想让网址好看、或要 HTTPS 可信，才需要买域名 + ICP 备案。" -ForegroundColor Cyan
