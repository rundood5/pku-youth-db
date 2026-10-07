# 把这个网站发布到公网（让别人能打开）

> **本文已按你的账号填写好，可直接照抄命令。**
> 你的 GitHub 账号：`rundood5`
> 建议的仓库名：`pku-youth-db`
> 发布后的网址：**`https://rundood5.github.io/pku-youth-db/`**

网站本身已经是**可直接部署的纯静态站点**：0.97 MB、11 个文件、无外部依赖、不需要后端和数据库。
所以发布这件事只剩下"把 `site/` 这个文件夹放到一个能对外提供访问的地方"。

本文给你三条路，**按推荐顺序排列**。选一条走完即可，都不用备案。

| 方案 | 网址长什么样 | 上线速度 | 国内访问 | 需要什么 |
| --- | --- | --- | --- | --- |
| **① GitHub Pages** | `https://rundood5.github.io/pku-youth-db/` | 约 3–5 分钟 | 一般，偶尔慢 | GitHub 账号（你已有）|
| **② Cloudflare Pages** | `https://pku-youth-db.pages.dev` | 约 3 分钟 | 尚可，通常比 ① 好 | Cloudflare 账号（可绑定 GitHub 一键导入）|
| **③ Vercel** | `https://pku-youth-db.vercel.app` | 约 2 分钟 | 尚可 | Vercel 账号 |

> **关于国内访问**：免费的海外托管都不需要 ICP 备案，代价是国内访问速度不稳定。
> 如果这个站以后要正式对内发布、必须稳定快速，就得走"国内云静态托管 + 已备案域名"
> （阿里云 OSS / 腾讯云 COS + CDN），那一步需要备案，见文末第五节。

---

## 一、准备工作：把项目做成一个 Git 仓库 ✅ 已完成

我已经在本机做完了，无需你再操作：

- `git init -b main` 并完成首次提交（20 个文件，commit `6517c4c`）
- 放好 `.gitignore`：**`demo/` 和 `source/` 里的原始 Word 资料默认不会上传到公网**
- 放好 GitHub Pages 自动发布配置 `.github/workflows/deploy-pages.yml`

如果你希望**原始 Word 资料也一起进仓库**，先删掉 `.gitignore` 里的 `demo/`、`source/` 两行，
再执行 `git add . && git commit -m "加入原始资料"`。

---

## 二、方案① GitHub Pages（推荐：一次配好，以后更新只推代码）

### 第 1 步：在 GitHub 上新建仓库

打开 <https://github.com/new>，填写：

| 字段 | 填什么 |
| --- | --- |
| Repository name | `pku-youth-db` |
| Description | 重要讲话与最新提法数据库（可选）|
| Public / Private | **都可以**（私有仓库部署 Pages 属于付费功能，演示建议选 Public）|
| Add a README file | **不要勾选** |
| Add .gitignore / license | **都不要选** |

点 **Create repository**。

### 第 2 步：在本机推送（在你自己的终端里运行，不在本会话里）

```powershell
cd D:\demo
git remote add origin https://github.com/rundood5/pku-youth-db.git
git push -u origin main
```

第一次推送会弹出浏览器让你登录 GitHub 授权，按提示点一下即可。

### 第 3 步：开启 Pages（关键，只做一次）

推送完成后，打开 <https://github.com/rundood5/pku-youth-db/settings/pages>：

- **Source** 选 **GitHub Actions**（不要选 "Deploy from a branch"）

仓库里已经有 `.github/workflows/deploy-pages.yml`，它会自动把 `site/` 目录发布出去。

### 第 4 步：等 1–2 分钟，拿到网址

打开 <https://github.com/rundood5/pku-youth-db/actions>，
看到 `Deploy site to GitHub Pages` 这次运行变成绿色对勾后，网址就是：

```
https://rundood5.github.io/pku-youth-db/
```

**以后更新内容**：本地重跑 `python tools\extract.py` 和 `python tools\build.py`，然后

```powershell
cd D:\demo
git add .
git commit -m "更新总第23期"
git push
```

网站会自动重新发布，不用再动任何设置。

---

## 三、方案② Cloudflare Pages（国内访问通常更好一些）

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) →
   左侧 **Workers & Pages** → **Create** → **Pages** → **Connect to Git**。
2. 授权并选择仓库 `pku-youth-db`。
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

1. 登录 [vercel.com](https://vercel.com/) → **Add New** → **Project** → 导入仓库 `pku-youth-db`。
2. 配置：

| 配置项 | 填什么 |
| --- | --- |
| Framework Preset | `Other` |
| Root Directory | `site` |
| Build Command | *（留空，或覆盖为 `echo skip`）* |
| Install Command | *（留空，或覆盖为 `echo skip`）* |
| Output Directory | *（留空）* |

3. **Deploy**，得到 `https://pku-youth-db.vercel.app`。

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

已经打好了：**`D:\demo\重要讲话与最新提法数据库-网站.zip`**（0.3 MB）。

因为数据已经内嵌在 `data/db.js` 里，**对方不需要联网、不需要装任何软件、也不需要 Python**，
解压后双击 `index.html` 就能完整浏览。唯一注意：直接双击打开时网址栏是 `file:///...`，这是正常的。

> 提醒：**不要只发 `index.html` 单个文件**——样式、数据在 `assets/` 和 `data/` 里，单独发会白屏。
> 手机浏览器无法直接打开本地 html，要让别人用手机看，只能走第一到第四节的上网方案。

---

## 七、发布前自查清单

我在本机已经验证过下面这些项，你部署后可以按同样方式再确认一次：

- [x] 无绝对路径（`/xxx`）——已实测部署到 `rundood5.github.io/pku-youth-db/` 这种子目录也能正常显示
- [x] 无外部 CDN、字体、图片依赖——断网也能完整显示
- [x] 不需要构建命令、不需要后端与数据库
- [x] 8 个页面均可访问（HTTP 200），带参数的页面（`issue.html?no=13`、`search.html?q=青年`）行为正确
- [x] 已放置 `.nojekyll`，避免 GitHub Pages 的 Jekyll 处理干扰
- [x] 已配置缓存策略，避免更新内容后访问者看到旧数据
- [x] 自定义 404 页面（`404.html`），GitHub Pages 会自动使用
- [x] 已排除 `demo/`、`source/`，内部 Word 资料不会上传到公网

部署完成后，建议用**手机流量（不是 WiFi）**打开一次网址，确认外网访问正常。
