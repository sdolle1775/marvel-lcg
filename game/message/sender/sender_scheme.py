from . import *
from typing import Final

class SenderScheme:
    ################################################################################
    # Scheme
    ################################################################################
    class WhenMainSchemeStageWouldBeCompleted(TriggerSchemeMessage, InActivationMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, scheme: 'MainScheme', activate_message: 'Message.WhenUnitWouldScheme|None') -> None:
            from game.message import Message
            super().__init__(trigger=scheme, activate_message=activate_message, end_event=Message.WhenMainSchemeStageCompleted)
            text = TransText("{scheme} would be completed", scheme=scheme)
            self.Present(text, "", scheme)

    class WhenMainSchemeStageCompleted(TriggerSchemeMessage, HasPreEventMessage, HasEndEventMessage):
        def __init__(self, scheme: 'MainScheme', would_messasge: 'Message.WhenMainSchemeStageWouldBeCompleted') -> None:
            from game.message import Message
            super().__init__(trigger=scheme, pre_message=would_messasge, end_event=Message.AfterMainSchemeCompleted)
            text = TransText("{scheme} completed", scheme=scheme)
            self.Present(text, "", scheme)

    class AfterMainSchemeCompleted(TriggerSchemeMessage, HasPreEventMessage):
        def __init__(self, scheme: 'MainScheme', message: 'Message.WhenMainSchemeStageCompleted') -> None:
            super().__init__(trigger=scheme, pre_message=message)

    class WhenMainSchemeWouldAdvance(TriggerSchemeMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, scheme: 'MainScheme', by_effect: 'Effect') -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            super().__init__(trigger=scheme, end_event=Message.AfterMainSchemeAdvanced)
            text = TransText("{scheme} advances", scheme=scheme)
            self.Present(text, "", scheme)

        @property
        def scheme(self) -> 'MainScheme':
            from game.card.face import MainScheme
            return self.private_trigger.CastTo(MainScheme)

    class AfterMainSchemeAdvanced(TriggerSchemeMessage, HasPreEventMessage):
        def __init__(self, message: 'Message.WhenMainSchemeWouldAdvance') -> None:
            # from game.message import OnEvent
            scheme = message.scheme
            self.scheme: Final = scheme
            super().__init__(trigger=scheme, pre_message=message)
            # self.TriggerOnEvent(OnEvent.MainSchemeStage)

    class WhenMainSchemePhaseStart(Message2):
        def __init__(self, world: 'World') -> None:
            super().__init__(world=world)
            text = TransText("Main scheme phase start")
            self.Present(text, "")

    class WhenMainSchemePhaseEnd(Message2):
        def __init__(self, world: 'World') -> None:
            super().__init__(world=world)
            text = TransText("Main scheme phase end")
            self.Present(text, "")

    class CalcMainSchemeEscalation(TriggerSchemeMessage):
        def __init__(self, scheme: 'MainScheme', escalation_threat: int, icons: List['HasAccelerationIcon'], tokens: List['CanAccelerationToken']) -> None:
            for face in icons:
                escalation_threat += face.acceleration_icon
            for face in tokens:
                escalation_threat += face.acceleration_token
            self.escalation_threat = escalation_threat # For "02018b"
            super().__init__(trigger=scheme)
            self.Present(None, "", scheme, *icons, *tokens)

        def UpdateEscalationThreat(self, value: int):
            self.escalation_threat += value

    # class AfterSchemeGainAcceleration(TriggerSchemeMessage):
    #     def __init__(self, scheme: 'Scheme2', num: int) -> None:
    #         text = TransText("{scheme} places {num} acceleration token")
    #         Render.Present(text, "activate", self, scheme)
    #         super().__init__(trigger=scheme)

    class WhenSchemeWouldPlaceThreat(TriggerSchemeMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, scheme: 'Scheme2', value: int, by_effect: 'Effect', sch_message: 'Message.WhenUnitWouldScheme|None') -> None:
            from game.message import Message
            self.value = value
            self.by_effect: Final = by_effect
            self.sch_message: Final = sch_message
            super().__init__(trigger=scheme, end_event=Message.AfterSchemePlaceThreat)
            text = TransText("{scheme} would place {value}{symbol} ({effect})", scheme=scheme, value=value, symbol=Symbol.threat, effect=by_effect)
            self.Present(text, "", scheme, by_effect.this)

        def UpdateValue(self, value: int, by_effect: 'Effect'):
            self.value += value

        def PreventThreat(self, value: int|Literal["All"], by_effect: 'Effect'):
            if value == "All":
                self.value = 0
            else:
                self.UpdateValue(-1 * value, by_effect)

        def ReduceThreat(self, value: int, by_effect: 'Effect'):
            self.UpdateValue(-1 * value, by_effect)

    class AfterSchemePlaceThreat(TriggerSchemeMessage, HasPreEventMessage):
        def __init__(self, scheme: 'Scheme2', value: int, by_effect: 'Effect', would_message: 'Message.WhenSchemeWouldPlaceThreat') -> None:
            # from game.message import OnEvent
            self.value: Final = value
            super().__init__(trigger=scheme, pre_message=would_message)
            text = TransText("{scheme} gained {value}{symbol}", scheme=scheme, value=value, symbol=Symbol.threat)
            self.Present(text, "", scheme, by_effect.this)
            # self.TriggerOnEvent(OnEvent.Threat)

    class WhenSchemeWouldRemoveThreat(TriggerSchemeMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, scheme: 'Scheme2', by_face: 'CardFace', value: int, by_effect: 'Effect', being_thw_message: 'Message.WhenSchemeBeingThwart|None') -> None:
            from game.message import Message
            self.value: Final = value
            self.by_face: Final = by_face
            self.by_effect: Final = by_effect
            self.being_thw_message: Final = being_thw_message
            self.would_thw_message: Final = being_thw_message.would_thw_message if being_thw_message else None
            self.cannot_be_removed = False
            super().__init__(trigger=scheme, end_event=Message.AfterSchemeRemoveThreat)
            text = TransText("{scheme} would remove {value}{symbol}", scheme=scheme, value=value, symbol=Symbol.threat)
            self.Present(text, "", scheme, by_face)

        def SetCannotBeRemoved(self, by_effect: 'Effect'):
            self.cannot_be_removed = True
            text = TransText("Threat cannot be removed from {trigger}", trigger=self.trigger)
            self.Present_ByEffect(text, "activate", self.trigger, by_effect.this)

    class AfterSchemeRemoveThreat(TriggerSchemeMessage, HasPreEventMessage):
        def __init__(self, scheme: 'Scheme2', value: int, by_effect: 'Effect', would_remove_message: 'Message.WhenSchemeWouldRemoveThreat') -> None:
            # from game.message import OnEvent
            self.value: Final = value
            self.would_thw_message: Final = would_remove_message.would_thw_message
            self.by_effect: Final = by_effect
            super().__init__(trigger=scheme, pre_message=would_remove_message)
            if scheme.IsInPlay():
                text = TransText("{scheme} removed {value}{symbol}", scheme=scheme, value=value, symbol=Symbol.threat)
                self.Present(text, "", scheme, by_effect.this)
            # self.TriggerOnEvent(OnEvent.Threat)

        @property
        def would_remove_message(self) -> 'Message.WhenSchemeWouldRemoveThreat':
            return self.pre_message

        def GetByPlayer(self) -> 'Player|None':
            from game.player import Player
            would_sch_message = self.would_thw_message
            if would_sch_message:
                player = would_sch_message.trigger.GetControlByOrOwner()
            else:
                player = self.by_effect.initiator
            if isinstance(player, Player):
                return player
            else:
                return None

    class WhenSchemeWouldBeDefeated(TriggerSchemeMessage, CanBeInstead):
        def __init__(self, scheme: 'Scheme2', by_effect: 'Effect', killer: 'CardFace|None', being_thw_message: 'Message.WhenSchemeBeingThwart|None') -> None:
            self.by_effect: Final = by_effect
            self.killer: Final = killer
            self.being_message: Final = being_thw_message
            super().__init__(trigger=scheme)

    class WhenSchemeBeDefeated(TriggerSchemeMessage, HasEndEventMessage):
        def __init__(self, this: 'Scheme2', would_defeat_message: 'Message.WhenSchemeWouldBeDefeated', ignore_when_defeated: bool) -> None:
            from game.message import Message
            killer = would_defeat_message.killer
            by_effect = would_defeat_message.by_effect
            self.killer: Final = killer if killer else by_effect.this
            self.by_effect: Final = by_effect
            self.ignore_when_defeated: Final = ignore_when_defeated
            self.add_to_victory_display = False
            # player = message.killer.GetController()
            # if cause:
            #     Render.Print(f'{this} was defeated by {by_effect}', this, by_effect.this)
            # else:
            #     Render.Print(f'{this} was defeated', this)
            def get_defeated_player():
                from game.player import Player
                if self.killer:
                    player = self.killer.GetControlBy()
                    if Player.IsType(player):
                        return player
                if self.by_effect:
                    if isinstance(self.by_effect.initiator, Player):
                        return self.by_effect.initiator
            self.defeating_player = get_defeated_player()
            super().__init__(trigger=this, end_event=Message.AfterSchemeBeDefeated)
            text = TransText("{this} was defeated", this=this)
            self.Present(text, "", this, by_effect.this)

        def GetDefeatingPlayer(self) -> 'Player':
            assert self.defeating_player
            return self.defeating_player

    class AfterSchemeBeDefeated(TriggerSchemeMessage, HasPreEventMessage):
        def __init__(self, this: 'Scheme2', by_effect: 'Effect', message: 'Message.WhenSchemeBeDefeated') -> None:
            self.killer: Final = by_effect.this
            super().__init__(trigger=this, pre_message=message)
            text = TransText("{this} was defeated", this=this)
            self.Present(text, "", this, by_effect.this)

    # TODO: Pre message
    class AfterUnitDefeatedScheme(TriggerFaceMessage, ThwarterMessage):
        def __init__(self, killer: 'CardFace', scheme: 'Scheme2', by_effect: 'Effect', *, exact_defeat: bool=False) -> None:
            self.killer: Final = killer
            self.scheme: Final = scheme
            self.by_effect: Final = by_effect
            self.exact_defeat: Final = exact_defeat
            super().__init__(trigger=killer, thwarter=killer, thwarted=[scheme])
            self.AddRelatedFace(killer, scheme, by_effect)
