# 基于真实日常笔迹的中英文字体数字化：以 Glyphs 3 为核心的可扩展生产系统研究

## Executive Summary 与关键结论

你的项目与通常所谓的“设计一款手写字体”有一个根本区别：**源数据不是“为了字体而写出来的漂亮字形”，而是你原本就存在的日常 handwriting；字体工程的任务，是尽量少地改变它。** 这一点会反过来改变模板设计、图像处理、坐标映射、矢量化、Glyphs 内部编辑规范，甚至字符集扩充策略。

我的核心结论是：

> **最推荐的系统不是“扫描 → 自动识别每个字的 bounding box → 放大居中 → 生成字体”，而是“先建立统一的纸面坐标系，再把纸面坐标稳定映射到字体坐标系；字形本身不做逐字归一化”。**

也就是说，你特别提出的：

**纸面统一坐标 → Glyphs 统一坐标**

而不是：

**每字 bbox → 单独 fit → 单独居中**

不仅合理，而且在“个人笔迹保真”这一目标下，我认为应当成为整个 pipeline 的首要设计原则。

近年的一个实际中文研究项目 InkFontify 很有启发性：它已经做出了“生成中文书写模板 → QR 识别 → OpenCV 校正 → 自动切字 → SVG → FontForge → OpenType contextual alternates”的完整原型，并让 20 名参与者每人书写约 4,800 字。它还发现同一字符多个真实版本确实能显著增强“像真实手写”的感知。citeturn21view0 但这个项目为了排版整齐，会计算每个字的 center of mass 并重新对齐，因为作者认为不居中会造成排版“zigzag”。citeturn22view2 **这恰恰是你的项目应该有意识地与之分叉的地方**：他们优化的是“看起来舒服的人类手写字体”，你追求的是“尽可能忠实地数字化自己的书写行为”。

另一个极有价值的实际 precedent 是开源项目 **wefont**。它已经实现了中文模板生成、打印、扫描、二维码识别、OpenCV/Potrace/FontForge 处理、6763 字级模板、自定义语料字表，以及最重要的 **patch workflow：只重新生成写坏字符的模板，再替换原字体对应字符**。citeturn10view0turn12search0 它已经停止维护并且不是 Glyphs-centered，但它几乎直接验证了你设想的工程结构是可行的。

因此，我推荐的技术架构是：

**Python manifest / OpenCV / Potrace 等负责纸面世界，Glyphs 3 负责字体世界，中间通过一个严格保存坐标的 SVG + PNG 接口连接。**

```text
Unicode 字表 / manifest
        ↓
Python 生成 A4 模板 + page manifest
        ↓
打印 → 正常速度书写
        ↓
600 dpi 扫描（手机作为 fallback）
        ↓
OpenCV
ArUco/QR → 页面校正 → 固定坐标切格
        ↓
每字保留两个版本
raw grayscale PNG + trace binary PNG
        ↓
Potrace 为默认批量矢量化
        ↓
坐标变换到固定 1000-unit writing box
        ↓
uni4E2D.svg + uni4E2D.png
        ↓
Glyphs Python Script
自动建 glyph → 设置 Unicode/width
→ 导入 SVG → 挂原始 PNG
→ 设置 status/tag/color/note
        ↓
Glyphs 中只做 Technical Cleanup
        ↓
测试 → OTF/TTF
        ↓
rewrite list → 自动生成 patch template
```

Glyphs 3 在这里绝不只是“最后导出 OTF 的软件”。它应该是**字符数据库、最终轮廓 source of truth、OpenType 工程、状态管理、人工 QA、patch 合并、排版测试和导出中心**。Glyphs 官方 API 确实提供批量建 glyph、访问 layer、background image、宽度、颜色、note、路径方向修正、重叠处理、特性更新和字体导出所需的基础能力。citeturn1view1turn6view1turn6view3

本方案以 **Glyphs 3.3** 为目标版本，API 与工作流均以 3.3 的实际兼容性为准。导入、保存、重新打开和导出需在 Glyphs 3.3 内验证。

最重要的原则可以浓缩成一句：

> **统一“测量系统”，不要统一“字”。**

统一的是 UPM、纸面坐标、页面校准、Unicode、CJK advance、扫描和状态管理；应保留的是你的字的真实大小、重心、偏移、宽窄、斜度、笔画粗细和结构变化。

## 现有成熟工作流、真实案例与工具生态

**英文个人 handwriting font** 已经有很成熟的“template → handwritten cells → scan/photo → extract → font”消费级工作流。Calligraphr 是最典型例子：官方流程就是下载模板、打印、用笔填写、确保模板边缘定位标志仍在图像里，再扫描/拍摄上传；它还允许后续替换字符和给一个字符增加多个版本。citeturn8search6turn8search0 Calligraphr 对高频 Latin 字母建议准备多个 variants，以降低机械重复感；官方教程尤其建议常见字母准备更多版本。citeturn8search14

这说明英文 handwriting font 的工业问题早已不是“能不能做”，而是**多大程度上愿意为了字体排版而规范原书写**。大多数消费工具优化的是方便、视觉一致性和快速成品，因此不能自动假设它们保留了你所关心的绝对字面大小和位置。

实际个人 Glyphs 项目也存在。2025 年 Glyphs Forum 就有用户明确表示，他们在做“自己的 handwriting font”，目标是让数字笔记和自己手写的 revision notes 几乎无法区分，并在 Glyphs 中处理多套字形、spacing 和 kerning。citeturn20search22 另一个公开个人案例采用 Illustrator 处理字形，再在 Glyphs 中赋予字符、处理标点、spacing 与 kerning。citeturn20search29 这些案例证明 Glyphs 作为个人 handwriting font 的最终编辑环境是成熟用法，但公开案例通常字符规模较小，自动化程度也远低于你的中文项目。

中文方面，现成方案比 Latin 少得多，但有两个非常关键的成熟 precedent。

**wefont** 是目前与你的设想最接近的开源案例之一。它自称“中文个人手写字体制作工具”，以 Python、OpenCV、Potrace、QR、FontForge 等组成完整生产链，可以生成 1000、2000、6763 字等模板，也可以从自定义文本语料生成字符清单；README 直接提供“写坏几个字 → 生成只含这些字的模板 → `patch_my_font.sh` 替换”的流程。citeturn10view0 项目已在 2023 年归档，因此更适合当作**架构参考和代码矿藏**，而不应直接成为新工程的长期核心。

更近的 **InkFontify** 论文在 2026 年展示了实际 4,808 个繁体中文字符的模板生产。模板程序可选择 8、10、12 mm 格子和不同辅助网格，在页底放置 QR；OpenCV 用 QR 做旋转校正和 page number 识别，然后检测格子并逐格裁切。citeturn21view0turn22view0turn22view1 最终字符图片转 SVG，再由 FontForge 创建字体和 contextual substitutions。citeturn22view2

它尤其给你的项目提供了两个重要证据。

第一，它明确报告：**随着用户不断写模板，“handwriting tends to improve with practice”**，以至于作者故意把高频字符放到后面，以获得“更 refined”的最终字形。citeturn21view0 这对你来说其实是一条警告：填写数千格模板本身会改变书写状态，因此不能把“认真填模板的字”未经验证地等同于“日常自然字迹”。

第二，它为了输出阅读舒适而统一 center of mass。citeturn22view2 这说明**批量个人字体系统确实会面临“忠实位置”与“排版整齐”之间的冲突**。你的项目应明确选择前者，至少在 source master 中如此。

### 各工具在你的系统里应该承担什么角色

| 工具 | 适合承担的角色 | 不建议承担的角色 |
|---|---|---|
| **Glyphs 3** | 字符库、Unicode、最终轮廓、原图参考、状态管理、人工清理、OpenType、测试、导出、patch 合并 | A4 页面识别、大规模透视矫正、图像 segmentation |
| **OpenCV** | ArUco/QR、homography、页面校正、裁切、threshold、connected components、QA | 直接作为字体轮廓编辑器 |
| **Potrace** | 可重复、CLI 化的二值字迹 outline tracing | centerline handwriting model |
| **ImageMagick** | 批量格式转换、快速 crop/resize/灰度化、命令行 QA | 复杂页面结构识别 |
| **Illustrator Image Trace** | 困难 glyph 的交互式 trace 对照和救援 | 6000 字的核心可复现 pipeline |
| **Inkscape** | 免费的 SVG 检查、手工 trace/转换辅助 | 主批处理数据库 |
| **FontForge** | 对照实现、历史开源方案、Potrace autotrace、字体检查 | 你的最终 source of truth |
| **Calligraphr** | Latin PoC、研究模板/alternates 思路 | 大规模中文、绝对坐标保真 |
| **Fontself** | 已经在 Illustrator/iPad 得到 artwork 时快速做小字体 | 扫描数千中文字的核心系统 |

FontForge 的脚本接口中确实有 `AutoTrace()`，可调用 Potrace/autotrace 处理背景图；这正是为什么许多自动字体生成项目喜欢选择它。citeturn8search4turn8search7 但对你而言，它的价值更多是作为 **reference implementation**：wefont 和 InkFontify 已证明这种方法可行，而最终字体工程可以搬到 Glyphs。

Potrace 本身是典型的 **black-region outline tracer**：它把黑白 bitmap 转成 SVG、PDF、EPS 等平滑路径，并明确适用于 scanned handwritten material。citeturn12search3turn12search6 因而很适合你的批处理，但它并不是“理解笔画”的系统。

Adobe Illustrator Image Trace 在当前版本里提供 Paths、Corners、Noise 等参数，可以在“紧贴原像素”和“更少节点、更平滑”之间交互调节，Adobe 也明确指出刷写/笔迹类 artwork 往往需要在 threshold、noise 与 path smoothness 之间折中。citeturn19search0turn19search4 它非常适合 PoC 阶段做 **Potrace 的质量对照组**，但不适合当 6000 字 pipeline 中的不可追踪手工步骤。

在这次检索中，我**没有找到一个目前仍活跃、成熟、直接完成“中文模板扫描 → 自动切字 → 绝对坐标矢量化 → Glyphs 3 source”这一整条链的开源项目**。最接近的是 wefont 和 InkFontify，但两者最终使用 FontForge，且 InkFontify 还会逐字重心归一。因此最合理的工程策略不是继续寻找“一个万能项目”，而是：

> **借 wefont / InkFontify 的 template + segmentation 思想，自己写非常薄的一层 Glyphs importer。**

这是本项目最值得自行开发的部分。

### 字符集不要从“GB2312 全集”开始

你的内部 canonical charset 应始终是 **Unicode code point list**，而不是“某个编码标准的槽位”。

对于简体中文，现代而实用的扩充里程碑比“一上来 GB2312 6763 字”更适合用《通用规范汉字表》。教育部公布的主表有 8105 字，其中一级 3500 字，二级 3000 字，一二级合计 6500，三级另有 1605 字。一级定位就是常用字集。citeturn17search0turn17search20

因此我推荐：

```text
个人语料 Top 100
→ 个人语料 Top 1000
→ 2500 左右的个人+通用集合
→ 通用规范汉字一级 3500
→ 一级+二级 6500
→ GB2312 6763 compatibility profile（若有需要）
→ 通用规范汉字 8105 / 更大的自定义 Unicode 集
```

GB2312 的价值是兼容性与历史生态，而不是“现代个人字体的最佳字符优先级”。wefont 提供 6763 字规模模板，说明它适合作为一个成熟 milestone，但不必让它决定前 2500 个字写什么。citeturn10view0

更不建议把“支持 GB18030”理解成“我要把 GB18030 所涉及的一切全都手写”。GB18030 是编码与交换标准，不是合理的个人手写 acquisition list；Unicode 本身的 CJK repertoire 也已经远远超过日常现代汉语需要的字符范围。当前 Unicode 17.0 的官方 code charts继续包含多个 CJK 扩展区。citeturn17search8turn17search1

真正适合你的 Phase 1 字表，应由：

**你的邮件、笔记、日记、文档、聊天、专业词汇的字符频率**

加上

**现代通用字 profile**

共同决定。

## Glyphs 3 作为生产核心：字符、导入、状态和自动化

Glyphs 对这个项目最大的价值并不是它会画 Bézier curve，而是它已经拥有一个完整的 **glyph-oriented object model**。

### Unicode 与 glyph naming

Glyphs 官方文档明确说明，可以在 Add Glyphs 中批量输入 glyph names、字符、Unicode-style 名称和范围。citeturn2view2 对没有常规 Adobe glyph name 的字符，Glyphs 使用：

- BMP：`uni` + 四位十六进制，例如 `uni5B57`
- BMP 以外：`u` + 五或六位十六进制，例如 `u20547`

这是官方推荐兼容生产命名逻辑的一部分。citeturn2view3

因此：

```text
uni4E2D.png
uni4E2D.trace.png
uni4E2D.svg
```

作为中文 pipeline 的 stable file ID **非常合适**。

但建议将“文件 ID”和“Glyphs 内部 nice glyph name”分开：

```csv
unicode,glyph_name,file_id,char
4E2D,uni4E2D,uni4E2D,中
0041,A,uni0041,A
0061,a,uni0061,a
0030,zero,uni0030,0
```

中文 BMP 字通常二者相同；Latin 则让 Glyphs 继续使用 `A`、`a`、`zero`、`comma` 等正常 glyph names，而外部文件系统统一按 Unicode 编号。这可以让 pipeline 的文件命名完全机械化，同时不破坏 Glyphs 原有的 naming / OpenType 工作习惯。Glyphs 会依据 glyph name 和 Unicode 维护其字符属性。citeturn2view3

### 最可靠的批量导入方式不是“人工拖文件”，而是 Glyphs Python API

Glyphs Forum 已有实际脚本用于：

```python
layer.backgroundImage = GSBackgroundImage(path)
```

然后按 `glyph.unicode` 从目录自动匹配图片。Glyphs 开发者还展示了遍历整个 font、按 Unicode 拼出文件名并批量设置 background image 的模式。citeturn7view2

论坛中已有 `dyyybek/Glyphs-Scripts` 的 **Import Images by Unicode Code Point** 脚本，它能够从文件名建立/匹配 glyph 并把图片加入当前 master。citeturn7view2

官方 Python API 更进一步提供 `GSBackgroundImage` 的：

- path
- position
- scale
- rotation
- crop
- alpha
- transform

等属性。citeturn6view1

因此完全可以实现：

```text
processed/glyphs/uni4E2D.png
             ↓
Glyphs importer
             ↓
glyph = uni4E2D
layer.backgroundImage = source PNG
```

这非常重要，因为它使 **原始扫描证据和最终 vector 同时存在于 Glyphs 工作现场**。

这里要特别区分两个 Glyphs 概念：

**Background layer** 是一个 layer 的备用矢量层，可以用于保存旧 outline、raw trace 或备份；Glyphs 官方 handbook 明确把它描述为临时存储、比较和 backup 的地方。citeturn2view5

**Background image / image** 则是挂在 layer 上的扫描图。API 中就是 `GSLayer.backgroundImage`。citeturn6view1

对你的项目，我建议形成一个非常清晰的三层 provenance：

```text
GSLayer.backgroundImage
    = 对应单字的 rectified grayscale PNG

GSLayer.background
    = 第一次自动 trace 出来的 raw vector

GSLayer foreground
    = 当前经过 technical cleanup 的生产轮廓
```

这比把扫描原图删掉再“凭感觉修曲线”可靠得多。

### SVG 是最适合自动化的中间矢量格式

Glyphs Forum 中已经有程序化的 SVG outline 导入调用：

```python
masterLayer.importOutlinesFromURL_scale_error_(svgURL, 1, None)
```

证明 Glyphs 3 可以脚本化把 SVG outline 导入 layer。citeturn7view0

不过同一个讨论也反映了一个与你极其相关的问题：**SVG 的 width、height、viewBox 和 Glyphs 的 import scaling 可能产生意外缩放。**citeturn7view0

因此我不建议做：

```text
Potrace 输出任意尺寸 SVG
→ Glyphs “看起来差不多”导入
```

而应该建立一个严格接口：

```text
vectors/raw/uni4E2D.svg

SVG viewBox 已经是你的 canonical font coordinate
例如 0 0 1000 1000

↓ Glyphs import

脚本检查导入后的 reference coordinates
↓
通过才进入 review 状态
```

换句话说，**坐标变换必须在进入 Glyphs 之前就已经确定，Glyphs importer 不应该再“fit glyph”。**

至于 EPS/PDF：本次研究没有找到 Glyphs 3 官方 API 中比 SVG 更明确、更适合稳定批量自动导入的 EPS/PDF workflow。既然 Potrace 可以直接输出 SVG，而模板 PDF 是纸张输出格式，因此最稳妥的工程约定是：

```text
PDF = template / print artifact
PNG/TIFF = raster source
SVG = pipeline vector interchange
Glyphs = font source
OTF/TTF = build artifact
```

不要让 EPS/PDF 成为单字生产链的中间格式。

### Glyphs 内部状态管理

Glyphs 本身已经有足够多的 metadata 可组合成轻量生产管理系统。

官方 handbook 说明 **glyph/layer colors 只用于组织，不影响导出**，而 Smart Filters 可以按这些属性筛选。citeturn1view0 Handbook 还支持 tags，并可在 Smart Filters 等场景中使用。citeturn1view0 Python API 则提供 glyph 的 `color`、`note`、`export`、master compatibility 等属性。citeturn1view1

我的建议是**状态语义用 tag，颜色只是视觉提示**：

| tag | 含义 |
|---|---|
| `hw:unprocessed` | 没有 trace |
| `hw:trace-issue` | 自动 trace 异常 |
| `hw:review` | 有轮廓，待人工看 |
| `hw:clean` | technical cleanup 完成 |
| `hw:verified` | 与扫描原图核对完成 |
| `hw:rewrite` | 不应修 vector，应该重写 |
| `hw:patched` | 后续补写替换过 |

颜色可以对应这些状态，但不要把 color index 本身当数据库。

权威状态仍应保存在外部 `manifest.csv/json`。Glyphs 中的信息是 UI 工作镜像。原因很简单：外部 manifest 才能记录：

```text
scan page
page revision
cell coordinate
write session
threshold
vectorizer version
vectorizer parameters
source image hash
patch revision
```

这些东西塞进 glyph note 会迅速失控。

### Glyphs Python 自动化覆盖面

以下全部适合脚本化，而且官方 API 已经具备基本对象和路径操作能力。citeturn1view1turn6view1turn6view3

| 工作 | 推荐自动化程度 |
|---|---:|
| 从 manifest 批量建立 glyph | 100% |
| 设置 Unicode / glyph name | 100% |
| 设置 CJK width=1000 | 100% |
| 挂 source PNG | 100% |
| 导入对应 SVG | 100% |
| 设置状态/tag/color/note | 100% |
| 检查 empty glyph | 100% |
| 找缺字 | 100% |
| 找 duplicate Unicode | 100% |
| 输出 `rewrite.txt` | 100% |
| raw trace → background backup | 100% |
| correct path direction | 可批量 |
| remove obvious overlap | 可批量但要审慎 |
| 简化节点 | 自动建议，人工抽查 |
| 改重心/大小/倾斜 | **禁止自动化** |

Glyphs API 提供 `correctPathDirection()`、`removeOverlap()`、坐标 rounding、extreme nodes 等路径操作，因此 technical cleanup 可以部分脚本化。citeturn6view3turn6view5

Glyphs 的插件/脚本系统本身就是官方支持的扩展路线，当前要求 Python 3，脚本可以快速 reload，插件 SDK 也是开放的。citeturn3view2

所以不需要先写一个庞大的 Glyphs plugin。最合理的是从：

```text
scripts/glyphs/
    create_glyphs.py
    import_sources.py
    import_vectors.py
    status_report.py
    mark_rewrite.py
    check_missing.py
    build_test_tab.py
```

这些小脚本开始。

## 从真实 handwriting 到单字图：采集、模板、扫描和绝对坐标

这里是整个项目最容易“技术正确但目标失败”的地方。

### 在正式模板之前先采集 natural handwriting

我非常建议在任何模板出现以前，先保存一组自然书写 baseline：

```text
日常笔记 5–10 页
中文连续文字
英文连续文字
中英混写
数字、日期、网址、括号、标点
真正平时使用的纸和笔
```

这是方法学建议，而不是字体规范。

原因是 InkFontify 已经观察到，在连续填写数千字符的过程中，参与者的书写会因为练习而“improve”，项目甚至利用这种变化故意调整字符顺序。citeturn21view0 对你的目标来说，这说明“填模板”本身是一种实验干扰。

因此 natural samples 的作用不是直接覆盖所有字符，而是建立一个 **reference dataset**：

你平时的“口”到底多大？

你平时的“一”到底多宽？

你的“了”到底平均偏多少？

你英文 `a` 是一种还是两种？

你的 baseline 真的是直的吗？

你的中英文在同一行时实际相对高度是什么？

后续模板字如果显著偏离这些 reference，应优先判断“我是不是因为认真填格子而改变了字”，而不是马上导入字体。

### 中文与英文不要共用一种模板

中文适合 **cell-based acquisition**。

英文更适合 **baseline-based acquisition + isolated coverage 的混合模式**。

我的首版推荐如下：

| 项目 | 中文 | English |
|---|---|---|
| 基本单位 | 固定 writing square | 连续 baseline strip + isolated slots |
| 主要参考线 | 外框即可 | baseline 必需 |
| center line | 默认无 | 无 |
| 九宫格/十字 | 默认无 | 不适用 |
| prompt | 格外上方 | 行上方/左侧 |
| x-height | 不适用 | 可淡显示，但不要要求“贴线” |
| ascender/descender | 不适用 | 可淡显示 |
| 目的 | 保留字面大小/重心 | 保留 baseline、比例、自然节奏 |

InkFontify 本身允许“无辅助线 / 四格 / 九格”模式，说明网格密度完全可以作为可变模板参数。citeturn21view0 对你的目标，我会从 **none 或非常弱的外框** 开始，而不是九宫格。

原因是十字中心线、米字格、九宫格实际上都在告诉写字者：

> “请把这个字认真地摆在正确位置。”

而你并不想得到这个行为。

### 推荐 A4 中文模板

推荐 PoC 首先测试：

**20 mm 左右的 writing cell，约每页 70–90 字。**

wefont 默认模板参数里已经存在 20 的 cell-size 级别设置，并用于大规模中文个人字体 workflow。citeturn10view0 InkFontify 为提高 4,808 字的书写密度使用 8/10/12 mm 格子；这说明更小尺寸可以工作，但它的目标更偏向生产效率。citeturn21view0

你的目标是保真，因此我会宁愿牺牲纸张数量。

20 mm 在 600 dpi 下约有：

\[
20 / 25.4 \times 600 \approx 472
\]

像素宽度。

这给中性笔边缘、细小点、短撇等留下很充足的采样空间。

但这里要区分两个框：

```text
cell / crop box
┌──────────────────────┐
│  prompt: 中 U+4E2D   │
│   ┌──────────────┐   │
│   │ writing box  │   │
│   │              │   │
│   │    你写的字  │   │
│   │              │   │
│   └──────────────┘   │
└──────────────────────┘
```

**prompt 不要在 writing box 内。**

否则后处理必须从你的黑色笔迹中判断哪个黑色像素是 prompt，很容易误删。

writing box 本身也不建议画重黑框。优先采用：

- 很淡的外围线；
- 或只画四个小角；
- 内部无交叉线；
- prompt 在上方。

如果后续发现你根本不需要看到外框，可以进一步用“角标”替代完整方框。

### ArUco、QR 和页面识别

InkFontify 已实际证明单个 QR 可以同时用于 page ID 和扫描旋转校正。citeturn22view1 OpenCV 官方的 `QRCodeDetector` 也能检测二维码区域并解码内容。citeturn14search1

但如果希望同时支持 **手机拍摄产生的透视变形**，我更推荐：

```text
左上：ArUco ID 10
右上：ArUco ID 11

         writing grid

左下：ArUco ID 12
右下：ArUco ID 13

底边：QR = project/template/page/revision
```

ArUco 官方文档说明其黑色边框用于快速检测，内部编码提供 ID 以及错误检测/纠正；OpenCV 将其定位为快速、稳健、简单的 fiducial system。citeturn15search0turn15search8

四角 ArUco 给你四组已知纸面坐标，从而直接得到 page homography：

```text
camera/scanner coordinates
           ↓
4-corner correspondence
           ↓
getPerspectiveTransform / homography
           ↓
canonical A4 page coordinates
```

QR 则只负责 metadata。

这样页面识别根本不需要依赖“找表格线”。

这是一个非常重要的优化：

> **只要模板几何已知，就不应该每次重新“猜格子在哪里”。**

InkFontify 是检测 grid 再裁切；citeturn22view1 你的新系统可以更稳：

```text
识别 page
→ 几何矫正到 canonical A4
→ 读取该 page manifest
→ cell 17 永远按固定坐标裁
```

这能避免中文“回、国、口”等方形结构被误识别成格子边框的问题；InkFontify 自己就专门提到这一检测难点。citeturn21view0

### 扫描仪优先，手机作为 fallback

推荐 acquisition master：

```text
flatbed scanner
600 dpi
8-bit grayscale 或 24-bit color
PNG/TIFF lossless
100% physical scale
```

保留 color master 有一个额外好处：以后若改用淡蓝/淡灰模板线，可以通过颜色更容易分离。

300 dpi 也完全能够做 font source，但 600 dpi 给中性笔边缘和后续 threshold 更多余量。对 A4 而言文件虽然明显变大，但对个人字体工程仍是容易管理的规模。

手机适合补写 patch，不适合优先成为数千字符 acquisition source。手机会多出：

- perspective；
- lens distortion；
- uneven lighting；
- shadow；
- JPEG sharpening；
- camera noise。

不过有四角 fiducials 和 homography 之后，它可以成为可靠的 secondary route。OpenCV 的 ArUco 和透视变换功能正适合这一环节。citeturn15search0turn14search3

### 你提出的固定 paper → font mapping，我建议明确写进项目规范

假设校正后的单个 writing box 的像素坐标为：

```text
left   = x0
right  = x1
top    = y0
bottom = y1
```

希望它对应 font 中固定的：

```text
X = 0 … 1000
Y = 0 … 1000
```

那么每个原始墨迹点直接映射为：

\[
X=1000\frac{x-x_0}{x_1-x_0}
\]

\[
Y=1000\frac{y_1-y}{y_1-y_0}
\]

注意 Y 反转，因为 raster/SVG 与字体坐标通常方向不同。

最关键的是：

> **`x0,x1,y0,y1` 来自模板 cell，不来自 ink bounding box。**

所以：

小“口”：

```text
原来只占 writing box 中央 40%
→ 导入后继续只占 em 的约 40%
```

宽“一”：

```text
原来横跨 writing box 85%
→ 导入后继续约 850 units 宽
```

偏左“了”：

```text
原来重心在 x=420
→ 导入后仍在 x≈420
```

**不允许随后执行：**

```text
Fit to 900
Center horizontally
Center vertically
Normalize sidebearings from bbox
```

Glyphs 本身甚至提供 CJK Grid / CJK Guide 这样的虚拟字身视觉辅助，说明以固定 CJK body 管理中文字形本来就是它支持的工作方式之一。citeturn2view4

### 但固定坐标也有一个需要认真控制的副作用

它会忠实保留：

**你的真实位置习惯**

也会忠实保留：

**你因为“填格子”而产生的随机摆位误差。**

二者不是一回事。

因此不应该通过逐字居中解决，而应该从 acquisition 上解决：

1. 先有 natural handwriting reference。
2. 格子不要强迫居中。
3. 正常速度写。
4. 一次不要写过多。
5. 不满意时不要在 vector 里“摆正”，标记 rewrite。
6. 对 20–30 个代表字在不同日期重复采集，比较模板写法与 natural sample。

另外，只允许进行**整页或整次 session 的全局校正**。

例如发现打印机整页缩了 1.2%，可以全页 correction。

发现 scanner 整页偏 0.5°，可以整页 correction。

但：

```text
这个字偏左 → 移右 37 units
那个字小 → 放大 18%
```

就已经跨入了 design modification。

## 图像处理、矢量化与“只做 Technical Cleanup”的边界

普通黑色中性笔是这个项目的好消息：它比毛笔、铅笔、水彩笔容易自动化得多。

### 原始图像首先必须“不可变”

推荐严格分层：

```text
scans/raw/
    2026-09-xx_p001.tif

processed/pages/
    2026-09-xx_p001_rectified.png

processed/glyphs/grayscale/
    uni4E2D.png

processed/glyphs/binary/
    uni4E2D.png
```

`scans/raw` 永远不覆盖。

任何 threshold、去噪、形态学处理都必须可以从 raw 重算。

这样几年以后如果你发现“原来 threshold 太重，把我所有笔尖 terminal 都削平了”，你还可以重新生产，而不是重新写 6000 字。

### 推荐页面处理顺序

```text
raw color/gray scan
↓
ArUco + QR detection
↓
homography / rotate / crop page
↓
可选 illumination correction
↓
按 page manifest 固定坐标切 cell
↓
去除已知模板区域
↓
grayscale
↓
threshold
↓
very light component cleanup
↓
binary image for tracing
```

OpenCV 官方提供 adaptive threshold、perspective transformation、morphological processing 等基础图像操作，非常适合把这一步做成可重放脚本。citeturn14search3turn14search5

ImageMagick 则很适合外围工程：格式转换、crop、resize、depth/colorspace 处理都有成熟 CLI。citeturn15search6turn15search18

### Threshold：扫描仪与手机不要用同一策略

对平整 scanner：

**优先全页/单 session 的 global threshold 或 Otsu 类方法。**

对手机不均匀照明：

**才优先 adaptive threshold / background normalization。**

不要一开始就每字自动求一个完全不同的阈值，否则你会无意中把真实“这个字写得比较轻/比较重”的差异归一化掉。

更合理的数据模型是：

```text
session default threshold = T

个别异常 glyph:
uni4E2D threshold_override = T2
```

并把 override 写回 manifest。

### Denoise 和 morphology 应该非常保守

对于真实 handwriting，很多传统“clean image”操作其实会把你最关心的东西删掉。

比如：

- 很小的点可能是标点，不是 noise；
- 很短的笔画可能是你的真实写法；
- 两笔接近的 gap 可能是你的习惯；
- pen terminal 的毛边可能形成真实轮廓的一部分。

所以 connected-component removal 应按照**物理尺寸**判断，而不是简单说“少于 20 像素就删除”。

如果项目从 600 dpi 改成 300 dpi，20 pixels 已经不是同一个物理尺寸。

Morphological opening / closing 尤其不要作为全字默认“美化”步骤。它们适合处理明确的扫描 artifact，而不是让笔迹“更圆滑”。

### 抗锯齿与笔压如何保留

建议：

**grayscale source 保留；trace input 不保留。**

Potrace 的正常工作输入是 B/W region，所以 trace 时需要二值版本。citeturn12search3turn12search6

但不要因此删掉 grayscale。

普通单色 OTF/TTF 的字形最终是 vector filled outline，它无法像原始扫描那样保留每一点 ink density。你真正能够保留的是：

- 笔迹外形；
- 笔宽变化；
- 墨团；
- 收笔形状；
- 局部 taper；
- 笔画相接关系。

如果以后真的希望保留纸墨 texture / grayscale，那已经进入 OpenType-SVG/color-font/bitmap glyph 的另一类项目，不应污染第一阶段。

### 普通中性笔 handwriting：我推荐 outline trace，而不是 centerline

这是一个重要结论。

对你的目标，**直接 outline tracing 是第一选择。**

原因不是 Potrace “最先进”，而是信息论上更符合你的 source：

你的中性笔写在纸上的东西本身就是一个**有面积的墨迹 footprint**。

假设真实墨迹是：

```text
██████
  ████
   ███
```

outline trace 保存的是这个实际 footprint。

而 centerline 会把它压缩成：

```text
 ─────
```

然后还必须人为决定：

```text
stroke width = ?
cap style = ?
join style = ?
variable width = ?
```

也就是说，centerline → stroke expansion 会**主动重新制造一套你原纸面上没有明确给出的设计参数**。

Glyphs 确实支持 open path/stroke 并能 expand outline，甚至可以调整 stroke width、height、angle 等属性。citeturn3view1 所以 centerline 模型在技术上完全可做，但更适合：

- monoline 字体设计；
- 极低节点数的工程；
- 需要可编辑 stroke model；
- 想“重建笔画系统”。

它不应成为你的“忠实扫描 archive”主路线。

### 矢量化工具比较

| 方法 | 保真 | 节点/曲线 | 批量性 | 适合你的角色 |
|---|---:|---:|---:|---|
| **Potrace** | 高，强依赖 threshold | 通常较好，可调 | **极强** | **默认 production tracer** |
| Illustrator Image Trace | 高，可交互调 | 调节能力强 | 中/低 | 困难字对照与救援 |
| Glyphs Trace Image | 好 | 适合人工观察 | 低/中 | PoC/单字 fallback |
| Inkscape Trace Bitmap | 好 | 可人工调 | 中/低 | 免费 GUI 对照 |
| OpenCV `findContours` | 像素位置非常可控 | 原始轮廓需自行 curve fitting | **极强** | QA/特殊算法，不建议首版 |
| Centerline/skeleton | 外轮廓保真较差 | 很少 | 可高 | 第二实验路线 |
| 人工描 Bézier | 取决于操作者 | 最整洁 | 极低 | 只适合极少数异常字 |

Glyphs 用户的实际经验是其 **Trace Image “quite okay / really good”**，但对于几百字以上，论坛建议直接用 Python 处理导入和批量流程。citeturn19search2 这非常符合本项目定位：Glyphs Trace Image 是优质的 **comparison/fallback tool**，不是页面级 factory。

Potrace 应成为首版 production baseline，因为：

```text
deterministic
CLI
可记录参数
可批量
SVG output
容易重新生产
```

而 Illustrator 更适合选 20–30 个代表字对照。Adobe 当前 Image Trace 的 Paths / Corners / Noise / Threshold 正好可以帮助你判断 Potrace 是否把某类 pen edge 处理得太生硬。citeturn19search0turn19search4

### 不要以“节点越少越专业”为清理目标

对个人 handwriting 来说，节点数是成本指标，不是美学目标。

建议把自动 simplification 变成一个可测试的操作：

```text
raw vector
↓ simplify
↓
重新 rasterize 到 canonical resolution
↓
与原 binary mask 比较
```

只要 simplification 造成明显轮廓移动，就拒绝。

这样你的人工原则就不再是：

> “这条曲线看起来更漂亮了。”

而是：

> “这个改动减少了技术冗余，但没有可感知地改变源笔迹。”

### Technical Cleanup 与 Design Modification 必须制度化分开

**允许大量进行的 Technical Cleanup：**

| 操作 | 原则 |
|---|---|
| 删除扫描灰尘 | 源图可证明不是墨迹 |
| 删除模板残留 | 明确来自模板 |
| 修复 threshold 导致的假断裂 | grayscale source 明确显示原来连续 |
| 关闭错误 open contour | 技术修复 |
| 修正 contour direction | 技术修复 |
| 去除 duplicate nodes | 技术修复 |
| 删除明显自交/错误轮廓 | 技术修复 |
| 合理减少冗余节点 | 必须通过 raster comparison |
| 清理误识别 holes | 对照扫描 |
| overlap / winding | 为字体有效性服务 |

Glyphs API 已提供 path-direction、overlap 等相关工具，因此这一部分很适合自动检测与半自动修复。citeturn6view3turn6view5

**原则上禁止的 Design Modification：**

```text
“这个字有点歪” → 旋正
“口太小” → 放大
“了偏左” → 居中
“这一横短了” → 拉长
“这个字看着不平衡” → 调重心
“同一批字高度不齐” → 全部 fit 到 900
“英文 a 有点低” → 抬上 baseline
```

如果你确实认为一个字是**那次写坏了**，正确操作不是设计它，而是：

```text
status = hw:rewrite
→ patch template
→ 重新自然写一次
```

这条规范会是整个项目能否保持初心的关键。

## 中英文排版、advance、alternates 与真实变化

### 中文：固定 advance width，与固定 outline size 是两回事

我建议 CJK ideographs：

**advance width = 1000 units**

而**实际字迹 footprint 不固定**。

这是最适合你目标的组合：

```text
glyph body
0                              1000
│--------------------------------│

小“口”
          ┌──────┐
          │  口  │
          └──────┘

宽“一”
    ──────────────────────────
```

这意味着排版仍然保持 CJK 全角节奏，而你个人的“这个字写得小”仍然是 outline 内部特征。

绝对不要因为“口”只宽 400 units 就把它的 advance width 自动变成 500。

否则你保存的不再是 handwriting 的内部结构，而是把“字写得小”错误翻译成“下一个字提前出现”。

### 字身与 baseline 不必假装中文没有垂直度量

Glyphs master 本身有 ascender、cap height、x-height、descender 等 metrics 属性。citeturn1view1 中英文同一个 font 最终必须共用一个字体坐标系统，所以不能分别建立两个互不相干的 vertical universe。

我不建议在研究开始前硬规定：

```text
CJK = y 0…1000
Latin ascender = 800
Latin descender = -200
```

然后再强迫你的字去适应数字。

更忠实的办法是利用你最初的 natural mixed-writing samples：

1. 测出你自然中英混写时，Latin baseline 相对于中文 body 的位置。
2. 测出真实 lowercase x-height。
3. 测出 ascender/descender 范围。
4. 再确定 common master coordinates。
5. 一旦 Phase 0 锁定，就不再逐字改变。

例如最后可能得到：

```text
CJK virtual body ≈ -100 … 900
Latin baseline = 0
x-height ≈ 你实际测出的值
ascender ≈ 你实际测出的值
descender ≈ 你实际测出的值
```

具体数值应由你自己的样本决定，而不是照抄一个“标准手写体”。

### 英文不要使用 CJK 式一字一方格 normalize

Latin 最大的差别是 **advance width 本来就是语言的一部分**。

`i`

和

`m`

显然不应该占相同宽度。

所以 Latin 应保持：

- shared baseline；
- shared vertical paper mapping；
- proportional advance；
- natural sidebearings；
- 必要的 kerning。

Glyphs API 支持读取和设置 kerning pair，也提供 x-height、ascender、descender 等 master metrics。citeturn1view1

但对于“真实 handwriting”，不建议一开始让 auto-spacing algorithm 从 bbox 推出所有 widths。

更好的数据来源是：

**连续真实书写。**

### 英文采集应是“连续文本 + 字符模板”的混合

只写：

```text
a b c d e f ...
```

会得到一种“alphabet mode handwriting”。

你平时写：

```text
I need to send the file tomorrow.
```

时的 `t`、`e`、`r` 可能完全不同。

所以最好的 Phase 0 Latin acquisition 是双轨：

**coverage sheet**

保证：

```text
A–Z
a–z
0–9
punctuation
symbols
```

都至少有 source。

同时增加 **natural text sheets**：

```text
pangrams
日常英文句子
你实际会写的内容
数字/日期/email/URL
```

从连续文本里观察或提取：

- natural `a/e/t/r/s` forms；
- 字母实际宽度；
- word spacing；
- baseline drift；
- joining behavior；
- punctuation position。

如果你真实英文 handwriting 本身有连接笔画，Phase 1 不必为了“做出连笔字体”而强行建复杂 contextual joining。第一版可以接受 base glyph reproduction 不完全重现连接关系；真实连接可以以后作为 ligatures/contextual forms 增强。

### Alternates 应明确放到第二阶段

这点你的判断完全正确。

InkFontify 的实验是很有力的证据：同一个实际 handwriting font，开启多个真实 glyph variants 的版本在“像真实手写”评分和 forced-choice 中都优于没有 variants 的版本；开启 variation 的结果甚至与真实 handwriting 样本在该实验的 post-hoc comparison 中没有显著差异。citeturn21view0

但第一版先把：

```text
1 Unicode → 1 real glyph
```

做好，比一开始维护 `的.ss01`、`的.ss02` 重要得多。

Glyphs 对 `.ss01` 至 `.ss20` 有标准 naming convention。citeturn3view4 高级 contextual alternates 则有专门的 Glyphs 官方教程，目标场景正是“handwritten font with loads of alternates”。citeturn20search1 `calt` 本身不能像某些自动 feature 一样简单自动生成，通常需要写 OpenType feature code。citeturn3view3

还要特别注意：

> **OpenType 没有真正的随机数发生器。**

Glyphs Forum 对此有很明确的讨论：“there’s no random”；所谓随机 handwriting alternates 实际是利用 context、class 和 substitution pattern 做出 pseudo-random / cycling 效果。citeturn20search13

mekkablue/Glyphs-Scripts 也有 **Create Pseudorandom Calt Feature** 这类现成脚本可作为 Phase 3 起点。citeturn20search2

中文不建议一开始给 6000 个字各写三版。更现实的是：

```text
Latin:
a/e/t/s/r/n 等高频字母 3–4 versions

Chinese:
个人语料 Top 50–200 个高频字
如 的 一 是 我 了 不 在 人 有 …
各 2–3 versions
```

InkFontify 也采取类似的非均匀策略：主字表一套，而只让高频 520 字、再其中高频 200 字获得额外版本。citeturn21view0

## 可实际执行的 Glyphs-centered 工程 Pipeline

我建议 source font 采用 `.glyphspackage` 而不是单一巨大的 `.glyphs` 文件进行 Git 管理。Glyphs 3 用户已经在实际使用 `.glyphspackage` + Git workflow；论坛也明确把它作为便于 version control 的文件包格式使用。citeturn18search36turn18search32 对几千中文字而言，按 glyph 拆分的 package 比单大文本文件更容易 diff、merge 和审计。

可以同时定期保存 `.glyphs` snapshot。

### 推荐工程目录

```text
MyHandwriting/
│
├── font/
│   ├── MyHandwriting.glyphspackage/
│   └── snapshots/
│
├── charset/
│   ├── manifest.csv
│   ├── personal_frequency.txt
│   ├── phase0.txt
│   ├── phase1_1000.txt
│   ├── common_2500.txt
│   ├── tghz_3500.txt
│   └── gb2312.txt
│
├── templates/
│   ├── pdf/
│   ├── manifests/
│   └── patches/
│
├── scans/
│   ├── raw/
│   └── rejected/
│
├── processed/
│   ├── pages/
│   ├── glyphs/
│   │   ├── grayscale/
│   │   └── binary/
│   └── qa/
│
├── vectors/
│   ├── raw/
│   ├── cleaned/
│   └── rejected/
│
├── scripts/
│   ├── charset/
│   ├── template/
│   ├── scan/
│   ├── vector/
│   └── glyphs/
│
├── tests/
│   ├── strings/
│   ├── raster_diff/
│   ├── builds/
│   └── reports/
│
└── docs/
    ├── acquisition.md
    ├── cleanup-policy.md
    ├── coordinate-system.md
    └── changelog.md
```

`manifest.csv` 是整个系统的 spine。至少包括：

```csv
unicode,glyph_name,char,script,phase,status,
page_id,cell_id,session,
source_scan,source_hash,
threshold,vectorizer,vector_params,
revision,verified
```

模板自己的 manifest 则应该把纸面坐标写死：

```json
{
  "template_version": 3,
  "page_id": "CN-P001",
  "paper": "A4",
  "cells": [
    {
      "unicode": "4E2D",
      "glyph_name": "uni4E2D",
      "writing_box_mm": [18.0, 30.0, 38.0, 50.0],
      "crop_box_mm": [16.0, 26.0, 40.0, 52.0]
    }
  ]
}
```

这样真正的 pipeline 是：

```text
Unicode
↕
manifest
↕
template cell
↕
scan cell
↕
PNG
↕
SVG
↕
Glyphs glyph
```

所有环节都可追溯。

### Phase 0：Pipeline Test

规模：

**50–100 个中文代表字 + ASCII / Basic Latin 核心集。**

中文字不要只选最常用，要故意覆盖：

```text
极简：一、乙、人
方框：口、回、国
密集：鬱类不必首版，但可选赢/器等复杂字
小点：心、下、六
长撇捺：大、文
左右：你、他、树
上下：要、意
自然偏位明显的个人特征字
```

此阶段重点完全不是“做出好看的字体”，而是把机器系统打通。

| 环节 | 做法 |
|---|---|
| 字表 | `charset/phase0.txt` |
| template | Python A4 generator |
| 页面定位 | 4 ArUco + QR |
| acquisition | scanner 600 dpi |
| crop | OpenCV fixed geometry |
| vector | Potrace + 20 字 Illustrator/Glyphs comparison |
| import | Glyphs Python |
| CJK width | 1000 |
| source PNG | 挂在 Glyphs layer |
| raw trace | 存 background |
| cleanup | technical only |
| export | Glyphs OTF/TTF |

**成功条件：**

不是“字体看起来不错”，而是：

- 每页 page ID 自动正确；
- 每格 Unicode 映射零错位；
- PNG→SVG→Glyphs 没有逐字 bbox scaling；
- 固定 calibration glyph 的位置误差稳定；
- 原图和轮廓可 overlay；
- `uni4E2D.png → uni4E2D.svg → uni4E2D` 全自动；
- empty/missing list 可自动生成；
- 字体可正常导出、安装、输入；
- patch 一个字符后只影响该字符。

建议在这个阶段设置一个工程阈值，例如 scanner pipeline 的坐标误差目标先试 **10–20 font units 以内**，然后根据真实 PoC 数据再决定标准，而不要一开始假装已有行业统一容差。

### Phase 1：Minimum Personal Font

目标：

**约 1000 中文 + 完整常用 Latin。**

中文字由你的个人 corpus frequency 为主。

Latin 至少覆盖：

```text
A–Z
a–z
digits
ASCII punctuation
你实际使用的 smart quotes / dash
常用 currency
中英文标点
```

这一阶段开始认真测：

```text
个人文本 coverage
英文 spacing
中英文混排
punctuation position
vertical metrics
```

成功条件不是“1000 个字都在”，而是：

> **你实际最常写的材料，大多数都不再出现 fallback glyph。**

coverage 目标最好由你的 corpus 统计决定，而不是设一个虚假的全行业百分比。

### Phase 2：扩字生产

依次建议：

```text
1000
→ 2500
→ 通用规范汉字一级 3500
→ 个人需要决定：
   6500 通规一级+二级
   或 GB2312 6763
→ 8105 / specialty
```

《通用规范汉字表》3500 / 6500 / 8105 的三级结构给了一个比 legacy encoding 更符合现代使用频率的自然扩展路线。citeturn17search0

这个阶段生产能力的关键不再是 tracing，而是：

**patch、QA 和 fatigue management。**

例如：

```text
glyph uni76F4
status = rewrite
reason = stroke clipped

glyph uni8FD9
status = trace-issue

glyph uni4E86
status = verified
```

脚本：

```text
collect status=hw:rewrite
→ rewrite_2026_10_01.txt
→ make_patch_template.py
→ patch_014.pdf
```

然后：

```text
扫描 patch
→ page revision=14
→ 只生成对应 PNG/SVG
→ Glyphs import script
→ 旧 foreground 自动复制到 background
→ 替换
→ status=review
```

这正是 wefont 已经证明可行的生产模式，只是你把最终 font editor 换成 Glyphs。citeturn10view0

### Phase 3：增强真实感

等基本字库稳定以后才加入：

```text
.ss01
.ss02
calt
高频字符 variants
英文 contextual forms
真实 ligatures
更多 Latin language support
更多中文标点
```

Glyphs 官方专门有 advanced contextual alternates 教程，且 `.ss01` 等命名有标准支持。citeturn20search1turn3view4

此阶段仍然应坚持：

> alternate 是“重新真实写一次”，不是在 Glyphs 里把原 outline 拉成另一个样子。

### Git、版本和 patch

建议 Git commit 粒度直接描述 acquisition / glyph batch：

```text
template: generate phase0 v3
scan: add session 2026-09-12 pages 001-003
vector: trace CN-P001
glyphs: import phase0 batch A
cleanup: verify 4E00-4E5F
patch: replace 4E2D and 4E86
```

`.glyphspackage` 已被 Glyphs 用户用于 Git version control。citeturn18search36

大型扫描 TIFF/PNG 是否进入 Git 本体则要视仓库大小决定；最少必须 Git 管：

```text
manifest
scripts
templates
SVG
glyphspackage
status metadata
```

raw scans 即使存外部，也必须有 checksum/immutable archive。

## 立即可执行的 Proof-of-Concept、风险控制与参考资料

### 最值得马上执行的 100 字 PoC

不要先写 1000 字。

第一次实验只需要大约两次书写 session。

**Session A：natural reference**

写两页完全正常的内容：

中文一页、英文一页。

不考虑字体、不刻意漂亮。

**Session B：template**

生成：

```text
80 中文
A–Z
a–z
0–9
约 20 个标点
```

A4 每页约 80 个中文格，20 mm 左右 writing box。

四角 ArUco，底部一个 QR。

prompt 在格子上方。

不放中心十字。

用你平时的黑色中性笔，以正常速度写。

然后测试四条 vector pipeline：

```text
10 字 Potrace
10 字 Glyphs Trace Image
10 字 Illustrator Image Trace
少量 OpenCV contours 实验
```

不是为了选四个不同 production 工具，而是建立视觉和技术 benchmark。

最终应该在 Glyphs 中得到这样一个 glyph：

```text
uni4E2D

foreground:
    technical-clean vector

background:
    original automatic vector trace

backgroundImage:
    rectified uni4E2D.png

width:
    1000

tag:
    hw:review

note:
    session=S001 page=P001 cell=17
```

Glyphs 的 background、image、color/tag/Smart Filter 和 Python object model足以支撑这样的组织方式。citeturn2view5turn6view1turn1view0

然后专门打出一张测试页：

```text
你自然写的原句
vs
用字体重新排的同一句
```

重点看：

- “口”是否变大了；
- “一”是否变窄了；
- 偏左字是否被自动纠正；
- 汉字 line rhythm 是否和自然 sample 差异很大；
- Latin baseline 是否失真；
- spacing 是否比字形本身更影响观感。

只有这一步通过以后，才值得开始 1000 字。

### 最主要的风险

| 风险 | 真正原因 | 处理方式 |
|---|---|---|
| **模板让字变工整** | acquisition 改变行为 | natural sample、弱参考线、正常速度、多 session |
| **绝对位置保存的是“填格误差”** | isolated cells 不等于自然文本 | 与 natural sample 对照，不逐字居中 |
| **trace 节点爆炸** | noise/threshold/高分辨率边缘 | threshold policy + Potrace tuning + raster diff simplification |
| **细笔画丢失** | threshold/morphology 过重 | 保存 grayscale、降低清理强度 |
| **中文工程量失控** | 字量而非字体技术 | 100→1000→2500→3500 分阶段 |
| **Glyphs SVG scale 意外** | importer coordinate handling | canonical SVG + calibration tests |
| **英文看起来不像本人** | isolated alphabet 改变写法 | continuous text + isolated coverage |
| **中文行看起来歪** | 真实 offset 被保留 | 先接受；source master 不 recenter |
| **混排 vertical metrics 奇怪** | CJK/Latin 共用 metrics | 用自然混排样本校准 |
| **补字越来越混乱** | source provenance 缺失 | manifest + revision + patch template |
| **把错误写法“修漂亮”** | technical/design cleanup 混淆 | rewrite，不 design-correct |
| **alternates 工程爆炸** | glyph count × variants | 只做高频字，Phase 3 再做 |

其中最值得你心理上提前接受的一点是：

> **忠实 handwriting font 不一定是“最舒服的字体”。**

InkFontify 选择 center-of-mass alignment，正是因为完全保留位置变化会造成新排列中的跳动。citeturn22view2

你的 source font 完全可以坚持不调整。

以后若实际使用中觉得太跳，可以另外派生：

```text
MyHandwriting-Archive
    = 最大保真 master

MyHandwriting-Text
    = 极轻度 global typographic normalization
```

但不要把第二个版本的排版选择反向污染 archive master。

### 最终技术栈建议

最终我会锁定为：

```text
Charset / corpus
    Python

Template PDF
    Python PDF generator
    + OpenCV ArUco
    + QR metadata

Scan
    600 dpi flatbed
    PNG/TIFF archive

Page processing
    OpenCV

Batch file conversion
    ImageMagick optional

Segmentation
    manifest-driven OpenCV crop
    不依赖 glyph bbox

Trace
    Potrace production baseline

Difficult trace QA
    Glyphs Trace Image
    Illustrator Image Trace
    Inkscape optional

Font source / glyph database
    Glyphs 3 .glyphspackage

Import / patch / QA
    Glyphs Python API

OpenType
    Glyphs

Alternates
    .ss01 / .ss02
    + calt
    + mekkablue pseudorandom script as reference

Build
    Glyphs OTF/TTF
```

这里最关键的“不使用”同样值得写进规范：

```text
NO per-glyph bbox normalization
NO automatic centering
NO automatic visual scaling
NO automatic slant correction
NO stroke standardization
NO center-of-mass alignment
NO design correction disguised as cleanup
```

### 关键一手资料与原始链接

**Glyphs 官方资料**

Glyphs 3.4 release（历史参考，项目目标版本为 3.3）：  
`https://glyphsapp.com/news/glyphs-3-4-released` citeturn4search3

Glyphs Python API：  
`https://docu.glyphsapp.com/` citeturn1view1turn6view1

Glyphs Handbook：  
`https://handbook.glyphsapp.com/en/single-page/`  
需要注意当前 handbook 已随 Glyphs 4 继续更新；本报告对 Glyphs 3 的具体自动化操作优先交叉使用 Glyphs 3 时代 API 与论坛资料。citeturn1view0

Glyphs 官方 Advanced Contextual Alternates：  
`https://glyphsapp.com/learn/features-part-3-advanced-contextual-alternates` citeturn20search1

Glyphs 官方 Positional Alternates：  
`https://glyphsapp.com/learn/features-part-4-positional-alternates` citeturn20search9

**Glyphs Forum：实际扫描/批量工作流**

Import many images at once：  
`https://forum.glyphsapp.com/t/import-many-images-at-once/3315` citeturn7view2

Create a font from a scanned image：  
`https://forum.glyphsapp.com/t/design-method-create-a-font-from-a-scanned-image/26422` citeturn19search2

SVG Import Scaling/Cropping：  
`https://forum.glyphsapp.com/t/svg-import-scaling-cropping/28494` citeturn7view0

Git + `.glyphspackage`：  
`https://forum.glyphsapp.com/t/using-git-for-version-control/29010` citeturn18search36

个人 handwriting font Glyphs 案例：  
`https://forum.glyphsapp.com/t/creating-masters-of-a-handwriting-font/33113` citeturn20search22

**中文自动化 / 开源案例**

wefont — 中文个人手写字体制作工具：  
`https://github.com/wenzhenl/wefont` citeturn10view0

InkFontify 论文，*Design and Evaluation of Handwritten Traditional Chinese Fonts Reflecting Human-like Writing Characteristics via Computer-Mediated Communication*：  
`https://www.cad-journal.net/files/vol_23/CAD_23(3)_2026_282-291.pdf` citeturn21view0

Make Me a Hanzi，可作为 CJK 字符数据/reference 的旁路资源：  
`https://github.com/skishore/makemeahanzi` citeturn9search8

Chinese Hershey Font，属于 centerline/single-line Chinese 的技术参考而非个人 handwriting capture：  
`https://github.com/LingDong-/chinese-hershey-font` citeturn9search0

**Glyphs 脚本资源**

mekkablue Glyphs Scripts：  
`https://github.com/mekkablue/Glyphs-Scripts`  
其中包括 pseudorandom `calt` 等可参考自动化脚本。citeturn20search2

dyyybek Glyphs Scripts：  
`https://github.com/dyyybek/Glyphs-Scripts`  
其中有按 Unicode code point 批量导入图片的实践。citeturn7view2

**图像处理与 tracing**

OpenCV ArUco 官方教程：  
`https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html` citeturn15search0

OpenCV Python tutorials：  
`https://docs.opencv.org/5.0/py_tutorials/py_tutorials.html` citeturn15search25

Potrace：  
`https://potrace.sourceforge.net/` citeturn12search3

ImageMagick：  
`https://imagemagick.org/` citeturn15search6

Adobe Illustrator Image Trace options：  
`https://helpx.adobe.com/sg/illustrator/desktop/manage-objects/traces-mockups-symbols/image-trace-panel-options.html` citeturn19search0

**个人 handwriting 服务与 Latin precedent**

Calligraphr template tutorial：  
`https://www.calligraphr.com/en/docs/tutorial1/` citeturn8search6

Calligraphr randomized characters / variants：  
`https://www.calligraphr.com/en/docs/tutorial2/` citeturn8search14

Calligraphr FAQ：  
`https://www.calligraphr.com/en/docs/faq/` citeturn8search0

Fontself：  
`https://www.fontself.com/` citeturn19search5

**现代中文字符集**

教育部《通用规范汉字表》：  
`https://www.moe.gov.cn/jyb_sjzl/ziliao/A19/201306/t20130601_186002.html` citeturn17search20

教育部关于 8105 / 3500 / 3000 / 1605 字分级的说明：  
`https://www.moe.gov.cn/jyb_xwfb/s5147/201308/t20130828_156388.html` citeturn17search0

Unicode 当前 CJK Code Charts：  
`https://www.unicode.org/charts/` citeturn17search8

综合这些一手资料和真实案例，**最值得投入开发的并不是“更聪明地自动把字摆漂亮”的算法，而是一个严格维护 provenance 与坐标的 production system**。只要固定 paper-space mapping、manifest、patch 和 Glyphs import 四件事从 Phase 0 就设计正确，后续从 100 字扩到 1000、2500、3500 甚至 6763 字，本质上只是生产规模增加；反过来，如果第一版已经逐字 bbox fit、center、normalize，那么即使做满 6000 字，你获得的也会是一套“根据你的笔迹加工出来的手写字体”，而不是你真正想要的那套**可安装、可输入、可维护的本人真实 handwriting 数字档案**。