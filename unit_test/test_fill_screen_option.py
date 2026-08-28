from pathlib import Path
import unittest


class TestFillScreenOption(unittest.TestCase):

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_scene_setup_offers_the_fill_screen_option(self):
        html = (self.project_root / "public" / "scene.html").read_text(encoding="utf-8")

        self.assertIn('<input type="checkbox" id="fill_screen">Fill Screen', html)
        self.assertIn("getOption('#fill_screen', '&fill_screen')", html)
        self.assertIn("'scene_3d', 'fill_screen'", html)

    def test_the_setting_reads_the_fill_screen_parameter(self):
        settings = (
            self.project_root / "public" / "js" / "marvel" / "settings.ts"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "static fill_screen: boolean = search_params.has('fill_screen')",
            settings,
        )

    def test_the_stage_width_follows_the_viewport_without_letterboxing(self):
        fill_screen = (
            self.project_root / "public" / "js" / "marvel" / "fill-screen.ts"
        ).read_text(encoding="utf-8")
        marvel = (
            self.project_root / "public" / "js" / "marvel" / "marvel.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("document.documentElement.style.setProperty('--scene-width'", fill_screen)
        self.assertIn("adjustSceneScale()", fill_screen)
        self.assertIn("MoveCard.doMoveFirstTime()", fill_screen)
        self.assertIn("FillScreen.init()", marvel)

    def test_the_right_hand_cluster_is_anchored_to_the_right_edge(self):
        fill_screen = (
            self.project_root / "public" / "js" / "marvel" / "fill-screen.ts"
        ).read_text(encoding="utf-8")

        for selector, x in (
            ("#area-schemes-main", 1880),
            ("#area-schemes-side", 1880),
            ("#victory-display", 1250),
            ("#removed-pool", 1400),
            ("#area-removed", 1400),
            ("#nemesis-pool", 1550),
            ("#area-advanced", 1700),
        ):
            self.assertIn(f"'{selector}': {x},", fill_screen)

        self.assertIn("element.style.setProperty('--x', String(x))", fill_screen)
        self.assertNotIn("calc(var(--scene-width)", fill_screen)

    def test_the_right_side_bar_is_opened_by_its_handle_on_touch(self):
        mobile_ts = (
            self.project_root / "public" / "js" / "marvel" / "mobile.ts"
        ).read_text(encoding="utf-8")
        mobile_css = (
            self.project_root / "public" / "css" / "marvel" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn("document.getElementById('right-side-bar-handle')", mobile_ts)
        self.assertIn("side_bar.classList.toggle('touch-open')", mobile_ts)
        self.assertIn("side_bar.classList.remove('touch-open')", mobile_ts)
        self.assertIn("body.is-touch #right-side-bar.touch-open", mobile_css)
        self.assertNotIn("body.is-touch #right-side-bar {", mobile_css)


if __name__ == "__main__":
    unittest.main()
