# 字记 · myfont

本地完成 **模板 → 扫描 → 切字 → 矢量轮廓 → Glyphs 源文件 + 预览 OTF**。你负责写字和微调；工程侧负责运行转换。前几个环节通过本机 Web GUI 操作，不使用云端服务。

当前已实现模板编辑/即时预览/下载、照片上传/校正/切字、逐字勾选核对、在线试字和完整 Glyphs 资源包下载。用户提供的第一张手机照片已跑通 56 个真实手写字的转换。Glyphs 原生界面验收仍待完成。

## 进入项目

在仓库根目录（不要进 `web/`）：

```sh
npm run dev
```

打开 [http://127.0.0.1:5173/](http://127.0.0.1:5173/)。这条命令会同时拉起接口和前端。`Ctrl+C` 一起停。新机器先看下面的安装步骤。

## 你现在可以做什么

已生成 [MVP 书写模板](work/assets/templates/mvp/template.pdf)，每字一个方格：提示字和 `U+XXXX` 编码都在格子下面，黑体为 IBM Plex Sans SC。4 页、190 字符：75 汉字、94 ASCII、21 个中文标点/符号。先打印第一页，按正常速度写；无需一次写完全部模板。

- 100% / 实际大小打印；不要“适应页面”。
- 用常用黑笔，在**方格内**写；不用填满，也不用追求工整。
- 英文以两侧小短线为基线参考，不要求贴线。
- 完整拍进四角定位标记和页头二维码。平板扫描也可以；网页可以把手机整页照片裁切、拉平成扫描图，你看过再切字。建议尽量铺平、少反光。
- 写错留着，核对时排除或之后补写；不要涂黑整格。

当前围绕一套字体工程工作。主页按字符管理，字符可以独立存在，也可以有多个字形；不提供多项目或字重切换。

- **字符库**：单个或批量添加字符、自动去重、搜索筛选和批量删除。未设置默认字形时显示浅色占位字，不自动拿其他写法作为封面，也不参与导出。进入字符二级界面后管理不同写法，设置一个默认字形用于预览和导出。
- **生成模板**：从主页进入已有模板，或选中字符直接生成排好字的模板。画布支持继续排版、保存和下载 PDF，可反复使用；字块库与工程字符库共用，添加后跨模板保留，可以重复放入；支持按模板使用情况和正式字形筛选。
- **照片转字符**：上传照片、校正并提取后，结果先留在整理空间。修正对应字符、勾选保留结果，保存后可稍后继续；确认加入时，为已有字符增加字形，或创建新字符，不覆盖已有写法及默认选择。

整理转换结果时可以批量设置汉字等比归一化、缩放和水平／垂直居中；字符二级页面点击「管理」后可多选统一调整大小与位置；单击字形进入独立编辑页。修正默认关闭，原始轮廓和照片保留；保存后应用于预览与导出，已导出的字体需要重新生成。自动归一化只处理汉字，避免放大标点和英文。

删除字形保留字符；删除字符将关联字形移入回收站并取消默认选择。恢复字形会恢复对应字符。每个字符目前仅导出默认写法，其余字形保留在工程中。
字形资产保存在 `work/assets/glyphs/`，选用清单在 `work/state/font.json`。转换记录在 `work/history/`，导出字体在 `work/exports/`。启动时会把旧的 `work/glyphs`、`work/runs`、`work/live` 等目录迁到这一布局，并独立保留字形文件。照片页的“清理全部已完成”会先校验独立资产，再删除转换目录及对应上传照片；字形和字体选择保留。模板和字形都可以先放进回收站，再永久删除文件。待完成转换会保留必要的识别数据。所有数据仅在本机处理。

## 工程操作

以下命令在项目根目录执行。所有输出目录必须是新目录，工具拒绝覆盖已有结果和微调文件。

```sh
# 环境检查
.venv/bin/handfont doctor

# 如需新模板；已有模板在 work/assets/templates/mvp
.venv/bin/handfont template --charset charset/mvp.txt --cell-mm 16 --output work/assets/templates/batch-02

# 扫描转候选；可以只扫描当前已写完的页面
.venv/bin/handfont process --templates work/templates/mvp --output work/runs/batch-01 scans/page-01.png

# 先查看 contact-01.png 和 review.csv，再生成预览和可编辑源文件
.venv/bin/handfont build work/runs/batch-01 --output work/builds/batch-01

# 查看字体结构与实际字符覆盖
.venv/bin/handfont check work/builds/batch-01/Preview.otf
```

多页扫描在 `process` 后列出多个路径。目录名和文件名不参与页面身份判断，程序用二维码匹配模板。默认扫描模式只接受单页 PNG/TIFF；整页照片加 `--photo`，支持 JPEG/PNG/WEBP/HEIC/TIFF。照片须对应带方格的项目模板，无法匹配二维码或完整格框时会拒绝处理。扫描 PDF、无模板笔记仍不支持。

```sh
.venv/bin/handfont process --photo --dpi 300 --templates work/templates/mvp --output work/runs/photo-02 your-photo.jpg
```

照片模式保留原文件，使用格框位置平移局部裁切原点；不会按手写字的包围盒放大或居中。每个字仍用相同物理比例。光照校正不能恢复反光、模糊或严重纸张弯曲丢失的细节。

`process` 默认按整页 Otsu 二值化；如果细笔画丢失，工程侧可用 `--threshold 180` 等值创建另一批候选进行对比。不能从参数名称判断哪个更好，需要看原图。`--dpi 300` 可用于开发快检，真实扫描默认保留 600 dpi 处理。

转换结果：

| 文件 | 用途 |
|---|---|
| `raw/`、页面 manifest、`run.json` | 原扫描副本、字符身份、版本、坐标及参数 |
| 每字 `gray.png` / `binary.png` / `outline.svg` | 原图、描边输入、矢量结果 |
| `contact-*.png` | 提示字与实际笔迹的核对图，检查写错/串格 |
| `review.csv` | `review` 待审核、`blank` 未写、`edge` 笔迹触边 |
| `rewrite.txt` | 自动收集空格/触边字符，可直接作补写字表 |

`review` 只表示机器未发现这两类异常，**不代表字写对或已人工通过**。系统不使用 OCR 猜 Unicode，也不自动删除小点。`blank/edge` 默认不进入字体。对写错但机器未发现的字，在构建时使用 `--exclude '错字'` 排除。

## 在 Glyphs 中微调

1. 打开构建目录中的 `Candidates.glyphs`，可看到单字轮廓及对应背景原图。
2. 首次编辑前，用“另存为”建立自己的工作字体，保留构建目录的候选原件。若移动整个字体工程，请连同 `images/` 一起移动并检查背景图链接；不要只复制一个 `.glyphs` 文件后删除原图片。
3. 微调字形、字宽和标点；在 Glyphs 中导出最终 OTF。**CLI 的 `build` 只编译原始转换候选，不会读取你的 Glyphs 微调结果。**
4. `Preview.otf` 与 `proof.png` 用于快速核对原始转换效果。每个构建有独立内部字体名，避免不同排除列表的预览互相混淆。

可选脚本在 `scripts/glyphs/`。放入 Glyphs 的 Scripts 文件夹（Script 菜单的 Open Scripts Folder），按 Glyphs 的菜单重新加载方式加载：

- **Handfont - 导入候选（保留现有微调）**：当前打开自己的正式工作字体，选择另一个批次的 `Candidates.glyphs`。新增字直接加入，已有字仅增加辅助候选层；重复导入同一批跳过。
- **Handfont - 采用当前候选（保留旧轮廓）**：在 Layers 面板选中 `Handfont candidate…` 图层后执行。仅替换对应字，旧正式轮廓留在 `Handfont previous…` 层。需要恢复时，可从旧图层复制回主图层。

脚本逻辑已用兼容对象模型验证；本机 Glyphs 3.3 的原生界面连接超时，尚未完成应用内运行验证。它们是辅助入口，首次打开候选源文件和预览 OTF 不依赖脚本安装。

## 补写

使用某批 `rewrite.txt` 或自建只含目标字符的文本生成新模板，再扫描、转换到新目录，用上述候选脚本合并。补写必须沿用同一 `--cell-mm`；比例不同的批次会拒绝合并。不自动覆盖旧字，也没有后台同步或自动发布。

## 新机器安装

需要 Python 3.11+、Potrace、Glyphs 3（用于人工微调）。已验证环境为 macOS arm64、Python 3.13、Potrace 1.16。

```sh
brew install potrace
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/handfont doctor
npm run dev
```

模板提示默认使用随包的 IBM Plex Sans SC（黑体，无衬线）。其他系统可通过 `template` 和 `process` 的 `--label-font /path/to/IBMPlexSansSC-Regular.otf` 指定同一字体。首版不承诺所有系统兼容；Glyphs 编辑仍在 macOS。

## 最小验证

```sh
.venv/bin/python -m unittest discover -s tests -v

# 独立演示，目录必须未存在；这些都是模拟笔画
.venv/bin/python scripts/make_demo.py work/demo-new
.venv/bin/handfont process --templates work/demo-new/template --output work/demo-new/run work/demo-new/synthetic-scan.png
.venv/bin/handfont build work/demo-new/run --output work/demo-new/build
```

仅保留 3 个回归场景：坐标/孔洞/字体实际渲染；缺标记拒绝与防覆盖；候选重导入、人工编辑保护及旧轮廓保留。真实笔迹仍需验证细点、断笔、墨迹粗细、字距及混排，不把模拟测试当成质量保证。

暂不做：云端服务、数据库、自动错字识别、照片纠弯、AI 补字、多字形替换、完整字体审计或自动发布。中文保持固定 1000 字宽；ASCII 只建议比例字宽，不缩放轮廓，中文标点暂按全角处理。

- [产品定位：本地制字工具](docs/direction.md)
- [完整架构方案](docs/implementation-plan.md)：后续路线；MVP 实际范围以上文为准。
- [MVP 实现与验证记录](docs/mvp-status.md)
- [原始研究报告](deep-research-report%20%283%29.md)


## MVP 范围与后续规划

第一版专注字符库、照片转换、非破坏字形修正和字体导出。拆笔画已下线，工程实现保存在 `archive/strokes/`，不参与运行或打包；已有草稿与已发布字形保留。

大小修正新增“参考字面适配”：用内置 IBM Plex Sans SC 同字符的最长边确定大小，保持手写轮廓宽高比，支持整体缩放和水平、垂直位移。默认仍保留原稿；旧统一最长边参数兼容。参考字体只提供尺寸，不替换轮廓，不保证不同书写风格都最优。

项目文件导入导出、SVG 等导入入口的范围与验收见 [后续规划](docs/roadmap.md)。

### 通用书写纸与扫描后匹配

模板库固定提供一份不能删除的「通用书写纸」。打印空格、自由书写，扫描切字后再匹配并确认字符。指定字符模板仍由你自己排字、保存和删除；编辑器里不再切换这两种类型。

切字后，系统从已有、未归档的正式字形中按外观相似度推荐最多三个字符。这是本地字形检索，不是 OCR，分数不是识别概率；首次使用或没有参考字形时需手动填写。候选不会自动确认，通用字格必须逐字确认才能入库，改字后需重新确认。未匹配结果可以保存待办，空白格可排除。
