from core import *
from game.card.face.base import *
from game.card.face import *
from game.deck import *
from game.ability import *
from game.message import *
from cards.paper import Paper

class Scheme2(HasAmplify, HasHazard, CanHinder, CanPlaceCounter, HasAssault, HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        self.start_threat = 0

        self.corresponding_villain_name: str|None = None

        super().__init__(paper)

        self.RegisterAttribute("StartingThreat", "start_threat")

        def parse(value: str):
            self.corresponding_villain_name = value
            from game.card.face.base import Villain
            Villain.VILLAIN_SCHEME[value] = self.name
        self.RegisterAttribute("CorrespondingCard", parse)

    @override
    def CheckPrintedValue(self):
        assert self.start_threat >= 0
        return super().CheckPrintedValue()

    @override
    def OnWouldEnterPlay(self, into_area: 'Deck') -> bool:
        self.ResetStartThreat()
        return super().OnWouldEnterPlay(into_area)

    def ResetStartThreat(self, *, by_flip: bool=False):
        from game.effect.rule import ResetKeyword
        start_threat = self.start_threat
        if by_flip:
            # See "27102a" "27100b" in expert mode
            start_threat += self.threat
        self.SetTokens(start_threat, 'threat', ResetKeyword(self))

    @override
    def OnFlip(self, by_effect: 'Effect', origin_face: 'CardFace|None'):
        if self.IsInPlay():
            self.ResetStartThreat(by_flip=True)
        return super().OnFlip(by_effect, origin_face)

    @override
    def OnBeDefeated(self, would_defeated_message: 'Message.WhenSchemeWouldBeDefeated|Message.WhenUnitWouldBeDefeated', *, as_asset: bool, ignore_when_defeated: bool):
        from game.operate.faces import Faces

        being_message = would_defeated_message.being_message
        by_effect = would_defeated_message.by_effect
        killer = would_defeated_message.killer

        assert isinstance(would_defeated_message, Message.WhenSchemeWouldBeDefeated)

        if being_message != None:
            assert type(being_message) is Message.WhenSchemeBeingThwart

        # Fix "04122"
        defeated_message = Message.WhenSchemeBeDefeated(self, would_defeated_message, ignore_when_defeated)
        defeated_message.Send()
        if defeated_message.add_to_victory_display and self.IsInPlay():
            self.CastTo(HasVictory).MoveToVictoryDisplay()
        super().OnBeDefeated(would_defeated_message, as_asset=as_asset, ignore_when_defeated=ignore_when_defeated)
        if self.IsInPlay():
            Faces.DiscardAll([self], by_effect)
        after_defeated_message = Message.AfterSchemeBeDefeated(self, by_effect, defeated_message)
        after_defeated_message.Send()
        if not killer:
            killer = by_effect.this
        exact_defeat = bool(being_message and being_message.exact_defeat)
        unit_defeated_message = Message.AfterUnitDefeatedScheme(
            killer,
            self,
            by_effect,
            exact_defeat=exact_defeat,
        )
        unit_defeated_message.Send()

    @override
    def OnWhenCardRevealed(self, revealed_message: 'Message.WhenCardRevealed') -> None:
        player = revealed_message.GetToPlayer()
        if self.PutIntoPlay(player, revealed_message.by_effect):
            return super().OnWhenCardRevealed(revealed_message)

    # @override
    # def GetInfoDict(self) -> Dict[str, int]:
    #     # return {
    #     #     "threat": self.threat,
    #     # } |
    #     return super().GetInfoDict()

    @override
    def OnWouldDefeated(self, killer: 'CardFace|None', by_effect: 'Effect', being_message: 'Message.WhenSchemeBeingThwart|Message.WhenUnitBeingAttack|None') -> 'Message.WhenSchemeWouldBeDefeated|Message.WhenUnitWouldBeDefeated|None':
        assert isinstance(being_message, Message.WhenSchemeBeingThwart|None)
        would_defeated_message = Message.WhenSchemeWouldBeDefeated(self, by_effect, killer, being_message)
        would_defeated_message.Send()
        return would_defeated_message

    ################################################################################
    #
    @override
    def PlaceTokensInternal(self, value: INT_TYPE, name: 'CardFace.TOKEN', by_effect: 'Effect') -> int | None:
        if name == 'threat':
            message = self.PlaceThreatInternal(value, by_effect)
            if message:
                return message.value
            else:
                return None
        else:
            return super().PlaceTokensInternal(value, name, by_effect)

    def PlaceThreatInternal(self, value: INT_TYPE, by_effect: 'Effect', sch_message: 'Message.WhenUnitWouldScheme|None'=None) -> 'Message.AfterSchemePlaceThreat|None':
        from game.message import Message
        from game.card.face.card_type import MainScheme
        from game.operate.worlds import Worlds

        event_manager = self.card.world.event_manager
        timing_occurrence = (
            event_manager.BeginTimingOccurrence()
            if not MainScheme.IsType(self) and
            (not event_manager.timing_occurrences or
             event_manager.broadcasting_messages)
            else None
        )
        value = Worlds.ConvertPerPlayerIconToInt(value, by_effect)
        message = Message.WhenSchemeWouldPlaceThreat(self, value, by_effect, sch_message)
        message.Send()
        if not message.is_be_instead and message.value > 0:
            super().PlaceTokensInternal(message.value, 'threat', by_effect)
            after_message = Message.AfterSchemePlaceThreat(self, message.value, by_effect, message)
            after_message.Send()
            event_manager.EndTimingOccurrence(timing_occurrence)
            return after_message
        event_manager.EndTimingOccurrence(timing_occurrence)
        return None

    @override
    def RemoveTokensInternal(self, value: Literal["All"]|INT_TYPE, name: 'CardFace.TOKEN', by_effect: 'Effect', forced: bool|None = None) -> 'int|None':
        if name == 'threat':
            return self.RemoveThreatInternal(by_effect.this, value, by_effect)
        else:
            return super().RemoveTokensInternal(value, name, by_effect, forced)

    def RemoveThreatInternal(self, by_face: 'CardFace', value: Literal["All"]|INT_TYPE, by_effect: 'Effect', thw_message: 'Message.WhenSchemeBeingThwart|None'=None) -> int:
        from game.message import Message
        from game.card.face.card_type import MainScheme
        from game.operate.worlds import Worlds

        event_manager = self.card.world.event_manager
        timing_occurrence = (
            event_manager.BeginTimingOccurrence()
            if not MainScheme.IsType(self) and
            (not event_manager.timing_occurrences or
             event_manager.broadcasting_messages)
            else None
        )
        if self.threat > 0:
            if value == "All":
                value = self.threat
            else:
                value = Worlds.ConvertPerPlayerIconToInt(value, by_effect)
            remove_message = Message.WhenSchemeWouldRemoveThreat(self, by_face, value, by_effect, thw_message)
            remove_message.Send()
            if remove_message.value and not remove_message.is_be_instead and not remove_message.cannot_be_removed:
                threat = min(self.threat, remove_message.value)
                if thw_message:
                    thw_message.exact_defeat = threat == remove_message.value
                super().RemoveTokensInternal(threat, 'threat', by_effect, forced=True)
                message = Message.AfterSchemeRemoveThreat(self, threat, by_effect, remove_message)
                message.Send()

                if self.threat == 0 and \
                    not MainScheme.IsType(self) and \
                    not self.card.area.flags.is_victory_display:
                    self.Defeated(by_face, by_effect, thw_message)
                event_manager.EndTimingOccurrence(timing_occurrence)
                return threat
        event_manager.EndTimingOccurrence(timing_occurrence)
        return 0

    def MoveThreat(self, value: Literal["All"]|int, by_effect: 'Effect', target: List['Scheme2']|List['CardFace']) -> int:
        value = self.RemoveThreatInternal(self, value, by_effect)
        self.PlaceThreatOnSchemes(target, value, by_effect)
        return value

    @property
    def threat(self) -> int:
        return self.GetTokens('threat')

    def CanBeThwartBy(self, effect: 'Effect') -> bool:
        if self.threat == 0:
            return False
        check_message = Message.CheckIfSchemeCanBeThwartBy(self, effect)
        check_message.Send()
        return check_message.can_be_thwart

    def FindCorrespondingVillain(self) -> 'Villain|None':
        from game.card.face.base import Villain
        from game.operate.worlds import Worlds
        faces = Worlds.GetOnFieldCards(self.card.game_area)
        villains = CardFinder(name=self.corresponding_villain_name).Checks2(faces, Villain)
        if villains:
            return villains[0]
        else:
            return None
