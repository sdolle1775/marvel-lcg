"""Issue #149: MACH-IV restricts basic defenses, not defense events."""
import contextlib
import io
import unittest
from unittest.mock import patch

from engine import Engine
from cards.database import CardsDB
from engine.file import Cache
from engine.log import Log
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestMachIV(unittest.TestCase):
    def setUp(self):
        for name in ('papers', 'sets_cards', 'linked_papers', 'ability_cache',
                     'ability_link_cards', 'full_link_cards'):
            self.enterContext(patch.object(CardsDB, name, {}))
        self.enterContext(patch.object(Cache, 'link_pic', {}))
        initialize_database()

    def run_attack(self, *, timing, hero='spider_man', exhausted=False,
                   payment='01088', basic_defender=None):
        scene = SceneLoader.NewScene('rhino', None, [hero], 149)
        scene.rules = ['v16_all', timing]
        commands = iter([
            'puzzle.ClearHand()',
            'puzzle.ChangeFormFor(0, "Hero")',
            'puzzle.PutIntoPlay("50156")',
            'puzzle.PutIntoPlay("03011")',
            'puzzle.PutIntoPlay("01002")',
            'puzzle.PlaceThreat("01097b", 4)',
            f'puzzle.CreateHandCards("27014", "{payment}")',
            *(['puzzle.Exhaust("01001a")'] if exhausted else []),
            # One boost icon makes the attack deal 3 damage before prevention.
            'puzzle.CreateEncounterDeck("01189")',
            'puzzle.DoAttack("50156")',
        ])
        basic_options = set()
        played = False

        def choose(prompt):
            nonlocal played
            if len(devices.prompts) > 45:
                raise AssertionError('MACH-IV attack did not finish')
            world = Engine.game.world
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(commands, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                return None
            if prompt.event_name == 'WhenUnitBeingAttack':
                for option in prompt.options:
                    card_id = world.object_manager.card_dict[option['bind_id']].face.paper.card_id
                    basic_options.add(card_id)
                    if card_id == basic_defender:
                        return CommandDescriptor(devices._DescriptorId(option))
                return CommandDescriptor()
            if prompt.event_name == 'WhenUnitWouldTakeDamage' and basic_defender is None:
                hand = world.GetFirstPlayer().hand_cards.Get()
                jump_flip = next(face for face in hand if face.paper.card_id == '27014')
                option = next(option for option in prompt.options
                              if option['bind_id'] == jump_flip.card.object_id)
                payments = [str(effect_id)
                            for target in option['target_payment'].values()
                            for group in target['payment']
                            for effect_id, resources in group.items()
                            if resources == ('YY' if payment == '01088' else 'RR')]
                self.assertTrue(payments)
                played = True
                return CommandDescriptor(devices._DescriptorId(option), [], payments[:1])
            if prompt.event_name == 'WhenPlayerChooseAbility' and played:
                return devices._DefaultChoice(prompt)
            return CommandDescriptor() if prompt.show_cancel else devices._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (contextlib.redirect_stdout(io.StringIO()),
              patch('game.test.v18_timing_harness.initialize_database'),
              patch.object(WorldRender, 'ErrorOccurred') as errors,
              patch.object(Engine, 'SaveCrash') as crashes,
              patch.object(Log, 'Warn') as warnings):
            game = run_scene_with_devices(scene, devices)
        errors.assert_not_called()
        crashes.assert_not_called()
        warnings.assert_not_called()
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        return game, basic_options, played

    def test_jump_flip_prevents_damage_without_aerial_or_basic_defense(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for exhausted in (False, True):
                for payment in ('01088', '01090'):
                    with self.subTest(timing=timing, exhausted=exhausted, payment=payment):
                        game, basic_options, played = self.run_attack(
                            timing=timing, exhausted=exhausted, payment=payment,
                        )
                        self.assertTrue(played)
                        self.assertIn('03011', basic_options)  # Aerial Falcon can defend.
                        self.assertNotIn('01001a', basic_options)
                        self.assertNotIn('01002', basic_options)
                        player = game.world.GetFirstPlayer()
                        hero = player.GetHero()
                        self.assertEqual(hero.health, hero.max_health - 1)
                        self.assertEqual(hero.IsExhaust(), exhausted)
                        discarded = [face.paper.card_id for face in player.discard_pile.Get()]
                        self.assertIn('27014', discarded)
                        self.assertIn(payment, discarded)
                        scheme = game.world.FindCardsOnField(name='01097b')[0]
                        self.assertEqual(scheme.threat, 2 if payment == '01088' else 4)

    def test_aerial_hero_can_make_a_basic_defense(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            with self.subTest(timing=timing):
                game, basic_options, played = self.run_attack(
                    timing=timing, hero='angel', basic_defender='42001a',
                )
                self.assertIn('42001a', basic_options)
                self.assertFalse(played)
                hero = game.world.GetFirstPlayer().GetHero()
                self.assertTrue(hero.IsExhaust())
                self.assertEqual(hero.health, hero.max_health - 1)
                self.assertEqual(game.world.FindCardsOnField(name='01097b')[0].threat, 4)


if __name__ == '__main__':
    unittest.main()
