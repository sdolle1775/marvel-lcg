import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import call, patch

from engine import Engine
from engine.lib import Ver
from engine.log import Log, Notify
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import (
    initialize_database,
    run_scene_with_devices,
    validate_file,
)
from game.world.world_render import WorldRender


class TestSenseLastThreat(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_reported_save_offers_acute_tactility_during_superior_taste(self):
        # The checkpoint keeps the reported choices through Superior Taste,
        # with CRCs and earlier Sense triggers updated for the fixes, including
        # enemy-defeat interrupts before When Defeated abilities (#107).
        scene = validate_file(Path(__file__).parent / "fixtures" / "issue_99_sense_interrupt.json")
        expected_crcs = [operation.crc for operation in scene.inputs]
        devices = HeadlessDeviceManager(stop_when=lambda prompt: True)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(WorldRender, "ErrorOccurred") as errors,
            patch.object(Log, "Warn") as warnings,
            patch.object(Notify, "Game") as notices,
        ):
            game = run_scene_with_devices(scene, devices, load_type="InTesting")

        errors.assert_not_called()
        expected_warnings = [call("VERSION", f"Version {scene.version} is lower than last version {Ver.version}")] \
            if Ver(scene.version) < Ver.version else []
        self.assertEqual(warnings.call_args_list, expected_warnings)
        notices.assert_not_called()
        self.assertEqual(game.controller_manager.replay.current_step_id, 63)
        self.assertEqual(
            [operation.crc for operation in game.controller_manager.replay.history_inputs],
            expected_crcs,
        )
        prompt = devices.stopped_prompt
        self.assertEqual(prompt.event_name, "WhenSchemeWouldRemoveThreat")
        self.assertEqual(prompt.ability_type, "Interrupt")
        self.assertEqual([option["bind_id"] for option in prompt.options], [2])
        self.assertIn("Acute_Tactility", prompt.options[0]["name"])
        self.assertTrue(game.world.GetFirstPlayer().GetIdentity().IsExhaust())
        sense = game.world.object_manager.card_dict[2].face
        self.assertEqual(sense.GetBindFace().paper.card_id, "60012")
        self.assertEqual(sense.GetBindFace().threat, 2)

    def test_sense_interrupt_precedes_defeat_and_is_available_to_put_back_into_play(self):
        for timing in ("v18_timing", "no_v18_timing"):
            for sense_id in ("60002", "60003"):
                with self.subTest(timing=timing, sense=sense_id):
                    scene = SceneLoader.NewScene("rhino", None, ["daredevil"], 99)
                    scene.rules = ["v16_all", timing]
                    commands = iter((
                        'puzzle.ClearHand()',
                        'puzzle.ChangeFormFor(0, "Hero")',
                        'puzzle.PutIntoPlay("60012")',
                        'puzzle.FindOrCreateFace("60012").SetTokens(2, "threat", DebugRule(hero))',
                        f'p.additional_deck.FindCard(name="{sense_id}").PutIntoPlay(p, DebugRule(hero))',
                    ))
                    thwarted = False
                    interrupt = None
                    put_into_play = None

                    def choose(prompt):
                        nonlocal thwarted, interrupt, put_into_play
                        world = Engine.game.world
                        player = world.GetFirstPlayer()
                        focus = next(iter(world.FindCardsOnField(name="Focus the Senses")), None)
                        if prompt.event_name == "WhenPlayerInTurn":
                            command = next(commands, None)
                            if command:
                                Engine.game.controller_manager.console.SetCommand(command, world)
                                return CommandDescriptor()
                            if thwarted:
                                return None
                            thwarted = True
                            option = next(option for option in prompt.options if option["name"] == "Thwart")
                            return CommandDescriptor(
                                HeadlessDeviceManager._DescriptorId(option),
                                [str(focus.card.object_id)], [],
                            )
                        for option in prompt.options:
                            source = world.object_manager.card_dict.get(option["bind_id"])
                            if (
                                thwarted and source and source.face.paper.card_id == sense_id
                                and prompt.ability_type == "Interrupt"
                            ):
                                interrupt = (prompt.event_name, focus.threat, player.GetIdentity().IsExhaust())
                                return CommandDescriptor(
                                    HeadlessDeviceManager._DescriptorId(option),
                                    [str(target) for target in option["all_legal_targets"]], [],
                                )
                            if option["name"] == "Choose_Sense_upgrades_to_put_into_play":
                                put_into_play = option
                                return None
                            if not thwarted and focus and focus.card.object_id in option["all_legal_targets"]:
                                return CommandDescriptor(
                                    HeadlessDeviceManager._DescriptorId(option),
                                    [str(focus.card.object_id)], [],
                                )
                        return HeadlessDeviceManager._DefaultChoice(prompt)

                    devices = HeadlessDeviceManager(choice_provider=choose)
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        patch.object(WorldRender, "ErrorOccurred") as errors,
                    ):
                        game = run_scene_with_devices(scene, devices)

                    errors.assert_not_called()
                    self.assertEqual(interrupt, ("WhenSchemeWouldRemoveThreat", 2, True))
                    self.assertIsNotNone(put_into_play)
                    player = game.world.GetFirstPlayer()
                    sense = player.additional_deck.FindCard(name=sense_id)
                    self.assertIsNotNone(sense)
                    self.assertIn(sense.card.object_id, put_into_play["all_legal_targets"])
                    if sense_id == "60002":
                        self.assertFalse(player.GetIdentity().IsExhaust())


if __name__ == "__main__":
    unittest.main()
