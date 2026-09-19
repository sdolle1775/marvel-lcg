from . import *
from typing import Final


def _get_activation_target_player(being_message: 'Message.WhenUnitBeingAttack|Message.WhenSchemeBeingScheme') -> 'Player':
    defender = getattr(being_message, "defender", None)
    if defender:
        return defender.GetControlByPlayer()
    player = being_message.would_message.property.against_player
    assert player
    return player


class SenderCard:

    class DiscardedCardFound_Text(TextMessage):
        def __init__(self, face: 'CardFace') -> None:
            super().__init__(world=face.card.world)
            # The final discarded card may already be back in a shuffled deck.
            # Keep its printed identity available without exposing its position.
            text = TransText(
                "Discarded card found: {face}",
                face=face.GetDisplayName(no_hidden=True, no_object_id=True),
            )
            self.Present(text, "")

    class LookAt_Text(TextMessage):
        def __init__(self, player: 'Player', faces: Sequence['CardFace']) -> None:
            for face in faces:
                face.card.visible.Set(player)

            # super().__init__(trigger=player.GetIdentity())
            super().__init__(world=player.world)

            text = TransText("{player} looks at {faces}", player=player, faces=faces)
            self.Present(text, "", *faces)

            # for face in faces:
            #     if face.IsInDeck():
            #         face.card.SetVisible("Auto")

    # class EndLookAt_Text(TriggerFaceMessage):
    #     def __init__(self) -> None:
    #         self.Present(None, "")

    ################################################################################
    # Card
    ################################################################################
    # class WhenCardBeCreated(TriggerFaceMessage):
    #     def __init__(self, face: 'CardFace') -> None:
    #         super().__init__(trigger=face)

    class WhenCardResetKeyword(TriggerFaceMessage):
        def __init__(self, face: 'CardFace') -> None:
            super().__init__(trigger=face)

    class WhenCardDefeating_Text(TextMessage):
        def __init__(self, this: 'CardFace') -> None:
            super().__init__(world=this.card.world)
            text = TransText("{this} is being defeated", this=this)
            self.Present(text, "destroyed", this)

    class WhenCardWouldUpdateKeyword_Text(TextMessage):
        def __init__(self, face: 'CardFace', diff: int, keyword: "CardFace.KEY", by_effect: 'Effect', *, render_ui: bool=False) -> 'None':
            super().__init__(world=by_effect.world)
            assert keyword != "HP"
            if face.IsFaceUp() and diff != 0:
                from game.effect.rule import ResetKeyword
                if not self.world.is_game_started:
                    pass
                elif type(by_effect) == ResetKeyword:
                    pass
                else:
                    if render_ui:
                        text = TransText("{face} would {diff:+} {keyword}", face=face, diff=diff, keyword=keyword)
                        self.Present(text, "", face, by_effect.this)
                    pass

    class WhenCardKeywordUpdated(CardStateUpdatedMessage):
        def __init__(self, face: 'CardFace', diff: int, keyword: "CardFace.KEY", by_effect: 'Effect') -> 'None':
            # from game.message import OnEvent
            assert keyword != "HP"
            self.keyword: Final = keyword
            super().__init__(trigger=face)
            # if keyword in ["Hazard", "Crisis", "Acceleration", "Amplify"]:
            #     self.TriggerOnEvent(OnEvent.Icons)
            # if keyword in ["ATK","THW", "SCH"]:
            #     self.TriggerOnEvent(OnEvent.CardKeyword)

    class WhenCardWouldGainBoostIcons_Text(TextMessage):
        def __init__(self, face: 'CardFace', value: int, effect: 'Effect') -> None:
            super().__init__(world=effect.world)
            self.Present(None, "", effect.this, face)

    class WhenCardGainBoostIcons_Text(TextMessage):
        def __init__(self, face: 'CardFace', value: int, effect: 'Effect') -> None:
            super().__init__(world=effect.world)
            sound = "activate" if value > 0 else ""
            text = TransText("{face} gains {value} boost icons", face=face, value=value)
            self.Present(text, sound, effect.this, face)

    # TODO: Pre message
    class WhenCardBeSpendAsResource(TriggerFaceMessage, TriggerPlayerMessage):
        def __init__(self, face: 'CardFace', res: 'Resources', for_effect: 'Effect', player: 'Player') -> None:
            self.for_effect: Final = for_effect
            if self.for_effect.ability.is_play:
                pay_for_card = self.for_effect.this
            else:
                pay_for_card = None
            self.pay_for_card: Final = pay_for_card
            self.res = res
            super().__init__(player=player, trigger=face)
            text = TransText("{player} gains resource {resource} from {by_effect}, total {total_res}", by_effect=face, player=player, resource=res, total_res=player.res_pool.Get())
            self.Present(text, "token", face)

    class AfterCardsBeSpendAsResource(TriggerPlayerMessage):
        def __init__(self, faces: List['CardFace'], for_effect: 'Effect', player: 'Player') -> None:
            self.for_effect: Final = for_effect
            if self.for_effect.ability.is_play:
                pay_for_card = self.for_effect.this
            else:
                pay_for_card = None
            self.pay_for_card: Final = pay_for_card
            self.faces = faces
            super().__init__(player=player)
            self.AddRelatedFace(*faces, for_effect)

    # class BeforeCardFlip(TriggerFaceMessage):
    #     def __init__(self, face: 'CardFace', by_effect: 'Effect', ui_group: bool) -> None:
    #         self.by_effect = by_effect
    #         super().__init__(trigger=face)
    class WhenCardWouldFlip(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, face: 'CardFace', to_face: 'CardFace|None', by_effect: 'Effect', ui_group: bool, ui_look_at: bool, by_swapping: bool) -> None:
            from game.message import Message
            self.to_face: Final = to_face
            self.ui_group: Final = ui_group
            self.ui_look_at: Final = ui_look_at
            self.by_swapping: Final = by_swapping
            super().__init__(trigger=face, end_event=Message.WhenCardFlip)

    class WhenCardFlip(TriggerFaceMessage, HasPreEventMessage, HasEndEventMessage):
        # Will remove all attched effects
        def __init__(self, face: 'CardFace', by_effect: 'Effect', message: 'Message.WhenCardWouldFlip') -> None:
            # from game.message import OnEvent
            from game.message import Message
            self.by_effect: Final = by_effect
            self.to_face: Final = message.to_face
            self.ui_group: Final = message.ui_group
            self.ui_look_at: Final = message.ui_look_at
            self.by_swapping: Final = message.by_swapping
            super().__init__(trigger=face, pre_message=message, end_event=Message.AfterCardFlip)
            self.AddRelatedFace(face, *face.card.back_faces, by_effect)
            # self.TriggerOnEvent(OnEvent.AssetEffect) # Fix identity flip

    class AfterCardFlip(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, from_face: 'CardFace', to_face: 'CardFace', when_flip_message: 'Message.WhenCardFlip') -> None:
            from game.message import OnEvent
            self.from_face: Final = from_face
            self.to_face: Final = to_face
            self.by_effect: Final = when_flip_message.by_effect
            area = to_face.card.area
            super().__init__(trigger=to_face, pre_message=when_flip_message)
            if not when_flip_message.ui_group:
                if area.flags.is_processing or area.flags.is_deck or area.flags.is_in_play or area.flags.is_boost_area:
                    if to_face.IsFaceUp() and \
                        (
                            to_face.IsInPlay() or \
                            to_face.card.area.flags.is_boost_area or \
                            when_flip_message.ui_look_at
                        ):
                        text = TransText("{to_face} was flipped ({effect})", to_face=to_face, effect=self.by_effect.this)
                        self.Present(text, "flip", to_face, self.by_effect.this)
            # Will call AfterCardEnterPlay
            if to_face.IsFaceUp():
                self.TriggerOnEvent(OnEvent.Faceup)

        @property
        def when_flip_message(self) -> 'Message.WhenCardFlip':
            return self.pre_message

    ################################################################################
    #
    # When card flip, it will only gain the abilities, not the upgrade card
    # TODO: Pre message
    class AfterCardGainUpgradeAbility(TriggerFaceMessage):
        def __init__(self, this: 'CardFace', upgrade: 'CanAttach') -> None:
            # from game.message import OnEvent
            self.upgrade: Final = upgrade
            super().__init__(trigger=this)
            # self.TriggerOnEvent(OnEvent.AssetEffect)

    # TODO: Pre message
    class AfterCardLostUpgradeAbility(TriggerFaceMessage):
        def __init__(self, this: 'CardFace', upgrade: 'CanAttach', by_flip: bool) -> None:
            # from game.message import OnEvent
            self.upgrade: Final = upgrade
            self.by_flip: Final = by_flip
            super().__init__(trigger=this)
            # self.TriggerOnEvent(OnEvent.AssetEffect)

    class WhenCardWouldAttachTo(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, this: 'CanAttach', to_face: 'CardFace', by_effect: 'Effect') -> None:
            from game.message import Message
            self.to_face: Final = to_face
            self.upgrade: Final = this
            self.by_effect: Final = by_effect
            super().__init__(trigger=this, end_event=Message.AfterCardAttachTo)

        def AttachToInstead(self, to_face: 'CardFace', by_effect: 'Effect'):
            self.SetBeInstead(by_effect)
            self.upgrade.AttachTo2(to_face, by_effect)

    class AfterCardAttachTo(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, this: 'CardFace', upgrade: 'CanAttach', message: 'Message.WhenCardWouldAttachTo') -> None:
            # from game.message import OnEvent
            self.upgrade: Final = upgrade
            self.to_face: Final = this
            super().__init__(trigger=upgrade, pre_message=message)
            text = TransText("{this} equipped {upgrade} ({effect})", this=this, upgrade=upgrade, effect=message.by_effect.this)
            self.Present(text, "equip", this)
            self.AddRelatedFace(this, upgrade)
            # self.TriggerOnEvent(OnEvent.AttachedMove)

    # TODO: Pre message
    class AfterCardDetachFrom(TriggerFaceMessage):
        def __init__(self, this: 'CardFace', upgrade: 'CanAttach') -> None:
            # from game.message import OnEvent
            self.upgrade: Final = upgrade
            self.from_face: Final = this
            super().__init__(trigger=upgrade)
            text = TransText("{this} unequipped {upgrade}", this=this, upgrade=upgrade)
            self.Present(text, "", this)
            # self.TriggerOnEvent(OnEvent.AttachedMove)

    # TODO: Pre message
    class AfterCardExhausted(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect', *, ui_group: bool=False) -> None:
            super().__init__(trigger=face)
            if not ui_group:
                text = TransText("{face} exhausted", face=face)
                self.Present(text, "flip", face, by_effect.this)

    class WhenCardWouldReady(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect', *, ui_group: bool) -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            # faces = [face]
            # if not ui_group:
            #     faces.append(by_effect.this)
            # text = TransText("{face} would ready")
            # self.Present(text, "", *faces)
            super().__init__(trigger=face, end_event=Message.AfterCardReady)

    class AfterCardReady(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect', message: 'Message.WhenCardWouldReady', ui_group: bool) -> None:
            self.by_effect = by_effect
            super().__init__(trigger=face, pre_message=message)
            if not ui_group:
                text = TransText("{face} readied", face=face)
                self.Present(text, "flip", face, by_effect.this)

    class WhenCardSetup(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', before_put_setup_cards: bool) -> None:
            self.before_put_setup_cards = before_put_setup_cards
            super().__init__(trigger=face)

    ################################################################################
    # Card Move
    # We don't extend `CanBeInstead` because when game is over, all `CanBeInstead` will be instead
    # Some cards may trigger the assert
    class WhenCardWouldMoveToArea(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', from_area: 'Deck', into_area: 'Deck', by_effect: 'Effect', ui_group: bool, index: int=-1) -> None:
            # from game.message import Message
            self.from_area: Final = from_area
            self.into_area = into_area
            self.index = index
            self.cannot = False
            self.by_effect = by_effect

            # super().__init__(trigger=face, end_event=Message.AfterCardMoved)
            super().__init__(trigger=face)

            if not ui_group:
                if into_area.flags.is_discards or into_area.flags.is_removed or into_area.flags.is_engaged or into_area.flags.is_upgrades or into_area.flags.is_processing or into_area.flags.is_in_play or into_area.flags.is_in_hand or into_area.flags.is_boost_area or into_area.flags.is_resources_area or into_area.flags.is_dealt_encounter or (into_area.flags.is_deck and from_area.flags.is_discards) or (from_area.flags.is_discards and into_area.flags.is_deck):
                # (into_area.IsDeck() and from_area.IsRemoved()):
                    pass
                else: # and World().phase != Phase.PlayerTurnEnd:
                    text = TransText("{face} is moving to {into_area}", face=face, into_area=into_area)
                    self.Present(text, "", face)

        def ChangeToArea(self, into_area: 'Deck|None', by_effect: 'Effect', *, index: int=-1):
            if into_area != None:
                self.into_area = into_area
                self.index = index
                text = TransText("{this} changes the area to {into_area}", this=by_effect.this, into_area=into_area)
            else:
                self.into_area = self.from_area
                text = TransText("{this} cancels this move", this=by_effect.this)
            self.Present_Activate(text, by_effect)

        def ChangeToBottomOfDeck(self, into_area: 'Deck', by_effect: 'Effect'):
            self.ChangeToArea(into_area, by_effect, index=0)

        def SetCannot(self, by_effect: 'Effect'):
            self.cannot = True
            text = TransText("{this} prevents {face} from moving", this=by_effect.this, face=self.trigger)
            self.Present_Activate(text, by_effect)

    class AfterCardControlChanged(TriggerFaceMessage):
        def __init__(
            self,
            face: 'CardFace',
            from_controller: 'Player|Scenario|None',
            to_controller: 'Player|Scenario|None',
            by_effect: 'Effect',
        ) -> None:
            self.from_controller: Final = from_controller
            self.to_controller: Final = to_controller
            self.by_effect: Final = by_effect
            super().__init__(trigger=face)
            self.AddRelatedFace(from_controller, to_controller, by_effect)

    class AfterCardEnterHand(TriggerFaceMessage, TriggerPlayerMessage):
        def __init__(self, face: 'CardFace', from_area: 'Deck', into_area: 'Deck', by_effect: 'Effect') -> None:
            self.from_area = from_area
            self.into_deck = into_area
            super().__init__(trigger=face, player=into_area.GetOwnerPlayer())

    class WhenCardWouldLeavePlay(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, face: 'CardFace', from_area: 'Deck', into_area: 'Deck', by_effect: 'Effect', by_swapping: bool, index: int=-1) -> None:
            from game.message import Message
            self.into_area: Final = into_area
            self.by_effect: Final = by_effect
            self.by_swapping: Final = by_swapping
            self.from_area: Final = from_area
            self.index: Final = index
            super().__init__(trigger=face, end_event=Message.WhenCardLeavePlay)

    class WhenCardLeavePlay(TriggerFaceMessage, HasPreEventMessage, HasEndEventMessage):
        """
        Haven't lose equipment
        """
        def __init__(self, face: 'CardFace', pre_message: 'Message.WhenCardWouldLeavePlay') -> None:
            from game.message import Message
            # from game.message import OnEvent
            self.into_area: Final = pre_message.into_area
            self.by_effect: Final = pre_message.by_effect
            self.by_swapping: Final = pre_message.by_swapping
            self.from_area: Final = pre_message.from_area
            self.index: Final = pre_message.index
            super().__init__(trigger=face, pre_message=pre_message, end_event=Message.AfterCardLeavePlay)
            # self.TriggerOnEvent(OnEvent.LeavePlayWhen)

        @property
        def would_leave_play_message(self) -> 'Message.WhenCardWouldLeavePlay':
            return self.pre_message

    class AfterCardLeavePlay(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', from_area: 'Deck', into_area: 'Deck', leave_play_message: 'Message.WhenCardLeavePlay') -> None:
            # from game.message import OnEvent
            self.from_area: Final = from_area
            self.into_area: Final = into_area
            self.by_effect: Final = leave_play_message.by_effect
            self.by_swapping: Final = leave_play_message.by_swapping
            super().__init__(trigger=face, pre_message=leave_play_message)
            # self.TriggerOnEvent(OnEvent.LeavePlayAfter)

        @property
        def when_leave_play_message(self) -> 'Message.WhenCardLeavePlay':
            return self.pre_message

        @property
        def would_leave_play_message(self) -> 'Message.WhenCardWouldLeavePlay':
            return self.when_leave_play_message.would_leave_play_message

    class WhenCardWouldDiscard(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, trigger: 'CardFace', by_effect: 'Effect') -> None:
            from game.message import Message
            self.into_area = None
            self.by_effect: Final = by_effect
            self.is_top: Final = trigger.card.area.GetTop() == trigger
            super().__init__(trigger, end_event=Message.AfterCardDiscard)

        def SetToArea(self, deck: 'Deck'):
            self.into_area = deck

    class AfterCardDiscard(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, trigger: 'CardFace', from_area: 'Deck', by_effect: 'Effect', discard_message: 'Message.WhenCardWouldDiscard') -> None:
            self.from_area: Final = from_area
            self.by_effect: Final = by_effect
            super().__init__(trigger, pre_message=discard_message)
            if from_area.flags.is_deck or from_area.flags.is_in_play:
                text = TransText("{face} was discarded to {into_area} ({effect})", face=trigger, into_area=trigger.card.area, effect=by_effect.this)
                self.Present(text, 'carddrop', trigger, by_effect.this)

        @property
        def discard_message(self) -> 'Message.WhenCardWouldDiscard':
            return self.pre_message

    ################################################################################
    #
    class WhenEffectBeCancel(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect', be_cancel_effect: Literal["All", "WhenReveal"]) -> None:
            self.cancel_by_effect: Final = by_effect
            self.be_cancel_effect: Final = be_cancel_effect
            super().__init__(trigger=face)
            text = TransText("{face}'s {be_cancel_effect} effect was canceled by {by_effect}", face=face, be_cancel_effect=be_cancel_effect, by_effect=by_effect.this)
            self.Present(text, "negate", by_effect.this)

    class WhenCardWouldReveal(TriggerPlayerMessage, TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        """Before flip"""
        def __init__(self, face: 'CardFace', player: 'Player', by_effect: 'Effect', from_area: 'Deck', is_by_flipping: bool) -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            self.from_area: Final = from_area
            self.is_by_flipping: Final = is_by_flipping

            super().__init__(player=player, trigger=face, end_event=Message.AfterCardRevealedEnd)

            if face.card.area.flags.is_dealt_encounter:
                text = TransText("{face} would be revealed ({by_effect})", face=face, by_effect=by_effect.this)
                self.Present(text, "", face, player.GetIdentity())

    class AfterCardsMovedToRevealingArea_Text(TextMessage):
        def __init__(self, faces: List['CardFace']) -> None:
            super().__init__(world=faces[0].card.world)
            text = TransText("{faces} moved to revealing area", faces=faces)
            self.Present(text, "set", *faces)

    class WhenCardPutIntoPlay(TriggerPlayerMessage, TriggerFaceMessage, HasEndEventMessage):
        def __init__(self, face: 'CardFace', player: 'Player', from_area: 'Deck', by_effect: 'Effect', target_game_area: 'GameArea|None'=None) -> None:
            from game.message import Message
            # from game.message import OnEvent
            self.by_effect: Final = by_effect
            self.from_area: Final = from_area
            self.target_game_area: Final = target_game_area
            super().__init__(player=player, trigger=face, end_event=Message.AfterCardPutIntoPlay)
            # text = TransText("{face} puts into play", face=face)
            # self.Present(text, "", face)
            # self.TriggerOnEvent(OnEvent.CardInPlay)

    class AfterCardPutIntoPlay(TriggerPlayerMessage, TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenCardPutIntoPlay') -> None:
            from game.message import Message
            # from game.message import OnEvent
            self.by_effect: Final = message.by_effect
            moved_message = Message.AfterCardsMoved({face: message.from_area}, by_put_into_play=True)
            moved_message.Send()
            super().__init__(player=message.GetToPlayer(), trigger=face, pre_message=message)
            # self.TriggerOnEvent(OnEvent.CardInPlay)

        @property
        def when_card_put_into_play(self) -> 'Message.WhenCardPutIntoPlay':
            return self.pre_message

    class WhenPlayerRevealCard(TriggerPlayerMessage, TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenCardWouldReveal', **kwargs: Any) -> None:
            from game.message import Message
            from game.message import OnEvent
            from game.card.face.attribute.has_permanent import HasPermanent
            from game.card.face.base import Villain
            from game.card.face.card_type import MainScheme
            self.from_area: Final = message.from_area
            self.would_reveal_message: Final = message

            self.cancel_when_revealed = False
            self.cancel_all_effects = False
            self.cannot_be_cancel = False

            if HasPermanent.IsType(face) and face.permanent:
                self.cannot_be_cancel = True
            elif Villain.IsType(face) or MainScheme.IsType(face):
                self.cannot_be_cancel = True

            effects = face.effect.Find(type=AbilityType.WhenRevealed)
            for effect in effects:
                if effect.ability.cannot_be_cancel:
                    self.cannot_be_cancel = True
                    break

            self.by_effect: Final = message.by_effect

            self.resolved: List[Effect] = []
            player = message.GetToPlayer()
            self.give_to_player: 'Player' = player

            super().__init__(player=player, trigger=face, end_event=Message.WhenCardRevealed)

            text = TransText("{face} is being revealed", face=face)
            self.Present(text, "reveal", face, player.GetIdentity())
            self.TriggerOnEvent(OnEvent.Reveal)

        def AddResolved(self, by_effect: 'Effect'):
            self.resolved.append(by_effect)

        def CancelWhenRevealedEffect(self, by_effect: 'Effect') -> None:
            from game.message import Message
            self.cancel_when_revealed = True
            assert not self.cannot_be_cancel
            message = Message.WhenEffectBeCancel(self.trigger, by_effect, "WhenReveal")
            message.Send()

        def IsFromEncounterDeck(self) -> bool:
            from game.operate.worlds import Worlds
            if self.from_area.flags.is_dealt_encounter:
                return True
            for villain in Worlds.GetAllVillains(self.world):
                if self.from_area == villain.encounter_deck:
                    return True
            return False

        def CancelAllEffectsAndDiscardIt(self, by_effect: 'Effect') -> None:
            return self.CancelAllEffectsInternal(by_effect, discard_it=True)

        """
        Canceling the effects of a treachery card, means canceling all of the effects on that card,including keywords.
        So if you cancel the effects of a card with Incite, you also cancel the Incite keyword.
        e.g. Spycraft
        """
        def CancelAllEffectsInternal(self, by_effect: 'Effect', *, discard_it: bool=False) -> None:
            from game.message import Message
            from game.operate.faces import Faces

            self.cancel_all_effects = True
            message = Message.WhenEffectBeCancel(self.trigger, by_effect, "All")
            message.Send()
            if discard_it:
                Faces.DiscardAll([self.trigger], by_effect)
                self.trigger.card.state.is_revealing = False

        def CanBeCancel(self, cancel_level: Literal['WhenRevealed', 'All'], by_effect: 'Effect') -> bool:
            from game.message import Message
            from game.card.face.card_type import Treachery
            message = Message.CheckIfEffectCanBeCancelBy(self.by_effect, by_effect)
            message.Send()
            if self.cannot_be_cancel:
                return False
            if not message.can_be_cancel:
                return False
            if cancel_level == 'WhenRevealed':
                when_revealed_effects = self.trigger.effect.Find(
                    type=AbilityType.WhenRevealed,
                )
                if not bool(self.world.rule.v18_timing):
                    when_revealed_effects = [
                        effect
                        for effect in when_revealed_effects
                        if not effect.ability.v18_timing_keyword
                    ]
                return not not when_revealed_effects and \
                    not self.cancel_all_effects and \
                    not self.cancel_when_revealed
            if cancel_level == 'All':
                face = self.trigger
                return not self.cancel_all_effects and \
                    (
                        not Treachery.IsType(face) or \
                        ( face.incite > 0) or \
                        ( not self.cancel_when_revealed and not not face.effect.Find(type=AbilityType.WhenRevealed))
                    )

        def GetGaveToPlayer(self) -> 'Player':
            return self.give_to_player

        def SetGiveToPlayer(self, player: 'Player'):
            self.give_to_player = player

    class CheckIfEffectCanBeCancelBy(CheckIfMessage):
        def __init__(self, check_effect: 'Effect', by_effect: 'Effect') -> None:
            self.can_be_cancel = True
            self.check_effect: Final = check_effect
            self.by_effect: Final = by_effect
            super().__init__(by_effect.this)

        def SetCannotBeThwart(self, by_effect: 'Effect'):
            self.can_be_cancel = False
            self.SetCauseBy(by_effect)

    class WhenObligationGiveToPlayer(TriggerPlayerMessage, TriggerFaceMessage):
        def __init__(self, player: 'Player', message: 'Message.WhenCardRevealed') -> None:
            face = message.trigger
            super().__init__(player=player, trigger=face)

        def GetGaveToPlayer(self) -> 'Player':
            return self.GetToPlayer()

    class WhenCardRevealed(TriggerPlayerMessage, TriggerFaceMessage, HasPreEventMessage, HasEndEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenPlayerRevealCard') -> None:
            # self.from_area: Final = message.from_area
            from game.message import Message
            self.reveal_message: Final = message
            self.by_effect: Final = message.by_effect
            self.from_area: Final = message.from_area
            player = message.GetToPlayer()

            super().__init__(player=player, trigger=face, pre_message=message, end_event=Message.AfterCardRevealed)

            text = TransText("{face} was revealed", face=face)
            self.Present(text, "", face)

        @property
        def is_by_flipping(self) -> bool:
            return self.when_player_reveal_message.would_reveal_message.is_by_flipping

        @property
        def when_player_reveal_message(self) -> 'Message.WhenPlayerRevealCard':
            return self.pre_message

        def IsFromEncounterDeck(self) -> bool:
            return self.reveal_message.IsFromEncounterDeck()

        def GetGaveToPlayer(self) -> 'Player':
            return self.when_player_reveal_message.GetGaveToPlayer()

    class AfterCardRevealed(TriggerPlayerMessage, TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenCardRevealed', **kwargs: Any) -> None:
            reveal_message = message.reveal_message
            revealed_message = message

            self.reveal_message: Final = reveal_message
            self.revealed_message: Final = revealed_message

            self.is_cancel_all: Final = reveal_message.cancel_all_effects
            self.is_cancel_when_revealed: Final = reveal_message.cancel_when_revealed

            super().__init__(player=message.GetToPlayer(), trigger=face, pre_message=revealed_message)

            # text = TransText("{face} reveals end", face=face)
            # self.Present(text, "", face)

    class AfterCardRevealedEnd(TriggerPlayerMessage, TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenPlayerRevealCard', revealed_message: 'Message.WhenCardRevealed|None', **kwargs: Any) -> None:
            self.reveal_message: Final = message
            self.revealed_message: Final = revealed_message
            would_message = message.would_reveal_message
            super().__init__(player=message.GetToPlayer(), trigger=face, pre_message=would_message)

    # class WhenCardRevealedFake(WhenCardRevealed):
    #     def __init__(self, face: 'CardFace', player: 'Player', from_area: 'Deck') -> None:
    #         super().__init__(face, player, from_area, broadcast=False)

    # class AfterCardRevealed(ToPlayerMessage, TriggerMessage):
    #     def __init__(self, face: 'CardFace', player: 'Player') -> None:
    #         super().__init__(player=player, trigger=face)

    class WhenBoostIconsWouldBeCount(TriggerFaceMessage, CanBeInstead):
        def __init__(self, face: 'HasBoostIcon') -> None:
            self.update_boost_icons = 0
            self.set_boost_icons = 0
            super().__init__(trigger=face)
            text = TransText("{face} would count boost icons ({boost})", face=face, boost=face.printed_boost * Symbol.boost)
            self.Present(text, "token" if face.printed_boost > 0 else "", face)

        def UpdateBoostIcon(self, value: int, by_effect: 'Effect'):
            from game.card.face.attribute.has_boost_icon import HasBoostIcon
            assert HasBoostIcon.IsType(self.trigger)
            self.update_boost_icons = value
            text = TransText("{trigger} boost icons {value:+} ({by_effect})", trigger=self.trigger, value=value, by_effect=by_effect.this)
            self.Present_ByEffect(text, "", self.trigger, by_effect.this)
            # self.trigger.GainBoostIcons(value, by_effect)

        def SetBoostIcon(self, value: int, by_effect: 'Effect'):
            from game.card.face.attribute.has_boost_icon import HasBoostIcon
            assert HasBoostIcon.IsType(self.trigger)
            # diff = value - self.trigger.boost_const
            # self.UpdateBoostIcon(diff, by_effect)
            self.set_boost_icons = value
            text = TransText("{trigger} boost icons were set to {value} ({by_effect})", trigger=self.trigger, value=value, by_effect=by_effect.this)
            self.Present_ByEffect(text, "", self.trigger, by_effect.this)

    class WhenBoostCardWouldTurnedFaceUp(TriggerFaceMessage, TriggerNonePlayerMessage, AttackerNoneMessage, CanBeInstead):
        def __init__(self, face: 'CardFace', being_message: 'Message.WhenUnitBeingAttack|Message.WhenSchemeBeingScheme') -> None:
            from game.message import Message
            player = _get_activation_target_player(being_message)
            self.being_message: Final = being_message
            self.would_message: Final = being_message.would_message
            self.would_atk_message: Final = being_message.would_message if isinstance(being_message.would_message, Message.WhenUnitWouldAttack) else None
            being_atk_message = being_message if self.would_atk_message else None
            super().__init__(player=player, being_atk_message=being_atk_message, trigger=face)

    class AfterCardsMovedToBoostingArea_Text(TextMessage):
        def __init__(self, faces: List['CardFace']) -> None:
            super().__init__(world=faces[0].card.world)
            text = TransText("{faces} moved to boosting area", faces=faces)
            self.Present(text, "set", *faces)

    class WhenBoostCardTurnedFaceUp(TriggerFaceMessage, TriggerNonePlayerMessage):
        def __init__(self, face: 'CardFace', being_message: 'Message.WhenUnitBeingAttack|Message.WhenSchemeBeingScheme') -> None:
            from game.card.face.base import EncounterNonVillainCard
            from game.message import Message
            player = _get_activation_target_player(being_message)
            
            self.being_message: Final = being_message
            self.would_message: Final = being_message.would_message

            if isinstance(being_message, Message.WhenUnitBeingAttack):
                self.would_atk_message: Final = being_message.would_atk_message 

            self.boost_icons = face.boost_const if EncounterNonVillainCard.IsType(face) else 0
            self.original_boost_icons: Final = self.boost_icons

            self.cancel_boost_icons = False
            self.cancel_boost_ability = False

            super().__init__(player=player, trigger=face)

        def CancelAllBoostIcons(self, by_effect: 'Effect') -> int:
            self.cancel_boost_icons = True
            cancel_num = self.boost_icons
            self.boost_icons = 0
            from game.card.face.attribute.has_boost_icon import HasBoostIcon
            if HasBoostIcon.IsType(self.trigger):
                self.trigger.SetBoostIcon(0, by_effect)
                return cancel_num
            return 0

        def CancelBoostAbility(self, by_effect: 'Effect'):
            self.cancel_boost_ability = True

    class WhenCardBecomeBoost(TriggerFaceMessage, HasEndEventMessage, TriggerNonePlayerMessage):
        def __init__(self, face: 'CardFace', flip_message: 'Message.WhenBoostCardTurnedFaceUp') -> None:
            from game.message import Message
            from game.card.face.base import Enemy
            self.is_cancel_boost_ability: Final = flip_message.cancel_boost_ability
            self.being_message: Final = flip_message.being_message
            self.would_message = self.being_message.would_message
            player = _get_activation_target_player(self.being_message)
            self.against_player = player

            if isinstance(self.being_message, Message.WhenSchemeBeingScheme):
                self.would_sch_message: Final = self.being_message.would_sch_message
            if isinstance(self.being_message, Message.WhenUnitBeingAttack):
                self.would_atk_message: Final = self.being_message.would_atk_message

            self.activating_enemy: Final = self.would_message.trigger.CastTo(Enemy)

            # Any constant or boost abilities that refer to "you" refer to the defending player.
            super().__init__(player=player, trigger=face, end_event=Message.AfterCardBecomeBoost)

            # text = TransText("{face} gives {boost_const} for {message}", face=face, boost_const=flip_message.boost_icons, message=self.being_message.GetDisplayName())
            # self.Present(text, "reveal", face)

        def GetAgainstPlayer(self) -> 'Player|None':
            return self.GetToPlayer()

        # for this activation.
        def GainBoostIcon(self, value: int, by_effect: 'Effect'):
            from game.card.face.base import EncounterNonVillainCard
            from game.message import Message
            trigger = self.trigger
            assert EncounterNonVillainCard.IsType(trigger)
            trigger.GainBoostIcons(value, by_effect)

            from game.ability.ability import Ability
            from game.ability.ability import AbilityType

            trigger.effect.RegisterTemp(
                Ability(
                    AbilityType.Temp0,
                    Message.AfterCardBecomeBoost,
                    [
                        lambda effect, message:
                            self == message.boost_message,
                    ],
                    lambda boost_effect, message:
                        trigger.GainBoostIcons(-1 * value, by_effect)
                ),
                unregister_after_exec=True,
                until_turn_end=True
            )

        def GiveActivatingEnemyAdditionalBoostCard(self, num: int, by_effect: 'Effect'):
            self.GiveBoostCardForThisActivation(self.activating_enemy, num, by_effect)

        def GiveBoostCardForThisActivation(self, card_type: Type['Villain']|Type['Enemy']|'CardFace', num: int, by_effect: 'Effect'):
            #  If a boost ability on a boost card dealt to a minion refers to “the villain,” that ability still applies to the villain (even though a minion is resolving it).
            from game.card.face.attribute.can_boost import CanBoost
            from game.card.face.base import Villain
            from game.card.face.card_face import CardFace
            trigger = self.being_message.by_face
            face = None
            if isinstance(card_type, CardFace):
                if trigger == card_type:
                    face = trigger
            elif Villain.IsType(trigger):
                face = trigger

            if face:
                face.CastTo(CanBoost).GiveFacedownBoostCardsInternal(num, by_effect, self.would_message)

        def AfterThisActivation(self, effect: 'Effect', action: Callable[[], Any]):
            from game.operate.run_at import RunAt
            RunAt.AfterEnemyActivationEnd(effect, self.being_message, action)

        @override
        def GetToPlayer(self) -> 'Player':
            from game.player import Player
            if type(self.to_player) is Player:
                return self.to_player
            else:
                return self.world.GetCurrentPlayer()

    class AfterCardBecomeBoost(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenCardBecomeBoost') -> None:
            self.boost_message: Final = message
            super().__init__(trigger=face, pre_message=message)

        def GetAgainstPlayer(self) -> 'Player|None':
            return self.boost_message.GetToPlayer()

    ################################################################################
    # Those message only for UI
    class WhenCardReset_Text(TextMessage):
        def __init__(self, face: 'CardFace', is_flip: bool) -> None:
            # Notify.WaitConfirm(f'{face} reseted', face)
            self.is_flip = is_flip

    class AfterCardsDiscard_Text(TextMessage):
        def __init__(self, face_deck: Dict['CardFace', 'Deck']) -> None:
            from game.message import Message
            if face_deck:
                face = list(face_deck.keys())[0]
                super().__init__(world=face.card.world)
                # present = True
                # for face in face_deck:
                #     if face_deck[face].flags.is_in_play or face_deck[face].flags.is_deck:
                #         present = False
                #         break
                if not any(face_deck[face].flags.is_in_play or face_deck[face].flags.is_deck for face in face_deck):
                    text = TransText("{cards} were discarded", cards=list(face_deck.keys()))
                    self.Present(text, "carddrop")
                message = Message.AfterCardsMoved(face_deck, by_discard=True)
                message.Send()

    class AfterCardsReturnToHand_Text(TextMessage):
        def __init__(self, faces: Sequence['CardFace'], by_effect: 'Effect') -> None:
            from game.message import Message
            from game.operate.faces import Faces
            if len(faces) > 0:
                super().__init__(world=faces[0].card.world)
                text = TransText("{cards} were returned to hand ({by_effect})", cards=faces, by_effect=by_effect.this)
                self.Present(text, "", *faces, by_effect.this)
                from_decks = Faces.GetDecksInDeck(faces)
                message = Message.AfterCardsMoved(from_decks, by_return_to_hand=True)
                message.Send()

    class AfterCardsMoved_Text(TextMessage):
        def __init__(self, faces: List['CardFace'], from_area: 'Deck|None'=None, into_area: 'Deck|None'=None):
            if len(faces) > 0:
                super().__init__(world=faces[0].card.world)

                sound: 'Message2.SOUND_NAMES' = ''

                if into_area == None:
                    into_area = faces[0].card.area

                if into_area.flags.is_resources_area:
                    text = TransText("{faces} were moved to {into_area}", faces=faces, into_area=into_area)
                elif from_area and from_area.flags.is_in_hand:
                    text = TransText("{faces} were moved to {into_area}", faces=faces, into_area=into_area)
                    sound = 'set'
                elif into_area.flags.is_boost_area:
                    if into_area.bind_card:
                        text = TransText("{faces} were moved to {into_area}'s boost area", faces=faces, into_area=into_area.bind_card.face)
                    else:
                        text = TransText("{faces} moved to boost area", faces=faces)
                    sound = 'token'
                elif into_area.flags.is_in_hand and from_area and not from_area.flags.is_in_hand:
                    text = TransText("{player} drew {faces} from {from_area}", player=into_area.bind_owner, faces=faces, from_area=from_area)
                    sound = 'draw'
                elif into_area.flags.is_removed: # and not from_area.IsRemoved():
                    text = TransText("{faces} were removed from {from_area}", faces=faces, from_area=from_area)
                    sound = 'banished'
                elif into_area.flags.is_resources_area:
                    text = TransText("{faces} were moved to {into_area}", faces=faces, into_area=into_area)
                elif into_area.flags.is_discards:
                    text = TransText("{faces} were discarded to {into_area}", faces=faces, into_area=into_area)
                    sound = 'carddrop'
                else:
                    text = TransText("{faces} were moved to {into_area}", faces=faces, into_area=into_area)
                    sound = 'set'

                self.Present(text, sound, *faces)

    # No pre message
    class AfterCardsMoved(Message2):
        def __init__(self, face_areas: Dict['CardFace', 'Deck'], *,
                    by_shuffle: bool=False,
                    by_discard: bool=False,
                    by_put_into_play: bool=False,
                    by_place_on_table: bool=False,
                    by_return_to_hand: bool=False,
                    by_swap: bool=False,
                    by_setaside: bool=False,
                    by_draw_up: bool=False,
                    by_resources: bool=False,
                    by_deal_encounter_card: bool=False,
                    by_boost: bool=False,
                    by_remove: bool=False,
                    move_by_position: bool=False
                    ) -> None:
            from game.message import Message
            self.face_areas: Final = face_areas # from
            self.faces: Final = list(face_areas.keys())

            self.from_areas: Final = set(face_areas.values())
            self.into_areas: Final = set([x.card.area for x in self.faces])
            self.related_decks: Final = set(self.from_areas) | set(self.into_areas)
            self.by_shuffle: Final = by_shuffle

            if len(self.faces) > 0:
                super().__init__(world=self.faces[0].card.world)
                self.AddRelatedFace(*self.faces)

                if by_shuffle or by_discard or by_put_into_play or by_place_on_table or by_return_to_hand or by_swap or by_setaside or by_draw_up or by_resources or by_deal_encounter_card or by_boost or by_remove or move_by_position:
                    # We had handled it elsewhere
                    pass
                else:
                    assert len(self.into_areas) == 1
                    from_area = list(self.from_areas)[0] if len(self.from_areas) == 1 else None
                    into_area = list(self.into_areas)[0]
                    Message.AfterCardsMoved_Text(self.faces, from_area, into_area)

        def IsDeckTypeRelated(self, deck_type: 'DeckType') -> bool:
            for deck in self.related_decks:
                if deck.deck_type == deck_type:
                    return True
            return False

        @override
        def Send(self):
            if self.face_areas:
                return super().Send()

        def IsIncludeFace(self, which_card: 'Condition.CARD_TYPE', by_effect: 'Effect') -> 'CardFace|None':
            for face in self.face_areas:
                if Condition.CheckWhichCard(which_card, face, by_effect):
                    return face
            return None

    class AfterCardsExhaust_Text(TextMessage):
        def __init__(self, faces: Sequence['CardFace'], by_effect: 'Effect') -> None:
            if len(faces) > 0:
                super().__init__(world=faces[0].card.world)
                text = TransText("{cards} exhausted ({by_effect})", cards=faces, by_effect=by_effect.this)
                self.Present(text, "flip", *faces, by_effect.this)

    class AfterCardsSwapDeck_Text(TextMessage):
        def __init__(self, face0: 'CardFace', face1: 'CardFace') -> None:
            from game.message import Message
            super().__init__(world=face0.card.world)
            text = TransText("{face0} {face1} swapped", face0=face0, face1=face1)
            self.Present(text, "set")
            message = Message.AfterCardsMoved({
                face0: face1.card.area,
                face1: face0.card.area,
            }, by_swap=True)
            message.Send()

    class AfterCardsPlaceOnTable_Text(TextMessage):
        def __init__(self, faces: Sequence['CardFace']) -> None:
            if len(faces) > 0:
                super().__init__(world=faces[0].card.world)
                text = TransText("{cards} were placed on table", cards=faces)
                self.Present(text, "set", *faces)

    class AfterCardsRemove_Text(TextMessage):
        def __init__(self, cards: Sequence['CardFace']) -> None:
            if len(cards) > 0:
                super().__init__(world=cards[0].card.world)
                text = TransText("{cards} removed", cards=cards)
                self.Present(text, "carddrop")

    class AfterCardsFlipAll_Text(TextMessage):
        def __init__(self, faces: Sequence['CardFace']) -> None:
            if len(faces) > 0:
                super().__init__(world=faces[0].card.world)
                text = TransText("{cards} were flipped", cards=faces)
                self.Present(text, "flip")

    class AfterCardsSetAside_Text(TextMessage):
        def __init__(self, face_deck: Dict['CardFace', 'Deck']) -> None:
            from game.message import Message
            if face_deck:
                super().__init__(world=list(face_deck.keys())[0].card.world)
                text = TransText("{cards} were set aside", cards=list(face_deck.keys()))
                self.Present(text, "set")
                message = Message.AfterCardsMoved(face_deck, by_setaside=True)
                message.Send()

    class AfterCardsReadied_Text(TextMessage):
        def __init__(self, faces: Sequence['CardFace'], by_effect: 'Effect') -> None:
            super().__init__(world=by_effect.world)
            if len(faces) > 0:
                text = TransText("{cards} readied ({by_effect})", cards=faces, by_effect=by_effect.this)
                self.Present(text, "flip", *faces, by_effect.this)

    class WhenCardUpdateTrait_Text(TextMessage):
        def __init__(self, face: 'CardFace', diff: int, traits: List["CardFace.TRAITS"], by_effect: 'Effect'):
            from game.message import Message
            face.card.ui.SetEffectedBy(diff, by_effect)
            if diff == 1:
                message = Message.AfterCardGainTrait(face, traits, by_effect)
                message.Send()
            elif diff == -1:
                message = Message.AfterCardLoseTrait(face, traits, by_effect)
                message.Send()

    # TODO: Pre message
    class AfterCardGainTrait(CardStateUpdatedMessage):
        def __init__(self, face: 'CardFace', traits: List["CardFace.TRAITS"], by_effect: 'Effect'):
            # from game.message import OnEvent
            self.by_effect = by_effect
            self.traits: Final = traits
            # text = TransText("{face} gains {trait} ({by_effect})", face=face, trait=trait, by_effect=by_effect.this)
            # self.Present(text, "activate", face, by_effect.this)
            super().__init__(trigger=face)
            # self.TriggerOnEvent(OnEvent.Trait)

    # TODO: Pre message
    class AfterCardLoseTrait(CardStateUpdatedMessage):
        def __init__(self, face: 'CardFace', traits: List["CardFace.TRAITS"], by_effect: 'Effect'):
            # from game.message import OnEvent
            self.by_effect = by_effect
            self.traits: Final = traits
            # text = TransText("{face} loses {trait} ({by_effect})", face=face, trait=trait, by_effect=by_effect.this)
            # self.Present(text, "activate", face, by_effect.this)
            super().__init__(trigger=face)
            # self.TriggerOnEvent(OnEvent.Trait)

    ################################################################################
    # Consider As
    class WhenAreaCardUpdateConsiderAs(TriggerFaceMessage):
        def __init__(self, face: 'CardFace') -> None:
            assert False
            super().__init__(trigger=face)

    ################################################################################
    # Environment
    ################################################################################

    class WhenCardFaceActivated(TriggerFaceMessage, HasEndEventMessage):
        """Refresh continuous effects after a flip, without entering play."""
        def __init__(self, face: 'CardFace', by_effect: 'Effect') -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            super().__init__(trigger=face, end_event=Message.AfterCardFaceActivated)

    class AfterCardFaceActivated(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', message: 'Message.WhenCardFaceActivated') -> None:
            self.by_effect: Final = message.by_effect
            super().__init__(trigger=face, pre_message=message)

    # Actual entry into play. Changing the active face uses the internal
    # face-activation messages above, so entry abilities cannot fire on flips.
    class WhenCardEnterPlay(TriggerFaceMessage, HasEndEventMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect') -> None:
            from game.card.face.attribute.has_cost import HasCost
            from game.element.resources import Resources
            from game.element.cost import Cost
            from game.ability.cost_func import CostFunc
            from game.message import Message

            self.by_effect: Final = by_effect

            paid_cost = Resources("0")
            need_cost = Cost("0")

            if by_effect.is_rule or \
                not HasCost.IsType(face) or \
                by_effect.is_forced:
                pass
            elif by_effect.this == face:
                # put into play by its play
                paid_cost = by_effect.context.paid_this_resources
                if by_effect.context.this_effect_need_cost:
                    need_cost = by_effect.context.this_effect_need_cost
                else:
                    need_cost = Cost("0")
            elif by_effect.ability.is_play:
                # Fix play 12011
                # put into play by other ability
                cost_fn = by_effect.cost_func.Has(CostFunc.PayPrintCost)
                if cost_fn:
                    paid_cost = cost_fn.return_paid_resources
                need_cost = face.printed_cost

            self.paid_cost: Final = paid_cost
            self.overpaid: Final = paid_cost.val - need_cost.val

            super().__init__(trigger=face, end_event=Message.AfterCardEnterPlay)

            text = TransText("{face} is entering play ({by_effect})", face=face, by_effect=by_effect.this)
            self.Present(text, "", face)

    class AfterCardEnterPlay(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', from_area: 'Deck', into_area: 'Deck', by_effect: 'Effect', enter_play_message: 'Message.WhenCardEnterPlay') -> None:
            self.from_area: Final = from_area
            self.into_area: Final = into_area
            self.by_effect: Final = by_effect
            self.paid_resources: Final = by_effect.context.paid_this_resources
            super().__init__(trigger=face, pre_message=enter_play_message)
            text = TransText("{face} entered play ({by_effect})", face=face, by_effect=by_effect.this)
            self.Present(text, "set" if not from_area.flags.is_in_play else "", face)

    class WhenCardWouldRemoveFromGame(TriggerFaceMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect', *, ui_group: bool=False) -> None:
            from game.message import Message
            self.by_effect = by_effect
            super().__init__(trigger=face, end_event=Message.AfterCardRemoveFromGame)
            if not ui_group:
                text = TransText("{face} would be removed from game", face=face)
                self.Present(text, "", face)

    class AfterCardRemoveFromGame(TriggerFaceMessage, HasPreEventMessage):
        def __init__(self, face: 'CardFace', would_remove_message: 'Message.WhenCardWouldRemoveFromGame') -> None:
            super().__init__(trigger=face, pre_message=would_remove_message)

    ################################################################################
    #
    class WhenCardTreatAsIfBlank(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', by_effect: 'Effect') -> None:
            self.by_effect: Final = by_effect
            super().__init__(trigger=face)
            text = TransText("{face} is treated as if blank ({by_effect})", face=face, by_effect=by_effect.this)
            self.Present(text, "", face)

    class WhenCardWouldTreatAsIfBlank(TriggerFaceMessage, CanBeInstead):
        def __init__(self, face: 'CardFace', by_effect: 'Effect') -> None:
            self.by_effect: Final = by_effect
            super().__init__(trigger=face)

    class WhenCardSetAs(TriggerFaceMessage):
        def __init__(self, face: 'CardFace', to_face: 'CardFace') -> None:
            self.to_face: Final = to_face
            super().__init__(trigger=face)
