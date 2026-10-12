"""联调冒烟测试：在 offscreen 模式下验证主窗口与数据层核心功能。

使用临时数据库文件，不写入项目数据；验证完成后清理。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config  # noqa: E402

# 使用独立临时数据库，避免污染项目数据
config.DB_PATH = Path(tempfile.gettempdir()) / "smoke_fluent_notepad.db"

from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import isDarkTheme  # noqa: E402

from app.database import Database  # noqa: E402
from app.markdown_utils import extract_title, make_summary, markdown_to_html  # noqa: E402
from app.main_window import MainWindow  # noqa: E402


def check_database() -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    db = Database(config.DB_PATH)
    db.init_schema()

    note_id = db.create_note("# 冒烟测试\n\n**加粗** 与 `代码`", content="# 冒烟测试\n\n**加粗** 与 `代码`")
    assert note_id > 0

    notes = db.list_notes()
    assert len(notes) == 1 and notes[0].id == note_id
    assert notes[0].summary

    note = db.get_note(note_id)
    assert note is not None and "加粗" in (note.content or "")

    db.toggle_favorite(note_id)
    assert db.get_note(note_id).is_favorite is True
    assert len(db.list_notes(favorite_only=True)) == 1

    db.toggle_pinned(note_id)
    assert db.get_note(note_id).is_pinned is True

    db.update_note(note_id, title="更新后的标题", content="更新后的内容")
    note = db.get_note(note_id)
    assert note.title == "更新后的标题" and note.content == "更新后的内容"

    assert len(db.list_notes(keyword="更新")) == 1
    assert len(db.list_notes(keyword="不存在的关键词")) == 0

    db.move_to_trash(note_id)
    assert len(db.list_notes()) == 0
    assert len(db.list_notes(deleted=True)) == 1
    db.restore_note(note_id)
    assert len(db.list_notes()) == 1

    db.move_to_trash(note_id)
    db.delete_permanently(note_id)
    assert len(db.list_notes(deleted=True)) == 0

    db.close()
    print("[ok] 数据库层冒烟通过")


def check_markdown() -> None:
    assert extract_title("# 标题一\n\n正文") == "标题一"
    assert extract_title("第一行就是标题\n第二行") == "第一行就是标题"
    assert extract_title("") == "未命名笔记"
    assert "…" not in make_summary("短内容")
    assert make_summary("# 标题 **粗体**") == "标题 粗体"
    html = markdown_to_html("| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in html
    html = markdown_to_html("```python\nprint(1)\n```")
    assert "<pre>" in html and "print" in html
    print("[ok] Markdown 工具冒烟通过")


def check_ui() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()

    # 页面与导航
    assert window.notes_page is not None
    assert window.favorites_page is not None
    assert window.trash_page is not None
    assert window.settings_page is not None

    # 新建 -> 选中 -> 编辑 -> 保存
    window.notes_page.create_note()
    app.processEvents()
    note_id = window.notes_page.editor.current_note_id
    assert note_id is not None

    window.notes_page.editor.title_edit.setText("UI 测试标题")
    window.notes_page.editor.edit_area.setPlainText("# UI 测试\n\n正文内容")
    window.notes_page.flush_editor()
    app.processEvents()

    note = window.db.get_note(note_id)
    assert note.title == "UI 测试标题", note.title
    assert note.content == "# UI 测试\n\n正文内容", note.content

    # 视图模式切换
    for mode in ("edit", "preview", "split"):
        window.notes_page.editor._apply_mode(mode)
        app.processEvents()

    # 主题切换
    window.apply_theme("dark")
    app.processEvents()
    assert isDarkTheme() is True
    window.apply_theme("light")
    app.processEvents()

    # 收藏切换与列表刷新
    window.notes_page.editor.favorite_btn.click()
    app.processEvents()
    assert window.db.get_note(note_id).is_favorite is True

    # 回收站恢复流程
    window.notes_page._move_to_trash(note_id)
    app.processEvents()
    assert len(window.db.list_notes(deleted=True)) == 1
    window.trash_page.refresh()
    window.trash_page.note_list.select_note(note_id)
    window.trash_page.restore_selected()
    app.processEvents()
    assert window.db.get_note(note_id).is_deleted is False

    # 搜索
    window.notes_page.note_list.search_edit.setText("UI 测试")
    app.processEvents()
    assert window.notes_page.note_list.selected_note_id() is not None
    window.notes_page.note_list.search_edit.setText("")

    # 全部页面刷新
    window.refresh_all_pages()
    app.processEvents()

    # 清理测试数据
    window.db.delete_permanently(note_id)
    window.db.close()
    print("[ok] UI 冒烟通过")


def check_images() -> None:
    """图片插入功能测试：入库、引用、粘贴、拖放、删除清理。"""
    import shutil

    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent, QImage
    from qfluentwidgets import TransparentToolButton  # noqa: F401

    from app import image_utils
    from app.widgets.markdown_editor import MarkdownEditor

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. 外部图片文件复制入库
    work_dir = Path(tempfile.mkdtemp(prefix="smoke_img_work_"))
    src = work_dir / "photo.png"
    image = QImage(48, 32, QImage.Format_RGB32)
    image.fill(Qt.red)
    assert image.save(str(src), "PNG")
    lib_path = image_utils.save_image_file(src)
    assert lib_path.is_file() and lib_path.parent == config.IMAGES_DIR

    # 2. Markdown 引用生成与路径提取（含目录安全检查）
    markdown = image_utils.image_markdown(lib_path, alt="测试图")
    assert markdown.startswith("![测试图](images/") and markdown.endswith(".png)")
    paths = image_utils.extract_image_paths(markdown)
    assert len(paths) == 1 and paths[0] == lib_path.resolve() and paths[0].is_file()
    # import_image_markdown 会复制一张新图片并返回其引用
    imported_md = image_utils.import_image_markdown(src, "导入")
    imported_paths = image_utils.extract_image_paths(imported_md)
    assert len(imported_paths) == 1 and imported_paths[0].is_file()
    assert image_utils.remove_images_in_content(imported_md) == 1
    assert not imported_paths[0].exists()
    # 外链与库外路径不应被提取
    assert image_utils.extract_image_paths("![x](https://a.com/b.png)") == []
    assert image_utils.extract_image_paths("![x](../secret.png)") == []

    # 3. 剪贴板 QImage 保存
    clip_lib = image_utils.save_qimage(image)
    assert clip_lib.is_file() and clip_lib.suffix == ".png"

    # 4. 编辑区粘贴图片（模拟 insertFromMimeData）
    editor = MarkdownEditor()
    mime = QMimeData()
    mime.setImageData(image)
    editor.edit_area.insertFromMimeData(mime)
    text = editor.edit_area.toPlainText()
    assert text.count("](images/") == 1, text

    # 5. 拖放图片文件（模拟 dropEvent）
    drop_mime = QMimeData()
    drop_mime.setUrls([QUrl.fromLocalFile(str(src))])
    event = QDropEvent(
        QPointF(10, 10), Qt.CopyAction, drop_mime, Qt.LeftButton, Qt.NoModifier
    )
    editor.edit_area.dropEvent(event)
    text2 = editor.edit_area.toPlainText()
    assert text2.count("](images/") == 2, text2

    # 6. 按内容清理图片（文本引用仍在，但文件应被删除）
    assert image_utils.remove_images_in_content(text2) == 2
    remaining = image_utils.extract_image_paths(text2)
    assert len(remaining) == 2
    assert all(not p.exists() for p in remaining)
    # 6b. markdown 字符串引用的图片同样可被清理
    assert image_utils.remove_images_in_content(markdown) == 1
    assert not lib_path.exists()
    clip_lib.unlink(missing_ok=True)

    # 7. 端到端：彻底删除笔记时数据库层自动清理图片
    db = Database(config.DB_PATH)
    db.init_schema()
    lib2 = image_utils.save_image_file(src)
    note_md = image_utils.image_markdown(lib2, "端到端")
    note_id = db.create_note("图片笔记", note_md)
    db.move_to_trash(note_id)
    db.delete_permanently(note_id)
    assert not lib2.exists(), "彻底删除笔记后图片应被清理"
    # 软删除不清理图片
    lib3 = image_utils.save_image_file(src)
    note_id2 = db.create_note("图片笔记2", image_utils.image_markdown(lib3))
    db.move_to_trash(note_id2)
    assert lib3.exists(), "软删除不应清理图片"
    db.restore_note(note_id2)
    db.delete_permanently(note_id2)
    assert not lib3.exists()
    db.close()

    # 清理临时工作目录与图片库（仅删图片库目录本身）
    shutil.rmtree(work_dir, ignore_errors=True)
    if config.IMAGES_DIR.exists():
        shutil.rmtree(config.IMAGES_DIR, ignore_errors=True)
    print("[ok] 图片插入功能冒烟通过")


def main() -> None:
    check_database()
    check_markdown()
    check_images()
    check_ui()
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
