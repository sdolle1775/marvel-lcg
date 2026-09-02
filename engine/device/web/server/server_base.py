from core import *
from engine.network import WebServer
from aiohttp import web
from engine.device.manager.web.manager import WebDeviceManager
from engine.controller import *

class GameServerBase(WebServer):

    def __init__(self) -> None:
        super().__init__()

    def SetManager(self, manager: 'WebDeviceManager'):
        self.device_manager = manager

    def get_player_ids(self, request: web.Request) -> List[int]:
        is_hot_seat = 'hot_seat' in request.rel_url.query
        if is_hot_seat:
            manager = self.controller_manager
            return list(range(manager.total_players))

        p = request.query.get('p', '0')
        if p == '':
            return [0]

        player_ids = p.split(',')
        if player_ids:
            player_ids = [int(id) for id in player_ids]
        else:
            player_ids = [0]
        return player_ids

    def get_first_controller(self, request: web.Request) -> 'Controller':
        player_ids = self.get_player_ids(request)
        player_id = player_ids[0]
        return self.device_manager.controllers[player_id]

    def set_full_search_preference(self, player_id: int, enabled: bool) -> None:
        if player_id < 0 or player_id >= len(self.device_manager.controllers):
            return
        controller = self.device_manager.controllers[player_id]
        controller.SetShowDeckDuringFullSearch(enabled)
        if not enabled:
            self.device_manager.AcknowledgeFullSearchPresentation(player_id)

    @property
    def controller_manager(self):
        controller = self.device_manager.controllers[0]
        return controller.manager

    @property
    def game(self):
        controller = self.device_manager.controllers[0]
        return controller.game

