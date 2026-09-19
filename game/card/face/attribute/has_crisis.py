from . import *

class CanCrisis(HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        # If a side scheme has the crisis icon,
        # it must be defeated before threat can be removed from the main scheme
        self.printed_crisis = 0

        super().__init__(paper)

        self.RegisterAttribute("Crisis", "printed_crisis")
        self.RegisterInfoDict('crisis')

    @override
    def OnWhenCardEnterPlay(self, message: 'Message.WhenCardEnterPlay') -> bool:
        if super().OnWhenCardEnterPlay(message):
            self.SetCrisisEffectedBy(self.IsCrisis())
            return True
        return False

    ################################################################################
    #
    @override
    def OnResetKeywords(self, by_effect: 'Effect'):
        self.GainCrisis(self.printed_crisis, by_effect)
        return super().OnResetKeywords(by_effect)

    @override
    def OnWhenCardFaceActivated(self, message: 'Message.WhenCardFaceActivated') -> bool:
        if super().OnWhenCardFaceActivated(message):
            self.SetCrisisEffectedBy(self.IsCrisis())
            return True
        return False

    ################################################################################
    #
    @final
    def IsCrisis(self) -> bool:
        return self.crisis > 0

    @final
    @property
    def crisis(self) -> int:
        return self.GetKeyword('Crisis')

    @final
    def SetCrisisEffectedBy(self, diff: int, forced: bool=False):
        from game.effect.rule import GameRule
        from game.operate.worlds import Worlds

        if diff != 0 and (self.IsInPlay() or forced):
            for scheme in Worlds.GetMainSchemesAffectedByCrisis(self):
                scheme.card.ui.SetEffectedBy(diff, GameRule(self))

    @final
    def GainCrisis(self, diff: int, by_effect: 'Effect'):
        self.GainKeyword(diff, 'Crisis', by_effect)
        self.SetCrisisEffectedBy(diff)

    @final
    def SetIgnoreCrisis(self, diff: int, by_effect: 'Effect'):
        self.SetIgnoreKeyword(diff, 'Crisis', by_effect)

    @final
    def ClearCrisisEffectTargets(self):
        self.SetCrisisEffectedBy(-1 * self.IsCrisis(), forced=True)

    @override
    def OnLeaveGameArea(self, game_area: 'GameArea'):
        self.ClearCrisisEffectTargets()
        return super().OnLeaveGameArea(game_area)

    @override
    def OnEnterGameArea(self, game_area: 'GameArea'):
        self.ClearCrisisEffectTargets()
        return super().OnEnterGameArea(game_area)

    @override
    def OnAfterCardLeavePlay(self, message: 'Message.AfterCardLeavePlay') -> None:
        self.ClearCrisisEffectTargets()
        return super().OnAfterCardLeavePlay(message)

