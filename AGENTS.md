# 项目规则

- 字记首先是好用的本地制字工具，不是 SaaS、营销页或个人站。改产品时遵循 [docs/direction.md](docs/direction.md)：下一步明确、工作对象占主面积、状态可读。好看和材质为任务让路；不要为作品集另做皮肤。
- 所有 UI 图标必须使用 `uplus-icon`（React 项目使用 `@uplus-icon/react`）。不得使用其他图标库、自绘 SVG、emoji、Unicode 符号，或浏览器原生控件自带的图标（例如 `<details>` / `<summary>` 的展开三角、用 `list-style` 圆点当图标）。折叠、展开、返回、下载等一律用 `@uplus-icon/react`。折叠面板用项目里的 `Disclosure`，不要裸写带默认三角的 `<summary>`。
- 操作按钮不得做成无边框 ghost / `text-button` 或描边空心按钮。删除用实心红色 `danger`。工具条里的「全选」「取消」「完成」用实心底，不要 secondary 描边。
