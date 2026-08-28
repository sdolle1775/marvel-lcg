from core import *
from engine.lib import Json
from engine.log import Log
from engine.device import *
from engine.device.web import *
from engine.device.web.game_status import GameStatus

from aiohttp import web
from engine.device.web.server.server_base import GameServerBase

CATEGORY_NAME = "WEB"

class GameServerSync(GameServerBase):

    def get_render_id(self, request: web.Request) -> int:
        return int(request.rel_url.query.get('r', 0))

    def get_game_id(self, request: web.Request) -> int:
        return int(request.rel_url.query.get('g', 0))

    async def handle_debug_command(self, request: web.Request) -> web.Response:
        controller = self.get_first_controller(request)
        controller_manager = controller.manager
        debug_cmd = Unquote(request.rel_url.query_string)
        controller_manager.console.SetCommand(debug_cmd, controller.world)

        if controller_manager.console.debug_cmds or \
            controller_manager.console.debug_break or \
            controller_manager.skip.is_skipping or \
            controller_manager.skip.skip_to > 0 or \
            controller_manager.replay.is_updated:
            self.device_manager.ExitWait()

        return web.Response(text=debug_cmd)

    async def handle_client_updated(self, request: web.Request) -> web.Response:
        render_id = self.get_render_id(request)
        player_ids = self.get_player_ids(request)
        game_id = self.get_game_id(request)

        for player_id in player_ids:
            self.device_manager.ClientUpdateRenderId(player_id, render_id, game_id)
        Log.DebugSilent("SYNC", f"[Client] Updated, render id: {render_id}, player_id: {player_ids}")
        return web.Response(status=200)

    async def handle_get_ask(self, request: web.Request) -> web.Response:
        player_ids = self.get_player_ids(request)

        if self.device_manager.asking_players == []:
            return web.json_response({})

        data = None
        for player_id in player_ids:
            if player_id in self.device_manager.asking_players:
                if data == None:
                    data = asdict(self.device_manager.ask_options[player_id])
                else:
                    list1 = Json.LoadsAs(data['options_json'], List[Any])
                    list2 = Json.LoadsAs(asdict(self.device_manager.ask_options[player_id])['options_json'], List[Any])
                    combined_list = list1 + list2
                    data['options_json'] = Json.Dumps(combined_list)
            pass

        if data == None:
            return web.json_response({})

        Log.Debug(CATEGORY_NAME, f"[Client] ask_player_id: {player_ids}")

        # data_size = Json.DumpsSize(data)
        # Game.run.device_manager.GetConfig(WebDeviceConfig).AddSize("Ask", data_size)
        # return web.json_response(data)
        compressed_data = Json.DumpGZip(data)
        self.device_manager.AddSize("Ask", len(compressed_data))
        return web.Response(body=compressed_data, content_type='application/json', headers={'Content-Encoding': 'gzip'})

    async def handle_get_world(self, request: web.Request) -> web.Response:
        player_ids = self.get_player_ids(request)
        controller = self.get_first_controller(request)
        if controller.world:
            data = controller.world.render.descriptor
        else:
            # Bug here, if we return {}, ts code will read null and crash
            from game.render.descriptor.world import WorldDescriptor
            data = WorldDescriptor()

        compressed_data = Json.DumpGZip(data)

        self.device_manager.AddSize("World", len(compressed_data))
        Log.DebugSilent("SYNC", f"[Client] Get world {data.render_id}, player_id: {player_ids}")

        return web.Response(body=compressed_data, content_type='application/json', headers={'Content-Encoding': 'gzip'})

    async def handle_post(self, request: web.Request) -> web.Response:
        post_data = await request.text()
        player_ids = self.get_player_ids(request)
        post_json = Unquote(post_data)
        assert len(player_ids) == 1
        if post_json:
            GameStatus.OnMove()
            for player_id in player_ids:
                if player_id in self.device_manager.asking_players:
                    self.device_manager.WhenInput(post_json, player_id)

        return web.Response(status=200)

    @override
    def __init__(self) -> None:
        super().__init__()
        self.AddAwaitGetSecurity('/debug', self.handle_debug_command)

        self.AddAwaitGetSecurity('/client_updated', self.handle_client_updated)
        self.AddAwaitGetSecurity('/get_ask', self.handle_get_ask)
        self.AddAwaitGetSecurity('/get_world', self.handle_get_world)

        self.AddPostSecurity('/post', self.handle_post)

