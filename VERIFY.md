# 如何验证"网站真的发布成功了"

发布这件事有三层，**必须逐层验证**——很多人卡在"以为成功了，其实只是本地好着"。
下面每一层都给你可复制的命令或可点的链接。

---

## 第 0 层：本地是否已经准备好（✅ 我已经替你验过）

```powershell
cd D:\demo
git log --oneline          # 应看到 4 条提交，最新一条含"部署验证脚本"
git status                 # 应显示 working tree clean
git ls-files | Measure-Object -Line   # 应为 24 个文件
python tools\check_workflow.py        # 应输出 [PASS] 工作流配置完整
node tools\verify.js                  # 应输出 全部检查通过 ✓
```

这一层目前**全部通过**，无需你再做。

---

## 第 1 层：代码是否成功推送到 GitHub

**验证位置**：<https://github.com/rundood5/pku-youth-db>

看三件事：

| 检查点 | 通过的标准 |
| --- | --- |
| 仓库里有文件 | 能看到 `site/`、`tools/`、`README.md`、`DEPLOY.md`、`VERIFY.md` |
| 默认分支是 `main` | 页面左上角分支下拉显示 `main` |
| 提交信息对得上 | 点 commits，能看到 4 条提交、最新一条含"部署验证脚本" |

❌ **不通过的表现**：仓库是空的，或只有自动生成的 README。
→ 说明 `git push` 没成功，回到终端重跑 `git push -u origin main` 看报错。

---

## 第 2 层：GitHub Actions 是否部署成功

**验证位置**：<https://github.com/rundood5/pku-youth-db/actions>

| 检查点 | 通过的标准 |
| --- | --- |
| 有运行记录 | 列表里有一条 `Deploy site to GitHub Pages` |
| 图标是绿勾 | ✅ 绿色对勾；黄色圆点是还在跑（等 1–2 分钟）；红色叉是失败 |
| deploy 步骤成功 | 点进那次运行 → 左侧 `deploy` 是绿勾 |

绿勾之后，点这次运行的 **deploy** 步骤，展开会有 `page_url`，就是你的网址。

❌ **常见失败原因**（点红叉能看到日志）：

| 报错关键字 | 原因 | 解决 |
| --- | --- | --- |
| `Get Pages site failed` / `Not Found` | Settings → Pages 的 Source 没选成 GitHub Actions | 去 <https://github.com/rundood5/pku-youth-db/settings/pages> 把 Source 改成 **GitHub Actions** 后重新运行 |
| `Resource not accessible by integration` | 仓库 Settings → Actions → General 里 Workflow permissions 权限不足 | 选 **Read and write permissions** |
| `deployment_branch_policy` / environment 相关 | Pages 环境被限制 | 在 Settings → Environments → github-pages 里放开分支限制 |

---

## 第 3 层：网站是否真的能打开、内容对不对（最关键）

**这一步我可以直接替你验证**——网址上线后告诉我，我用 `web_fetch` 检查公网返回的真实内容。

你也可以自己跑（一条命令检查 6 类问题）：

```powershell
cd D:\demo
python tools\verify_live.py
```

它会检查这些**"返回 200 但其实是坏的"**的情况：

| 检查项 | 为什么重要 |
| --- | --- |
| 7 个页面 + 4 个资源文件是否都取得到 | 缺一个页面就是没部署全 |
| 资源路径是否为相对路径 | 部署在 `/pku-youth-db/` 子目录时，以 `/` 开头会全部 404 |
| `data/db.js` 里是否真有 `DSH_DB` 数据 | 路径写错时 GitHub 会返回一个 404 的 HTML 页面，状态码却是 200，肉眼看不出 |
| 期次/条目/论述数量是否为 20/36/42 | 确认数据完整，不是空壳 |
| 中文是否正常 | 编码没坏 |
| 缓存响应头 | 避免更新后别人看到旧内容 |

**通过的表现**（结尾会打印）：

```
结果：部署成功 ✓
可以把这个网址发给别人了：
   https://rundood5.github.io/pku-youth-db/
```

❌ **失败时会告诉你排查顺序**，不用自己猜。

---

## 第 4 层：人工确认（机器验不了的）

- [ ] **用手机流量（关掉 WiFi）**打开网址 —— 这是唯一能确认"外网真的能访问"的方法
- [ ] 手机上看一眼排版有没有错乱（响应式布局）
- [ ] 随便点几个按钮：进数据库 → 点一期 → 点一条原文链接，确认能跳出去
- [ ] 在检索框输入"青年"，确认有命中结果和高亮

> 关于速度：免费的 GitHub Pages 在国内访问**时快时慢**，这是正常现象，不是部署失败。
> 如果打开明显慢或偶尔打不开，改用 Cloudflare Pages（见 `DEPLOY.md` 第三节），
> 部署同一个仓库，配置只有"Build output directory 填 `site`"这一项。

---

## 一页速查表

| 层 | 在哪看 | 通过标准 |
| --- | --- | --- |
| 0 本地 | `git log` / `git status` | ✅ 已通过（4 条提交、工作区干净） |
| 1 推送 | github.com/rundood5/pku-youth-db | 有 22 个文件、分支是 main |
| 2 构建 | 仓库的 Actions 标签 | 绿勾 + deploy 步骤绿勾 |
| 3 线上内容 | `python tools/verify_live.py` | 打印"部署成功 ✓" |
| 4 真实体验 | 手机流量打开网址 | 能打开、能点、排版正常 |

**最关键的一句话**：只有第 1、2 层都绿了，第 3 层才可能通过。如果 `verify_live.py` 报 404，
九成是第 2 层里 **Pages 的 Source 没选成 GitHub Actions**。
