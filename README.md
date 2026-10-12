# MuNoteBook

基于 **PySide6-Fluent-Widgets** 的 Fluent 设计风格 Markdown 笔记桌面应用，数据存储于 SQLite，自定义样式使用 QSS。

## 功能特性

- 笔记管理：新建、重命名、编辑、置顶、收藏、搜索（标题 + 内容）
- 软删除与回收站：删除进入回收站，支持恢复与彻底删除，可一键清空
- Markdown 编辑器：编辑 / 预览 / 双栏三种视图模式，输入防抖后自动渲染与自动保存
- 图片插入：工具栏按钮选择图片、剪贴板粘贴截图、拖入图片文件，三种方式均可；
  图片统一存入 `images/` 目录，以相对路径引用，彻底删除笔记时自动清理
- 文档导入与编辑（类 WPS 体验，按类型自动路由编辑器）：
  - `.md` / `.txt` -> Markdown 笔记（现有三模式编辑器）
  - `.docx` -> **Word 富文本笔记**：导入时转换为 HTML 保留标题/列表/表格/
    字体/颜色/对齐/图片，用所见即所得富文本编辑器编辑（粗体/斜体/下划线/
    字号/颜色/对齐/列表/插图），可导出回 `.docx`
  - `.pdf` -> **PDF 渲染查看笔记**：按页渲染图片滚动查看，支持缩放与翻页（只读），
    可另存 PDF 原件
  - 导入支持多选，原件自动留存到 `documents/` 文档库
- 文档导出：按笔记类型提供对应导出（md 笔记可导 md/docx，docx 笔记可导 docx，
  pdf 笔记可另存原件；有原件的笔记均可"另存原件副本"）
- 收藏页：快速筛选收藏笔记
- 设置页：主题模式（浅色 / 深色 / 跟随系统）、主题色、自动保存开关
- Fluent 风格界面：左侧导航、深浅双主题、QSS 自定义列表项与编辑器样式

## 运行环境

- conda 虚拟环境 `pyside6l`
- Python + PySide6 6.11.2
- PySide6-Fluent-Widgets 1.11.3
- markdown >= 3.6（Markdown 渲染）

## 安装依赖

```powershell
conda activate pyside6l
pip install -r requirements.txt
```

## 运行

```powershell
conda activate pyside6l
python main.py
```

数据库文件 `notes.db` 首次运行时自动生成于项目根目录；用户配置保存在 `app_config.json`；
笔记中插入的图片统一存放于 `images/` 目录（首次插入图片时自动创建）；
导入的文档原件留存于 `documents/` 目录（首次导入文档时自动创建）。

## 项目结构

```
.
├── main.py                      # 应用入口
├── requirements.txt             # 依赖清单
├── app/
│   ├── config.py                # 全局常量配置
│   ├── app_settings.py          # 用户设置（JSON 持久化）
│   ├── models.py                # Note 数据模型
│   ├── database.py              # SQLite 数据访问层
│   ├── image_utils.py           # 图片库管理（入库 / 引用 / 清理）
│   ├── document_utils.py        # 文档导入导出（docx<->HTML、md->docx、pdf 提取）
│   ├── markdown_utils.py        # Markdown 渲染 / 标题提取 / 摘要
│   ├── main_window.py           # FluentWindow 主窗口与导航
│   ├── resources/
│   │   └── style.qss            # 全局 QSS 样式
│   ├── pages/                   # 功能页面
│   │   ├── notes_page.py        #   所有笔记页
│   │   ├── favorites_page.py    #   收藏页
│   │   ├── trash_page.py        #   回收站页
│   │   └── settings_page.py     #   设置页
│   └── widgets/                 # 可复用组件
│       ├── note_list_widget.py  #   笔记列表
│       ├── markdown_editor.py   #   Markdown 编辑器（md 笔记）
│       ├── rich_text_editor.py  #   Word 富文本编辑器（docx 笔记，所见即所得）
│       └── pdf_viewer.py        #   PDF 渲染查看器（pdf 笔记，只读）
├── notes.db                     # 运行时自动生成（SQLite 数据库）
├── images/                      # 运行时自动生成（笔记图片库）
└── documents/                   # 运行时自动生成（导入文档原件库）
```
