from . import *

class HasTeamwork(HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        # After a minion with teamwork enters play and engages a
        # player, if there is at least one other minion that shares the
        # specified trait in play, the minion that just entered play
        # activates against the player it is engaged with.
        self.printed_teamwork: "CardFace.TRAITS|None" = None
        self.teamwork_internal: Dict["CardFace.TRAITS", List['CardFace']] = {}

        super().__init__(paper)

        self.RegisterAttribute("Teamwork", "printed_teamwork", str)
        self.RegisterInfoDict('teamwork')

    def CheckPrintedValue(self):
        from game.element.utility import IsTrait
        assert self.printed_teamwork == None or IsTrait(self.printed_teamwork)
        return super().CheckPrintedValue()

    ################################################################################
    #
    @override
    def OnResetKeywords(self, by_effect: 'Effect'):
        if self.printed_teamwork:
            self.GainTeamwork(1, self.printed_teamwork, by_effect)
        return super().OnResetKeywords(by_effect)

    def GainTeamwork(self, diff: int, teamworks: "CardFace.TRAITS"|List["CardFace.TRAITS"], by_effect: 'Effect'):
        face = by_effect.this
        def gain_teamwork(trait: "CardFace.TRAITS"):
            if diff == 1:
                if trait in self.teamwork_internal:
                    self.teamwork_internal[trait].append(face)
                else:
                    self.teamwork_internal[trait] = [face]
            elif diff == -1:
                self.teamwork_internal[trait].remove(face)
                if self.teamwork_internal[trait] == []:
                    del self.teamwork_internal[trait]
            else:
                assert False

        the_traits: List["CardFace.TRAITS"] = []
        if isinstance(teamworks, list):
            the_traits = teamworks
        else:
            the_traits = [teamworks]

        for trait in the_traits:
            gain_teamwork(trait)

    @property
    def teamwork(self) -> List["CardFace.TRAITS"]:
        return [x for x in self.teamwork_internal if len(self.teamwork_internal[x]) > 0]

class CanTeamwork(HasTeamwork):

    @override
    def GetAbilities(self) -> List['Ability']:
        return [
            Ability(
                AbilityType.ForcedResponse,
                Message.AfterCardEnterPlay,
                [
                    lambda effect, message:
                        bool(effect.world.rule.v18_timing) and
                        effect.this is message.trigger and
                        bool(effect.this.CastTo(CanTeamwork).teamwork) and
                        effect.this.IsInPlay()
                ],
                lambda effect, message:
                    effect.this.CastTo(CanTeamwork).ResolveTeamwork(),
                is_local=True,
            ).SetName("Teamwork")
        ] + super().GetAbilities()

    def ResolveTeamwork(self) -> None:
        from game.effect.rule import Teamwork
        from game.card.face.card_type import Minion
        from game.operate.worlds import Worlds

        if not self.teamwork:
            return

        has_teamwork = False
        minions = Worlds.GetOnFieldMinions(self.card.game_area)
        for minion in minions:
            if minion != self and minion.HasTrait(*self.teamwork):
                has_teamwork = True
                break

        if has_teamwork:
            # The v1.8 keyword activates only the entering minion, including
            # games that did not also enable the older v1.6 rule switches.
            if self.card.world.rule.v18_timing or self.card.world.rule.v16_teamwork:
                minion = self.card.CastTo(Minion)
                minion.DoActivate(minion.GetEngagedPlayer(), Teamwork(minion))
            else:
                for minion in minions:
                    if minion.teamwork == self.teamwork and not minion.IsDefeated():
                        minion.DoActivate(minion.GetEngagedPlayer(), Teamwork(minion))

    @override
    def OnAfterCardEnterPlay(self, message: 'Message.AfterCardEnterPlay') -> None:
        if not bool(self.card.world.rule.v18_timing):
            self.ResolveTeamwork()

        return super().OnAfterCardEnterPlay(message)

