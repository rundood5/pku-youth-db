# 把这个网站发布到公网（让别人能打开）

网站本身已经是**可直接部署的纯静态站点**：0.97 MB、11 个文件、无外部依赖、不需要后端和数据库。
所以发布这件事只剩下"把 `site/` 这个文件夹放到一个能对外提供访问的地方"。

本文给你三条路，**按推荐顺序排列**。选一条走完即可，都不用备案。

| 方案 | 网址长什么样 | 上线速度 | 国内访问 | 需要什么 |
| --- | --- | --- | --- | --- |
| **① GitHub Pages** | `https://你的用户名.github.io/仓库名/` | 约 3–5 分钟 | 一般，偶尔慢 | GitHub 账号 |
| **② Cloudflare Pages** | `https://仓库名.pages.dev` | 约 3 分钟 | 尚可，通常比 ① 好 | Cloudflare 账号（可绑定 GitHub 一键导入）|
| **③ Vercel** | `https://仓库名.vercel.app` | 约 2 分钟 | 尚可 | Vercel 账号 |

> **关于国内访问**：免费的海外托管都不需要 ICP 备案，代价是国内访问速度不稳定。
> 如果这个站以后要正式对内发布、必须稳定快速，就得走"国内云静态托管 + 已备案域名"
> （阿里云 OSS / 腾讯云 COS + CDN），那一步需要备案，见文末第五节。

---

## 一、准备工作：把项目做成一个 Git 仓库

我已经放好 `.gitignore`（默认不上传体积较大、且属于内部材料的 `source/` 原始 Word 目录）
和 GitHub Pages 的自动发布配置。你只需要在本机执行一次初始化：

```powershell
cd D:\demo
git init -b main
git add .
git commit -m "重要讲话与最新提法数据库 网站"
```

如果你希望**原始 Word 资料也一起进仓库**，先删掉 `.gitignore` 里的 `source/` 这一行再执行上面的命令。

---

## 二、方案① GitHub Pages（推荐，配好后每次更新只推代码）

1. 在 GitHub 上新建一个仓库（Public 或 Private 都可以），
   例如命名 `pku-youth-db`。**不要**勾选 "Add a README"。
2. 在本机把本地仓库关联上去并推送：

```powershell
cd D:\demo
git remote add origin https://github.com/你的用户名/pku-youth-db.git
git push -u origin main
```

3. 打开仓库页面 → **Settings** → 左侧 **Pages** →
   "Build and deployment" 的 **Source** 选 **GitHub Actions**。
   仓库里已经有 `.github/workflows/deploy-pages.yml`，它会自动把 `site/` 目录发布出去。
4. 回到仓库 **Actions** 标签，等 `Deploy site to GitHub Pages` 跑完（约 1–2 分钟），
   网址会显示在这次运行的 `deploy` 步骤里，形如：

```
https://你的用户名.github.io/pku-youth-db/
```

**以后更新内容**：本地重跑 `python tools\extract.py` 和 `python tools\build.py`，
然后 `git add . && git commit -m "更新总第23期" && git push`，网站会自动重新发布。

---

## 三、方案② Cloudflare Pages（国内访问通常更好一些）

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) →
   左侧 **Workers & Pages** → **Create** → **Pages** → **Connect to Git**。
2. 授权并选择你刚推送的仓库。
3. 构建配置这样填（**关键：不需要任何构建命令**）：

| 配置项 | 填什么 |
| --- | --- |
| Framework preset | `None` |
| Build command | *（留空）* |
| Build output directory | `site` |

4. 点 **Save and Deploy**，约 1 分钟后就得到网址：

```
https://pku-youth-db.pages.dev
```

`site/_headers` 已经配好缓存策略（HTML 与 `db.js` 不缓存，避免更新后别人看到旧内容）。

---

## 四、方案③ Vercel

1. 登录 [vercel.com](https://vercel.com/) → **Add New** → **Project** → 导入该仓库。
2. 配置：

| 配置项 | 填什么 |
| --- | --- |
| Framework Preset | `Other` |
| Build Command | *（留空，或覆盖为 `echo skip`）* |
| Output Directory | `site` |
| Install Command | *（留空，或覆盖为 `echo skip`）* |

3. **Deploy**，得到 `https://pku-youth-db.vercel.app`。

> Vercel 有个限制：如果 Output Directory 必须存在构建产物，就用
> "Root Directory" 设为 `site`、Framework 选 `Other`、Build Command 留空的方式部署。

---

## 五、如果以后要正式对内发布（国内稳定访问）

这条路需要 **ICP 备案**（个人或单位主体均可，通常 5–20 个工作日），流程大致是：

1. 在阿里云/腾讯云购买一台最轻量的云服务器（ECS/轻量应用服务器）或开通对象存储 OSS/COS 的静态网站功能；
2. 买一个域名，完成 **ICP 备案**，解析到上面的服务；
3. 把 `site/` 里的全部文件上传到网站根目录即可（本站在子目录下也能正常工作，路径全是相对路径）；
4. 如需 HTTPS，用云厂商的免费证书。

对**演示**而言不必走到这一步；如果只是给评审、答辩、汇报看，方案①②③ 足够。

---

## 六、其他两种"不联网"的分享方式

### 局域网 / 内网演示（同一 WiFi 下别人用手机就能看）

```powershell
# 在 D:\demo 下执行，然后让别人访问 http://你的电脑IP:8123/
python -m http.server 8123 --directory site --bind 0.0.0.0
```

查看你的电脑 IP：`ipconfig`，找"IPv4 地址"（形如 `192.168.1.23`）。
注意：Windows 防火墙可能会弹窗询问是否允许，选"允许"。

### 做成离线压缩包（U 盘拷给别人、双击就能看）

把 `site` 整个文件夹压缩成 zip 发出去即可。因为数据已经内嵌在 `data/db.js` 里，
**对方不需要联网、不需要装任何软件、也不需要 Python**，双击 `index.html` 就能完整浏览。

> 唯一注意：直接双击打开时网址栏是 `file:///...`，这是正常的，所有功能（检索、筛选、翻页）都可用。

---

## 七、发布前自查清单

我在本机已经验证过下面这些项，你部署后可以按同样方式再确认一次：

- [x] 无绝对路径（`/xxx`）——部署到 `用户名.github.io/仓库名/` 这种子目录也能正常显示
- [x] 无外部 CDN、字体、图片依赖——断网也能完整显示
- [x] 不需要构建命令、不需要后端与数据库
- [x] 8 个页面均可访问（HTTP 200），带参数的页面（`issue.html?no=13`、`search.html?q=青年`）行为正确
- [x] 已放置 `.nojekyll`，避免 GitHub Pages 的 Jekyll 处理干扰
- [x] 已配置缓存策略，避免更新内容后访问者看到旧数据
- [x] 自定义 404 页面（`404.html`），GitHub Pages / Cloudflare Pages 会自动使用

部署完成后，建议用**手机流量（不是 WiFi）**打开一次网址，确认外网访问正常。
