import contextlib
from importlib import import_module
import io
from pathlib import Path
import unittest
from unittest.mock import call, patch

from engine import Engine
from engine.lib import Ver
from engine.log import Log, Notify
from cards.database import CardsDB
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices, validate_file
from game.world.world_render import WorldRender


FIXTURE = Path(__file__).parent / "fixtures" / "issue_106_hung_out_to_dry.json"


class TestHungOutToDry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_game(self, scene, devices, *, load_type="New"):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(WorldRender, "ErrorOccurred") as errors,
            patch.object(Log, "Warn") as warnings,
            patch.object(Notify, "Game") as notices,
            patch.object(Engine, "SaveCrash"),
        ):
            game = run_scene_with_devices(scene, devices, load_type=load_type)
        errors.assert_not_called()
        notices.assert_not_called()
        expected_warnings = [call("VERSION", f"Version {scene.version} is lower than last version {Ver.version}")] \
            if Ver(scene.version) < Ver.version else []
        self.assertEqual(warnings.call_args_list, expected_warnings)
        self.assertIsNotNone(devices.stopped_prompt)
        self.assertEqual(devices.stopped_prompt.event_name, "WhenPlayerInTurn")
        return game

    def run_commands(self, timing, commands, *, players=1):
        scene = SceneLoader.NewScene("rhino", None, ["daredevil", "captain_marvel"][:players], 106)
        scene.rules = ["v16_all", timing]
        scene.campaign.schemes = ["60136a,60136b", "60135a,60135b"][:players]
        commands = iter(commands)
        snapshots = []

        def choose(prompt):
            if len(devices.prompts) > 45:
                self.fail("Unexpected repeated prompt")
            if prompt.event_name == "WhenPlayerInTurn":
                world = Engine.game.world
                player = world.GetFirstPlayer()
                scheme = next(face for face in world.area_schemes_main.Get()
                              if face.paper.card_id == "60136b")
                snapshots.append((player.GetIdentity().health, scheme.threat, player.IsHero()))
                command = next(commands, None)
                if command is None:
                    return None
                if command == "change_form":
                    option = next(option for option in prompt.options if option["name"] == "Change_Form")
                    return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option), [], [])
                Engine.game.controller_manager.console.SetCommand(command, world)
                return CommandDescriptor()
            if prompt.show_cancel:
                return CommandDescriptor()
            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = self.run_game(scene, devices)
        return game, snapshots

    def test_form_changes_in_both_directions_do_not_damage_or_add_threat(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                _, snapshots = self.run_commands(timing, [
                    "change_form",
                    'puzzle.ChangeFormFor(0, "Identity")',
                ])
                self.assertEqual([state[2] for state in snapshots], [False, True, False])
                self.assertEqual([state[:2] for state in snapshots], [snapshots[0][:2]] * 3)

    def test_actual_allies_and_minions_still_take_damage_and_add_threat(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                game, snapshots = self.run_commands(timing, [
                    'puzzle.PutIntoPlayFor(0, "01067")',
                    'puzzle.PutIntoPlayFor(0, "01172")',
                ])
                self.assertEqual([state[1] for state in snapshots],
                                 [snapshots[0][1], snapshots[0][1] + 1, snapshots[0][1] + 2])
                player = game.world.GetFirstPlayer()
                ally = player.allies.FindCard(name="01067")
                minion = max((face for face in player.GetEngagedMinions() if face.paper.card_id == "01172"),
                             key=lambda face: face.card.object_id)
                self.assertEqual(ally.health, ally.max_health - 1)
                self.assertEqual(minion.health, minion.max_health - 1)

    def test_characters_entering_another_players_area_do_not_trigger(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                game, snapshots = self.run_commands(timing, [
                    'puzzle.PutIntoPlayFor(1, "01067")',
                    'puzzle.PutIntoPlayFor(1, "01172")',
                ], players=2)
                self.assertEqual([state[1] for state in snapshots], [snapshots[0][1]] * 3)
                other = game.world.const_seat_order_players[1]
                ally = other.allies.FindCard(name="01067")
                minion = max((face for face in other.GetEngagedMinions() if face.paper.card_id == "01172"),
                             key=lambda face: face.card.object_id)
                self.assertEqual(ally.health, ally.max_health)
                self.assertEqual(minion.health, minion.max_health)

    def test_reported_form_change_preserves_seven_health_and_six_threat(self):
        # The checkpoint keeps the reported choices, with Sense defeat trigger
        # names updated for their corrected interrupt timing (#107).
        scene = validate_file(FIXTURE)
        # This save also relies on the historical Pawn Shop Showdown bug
        # (#105). Reproduce only that old discount during the recorded history
        # to reach the reported step; Hung Out to Dry uses its real abilities.
        pawn = import_module("cards.pack.fne.protection_racket.60137b")
        historical_discount = pawn.AbilityFactory.UpdateCostOfCardInternal(
            pawn.Upgrade, -1, "AnyPlayer", is_play=True,
            conditions=[lambda effect, message: message.GetToPlayer() == pawn.GetSchemeOwner(effect)],
        ).LimitOncePerRound()
        historical_pawn = [historical_discount, *pawn.GetAbilities()[1:]]
        devices = HeadlessDeviceManager(stop_when=lambda prompt: True)
        with patch.dict(CardsDB.ability_cache, {"60137b": historical_pawn}):
            game = self.run_game(scene, devices, load_type="InTesting")
        self.assertEqual(game.controller_manager.replay.current_step_id, 163)
        self.assertEqual([operation.crc for operation in game.controller_manager.replay.history_inputs],
                         [operation.crc for operation in scene.inputs])
        player = game.world.GetFirstPlayer()
        scheme = game.world.area_schemes_main.Get()[0]
        self.assertTrue(player.IsHero())
        self.assertEqual(player.GetIdentity().health, 7)
        self.assertEqual(scheme.paper.card_id, "60136b")
        self.assertEqual(scheme.threat, 6)


if __name__ == "__main__":
    unittest.main()
