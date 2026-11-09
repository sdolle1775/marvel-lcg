from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from engine import Engine
from game.world.world import World


def live_world(**overrides):
    world = SimpleNamespace(
        scene=SimpleNamespace(is_puzzle=False),
        controller_manager=SimpleNamespace(
            replay=SimpleNamespace(is_replay=False),
            skip=SimpleNamespace(is_skipping=False),
        ),
    )
    for name, value in overrides.items():
        setattr(world, name, value)
    return world


class TestAutoSaveOnRoundStart(unittest.TestCase):

    def _run(self, world, *, testing=False, save_error=None, statistics_error=None,
             auto_save_enabled=True):
        game = SimpleNamespace(session=SimpleNamespace(
            auto_save_enabled=auto_save_enabled,
            SaveScene=Mock(
                return_value="auto_save.json",
                side_effect=save_error,
            ),
        ))
        statistics = SimpleNamespace(Save=Mock(side_effect=statistics_error))
        with (
            patch("game.test.test.Test.IsInTesting", return_value=testing),
            patch.object(Engine, "in_unit_test", False),
            patch.object(Engine, "statistics", statistics, create=True),
            patch.object(Engine, "game", game, create=True),
        ):
            World.AutoSaveOnRoundStart(world)
        return game, statistics

    def test_live_round_writes_auto_save_json(self):
        game, statistics = self._run(live_world())

        statistics.Save.assert_called_once_with()
        game.session.SaveScene.assert_called_once_with(
            name="auto_save.json",
            delete_old=False,
        )

    def test_disabled_auto_save_does_not_write(self):
        game, statistics = self._run(live_world(), auto_save_enabled=False)

        statistics.Save.assert_not_called()
        game.session.SaveScene.assert_not_called()

    def test_save_failure_does_not_propagate(self):
        game, statistics = self._run(
            live_world(),
            statistics_error=OSError("disk full"),
        )

        statistics.Save.assert_called_once_with()
        game.session.SaveScene.assert_not_called()

    def test_scene_save_failure_does_not_propagate(self):
        game, statistics = self._run(
            live_world(),
            save_error=OSError("locked"),
        )

        statistics.Save.assert_called_once_with()
        game.session.SaveScene.assert_called_once_with(
            name="auto_save.json",
            delete_old=False,
        )

    def test_skips_replay_fast_forward_puzzle_and_tests(self):
        skipping = live_world()
        skipping.controller_manager.skip.is_skipping = True
        replaying = live_world()
        replaying.controller_manager.replay.is_replay = True
        puzzle = live_world()
        puzzle.scene.is_puzzle = True

        for world, testing in (
            (skipping, False),
            (replaying, False),
            (puzzle, False),
            (live_world(), True),
        ):
            with self.subTest(world=world, testing=testing):
                game, statistics = self._run(world, testing=testing)
                statistics.Save.assert_not_called()
                game.session.SaveScene.assert_not_called()

    def test_round_start_and_log_menu_are_wired(self):
        project_root = Path(__file__).resolve().parents[1]
        world_source = (project_root / "game" / "world" / "world.py").read_text(
            encoding="utf-8"
        )
        buttons_source = (
            project_root / "public" / "js" / "marvel" / "buttons.ts"
        ).read_text(encoding="utf-8")
        settings_source = (
            project_root / "public" / "js" / "marvel" / "settings.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("self.round_id += 1", world_source)
        self.assertIn("self.AutoSaveOnRoundStart()", world_source)
        self.assertIn("auto_save_enabled", world_source)
        self.assertIn('text: "Load Auto-Save"', buttons_source)
        self.assertIn('Button.doLoadSave("auto_save.json")', buttons_source)
        self.assertIn("Button.doLoadSave(`save_${solt}.json`)", buttons_source)
        self.assertIn("static auto_save = 1", settings_source)
        pause_button = buttons_source.index('text: "Auto Pause"')
        auto_save_button = buttons_source.index('text: "Auto Save"')
        self.assertLess(pause_button, auto_save_button)
        self.assertIn("cookie_name: 'btn_auto_save'", buttons_source)
