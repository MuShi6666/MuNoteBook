# Fluent 记事本

基于 **PySide6-Fluent-Widgets** 的 Fluent 设计风格 Markdown 记事本桌面应用，数据存储于 SQLite，自定义样式使用 QSS。

## 功能特性

- 笔记管理：新建、重命名、编辑、置顶、收藏、搜索（标题 + 内容）
- 软删除与回收站：删除进入回收站，支持恢复与彻底删除，可一键清空
- Markdown 编辑器：编辑 / 预览 / 双栏三种视图模式，输入防抖后自动渲染与自动保存
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

数据库文件 `notes.db` 首次运行时自动生成于项目根目录；用户配置保存在 `app_config.json`。

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
│       └── markdown_editor.py   #   Markdown 编辑器
└── notes.db                     # 运行时自动生成
```
