from pathlib import Path
from types import SimpleNamespace
import json
import unittest

from engine import Engine  # noqa: F401 - establishes the project's import order
from engine.device.web.game_status import GameStatus
from engine.device.web.server.server_status import GameServerStatus

from game.render.descriptor.world import WorldDescriptor


def make_card(name: str, card_type: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, card_type=card_type)


def make_server(world, is_running: bool) -> SimpleNamespace:
    controller = SimpleNamespace(
        world=SimpleNamespace(render=SimpleNamespace(descriptor=world)) if world else None,
        game=SimpleNamespace(state=SimpleNamespace(is_running=is_running)),
    )
    return SimpleNamespace(
        get_first_controller=lambda request: controller,
        HeaderCache={},
    )


def make_world(round_id: int, villains, heroes) -> WorldDescriptor:
    world = WorldDescriptor()
    world.round_id = round_id
    world.area_villain = villains
    world.players = [
        WorldDescriptor.PlayerDescriptor(area_hero=[hero]) for hero in heroes
    ]
    return world


class TestGameStatusEndpoint(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        GameStatus.Reset()

    def tearDown(self) -> None:
        GameStatus.Reset()

    async def read_status(self, server) -> dict:
        response = await GameServerStatus.handle_game_status(server, SimpleNamespace())
        return json.loads(response.text)

    async def test_no_game_is_reported_when_nothing_has_been_created(self):
        status = await self.read_status(make_server(None, False))

        self.assertEqual(status["state"], "none")
        self.assertEqual(status["heroes"], [])
        self.assertIsNone(status["created_age_seconds"])

    async def test_a_created_game_is_reported_before_anybody_joins(self):
        GameStatus.created_at = 100.0
        GameStatus.created_scenario = "Rhino"
        GameStatus.created_heroes = ["Spider-Man", "Captain Marvel"]

        status = await self.read_status(make_server(None, False))

        self.assertEqual(status["state"], "created")
        self.assertEqual(status["scenario"], "Rhino")
        self.assertEqual(status["heroes"], [
            {"name": "Spider-Man", "player_id": 0},
            {"name": "Captain Marvel", "player_id": 1},
        ])
        self.assertIsNotNone(status["created_age_seconds"])

    async def test_a_running_game_reports_the_scenario_the_round_and_the_heroes(self):
        world = make_world(
            round_id=3,
            villains=[
                make_card("Rhino Scheme", "MainScheme"),
                make_card("Rhino", "EncounterVillain"),
            ],
            heroes=[
                make_card("Spider-Man", "Hero"),
                make_card("Carol Danvers", "AlterEgo"),
            ],
        )

        status = await self.read_status(make_server(world, True))

        self.assertEqual(status["state"], "running")
        self.assertEqual(status["scenario"], "Rhino")
        self.assertEqual(status["round"], 3)
        self.assertEqual(status["heroes"], [
            {"name": "Spider-Man", "player_id": 0},
            {"name": "Carol Danvers", "player_id": 1},
        ])

    async def test_a_finished_game_is_reported_as_over(self):
        world = make_world(
            round_id=9,
            villains=[make_card("Rhino", "EncounterVillain")],
            heroes=[make_card("Spider-Man", "Hero")],
        )

        status = await self.read_status(make_server(world, False))

        self.assertEqual(status["state"], "over")

    async def test_the_time_of_the_last_move_is_measured_by_the_game(self):
        GameStatus.OnMove()
        world = make_world(
            round_id=1,
            villains=[make_card("Rhino", "EncounterVillain")],
            heroes=[make_card("Spider-Man", "Hero")],
        )

        status = await self.read_status(make_server(world, True))

        self.assertIsNotNone(status["last_move_age_seconds"])
        self.assertGreaterEqual(status["last_move_age_seconds"], 0)

    def test_creating_a_game_records_the_scenario_and_the_heroes(self):
        new_game = SimpleNamespace(
            campaign_json=json.dumps({"version": "1", "name": "Klaw"}),
            hero_json=[
                json.dumps({
                    "version": "1",
                    "name": "Black Panther",
                    "hero": ["01040a"],
                    "hero_deck": [],
                    "obligations": [],
                    "nemesis_set": [],
                }),
            ],
        )

        GameStatus.OnNewGame(new_game)

        self.assertEqual(GameStatus.created_scenario, "Klaw")
        self.assertEqual(GameStatus.created_heroes, ["Black Panther"])
        self.assertIsNone(GameStatus.last_move_at)

    def test_the_game_records_the_moves_and_the_new_games_it_is_told_about(self):
        project_root = Path(__file__).resolve().parents[1]
        new_game = (
            project_root / "engine" / "device" / "web" / "server" / "server_new_game.py"
        ).read_text(encoding="utf-8")
        sync = (
            project_root / "engine" / "device" / "web" / "server" / "server_sync.py"
        ).read_text(encoding="utf-8")
        server = (
            project_root / "engine" / "device" / "web" / "server" / "server.py"
        ).read_text(encoding="utf-8")

        self.assertIn("GameStatus.OnNewGame(new_game)", new_game)
        self.assertIn("GameStatus.OnMove()", sync)
        self.assertIn("GameServerStatus", server)

    def test_the_main_menu_reads_the_status_from_the_game(self):
        project_root = Path(__file__).resolve().parents[1]
        main_html = (project_root / "public" / "main.html").read_text(encoding="utf-8")
        main_status = (
            project_root / "public" / "js" / "menu" / "main_status.ts"
        ).read_text(encoding="utf-8")

        self.assertIn('src="/public/js/menu/main_status.js', main_html)
        self.assertIn("fetch('/game_status', { cache: 'no-store' })", main_status)
        self.assertIn("link.href = `/?p=${hero.player_id}`", main_status)


if __name__ == "__main__":
    unittest.main()
