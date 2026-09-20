import contextlib
import io
import unittest
from unittest.mock import patch

from engine import Engine
from engine.log import Log, Notify
from game.ability import AbilityType
from game.effect.effect_invoke import EffectInvoker
from game.event.manager import EventManager
from game.message import Message
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestVictoryDefeat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def defeat_card(self, card_id, *, rules=None, is_scheme=True, attachment=False,
                    heroes=('captain_marvel',), setup_commands=(), reveal=False,
                    decline_defeat_choice=False, legacy_order=None):
        scene = SceneLoader.NewScene('rhino', None, list(heroes), 115)
        scene.rules = [] if rules is None else rules
        commands = iter([
            *(f'puzzle.ClearHandFor({i})' for i in range(len(heroes))),
            'puzzle.ChangeFormFor(0, "Hero")',
            'puzzle.PutIntoPlay("04047")',  # Skilled Investigator
            *setup_commands,
            f'puzzle.{"Reveal" if reveal else "PutIntoPlay"}("{card_id}")',
            'puzzle.SetThreat("01097b", 5)',
            *(['puzzle.FindOrCreateFace("32170").AttachTo2('
               f'puzzle.FindOrCreateFace("{card_id}"), DebugRule(hero))'] if attachment else []),
            *([f'puzzle.SetThreat("{card_id}", 2)'] if is_scheme else [
                f'puzzle.Damage("{card_id}", '
                f'puzzle.FindOrCreateFace("{card_id}").max_health - 1)',
            ]),
        ])
        acted = False
        target = None
        operations = []
        leave_play = []
        leave_hands = []
        response_states = []
        chosen_orders = []
        invoke = EffectInvoker.InvokeOperation
        after_leave = Message.AfterCardLeavePlay.Send

        def record_operation(effect, message):
            record = effect.this.paper.card_id == card_id and effect.ability.type == AbilityType.WhenDefeated
            before = effect.this.IsInPlay()
            result = invoke(effect, message)
            if record:
                operations.append((effect.ability.name == 'Victory', before, effect.this.IsInPlay()))
            return result

        def record_leave(message):
            if message.trigger.paper.card_id in (card_id, '32170'):
                leave_play.append((message.trigger.paper.card_id, message.into_area.flags.is_victory_display))
            if message.trigger.paper.card_id == card_id:
                leave_hands.append([[face.paper.card_id for face in player.hand_cards.Get()]
                                    for player in message.world.const_players])
            return after_leave(message)

        def choose(prompt):
            nonlocal acted, target
            if len(devices.prompts) > 35:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(commands, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, Engine.game.world)
                    return CommandDescriptor()
                if acted:
                    return None
                acted = True
                target = next(card.face for card in Engine.game.world.object_manager.card_dict.values()
                              if card.face.paper.card_id == card_id and card.face.IsInPlay())
                option = next(o for o in prompt.options if o['name'] == ('Thwart' if is_scheme else 'Attack'))
                return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                         [str(target.card.object_id)], [])
            if prompt.ability_type == 'ForcedInterrupt':
                option = next((o for o in prompt.options if legacy_order and
                               o['name'].endswith(legacy_order)), prompt.options[0])
                chosen_orders.append(option['name'])
                return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option), [], [])
            if acted and prompt.event_name == 'AfterSchemeBeDefeated':
                response_states.append((target.card.area.flags.is_victory_display, len(operations)))
                return HeadlessDeviceManager._DefaultChoice(prompt)
            if acted and prompt.event_name == 'WhenPlayerChooseAbility':
                if decline_defeat_choice:
                    option = next(o for o in prompt.options if o['name'] == 'Cancel')
                    return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option), [], [])
                return HeadlessDeviceManager._DefaultChoice(prompt)
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch('game.test.v18_timing_harness.initialize_database'),
            patch.object(EffectInvoker, 'InvokeOperation', side_effect=record_operation),
            patch.object(Message.AfterCardLeavePlay, 'Send', new=record_leave),
            patch.object(WorldRender, 'ErrorOccurred') as errors,
            patch.object(Log, 'Warn') as warnings,
            patch.object(Notify, 'Game') as notices,
            patch.object(Engine, 'SaveCrash'),
        ):
            game = run_scene_with_devices(scene, devices)
        errors.assert_not_called()
        warnings.assert_not_called()
        notices.assert_not_called()
        self.assertTrue(acted)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        if legacy_order is None:
            self.assertFalse(any(option['name'].endswith('Victory')
                                 for prompt in devices.prompts for option in prompt.options))
        return game.world, target, operations, leave_play, response_states, chosen_orders, leave_hands

    def test_player_side_schemes_resolve_victory_without_ordering_prompt(self):
        for rules in ([], ['v18_timing']):
            for card_id in ('41016', '43018', '48020'):
                with self.subTest(rules=rules, card=card_id):
                    world, target, operations, leaves, responses, choices, _ = self.defeat_card(
                        card_id, rules=rules)
                    self.assertEqual(operations, [(True, True, True), (False, True, True)])
                    self.assertEqual(choices, [])
                    self.assertTrue(target.card.area.flags.is_victory_display)
                    self.assertEqual(leaves, [(card_id, True)])
                    self.assertEqual(responses, [(True, 2)])
                    self.assertEqual(len(world.GetFirstPlayer().hand_cards.Get()), 1)
                    villain = world.GetScenario().area_villain.Get()[0]
                    if card_id == '41016':  # Lay the Trap deals 5 damage.
                        self.assertEqual(villain.health, villain.max_health - 5)
                    elif card_id == '43018':  # Keep Them Busy removes 5 threat.
                        self.assertEqual(world.area_schemes_main.Get()[0].threat, 0)
                    else:  # Astonishing X-Men stuns and confuses each enemy.
                        self.assertTrue(villain.IsStunned())
                        self.assertTrue(villain.IsConfused())

    def test_encounter_scheme_keeps_optional_defeat_effect_before_responses(self):
        for decline in (False, True):
            with self.subTest(decline=decline):
                world, target, operations, leaves, responses, choices, _ = self.defeat_card(
                    '16127', decline_defeat_choice=decline)
                self.assertEqual(world.GetFirstPlayer().GetHero().IsExhaust(), decline)
                self.assertEqual(operations, [(True, True, True), (False, True, True)])
                self.assertEqual(choices, [])
                self.assertTrue(target.card.area.flags.is_victory_display)
                self.assertEqual(leaves, [('16127', True)])
                self.assertEqual(responses, [(True, 2)])

    def test_security_breach_returns_both_players_cards_before_victory(self):
        for rules in ([], ['v18_timing']):
            with self.subTest(rules=rules):
                _, target, operations, leaves, responses, choices, leave_hands = self.defeat_card(
                    '21181', rules=rules, heroes=('captain_marvel', 'spider_man'), reveal=True,
                    setup_commands=(
                        'puzzle.CreateHandCardsFor(0, "01089")',
                        'puzzle.CreateHandCardsFor(1, "01090")',
                    ))
                self.assertEqual(choices, [])
                self.assertEqual(operations, [(True, True, True), (False, True, True)])
                self.assertEqual(leave_hands, [[['01089'], ['01090']]])
                self.assertEqual(target.GetPlacedCardArea().Get(True), [])
                self.assertTrue(target.card.area.flags.is_victory_display)
                self.assertEqual(leaves, [('21181', True)])
                self.assertEqual(responses, [(True, 2)])

    def test_victory_minion_leaves_play_once_for_victory_display(self):
        _, target, operations, leaves, _, choices, _ = self.defeat_card('16183', is_scheme=False)
        self.assertEqual(choices, [])
        self.assertEqual(operations, [(True, True, True)])
        self.assertTrue(target.card.area.flags.is_victory_display)
        self.assertEqual(leaves, [('16183', True)])

    def test_saved_victory_order_is_consumed_without_replay_divergence(self):
        for order in ('Victory', 'When_Defeated'):
            with self.subTest(order=order):
                # Record the old UI's choice with the real controller, then
                # reload that history under automatic Victory resolution.
                with patch.object(EventManager, '_GetAutomaticTimingCandidate', return_value=None):
                    world, _, _, _, _, choices, _ = self.defeat_card(
                        '21181', legacy_order=order, heroes=('captain_marvel', 'spider_man'),
                        reveal=True, setup_commands=(
                            'puzzle.CreateHandCardsFor(0, "01089")',
                            'puzzle.CreateHandCardsFor(1, "01090")',
                        ))
                self.assertEqual(len(choices), 1)
                self.assertTrue(choices[0].endswith(order))
                scene = world.scene
                scene.UpdateInputs(Engine.game)
                devices = HeadlessDeviceManager(stop_when=lambda p: p.event_name == 'WhenPlayerInTurn')
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    patch('game.test.v18_timing_harness.initialize_database'),
                    patch.object(WorldRender, 'ErrorOccurred') as errors,
                    patch.object(Log, 'Warn') as warnings,
                    patch.object(Notify, 'Game') as notices,
                    patch.object(Engine, 'SaveCrash'),
                ):
                    game = run_scene_with_devices(scene, devices, load_type='InTesting')
                errors.assert_not_called()
                warnings.assert_not_called()
                notices.assert_not_called()
                self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
                self.assertEqual(game.controller_manager.replay.replay_step_id, len(scene.inputs))
                target = next(c.face for c in game.world.object_manager.card_dict.values()
                              if c.face.paper.card_id == '21181')
                self.assertTrue(target.card.area.flags.is_victory_display)
                self.assertIn('01089', [f.paper.card_id for f in game.world.const_players[0].hand_cards.Get()])
                self.assertIn('01090', [f.paper.card_id for f in game.world.const_players[1].hand_cards.Get()])

    def test_victory_attachment_still_moves_when_its_host_is_defeated(self):
        _, target, _, leaves, _, _, _ = self.defeat_card('01129', is_scheme=False, attachment=True)
        self.assertFalse(target.card.area.flags.is_victory_display)
        self.assertEqual(leaves, [('32170', True), ('01129', False)])

    def test_explicit_legacy_timing_preserves_victory_destination(self):
        for card_id, is_scheme in (('16127', True), ('16183', False)):
            with self.subTest(card=card_id):
                _, target, _, leaves, _, choices, _ = self.defeat_card(
                    card_id, is_scheme=is_scheme, rules=['v16_all', 'no_v18_timing'])
                self.assertTrue(target.card.area.flags.is_victory_display)
                self.assertEqual(leaves, [(card_id, True)])
                self.assertEqual(choices, [])


if __name__ == '__main__':
    unittest.main()
