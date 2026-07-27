# Daily Brief · 每日新闻

双语 AI/科技与综合新闻简报网站，每日 7:00（北京时间）自动更新。

## 新闻来源

- **Hacker News** — 技术社区热门
- **TechCrunch** — 全球科技创业
- **Reuters** — 国际综合新闻
- **机器之心** — AI 科技中文资讯

## 本地运行

```bash
pip install -r requirements.txt
python build.py
```

构建产物在 `output/` 目录，直接打开 `output/index.html` 即可预览。

## GitHub Pages 部署

1. Fork 或 push 本仓库到你的 GitHub
2. 仓库 Settings → Pages → 设置 Source 为 **GitHub Actions**
3. 每天 7:00 自动构建部署，也可以在 Actions 页面手动触发

## 自定义

- 修改 `src/fetcher.py` 的 `SOURCES` 字典 增减新闻源
- 修改 `templates/index.html` 调整页面样式
- 修改 `build.py` 的 `CATEGORY_KEYWORDS` 调整分类规则
