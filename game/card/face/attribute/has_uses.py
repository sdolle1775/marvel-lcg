from . import *

class HasUses(CanPlaceCounter, HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        self.uses_counters = 0
        self.uses_counter_name: 'CardFace.COUNTER'

        super().__init__(paper)

        def parse(value: str):
            from game.element.utility import IsCounter
            values = value.split(',')
            self.uses_counters = self.FormatPlayerNumValue(values[0])
            assert IsCounter(values[1])
            self.uses_counter_name = values[1]
        self.RegisterAttribute("Uses", parse)

    @override
    def OnWhenCardEnterPlay(self, message: 'Message.WhenCardEnterPlay') -> bool:
        if super().OnWhenCardEnterPlay(message):
            # Setup can select the other mode face during this actual entry
            # (Public Outcry). Initialize that face once; later flips do not
            # enter play and must not refill its counters.
            face = self.card.face
            if HasUses.IsType(face) and face.uses_counters:
                face.components.counter.PlaceCounters(face.uses_counters, face.uses_counter_name)
            return True
        return False

    ################################################################################
    #
    @override
    def ConvertAllPurpose(self) -> 'CardFace.COUNTER':
        if self.uses_counters != 0:
            return self.uses_counter_name
        else:
            return super().ConvertAllPurpose()

    ################################################################################
    # Counter
    # @override
    # def PlaceCountersInternal(self, num: int, name: 'CardFace.COUNTER|Literal["all-purpose"]', by_effect: 'Effect', *, maximum: int|None=None) -> int:
    #     return super().PlaceCountersInternal(num, name, by_effect, maximum=maximum)

    @override
    def RemoveCountersInternal(self, counters: Literal["All"]|int, name: 'CardFace.COUNTER|Literal["all-purpose"]', by_effect: 'Effect', *, forced: bool|None=None) -> 'Message.AfterCardRemovedCounter|None':
        from game.operate.faces import Faces
        from game.effect.rule import GameRule

        after_message = super().RemoveCountersInternal(counters, name, by_effect, forced=forced)
        if after_message and self.IsInPlay():
            if self.GetAllCounters() <= 0 and self.uses_counters != 0:
                effect = GameRule(self)
                # Hack
                if isinstance(self, HasVictory) and self.victory: # "51031"
                    Faces.AddToVictoryDisplay([self], effect)
                else:
                    Faces.DiscardAll([self], effect)
                # self.Defeated(None, effect), we cannot use this in current version
        return after_message

    ################################################################################
    #
    @override
    def GetInfoDict(self) -> Dict[str, int]:
        the_dict: Dict[str, int] = {}
        for key in self.components.counter.GetCounterNames():
            if self.uses_counters > 0 and self.uses_counter_name == key:
                key_name = 'c_' + key
                the_dict |= {key_name + '_printed': self.uses_counters}
        return the_dict | super().GetInfoDict()

