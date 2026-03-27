import argparse
import re
import sys
import warnings
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import markdown
import ebooklib
from ebooklib import epub
from PIL import Image


@dataclass
class Chapter:
    title: str
    html_body: str
    images: dict[str, bytes]


def parse_args() -> argparse.Namespace:
    ...


def extract_chapter_title(md_text: str, filename: str) -> str:
    ...


def collect_images(html: str, source_dir: Path) -> dict[str, bytes]:
    ...


def md_file_to_chapter(md_path: Path) -> Chapter:
    ...


def build_epub(chapters: list[Chapter], args: argparse.Namespace) -> epub.EpubBook:
    ...


def main() -> None:
    ...


if __name__ == "__main__":
    main()
