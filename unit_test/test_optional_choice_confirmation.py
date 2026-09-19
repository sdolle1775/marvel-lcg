import contextlib
import io
import unittest
from unittest.mock import patch

from engine import Engine
from engine.log import Log, Notify
from game.ability.factory import AbilityFactory
from game.element.cost import Cost
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestOptionalChoiceConfirmation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_choice(self, command, *, accept, card_id=None, rules=None):
        scene = SceneLoader.NewScene('rhino', None, ['black_panther_shuri'], 109)
        scene.rules = rules if rules is not None else ['v16_all', 'v18_timing']
        setup = iter([
            'puzzle.ClearHand()',
            'puzzle.ChangeFormFor(0, "Hero")',
            *([f'puzzle.PutIntoPlay("{card_id}")'] if card_id else []),
            'puzzle.Damage("51001a", 2)',
            'puzzle.SetThreat("01097b", 3)',
        ])
        resolved = False
        prompts = []
        before = []

        def choose(prompt):
            nonlocal resolved
            world = Engine.game.world
            if len(devices.prompts) > 25:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                setup_command = next(setup, None)
                if setup_command:
                    Engine.game.controller_manager.console.SetCommand(setup_command, world)
                    return CommandDescriptor()
                if not resolved:
                    before.append((world.GetFirstPlayer().GetHero().health,
                                   world.GetScenario().area_villain.Get()[0].health))
                    resolved = True
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                return None
            if prompt.event_name == 'WhenPlayerChooseAbility' and any(
                option['name'].startswith('Discard_this_card') if card_id else
                option['name'] in ('Recover_health', 'Choose_your_hero')
                for option in prompt.options
            ):
                prompts.append(prompt)
                if accept:
                    # Send the same targetless command as the web client for
                    # a preselected singleton; the controller restores it.
                    return CommandDescriptor(
                        HeadlessDeviceManager._DescriptorId(prompt.options[0]), [], [])
                if prompt.show_cancel:
                    return CommandDescriptor()
                cancel = next(option for option in prompt.options if option['name'] == 'Cancel')
                return CommandDescriptor(HeadlessDeviceManager._DescriptorId(cancel), [], [])
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch('game.test.v18_timing_harness.initialize_database'),
            patch('game.world.cheat.cheat_cmd_helper.AbilityFactory', AbilityFactory, create=True),
            patch('game.world.cheat.cheat_cmd_helper.Cost', Cost, create=True),
            patch.object(WorldRender, 'ErrorOccurred') as errors,
            patch.object(Log, 'Warn') as warnings,
            patch.object(Notify, 'Game') as notices,
            patch.object(Engine, 'SaveCrash'),
        ):
            game = run_scene_with_devices(scene, devices)
        errors.assert_not_called()
        warnings.assert_not_called()
        notices.assert_not_called()
        self.assertTrue(resolved)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(len(prompts), 1)
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        return game.world, prompts[0], before[0]

    def check_upgrade(self, card_id, accept, *, rules=None):
        world, prompt, before = self.run_choice(
            f'p.ResolveSpecialAbility([puzzle.FindOrCreateFace("{card_id}")], DebugRule(hero))',
            accept=accept, card_id=card_id, rules=rules,
        )
        player = world.GetFirstPlayer()
        hero = player.GetHero()
        villain = world.GetScenario().area_villain.Get()[0]
        upgrade = next(card.face for card in world.object_manager.card_dict.values()
                       if card.face.paper.card_id == card_id)
        option, cancel = prompt.options
        self.assertEqual(cancel['name'], 'Cancel')
        self.assertFalse(option['automatic_submit'])
        self.assertEqual(option['automatic_targets'], option['all_legal_targets'])
        self.assertEqual(upgrade.IsInPlay(), not accept)
        self.assertEqual(upgrade in player.discard_pile.Get(), accept)
        expected_damage = {'51010': 0, '51011': 5 if accept else 2, '51012': 1, '51013': 1}
        self.assertEqual(villain.health, before[1] - expected_damage[card_id])
        self.assertEqual(world.area_schemes_main.Get()[0].threat, 2 if card_id == '51010' else 3)
        self.assertEqual(hero.health, before[0] + (1 if card_id == '51013' else 0))
        self.assertEqual(villain.IsConfused(), accept and card_id == '51010')
        self.assertEqual(villain.IsStunned(), accept and card_id == '51012')
        self.assertEqual(hero.IsTough(), accept and card_id == '51013')

    def test_shuri_can_keep_each_upgrade_and_resolve_the_initial_special(self):
        for card_id in ('51010', '51011', '51012', '51013'):
            with self.subTest(card_id=card_id):
                self.check_upgrade(card_id, False)

    def test_shuri_can_confirm_each_discard_and_receive_its_bonus(self):
        for card_id in ('51010', '51011', '51012', '51013'):
            with self.subTest(card_id=card_id):
                self.check_upgrade(card_id, True)

    def test_legacy_timing_also_preserves_the_optional_discard(self):
        self.check_upgrade('51013', False, rules=['v16_all', 'no_v18_timing'])

    def test_optional_choice_without_a_cancel_ability_requires_confirmation(self):
        for accept in (False, True):
            with self.subTest(accept=accept):
                world, prompt, before = self.run_choice(
                    '(p.ChooseAbilities(DebugRule(hero), '
                    'AbilityFactory.ForChoiceAbilityWithCost(Cost("0"), "Recover health", '
                    'lambda targets, resources: targets[0].HealHealth(1, DebugRule(targets[0])))'
                    '.SetTarget("YourHero"), forced=False), None)[1]',
                    accept=accept,
                )
                self.assertTrue(prompt.show_cancel)
                self.assertFalse(prompt.options[0]['automatic_submit'])
                self.assertEqual(world.GetFirstPlayer().GetHero().health, before[0] + int(accept))

    def test_mandatory_choice_keeps_automatic_target_submission(self):
        _, prompt, _ = self.run_choice(
            'p.ChooseAbilities(DebugRule(hero), '
            'AbilityFactory.ForChoiceAbility("Choose your hero").SetTarget("YourHero"), '
            'AbilityFactory.ForChoiceAbility("Choose no target"))',
            accept=True,
        )
        self.assertFalse(prompt.show_cancel)
        self.assertTrue(prompt.options[0]['automatic_submit'])
        self.assertEqual(len(prompt.options[0]['automatic_targets']), 1)


if __name__ == '__main__':
    unittest.main()
