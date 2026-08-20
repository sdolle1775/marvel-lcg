from core import *
from core.lib import Time

from engine.lib import Json
from engine.log import Log

from game.game_run.game_new import NewGameDescriptor
from game.scene.replay.campaign import CampaignDescriptor
from game.scene.replay.hero import HeroDescriptor

CATEGORY_NAME = "STATUS"


class GameStatus:
    created_at: float | None = None
    created_scenario: str = ""
    created_heroes: List[str] = []
    last_move_at: float | None = None

    @staticmethod
    def Reset() -> None:
        GameStatus.created_at = None
        GameStatus.created_scenario = ""
        GameStatus.created_heroes = []
        GameStatus.last_move_at = None

    @staticmethod
    def OnNewGame(new_game: 'NewGameDescriptor') -> None:
        """Records the table a player just created, before anybody has joined."""
        GameStatus.created_at = Time.GetTime()
        GameStatus.last_move_at = None
        GameStatus.created_scenario = GameStatus._ReadScenarioName(new_game)
        GameStatus.created_heroes = GameStatus._ReadHeroNames(new_game)

    @staticmethod
    def OnMove() -> None:
        """Records that a player answered the game."""
        GameStatus.last_move_at = Time.GetTime()

    @staticmethod
    def GetCreatedAge() -> float | None:
        return GameStatus._GetAge(GameStatus.created_at)

    @staticmethod
    def GetLastMoveAge() -> float | None:
        return GameStatus._GetAge(GameStatus.last_move_at)

    @staticmethod
    def _GetAge(moment: float | None) -> float | None:
        if moment is None:
            return None
        return max(0.0, Time.GetTime() - moment)

    @staticmethod
    def _ReadScenarioName(new_game: 'NewGameDescriptor') -> str:
        try:
            campaign = Json.LoadsAs(new_game.campaign_json, CampaignDescriptor)
            return campaign.name
        except Exception as exc:
            Log.Warn(CATEGORY_NAME, f"Could not read the scenario of the new game: {exc}")
            return ""

    @staticmethod
    def _ReadHeroNames(new_game: 'NewGameDescriptor') -> List[str]:
        names: List[str] = []
        for hero_json in new_game.hero_json:
            try:
                hero = Json.LoadsAs(hero_json, HeroDescriptor)
                names.append(hero.name)
            except Exception as exc:
                Log.Warn(CATEGORY_NAME, f"Could not read a hero of the new game: {exc}")
                names.append("")
        return names
