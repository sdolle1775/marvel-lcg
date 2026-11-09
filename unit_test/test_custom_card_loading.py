"""Issue #148: load legacy custom scripts without silently losing abilities."""
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from engine import Engine  # noqa: F401 - establishes project import order
from cards import database
from cards.database import CardsDB
from engine.lib import Ver
from game.card.factory import CardFactory


SCRIPT = """from . import *

def GetAbilities() -> Sequence['Ability']:
    return [AbilityFactory.WhenInYourPlayTurn(
        AbilityType.HeroAction, lambda effect, message: None,
    ).SetName('Réparer')]
"""


class TestCustomCardLoading(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(contextlib.ExitStack())
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(contextlib.chdir(directory))
        for name in ('papers', 'sets_cards', 'linked_papers', 'ability_cache',
                     'ability_link_cards', 'full_link_cards'):
            stack.enter_context(patch.object(CardsDB, name, {}))
        stack.enter_context(patch.object(CardsDB, 'cards_custom_files', []))
        stack.enter_context(patch.object(CardsDB, 'cards_json_file', ''))
        stack.enter_context(patch.object(CardsDB, 'checksum_ok', True))
        stack.enter_context(patch.object(database.CARDS_JSON_FILE, 'value', ''))
        stack.enter_context(patch.object(database.CARDS_JSON_CUSTOM_FILE, 'value', 'custom_card.json'))
        stack.enter_context(patch.object(database.CARDS_JSON_CUSTOM_FILES, 'value', []))
        Ver.Initialize()
        Path('data').mkdir()
        Path('data/sets_info.json').write_text('{}', encoding='utf-8')
        Path('custom_card.json').write_text(json.dumps({'custom': [{
            'card_id': 'custom_148', 'type': 'Environment', 'name': 'Custom rescue',
            'subtitle': '', 'desc': {}, 'traits': [], 'set_name': '', 'text': '',
        }]}), encoding='utf-8')
        CardsDB.Initialize()

    def write_script(self, path, source=SCRIPT, encoding='utf-8'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode(encoding))
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def load_face(self):
        world = MagicMock()
        world.GetPlayerNumIcon.return_value = 1
        return CardFactory.CreateFace(CardsDB.FindCardPaper('custom_148'), world)

    def test_legacy_paths_and_python_source_encodings_load_through_card_factory(self):
        for folder in ('cards', 'cards/pack'):
            for suffix in ('.py', '.py.txt'):
                for encoding in ('utf-8', 'utf-8-sig', 'cp1252'):
                    with self.subTest(folder=folder, suffix=suffix, encoding=encoding):
                        source = '# coding: cp1252\n' + SCRIPT if encoding == 'cp1252' else SCRIPT
                        path = self.write_script(f'{folder}/custom_148{suffix}', source, encoding)
                        CardsDB.ability_cache.clear()
                        try:
                            face = self.load_face()
                            self.assertTrue(any(ability.name == 'Réparer' for ability in face.ability.abilities))
                            cached = CardsDB.ability_cache['custom_148']
                            self.assertIs(CardsDB.FindAbilities('custom_148', 'custom', ''), cached)
                        finally:
                            path.unlink()

    def test_invalid_script_reports_file_and_cause_and_can_be_retried_after_repair(self):
        for source, cause in (
            ('def GetAbilities(:\n', SyntaxError),
            ('import missing_custom_card_dependency_148\n', ModuleNotFoundError),
            ('def GetAbilities():\n    raise ValueError("broken ability")\n', ValueError),
            ('# Missing GetAbilities\n', AttributeError),
        ):
            with self.subTest(cause=cause.__name__):
                CardsDB.ability_cache.clear()
                path = self.write_script('cards/custom_148.py', source)
                with self.assertRaisesRegex(RuntimeError, r'custom_148.*cards/custom_148.py') as raised:
                    self.load_face()
                self.assertIsInstance(raised.exception.__cause__, cause)
                self.assertNotIn('custom_148', CardsDB.ability_cache)
                path.write_bytes(SCRIPT.encode('utf-8'))
                self.assertTrue(any(ability.name == 'Réparer' for ability in self.load_face().ability.abilities))

    def test_unscripted_custom_card_keeps_its_empty_ability_list(self):
        self.load_face()
        self.assertEqual(CardsDB.ability_cache['custom_148'], [])


if __name__ == '__main__':
    unittest.main()
