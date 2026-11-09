from typing import Final
from core import *
from game.card.face import *
from game.effect import *
from game.player import *
from game.message import *
from game.world import *

# game step, game function, or card ability
class GameRule(Effect):
    def __init__(self, face: 'CardFace', bind_message: 'Message2|None'=None, *, display_name: str="", initiator: 'User|None'=None) -> None:
        from game.effect.effect_context import EffectContext

        self.this: 'CardFace' = face

        self.context = EffectContext(self)
        if initiator == None:
            initiator = face.GetControlByOrOwner()
        self.context.initiator = initiator

        self.display_name = display_name
        self.context.bind_message = bind_message
        self.world = face.card.world

    @property
    @override
    def is_rule(self) -> bool:
        return True

    def __repr__(self) -> str:
        return "Game Rule"

    @override
    def GetDisplayName(self, *, remove_space: bool=False) -> str:
        if self.display_name:
            return self.display_name
        else:
            return str(self)

class Ties(GameRule):
    def __init__(self, name: str="Ties", *, world: 'World') -> None:
        first_player = world.GetFirstPlayer()
        face = first_player.GetIdentity()
        super().__init__(face, display_name=name)

    def __repr__(self) -> str:
        return "Ties"

class MainSchemePhasePlaceThreat(GameRule):
    def __repr__(self) -> str:
        return "Main Scheme Phase Place Threat"

class UniqueEncounterCardRevealed(GameRule):
    def __repr__(self) -> str:
        return "Unique Encounter Card Revealed"

class Activate(GameRule):
    def __repr__(self) -> str:
        return "Activate"

################################################################################
#
# class HasInitiator(GameRule):
#     def __init__(self, face: 'CardFace') -> None:
#         self.initiator = face.GetControlByOrOwner()
#         super().__init__(face)

class Retaliate(GameRule):
    def __repr__(self) -> str:
        return "Retaliate"

class Consequential(GameRule):
    def __repr__(self) -> str:
        return "Consequential"

class Quickstrike(GameRule):
    def __repr__(self) -> str:
        return "Quickstrike"

class Teamwork(GameRule):
    def __repr__(self) -> str:
        return "Teamwork"

class Modifier(GameRule):
    def __repr__(self) -> str:
        return "Modifier"

# class ThwartActive(GameRule):
#     def __init__(self, face: 'CardFace') -> None:
#         self.this: 'CardFace' = face
#         self.initiator = face.GetControlBy()

#     def __repr__(self) -> str:
#         return "Thwart"

class SchemeActive(GameRule):
    def __init__(self, face: 'CardFace') -> None:
        super().__init__(face)
        self.this: 'CardFace' = face
        self.context.initiator = face.GetControlByOrOwner()
        self.world: Final = face.card.world

    def __repr__(self) -> str:
        return "Scheme"

# class PuzzleRule(GameRule):
#     def __init__(self, face: 'CardFace', *, display_name: str="") -> None:
#         self.initiator = face.GetOwner()
#         super().__init__(face, display_name=display_name)

#     def __repr__(self) -> str:
#         return "Puzzle Rule"

class DebugRule(GameRule):
    def __init__(self, face: 'CardFace', *, display_name: str="") -> None:
        super().__init__(face, display_name=display_name)
        self.context.initiator = face.GetOwner()

    def __repr__(self) -> str:
        return "Debug Rule"

class Incite(GameRule):
    def __repr__(self) -> str:
        return "Incite"

class Toughness(GameRule):
    def __repr__(self) -> str:
        return "Toughness"

# class DoScheme(GameRule):
#     def __repr__(self) -> str:
#         return ""

class ResetKeyword(GameRule):
    def __repr__(self) -> str:
        return "Reset"

class Surge(GameRule):
    def __repr__(self) -> str:
        return "Surge"

class Advance(GameRule):
    def __repr__(self) -> str:
        return "Advance"

class EndPhase(GameRule):
    def __init__(self, initiator: 'Player') -> None:
        face = initiator.world.insert
        super().__init__(face, initiator=initiator)

    def __repr__(self) -> str:
        return "End Phase"

