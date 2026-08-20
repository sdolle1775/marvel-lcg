from core import *
from aiohttp import web

from engine.device.web.game_status import GameStatus
from engine.device.web.server.server_base import GameServerBase

from game.render.descriptor.card import CardDescriptor
from game.render.descriptor.world import WorldDescriptor

CATEGORY_NAME = "STATUS"


class GameServerStatus(GameServerBase):

    async def handle_game_status(self, request: web.Request) -> web.Response:
        controller = self.get_first_controller(request)
        world = controller.world.render.descriptor if controller.world else None
        is_running = controller.game.state.is_running

        if world and world.players:
            state = 'running' if is_running else 'over'
            answer = {
                'state': state,
                'scenario': GameServerStatus._GetScenarioName(world),
                'round': world.round_id,
                'heroes': GameServerStatus._GetHeroes(world),
                'last_move_age_seconds': GameStatus.GetLastMoveAge(),
                'created_age_seconds': GameStatus.GetCreatedAge(),
            }
        elif GameStatus.created_at is not None:
            answer = {
                'state': 'created',
                'scenario': GameStatus.created_scenario,
                'round': 0,
                'heroes': [
                    {'name': name, 'player_id': player_id}
                    for player_id, name in enumerate(GameStatus.created_heroes)
                ],
                'last_move_age_seconds': None,
                'created_age_seconds': GameStatus.GetCreatedAge(),
            }
        else:
            answer = {
                'state': 'none',
                'scenario': "",
                'round': 0,
                'heroes': [],
                'last_move_age_seconds': None,
                'created_age_seconds': None,
            }

        return web.json_response(answer, headers=self.HeaderCache)

    @staticmethod
    def _GetScenarioName(world: 'WorldDescriptor') -> str:
        villains = world.area_villain
        if not villains:
            return ""

        villain = GameServerStatus._FindCard(villains, ['EncounterVillain'])
        if villain is None:
            villain = villains[0]
        return villain.name

    @staticmethod
    def _GetHeroes(world: 'WorldDescriptor') -> List[Dict[str, Any]]:
        heroes: List[Dict[str, Any]] = []
        for player_id, player in enumerate(world.players):
            card = GameServerStatus._FindCard(player.area_hero, ['Hero', 'AlterEgo'])
            heroes.append({
                'name': card.name if card else "",
                'player_id': player_id,
            })
        return heroes

    @staticmethod
    def _FindCard(cards: Sequence['CardDescriptor'], card_types: List[str]) -> 'CardDescriptor|None':
        for card in cards:
            if card.card_type in card_types:
                return card
        return None

    @override
    def __init__(self) -> None:
        super().__init__()
        self.AddAwaitGetSecurity('/game_status', self.handle_game_status)
