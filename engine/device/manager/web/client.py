from typing import Final
from core import *
from aiohttp import web
from engine.log import Log
from engine.task.condition import Condition

CATEGORY_NAME = "WEB_DEVICE_MANAGER"

class ClientManager:

    class ClientInfo:

        def __init__(self, player_ids: List[int], url: str, ws: 'web.WebSocketResponse', id: int) -> None:
            self.id = id
            self.player_ids: Final = player_ids
            # A hotseat client controls every seat, including players added by a
            # new game after this websocket was opened.  player_ids is only a
            # snapshot of the controllers that existed at connection time.
            self.is_hot_seat: Final = any(
                part.partition('=')[0] == 'hot_seat'
                for part in url.split('&')
            )
            self.states: Literal["busy", "idle"] = "idle"
            self.url = url
            self.condition = Condition("Client")

            class Pos:
                def __init__(self) -> None:
                    self.x: float = 0
                    self.y: float = 0
            self.mouse = Pos()

            self.ws: Final = ws

        def __repr__(self) -> str:
            return f"{self.id} ({self.player_ids})"

    def __init__(self) -> None:
        self.connected_clients: List[ClientManager.ClientInfo] = []
        self.client_synced: List[int] = [0]*4

    def Add(self, ws: web.WebSocketResponse, player_ids: List[int], url: str):
        self.connected_clients.append(ClientManager.ClientInfo(player_ids, url, ws, len(self.connected_clients)))
        Log.Info(CATEGORY_NAME, f"[Client] Player {player_ids} connected")

    def Remove(self, ws: web.WebSocketResponse):
        client = self.GetClientByWS(ws)
        self.connected_clients.remove(client)
        Log.Info(CATEGORY_NAME, f"[Client] Player {client.player_ids} disconnect")

    def GetClientByWS(self, ws: web.WebSocketResponse) -> 'ClientManager.ClientInfo':
        for client in self.connected_clients:
            if client.ws == ws:
                return client
        assert False

    def GetClients(self, player_id: int):
        clients: List[ClientManager.ClientInfo] = []
        for client in self.connected_clients:
            if client.is_hot_seat or player_id in client.player_ids:
                clients.append(client)
        return clients

    def ClearSync(self):
        self.client_synced = [0]*4

    def RemoveAll(self):
        # clients: List[web.WebSocketResponse] = []
        # for client in self.connected_clients:
        #     clients.append(client)
        # for client in clients:
        #     self.Remove(client)
        #     # TODO: use this
        #     # asyncio.run(client.close())
        pass

    def IsBusy(self, client: 'ClientManager.ClientInfo') -> bool:
        return client.states == "busy"

    def SetStates(self, client: 'ClientManager.ClientInfo', states: Literal["busy", "idle"]):
        client.states = states

    async def WaitCondition(self, client: 'ClientManager.ClientInfo'):
        def check():
            return not self.IsBusy(client)
        client.condition.Wait(check)

    async def NotifyCondition(self, client: 'ClientManager.ClientInfo'):
        client.condition.NotifyAll()

    def GetInfo(self) -> List[str]:
        urls: List[str] = []
        for client in self.connected_clients:
            urls.append(client.url)
        return urls

