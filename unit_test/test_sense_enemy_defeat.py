import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import call, patch

from engine import Engine
from cards.database import CardsDB
from engine.lib import Ver
from engine.log import Log, Notify
from game.card.face.base.villain import Villain
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices, validate_file
from game.world.world_render import WorldRender


class TestSenseEnemyDefeat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_game(self, scene, devices, **kwargs):
        # Reinitializing the database appends linked encounter cards again.
        # The reported deck includes Lady Deadpool's linked set: keep one copy
        # of each link, as on the original application's first initialization.
        links = {key: list(dict.fromkeys(value)) for key, value in CardsDB.linked_papers.items()}
        with (
            patch.dict(CardsDB.linked_papers, links),
            patch('game.test.v18_timing_harness.initialize_database'),
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(WorldRender, 'ErrorOccurred') as errors,
            patch.object(Log, 'Warn') as warnings,
            patch.object(Notify, 'Game') as notices,
            patch.object(Engine, 'SaveCrash'),
        ):
            game = run_scene_with_devices(scene, devices, **kwargs)
        errors.assert_not_called()
        expected = [call('VERSION', f'Version {scene.version} is lower than last version {Ver.version}')] \
            if Ver(scene.version) < Ver.version else []
        self.assertEqual(warnings.call_args_list, expected)
        notices.assert_not_called()
        return game

    @staticmethod
    def choice(option, targets=None, resources=()):
        if targets is None:
            targets = option['all_legal_targets'][:option['target_num_range'][0]]
        return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                 [str(target) for target in targets], list(resources))

    def test_reported_save_offers_olfaction_before_the_minion_leaves_play(self):
        scene = validate_file(Path(__file__).parent / 'fixtures' / 'issue_107_enhanced_olfaction.json')
        # Retain every recorded choice through Raising Hell. The last saved
        # Radar Sense response follows the missing interrupt, so stop before it.
        scene.inputs = scene.inputs[:44]
        snapshot = []

        def choose(prompt):
            world = Engine.game.world
            sense = world.object_manager.card_dict[3].face
            minion = world.object_manager.card_dict[97].face
            snapshot.append((sense.IsInPlay(), sense.bind_face is minion, minion.IsInPlay(), minion.health))
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = self.run_game(scene, devices, load_type='InTesting')
        self.assertEqual(game.controller_manager.replay.current_step_id, 44)
        self.assertEqual([operation.crc for operation in game.controller_manager.replay.history_inputs],
                         [operation.crc for operation in scene.inputs])
        prompt = devices.stopped_prompt
        self.assertEqual(prompt.event_name, 'WhenUnitWouldBeDefeated')
        self.assertEqual(prompt.ability_type, 'Interrupt')
        self.assertEqual([option['bind_id'] for option in prompt.options], [3])
        self.assertEqual(snapshot, [(True, True, True, 0)])

    def test_reported_olfaction_discount_survives_raising_hell_finishing(self):
        scene = validate_file(Path(__file__).parent / 'fixtures' / 'issue_107_enhanced_olfaction.json')
        scene.inputs = scene.inputs[:44]
        used = []
        costs = []

        def choose(prompt):
            if prompt.event_name == 'WhenUnitWouldBeDefeated':
                option = next(option for option in prompt.options if option['bind_id'] == 3)
                used.append(option['bind_id'])
                return self.choice(option)
            if prompt.event_name == 'WhenPlayerInTurn':
                option = next(option for option in prompt.options
                              if option['name'] == 'Play' and option['bind_id'] == 29)
                costs.append(next(iter(option['target_payment'].values()))['cost'])
                return None
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = self.run_game(scene, devices, load_type='InTesting')
        self.assertEqual(used, [3])
        self.assertEqual(costs, ['1'])  # Three-cost Beat Cop receives the two-resource discount.
        self.assertIn(game.world.object_manager.card_dict[3].face,
                      game.world.GetFirstPlayer().additional_deck.Get())
        self.assertFalse(game.world.object_manager.card_dict[97].face.IsInPlay())

    def defeat_minion(self, timing, sense_id, attack, *, accept=True, attach_to_villain=False):
        scene = SceneLoader.NewScene('rhino', None, ['daredevil'], 107)
        scene.rules = ['v16_all', timing]
        setup = iter([
            'puzzle.ClearHand()',
            'puzzle.ChangeFormFor(0, "Hero")',
            'puzzle.PutIntoPlay("60203")',
            'puzzle.Damage("60203", 2)',
            *(['puzzle.PutIntoPlay("01067")'] if attack == 'ally' else []),
            f'p.additional_deck.FindCard(name="{sense_id}").PutIntoPlay(p, DebugRule(hero))',
            'puzzle.CreateHandCards("60011", "01088", "01057", "01065", "01089")',
            *(['puzzle.Exhaust("60001a")'] if attack != 'basic' else []),
        ])
        attacked = False
        played_discounted_card = False
        interrupts = []
        costs = []
        minion = sense = None

        def choose(prompt):
            nonlocal attacked, played_discounted_card, minion, sense
            world = Engine.game.world
            player = world.GetFirstPlayer()
            if len(devices.prompts) > 30:
                raise AssertionError('Unexpected repeated prompt')
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(setup, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                if not attacked:
                    minion = next(face for face in player.GetEngagedMinions() if face.paper.card_id == '60203')
                    sense = world.object_manager.card_dict[2 if sense_id == '60002' else 3].face
                    attacked = True
                    if attack == 'event':
                        event = player.hand_cards.FindCard(name='60011')
                        option = next(option for option in prompt.options
                                      if option['name'] == 'Play' and option['bind_id'] == event.card.object_id)
                        payments = next(iter(option['target_payment'].values()))['payment']
                        resource = next(effect_id for payment in payments for effect_id in payment
                                        if payment[effect_id] == 'YY')
                        return self.choice(option, resources=[resource])
                    attacker = player.GetIdentity() if attack == 'basic' else player.allies.FindCard(name='01067')
                    option = next(option for option in prompt.options
                                  if option['name'] == 'Attack' and option['bind_id'] == attacker.card.object_id)
                    return self.choice(option, [minion.card.object_id])
                if sense_id == '60003':
                    card_id = '01065' if played_discounted_card else '01057'
                    card = player.hand_cards.FindCard(name=card_id)
                    option = next(option for option in prompt.options
                                  if option['name'] == 'Play' and option['bind_id'] == card.card.object_id)
                    costs.append(next(iter(option['target_payment'].values()))['cost'])
                    if not played_discounted_card and interrupts and accept:
                        played_discounted_card = True
                        return self.choice(option)
                return None
            for option in prompt.options:
                source = world.object_manager.card_dict[option['bind_id']].face
                if attacked and source is sense and prompt.ability_type == 'Interrupt':
                    interrupts.append((prompt.event_name, sense.IsInPlay(), sense.bind_face is minion,
                                       minion.IsInPlay(), player.GetIdentity().IsExhaust()))
                    return self.choice(option) if accept else CommandDescriptor()
                if not attacked:
                    targets = [world.object_manager.card_dict[target].face for target in option['all_legal_targets']]
                    target = next((face for face in targets
                                   if (Villain.IsType(face) if attach_to_villain
                                       else face.paper.card_id == '60203')), None)
                    if target:
                        return self.choice(option, [target.card.object_id])
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game = self.run_game(scene, devices)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertFalse(minion.IsInPlay())
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        if attach_to_villain:
            self.assertTrue(sense.IsInPlay())
            self.assertTrue(Villain.IsType(sense.bind_face))
        else:
            self.assertIn(sense, game.world.GetFirstPlayer().additional_deck.Get())
        return game.world.GetFirstPlayer(), interrupts, costs

    def test_hero_basic_and_event_defeats_trigger_both_senses(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for sense_id in ('60002', '60003'):
                for attack in ('basic', 'event'):
                    with self.subTest(timing=timing, sense=sense_id, attack=attack):
                        player, interrupts, costs = self.defeat_minion(timing, sense_id, attack)
                        self.assertEqual(interrupts, [('WhenUnitWouldBeDefeated', True, True, True, True)])
                        if sense_id == '60002':
                            self.assertFalse(player.GetIdentity().IsExhaust())
                        else:
                            self.assertEqual(costs, ['0', '2'])

    def test_ally_defeats_do_not_trigger_either_sense(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for sense_id in ('60002', '60003'):
                with self.subTest(timing=timing, sense=sense_id):
                    player, interrupts, costs = self.defeat_minion(timing, sense_id, 'ally')
                    self.assertEqual(interrupts, [])
                    self.assertTrue(player.GetIdentity().IsExhaust())
                    if sense_id == '60003':
                        self.assertEqual(costs, ['2'])

    def test_declining_olfaction_does_not_grant_a_discount(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            with self.subTest(timing=timing):
                _, interrupts, costs = self.defeat_minion(timing, '60003', 'basic', accept=False)
                self.assertEqual(len(interrupts), 1)
                self.assertEqual(costs, ['2'])

    def test_defeating_an_unattached_enemy_does_not_trigger(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for sense_id in ('60002', '60003'):
                with self.subTest(timing=timing, sense=sense_id):
                    _, interrupts, costs = self.defeat_minion(timing, sense_id, 'basic', attach_to_villain=True)
                    self.assertEqual(interrupts, [])
                    if sense_id == '60003':
                        self.assertEqual(costs, ['2'])


if __name__ == '__main__':
    unittest.main()
