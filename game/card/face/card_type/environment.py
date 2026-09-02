from core import *
from game.card.face import *
from game.ability import *
from game.message import *
from game.player import *
from cards.paper import Paper

@final
class Environment(HasAccelerationIcon, HasAmplify, CanCrisis, HasHazard, HasUses, CanPlaceCounter, HasPermanent, HasSetup, EncounterNonVillainCard, FinalType):
    @override
    def __init__(self, paper: 'Paper') -> None:
        super().__init__(paper)

    @override
    def OnPutIntoPlay(self, message: 'Message.WhenCardPutIntoPlay') -> 'bool':
        # When a player reveals a Spell environment, they place that card in front of them in their play area. 
        from game.operate.faces import Faces
        if self.HasTrait("SPELL"):
            area_environment = message.GetToPlayer().area_environment
        else:
            area_environment = self.card.world.area_environment
        if Faces.MoveAllTo([self], area_environment, message.by_effect):
            return super().OnPutIntoPlay(message)
        else:
            return False

    @override
    def OnWhenCardRevealed(self, revealed_message: 'Message.WhenCardRevealed') -> None:
        player = revealed_message.GetToPlayer()
        # Fix "21100a" flip
        if revealed_message.is_by_flipping or \
            self.PutIntoPlay(player, revealed_message.by_effect):
            return super().OnWhenCardRevealed(revealed_message)

    @property
    def bind_face(self) -> 'CardFace|None':
        player = self.card.area.play_area
        if player:
            return player.GetIdentity()
        return None

