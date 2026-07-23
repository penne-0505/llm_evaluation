"""UI font CSS references must resolve to tracked public assets."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "frontend" / "src" / "index.css"
FONTS_DIR = ROOT / "frontend" / "public" / "fonts"
LICENSE_PATH = FONTS_DIR / "UDEVGothic-LICENSE.txt"

FONT_URL_RE = re.compile(r"""url\(\s*['"]?/fonts/([^'")\s]+)['"]?\s*\)""")


class UiFontAssetContractTests(unittest.TestCase):
    def test_css_font_urls_resolve_to_tracked_files(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8")
        referenced = sorted(set(FONT_URL_RE.findall(css)))
        self.assertTrue(referenced, "index.css should reference at least one /fonts/ asset")

        missing = [name for name in referenced if not (FONTS_DIR / name).is_file()]
        self.assertEqual(
            missing,
            [],
            f"CSS font references missing under {FONTS_DIR.relative_to(ROOT)}: {missing}",
        )

    def test_udev_gothic_license_present_with_font_files(self) -> None:
        font_files = sorted(FONTS_DIR.glob("UDEVGothic*.ttf"))
        self.assertTrue(font_files, "expected UDEV Gothic TTF assets to be bundled")
        self.assertTrue(
            LICENSE_PATH.is_file(),
            f"missing license file: {LICENSE_PATH.relative_to(ROOT)}",
        )


if __name__ == "__main__":
    unittest.main()
