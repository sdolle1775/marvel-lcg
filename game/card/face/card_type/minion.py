from core import *
from game.card.face import *
from game.ability import *
from game.message import *
from game.player import *
from game.world.game_area import *
from cards.paper import Paper

@final
class Minion(Enemy, CanQuickstrike, CanTeamwork, HasGuard, HasPatrol, HasVillainous, HasAccelerationIcon, HasHazard, HasAmplify, CanAttach, EncounterNonVillainCard, FinalType):
    @override
    def __init__(self, paper: 'Paper') -> None:
        self.nemesis = ""

        super().__init__(paper)

        self.RegisterAttribute("Nemesis", "nemesis", str)

    @override
    def GetInfoDict(self) -> Dict[str, int]:
        # We show ATK .. first
        # not self.card.area.flags.is_upgrades and \
        if self.IsInPlay() and \
            self.engaged_player != None:
            engaged_with = self.GetEngagedPlayer().player_id + 1
        else:
            engaged_with = 0
        return super().GetInfoDict() | {
            'engaged_with': engaged_with,
        }

    ################################################################################
    #
    @override
    def OnAfterCardRevealedEnd(self, message: 'Message.AfterCardRevealedEnd') -> None:
        if not message.world.is_game_over:
            assert not self.card.area.flags.is_dealt_encounter, f"{self.card.area=}"

        if self.card.area.flags.is_in_play:
            if self.engaged_player == None:
                assert self.card.world.is_game_over, f"{self.engaged_player=}"
        return super().OnAfterCardRevealedEnd(message)

    @override
    def OnWhenCardRevealed(self, revealed_message: 'Message.WhenCardRevealed') -> None:
        from game.effect.rule import UniqueMinionRevealed
        player = revealed_message.GetToPlayer()
        if self.PutIntoPlay(player, revealed_message.by_effect):
            return super().OnWhenCardRevealed(revealed_message)
        else:
            # If a unique minion is revealed from the encounter deck and attempts to enter play while another unique character with the same title is already in play, the player who is revealing that minion discards it, then reveals a new card from the encounter deck.
            if revealed_message.IsFromEncounterDeck():
                player.DealEncounterCards(1, UniqueMinionRevealed(self))
            return None

    @override
    def OnPutIntoPlay(self, message: 'Message.WhenCardPutIntoPlay') -> 'bool':
        player = message.GetToPlayer()
        if self.engaged_player == player:
            return True
        if self.EngagePlayer(player, message.by_effect):
            return super().OnPutIntoPlay(message)
        else:
            return False

    def ClearGuardPatrolEffectTargets(self):
        self.SetGuardPatrolEffectedBy(-1 * self.IsGuard(), -1 * self.IsPatrol(), forced=True)

    @override
    def OnLeaveGameArea(self, game_area: 'GameArea'):
        self.ClearGuardPatrolEffectTargets()
        return super().OnLeaveGameArea(game_area)

    @override
    def OnEnterGameArea(self, game_area: 'GameArea'):
        self.ClearGuardPatrolEffectTargets()
        return super().OnEnterGameArea(game_area)

    @override
    def OnAfterCardLeavePlay(self, message: 'Message.AfterCardLeavePlay') -> None:
        self.ClearGuardPatrolEffectTargets()
        return super().OnAfterCardLeavePlay(message)

    # @override
    # def OnWhenEnterPlay(self):
    #     self.SetGuardPatrolEffectedBy(self.IsGuard(), self.IsPatrol())
    #     return super().OnWhenEnterPlay()

    ################################################################################
    #
    def SetGuardPatrolEffectedBy(self, guard_diff: int, patrol_diff: int, forced: bool=False):
        from game.effect.rule import GameRule
        from game.operate.worlds import Worlds

        if guard_diff != 0 and (self.card.area.flags.is_engaged or forced):
            for villain in Worlds.GetVillains(self.card.game_area):
                villain.card.ui.SetEffectedBy(guard_diff, GameRule(self))
        if patrol_diff != 0 and (self.card.area.flags.is_engaged or forced):
            for scheme in Worlds.GetMainSchemes(self.card.game_area):
                scheme.card.ui.SetEffectedBy(patrol_diff, GameRule(self))

    ################################################################################
    #
    def OnWhenCardEnterPlay(self, message: 'Message.WhenCardEnterPlay') -> bool:
        if not super().OnWhenCardEnterPlay(message):
            return False
        # Fix "56077"
        if self.card.area.flags.is_engaged:
            self.OnEngagePlayer(message.by_effect)
        return True

    @final
    def OnEngagePlayer(self, by_effect: 'Effect'):
        player = self.GetEngagedPlayer()
        would_message = Message.WhenMinionWouldEngagePlayer(self, player, by_effect)
        would_message.Send()

        engaged_message = Message.WhenMinionEngagePlayer(would_message)
        engaged_message.Send()

        if not bool(self.card.world.rule.v18_timing):
            self.ResolveQuickstrike(player)

        after_message = Message.AfterMinionEngagePlayer(self, player, engaged_message)
        after_message.Send()

        self.SetGuardPatrolEffectedBy(self.IsGuard(), self.IsPatrol())

    @override
    def OnWhenCardFaceActivated(self, message: 'Message.WhenCardFaceActivated') -> bool:
        if not super().OnWhenCardFaceActivated(message):
            return False
        self.SetGuardPatrolEffectedBy(self.IsGuard(), self.IsPatrol())
        return True

    def EngagePlayer(self, player: 'Player', by_effect: 'Effect') -> bool:
        from game.effect.rule import GameRule
        from game.operate.faces import Faces

        # card abilities cannot cause the minion to engage with the same player again
        if self.engaged_player == player:
            return True

        was_in_play = self.card.area.flags.is_in_play

        if Faces.MoveAllTo([self], player.engaged_minions, GameRule(self)):
            # if was not in play, `OnEngagePlayer` is called in `OnWhenCardEnterPlay`
            if was_in_play:
                self.OnEngagePlayer(by_effect)
            return True
        else:
            return False

    def GetEngagedPlayer(self) -> 'Player':
        if self.engaged_player == None:
            return self.card.area.GetOwnerPlayer()
        assert self.engaged_player, f"{self=}"
        return self.engaged_player

    @property
    def engaged_player(self) -> 'Player|None':
        if self.card.area.flags.is_engaged:
            return self.card.area.play_area
        return None

