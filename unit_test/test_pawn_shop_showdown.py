import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import call, patch

from engine import Engine
from engine.lib import Ver
from engine.log import Log, Notify
from game.card.face import Upgrade
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices, validate_file
from game.world.world_render import WorldRender


FIXTURE = Path(__file__).parent / "fixtures" / "issue_105_pawn_shop_showdown.json"


class TestPawnShopShowdown(unittest.TestCase):
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
        expected_warnings = [call("VERSION", f"Version {scene.version} is lower than last version {Ver.version}")] \
            if Ver(scene.version) < Ver.version else []
        self.assertEqual(warnings.call_args_list, expected_warnings)
        notices.assert_not_called()
        self.assertIsNotNone(devices.stopped_prompt)
        self.assertEqual(devices.stopped_prompt.event_name, "WhenPlayerInTurn")
        return game

    def option(self, prompt, card_id):
        return next(option for option in prompt.options
                    if option["name"] == "Play" and
                    Engine.game.world.object_manager.card_dict[option["bind_id"]].face.paper.card_id == card_id)

    def payment(self, prompt, card_id, player_id=0, *, target=None):
        option = self.option(prompt, card_id)
        target = target or Engine.game.world.const_seat_order_players[player_id].GetIdentity()
        payments = option["target_payment"]
        return payments.get(str(target.card.object_id), payments.get("0"))

    def play(self, prompt, card_id, player_id=0, *, target=None):
        option = self.option(prompt, card_id)
        target = target or Engine.game.world.const_seat_order_players[player_id].GetIdentity()
        payment = self.payment(prompt, card_id, player_id, target=target)
        resources = []
        if int(payment["cost"]) > 0:
            # Every resource in these fixtures generates two resources.
            resources = [str(next(iter(entry))) for entry in payment["payment"]
                         if next(iter(entry.values())) in ("RR", "BB", "YY")][:1]
            self.assertTrue(resources)
        return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                 [str(target.card.object_id)], resources)

    def run_actions(self, timing, actions, *, players=1, extra_setup=()):
        scene = SceneLoader.NewScene("rhino", None, ["spider_man", "captain_marvel"][:players], 105)
        scene.rules = ["v16_all", timing]
        scene.campaign.schemes = ["60137a,60137b", "60135a,60135b"][:players]
        setup = iter([
            'puzzle.ChangeFormFor(0, "Hero")',
            *[f'puzzle.ClearHandFor({i})' for i in range(players)],
            'puzzle.CreateHandCardsFor(0, "01081", "01057", "01065", "01088", "01089", "01090")',
            'puzzle.CreateEncounterDeck("01189", "01189", "01189")',
            *extra_setup,
        ])
        actions = iter(actions)

        def choose(prompt):
            if len(devices.prompts) > 60:
                self.fail("Unexpected repeated prompt")
            if prompt.event_name == "WhenPlayerInTurn":
                command = next(setup, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, Engine.game.world)
                    return CommandDescriptor()
                action = next(actions, None)
                return action(prompt) if action else None
            if prompt.show_cancel:
                return CommandDescriptor()
            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        return self.run_game(scene, devices)

    def test_reported_save_restores_and_second_upgrades_pay_full_cost(self):
        scene = validate_file(FIXTURE)
        devices = HeadlessDeviceManager(stop_when=lambda prompt: True)
        game = self.run_game(scene, devices, load_type="InTesting")
        self.assertEqual(game.controller_manager.replay.current_step_id, 65)
        self.assertEqual([op.crc for op in game.controller_manager.replay.history_inputs],
                         [op.crc for op in scene.inputs])
        self.assertEqual([face.paper.card_id for face in game.world.GetFirstPlayer().stat.this_round_played_cards],
                         ["60052"])
        upgrades = 0
        for option in devices.stopped_prompt.options:
            face = game.world.object_manager.card_dict[option["bind_id"]].face
            if option["name"] == "Play" and Upgrade.IsType(face):
                upgrades += 1
                self.assertEqual({p["cost"] for p in option["target_payment"].values()},
                                 {face.printed_cost.text_legacy}, face.name)
        self.assertGreater(upgrades, 1)

    def test_discount_is_consumed_by_play_and_returns_next_round(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                def first(prompt):
                    self.assertEqual(self.payment(prompt, "01081")["cost"], "0")
                    self.assertEqual(self.payment(prompt, "01057")["cost"], "1")
                    return self.play(prompt, "01081")

                def second(prompt):
                    self.assertEqual(self.payment(prompt, "01057")["cost"], "2")
                    return self.play(prompt, "01057")

                def end_turn(prompt):
                    self.assertEqual(self.payment(prompt, "01065")["cost"], "2")
                    return CommandDescriptor()

                def next_round(prompt):
                    self.assertEqual(self.payment(prompt, "01065")["cost"], "1")
                    return None

                self.run_actions(timing, [first, second, end_turn, next_round])

    def test_discount_follows_destination_and_another_area_does_not_consume_it(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                def elsewhere(prompt):
                    self.assertEqual(self.payment(prompt, "01081", 0)["cost"], "0")
                    self.assertEqual(self.payment(prompt, "01081", 1)["cost"], "1")
                    return self.play(prompt, "01081", 1)

                def first_here(prompt):
                    self.assertEqual(self.payment(prompt, "01057", 0)["cost"], "1")
                    self.assertEqual(self.payment(prompt, "01057", 1)["cost"], "2")
                    return self.play(prompt, "01057", 0)

                def consumed(prompt):
                    self.assertEqual(self.payment(prompt, "01065", 0)["cost"], "2")
                    return None

                self.run_actions(timing, [elsewhere, first_here, consumed], players=2)

    def test_put_into_play_does_not_consume_discount_but_printed_zero_cost_play_does(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                def zero_cost(prompt):
                    self.assertEqual(self.payment(prompt, "01057")["cost"], "1")
                    option = self.option(prompt, "48015")
                    minion = Engine.game.world.object_manager.card_dict[option["all_legal_targets"][0]].face
                    return self.play(prompt, "48015", target=minion)

                def consumed(prompt):
                    self.assertEqual(self.payment(prompt, "01057")["cost"], "2")
                    scheme = Engine.game.world.area_schemes_main.Get()[0]
                    # Both entry methods still trigger the printed threat response.
                    self.assertEqual(scheme.threat, 2)
                    return None

                self.run_actions(timing, [zero_cost, consumed], extra_setup=(
                    'puzzle.PutIntoPlayFor(0, "01081")',
                    'puzzle.PutIntoPlayFor(0, "01102")',
                    'puzzle.CreateHandCardsFor(0, "48015")',
                ))

    def test_another_player_can_use_the_shared_discount_only_once(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                def end_first_turn(prompt):
                    return CommandDescriptor()

                def first_upgrade(prompt):
                    self.assertEqual(prompt.player_id, 1)
                    self.assertEqual(self.payment(prompt, "01057", 0)["cost"], "1")
                    self.assertEqual(self.payment(prompt, "01057", 1)["cost"], "2")
                    return self.play(prompt, "01057", 0)

                def second_upgrade(prompt):
                    self.assertEqual(self.payment(prompt, "01065", 0)["cost"], "2")
                    return None

                self.run_actions(timing, [end_first_turn, first_upgrade, second_upgrade], players=2,
                                 extra_setup=(
                                     'puzzle.CreateHandCardsFor(1, "01057", "01065", "01088")',
                                 ))

    def test_iron_man_keeps_his_own_discount_after_pawn_shop_is_used(self):
        for timing in ("v18_timing", "no_v18_timing"):
            with self.subTest(timing=timing):
                def first_upgrade(prompt):
                    return self.play(prompt, "01081")

                def iron_man_discount(prompt):
                    option = self.option(prompt, "01074")
                    targets = {Engine.game.world.object_manager.card_dict[target].face.paper.card_id:
                               Engine.game.world.object_manager.card_dict[target].face
                               for target in option["all_legal_targets"]}
                    self.assertEqual(self.payment(prompt, "01074", target=targets["09039"])["cost"], "0")
                    self.assertEqual(self.payment(prompt, "01074", target=targets["01067"])["cost"], "1")
                    return self.play(prompt, "01074", target=targets["09039"])

                self.run_actions(timing, [first_upgrade, iron_man_discount], extra_setup=(
                    'puzzle.PutIntoPlayFor(0, "09039")',
                    'puzzle.PutIntoPlayFor(0, "01067")',
                    'puzzle.CreateHandCardsFor(0, "01074")',
                ))


if __name__ == "__main__":
    unittest.main()
