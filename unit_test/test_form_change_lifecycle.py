import contextlib
import io
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


class TestFormChangeLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_commands(self, identity, commands, *, scheme=None, timing='v18_timing',
                     expert=False, scenario='rhino', accept_form_responses=False):
        scene = SceneLoader.NewScene(scenario, None, [identity], 106115)
        scene.rules = ['v16_all', timing]
        scene.campaign.expert = expert
        if scheme:
            scene.campaign.schemes = [scheme]
        commands = iter(commands)
        snapshots = []
        entries = []
        entry_send = Message.AfterCardEnterPlay.Send

        def after_entry(message):
            if snapshots:
                entries.append(message.trigger.paper.card_id)
            return entry_send(message)

        def choose(prompt):
            if len(devices.prompts) > 70:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                world = Engine.game.world
                player = world.GetFirstPlayer()
                face = player.GetIdentity()
                snapshots.append({
                    'card': face.card,
                    'face': face.paper.card_id,
                    'health': face.health,
                    'max_health': face.max_health,
                    'stunned': face.IsStunned(),
                    'confused': face.IsConfused(),
                    'tough': face.IsTough(),
                    'exhausted': face.IsExhaust(),
                    'threat': world.area_schemes_main.Get()[0].threat,
                    'attack': getattr(face, 'attack', None),
                    'defense': getattr(face, 'defense', None),
                    'upgrades': sorted(upgrade.paper.card_id for upgrade in player.GetControlUpgrade()),
                    'tucked': sorted(card.paper.card_id for card in face.GetPlacedCardArea().Get()),
                    'counters': face.GetCounters('charge'),
                })
                command = next(commands, None)
                if command is None:
                    return None
                Engine.game.controller_manager.console.SetCommand(command, world)
                return CommandDescriptor()
            if accept_form_responses and prompt.event_name == 'AfterUnitChangeForm':
                return HeadlessDeviceManager._DefaultChoice(prompt)
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch('game.test.v18_timing_harness.initialize_database'),
            patch.object(Message.AfterCardEnterPlay, 'Send', new=after_entry),
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
        return game.world, snapshots, entries

    def test_identity_form_changes_are_not_entries(self):
        for identity in ('captain_marvel', 'ant_man', 'wasp', 'vision', 'colossus', 'shadowcat', 'echo', 'daredevil'):
            with self.subTest(identity=identity):
                _, snapshots, entries = self.run_commands(identity, [
                    'puzzle.ChangeFormFor(0, "Hero")',
                    'puzzle.ChangeFormFor(0, "Identity")',
                ])
                self.assertEqual(entries, [])
                self.assertEqual(len(snapshots), 3)
                self.assertTrue(all(s['card'] is snapshots[0]['card'] for s in snapshots))

    def test_mass_form_does_not_trigger_pawn_shop_showdown(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            with self.subTest(timing=timing):
                _, snapshots, entries = self.run_commands('vision', [
                    'puzzle.Flip("26002a")',
                    'puzzle.Flip("26002b")',
                ], scheme='60137a,60137b', timing=timing)
                self.assertEqual([s['threat'] for s in snapshots], [snapshots[0]['threat']] * 3)
                self.assertEqual(entries, [])

    def test_actual_allies_and_minions_still_enter_play(self):
        _, _, entries = self.run_commands('captain_marvel', [
            'puzzle.PutIntoPlay("01067")',
            'puzzle.PutIntoPlay("01172")',
        ])
        self.assertEqual(entries, ['01067', '01172'])

    def test_form_changes_preserve_character_state_and_attached_health(self):
        setup = [
            'puzzle.PutIntoPlay("05023")',  # Endurance, +3 health
            'puzzle.PutIntoPlay("01081")',  # Armored Vest
            'puzzle.Damage(hero, 3)',
            'hero.GainStatus("Stunned", DebugRule(hero))',
            'hero.GainStatus("Confused", DebugRule(hero))',
            'hero.GainStatus("Tough", DebugRule(hero))',
            'puzzle.Exhaust(hero)',
            'hero.TuckCardUnderHere(puzzle.FindOrCreateFace("01089"), DebugRule(hero))',
            'puzzle.Counter(hero, "charge", 2)',
        ]
        for identity in ('captain_marvel', 'ant_man', 'wasp'):
            with self.subTest(identity=identity):
                _, snapshots, entries = self.run_commands(identity, setup + ['puzzle.Flip(hero)'] * 6)
                stable = snapshots[len(setup):]
                for state in stable:
                    for key in ('card', 'health', 'max_health', 'stunned', 'confused', 'tough',
                                'exhausted', 'upgrades', 'tucked', 'counters'):
                        self.assertEqual(state[key], stable[0][key], key)
                self.assertEqual(entries, ['05023', '01081'])

    def test_mass_form_modifiers_refresh_after_each_flip(self):
        _, snapshots, entries = self.run_commands('vision', [
            'puzzle.ChangeFormFor(0, "Hero")',
            'puzzle.Flip("26002a")',
            'puzzle.ChangeFormFor(0, "Identity")',
            'puzzle.ChangeFormFor(0, "Hero")',
            'puzzle.Flip("26002b")',
        ])
        self.assertEqual([(s['attack'], s['defense']) for s in snapshots[1:]],
                         [(0, 0), (2, 2), (None, None), (2, 2), (0, 0)])
        self.assertEqual(entries, [])

    def test_printed_form_change_response_still_resolves(self):
        _, snapshots, entries = self.run_commands('ant_man', [
            'puzzle.SetThreat("01097b", 3)',
            'puzzle.ChangeFormFor(0, "Hero")',
        ], accept_form_responses=True)
        self.assertEqual(snapshots[-1]['threat'], 2)
        self.assertEqual(entries, [])

    def test_setup_mode_flip_initializes_uses_once_on_final_face(self):
        for expert, incoming, expected_face, expected_counters in (
            (False, '27174b,27174a', '27174a', 2),
            (True, '27174a,27174b', '27174b', 3),
        ):
            with self.subTest(expert=expert):
                world, _, entries = self.run_commands('captain_marvel', [
                    f'puzzle.PutIntoPlay("{incoming}")',
                ], expert=expert)
                card = next(face for face in world.FindCardsOnField(name='Public Outcry'))
                self.assertEqual(card.paper.card_id, expected_face)
                self.assertEqual(card.GetCounters('notoriety'), expected_counters)
                self.assertEqual(entries, [expected_face])

    def test_later_flips_do_not_refill_uses(self):
        world, _, entries = self.run_commands('captain_marvel', [
            'puzzle.PutIntoPlay("27174a,27174b")',
            'puzzle.Counter("27174a", "notoriety", -1)',
            'puzzle.Flip("27174a")',
            'puzzle.Flip("27174b")',
        ])
        card = next(face for face in world.FindCardsOnField(name='Public Outcry'))
        self.assertEqual(card.GetCounters('notoriety'), 1)
        self.assertEqual(entries, ['27174a'])

    def test_collector_recovers_health_when_flipping_at_round_end(self):
        world, snapshots, entries = self.run_commands('captain_marvel', [
            'puzzle.Damage("16080a", 100)',
            'Message.WhenRoundEnd(world).Send()',
        ], scenario='escape_the_museum')
        collector = next(face for face in world.FindCardsOnField(name='Collector'))
        self.assertEqual(collector.paper.card_id, '16080a')
        self.assertEqual(collector.health, collector.printed_health)
        self.assertEqual(snapshots[-1]['threat'], snapshots[0]['threat'] - 3)
        self.assertEqual(entries, [])


if __name__ == '__main__':
    unittest.main()
