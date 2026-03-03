# Licensed under the GPL-3.0 License.
# Created for TagStudio: https://github.com/CyanVoxel/TagStudio

import math
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, override

import markdown as md
import structlog
from PySide6.QtCore import QBuffer, QByteArray, QSize, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QMovie, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTextBrowser,
    QWidget,
)

from tagstudio.core.library.alchemy.library import Library
from tagstudio.core.media_types import MediaType
from tagstudio.qt.mixed.file_attributes import FileAttributeData
from tagstudio.qt.mixed.media_player import MediaPlayer
from tagstudio.qt.platform_strings import open_file_str, trash_term
from tagstudio.qt.previews.renderer import ThumbRenderer
from tagstudio.qt.translations import Translations
from tagstudio.qt.views.styles.rounded_pixmap_style import RoundedPixmapStyle

if TYPE_CHECKING:
    from tagstudio.qt.ts_qt import QtDriver

logger = structlog.get_logger(__name__)


THUMB_SIZE_FACTOR = 2


class _LocalOnlyTextBrowser(QTextBrowser):
    """QTextBrowser that blocks loading non-local resources (e.g., http/https).

    This is used for markdown previews so relative images work, while remote images
    are blocked (per current requirements).
    """

    @staticmethod
    def _accept_url(url: object) -> bool:
        qurl = url if isinstance(url, QUrl) else QUrl(str(url))
        scheme = (qurl.scheme() or "").lower()
        return scheme in {"", "file"}

    def loadResource(self, type_: int, name: QUrl | str):
        qurl = name if isinstance(name, QUrl) else QUrl(str(name))
        if not self._accept_url(qurl):
            return None
        return super().loadResource(type_, qurl)


class PreviewThumbView(QWidget):
    """The Preview Panel Widget."""

    __img_button_size: tuple[int, int]
    __image_ratio: float

    __filepath: Path | None
    __rendered_res: tuple[int, int]

    def __init__(self, library: Library, driver: "QtDriver") -> None:
        super().__init__()

        self.__img_button_size = (266, 266)
        self.__image_ratio = 1.0

        self.__image_layout = QStackedLayout(self)
        self.__image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.__image_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.__image_layout.setContentsMargins(0, 0, 0, 0)

        open_file_action = QAction(Translations["file.open_file"], self)
        open_file_action.triggered.connect(self._open_file_action_callback)
        open_explorer_action = QAction(open_file_str(), self)
        open_explorer_action.triggered.connect(self._open_explorer_action_callback)
        delete_action = QAction(
            Translations.format("trash.context.singular", trash_term=trash_term()),
            self,
        )
        delete_action.triggered.connect(self._delete_action_callback)

        self.__button_wrapper = QPushButton()
        self.__button_wrapper.setMinimumSize(*self.__img_button_size)
        self.__button_wrapper.setFlat(True)
        self.__button_wrapper.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.__button_wrapper.addAction(open_file_action)
        self.__button_wrapper.addAction(open_explorer_action)
        self.__button_wrapper.addAction(delete_action)
        self.__button_wrapper.clicked.connect(self._button_wrapper_callback)

        # In testing, it didn't seem possible to center the widgets directly
        # on the QStackedLayout. Adding sublayouts allows us to center the widgets.
        self.__preview_img_page = QWidget()
        self.__stacked_page_setup(self.__preview_img_page, self.__button_wrapper)

        self.__preview_gif = QLabel()
        self.__preview_gif.setMinimumSize(*self.__img_button_size)
        self.__preview_gif.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.__preview_gif.setCursor(Qt.CursorShape.ArrowCursor)
        self.__preview_gif.addAction(open_file_action)
        self.__preview_gif.addAction(open_explorer_action)
        self.__preview_gif.addAction(delete_action)
        self.__gif_buffer: QBuffer = QBuffer()

        self.__preview_gif_page = QWidget()
        self.__stacked_page_setup(self.__preview_gif_page, self.__preview_gif)

        self.__media_player = MediaPlayer(driver)
        self.__media_player.addAction(open_file_action)
        self.__media_player.addAction(open_explorer_action)
        self.__media_player.addAction(delete_action)

        # Need to watch for this to resize the player appropriately.
        self.__media_player.player.hasVideoChanged.connect(
            self.__media_player_video_changed_callback
        )

        self.__media_player_page = QWidget()
        self.__stacked_page_setup(self.__media_player_page, self.__media_player)

        # Text / Markdown preview
        self.__text_browser = _LocalOnlyTextBrowser()
        self.__text_browser.setOpenExternalLinks(False)
        self.__text_browser.setReadOnly(True)
        self.__text_browser.setFrameShape(QLabel().frameShape())
        self.__text_browser.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        self.__text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.__text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.__text_browser.addAction(open_file_action)
        self.__text_browser.addAction(open_explorer_action)
        self.__text_browser.addAction(delete_action)

        self.__text_browser.anchorClicked.connect(self.__on_text_anchor_clicked)
        self.__text_page = QWidget()
        self.__stacked_page_setup(self.__text_page, self.__text_browser)

        self.__thumb_renderer = ThumbRenderer(driver)
        self.__thumb_renderer.updated.connect(self.__thumb_renderer_updated_callback)
        self.__thumb_renderer.updated_ratio.connect(self.__thumb_renderer_updated_ratio_callback)

        self.__image_layout.addWidget(self.__preview_img_page)
        self.__image_layout.addWidget(self.__preview_gif_page)
        self.__image_layout.addWidget(self.__media_player_page)
        self.__image_layout.addWidget(self.__text_page)

        self.setMinimumSize(*self.__img_button_size)

        self.hide_preview()

    def _open_file_action_callback(self):
        raise NotImplementedError

    def _open_explorer_action_callback(self):
        raise NotImplementedError

    def _delete_action_callback(self):
        raise NotImplementedError

    def _button_wrapper_callback(self):
        raise NotImplementedError

    def __media_player_video_changed_callback(self, video: bool) -> None:
        self.__update_image_size((self.size().width(), self.size().height()))

    def __thumb_renderer_updated_callback(
        self, _timestamp: float, img: QPixmap, _size: QSize, _path: Path
    ) -> None:
        self.__button_wrapper.setIcon(img)

    def __thumb_renderer_updated_ratio_callback(self, ratio: float) -> None:
        self.__image_ratio = ratio
        self.__update_image_size(
            (
                self.size().width(),
                self.size().height(),
            )
        )

    def __stacked_page_setup(self, page: QWidget, widget: QWidget) -> None:
        layout = QHBoxLayout(page)
        layout.addWidget(widget)
        layout.setAlignment(widget, Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        page.setLayout(layout)

    def __update_image_size(self, size: tuple[int, int]) -> None:
        adj_width: float = size[0]
        adj_height: float = size[1]
        # Landscape
        if self.__image_ratio > 1:
            adj_height = size[0] * (1 / self.__image_ratio)
        # Portrait
        elif self.__image_ratio <= 1:
            adj_width = size[1] * self.__image_ratio

        if adj_width > size[0]:
            adj_height = adj_height * (size[0] / adj_width)
            adj_width = size[0]
        elif adj_height > size[1]:
            adj_width = adj_width * (size[1] / adj_height)
            adj_height = size[1]

        adj_size = QSize(int(adj_width), int(adj_height))

        self.__img_button_size = (int(adj_width), int(adj_height))
        self.__button_wrapper.setMaximumSize(adj_size)
        self.__button_wrapper.setIconSize(adj_size)
        self.__preview_gif.setMaximumSize(adj_size)
        self.__preview_gif.setMinimumSize(adj_size)

        self.__media_player.setMaximumSize(adj_size)
        self.__media_player.setMinimumSize(adj_size)

        full_size = QSize(int(size[0]), int(size[1]))
        self.__text_browser.setMinimumSize(full_size)
        self.__text_browser.setMaximumSize(full_size)

        proxy_style = RoundedPixmapStyle(radius=8)
        self.__preview_gif.setStyle(proxy_style)
        self.__media_player.setStyle(proxy_style)
        m = self.__preview_gif.movie()
        if m:
            m.setScaledSize(adj_size)

    def __switch_preview(self, preview: MediaType | None) -> None:
        if preview in [MediaType.AUDIO, MediaType.VIDEO]:
            self.__media_player.show()
            self.__image_layout.setCurrentWidget(self.__media_player_page)
        else:
            self.__media_player.stop()
            self.__media_player.hide()

        if preview == MediaType.TEXT:
            self.__button_wrapper.hide()
            if self.__preview_gif.movie():
                self.__preview_gif.movie().stop()
                self.__gif_buffer.close()
            self.__preview_gif.hide()
            self.__text_browser.show()
            self.__image_layout.setCurrentWidget(self.__text_page)
            return
        else:
            self.__text_browser.hide()

        if preview in [MediaType.IMAGE, MediaType.AUDIO]:
            self.__button_wrapper.show()
            self.__image_layout.setCurrentWidget(
                self.__preview_img_page if preview == MediaType.IMAGE else self.__media_player_page
            )
        else:
            self.__button_wrapper.hide()

        if preview == MediaType.IMAGE_ANIMATED:
            self.__preview_gif.show()
            self.__image_layout.setCurrentWidget(self.__preview_gif_page)
        else:
            if self.__preview_gif.movie():
                self.__preview_gif.movie().stop()
                self.__gif_buffer.close()
            self.__preview_gif.hide()

    def __render_thumb(self, filepath: Path) -> None:
        self.__filepath = filepath
        self.__rendered_res = (
            math.ceil(self.__img_button_size[0] * THUMB_SIZE_FACTOR),
            math.ceil(self.__img_button_size[1] * THUMB_SIZE_FACTOR),
        )

        self.__thumb_renderer.render(
            time.time(),
            filepath,
            self.__rendered_res,
            self.devicePixelRatio(),
            update_on_ratio_change=True,
        )

    def __update_media_player(self, filepath: Path) -> int:
        """Display either audio or video.

        Returns the duration of the audio / video.
        """
        self.__media_player.play(filepath)
        return self.__media_player.player.duration() * 1000

    def _display_video(self, filepath: Path, size: QSize | None) -> FileAttributeData:
        self.__switch_preview(MediaType.VIDEO)
        stats = FileAttributeData(duration=self.__update_media_player(filepath))

        if size is not None:
            stats.width = size.width()
            stats.height = size.height()

            self.__image_ratio = stats.width / stats.height
            self.resizeEvent(
                QResizeEvent(
                    QSize(stats.width, stats.height),
                    QSize(stats.width, stats.height),
                )
            )

        return stats

    def _display_audio(self, filepath: Path) -> FileAttributeData:
        self.__switch_preview(MediaType.AUDIO)
        self.__render_thumb(filepath)
        return FileAttributeData(duration=self.__update_media_player(filepath))

    def _display_gif(self, gif_data: bytes, size: tuple[int, int]) -> FileAttributeData | None:
        """Update the animated image preview from a filepath."""
        stats = FileAttributeData()

        # Ensure that any movie and buffer from previous animations are cleared.
        if self.__preview_gif.movie():
            self.__preview_gif.movie().stop()
            self.__gif_buffer.close()

        stats.width = size[0]
        stats.height = size[1]

        self.__image_ratio = stats.width / stats.height

        self.__gif_buffer.setData(gif_data)
        movie = QMovie(self.__gif_buffer, QByteArray())
        self.__preview_gif.setMovie(movie)

        # If the animation only has 1 frame, it isn't animated and shouldn't be treated as such
        if movie.frameCount() <= 1:
            return None

        # The animation has more than 1 frame, continue displaying it as an animation
        self.__switch_preview(MediaType.IMAGE_ANIMATED)
        self.resizeEvent(
            QResizeEvent(
                QSize(stats.width, stats.height),
                QSize(stats.width, stats.height),
            )
        )
        movie.start()

        stats.duration = movie.frameCount() // 60

        return stats

    def _display_image(self, filepath: Path):
        """Renders the given file as an image, no matter its media type."""
        self.__switch_preview(MediaType.IMAGE)
        self.__render_thumb(filepath)

    def __on_text_anchor_clicked(self, url) -> None:
        """Open only local file links from markdown/text preview."""
        qurl = url if isinstance(url, QUrl) else QUrl(str(url))
        scheme = (qurl.scheme() or "").lower()
        if scheme in {"", "file"}:
            QDesktopServices.openUrl(qurl)

    def _display_text(
        self,
        text: str,
        is_markdown: bool = False,
        source_filepath: Path | None = None,
    ) -> FileAttributeData:
        """Display plaintext or markdown in a scrollable, wrapped widget.

        Args:
            text: The text contents to display.
            is_markdown: If True, render as markdown.
            source_filepath: If provided, used to resolve relative links/images.
        """
        self.__switch_preview(MediaType.TEXT)

        if source_filepath is not None:
            base_url = QUrl.fromLocalFile(str(source_filepath.parent) + "/")
            self.__text_browser.document().setBaseUrl(base_url)
        else:
            self.__text_browser.document().setBaseUrl(QUrl())

        # Render markdown.
        if is_markdown:
            try:
                html_body = md.markdown(
                    text,
                    extensions=[
                        "extra",
                        "sane_lists",
                    ],
                    output_format="html",
                )
            except Exception:
                html_body = _rewrite_md_images(text)

            # Ensure images scale to the available width.
            html = (
                "<html><head><meta charset='utf-8'>"
                "<style>"
                "img{max-width:100%;height:auto;}"
                "pre{white-space:pre-wrap;}"
                "code{white-space:pre-wrap;}"
                "</style></head>"
                "<body style='margin:0; padding:0;'>" + html_body + "</body></html>"
            )
            self.__text_browser.setHtml(html)
        else:
            self.__text_browser.setPlainText(text)

        return FileAttributeData()

    def hide_preview(self) -> None:
        """Completely hide the file preview."""
        self.__switch_preview(None)
        self.__filepath = None
        self.__text_browser.clear()
        self.__text_browser.document().setBaseUrl(QUrl())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        self.__update_image_size((self.size().width(), self.size().height()))

        if self.__filepath is not None and self.__rendered_res < self.__img_button_size:
            self.__render_thumb(self.__filepath)

        return super().resizeEvent(event)

    @property
    def media_player(self) -> MediaPlayer:
        return self.__media_player


def _rewrite_md_images(markdown: str) -> str:
    """Rewrite common markdown image syntax to HTML <img> tags.

    This is a best-effort fallback used if full markdown -> HTML conversion fails.
    """
    _md_image_pattern = re.compile(r"!\[([^]]*)]\(([^\s)]+)(?:\s+\"([^\"]*)\")?\)")

    def repl(m: re.Match) -> str:
        alt = m.group(1) or ""
        src = m.group(2) or ""
        title = m.group(3)
        title_attr = f' title="{title}"' if title else ""
        return f'<img src="{src}" alt="{alt}"{title_attr} style="max-width:100%; height:auto;" />'

    return _md_image_pattern.sub(repl, markdown)
