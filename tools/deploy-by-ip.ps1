#Requires -Version 5.1
<#
  用 IP 部署「北大青年纵横」网站到 39.107.65.84
  —— 不需要域名、不需要备案、不需要登录阿里云改安全组

  实测：该服务器 TCP 22 与 443 开放，TCP 80 关闭。
  因此本脚本默认把网站放在 **443 端口**上，用自签名证书提供 HTTPS。
  这样无需任何云端配置即可立刻访问。

  用法（在你自己的 PowerShell 窗口里执行，不要在本对话里执行）：
      cd D:\demo
      .\tools\deploy-by-ip.ps1
      按提示输入服务器密码（不回显、不写文件）

  可选参数：
      -HttpsPort 8443     改用别的端口（需先在阿里云安全组放行该端口）
      -SkipCertCheck      跳过证书生成（证书已存在时）

  关于浏览器警告：因为用的是自签名证书（没有域名，无法申请正式证书），
  浏览器首次打开会提示"您的连接不是私密连接"，点"高级 → 继续前往"即可。
  内容传输本身仍是加密的。
#>

[CmdletBinding()]
param(
  [int]$HttpsPort = 443,
  [switch]$SkipCertCheck
)

$ErrorActionPreference = 'Stop'

$Server    = '39.107.65.84'
$User      = 'root'
$Root      = Split-Path $PSScriptRoot -Parent
$LocalSite = Join-Path $Root 'site'
$RemoteDir = '/var/www/pku-youth-db'
$SslDir    = '/etc/nginx/ssl'

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
  $out = & cmd.exe /c "echo $pw| ssh $OPTS $User@$Server `"$Command`"" 2>&1
  if ($LASTEXITCODE -ne 0 -and -not $AllowFail) {
    throw "远程命令失败 (exit $LASTEXITCODE): $Command`n$out"
  }
  return $out
}

Write-Host "`n=== 1/5 服务器环境 ===" -ForegroundColor Cyan
Invoke-Remote 'cat /etc/os-release | grep PRETTY_NAME; uname -m; echo ---; (nginx -v 2>&1 || echo NO_NGINX); echo ---; (ss -lntp 2>/dev/null | grep -E ":(80|443)\b" || echo PORTS_FREE); echo ---; (systemctl is-active firewalld 2>/dev/null; ufw status 2>/dev/null | head -1) ' |
  ForEach-Object { "  $_" }

Write-Host "`n=== 2/5 安装 nginx（如未安装）===" -ForegroundColor Cyan
Invoke-Remote 'if ! command -v nginx >/dev/null 2>&1; then (apt-get update -qq && apt-get install -y -qq nginx) || (yum install -y nginx); fi; nginx -v' |
  ForEach-Object { "  $_" }

Write-Host "`n=== 3/5 生成自签名证书（$SslDir）===" -ForegroundColor Cyan
if ($SkipCertCheck) {
  Write-Host "  已跳过"
} else {
  $subj = "/CN=$Server/O=PKU Youth Database"
  Invoke-Remote "mkdir -p $SslDir; [ -f $SslDir/pku.key ] || openssl req -x509 -nodes -days 825 -newkey rsa:2048 -keyout $SslDir/pku.key -out $SslDir/pku.crt -subj '$subj' -addext 'subjectAltName=IP:$Server' 2>/dev/null; echo '  证书文件:'; ls -1 $SslDir" |
    ForEach-Object { $_ }
}

Write-Host "`n=== 4/5 上传网站文件 ===" -ForegroundColor Cyan
Invoke-Remote "mkdir -p $RemoteDir" | Out-Null
& cmd.exe /c "echo $pw| scp $OPTS -r `"$LocalSite\*`" $User@$Server`:$RemoteDir/"
if ($LASTEXITCODE -ne 0) { throw "上传失败 (exit $LASTEXITCODE)" }
& cmd.exe /c "echo $pw| scp $OPTS `"$LocalSite\.nojekyll`" $User@$Server`:$RemoteDir/.nojekyll" 2>&1 | Out-Null
Invoke-Remote "echo -n '  目录大小: '; du -sh $RemoteDir | cut -f1; echo -n '  文件数: '; find $RemoteDir -type f | wc -l" |
  ForEach-Object { $_ }

Write-Host "`n=== 5/5 写 nginx 配置并启动 ===" -ForegroundColor Cyan
$conf = @"
server {
    listen $HttpsPort ssl default_server;
    listen [::]:$HttpsPort ssl default_server;
    ssl_certificate     $SslDir/pku.crt;
    ssl_certificate_key $SslDir/pku.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
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
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($conf))
Invoke-Remote "echo $b64 | base64 -d > /etc/nginx/conf.d/pku-youth-db.conf; nginx -t" | ForEach-Object { "  $_" }
Invoke-Remote 'systemctl enable nginx >/dev/null 2>&1; systemctl restart nginx; sleep 1; echo -n "  nginx: "; systemctl is-active nginx' |
  ForEach-Object { $_ }

Write-Host "`n=== 服务器本机自检 ===" -ForegroundColor Cyan
Invoke-Remote "for p in / /database.html /leaders.html /search.html /about.html /assets/style.css /data/db.js; do printf '  %-22s %s\n' `"`$p`" `"`$(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1:$HttpsPort`$p)`"; done" |
  ForEach-Object { $_ }

Write-Host "`n=== 从你的电脑测试外网访问（等同于别人来访问）===" -ForegroundColor Cyan
$base = "https://${Server}:$HttpsPort"
if ($HttpsPort -eq 443) { $base = "https://$Server" }
$paths = @('/index.html','/database.html','/leaders.html','/search.html','/issue.html?no=13','/assets/style.css','/assets/app.js','/data/db.js','/assets/pku-logo-white.png','/favicon.png')
$okCount = 0
foreach ($p in $paths) {
  try {
    $r = Invoke-WebRequest -Uri "$base$p" -UseBasicParsing -TimeoutSec 20 -SkipCertificateCheck -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $okCount++ }
    "  {0,-6} {1,-28} {2:N0} bytes" -f $r.StatusCode, $p, $r.RawContentLength
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    "  {0,-6} {1,-28} {2}" -f $(if($code){$code}else{'失败'}), $p, $(if($code){'HTTP 错误'}else{"$($_.Exception.Message)"})
  }
}

Write-Host "`n================ 结果 ================" -ForegroundColor Green
if ($okCount -eq $paths.Count) {
  Write-Host "  部署成功！网站地址：" -ForegroundColor Green
  Write-Host "      $base/" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  把这个地址发给别人即可。浏览器首次打开会提示证书不受信任，" -ForegroundColor Cyan
  Write-Host "  点「高级」→「继续前往」就能正常浏览（因为没有域名，无法申请正式证书）。" -ForegroundColor Cyan
} else {
  Write-Host "  有 $($paths.Count - $okCount) 个文件没取到，可能是安全组未放行 $HttpsPort 端口。" -ForegroundColor Yellow
  Write-Host "  请检查：阿里云控制台 -> ECS -> 该实例 -> 安全组 -> 入方向 是否放行 TCP $HttpsPort" -ForegroundColor Yellow
}
