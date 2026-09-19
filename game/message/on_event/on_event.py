from typing import Final, TypeAlias
from core import *
from game.card.face import *
from game.card.card_finder import *
from game.message import *
from game.ability import *
from game.deck.deck_type import DeckType

from game.ability.condition import Condition

CardTypeMin = Condition.CARD_TYPE_MIN
CardType = Condition.CARD_TYPE

TM2 = TypeVar("TM2", bound='TriggerMessage', covariant=True)

class OnEvent:

    class Base(metaclass=ClassNameMeta):

        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType['Message2'],
                            operation: OperationType['Message2']) -> List['Ability']:
            if self != OnEvent.NONE:
                assert False
            return []

        @final
        def GenerateAbilities2(self,
                            ability_type: AbilityType,
                            condition: ConditionType['Message2'],
                            operation: OperationType['Message2']) -> List['Ability']:
            abilities = self.GenerateAbilities(
                ability_type,
                condition,
                operation
            )
            for ability in abilities:
                ability.on_event = self
            return abilities

        def __repr__(self) -> str:
            return str(self.__class__)

    # Trigger when game area change
    class GameArea(Base):           pass

    # Trigger when enter/leave play
    class EnterPlayWhen(Base):
        def __init__(self,
                    which_card: CardType,) -> None:
            self.which_card = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            return [
                Ability(
                    ability_type,
                    Message.WhenCardEnterPlay|Message.WhenCardFaceActivated,
                    [
                        lambda effect, message:
                            Condition.CheckWhichCard(self.which_card, message.trigger, effect),
                        condition
                    ],
                    operation
                ),
            ]

    class EnterPlayAfter(Base):
        def __init__(self,
                    which_card: CardType,) -> None:
            self.which_card = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            return [
                Ability(
                    ability_type,
                    Message.AfterCardEnterPlay|Message.AfterCardFaceActivated,
                    [
                        lambda effect, message:
                            Condition.CheckWhichCard(self.which_card, message.trigger, effect),
                        condition
                    ],
                    operation
                ),
            ]

    class LeavePlayWhen(Base):      pass

    class LeavePlayAfter(Base):
        def __init__(self,
                    which_card: CardType,) -> None:
            self.which_card = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            return [
                Ability(
                    ability_type,
                    Message.AfterCardLeavePlay,
                    [
                        lambda effect, message:
                            Condition.CheckWhichCard(self.which_card, message.trigger, effect),
                        condition
                    ],
                    operation
                ),
            ]

    # Triggers when enter/leave play, card move, and also game area change
    class CardInPlay(GameArea):
        def __init__(self,
                    which_card: CardType,) -> None:
            self.which_card = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            def check_cards(effect: 'Effect', message: 'Message.GameAreaAddCard') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            def check_card_in_play(effect: 'Effect', message: 'Message.WhenCardLeavePlay|Message.WhenCardEnterPlay') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            def check_card_move(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                face = message.IsIncludeFace(self.which_card, effect)
                if not face:
                    return False
                from_area = message.face_areas[face]
                into_area = face.card.area
                return from_area.flags.is_in_play and not into_area.flags.is_in_play or \
                        not from_area.flags.is_in_play and into_area.flags.is_in_play

            return [
                Ability(
                    ability_type,
                    Message.AfterCardsMoved,
                    [
                        check_card_move,
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.WhenCardLeavePlay|Message.WhenCardEnterPlay|Message.WhenCardFaceActivated,
                    [
                        check_card_in_play,
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.GameAreaAddCard,
                    [
                        check_cards,
                        condition
                    ],
                    operation
                ),
            ]

    EngagedPlayer = CardInPlay

    # in play card move, also triggers when enter/leave play
    class PlayAreaCard(GameArea):
        def __init__(self, which_card: Literal["YouControlCards", "This"]|CardType) -> None:
            self.which_card: Final = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            from game.selector import Select

            def check_cards_move(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                found_face = None
                if self.which_card == "YouControlCards":
                    player = Select.GetYouSafe(effect)
                    for face in message.faces:
                        if message.face_areas[face].GetOwner() == player or \
                            face.card.area.GetOwner() == player: # Fix "29037"
                            found_face = face
                            break
                else:
                    found_face = message.IsIncludeFace(self.which_card, effect)

                if not found_face:
                    return False

                from_area = message.face_areas[found_face]
                into_area = found_face.card.area

                if from_area.flags.is_in_play and not into_area.flags.is_in_play or \
                    not from_area.flags.is_in_play and into_area.flags.is_in_play:
                    return True
                elif from_area.play_area != into_area.play_area or \
                    from_area.bind_owner != into_area.bind_owner:
                    if from_area.flags.is_in_play or into_area.flags.is_in_play:
                        return True
                return False

            def check_cards(effect: 'Effect', message: 'Message.GameAreaAddCard') -> bool:
                trigger = message.trigger
                if self.which_card == "YouControlCards":
                    return Select.GetYouSafe(effect) == trigger.GetControlBy()
                else:
                    return Condition.CheckWhichCard(self.which_card, trigger, effect)

            return [
                Ability(
                    ability_type,
                    Message.AfterCardsMoved,
                    [
                        check_cards_move,
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.GameAreaAddCard,
                    [
                        check_cards,
                        condition
                    ],
                    operation
                ),
            ]

    class CardType(CardInPlay):
        def __init__(self,
                    which_card: CardType,) -> None:
            self.which_card = which_card

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability
            def check_cards(effect: 'Effect', message: 'Message.GameAreaAddCard') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            def check_card_in_play(effect: 'Effect', message: 'Message.WhenCardLeavePlay|Message.WhenCardEnterPlay') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            def check_card_move(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                face = message.IsIncludeFace(self.which_card, effect)
                if not face:
                    return False
                return True

            return [
                Ability(
                    ability_type,
                    Message.AfterCardsMoved,
                    [
                        check_card_move,
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.WhenCardLeavePlay|Message.WhenCardEnterPlay|Message.WhenCardFaceActivated,
                    [
                        check_card_in_play,
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.GameAreaAddCard,
                    [
                        check_cards,
                        condition
                    ],
                    operation
                ),
            ]

    NONE = Base()

    # Internal use
    class AssetEffect(Base):

        def __init__(self) -> None:
            pass

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message2],
                            operation: OperationType[Message2]) -> List['Ability']:
            from game.ability import Ability

            return [
                Ability(
                    ability_type,
                    Message.AfterCardGainUpgradeAbility,
                    [
                        lambda effect, message:
                            effect.this == message.upgrade and \
                            Condition.CheckWhichCard("AttachedCard", message.trigger, effect),
                        condition
                    ],
                    operation
                ),
                Ability(
                    ability_type,
                    Message.AfterCardLostUpgradeAbility,
                    [
                        lambda effect, message:
                            effect.this == message.upgrade and \
                            Condition.CheckWhichCard("AttachedCard", message.trigger, effect),
                        condition
                    ],
                    operation
                ),
            ]

    ################################################################################
    # Different card area
    class TemplateCardArea(Base):

        def __init__(self,
                    deck_type: 'DeckType',
                    condition: ConditionType[Message.AfterCardsMoved]) -> None:
            self.deck_type: Final = deck_type
            self.condition: Final = condition

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[Message.AfterCardsMoved|Message.AfterDeckShuffle],
                            operation: OperationType[Message.AfterCardsMoved|Message.AfterDeckShuffle]) -> List['Ability']:
            from game.ability import Ability

            def check_which_area(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                return message.IsDeckTypeRelated(self.deck_type)

            def check_which_area2(effect: 'Effect', message: 'Message.AfterDeckShuffle') -> bool:
                return message.deck.deck_type == self.deck_type

            return [Ability(
                ability_type,
                Message.AfterCardsMoved,
                [
                    check_which_area,
                    self.condition,
                    condition,
                ],
                operation,
            ),
            Ability(
                ability_type,
                Message.AfterDeckShuffle,
                [
                    check_which_area2,
                    condition,
                ],
                operation,
            )]

    class Victory(TemplateCardArea):

        def __init__(self, which_card: CardType) -> None:

            def check_which_card(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                for face in message.faces:
                    if Condition.CheckWhichCard(which_card, face, effect):
                        return True
                return False

            super().__init__(DeckType.VictoryDisplay, check_which_card)

    # Triggers when player hand card update
    class HandCards(TemplateCardArea):

        def __init__(self, which_player: Literal["EngagedPlayer"]) -> None:

            def check(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                from game.selector import Select
                return Select.GetYou(effect).hand_cards in message.related_decks

            super().__init__(DeckType.HandsArea, check)

    # Trigger when call `TuckCardUnderHere`
    class TuckUnder(TemplateCardArea):

        def __init__(self, under_where: Literal["Here", "Identity"]) -> None:

            def check_under_here(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                if under_where == "Here":
                    area = effect.this.GetPlacedCardArea()
                    return area in message.related_decks
                else:
                    return True # Hack

            super().__init__(DeckType.PlaceCardArea, check_under_here)

    class PlacedCard(TuckUnder): pass

    class DealtEncounterCard(TemplateCardArea):

        def __init__(self, dealt_to_who: Literal["You"]) -> None:

            def check_under_here(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                area = effect.this.GetControlByPlayer().dealt_encounter_cards
                return area in message.related_decks

            super().__init__(DeckType.DealtEncounterCardsDeck, check_under_here)

    # Trigger when card moves from/into deck
    class DeckTopCard(TemplateCardArea):
        def __init__(self, from_where: Literal["YourDeck"]) -> None:
            from game.selector import Select

            def check(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
                player_deck = Select.GetYou(effect).player_deck
                return player_deck in message.related_decks

            super().__init__(DeckType.PlayerDeck, check)

    ################################################################################
    #
    class TemplateTriggerInPlay(GameArea):
        def __init__(self,
                    when: Type['TriggerMessage']|Any,
                    which_card: CardType,
                    *conditions: ConditionType[TM2]) -> None:
            self.which_card: Final = which_card
            self.when: Type[TriggerMessage] = when
            self.conditions: Final = conditions

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[TriggerMessage],
                            operation: OperationType[TriggerMessage]) -> List['Ability']:
            from game.ability import Ability

            def check_game_area(effect: 'Effect', message: 'Message.GameAreaAddCard|Message.AfterCardLeavePlay|Message.AfterCardEnterPlay') -> bool:
                if self.which_card == None:
                    return True
                if Condition.CheckWhichCard(self.which_card, message.trigger, effect):
                    return True
                if Condition.CheckWhichCard("This", message.trigger, effect):
                    return True
                return False

            return [Ability(
                ability_type,
                self.when,
                [
                    *self.conditions,
                    condition,
                ],
                operation,
            ),
            Ability(
                ability_type,
                Message.GameAreaAddCard,
                [
                    check_game_area,
                    condition,
                ],
                operation,
            ),
            Ability(
                ability_type,
                Message.AfterCardLeavePlay|Message.AfterCardEnterPlay|Message.AfterCardFaceActivated,
                [
                    check_game_area,
                    condition,
                ],
                operation,
            ),
        ]

    # There is not a feature that place a acceleration token before a card enters play, so we use `Base` instead of `EnterLeavePlay`7
    class AccelerationToken(TemplateTriggerInPlay):
        MESSAGE_TYPE = Message.AfterCardPlacedToken|Message.AfterCardRemovedToken

        def __init__(self, which_card: CardType) -> None:

            def check_token_name(effect: 'Effect', message: 'OnEvent.AccelerationToken.MESSAGE_TYPE') -> bool:
                return message.token_name == 'acceleration_token'

            def check_which_card(effect: 'Effect', message: 'OnEvent.AccelerationToken.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(which_card, message.trigger, effect)

            super().__init__(
                OnEvent.AccelerationToken.MESSAGE_TYPE,
                which_card,
                check_token_name,
                check_which_card
            )

    # [ATK, THW, SCH]
    class CardKeyword(TemplateTriggerInPlay):

        MESSAGE_TYPE = Message.WhenCardKeywordUpdated

        def __init__(self, which_card: CardType) -> None:

            def check_keywords(effect: 'Effect', message: 'OnEvent.CardKeyword.MESSAGE_TYPE') -> bool:
                return message.keyword in ["ATK","THW", "SCH"]

            def check_which_card(effect: 'Effect', message: 'OnEvent.CardKeyword.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(which_card, message.trigger, effect)

            super().__init__(
                OnEvent.CardKeyword.MESSAGE_TYPE,
                which_card,
                check_keywords,
                check_which_card
            )

    # ["Hazard", "Crisis", "Acceleration", "Amplify"]
    class Icons(TemplateTriggerInPlay):

        MESSAGE_TYPE = Message.WhenCardKeywordUpdated

        def __init__(self, where: Literal["InPlay"]) -> None:

            def check_icon(effect: 'Effect', message: 'OnEvent.Icons.MESSAGE_TYPE') -> bool:
                return message.keyword in ["Hazard", "Crisis", "Acceleration", "Amplify"]

            def check_which_area(effect: 'Effect', message: 'OnEvent.Icons.MESSAGE_TYPE') -> bool:
                return message.trigger.IsInPlay()

            super().__init__(
                OnEvent.Icons.MESSAGE_TYPE,
                None,
                check_icon,
                check_which_area
            )

    ################################################################################
    #
    class TemplateTrigger(Base):
        def __init__(self,
                    # trigger: CardType,
                    when: Type['TriggerMessage']|Any,
                    *conditions: ConditionType[TM2]) -> None:
            # self.trigger: Final = trigger
            self.when: Type[TriggerMessage] = when
            self.conditions: Final = conditions

        @override
        def GenerateAbilities(self,
                            ability_type: AbilityType,
                            condition: ConditionType[TriggerMessage],
                            operation: OperationType[TriggerMessage]) -> List['Ability']:
            from game.ability import Ability

            # def check_which_card(effect: 'Effect', message: 'TriggerMessage') -> bool:
            #     return Condition.CheckWhichCard(self.trigger, message.trigger, effect)

            return [Ability(
                ability_type,
                self.when,
                [
                    # check_which_card,
                    *self.conditions,
                    condition,
                ],
                operation,
            )]


    class MainSchemeStage(TemplateTrigger):

        def __init__(self, scheme: CardType) -> None:
            MESSAGE_TYPE = Message.AfterMainSchemeAdvanced

            def check_which_card(effect: 'Effect', message: 'MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(scheme, message.scheme, effect)

            super().__init__(
                MESSAGE_TYPE,
                check_which_card
            )

    class Reveal(TemplateTrigger):

        def __init__(self, face: CardType) -> None:
            MESSAGE_TYPE = Message.WhenPlayerRevealCard

            def check_which_card(effect: 'Effect', message: 'MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(face, message.trigger, effect)

            super().__init__(
                MESSAGE_TYPE,
                check_which_card
            )

    # Trigger when any in play unit health change
    class Health(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterUnitHealHealth|Message.AfterUnitLossHealth|Message.AfterUnitHitPointReset|Message.AfterUnitHitPointSet

        def __init__(self, which_card: CardType) -> None:
            self.which_card = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.Health.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.Health.MESSAGE_TYPE,
                check_which_card
            )

    class Counter(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterCardPlacedCounter|Message.AfterCardRemovedCounter

        def __init__(self, which_card: CardType, counter_name: 'CardFace.COUNTER|None') -> None:
            self.which_card: Final = which_card
            self.counter_name: Final = counter_name

            def check_which_card(effect: 'Effect', message: 'OnEvent.Counter.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.Counter.MESSAGE_TYPE,
                check_which_card
            )

    class Trait(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterCardGainTrait|Message.AfterCardLoseTrait|Message.AfterCardLeavePlay|Message.AfterCardEnterPlay|Message.AfterCardFaceActivated

        def __init__(self, which_card: CardType|Literal["YouControlCharacter"]) -> None:
            from game.selector import Select
            self.which_card: Final = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.Trait.MESSAGE_TYPE') -> bool:
                if self.which_card == "YouControlCharacter":
                    trigger = message.trigger
                    return Select.GetYou(effect) == trigger.GetControlBy()
                else:
                    return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.Trait.MESSAGE_TYPE,
                check_which_card
            )

    class Threat(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterSchemePlaceThreat|Message.AfterSchemeRemoveThreat|Message.AfterCardLeavePlay|Message.AfterCardEnterPlay|Message.AfterCardFaceActivated

        def __init__(self, which_card: CardType) -> None:
            self.which_card: Final = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.Threat.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.Threat.MESSAGE_TYPE,
                check_which_card
            )

    # Trigger when gain/lost status
    class Status(TemplateTrigger):
        MESSAGE_TYPE: TypeAlias = Message.AfterStatusCardPlaceOn|Message.AfterStatusDiscardFrom

        def __init__(self, which_card: CardType, which_status: Literal['Tough','Stunned','Confused']) -> None:
            self.which_card: Final = which_card
            self.which_status: Final = which_status


            def check_which_card(effect: 'Effect', message: 'OnEvent.Status.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            def check_which_status(effect: 'Effect', message: 'OnEvent.Status.MESSAGE_TYPE') -> bool:
                return self.which_status == message.status.name

            super().__init__(
                OnEvent.Status.MESSAGE_TYPE,
                check_which_card,
                check_which_status
            )

    # Trigger when a card flip to face up (whatever is in deck or in play)
    class Faceup(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterCardFlip

        def __init__(self, which_card: CardType) -> None:
            self.which_card = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.Faceup.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.Faceup.MESSAGE_TYPE,
                check_which_card
            )

    # Change "form", not hero/identity form
    class Form(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterUnitChangeForm|Message.AfterCardLeavePlay|Message.AfterCardEnterPlay|Message.AfterCardFaceActivated

        def __init__(self, which_card: CardType) -> None:
            from game.card.face.card_type import Upgrade
            self.which_card = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.Form.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect) or \
                    isinstance(message.trigger, Upgrade) and message.trigger.form != None

            super().__init__(
                OnEvent.Form.MESSAGE_TYPE,
                check_which_card
            )

    # Trigger when call `AttachTo2`
    class AttachedMove(TemplateTrigger):
        MESSAGE_TYPE = Message.AfterCardAttachTo|Message.AfterCardDetachFrom

        def __init__(self, which_card: CardType) -> None:
            self.which_card = which_card

            def check_which_card(effect: 'Effect', message: 'OnEvent.AttachedMove.MESSAGE_TYPE') -> bool:
                return Condition.CheckWhichCard(self.which_card, message.trigger, effect)

            super().__init__(
                OnEvent.AttachedMove.MESSAGE_TYPE,
                check_which_card
            )

