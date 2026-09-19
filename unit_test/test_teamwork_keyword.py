import contextlib
import io
import unittest
from unittest.mock import patch

from engine import Engine
from engine.log import Log, Notify
from game.card.face.base.enemy import Enemy
from game.effect.rule import Teamwork
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


class TestTeamworkKeyword(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def enter_minion(self, rules, *, hero=False, existing=('60202',), other_player=False,
                     reveal=True, grant_trait=False):
        scene = SceneLoader.NewScene('rhino', None,
                                     ['spider_man', 'captain_america'] if other_player else ['spider_man'], 108)
        scene.rules = rules
        existing_player = 1 if other_player else 0
        setup = iter([
            'puzzle.ClearHand()',
            *(['puzzle.ChangeFormFor(0, "Hero")'] if hero else []),
            *[f'puzzle.PutIntoPlayFor({existing_player}, "{card_id}")' for card_id in existing],
            *(['puzzle.FindOrCreateFace("01172").GainTraits(1, "TRACKSUIT", DebugRule(hero))']
              if grant_trait else []),
        ])
        entered = False
        calls = []
        before = []
        after = []
        original = Enemy.DoActivate

        def activate(minion, player, effect, *args, **kwargs):
            if entered and isinstance(effect, Teamwork):
                calls.append((minion.paper.card_id, player.player_id))
            return original(minion, player, effect, *args, **kwargs)

        def snapshot(world):
            return (world.GetFirstPlayer().GetIdentity().health,
                    world.area_schemes_main.Get()[0].threat)

        def choose(prompt):
            nonlocal entered
            world = Engine.game.world
            if len(devices.prompts) > 25:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(setup, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                if not entered:
                    before.append(snapshot(world))
                    entered = True
                    command = 'puzzle.Reveal("60203")' if reveal else 'puzzle.PutIntoPlay("60203")'
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                after.append(snapshot(world))
                return None
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(Enemy, 'DoActivate', new=activate),
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
        self.assertEqual(len(before), 1)
        self.assertEqual(len(after), 1)
        return calls, before[0], after[0]

    def test_current_teamwork_only_activates_the_entering_minion(self):
        for rules in ([], ['v18_timing'], ['v16_all', 'v18_timing'], ['v16_all', 'no_v18_timing']):
            for hero in (False, True):
                for reveal in (False, True):
                    with self.subTest(rules=rules, hero=hero, reveal=reveal):
                        calls, before, after = self.enter_minion(rules, hero=hero, reveal=reveal)
                        self.assertEqual(calls, [('60203', 0)])
                        self.assertEqual(after, (before[0] - 2, before[1]) if hero
                                         else (before[0], before[1] + 1))

    def test_no_other_matching_minion_means_no_activation(self):
        for existing in ((), ('01172',)):
            with self.subTest(existing=existing):
                calls, before, after = self.enter_minion(['v18_timing'], existing=existing)
                self.assertEqual(calls, [])
                self.assertEqual(before, after)

    def test_multiple_matching_minions_still_grant_only_one_activation(self):
        calls, before, after = self.enter_minion(['v18_timing'], existing=('60202', '60200'))
        self.assertEqual(calls, [('60203', 0)])
        self.assertEqual(after, (before[0], before[1] + 1))

    def test_matching_minion_can_be_engaged_with_another_player(self):
        calls, before, after = self.enter_minion(['v18_timing'], other_player=True)
        self.assertEqual(calls, [('60203', 0)])
        self.assertEqual(after, (before[0], before[1] + 1))

    def test_legacy_teamwork_remains_available_with_legacy_timing(self):
        calls, _, _ = self.enter_minion(['v15_all', 'no_v18_timing'])
        self.assertCountEqual(calls, [('60202', 0), ('60203', 0)])

    def test_matching_minion_needs_the_trait_but_not_the_teamwork_keyword(self):
        calls, before, after = self.enter_minion(['v18_timing'], existing=('01172',), grant_trait=True)
        self.assertEqual(calls, [('60203', 0)])
        self.assertEqual(after, (before[0], before[1] + 1))


if __name__ == '__main__':
    unittest.main()
