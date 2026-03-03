## Objective

The primary goal of this task was to address Issue #968, adding support for parsing and displaying Markdown (`.md`) files directly within the TagStudio file preview panel. Previously, markdown files could not be correctly formatted or failed to load assets in the preview.

## Requirements

REQ-2-1: Creating a new wrap for markdown files
When we detect that a file is a markdown file the system will display the contents of the file in a scrollable, wrapped widget.


## Technical Approach

The modifications are driven via the `tagstudio/qt/controllers/preview_thumb_controller.py` controller. The component detects markdown file suffixes and bridges the output to the `QTextBrowser` widget using injected CSS and HTML compilation instead of standard plain text inputs. Tests and resource resolution mechanisms are integrated to properly serve local file paths embedded dynamically in the text.

## Detailed Code Modifications

**File 1:** 

src/tagstudio/qt/controllers/preview_thumb_controller.py

This file houses the UI logic for initializing rendering operations in the right-side preview panel.

- **Import Updates:**
    Imported `markdown` to parse formatted markdown tokens to HTML dynamically.
- **Handling Parsing Logic:**
    Introduced suffix checks matching `('.md', '.markdown')`. Upon match, the raw file string is parsed via `markdown.markdown()` supporting extended formats.
- **CSS Preprocessing & Overrides:**
    Prepended an encompassing HTML container with embedded `<style>` properties (`img{max-width:100%;height:auto;}`) to ensure responsively scaled assets. Pre-formatted `<pre>` scopes inherit wrapping layouts for continuous reading.
- **Resource Linking (Base URL):**
    Assigned `.setBaseUrl(QUrl.fromLocalFile(file.parent))` against the `QTextDocument`. Relational paths in image links like `![](./docs/screen.png)` are resolved contextually against the opened origin.
- **Image Link Rewriting Fallback:**
    Created `_rewrite_md_images` method matching standard `![alt](url)` markdown snippets using regex, functioning as a fallback logic for responsive images.

**File 2:**

tests/qt/test_markdown_preview.py

A dedicated testing suite verifying behavior stability over changes:

- `test_markdown_preview_uses_text_widget`: Verifies markdown triggers text rendering in `QTextBrowser` mapping elements.
- `test_markdown_preview_relative_images_load_from_disk`: Simulates `![](./img.png)` parsing in a fake library path asserting Qt successfully loads `ImageResource` nodes through QUrl.
- `test_markdown_preview_large_images_are_scaled_down`: Creates oversized 2000px-wide visual buffers to mathematically verify layout bounds do not over-expand `browser.viewport().width()`.
- `test_markdown_preview_expands_to_available_space`: Tests window resize triggers resize updates correctly spanning bounding areas in the UI tree.
