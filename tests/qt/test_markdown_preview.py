import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pytestqt.qtbot import QtBot

from tagstudio.core.library.alchemy.library import Library
from tagstudio.qt.controllers.preview_thumb_controller import PreviewThumb
from tagstudio.qt.ts_qt import QtDriver


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_test_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    im.save(path)


def test_markdown_preview_uses_text_widget(qtbot: QtBot, tmp_path: Path):
    """Markdown files should be previewed as wrapped, scrollable text (not an image thumbnail)."""

    md_path = tmp_path / "example.md"
    md_path.write_text("# Title\n\nSome **bold** text.\n", encoding="utf-8")

    lib = Library()
    assert lib.open_library(tmp_path, ":memory:").success

    class Args:
        settings_file = tmp_path / "settings.toml"
        cache_file = tmp_path / "tagstudio.ini"
        open = tmp_path
        ci = True

    with patch("tagstudio.qt.ts_qt.Consumer"), patch("tagstudio.qt.ts_qt.CustomRunnable"):
        driver = QtDriver(Args())  # pyright: ignore[reportArgumentType]
        driver.lib = lib

        widget = PreviewThumb(lib, driver)
        qtbot.addWidget(widget)

        widget.display_file(md_path)

        text = widget._PreviewThumbView__text_browser.toPlainText()  # type: ignore[attr-defined]
        assert "Title" in text
        assert "bold" in text


def test_markdown_preview_relative_images_load_from_disk(qtbot: QtBot, tmp_path: Path):
    """Relative markdown images like ![](./img.png) should resolve against the md file's folder."""

    img_path = tmp_path / "assets" / "img.png"
    _make_test_png(img_path)

    md_path = tmp_path / "doc.md"
    md_path.write_text("# Doc\n\n![](./assets/img.png)\n", encoding="utf-8")

    lib = Library()
    assert lib.open_library(tmp_path, ":memory:").success

    class Args:
        settings_file = tmp_path / "settings.toml"
        cache_file = tmp_path / "tagstudio.ini"
        open = tmp_path
        ci = True

    with patch("tagstudio.qt.ts_qt.Consumer"), patch("tagstudio.qt.ts_qt.CustomRunnable"):
        driver = QtDriver(Args())  # pyright: ignore[reportArgumentType]
        driver.lib = lib

        widget = PreviewThumb(lib, driver)
        qtbot.addWidget(widget)

        widget.display_file(md_path)

        browser = widget._PreviewThumbView__text_browser  # type: ignore[attr-defined]
        doc = browser.document()

        # Verify the image resource got loaded.
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument

        # With baseUrl set, this relative URL should be resolvable.
        url = QUrl("assets/img.png")
        resource = doc.resource(QTextDocument.ResourceType.ImageResource, url)
        assert resource is not None


def test_markdown_preview_large_images_are_scaled_down(qtbot: QtBot, tmp_path: Path):
    """Large embedded images should be constrained to the preview width."""

    # Create a very wide image.
    img_path = tmp_path / "assets" / "wide.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (2000, 200), (0, 255, 0, 255)).save(img_path)

    md_path = tmp_path / "doc.md"
    md_path.write_text("# Doc\n\n![](./assets/wide.png)\n", encoding="utf-8")

    lib = Library()
    assert lib.open_library(tmp_path, ":memory:").success

    class Args:
        settings_file = tmp_path / "settings.toml"
        cache_file = tmp_path / "tagstudio.ini"
        open = tmp_path
        ci = True

    with patch("tagstudio.qt.ts_qt.Consumer"), patch("tagstudio.qt.ts_qt.CustomRunnable"):
        driver = QtDriver(Args())  # pyright: ignore[reportArgumentType]
        driver.lib = lib

        widget = PreviewThumb(lib, driver)
        qtbot.addWidget(widget)

        # Give the browser a deterministic size so we can assert scaling.
        widget.resize(500, 500)
        widget.show()
        qtbot.waitExposed(widget)

        widget.display_file(md_path)

        browser = widget._PreviewThumbView__text_browser  # type: ignore[attr-defined]

        # Verify the *rendered* image size fits the viewport.
        from PySide6.QtGui import QTextCursor, QTextImageFormat

        doc = browser.document()
        cursor = QTextCursor(doc)
        found_width = None

        while not cursor.atEnd():
            fmt = cursor.charFormat()
            if fmt.isImageFormat():
                img_fmt = QTextImageFormat(fmt)
                found_width = img_fmt.width()
                break
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)

        assert found_width is not None
        assert found_width <= browser.viewport().width()


def test_markdown_preview_expands_to_available_space(qtbot: QtBot, tmp_path: Path):
    """Text/markdown preview should expand with the preview panel size."""

    md_path = tmp_path / "example.md"
    md_path.write_text("# Title\n\nSome text\n", encoding="utf-8")

    lib = Library()
    assert lib.open_library(tmp_path, ":memory:").success

    class Args:
        settings_file = tmp_path / "settings.toml"
        cache_file = tmp_path / "tagstudio.ini"
        open = tmp_path
        ci = True

    with patch("tagstudio.qt.ts_qt.Consumer"), patch("tagstudio.qt.ts_qt.CustomRunnable"):
        driver = QtDriver(Args())  # pyright: ignore[reportArgumentType]
        driver.lib = lib

        widget = PreviewThumb(lib, driver)
        qtbot.addWidget(widget)

        widget.resize(700, 400)
        widget.show()
        qtbot.waitExposed(widget)

        widget.display_file(md_path)

        browser = widget._PreviewThumbView__text_browser  # type: ignore[attr-defined]
        # Leave tolerance for layout margins.
        assert browser.width() >= 500
        assert browser.height() >= 250

