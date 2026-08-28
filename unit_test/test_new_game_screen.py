from pathlib import Path
import unittest


class TestNewGameScreen(unittest.TestCase):

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def scene_html(self) -> str:
        return (self.project_root / "public" / "scene.html").read_text(encoding="utf-8")

    @property
    def new_game(self) -> str:
        return (
            self.project_root / "public" / "js" / "menu" / "new_game.ts"
        ).read_text(encoding="utf-8")

    @property
    def marvelcdb(self) -> str:
        return (
            self.project_root / "public" / "js" / "module" / "marvelcdb.ts"
        ).read_text(encoding="utf-8")

    def test_the_new_game_screen_loads_its_own_style_and_module(self):
        html = self.scene_html

        self.assertIn('<link rel="stylesheet" href="/public/css/menu/new-game.css">', html)
        self.assertIn('<script src="/public/js/menu/new_game.js?v=1.1.1r" type="module"></script>', html)

    def test_the_menu_folder_is_compiled(self):
        tsconfig = (
            self.project_root / "public" / "js" / "tsconfig.json"
        ).read_text(encoding="utf-8")

        self.assertIn('"menu/**/*.ts"', tsconfig)

    def test_the_picker_is_built_with_one_round_of_requests(self):
        html = self.scene_html

        self.assertIn(
            "const scenario_buttons = await Promise.all(scenario_names.map(text => createButtons(text)))",
            html,
        )
        self.assertIn(
            "const encounter_buttons = await Promise.all(encounter_names.map(text => createButtons(text)))",
            html,
        )
        self.assertIn(
            "const nemesis_buttons = await Promise.all(nemesis_names.map(text => createButtons(text, true)))",
            html,
        )

    def test_the_setup_requests_still_bypass_the_browser_cache(self):
        html = self.scene_html

        for endpoint in (
            "get_sets_json?",
            "get_sets_custom_scenario?",
            "list_scenarios?",
            "list_encounter_sets?",
            "get_encounter_set_json?",
            "get_scenario_json?",
        ):
            self.assertIn(f"fetchFresh(`{endpoint}", html)

    def test_a_hero_seat_opens_the_picker_and_reports_the_chosen_deck(self):
        new_game = self.new_game

        self.assertIn("NewGameScreen.openPicker(slot)", new_game)
        self.assertIn("window.SetHero(hero, slot)", new_game)
        self.assertIn("window.Reset(input)", new_game)
        self.assertIn("event.stopImmediatePropagation()", new_game)
        self.assertIn("caption.aspect.textContent = Array.from(aspects).join(' / ')", new_game)

    def test_the_names_shown_in_the_screen_are_written_to_be_read(self):
        new_game = self.new_game
        css = (
            self.project_root / "public" / "css" / "menu" / "new-game.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".replace(/\\b[IVX]+\\b/gi, numeral => numeral.toUpperCase())", new_game)
        self.assertIn("static toIdentityName(name: string): string", new_game)

        self.assertIn('#campaign_log_container input[type="checkbox"]', css)

    def test_an_imported_deck_is_resolved_by_its_identity_code(self):
        marvelcdb = self.marvelcdb

        self.assertIn("deck.hero_code || (deck.hero_name", marvelcdb)
        self.assertIn("fetch(`get_hero_json?${identity}`)", marvelcdb)
        self.assertIn("hero_deck.aspect = meta['aspect'] || \"\"", marvelcdb)
        self.assertIn("hero_deck.aspect2 = meta['aspect2'] || \"\"", marvelcdb)

    def test_an_imported_deck_leaves_out_the_cards_of_the_identity(self):
        marvelcdb = self.marvelcdb

        self.assertIn('static readonly EXCLUDED_CARD_ID = "26002"', marvelcdb)
        self.assertIn('card_dict[card_id].class === "Hero"', marvelcdb)

    def test_both_published_and_shared_decks_are_accepted(self):
        marvelcdb = self.marvelcdb

        self.assertIn("https://marvelcdb.com/api/public/decklist/${deck_id}.json", marvelcdb)
        self.assertIn("https://marvelcdb.com/api/public/deck/${deck_id}.json", marvelcdb)


if __name__ == "__main__":
    unittest.main()
