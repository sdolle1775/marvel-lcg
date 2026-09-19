import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from engine import Engine
from engine.log import Log, Notify
from cards.database import CardsDB
from game.message import Message
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices, validate_file
from game.world.world_render import WorldRender


class TestBerserkerBarrage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def run_game(self, scene, devices, *, load_type='New'):
        completed_attacks = []
        send = Message.AfterUnitAttackEnd.Send

        def attack_ends(message):
            if message.by_effect.this.paper.card_id == '35008':
                completed_attacks.append((
                    [target.paper.card_id for target in message.attacked_targets],
                    message.total_dealt_damage,
                ))
            return send(message)

        links = {key: list(dict.fromkeys(value)) for key, value in CardsDB.linked_papers.items()}
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch.dict(CardsDB.linked_papers, links),
            patch('game.test.v18_timing_harness.initialize_database'),
            patch.object(Message.AfterUnitAttackEnd, 'Send', new=attack_ends),
            patch.object(WorldRender, 'ErrorOccurred') as errors,
            patch.object(Log, 'Warn') as warnings,
            patch.object(Notify, 'Game') as notices,
            patch.object(Engine, 'SaveCrash'),
        ):
            game = run_scene_with_devices(scene, devices, load_type=load_type)
        errors.assert_not_called()
        warnings.assert_not_called()
        notices.assert_not_called()
        self.assertEqual(game.world.event_manager.timing_occurrences, [])
        return game, completed_attacks

    @staticmethod
    def choice(option, targets=()):
        return CommandDescriptor(HeadlessDeviceManager._DescriptorId(option),
                                 [str(target) for target in targets], [])

    def replay_report(self, decision=None, *, full=False):
        scene = validate_file(Path(__file__).parent / 'fixtures' / 'issue_113_berserker_barrage.json')
        if not full:
            # Step 26 records the unwanted automatic repeat. Preserve the
            # original save and replay through the initial attack only.
            scene.inputs = scene.inputs[:26]
        repeat_prompts = []
        before = []

        def choose(prompt):
            if prompt.event_name == 'WhenPlayerChooseAbility':
                repeat_prompts.append(prompt)
                world = Engine.game.world
                before.append((world.object_manager.card_dict[48].face.health,
                               world.object_manager.card_dict[98].face.health))
                if decision is not None:
                    option = next(option for option in prompt.options
                                  if (option['name'] == 'Cancel') == (not decision))
                    return self.choice(option)
            return None

        devices = HeadlessDeviceManager(choice_provider=choose)
        game, attacks = self.run_game(scene, devices, load_type='InTesting')
        self.assertEqual(
            [operation.crc for operation in game.controller_manager.replay.history_inputs[:len(scene.inputs)]],
            [operation.crc for operation in scene.inputs],
        )
        self.assertFalse(game.world.object_manager.card_dict[123].face.IsInPlay())
        if not full:
            self.assertEqual(before, [(11, 23)])
            self.assertEqual(len(repeat_prompts), 1)
            repeat, cancel = repeat_prompts[0].options
            self.assertEqual(cancel['name'], 'Cancel')
            self.assertEqual(repeat['automatic_targets'], [98])
            self.assertFalse(repeat['automatic_submit'])
        return game, devices, attacks

    def test_reported_save_waits_before_taking_damage_and_repeating(self):
        game, devices, _ = self.replay_report()
        self.assertEqual(game.controller_manager.replay.current_step_id, 26)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerChooseAbility')
        self.assertEqual(game.world.object_manager.card_dict[48].face.health, 11)
        self.assertEqual(game.world.object_manager.card_dict[98].face.health, 23)

    def test_reported_save_cancel_keeps_the_initial_kill_without_extra_damage(self):
        game, devices, attacks = self.replay_report(False)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.object_manager.card_dict[48].face.health, 11)
        self.assertEqual(game.world.object_manager.card_dict[98].face.health, 23)
        self.assertEqual(attacks, [(['01129'], 4)])

    def test_reported_save_confirm_pays_two_damage_and_completes_another_attack(self):
        game, devices, attacks = self.replay_report(True)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.object_manager.card_dict[48].face.health, 9)
        self.assertEqual(game.world.object_manager.card_dict[98].face.health, 19)
        self.assertEqual(attacks, [(['01129'], 4), (['01113'], 4)])

    def test_original_save_still_replays_its_recorded_repeat(self):
        game, devices, attacks = self.replay_report(full=True)
        self.assertEqual(game.controller_manager.replay.current_step_id, 27)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        self.assertEqual(game.world.object_manager.card_dict[48].face.health, 9)
        self.assertEqual(game.world.object_manager.card_dict[98].face.health, 19)
        self.assertEqual(len(attacks), 2)

    def play_with_claws(self, *, repeats, timing='v18_timing', minions=True):
        scene = SceneLoader.NewScene('rhino', None, ['wolverine'], 113)
        scene.rules = ['v16_all', timing]
        setup = iter([
            'puzzle.ClearHand()',
            'puzzle.ChangeFormFor(0, "Hero")',
            *(['puzzle.PutIntoPlay("01172")', 'puzzle.PutIntoPlay("01129")',
               'puzzle.Damage("01129", 3)'] if minions else []),
            'puzzle.Tough("Rhino")',
            'puzzle.CreateHandCards("35008")',
        ])
        played = False
        repeat_prompts = []

        def face(card_id):
            return next(card.face for card in Engine.game.world.object_manager.card_dict.values()
                        if card.face.paper.card_id == card_id and
                        (card.face.IsInPlay() or card.IsInHand()))

        def choose(prompt):
            nonlocal played
            if len(devices.prompts) > 30:
                raise AssertionError('Unexpected repeated prompt')
            world = Engine.game.world
            if prompt.event_name == 'WhenPlayerInTurn':
                command = next(setup, None)
                if command:
                    Engine.game.controller_manager.console.SetCommand(command, world)
                    return CommandDescriptor()
                if not played:
                    played = True
                    claws = next(option for option in prompt.options
                                 if option['bind_id'] == face('35002').card.object_id)
                    return self.choice(claws, [face('35008').card.object_id])
                return None
            if prompt.event_name == 'WhenPlayerLikeInTurn':
                option = next(option for option in prompt.options if option['name'] == 'Play')
                target = face('01172') if minions else world.GetScenario().area_villain.Get()[0]
                return self.choice(option, [target.card.object_id])
            if prompt.event_name == 'WhenPlayerChooseAbility' and played:
                repeat_prompts.append(prompt)
                if len(repeat_prompts) <= repeats:
                    target = face('01129') if len(repeat_prompts) == 1 else world.GetScenario().area_villain.Get()[0]
                    return self.choice(prompt.options[0], [target.card.object_id])
                return self.choice(next(option for option in prompt.options if option['name'] == 'Cancel'))
            return CommandDescriptor() if prompt.show_cancel else HeadlessDeviceManager._DefaultChoice(prompt)

        devices = HeadlessDeviceManager(choice_provider=choose)
        game, attacks = self.run_game(scene, devices)
        self.assertTrue(played)
        self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
        for prompt in repeat_prompts:
            self.assertFalse(prompt.options[0]['automatic_submit'])
            self.assertEqual(prompt.options[-1]['name'], 'Cancel')
        hero = game.world.GetFirstPlayer().GetHero()
        self.assertEqual(hero.health, hero.max_health - 2 - 2 * repeats)
        return game, attacks, repeat_prompts

    def test_each_defeat_offers_a_new_optional_repeat_and_preserves_claws_piercing(self):
        for timing in ('v18_timing', 'no_v18_timing'):
            for repeats in (0, 1, 2):
                with self.subTest(timing=timing, repeats=repeats):
                    game, attacks, prompts = self.play_with_claws(repeats=repeats, timing=timing)
                    self.assertEqual(len(prompts), min(repeats + 1, 2))
                    self.assertEqual(len(attacks), repeats + 1)
                    villain = game.world.GetScenario().area_villain.Get()[0]
                    self.assertEqual(villain.health, villain.max_health - (4 if repeats == 2 else 0))
                    self.assertEqual(villain.IsTough(), repeats != 2)

    def test_attack_that_does_not_defeat_an_enemy_cannot_repeat(self):
        game, attacks, prompts = self.play_with_claws(repeats=0, minions=False)
        self.assertEqual(prompts, [])
        self.assertEqual(len(attacks), 1)
        villain = game.world.GetScenario().area_villain.Get()[0]
        self.assertEqual(villain.health, villain.max_health - 4)


if __name__ == '__main__':
    unittest.main()
