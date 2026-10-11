from core import *

from engine.file import Cache
from engine.lib import ImageLib
from engine.device.web import *

from aiohttp import web
from engine.device.web.server.server_base import GameServerBase

CATEGORY_NAME = "WEB"

class GameServerFiles(GameServerBase):

    def ImageResponse(self, card_id: str, image_bytes: bytes) -> web.Response:
        headers = dict(self.HeaderCache)
        retry_seconds = Cache.GetImageRetrySeconds(card_id)
        if retry_seconds is not None:
            # A valid placeholder is still a failed download. Let the client
            # replace it automatically, and never cache it as finished artwork.
            headers['X-Card-Image-Retry-After'] = str(retry_seconds)
            headers['Cache-Control'] = 'no-store'
        return web.Response(
            body=image_bytes,
            content_type=ImageLib.GetContentType(image_bytes),
            headers=headers,
        )

    async def handle_marvel(self, request: web.Request) -> web.StreamResponse:
        if request.query_string == '':
            return self.ReadFile('./public/main.html')
        else:
            return self.ReadFile('./public/marvel.html')

    async def handle_players_404(self, request: web.Request) -> web.StreamResponse:
        player = request.match_info.get('player')
        return web.Response(text=f"Please visiting /?p={player}", status=404)

    def handle_sets_image(self, request: web.Request) -> web.StreamResponse:
        file_path = request.path

        image_bytes = Cache.LoadImage(file_path)

        return self.ImageResponse(file_path, image_bytes)

    def handle_image_request(self, request: web.Request) -> web.StreamResponse:
        # file_path = request.match_info['path']
        file_path = request.path
        file_path = file_path.split("/")[-1]

        image_bytes = Cache.LoadImage(file_path)
        image_size = len(image_bytes)

        self.device_manager.AddSize("Image", image_size)

        return self.ImageResponse(file_path, image_bytes)

    @override
    def __init__(self) -> None:
        super().__init__()

        self.AddDefaultGet()

        self.AddAwaitGetSecurity('/', self.handle_marvel)
        self.AddAwaitGetSecurity(r'/p={player:\d+}', self.handle_players_404)
        self.AddAwaitGetSecurity('/watch', self.handle_marvel)

        self.AddNonAwaitGetSecurity(r'/sets/{path:.+}', self.handle_sets_image)
        self.AddNonAwaitGetSecurity(r'/{path:.+}', self.handle_image_request)

