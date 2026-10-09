from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _markdown_links(path: Path) -> list[str]:
    return re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))


def test_public_documentation_has_english_and_simplified_chinese_pairs() -> None:
    english_documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    english_documents = [
        path for path in english_documents if not path.name.endswith(".zh-CN.md")
    ]
    assert english_documents
    for english in english_documents:
        chinese = english.with_name(f"{english.stem}.zh-CN.md")
        assert chinese.is_file(), f"missing Simplified Chinese edition for {english}"
        assert chinese.name in _markdown_links(english)
        assert english.name in _markdown_links(chinese)


def test_relative_markdown_links_resolve() -> None:
    documents = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
    documents.extend(sorted((ROOT / "docs").glob("*.md")))
    for document in documents:
        for target in _markdown_links(document):
            if "://" in target or target.startswith("#"):
                continue
            target_path = (document.parent / target.split("#", 1)[0]).resolve()
            assert target_path.exists(), f"broken link in {document}: {target}"
