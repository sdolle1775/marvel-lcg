from core import *
from aiohttp import web
from engine.device.web.server.server_base import GameServerBase

from engine.device.web.game_status import GameStatus
from engine.lib import Json
from engine.log import Log
from game.puzzle.puzzle_data import PuzzleData
from game.game_run.game_new import NewGameDescriptor
from game.game_run.campaign_settings import CampaignSettings

class GameServerNewGame(GameServerBase):

    async def new_debug(self, request: web.Request) -> web.Response:
        self.game.Restart()
        return web.json_response({'result': "New game created"})

    async def new_game(self, request: web.Request) -> web.Response:
        data = request.rel_url.query.get('data', "")
        new_game = Json.LoadsAs(data, NewGameDescriptor)
        try:
            CampaignSettings.UpdateForLaunch(new_game)
        except Exception as exc:
            # A local filesystem problem should not prevent the requested game
            # from launching, even though the campaign state could not persist.
            Log.Warn("CAMPAIGN_SETTINGS", f"Could not save campaign settings: {exc}")
        GameStatus.OnNewGame(new_game)
        self.game.NewGame(new_game)
        return web.json_response({'result': "New game created"})

    async def save_campaign_settings(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({'error': "Invalid JSON data"}, status=400)

        campaign_id = data.get('campaign_id', "") if isinstance(data, dict) else ""
        campaign_log = data.get('campaign_log', {}) if isinstance(data, dict) else {}
        if not isinstance(campaign_id, str) or not campaign_id:
            return web.json_response({'error': "No campaign selected"}, status=400)
        if not isinstance(campaign_log, dict):
            return web.json_response({'error': "Invalid campaign log"}, status=400)

        try:
            settings = CampaignSettings.Update(campaign_id, campaign_log)
        except Exception as exc:
            Log.Warn("CAMPAIGN_SETTINGS", f"Could not save campaign settings: {exc}")
            return web.json_response(
                {'error': "Could not save campaign settings"},
                status=500,
            )
        return web.json_response({
            'result': "Campaign settings saved",
            'settings': settings,
        })

    async def clear_campaign_settings(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({'error': "Invalid JSON data"}, status=400)

        campaign_id = data.get('campaign_id', "") if isinstance(data, dict) else ""
        if not isinstance(campaign_id, str) or not campaign_id:
            return web.json_response({'error': "No campaign selected"}, status=400)

        try:
            settings = CampaignSettings.Clear(campaign_id)
        except Exception as exc:
            Log.Warn("CAMPAIGN_SETTINGS", f"Could not clear campaign settings: {exc}")
            return web.json_response(
                {'error': "Could not clear campaign settings"},
                status=500,
            )

        return web.json_response({
            'result': "Campaign settings cleared",
            'settings': settings,
        })

    async def load_replay(self, request: web.Request) -> web.Response:
        self.game.LoadReplay(request.rel_url.query_string)
        return web.json_response({'result': "New game created"})

    async def load_replay_data(self, request: web.Request) -> web.Response:
        from game.scene.scene import Scene

        data = await request.json()
        replay_data = data.get('data', None)

        try:
            step = int(request.rel_url.query_string)
        except:
            step = None

        if replay_data is None:
            return web.json_response({'error': 'No data provided'}, status=400)

        # Process the replay_data as needed
        # Log.Print("Received replay data:", replay_data)

        scene = Json.LoadsAs(replay_data, Scene)
        if step == 0:
            state = 'Replay'
        else:
            state = 'Load'
        self.game.session.LoadScene(scene, step, state)

        return web.json_response({'result': "New game created"})

    async def save_replay_data(self, request: web.Request) -> web.Response:
        data = Json.SaveString(self.game.scene, ignore_check_sum=False)
        compressed_data = Json.DumpGZip(data)
        self.device_manager.AddSize("Save", len(compressed_data))
        return web.Response(body=compressed_data, content_type='application/json', headers={'Content-Encoding': 'gzip'})

    def play_puzzle(self, puzzle: 'PuzzleData'):
        from game.scene.scene import Scene

        def get_cards_text(cards: List[str]) -> str:
            text = ",".join(f"'{x}'" for x in cards)
            return text

        puzzle_pre_command: List[str] = []

        def append_puzzle_command(command: str, cards: List[str]) -> None:
            text = get_cards_text(cards)
            if text:
                puzzle_pre_command.append(f"{command}({text})")

        append_puzzle_command("Puzzle.CreateEncounterDeck", puzzle.encounter_deck)
        append_puzzle_command("Puzzle.CreateEncounterDiscardPile", puzzle.encounter_discard_pile)
        append_puzzle_command("Puzzle.CreateHandCards", puzzle.players[0].hand_cards)
        append_puzzle_command("Puzzle.CreatePlayerDiscardPile", puzzle.players[0].player_discard_pile)
        append_puzzle_command("Puzzle.CreatePlayerDeck", puzzle.players[0].player_deck)
        append_puzzle_command("Puzzle.CreatePlayerAdditionalDeck", puzzle.players[0].set_aside)

        puzzle_data = {
            "version": puzzle.version,
            "metadata": {
                "seed": puzzle.seed,
                "comment": puzzle.comment,
                "cover": puzzle.cover,
                "is_puzzle": True
            },
            "campaign": {
                "version": puzzle.version,
                "name": "Villain",
                "villain": puzzle.villain,
                "expert": puzzle.expert,
                "schemes": puzzle.schemes,
                "set_aside": puzzle.set_aside,
                "encounters": [],
                "encounter_sets": [],
                "modular_sets": []
            },
            "players": [
                {
                    "version": puzzle.version,
                    "name": f"Player {index}",
                    "hero": puzzle.players[index].identities,
                    "hero_deck": [],
                    "obligations": [],
                    "nemesis_set": [],
                    "set_aside": puzzle.players[index].set_aside,
                    "player_deck": []
                }
                for index in range(len(puzzle.players))
            ],
            "puzzle": puzzle_pre_command + puzzle.puzzle_command,
        }

        scene = Json.LoadsAs(Json.Dumps(puzzle_data), Scene)
        scene.UpdateVersion()

        self.game.session.LoadScene(scene, None, 'Replay')
        self.controller_manager.skip.SetSkipTo(0)

    async def load_puzzle(self, request: web.Request) -> web.Response:
        puzzle = Json.LoadAs(request.rel_url.query_string, PuzzleData, check_sum="Warn")
        self.play_puzzle(puzzle)
        return web.json_response({'result': "New game created"})

    async def new_puzzle_replay(self, request: web.Request) -> web.Response:
        from game.scene.scene import Scene

        scene = Json.LoadsAs(request.rel_url.query_string, Scene)
        scene.UpdateVersion()

        self.game.session.LoadScene(scene, None, 'Replay')
        self.controller_manager.skip.SetSkipTo(0)
        return web.json_response({'result': "New game created"})

    async def new_puzzle(self, request: web.Request) -> web.Response:
        puzzle = Json.LoadsAs(request.rel_url.query_string, PuzzleData)
        self.play_puzzle(puzzle)
        return web.json_response({'result': "New game created"})

    async def new_game_online(self, request: web.Request) -> web.Response:
        ip = request.query.get('ip')
        port = int(request.query.get('port', 2345))
        assert ip
        text = self.device_manager.AddOnlineSite(ip, port)
        return web.Response(text=text)

    async def new_game_lan(self, request: web.Request) -> web.Response:
        port = int(request.query.get('port', 2345))
        text = self.device_manager.AddLocalNetworkSite(port)
        return web.Response(text=text)

    @override
    def __init__(self) -> None:
        super().__init__()
        self.AddAwaitGetSecurity('/new', self.new_game)
        self.AddPostSecurity('/save_campaign_settings', self.save_campaign_settings)
        self.AddPostSecurity('/clear_campaign_settings', self.clear_campaign_settings)
        self.AddAwaitGetSecurity('/new_debug', self.new_debug)
        self.AddAwaitGetSecurity('/load_replay', self.load_replay)
        self.AddPostSecurity('/load_replay_data', self.load_replay_data)
        self.AddAwaitGetSecurity('/save_replay_data', self.save_replay_data)
        self.AddAwaitGetSecurity('/load_puzzle', self.load_puzzle)
        self.AddAwaitGetSecurity('/new_puzzle_replay', self.new_puzzle_replay)
        self.AddAwaitGetSecurity('/new_puzzle', self.new_puzzle)
        self.AddAwaitGetSecurity('/new_game_online', self.new_game_online)
        self.AddAwaitGetSecurity('/new_game_lan', self.new_game_lan)
