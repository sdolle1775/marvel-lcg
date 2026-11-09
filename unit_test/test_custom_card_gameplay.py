"""Exercise custom files through match setup, play, and action resolution."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine import Engine
from cards import database
from cards.database import CardsDB
from engine.file import Cache
from engine.log import Log
from game.scene import SceneLoader
from game.scene.replay.operation import CommandDescriptor
from game.test.headless import HeadlessDeviceManager
from game.test.v18_timing_harness import initialize_database, run_scene_with_devices
from game.world.world_render import WorldRender


ROOT = Path(__file__).resolve().parents[1]
EVENT = 'custom_148_event'
ALLY = 'custom_148_ally'
SUPPORT = 'custom_148_support'

EVENT_SCRIPT = '''from . import *

def GetAbilities() -> Sequence['Ability']:
    def strike(effect, message):
        effect.this.DealDamage(effect.targets, 2, effect)
    return [AbilityFactory.WhenInYourPlayTurn(
        AbilityType.HeroAction, strike,
    ).SetPlay().SetLabel('attack').SetTarget(Enemy).SetName('Éclair')]
'''

SUPPORT_SCRIPT = '''# coding: cp1252
from . import *

def GetAbilities() -> Sequence['Ability']:
    def heal(effect, message):
        effect.this.HealthUnits(effect.targets, 2, effect)
    return [AbilityFactory.WhenInYourPlayTurn(
        AbilityType.HeroAction, heal,
    ).SetTarget('YourIdentity').SetCostFunc(CostFunc.Exhaust('This')).SetName('Récupérer')]
'''


class TestCustomCardGameplay(unittest.TestCase):
    def test_custom_event_ally_and_support_load_and_resolve_in_a_match(self):
        for config_name in ('cards_json_custom_file', 'cards_json_custom_files'):
            with self.subTest(config=config_name), contextlib.ExitStack() as stack:
                directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
                (directory / 'cards/pack').mkdir(parents=True)
                (directory / f'cards/{EVENT}.py').write_bytes(EVENT_SCRIPT.encode('utf-8-sig'))
                (directory / f'cards/pack/{ALLY}.py').write_text(
                    (ROOT / 'cards/test_001.py').read_text(encoding='utf-8'), encoding='utf-8',
                )
                (directory / f'cards/{SUPPORT}.py.txt').write_bytes(SUPPORT_SCRIPT.encode('cp1252'))
                definitions = []
                for card_id, card_type, name in (
                    (EVENT, 'Event', 'Custom Éclair'),
                    (ALLY, 'Ally', 'Custom Test Ally'),
                    (SUPPORT, 'Support', 'Custom Recovery'),
                ):
                    desc = {'Cost': '0', 'RES': 'B', 'Class': 'Basic'}
                    if card_id == ALLY:
                        desc.update(HP='3', ATK='1*', THW='1*')
                    definitions.append(dict(
                        card_id=card_id, type=card_type, name=name, subtitle='',
                        desc=desc, traits=[], set_name='', text='',
                    ))
                definition_path = directory / 'custom_card.json'
                definition_path.write_text(json.dumps({'custom': definitions}), encoding='utf-8')
                for name in ('papers', 'sets_cards', 'linked_papers', 'ability_cache',
                             'ability_link_cards', 'full_link_cards'):
                    stack.enter_context(patch.object(CardsDB, name, {}))
                for name in ('cards_custom_files', 'cards_json_file', 'checksum_ok'):
                    stack.enter_context(patch.object(CardsDB, name, getattr(CardsDB, name)))
                stack.enter_context(patch.object(Cache, 'link_pic', {}))
                stack.enter_context(patch.object(database.CARDS_JSON_FILE, 'value', str(ROOT / 'data/cards.json')))
                stack.enter_context(patch.object(database.CARDS_JSON_CUSTOM_FILE, 'value',
                                                 str(definition_path) if config_name.endswith('_file') else ''))
                stack.enter_context(patch.object(database.CARDS_JSON_CUSTOM_FILES, 'value',
                                                 [str(definition_path)] if config_name.endswith('_files') else []))
                initialize_database()
                scene = SceneLoader.NewScene('rhino', None, ['spider_man'], 148)
                scene.rules = ['v16_all', 'v18_timing']
                scene.players[0].player_deck.extend([EVENT, ALLY, SUPPORT])
                stack.enter_context(patch('game.test.v18_timing_harness.initialize_database'))
                stack.enter_context(contextlib.chdir(directory))
                setup = iter([
                    'puzzle.ClearHand()',
                    'puzzle.ChangeFormFor(0, "Hero")',
                    'puzzle.Damage("01001a", 3)',
                    f'puzzle.CreateHandCards("{EVENT}", "{ALLY}", "{SUPPORT}")',
                ])
                actions = iter([
                    (EVENT, 'Éclair'), (ALLY, 'Play'), (SUPPORT, 'Play'),
                    (ALLY, 'Deal_4_damage'), (SUPPORT, 'Récupérer'),
                ])
                completed = []

                def face(card_id):
                    return next(card.face for card in Engine.game.world.object_manager.card_dict.values()
                                if card.face.paper.card_id == card_id and
                                (card.IsInHand() or card.face.IsInPlay()))

                def choose(prompt):
                    if len(devices.prompts) > 40:
                        raise AssertionError('Custom-card match did not reach its checkpoint')
                    if prompt.event_name != 'WhenPlayerInTurn':
                        return CommandDescriptor() if prompt.show_cancel else devices._DefaultChoice(prompt)
                    command = next(setup, None)
                    if command:
                        Engine.game.controller_manager.console.SetCommand(command, Engine.game.world)
                        return CommandDescriptor()
                    action = next(actions, None)
                    if action is None:
                        return None
                    card_id, name = action
                    option = next((option for option in prompt.options
                                   if option['bind_id'] == face(card_id).card.object_id and option['name'] == name), None)
                    self.assertIsNotNone(option, (action, [(item['bind_id'], item['name']) for item in prompt.options]))
                    target = (Engine.game.world.GetScenario().area_villain.Get()[0]
                              if card_id == EVENT or name == 'Deal_4_damage'
                              else Engine.game.world.GetFirstPlayer().GetIdentity())
                    completed.append(action)
                    return CommandDescriptor(devices._DescriptorId(option), [str(target.card.object_id)], [])

                devices = HeadlessDeviceManager(choice_provider=choose)
                log = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                errors = stack.enter_context(patch.object(WorldRender, 'ErrorOccurred'))
                crashes = stack.enter_context(patch.object(Engine, 'SaveCrash'))
                warnings = stack.enter_context(patch.object(Log, 'Warn'))
                game = run_scene_with_devices(scene, devices)
                errors.assert_not_called()
                crashes.assert_not_called()
                warnings.assert_not_called()
                self.assertEqual(len(completed), 5, log.getvalue())
                self.assertEqual(devices.stopped_prompt.event_name, 'WhenPlayerInTurn')
                hero = game.world.GetFirstPlayer().GetHero()
                villain = game.world.GetScenario().area_villain.Get()[0]
                self.assertEqual(villain.health, villain.max_health - 6)
                self.assertEqual(hero.health, hero.max_health - 1)
                self.assertTrue(face(ALLY).IsExhaust())
                self.assertTrue(face(SUPPORT).IsExhaust())
                self.assertTrue(any(card.paper.card_id == EVENT
                                    for card in game.world.GetFirstPlayer().discard_pile.Get()))
                for card_id in (EVENT, ALLY, SUPPORT):
                    self.assertTrue(CardsDB.ability_cache[card_id])


if __name__ == '__main__':
    unittest.main()
