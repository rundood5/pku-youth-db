#Requires -Version 5.1
<#
  部署「北大青年纵横」网站到公网服务器
  服务器: root@39.107.65.84

  用法（在你自己的 PowerShell 窗口里执行，不要在本对话里执行）：
      cd D:\demo
      .\tools\deploy.ps1
      然后按提示输入服务器密码（不会显示在屏幕上，也不会写进任何文件）

  如果你更习惯用环境变量传入密码，也可以：
      $env:SRV_PW='你的密码'; .\tools\deploy.ps1

  脚本会做四件事：
    1. 连接服务器，检查系统环境（发行版、是否已装 nginx、端口占用）
    2. 上传 site/ 里的全部文件到 /var/www/pku-youth-db/
    3. 安装并配置 nginx 指向该目录
    4. 自检：用 curl 在服务器本地请求页面，确认返回 200

  为什么必须你自己执行：本对话所在的沙箱禁止子进程使用管道，
  Windows 自带的 ssh 又无法用参数传入密码，两者叠加导致无法从这里自动登录。
#>

$ErrorActionPreference = 'Stop'

$Server   = '39.107.65.84'
$User     = 'root'
$LocalSite = Join-Path (Split-Path $PSScriptRoot -Parent) 'site'
$RemoteDir = '/var/www/pku-youth-db'

# ---------- 取密码 ----------
$pw = $env:SRV_PW
if (-not $pw) {
  $sec = Read-Host -Prompt "请输入 $User@$Server 的密码" -AsSecureString
  $pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
          [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
if (-not $pw) { Write-Host "未提供密码，退出。" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $LocalSite)) { Write-Host "找不到 $LocalSite" -ForegroundColor Red; exit 1 }

$SSH_OPTS = @(
  '-o','StrictHostKeyChecking=no',
  '-o','UserKnownHostsFile=NUL',
  '-o','PreferredAuthentications=password',
  '-o','PubkeyAuthentication=no',
  '-o','NumberOfPasswordPrompts=1',
  '-o','ConnectTimeout=15',
  '-o','LogLevel=ERROR'
)

function Invoke-Remote {
  param([string]$Command)
  # ssh 从 stdin 读密码，因此必须用 cmd /c 重定向，不能走 PowerShell 管道
  $line = "echo $pw| ssh $($SSH_OPTS -join ' ') $User@$Server `"$Command`""
  $out = & cmd.exe /c $line 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "远程命令失败 (exit $LASTEXITCODE): $Command`n$out"
  }
  return $out
}

Write-Host "`n=== 1/4 环境检查 ===" -ForegroundColor Cyan
$info = Invoke-Remote 'cat /etc/os-release | head -2; echo ---; uname -m; echo ---; df -h / | tail -1; echo ---; (nginx -v 2>&1 || echo NO_NGINX); echo ---; (ss -lntp 2>/dev/null | grep -E ":(80|443) " || echo PORTS_FREE)'
$info | ForEach-Object { "  $_" }

Write-Host "`n=== 2/4 安装 nginx（若未安装）===" -ForegroundColor Cyan
Invoke-Remote 'if ! command -v nginx >/dev/null 2>&1; then (apt-get update -qq && apt-get install -y -qq nginx) || (yum install -y nginx) ; fi; nginx -v' |
  ForEach-Object { "  $_" }

Write-Host "`n=== 3/4 上传网站文件 ===" -ForegroundColor Cyan
Invoke-Remote "mkdir -p $RemoteDir" | Out-Null
# scp 递归上传 site 目录内容
$scpLine = "echo $pw| scp $($SSH_OPTS -join ' ') -r `"$LocalSite\*`" $User@$Server`:$RemoteDir/"
& cmd.exe /c $scpLine
if ($LASTEXITCODE -ne 0) { throw "上传失败 (exit $LASTEXITCODE)" }
# .nojekyll 是隐藏文件，通配符可能漏掉，单独补传
& cmd.exe /c "echo $pw| scp $($SSH_OPTS -join ' ') `"$LocalSite\.nojekyll`" $User@$Server`:$RemoteDir/.nojekyll" 2>&1 | Out-Null
Write-Host "  已上传到 $RemoteDir"
Invoke-Remote "ls $RemoteDir | head -20; echo ...; du -sh $RemoteDir" | ForEach-Object { "  $_" }

Write-Host "`n=== 4/4 配置 nginx 并启动 ===" -ForegroundColor Cyan
$conf = @'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/pku-youth-db;
    index index.html;
    charset utf-8;
    location / {
        try_files $uri $uri/ =404;
    }
    error_page 404 /404.html;
    location = /404.html { internal; }
    # HTML 与数据文件不缓存，避免更新后看到旧内容
    location ~* \.(html|js|json)$ { add_header Cache-Control "no-cache"; }
    location ~* \.(css|png|jpg|svg|ico)$ { add_header Cache-Control "public, max-age=604800"; }
    gzip on;
    gzip_types text/html text/css application/javascript application/json image/svg+xml;
}
'@
$confB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($conf))
Invoke-Remote "echo $confB64 | base64 -d > /etc/nginx/conf.d/pku-youth-db.conf; nginx -t" | ForEach-Object { "  $_" }
Invoke-Remote 'systemctl enable nginx >/dev/null 2>&1; systemctl restart nginx; sleep 1; systemctl is-active nginx' | ForEach-Object { "  nginx 状态: $_" }

Write-Host "`n=== 服务器本机自检 ===" -ForegroundColor Cyan
$check = Invoke-Remote 'for p in / /database.html /leaders.html /search.html /about.html /assets/style.css /data/db.js; do printf "  %-22s %s\n" "$p" "$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1$p)"; done'
$check | ForEach-Object { $_ }

Write-Host "`n完成。现在从你的电脑访问：" -ForegroundColor Green
Write-Host "  http://39.107.65.84/" -ForegroundColor Yellow
Write-Host "`n如果从外网打不开，请按顺序检查：" -ForegroundColor Yellow
Write-Host "  1. 阿里云控制台 -> 该实例 -> 安全组，放行 TCP 80（当前检测到 80 端口是关闭的）"
Write-Host "  2. 服务器上的 firewalld/ufw 是否放行 80"
Write-Host "  3. 中国大陆服务器未备案时，阿里云通常屏蔽 80 端口，需完成 ICP 备案后才能用域名访问"
