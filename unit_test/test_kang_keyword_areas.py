from pathlib import Path
import unittest
from unittest.mock import patch

from engine import Engine  # noqa: F401 - establishes project import order
from game.card.face.attribute.can_attack import AttackProperty
from game.operate.worlds import Worlds
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import (
    initialize_database,
    run_scene_with_devices,
    validate_file,
)


SAVE = Path(__file__).parent / "fixtures" / "issue116_kang_stage_two.json"


class TestKangKeywordAreas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_commands(self, commands):
        scene = validate_file(SAVE)
        # The reported checkpoint's Kang has Tough; remove it so the tests
        # measure Retaliate damage and its Ranged/ignore exceptions directly.
        commands = [
            'Worlds.FindVillainByGameArea(p.GetGameArea()).DiscardAllTough(DebugRule(hero))',
            *commands,
        ]
        command_index = 0

        def choose(prompt):
            nonlocal command_index
            if prompt.event_name == "WhenPlayerInTurn":
                if command_index == len(commands):
                    return None
                command = commands[command_index]
                command_index += 1
                Engine.game.controller_manager.console.SetCommand(
                    command,
                    Engine.game.world,
                )
                return CommandDescriptor()
            # Decline optional responses and leave attacks undefended.
            if prompt.show_cancel:
                return CommandDescriptor()
            return HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        # Expose the real attack property type to the development console.
        with patch(
            "game.world.cheat.cheat_cmd_helper.AttackProperty",
            AttackProperty,
            create=True,
        ):
            game = run_scene_with_devices(scene, devices, load_type="InTesting")
        self.assertEqual(command_index, len(commands))
        self.assertIsNotNone(devices.stopped_prompt)
        self.assertEqual(devices.stopped_prompt.event_name, "WhenPlayerInTurn")
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        captain, wolverine = game.world.const_players
        self.assertNotEqual(captain.GetGameArea(), game.world.GetFirstGameArea())
        self.assertNotEqual(captain.GetGameArea(), wolverine.GetGameArea())
        return game, devices

    @staticmethod
    def attack_command(**properties):
        properties = {"do_not_give_boost": True, **properties}
        arguments = ", ".join(f"{key}={value!r}" for key, value in properties.items())
        return (
            'Worlds.FindVillainByGameArea(p.GetGameArea()).DoAttackYou('
            'p, DebugRule(hero), '
            f'property=AttackProperty({arguments}))'
        )

    def test_retaliate_two_damages_only_the_attacker_in_kang_stage_two(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                # Replay the checkpoint in its recorded timing mode, then
                # compare the same split-area attack in each dispatcher.
                game, _ = self.run_commands([
                    f'world.rule.v18_timing.Set({not legacy!r})',
                    'puzzle.PutIntoPlayFor(0, "03009")',
                    'puzzle.Tough("03001a")',
                    self.attack_command(),
                ])
                captain, wolverine = game.world.const_players
                captain_kang = Worlds.FindVillainByGameArea(captain.GetGameArea())
                wolverine_kang = Worlds.FindVillainByGameArea(wolverine.GetGameArea())

                self.assertEqual(bool(game.world.rule.v18_timing), not legacy)
                self.assertEqual(captain.GetIdentity().retaliate, 2)
                self.assertEqual(captain.GetIdentity().health, 9)
                self.assertEqual(captain_kang.health, 16)
                self.assertEqual(wolverine_kang.health, 18)

    def test_ranged_and_ignore_retaliate_attacks_skip_the_response_in_split_area(self):
        for properties in ({"ranged": True}, {"ignore_retaliate": True}):
            with self.subTest(properties=properties):
                game, _ = self.run_commands([
                    'puzzle.PutIntoPlayFor(0, "03009")',
                    'puzzle.Tough("03001a")',
                    self.attack_command(**properties),
                ])
                captain = game.world.const_players[0]
                kang = Worlds.FindVillainByGameArea(captain.GetGameArea())
                self.assertEqual(captain.GetIdentity().retaliate, 2)
                self.assertEqual(kang.health, 18)

    def test_vulnerable_discards_only_the_stunned_minion_in_split_area(self):
        game, _ = self.run_commands([
            'CardFactory.GenerateCard("60182", world.aside_deck, world).face.PutIntoPlay('
            'p1, DebugRule(p1.GetIdentity()), target_game_area=p1.GetGameArea())',
            'puzzle.PutIntoPlay("60182")',
            'puzzle.Stun("60182")',
        ])
        cops = game.world.FindCardsOnField(name="Cop")
        self.assertEqual(len(cops), 1)
        self.assertEqual(cops[0].card.GetGameArea(), game.world.const_players[1].GetGameArea())
        self.assertIn("60182", [
            face.paper.card_id
            for face in game.world.scenario.encounter_discard_pile.Get()
        ])
        self.assertFalse(any(
            face.name == "Stunned"
            for face in game.world.FindCardsOnField()
        ))


if __name__ == "__main__":
    unittest.main()
