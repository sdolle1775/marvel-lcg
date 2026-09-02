from core import *
import aiohttp
from engine.device import *
from engine.device.web import *
from engine.lib import Json
from engine.log import Log, Notify
from build import Build

from aiohttp import web
from engine.device.web.server.server_base import GameServerBase
from engine.device.manager.web.client import ClientManager
from engine.task import TaskManager

CATEGORY_NAME = "WEB"

class GameServerSocket(GameServerBase):

    async def BroadcastMousePositions(self):
        clients = self.device_manager.client_manager.connected_clients
        positions = {"mouse_position": [
            {
                'player_id': client.player_ids[0],
                'x': client.mouse.x,
                'y': client.mouse.y
            }
                for client in clients
            ]
        }
        message = Json.Dumps(positions)
        for ws in clients:
            await ws.ws.send_str(message)

    def WebSendRender(self, player_id: int, caller: str) -> None:
        Log.DebugSilent("SYNC", f"Send sync socket")

        device_manager = self.device_manager

        clients = device_manager.client_manager.GetClients(player_id)
        if not clients:
            return

        notify_texts = Notify.Get()

        async def process_client(client: ClientManager.ClientInfo):
            if client.ws.closed:
                return

            nonlocal caller
            nonlocal notify_texts
            await device_manager.client_manager.WaitCondition(client)

            device_manager.client_manager.SetStates(client, "busy")

            remaining_time = self.device_manager.timer.GetRemainingTime() or 0
            game = self.game
            world = game.world
            from game.render.descriptor.frame import FrameDescriptor
            data = FrameDescriptor(
                render_id           = world.render.last_render_id if world else 0,
                game_id             = game.session.game_id,
                ask_players         = self.device_manager.asking_players,
                full_search_presentation_players = (
                    [player_id]
                    if player_id in self.device_manager.full_search_presentations
                    else []
                ),
                remaining_time      = remaining_time,
                max_timeout         = self.device_manager.timer.max_timeout,
                notify_texts        = notify_texts,
                debug_message       = world.render.debug_message if world else "",
                current_step_id     = game.controller_manager.replay.current_step_id,
                max_replay_step_id  = game.controller_manager.replay.GetReplayOperationLen(),
                player_id           = player_id,
                total_players       = world.started_player_num if world else 0,
                show_deck_during_full_search = self.device_manager.controllers[player_id].preferences.show_deck_during_full_search,
                # game.controller_manager.skip.is_skipping,
            )
            try:
                Log.DebugSilent("SYNC", f"[Server] render id: {data.render_id}, player_id: {player_id}, ask_players: {data.ask_players}, clients: {clients}")
                # data_size_bytes = Json.DumpsSize(data)
                # compressed_data = Json.DumpGZip(data)
                # device_manager.AddSize("Socket", len(compressed_data))

                # compressed_data = Json.DumpGZip(data)
                # await client.send_bytes(compressed_data)
                await client.ws.send_json(data.__dict__)
            except Exception as exc:
                Log.FailedTrace(CATEGORY_NAME, exc)
                device_manager.client_manager.Remove(client.ws)
            finally:
                device_manager.client_manager.SetStates(client, "idle")
                await device_manager.client_manager.NotifyCondition(client)

        TaskManager.RunAwaitProcesses(process_client, clients)
        # job = JobManager.AddJob(process_client, clients, name="WebSendRender")
        # JobManager.WaitForAllJobsToComplete(job)

    async def websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        def is_cheat(request: web.Request) -> bool:
            query_params = request.rel_url.query
            return 'debug' in query_params or 'show' in query_params

        def is_replay(request: web.Request) -> bool:
            query_params = request.rel_url.query
            return 'replay' in query_params

        player_ids = self.get_player_ids(request)
        self.device_manager.client_manager.Add(ws, player_ids, request.query_string)

        if Build.release and is_cheat(request):
            self.game.statistics.SetPause(True)

        self.controller_manager.replay.SetIsReplay(is_replay(request))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT: # type: ignore
                    data = str(msg.data) # type: ignore
                    if 'mouse_position' in data:
                        # Update the client's mouse position
                        client = self.device_manager.client_manager.GetClientByWS(ws)
                        data = Json.Loads(data)
                        client.mouse.x = float(data['mouse_position']['x'])
                        client.mouse.y = float(data['mouse_position']['y'])
                        
                        # Broadcast the updated positions to all clients
                        await self.BroadcastMousePositions()
                    elif data.startswith('{'):
                        client_data = Json.Loads(data)
                        settings = client_data.get('client_settings', {})
                        full_search_settings = settings.get(
                            'show_deck_during_full_search',
                            {},
                        )
                        for player_id_text, enabled in full_search_settings.items():
                            player_id = int(player_id_text)
                            if player_id not in player_ids:
                                continue
                            self.set_full_search_preference(player_id, bool(enabled))
                            self.WebSendRender(player_id, "ClientSettings")
                    elif data.startswith('Connected'):
                        if len(player_ids) > 0:
                            self.WebSendRender(player_ids[0], "websocket_handler")
                        self.device_manager.notify.connect.NotifyAll()
                        Log.Debug(CATEGORY_NAME, f'Websocket: {data}')
        except Exception as exc:
            Log.FailedTrace(CATEGORY_NAME, exc)
        finally:
            if any(
                client.ws == ws
                for client in self.device_manager.client_manager.connected_clients
            ):
                self.device_manager.client_manager.Remove(ws)
            # Wake any presentation-only wait so a disconnected searching
            # player can never stall the game indefinitely.
            self.device_manager.notify.WhenPresentation()

        return ws

    @override
    def __init__(self) -> None:
        super().__init__()
        self.AddAwaitGetSecurity('/ws', self.websocket_handler)

