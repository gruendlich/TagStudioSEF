import pytest

from tagstudio.core.media_types import MediaCategories, MediaType

@pytest.mark.parametrize(
    "ext",
    [
        ".ass",
        ".idx",
        ".scc",
        ".srt",
        ".ssa",
        ".sub",
        ".vtt",
        ".sbv",
        ".stl",
        ".ttml",
    ],
)

def test_subtitle_extensions_are_classified_as_text(ext: str) -> None:
    assert MediaType.TEXT in MediaCategories.get_types(ext)
