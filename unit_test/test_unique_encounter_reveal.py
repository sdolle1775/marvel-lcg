"""Issue #151: unique encounter conflicts discard and deal one replacement."""
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


class TestUniqueEncounterReveal(unittest.TestCase):
    def setUp(self):
        for name in ('papers', 'sets_cards', 'linked_papers', 'ability_cache',
                     'ability_link_cards', 'full_link_cards'):
            self.enterContext(patch.object(CardsDB, name, {}))
        self.enterContext(patch.object(Cache, 'link_pic', {}))
        initialize_database()

    def run_commands(self, timing, commands, *, scenario='magneto', hero='magneto'):
        scene = SceneLoader.NewScene(scenario, None, [hero], 151)
        scene.rules = ['v16_all', timing]
        commands = iter(['puzzle.ClearHand()', 'puzzle.ChangeFormFor(0, "Hero")', *commands])

        def choose(prompt):
            if len(devices.prompts) > 40:
                raise AssertionError('Unique encounter reveal did not finish')
            if prompt.event_name != 'WhenPlayerInTurn':
                return CommandDescriptor() if prompt.show_cancel else devices._DefaultChoice(prompt)
            command = next(commands, None)
            if command is None:
                return None
            world = Engine.game.world
            if callable(command):
                command = command(world)
            Engine.game.controller_manager.console.SetCommand(command, world)
            return CommandDescriptor()

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
        return game.world

    def test_magneto_unique_attachments_deal_a_facedown_replacement(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for upgrade, attachment in (('49003', '32147'), ('49004', '32148')):
                with self.subTest(timing=timing, attachment=attachment):
                    world = self.run_commands(timing, [
                        f'puzzle.PutIntoPlay("{upgrade}")',
                        'puzzle.CreateEncounterDeck("01167")',
                        f'puzzle.Reveal("{attachment}")',
                    ])
                    player = world.GetFirstPlayer()
                    self.assertTrue(world.FindCardsOnField(name=upgrade)[0].IsInPlay())
                    self.assertEqual(world.FindCardsOnField(name=attachment), [])
                    discarded = world.scenario.encounter_discard_pile.FindCard(name=attachment)
                    self.assertIsNotNone(discarded)
                    self.assertIsNone(discarded.bind_face)
                    self.assertEqual([face.paper.card_id for face in player.dealt_encounter_cards.Get()], ['01167'])
                    self.assertEqual(world.FindCardsOnField(name='01167'), [])

    def test_magneto_attachments_without_a_conflict_attach_to_the_villain(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for attachment in ('32147', '32148'):
                with self.subTest(timing=timing, attachment=attachment):
                    world = self.run_commands(timing, [f'puzzle.Reveal("{attachment}")'])
                    attached = world.FindCardsOnField(name=attachment)[0]
                    self.assertIs(attached.GetBindFace(), world.scenario.area_villain.Get()[0])
                    self.assertEqual(world.GetFirstPlayer().dealt_encounter_cards.GetSize(), 0)

    def test_duplicate_minions_ignore_reveal_effects_and_keywords_from_any_pile(self):
        # Shocker damages heroes, Avalanche has Incite and a When Revealed
        # ability, and Hairbag has Surge. None should resolve for a duplicate.
        for timing in ('v18_timing', 'no_v18_timing'):
            for card_id in ('01103', '14026', '40113'):
                for source in ('encounter_deck', 'encounter_discard_pile'):
                    with self.subTest(timing=timing, card=card_id, source=source):
                        before = {}

                        def reveal_duplicate(world):
                            player = world.GetFirstPlayer()
                            before['hero_health'] = player.GetHero().health
                            before['scheme'] = world.FindCardsOnField(name='The Break-In!')[0]
                            before['threat'] = before['scheme'].threat
                            before['original'] = world.FindCardsOnField(name=card_id)[0]
                            before['duplicate'] = getattr(world.scenario, source).GetTop()
                            return f'puzzle.Reveal({before["duplicate"].card.object_id})'

                        create = 'CreateEncounterDeck' if source == 'encounter_deck' else 'CreateEncounterDiscardPile'
                        world = self.run_commands(timing, [
                            f'puzzle.PutIntoPlay("{card_id}")',
                            'puzzle.CreateEncounterDeck("01167", "01167")',
                            f'puzzle.{create}("{card_id}")',
                            reveal_duplicate,
                        ], scenario='rhino', hero='spider_man')
                        self.assertEqual(world.FindCardsOnField(name=card_id), [before['original']])
                        self.assertTrue(before['duplicate'].card.area.flags.is_discards)
                        self.assertFalse(before['duplicate'].card.state.is_revealing)
                        self.assertEqual(world.GetFirstPlayer().GetHero().health, before['hero_health'])
                        self.assertEqual(before['scheme'].threat, before['threat'])
                        self.assertTrue(world.GetFirstPlayer().GetHero().IsReady())
                        self.assertEqual(world.GetFirstPlayer().dealt_encounter_cards.GetSize(), 1)

    def test_putting_a_conflicting_attachment_into_play_does_not_deal_a_card(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            with self.subTest(timing=timing):
                world = self.run_commands(timing, [
                    'puzzle.PutIntoPlay("49004")',
                    'puzzle.PutIntoPlay("32148")',
                ])
                self.assertIsNotNone(world.scenario.encounter_discard_pile.FindCard(name='32148'))
                self.assertEqual(world.GetFirstPlayer().dealt_encounter_cards.GetSize(), 0)


if __name__ == '__main__':
    unittest.main()
