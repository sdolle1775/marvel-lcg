from pathlib import Path
import unittest


class TestTouchSupport(unittest.TestCase):

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def mobile(self) -> str:
        return (
            self.project_root / "public" / "js" / "marvel" / "mobile.ts"
        ).read_text(encoding="utf-8")

    def test_touch_support_starts_with_the_interface(self):
        marvel = (
            self.project_root / "public" / "js" / "marvel" / "marvel.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("import { Mobile } from './mobile.js';", marvel)
        self.assertIn("Mobile.init()", marvel)

    def test_touch_styling_is_only_loaded_on_a_touch_device(self):
        mobile = self.mobile

        self.assertIn("window.matchMedia('(pointer: coarse)').matches", mobile)
        self.assertIn('Lib.loader.loadCSS("./css./marvel./mobile.css")', mobile)
        self.assertIn("document.body.classList.add('is-touch')", mobile)

    def test_a_tap_selects_and_only_a_hold_previews(self):
        mobile = self.mobile

        self.assertIn("static readonly LONG_PRESS_MS = 350", mobile)
        self.assertIn("static readonly MOVE_CANCEL_PX = 12", mobile)
        self.assertIn("Mobile.last_pointer_touch && !Mobile.preview_active", mobile)
        self.assertIn("event.stopImmediatePropagation()", mobile)

    def test_a_mouse_on_a_touch_screen_keeps_the_desktop_preview(self):
        mobile = self.mobile

        self.assertIn("Mobile.last_pointer_touch = (event.pointerType === 'touch')", mobile)
        self.assertIn("if (!Mobile.last_pointer_touch || Mobile.flushing)", mobile)

    def test_the_fullscreen_button_joins_the_right_side_bar(self):
        mobile = self.mobile
        css = (
            self.project_root / "public" / "css" / "marvel" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn("document.getElementById('right-side-bar')", mobile)
        self.assertIn("orientation.lock('landscape')", mobile)
        self.assertIn("body.is-touch #mobile-fullscreen-btn", css)
        self.assertIn("body.is-touch.is-portrait:not(.is-fullscreen) #rotate-overlay", css)

    def test_the_latched_hover_layout_is_cancelled_on_touch_only(self):
        css = (
            self.project_root / "public" / "css" / "marvel" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn("@media (hover: none)", css)
        self.assertIn("body.is-touch .card:hover:not(.activating):not(.selected)", css)
        self.assertIn("body.is-touch:not(.scene-3d) .card", css)


if __name__ == "__main__":
    unittest.main()
