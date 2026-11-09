"""Issue #150: attacking Encased in Ice must not grant it unit attributes."""
import contextlib
import io
import unittest
from unittest.mock import patch

from engine import Engine
from cards.database import CardsDB
from engine.file import Cache
from engine.log import Log
from game.card.face.card_type import Attachment, Minion
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestEncasedInIce(unittest.TestCase):
    def setUp(self):
        for name in ('papers', 'sets_cards', 'linked_papers', 'ability_cache',
                     'ability_link_cards', 'full_link_cards'):
            self.enterContext(patch.object(CardsDB, name, {}))
        self.enterContext(patch.object(Cache, 'link_pic', {}))
        initialize_database()

    def test_attacks_place_damage_and_break_ice_without_retaliate_errors(self):
        cases = (
            ('spider_man', False, 1, 2),
            ('she_hulk', False, 1, 3),
            ('spider_man', False, 2, 4),
            ('spider_man', True, 1, 8),
        )
        for timing in ('v18_timing', 'no_v18_timing'):
            for hero_name, event_attack, attack_count, total_damage in cases:
                with self.subTest(timing=timing, hero=hero_name, event=event_attack, damage=total_damage):
                    scene = SceneLoader.NewScene('rhino', None, [hero_name], 150)
                    scene.rules = ['v16_all', timing]
                    commands = iter([
                        'puzzle.ClearHand()',
                        'puzzle.ChangeFormFor(0, "Hero")',
                        'puzzle.CreateHandCards("01005", "01088", "01090")',
                        'puzzle.Reveal("54035")',
                    ])
                    attacks = 0
                    needs_ready = False
                    ice = None

                    def choose(prompt):
                        nonlocal attacks, needs_ready, ice
                        if len(devices.prompts) > 35:
                            raise AssertionError('Attack against Encased in Ice did not finish')
                        world = Engine.game.world
                        if prompt.event_name != 'WhenPlayerInTurn':
                            return CommandDescriptor() if prompt.show_cancel else devices._DefaultChoice(prompt)
                        command = next(commands, None)
                        hero = world.GetFirstPlayer().GetIdentity()
                        if needs_ready:
                            command = f'puzzle.Ready("{hero.paper.card_id}")'
                            needs_ready = False
                        if command:
                            Engine.game.controller_manager.console.SetCommand(command, world)
                            return CommandDescriptor()
                        if attacks == attack_count:
                            return None
                        ice = world.FindCardsOnField(name='54035')[0]
                        self.assertIsInstance(ice, Attachment)
                        self.assertTrue(Minion.IsType(ice))
                        self.assertIs(ice.GetBindFace(), hero)
                        basic_attack = next(option for option in prompt.options
                                            if option['bind_id'] == hero.card.object_id and option['name'] == 'Attack')
                        self.assertEqual(basic_attack['all_legal_targets'], [ice.card.object_id])
                        option = basic_attack
                        payments = []
                        if event_attack:
                            event = world.GetFirstPlayer().hand_cards.FindCard(name='01005')
                            option = next(option for option in prompt.options
                                          if option['bind_id'] == event.card.object_id and option['name'] == 'Play')
                            payments = [str(effect_id)
                                        for target in option['target_payment'].values()
                                        for group in target['payment']
                                        for effect_id in group]
                        attacks += 1
                        needs_ready = True
                        return CommandDescriptor(devices._DescriptorId(option),
                                                 [str(ice.card.object_id)], payments)

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
                    self.assertEqual(attacks, attack_count)
                    self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
                    self.assertEqual(game.world.event_manager.timing_occurrences, [])
                    hero = game.world.GetFirstPlayer().GetHero()
                    self.assertEqual(hero.health, hero.max_health - max(0, total_damage - 3))
                    basic_attack = next(option for option in devices.stopped_prompt.options
                                        if option['bind_id'] == hero.card.object_id and option['name'] == 'Attack')
                    if total_damage < 3:
                        self.assertTrue(ice.IsInPlay())
                        self.assertEqual(ice.GetCounters('damage'), total_damage)
                        self.assertEqual(basic_attack['all_legal_targets'], [ice.card.object_id])
                    else:
                        self.assertFalse(ice.IsInPlay())
                        self.assertIsNotNone(game.world.scenario.encounter_discard_pile.FindCard(name='54035'))
                        villain = game.world.GetScenario().area_villain.Get()[0]
                        self.assertIn(villain.card.object_id, basic_attack['all_legal_targets'])


if __name__ == '__main__':
    unittest.main()
