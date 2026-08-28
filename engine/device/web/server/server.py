from engine.device.web.server.server_files import GameServerFiles
from engine.device.web.server.server_html import GameServerHTML
from engine.device.web.server.server_get import GameServerGet
from engine.device.web.server.server_new_game import GameServerNewGame
from engine.device.web.server.server_socket import GameServerSocket
from engine.device.web.server.server_sync import GameServerSync
from engine.device.web.server.server_status import GameServerStatus
from engine.device.manager.web.manager import WebDeviceManager

class GameServer(GameServerFiles, GameServerHTML, GameServerGet, GameServerNewGame, GameServerSocket, GameServerSync, GameServerStatus):

    def __init__(self, manager: 'WebDeviceManager') -> None:
        self.SetManager(manager)
        super().__init__()

