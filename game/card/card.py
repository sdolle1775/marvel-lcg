from typing import Final
from core import *
from game.card.states import CardIsStates, CardCanStates
from game.object import Object

from game.card.face import *
from game.deck import *
from game.player import *
from game.effect import *
from game.message import *

from game.world.game_area import *
from game.world import *
from game.render.descriptor.card import CardDescriptor

@final
class Card(Object):
    # def __enter__(self):
    #     self.SetLikeInHand(True)
    #     return self

    # def __exit__(self, *obj: object):
    #     self.SetLikeInHand(False)
    #     pass

    def __lt__(self, other: 'Card'):
        return self.object_id < other.object_id

    class Visible:
        def __init__(self, card: 'Card') -> None:
            self.visible_players: Set['Player'] = set()
            self.card: Final = card
            pass
        def Clean(self):
            self.visible_players.clear()
        def Update(self) -> None: # Only add
            for player in self.card.world.const_players:
                if self.card.IsVisible(player):
                    self.visible_players.add(player)
        def Set(self, visible: 'Literal[False, True]|Player') -> None:
            if visible == False:
                self.Clean()
            elif visible == True: # "All"
                for player in self.card.world.const_players:
                    self.visible_players.add(player)
            else:
                self.visible_players.add(visible)
        def IsVisible(self, player: 'User|Literal["Any"]') -> bool:
            if player == "Any":
                return len(self.visible_players) > 0
            if player in self.visible_players:
                return True
            return False

    def __init__(self, owner: 'Player|Scenario', *faces: 'CardFace', world: 'World', is_reference: bool=False) -> None:
        super().__init__('reference_card' if is_reference else 'card', world)

        self.area: 'Deck'

        self.owner_original: Final = owner # Fix "51036"
        self.owner_internal: 'Player|Scenario' = owner

        self.state = CardIsStates()
        self.can_state = CardCanStates()

        self.visible = Card.Visible(self)

        self.is_apply_unique_rule: bool|None = None

        self.face: CardFace = faces[0]
        self.back_faces: List[CardFace] = list(faces[1:])

        for face in [self.face] + self.back_faces:
            face.card = self

        self.game_area: 'GameArea'

        self.bind_discard_pile: 'Deck|None' = None

        class Components:
            from game.card.face.component.component import Component

            def __init__(self, card: 'Card') -> None:
                from game.card.face.component.inventory import Inventory
                from game.card.face.component.attach import PlacedCard
                from game.card.face.component.counter import Counter
                from game.card.face.component.boostable import Boostable
                from game.card.face.component.status import Status
                from game.card.face.component.buffs import Buffs
                from game.card.face.component.buffs import Token
                from game.card.face.component.buffs import Health
                # We create all of components here for card change
                # e.g. an item change to unit, in that case, this card need `Health` and so on
                self.inventory      = Inventory(card)
                self.placed_card    = PlacedCard(card)  # stack, slot
                self.status         = Status(card)
                self.counter        = Counter(card)
                self.token          = Token(card)
                self.health         = Health(card)
                self.boostable      = Boostable(card)   # boost
                self.buffs          = Buffs(card)

            def GetAll(self) -> List[Component]:
                return [self.inventory, self.placed_card, self.status, self.counter, self.token, self.health, self.boostable]
                # TODO: Find out why can not use this
                # return [x for x in vars(self) if isinstance(x, Component)]

            def OnRemove(self, by_effect: 'Effect'):
                for component in self.GetAll():
                    component.OnRemove(by_effect)
            def OnAfterLeavePlay(self, by_effect: 'Effect'):
                for component in self.GetAll():
                    component.OnParentLeavePlay(by_effect)
            def OnDiscard(self, by_effect: 'Effect') -> List['CardFace']:
                faces: List['CardFace'] = []
                for component in self.GetAll():
                    faces.extend(component.OnDiscard(by_effect))
                return faces
            # def OnWouldEnterPlay(self):
            #     for component in self.GetAll():
            #         component.OnWouldEnterPlay()
            def OnBeforeFlip(self, by_effect: 'Effect', no_detach: bool=False):
                for component in self.GetAll():
                    component.OnBeforeParentFlip(by_effect, no_detach=no_detach)
            # def OnFlip(self, by_effect: 'Effect', origin_face: 'CardFace|None'):
            #     for component in self.GetAll():
            #         component.OnFlip(by_effect, origin_face)
            def OnAfterFlip(self, by_effect: 'Effect'):
                for component in self.GetAll():
                    component.OnAfterParentFlip(by_effect)
            def OnReset(self):
                for component in self.GetAll():
                    component.OnParentReset()
            # def OnWhenEnterPlay(self):
            #     for component in self.GetAll():
            #         component.OnWhenEnterPlay()
            # def OnDefeating(self):
            #     for component in self.GetAll():
            #         component.OnDefeating()

        self.components = Components(self)

        self.printed_faces: List['CardFace'] = [self.face] + self.back_faces

        from game.card.ui_effect_by import UIEffectBy
        self.ui = UIEffectBy(self)

    # def GetSelf(self, face_type: Type['TC']) -> TC:
    #     # if isinstance(self, face_type):
    #     #     return self
    #     if isinstance(self.face, face_type):
    #         return self.face
    #     assert False, f"{self=} {face_type=}"

    # TP = TypeVar("TP", bound='Component')
    # def FindComponent(self, component_type: Type[TP]) -> TP|None:
    #     from typing import get_origin
    #     for component in self.components:
    #         if component.IsType(get_origin)(component_type) or component.IsType(component_type):
    #             assert isinstance(component, component_type|None), f"{component=} {component_type=}"
    #             return component
    #     return None

    # def CreateComponent(self, component_type: Type[TP]):
    #     if not self.FindComponent(component_type):
    #         self.components.append(component_type(self))

    # def GetComponent(self, component_type: Type[TP]) -> TP:
    #     component = self.FindComponent(component_type)
    #     assert component, f"{self=} {component_type=}"
    #     return component

    def GetCRC(self, *, recalculate: bool=False) -> int:
        if self.IsInHand():
            crc = -2
        elif self.IsInDeck() and self.area.GetAll()[-1] == self.face:
            crc = -3
        elif self.IsInDeck() and self.area.GetAll()[0] == self.face:
            crc = -4
        elif self.IsOnField() or self.area.flags.is_status_area:
            if recalculate:
                self.face.GetRenderInfo() # Calc crc here
            crc = self.face.crc_value
        else:
            crc = -1
        return crc

    ################################################################################
    #
    def __repr__(self) -> str:
        if self.back_faces:
            return f'{self.face} / {self.back_faces}'
        else:
            return f'{self.face}'

    ################################################################################
    #
    def SetOwner(self, owner: 'Player|None'):
        if owner == None:
            controller = self.world.GetScenario()
        else:
            controller = owner
        self.owner_internal = controller
    def GetOwner(self) -> 'Player|Scenario':
        return self.owner_internal
    def GetController(self) -> 'Player|Scenario|None':
        if self.IsOnField():
            if self.area.flags.is_side_scheme_area:
                # Fix "24057" "40027"
                if PlayerSideScheme.IsType(self.face):
                    return self.owner_internal
            bind_card =  self.area.bind_card
            if bind_card:
                bind_face = bind_card.face
                # Fix "30019" attached in the main scheme
                if MainScheme.IsType(bind_face):
                    return self.owner_internal
                # Fix "50121"
                elif EncounterSideScheme.IsType(bind_face):
                    return self.owner_internal
                elif (EncounterCard.IsType(bind_face) or Villain.IsType(bind_face)) and \
                    ClassCard.IsType(self.face):
                    return self.owner_internal
                elif ClassCard.IsType(bind_face) and EncounterCard.IsType(self.face):
                    return self.owner_internal
                elif PlayerSideScheme.IsType(bind_face):
                    return self.owner_internal

            return self.area.GetOwner()
        else:
            return None

    ################################################################################
    #
    def IsInHand(self) -> bool:
        return self.area.flags.is_in_hand
    def IsLikeInHand(self) -> bool:
        if self.can_state.is_like_in_hand != None:
            return self.can_state.is_like_in_hand

        from game.message import Message
        message = Message.CheckIfFaceIsLikeInHand(self.face)
        message.Send()
        return message.is_like_in_hand
    def IsCanReadyBy(self, by_effect: 'Effect') -> bool:
        return not self.IsReady()
        # TODO: Use the follow
        if self.can_state.is_can_ready == None:
            from game.message import Message
            message = Message.CheckIfFaceCanBeReadied(self.face, by_effect)
            message.Send()
            self.can_state.is_can_ready = message.is_can_be_readied
        return self.can_state.is_can_ready
    def IsOnField(self) -> bool:
        return self.area.flags.is_in_play
    def IsOnProcessingArea(self) -> bool:
        return self.area.flags.is_processing
    def IsInDeck(self) -> bool:
        return self.area.flags.is_deck
    def IsReady(self) -> bool:
        # attach = self.face1.GetAttachToCard()
        # if attach:
        #     return attach.IsReady()
        return self.state.is_ready
    def IsExhaust(self) -> bool:
        return not self.IsReady()
    def IsFaceUp(self) -> bool:
        return self.state.is_face_up
    def IsApplyUniqueRule(self) -> bool:
        if self.is_apply_unique_rule == None:
            from game.message import Message
            this = self.face
            check_message = Message.CheckIfFaceApplyUniqueRule(this)
            check_message.Send()
            self.is_apply_unique_rule = check_message.apply_unique_rule
        return self.is_apply_unique_rule

    def IsVisible(self, player: 'User|Literal["Any"]') -> bool:
        if self.IsFaceUp():
            return True
        if self.area.flags.is_in_hand and self.area.GetOwnerPlayer() == player:
            return True
        if self.IsLikeInHand() and self.GetOwner() == player:
            return True
        return self.visible.IsVisible(player)

    def GetGameArea(self) -> 'GameArea':
        assert self.game_area != None, f"{self=}"
        return self.game_area

    ################################################################################
    #
    @final
    def CastTo(self, face_type: Type[TF]) -> TF:
        face = self.face
        return face.CastTo(face_type)

    # @final
    # def IsType(self, card_type: 'Type[TF]') -> bool:
    #     face = self.face
    #     return isinstance(face, card_type) or face.IsConsiderAs(card_type=card_type)

    ################################################################################
    #
    def RegisterEffect(self, ability: 'Ability', face: 'CardFace', *, is_temp: bool=False, is_local: bool=False, world: 'World') -> 'Effect':
        from game.effect import Effect
        from game.card.face.attribute.has_cost import HasCost
        if ability.paper:
            if self.face == face:
                assert ability.paper == self.face.paper, f"{ability.paper=} {self.face.paper=}"
            else:
                found = False
                for back_face in self.back_faces:
                    if back_face == face:
                        assert ability.paper == back_face.paper, f"{ability.paper=} {back_face.paper=}"
                        found = True
                        break
                assert found, f"{self=} {ability=} {face=}"

        if ability.is_play:
            assert HasCost.IsType(face), f"{face=}"
            ability.SetPlayCost(face.GetPrintedCostWithRequirement())
        effect = Effect(face, ability, is_temp=is_temp, is_local=is_local, world=world)

        world.event_manager.RegisterEffect(effect)
        return effect

    ################################################################################
    # Move card, will auto reset
    # def MarkDiscard(self, by_effect: 'Effect', ui_group: bool=False) -> bool:
    #     world = self.world

    #     player = self.GetController()
    #     if isinstance(player, Player):
    #         area = player.area_will_discard
    #     else:
    #         area = world.area_will_discard

    #     return self.MoveToArea(area, by_effect, ui_group=ui_group)

    # def MoveToProcessingAreaInternal(self, by_effect: 'Effect', *, ui_group: bool=False) -> bool:
    #     world = self.world

    #     player = self.area.GetOwner()
    #     if isinstance(player, Player):
    #         area = player.area_processing
    #     else:
    #         area = world.area_processing

    #     return self.MoveToArea(area, by_effect, ui_group=ui_group)

    # def MoveToPeekArea(self, by_effect: 'Effect', *, ui_group: bool=False) -> bool:
    #     world = self.world

    #     return self.MoveToArea(world.area_peek, by_effect, ui_group=ui_group)

    def MoveToArea(self, into_area: 'Deck', by_effect: 'Effect',
                    *,
                    up_face: 'CardFace|None'=None,
                    ui_group: bool=False,
                    callback1: Callable[[], None]|None=None,
                    callback2: Callable[[], None]|None=None,
                    target_game_area: 'GameArea|None'=None,
                    index: int=-1
                    ) -> bool:
        message = self.CheckIfCanMove(into_area,
                                    by_effect,
                                    up_face=up_face,
                                    ui_group=ui_group,
                                    callback=callback1,
                                    index=index)
        if message != None and message != False and message != True:
            return self.MoveToAreaInternal(message,
                                    callback=callback2,
                                    target_game_area=target_game_area,
                                    index=message.index)
        return False

    def CheckIfCanMove(self, into_area: 'Deck', by_effect: 'Effect',
                        *,
                        up_face: 'CardFace|None'=None,
                        ui_group: bool=False,
                        callback: Callable[[], None]|None=None,
                        index: int=-1,
                        ) -> 'Message.WhenCardLeavePlay|Message.WhenCardWouldMoveToArea|None|bool':
        from game.message import Message
        from game.effect.rule import GameRule
        
        from_area = self.area
        if up_face == None:
            up_face = self.face

        if self.area == into_area:
            return False

        if not self.GetOwner().is_eliminated and \
            not self.world.is_game_over:
            if not ui_group and \
                not into_area.flags.is_place_card_area and \
                from_area.flags.is_deck and \
                (from_area.GetAll()[-1] != up_face or (not self.IsFaceUp() and into_area.flags.is_face_up) ):
                from_area.MoveToTopAndFlip(self, GameRule(up_face), ui_group=ui_group)
            elif not from_area.flags.is_in_hand and into_area.flags.is_face_up and not self.IsFaceUp() and not ui_group:
                self.Flip(GameRule(up_face))

        message = Message.WhenCardWouldMoveToArea(up_face, from_area, into_area, by_effect, ui_group, index)
        if not up_face.OnWhenCardWouldMoveToArea(message):
            return False

        if self.area == message.into_area:
            return True

        into_area = message.into_area
        self.can_state.Reset()
        self.is_apply_unique_rule = None

        def early_exit():
            self.state.is_leaving_play = False

        if not into_area.flags.is_in_play and from_area.flags.is_in_play:
            self.state.is_leaving_play = True

            would_leave_play_message = Message.WhenCardWouldLeavePlay(
                up_face,
                from_area,
                into_area,
                by_effect,
                False,
                message.index,
            )
            if not up_face.OnWhenCardWouldLeavePlay(would_leave_play_message):
                early_exit()
                return False
        else:
            would_leave_play_message = None

        if callback:
            callback()

        if self.world.is_game_started and into_area.flags.is_in_play:
            if self.world.IsThisUniqueInPlay(up_face):
                self.Discard(by_effect)
                early_exit()
                return False

        leave_play_message = None
        if would_leave_play_message:
            # Fix "32042"
            if self.IsAsOtherCard():
                self.ResetToPrintedCard()
                up_face = self.face

            leave_play_message = Message.WhenCardLeavePlay(up_face, would_leave_play_message)
            if not up_face.OnWhenCardLeavePlay(leave_play_message):
                return False

            # "21139b", Position has been change by effect
            if self.area != from_area:
                return False
            up_face.OnLeavedPlayEnd(by_effect)

        self.state.is_leaving_play = False

        # Fix "16135"
        if into_area.flags.is_boost_area:
            up_face.Reset(False)
        # Fix "01098"
        if into_area.flags.is_dealt_encounter:
            up_face.card.visible.Update()
            # Fix "45140"
            # up_face.Reset(False)
        if into_area.flags.is_in_play and not from_area.flags.is_in_play:
            # Fix "45066" with amplify
            # Fix "39035" with attachment
            if not from_area.flags.is_boost_area and \
                not from_area.flags.is_dealt_encounter and \
                not from_area.flags.is_place_card_area and \
                not from_area.flags.is_revealing:
                up_face.Reset(False)

            if not up_face.OnWouldEnterPlay(into_area):
                return False

        if leave_play_message:
            return leave_play_message
        else:
            return message

    def MoveToAreaInternal(self, leave_play_message: 'Message.WhenCardLeavePlay|Message.WhenCardWouldMoveToArea',
                            *,
                            callback: Callable[[], None]|None=None,
                            target_game_area: 'GameArea|None'=None,
                            index: int=-1) -> bool:
        from game.message import Message

        up_face = leave_play_message.trigger
        into_area = leave_play_message.into_area
        by_effect = leave_play_message.by_effect
        from_area = leave_play_message.from_area
        from_controller = self.GetController()

        self.area.Remove(self)
        into_area.Insert(index, self, target_game_area)

        self.visible.Update()

        if callback:
            callback()

        to_controller = self.GetController()
        if from_area.flags.is_in_play and \
            into_area.flags.is_in_play and \
            from_controller is not to_controller:
            Message.AfterCardControlChanged(
                up_face,
                from_controller,
                to_controller,
                by_effect,
            ).Send()

        if not into_area.flags.is_in_play and from_area.flags.is_in_play:
            # We call this before `AfterCardMoved` for render 21019
            self.ResetReady()

        need_shuffle = from_area.flags.is_deck and from_area.GetSize() == 0

        # after_moved_message = Message.AfterCardMoved(up_face, from_area, into_area, by_shuffle, by_effect, message, ui_group=False)
        # after_moved_message.Send()
        area_before_shuffle = self.area

        if need_shuffle:
            after_deck_runout = Message.AfterDeckRunOut(from_area)
            after_deck_runout.Send()

        if into_area.flags.is_in_hand:
            enter_hand_message = Message.AfterCardEnterHand(up_face, from_area, into_area, by_effect)
            enter_hand_message.Send()

        if area_before_shuffle != into_area:
            return False

        if not into_area.flags.is_in_play and from_area.flags.is_in_play and isinstance(leave_play_message, Message.WhenCardLeavePlay):
            after_leave_message = Message.AfterCardLeavePlay(up_face, from_area, into_area, leave_play_message)
            up_face.OnAfterCardLeavePlay(after_leave_message)
            # Fix surge
            if not from_area.flags.is_obligations_area and not into_area.flags.is_discards and not into_area.flags.is_place_card_area:
                up_face.Reset(False)
        elif into_area.flags.is_in_play and not from_area.flags.is_in_play:
            up_face.ApplyAfterEnterPlay(from_area, into_area, by_effect)

        return True

    # def ShuffleInto(self, deck: 'Deck', by_effect: 'Effect', *, ui_group: bool=False):
    #     self.MoveToAreaInternal(deck, by_effect, by_shuffle=True, ui_group=ui_group)
    #     deck.Shuffle(by_effect)

    # deck only
    def MoveToTop(self, deck: 'Deck', by_effect: 'Effect', *, ui_group: bool=False) -> bool:
        from game.message import Message
        if (deck.flags.is_deck or deck.flags.is_dealt_encounter) and \
            deck.GetTop() != self.face:
            area = self.area
            if area == deck:
                area.Append(self)
            else:
                self.MoveToArea(deck, by_effect, ui_group=ui_group)
            Message.AfterCardMovedToDeck_Text(area, [self.face], "top", by_effect)
            return True
        # self.area.cards.remove(self)
        # self.area.cards.insert(index, self)
        return False

    # deck only
    def MoveToBottom(self, deck: 'Deck', by_effect: 'Effect', *, ui_group: bool=False) -> bool:
        from game.message import Message
        if (deck.flags.is_deck or deck.flags.is_dealt_encounter) and \
            deck.GetBottom() != self.face:
            area = self.area
            if area == deck:
                deck.Insert(0, self)
            else:
                self.MoveToArea(deck, by_effect, ui_group=ui_group, index=0)
            Message.AfterCardMovedToDeck_Text(deck, [self.face], "bottom", by_effect)
            return True
        return False

    ################################################################################
    #
    def ResetReady(self) -> None:
        self.state.is_ready = True

    def Ready(self, by_effect: 'Effect', *, ui_group: bool=False) -> bool:
        from game.message import Message
        if not self.IsReady():
            message = Message.WhenCardWouldReady(self.face, by_effect, ui_group=ui_group)
            message.Send()
            if message.is_be_instead:
                return False
            self.state.is_ready = True
            after_message = Message.AfterCardReady(self.face, by_effect, message, ui_group)
            after_message.Send()
            return True
        return False

    def Exhaust(self, by_effect: 'Effect', *, ui_group: bool=False) -> bool:
        from game.message import Message
        if self.IsReady():
            self.state.is_ready = False
            after_message = Message.AfterCardExhausted(self.face, by_effect, ui_group=ui_group)
            after_message.Send()
            return True
        return False

    def SetAside(self, by_effect: 'Effect', *, ui_group: bool=False) -> bool:
        player = self.GetOwner()
        self.components.OnRemove(by_effect)
        if isinstance(player, Player):
            return self.MoveToArea(player.set_aside_deck, by_effect, ui_group=ui_group)
        else:
            return self.MoveToArea(self.world.aside_deck, by_effect, ui_group=ui_group)

    def Discard(self, by_effect: 'Effect', *, into_area: 'Literal["Owner"]|Deck|None'=None, ui_group: bool=False, up_face: 'CardFace|None'=None) -> bool:
        message, discard_message = self.CheckIfCanDiscard(by_effect, into_area=into_area, ui_group=ui_group, up_face=up_face)

        if message != None and message != False and message != True:
            # mutable container
            after_messages: List[Message.AfterCardDiscard] = []

            def action():
                after_discard_message = Message.AfterCardDiscard(message.trigger, message.from_area, by_effect, discard_message)
                after_messages.append(after_discard_message)

            return_value = self.MoveToAreaInternal(
                message,
                callback=action,
                index=message.index,
            )
            for after_message in after_messages:
                after_message.Send()
            return return_value
        return False

    def CheckIfCanDiscard(self, by_effect: 'Effect', *, into_area: 'Literal["Owner"]|Deck|None'=None, ui_group: bool=False, up_face: 'CardFace|None'=None) -> Tuple['Message.WhenCardLeavePlay|Message.WhenCardWouldMoveToArea|None|bool', Message.WhenCardWouldDiscard]:
        from game.message import Message
        from game.operate.faces import Faces
        if self.IsAsOtherCard():
            self.ResetToPrintedCard()

        if up_face == None:
            up_face = self.face

        from_area = self.area

        discard_message = Message.WhenCardWouldDiscard(up_face, by_effect)
        up_face.OnWhenCardWouldDiscard(discard_message)
        if discard_message.is_be_instead:
            return False, discard_message

        def get_owner_area(owner: 'Player|Scenario'):
            if isinstance(owner, Player):
                return owner.discard_pile
            else:
                return owner.encounter_discard_pile

        if into_area == "Owner":
            player = up_face.GetOwner()
            # Fix "16073b"
            into_area = get_owner_area(player)
        elif into_area != None:
            pass
        elif discard_message.into_area != None:
            into_area = discard_message.into_area
        elif self.bind_discard_pile != None:
            into_area = self.bind_discard_pile
        elif from_area.bind_discard_pile:
            into_area = from_area.bind_discard_pile
        elif EncounterCard.IsType(self.face):
            into_area = get_owner_area(self.owner_original)
        else:
            into_area = get_owner_area(self.owner_internal)

        def action():
            Faces.DiscardAll(up_face.card.components.OnDiscard(by_effect), by_effect, simultaneous=True)
        # all_faces: List['CardFace'] = [self.face] + up_face.card.components.OnDiscard(by_effect)
        # by_effect.world.GetFirstPlayer().ChooseOrder(all_faces, prompt="Simultaneous Discard")

        message = self.CheckIfCanMove(
            into_area,
            by_effect,
            ui_group=ui_group,
            up_face=up_face,
            callback=action
        )
        return message, discard_message

    def IsAsOtherCard(self) -> bool:
        for face in [self.face] + self.back_faces:
            if face not in self.printed_faces:
                return True
        return False

    # ~~TODO: Use Swap~~
    def SetAsCard(self, face: 'TF', back_faces: Sequence['CardFace'] = [], remove_legacy: bool=False) -> 'TF':
        from game.message import Message
        self.state.is_setting_as = True

        message = Message.WhenCardSetAs(self.face, face)
        message.Send()

        if remove_legacy:
            self.printed_faces = [face]
            self.printed_faces += back_faces

        self.face = face
        self.face.card = self

        self.back_faces = []
        self.back_faces += back_faces
        for check_face in back_faces:
            check_face.card = self

        self.state.is_setting_as = False
        assert self.face == face
        return face

    def SwapBackToPrintedCard(self, by_effect: 'Effect') -> 'CardFace':
        self.SwapCardFace(self.printed_faces[0], by_effect)
        return self.face

    def SwapCardFace(self, to_face: 'TF', by_effect: 'Effect', call_reveal: bool=False, no_detach: bool=False) -> 'TF':
        # self.original_face = self.face
        # self.printed_faces = [to_face]

        from_face = self.face
        # Swap the faces
        from_face.OnBeforeSwap(by_effect, to_face, no_detach=no_detach)
        self.face.OnAfterSwap(by_effect, call_reveal)

        # Fix "01066" "21153"
        if not self.face.card.area.flags.is_discards:
            assert self.face == to_face
        return to_face

    def SwapCard(self, to_face: 'CardFace', by_effect: 'Effect', *, is_advance: Villain|None=None) -> 'CardFace':
        from_face = self.face
        to_face_card = to_face.card

        self.printed_faces = [to_face]
        to_face_card.printed_faces = [from_face]

        # Swap the faces
        self.face = to_face
        self.face.card = self

        from_face.card = to_face_card
        to_face_card.face = from_face

        if Villain.IsType(to_face) and Villain.IsType(from_face):
            to_face.SetEncounterDeck(from_face.encounter_deck)

        self.face.OnBeforeSwapOld(by_effect, from_face)
        self.face.OnAfterSwap(by_effect)

        return self.face

    def ResetToPrintedCard(self) -> 'CardFace':
        self.face.Reset(False)
        self.face = self.printed_faces[0]
        self.back_faces = self.printed_faces[1:]
        return self.face

    def GetEffects(self) -> Sequence['Effect']:
        effects: List['Effect'] = []
        for face in [self.face] + self.back_faces:
            effects += face.effects[:]
        return effects

    def Destroy(self):
        self.area.Remove(self)
        assert not self.IsAsOtherCard(), f"{self=}"
        for effect in self.GetEffects():
            self.world.event_manager.UnRegisterEffect(effect)
        self.face.OnAfterDestroy()

    def Flip(self, by_effect: 'Effect', call_reveal: bool=True, *, ui_group: bool=False, ui_look_at: bool=False, by_swapping: bool=False) -> bool:
        from game.message import Message

        self.state.is_flipping = True
        if self.back_faces == []:
            to_face = None
        else:
            to_face = self.back_faces[0]
        # Do `Send.AfterCardLostUpgrade` first
        would_flip = Message.WhenCardWouldFlip(self.face, to_face, by_effect, ui_group, ui_look_at, by_swapping)
        would_flip.Send()
        if would_flip.is_be_instead:
            self.state.is_flipping = False
            return False

        self.face.OnBeforeFlip(by_effect)

        flip_message = Message.WhenCardFlip(self.face, by_effect, would_flip)
        self.face.OnWhenCardFlip(flip_message)

        if not to_face:
            origin_face = None
            self.state.is_face_up = not self.state.is_face_up
        else:
            origin_face = self.face
            self.face = to_face
            self.back_faces.remove(to_face)
            self.back_faces = self.back_faces + [origin_face]

        # if Upgrade.IsType(self.face) and self.face.restricted and self.face.IsInPlay() and self.face.IsFaceUp():
        #     player = self.face.GetControlByPlayer()
        #     player.limit_restricted.CheckLimit([])

        self.face.OnFlip(by_effect, origin_face)
        self.state.is_flipping = False
        self.state.is_revealing = False
        self.face.OnAfterFlip(by_effect, call_reveal)

        self.visible.Update()

        # if Upgrade.IsType(self.face) and self.face.restricted and self.face.IsInPlay() and self.face.IsFaceUp():
        #     player = self.face.GetControlByPlayer()
        #     player.limit_restricted.CheckLimit([])
        if not self.world.is_game_over and self.world.is_game_started:
            after_flip_message = Message.AfterCardFlip(origin_face if origin_face else self.face, self.face, flip_message)
            self.face.OnAfterCardFlip(after_flip_message)
            return True
        return False

    def Render(self) -> 'CardDescriptor':
        from game.card.face.base import Villain

        bind_object_id = 0
        if self.area.bind_card:
            bind_object_id = self.area.bind_card.object_id

        face_down_card_id: List[str] = []
        if self.back_faces:
            face_down_card_id = [x.paper.card_id for x in  self.back_faces]
        else:
            if Evidence.IsType(self.face):
                face_down_card_id = {
                    "Means": ['evidence-back-means'],
                    "Motive": ['evidence-back-motive'],
                    "Opportunity": ['evidence-back-opportunity'],
                }[self.face.subtype]
            elif self.GetOwner().is_scenario:
                if Villain.IsType(self.face):
                    face_down_card_id = ['villain']
                else:
                    face_down_card_id = ['encounter']
            else:
                face_down_card_id = ['player']

        visible_player: List[int] = []
        if self.world.rule.show_all_cards:
            visible_player = [0]
        else:
            for player in self.world.players:
                if self.IsVisible(player):
                    visible_player.append(player.player_id)

        def get_non_forced() -> Sequence['Effect']:
            effects: List['Effect'] = []
            for effect in self.GetEffects():
                if not effect.is_forced and not effect.ability.flags.is_resource and not effect.ability.flags.is_discard_pay:
                    effects.append(effect)
            return effects

        def get_resources() -> Sequence['Effect']:
            effects: List['Effect'] = []
            for effect in self.GetEffects():
                if effect.ability.is_paying:
                    effects.append(effect)
                pass
            return effects

        from engine import Engine

        assert isinstance(self.face, FinalType)

        return CardDescriptor(
            id                  = self.object_id,
            is_ready            = self.IsReady(),
            is_face_up          = self.IsFaceUp(),
            visible_for_players = visible_player,
            bind_object_id      = bind_object_id,
            effect_by_cards     = [x.card.object_id for x in self.face.card.ui.GetEffectedByFaces()],
            effect_to_cards     = [x.card.object_id for x in self.face.card.ui.GetEffectToFaces()],
            game_area           = self.game_area.object_id,
            name                = self.face.name,
            info                = self.face.GetRenderInfo(), # Calc crc here
            traits              = self.face.GetInfoTraits(),
            buffs               = self.face.GetBuffsText(),
            card_id             = self.face.paper.card_id,
            pic_id              = self.face.pic_id,
            down_card_ids       = face_down_card_id,
            effects             = [x.object_id for x in get_non_forced()],
            resources           = [x.object_id for x in get_resources()],
            card_type           = self.face.type_name,
            cost                = self.face.printed_cost.val if HasCost.IsType(self.face) else 0,
            crc                 = self.GetCRC(),
            is_new              = Engine.statistics.IsNew(self.face.paper.card_id),
            is_action           = any(x for x in self.face.effects if x.ability.flags.is_action) #  or x.ability.type.is_resource
        )
