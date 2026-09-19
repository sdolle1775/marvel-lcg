import contextlib
import io
from itertools import permutations
import unittest
from unittest.mock import patch

from engine import Engine
from engine.log import Log, Notify
from game.message import Message
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestWakandaStatusSequence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def resolve_sequence(self, order, *, stunned=False, confused=False, damage=3,
                         threat=3, timing='v18_timing', rules=None, steady=False,
                         extra_enemy=False):
        scene = SceneLoader.NewScene('rhino', None, ['black_panther'], 114)
        scene.rules = ['v16_all', timing] if rules is None else rules
        setup = iter([
            'puzzle.ClearHand()',
            'puzzle.ChangeFormFor(0, "Hero")',
            *[f'puzzle.PutIntoPlay("{card_id}")' for card_id in order],
            *(['puzzle.PutIntoPlay("01129")'] if extra_enemy else []),
            f'puzzle.Damage("01040a", {damage})',
            f'puzzle.SetThreat("01097b", {threat})',
            *(['hero.GainSteady(1, DebugRule(hero))'] if steady else []),
            *['hero.GainStatus("Stunned", DebugRule(hero))' for _ in range(stunned)],
            *['hero.GainStatus("Confused", DebugRule(hero))' for _ in range(confused)],
            'p.PlayCardsLikeInTurn([puzzle.FindOrCreateFace("01043a")], '
            'DebugRule(hero), ignore_resources_cost=True)',
        ])
        snapshots = []
        sequence_options = []
        special_send = Message.WhenResolveSpecialAbility.Send

        def snapshot():
            world = Engine.game.world
            hero = world.GetFirstPlayer().GetHero()
            return {
                'health': hero.health,
                'stunned': hero.IsStunned(),
                'confused': hero.IsConfused(),
                'stun_cards': hero.stunned,
                'confuse_cards': hero.confused,
                'villain_health': world.GetScenario().area_villain.Get()[0].health,
                'threat': world.area_schemes_main.Get()[0].threat,
            }

        def resolve_special(message):
            before = snapshot()
            result = special_send(message)
            snapshots.append((message.face.paper.card_id, before, snapshot()))
            return result

        def choose(prompt):
            if len(devices.prompts) > 35:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(setup, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, Engine.game.world)
                    return CommandDescriptor()
                return None
            if prompt.event_name == 'WhenPlayerLikeInTurn':
                option = next(option for option in prompt.options if option['name'] == 'Play')
                sequence_options.append(option)
                cards = Engine.game.world.object_manager.card_dict.values()
                targets = [next(card.object_id for card in cards
                                if card.face.paper.card_id == card_id and card.face.IsInPlay())
                           for card_id in order]
                return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                         [str(target) for target in targets], [])
            if prompt.event_name == 'WhenResolveSpecialAbility' and extra_enemy:
                option = prompt.options[0]
                villain_id = Engine.game.world.GetScenario().area_villain.Get()[0].card.object_id
                if villain_id in option['all_legal_targets']:
                    return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                             [str(villain_id)], [])
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch('game.test.v18_timing_harness.initialize_database'),
            patch.object(Message.WhenResolveSpecialAbility, 'Send', new=resolve_special),
            patch.object(WorldRender, 'ErrorOccurred') as errors,
            patch.object(Log, 'Warn') as warnings,
            patch.object(Notify, 'Game') as notices,
            patch.object(Engine, 'SaveCrash'),
        ):
            game = run_scene_with_devices(scene, devices)
        errors.assert_not_called()
        warnings.assert_not_called()
        notices.assert_not_called()
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        self.assertEqual([card_id for card_id, _, _ in snapshots], list(order))
        self.assertEqual(len(sequence_options), 1)
        self.assertEqual(sequence_options[0]['target_num_range'], [len(order), len(order)])
        self.assertEqual(len(sequence_options[0]['all_legal_targets']), len(order))
        return snapshots

    def test_stun_cancels_only_the_first_attack_in_either_order(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for order in (('01049', '01047'), ('01047', '01049')):
                with self.subTest(timing=timing, order=order):
                    snapshots = self.resolve_sequence(order, stunned=True, timing=timing)
                    _, before, after = snapshots[0]
                    self.assertTrue(before['stunned'])
                    self.assertFalse(after['stunned'])
                    self.assertEqual(after['health'], before['health'])
                    self.assertEqual(after['villain_health'], before['villain_health'])
                    _, before, after = snapshots[1]
                    self.assertEqual(after['villain_health'], before['villain_health'] -
                                     (4 if order[-1] == '01047' else 2))
                    self.assertEqual(after['health'], before['health'] +
                                     (2 if order[-1] == '01049' else 0))

    def test_non_attack_specials_do_not_consume_stun_or_break_the_sequence(self):
        snapshots = self.resolve_sequence(('01046', '01048', '01049', '01047'), stunned=True)
        self.assertTrue(snapshots[0][2]['stunned'])
        self.assertEqual(snapshots[0][2]['villain_health'], snapshots[0][1]['villain_health'] - 1)
        self.assertTrue(snapshots[1][2]['stunned'])
        self.assertEqual(snapshots[1][2]['threat'], 2)
        self.assertFalse(snapshots[2][2]['stunned'])
        self.assertEqual(snapshots[2][2]['villain_health'], snapshots[2][1]['villain_health'])
        self.assertEqual(snapshots[3][2]['villain_health'], snapshots[3][1]['villain_health'] - 4)

    def test_stun_and_confuse_cancel_their_respective_first_abilities(self):
        snapshots = self.resolve_sequence(('01049', '01047', '01048', '01046'),
                                          stunned=True, confused=True)
        self.assertFalse(snapshots[0][2]['stunned'])
        self.assertTrue(snapshots[0][2]['confused'])
        self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] - 2)
        self.assertFalse(snapshots[2][2]['confused'])
        self.assertEqual(snapshots[2][2]['threat'], 3)
        self.assertEqual(snapshots[3][2]['villain_health'], snapshots[3][1]['villain_health'] - 2)

    def test_undamaged_vibranium_suit_can_clear_stun_for_panther_claws(self):
        snapshots = self.resolve_sequence(('01049', '01047'), stunned=True, damage=0)
        self.assertFalse(snapshots[0][2]['stunned'])
        self.assertEqual(snapshots[0][2]['health'], snapshots[0][1]['health'])
        self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] - 4)

    def test_current_rules_allow_suit_to_clear_stun_without_legacy_switches(self):
        for rules in ([], ['v18_timing']):
            with self.subTest(rules=rules):
                snapshots = self.resolve_sequence(('01049', '01047'), stunned=True,
                                                  damage=0, rules=rules)
                self.assertFalse(snapshots[0][2]['stunned'])
                self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] - 4)

    def test_claws_first_while_undamaged_leaves_no_damage_for_vibranium_suit(self):
        snapshots = self.resolve_sequence(('01047', '01049'), stunned=True, damage=0)
        # Both upgrades deal no damage here: Claws removes stun, and the Suit
        # then has no damage to move. This is the expected rules interaction.
        self.assertFalse(snapshots[0][2]['stunned'])
        self.assertEqual(snapshots[-1][2]['villain_health'], snapshots[0][1]['villain_health'])

    def test_tactical_genius_can_clear_confuse_without_threat(self):
        snapshots = self.resolve_sequence(('01048', '01046'), confused=True, threat=0)
        self.assertFalse(snapshots[0][2]['confused'])
        self.assertEqual(snapshots[0][2]['threat'], 0)
        self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] - 2)

    def test_current_rules_allow_tactical_genius_to_clear_confuse_without_threat(self):
        for rules in ([], ['v18_timing']):
            with self.subTest(rules=rules):
                snapshots = self.resolve_sequence(('01048', '01046'), confused=True,
                                                  threat=0, rules=rules)
                self.assertFalse(snapshots[0][2]['confused'])
                self.assertEqual(snapshots[0][2]['threat'], 0)
                self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] - 2)

    def test_legacy_target_rules_remain_available_when_current_timing_is_disabled(self):
        snapshots = self.resolve_sequence(('01049', '01047'), stunned=True, damage=0,
                                          rules=['v15_all', 'no_v18_timing'])
        self.assertTrue(snapshots[0][2]['stunned'])
        self.assertFalse(snapshots[1][2]['stunned'])
        self.assertEqual(snapshots[-1][2]['villain_health'], snapshots[0][1]['villain_health'])

    def test_unaffected_sequence_resolves_all_specials_and_the_final_bonus(self):
        snapshots = self.resolve_sequence(('01049', '01047', '01048', '01046'))
        self.assertEqual(snapshots[-1][2]['health'], snapshots[0][1]['health'] + 1)
        self.assertEqual(snapshots[-1][2]['villain_health'], snapshots[0][1]['villain_health'] - 5)
        self.assertEqual(snapshots[-1][2]['threat'], 2)

    def test_all_upgrade_orders_preserve_later_attacks_under_current_rules(self):
        for order in permutations(('01046', '01047', '01048', '01049')):
            for damage in (0, 3):
                with self.subTest(order=order, damage=damage):
                    snapshots = self.resolve_sequence(order, stunned=True, confused=True,
                                                      damage=damage, rules=['v18_timing'])
                    first_attack = next(card_id for card_id in order if card_id in ('01047', '01049'))
                    claws_damage = (4 if order[-1] == '01047' else 2) if first_attack == '01049' else 0
                    suit_damage = min(damage, 2 if order[-1] == '01049' else 1) if first_attack == '01047' else 0
                    daggers_damage = 2 if order[-1] == '01046' else 1
                    before, after = snapshots[0][1], snapshots[-1][2]
                    self.assertFalse(after['stunned'])
                    self.assertFalse(after['confused'])
                    self.assertEqual(after['villain_health'], before['villain_health'] -
                                     claws_damage - suit_damage - daggers_damage)
                    self.assertEqual(after['health'], before['health'] + suit_damage)
                    self.assertEqual(after['threat'], before['threat'])

    def test_multiple_enemy_targets_do_not_cancel_the_second_attack(self):
        for order in (('01049', '01047'), ('01047', '01049')):
            with self.subTest(order=order):
                snapshots = self.resolve_sequence(order, stunned=True, extra_enemy=True,
                                                  rules=['v18_timing'])
                self.assertFalse(snapshots[0][2]['stunned'])
                self.assertEqual(snapshots[1][2]['villain_health'], snapshots[1][1]['villain_health'] -
                                 (4 if order[-1] == '01047' else 2))

    def test_steady_requires_two_status_cards_and_clears_both_together(self):
        for status_count in (1, 2):
            with self.subTest(status_count=status_count):
                snapshots = self.resolve_sequence(('01049', '01047', '01048', '01046'),
                                                  steady=True, stunned=status_count,
                                                  confused=status_count, rules=['v18_timing'])
                before, after = snapshots[0][1], snapshots[-1][2]
                self.assertEqual(after['stun_cards'], 1 if status_count == 1 else 0)
                self.assertEqual(after['confuse_cards'], 1 if status_count == 1 else 0)
                self.assertEqual(after['villain_health'], before['villain_health'] -
                                 (5 if status_count == 1 else 4))
                self.assertEqual(after['threat'], 2 if status_count == 1 else 3)


if __name__ == '__main__':
    unittest.main()
