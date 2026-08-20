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
        css = (
            self.project_root / "public" / "css" / "marvel" / "fill-screen.css"
        ).read_text(encoding="utf-8")

        for offset in (40, 670, 520, 370, 220):
            self.assertIn(f"--x: calc(var(--scene-width) - {offset});", css)


if __name__ == "__main__":
    unittest.main()
