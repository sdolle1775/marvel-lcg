from . import *
from typing import Final

class SenderUnit:
    ################################################################################
    # Unit
    ################################################################################
    class WhenUnitUseBasicPower(TriggerUnitMessage, HasEndEventMessage):
        def __init__(self, this: 'Unit2', power: "CardFace.BASIC_POWER", would_message: 'Message.WhenUnitWouldAttack|Message.WhenUnitWouldDefend|Message.WhenUnitWouldRecovery|Message.WhenUnitWouldScheme|Message.WhenUnitWouldThwart'):
            from game.message import Message
            self.power: Final = power
            self.would_message: Final = would_message
            super().__init__(trigger=this, end_event=Message.AfterUnitUseBasicPower)

        def IsHeroPower(self) -> bool:
            return self.power in ["ATK", "THW", "DEF"]

        def IsAllyPower(self) -> bool:
            return self.power in ["ATK", "THW"]

        def GainValue(self, value: int, by_effect: 'Effect'):
            from game.message import Message
            if isinstance(self.would_message, Message.WhenUnitWouldAttack):
                self.would_message.GainATKForThisAttack(value, by_effect)
            elif isinstance(self.would_message, Message.WhenUnitWouldDefend):
                self.would_message.GainDEFForThisAttack(value, by_effect)
            elif isinstance(self.would_message, Message.WhenUnitWouldRecovery):
                self.would_message.GainRECForThisRecover(value, by_effect)
            elif isinstance(self.would_message, Message.WhenUnitWouldScheme):
                self.would_message.GainSCHForThisScheme(value, by_effect)
            elif isinstance(self.would_message, Message.WhenUnitWouldThwart): # type: ignore
                self.would_message.GainTHWForThisThwart(value, by_effect)
            else:
                assert False, f"{type(self.would_message)=}"

        def AddThatMatchingPower(self, allies: Sequence['CardFace'], by_effect: 'Effect'):
            if self.power in ["ATK", "THW"]:
                for ally in allies:
                    self.would_message.AddMatchingPowerToThisPerformance(ally, by_effect)
                return

            from game.card.face.attribute.can_attack import HasAttack
            from game.card.face.attribute.can_thwart import HasThwart
            value = 0
            for ally in allies:
                if self.power == "ATK":
                    if isinstance(ally, HasAttack):
                        value += ally.attack
                if self.power == "THW":
                    if isinstance(ally, HasThwart):
                        value += ally.thwart
            self.GainValue(value, by_effect)

        def DoesNotTakeConsequentialDamage(self, by_effect: 'Effect'):
            from game.message import Message
            if isinstance(self.would_message, Message.WhenUnitWouldAttack) or isinstance(self.would_message, Message.WhenUnitWouldThwart): 
                self.would_message.DoesNotTakeConsequentialDamage(by_effect)

    class AfterUnitUseBasicPower(TriggerUnitMessage, HasPreEventMessage):
        def __init__(self, this: 'Unit2', power: "CardFace.BASIC_POWER", end_message: 'Message.AfterUnitAttackEnd|Message.AfterUnitDefenseInternal|Message.AfterUnitRecovery|Message.AfterUnitSchemeEnd|Message.AfterUnitThwartEnd', use_message: 'Message.WhenUnitUseBasicPower'):
            self.power: Final = power
            self.end_message: Final = end_message
            super().__init__(trigger=this, pre_message=use_message)

        # def IsHeroPower(self) -> bool:
        #     return self.power in ["Basic Recover", "Basic Attack", "Basic Thwart", "Basic Defense"]

    class WhenUnitBeDefeated(TriggerUnitMessage, AttackerNoneMessage):
        def __init__(self, this: 'Unit2', would_defeated_message: 'Message.WhenUnitWouldBeDefeated', ignore_when_defeated: bool) -> None:
            killer = would_defeated_message.killer
            being_atk_message = would_defeated_message.being_atk_message
            self.killer: Final = killer
            self.would_atk_message: Final = being_atk_message.would_atk_message if being_atk_message else None
            self.by_effect: Final = would_defeated_message.by_effect
            self.excess_damage: Final = this.health * -1
            self.ignore_when_defeated: Final = ignore_when_defeated
            self.add_to_victory_display = False

            def get_defeated_player() -> 'Player|None':
                from game.player import Player
                if self.killer:
                    controller = self.killer.GetControlBy()
                    if Player.IsType(controller):
                        return controller
                return None
            self.defeating_player = get_defeated_player()

            super().__init__(trigger=this, attacker=killer, being_atk_message=being_atk_message)
            if killer:
                text = TransText("{this} was defeated by {killer}", this=this, killer=killer)
            else:
                text = TransText("{this} was defeated", this=this)
            self.Present(text, "", *[x for x in [this, killer] if x and x.IsInPlay()])
            self.AddRelatedFace(this, killer, would_defeated_message.by_effect)

        def IsByConsequential(self) -> bool:
            from game.effect.rule import Consequential
            return type(self.by_effect) is Consequential

        def GetKillerPlayer(self) -> 'Player|None':
            from game.player import Player
            if self.killer:
                player = self.killer.GetControlBy()
                if Player.IsType(player):
                    return player
            return None

        def GetDefeatingPlayer(self) -> 'Player':
            assert self.defeating_player
            return self.defeating_player

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None or self.by_effect.ability.is_like_attack

    class AfterUnitBeDefeated(TriggerUnitMessage, AttackerNoneMessage, HasPreEventMessage):
        def __init__(self, this: 'Unit2', cause: 'CardFace|None', being_atk_message: 'Message.WhenUnitBeingAttack|None', would_defeated_message: 'Message.WhenUnitWouldBeDefeated') -> None:
            self.killer: Final = cause
            self.would_atk_message: Final = being_atk_message.would_atk_message if being_atk_message else None
            self.excess_damage: Final = this.health * -1
            super().__init__(trigger=this, being_atk_message=being_atk_message, pre_message=would_defeated_message)

        def IsByConsequential(self) -> bool:
            from game.effect.rule import Consequential
            return type(self.would_defeated_message.by_effect) is Consequential

        @property
        def would_defeated_message(self) -> 'Message.WhenUnitWouldBeDefeated':
            return self.pre_message

    # DefendAgainstAttack
    # No `CanBeInstead`
    class WhenUnitWouldDefend(TriggerUnitMessage, AttackerMessage, CanGainValueMessage, DefenderMessage):
        def __init__(self, unit: 'Unit2', by_effect: 'Effect', property: 'DefenseProperty', being_atk_message: 'Message.WhenUnitBeingAttack', ) -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            self.being_atk_message: Final = being_atk_message
            self.property: Final = property
            self.would_atk_message: Final = being_atk_message.would_atk_message
            if self.property.additional_value and self.IsBasicDefense():
                value = self.property.additional_value
                self.property.additional_value = 0
                unit.GainForThisActive(by_effect, self.would_atk_message, defense=value)
            super().__init__(trigger=unit, attacker=being_atk_message.attacker, attacked=[unit], defender=unit, would_atk_message=self.would_atk_message, end_event=Message.AfterUnitDefenseInternal)
            text = TransText("{unit} defense against {attacker}", unit=unit, attacker=being_atk_message.attacker)
            self.Present(text, "", unit, being_atk_message.trigger)

        def GainDEFForThisAttack(self, value: int, by_effect: 'Effect'):
            # Fix for "48018", "38016", "03033", "09015"
            # Playing a defense-labeled ability is not a basic defense and does not cause a hero to reduce the amount of damage dealt by that hero’s DEF.
            # assert self.IsBasicDefense()
            self.defender.GainForThisActive(
                by_effect,
                self.would_atk_message,
                defense=value)

        def IsBasicDefense(self):
            return self.property.is_basic_power

        def IfYouTakeNoDamage(self, operation: Callable[[], Any]):
            from game.ability.factory import AbilityFactory
            from game.ability.ability import AbilityType
            assert self.defender != None

            def condition(effect: 'Effect', message: 'Message.AfterUnitAttackEnd') -> bool:
                if self.would_atk_message not in message.would_atk_messages:
                    return False
                for atk_message in message.atk_messages:
                    if self.defender in atk_message.attacked_targets:
                        if self.defender not in atk_message.took_damage_targets:
                            return True
                        if atk_message.taken_damage == 0:
                            return True
                return False

            self.defender.effect.RegisterTemp(
                AbilityFactory.AfterUnitAttackEnd(
                    AbilityType.Temp0,
                    None,
                    lambda effect, message:
                        operation(),
                    conditions=[condition]
                ),
                unregister_after_exec=True,
                until_turn_end=True
            )

        def PreventAllDamage(self, by_effect: 'Effect'):
            from game.ability.factory import AbilityFactory
            from game.ability import AbilityType
            this = by_effect.this

            def action(effect: 'Effect', message: 'Message.WhenUnitWouldTakeDamage') -> None:
                message.PreventDamage("All", by_effect)
            this.effect.RegisterTemp(
                AbilityFactory.WhenUnitWouldTakeDamage(
                    AbilityType.Temp0,
                    None,
                    action,
                    is_from_attack=self.would_atk_message
                ),
                unregister_after_exec=False,
                until_event_end=self.would_atk_message
            )

    class AfterUnitDefenseInternal(TriggerUnitMessage, AttackerMessage, DefenderMessage):
        def __init__(self, unit: 'Unit2', would_def_message: 'Message.WhenUnitWouldDefend', use_basic_power_message: 'Message.WhenUnitUseBasicPower|None') -> None:
            self.property: Final = would_def_message.property
            self.use_basic_power_message: Final = use_basic_power_message
            self.would_def_message = would_def_message
            self.would_atk_message: Final = would_def_message.would_atk_message
            super().__init__(trigger=unit, attacker=would_def_message.attacker, attacked=[unit], defender=unit, would_atk_message=self.would_atk_message, pre_message=would_def_message)

        def IsBasicDefense(self):
            return self.property.is_basic_power

    # AfterUnitDefendAgainstAttack
    class AfterUnitDefendEnd(TriggerUnitMessage, AttackerMessage, DefenderMessage):
        def __init__(self, def_messages: List['Message.AfterUnitDefenseInternal'], would_atk_message: 'Message.WhenUnitWouldAttack', deal_damage: int, took_damage: int) -> None:
            attacker = would_atk_message.attacker
            defender = would_atk_message.defender
            self.would_atk_message: Final = would_atk_message
            self.def_messages: Final = def_messages
            self.would_def_messages: Final = [x.would_def_message for x in def_messages]
            self.dealt_damage: Final = deal_damage
            self.taken_damage: Final = took_damage
            assert defender != None
            super().__init__(trigger=defender, attacker=attacker, attacked=[defender], defender=defender, would_atk_message=would_atk_message)

        def GetDefender(self) -> 'Unit2':
            assert self.defender
            return self.defender

    ################################################################################
    # Health
    class WhenUnitHealHealth(TriggerUnitMessage, HasEndEventMessage):
        def __init__(self, trigger: 'Unit2', value: int, by_effect: 'Effect') -> None:
            from game.message import Message
            self.value: Final = value
            super().__init__(trigger=trigger, end_event=Message.AfterUnitHealHealth)
            self.Present(None, "", trigger, by_effect.this)

    class AfterUnitHealHealth(TriggerUnitMessage, HasPreEventMessage):
        def __init__(self, trigger: 'Unit2', value: int, by_effect: 'Effect', pre_message: 'Message.WhenUnitHealHealth') -> None:
            # from game.message import OnEvent
            self.value: Final = value
            super().__init__(trigger=trigger, pre_message=pre_message)
            text = TransText("{trigger} gains {value}{symbol}", trigger=trigger, value=value, symbol=Symbol.health)
            self.Present(text, "gainlp", trigger, by_effect.this)
            # self.TriggerOnEvent(OnEvent.Health)

    class WhenUnitLossHealth(TriggerUnitMessage, HasEndEventMessage):
        def __init__(self, trigger: 'Unit2', value: int, by_effect: 'Effect') -> None:
            from game.message import Message
            self.value: Final = value
            self.by_effect: Final = by_effect
            super().__init__(trigger=trigger, end_event=Message.AfterUnitLossHealth)
            self.Present(None, "", trigger)

    class AfterUnitLossHealthHelper(Message2):
        def __init__(self, damage_message: 'Message.AfterUnitLossHealth|None', would_take_damage_message: 'Message.WhenUnitWouldTakeDamage', excess_damage: int) -> None:
            self.lost_message: Final = damage_message
            self.excess_damage: Final = excess_damage
            self.would_take_damage_message: Final = would_take_damage_message
            super().__init__(world=would_take_damage_message.world)

    class AfterUnitLossHealth(TriggerUnitMessage, HasPreEventMessage):
        def __init__(self, trigger: 'Unit2', value: int, pre_message: 'Message.WhenUnitLossHealth') -> None:
            # from game.message import OnEvent
            self.value: Final = value
            super().__init__(trigger=trigger, pre_message=pre_message)
            text = TransText("{trigger} lost {value}{symbol}", trigger=trigger, value=value, symbol=Symbol.health)
            self.Present(text, "damage", trigger)
            # self.TriggerOnEvent(OnEvent.Health)

        @property
        def deal_message(self) -> 'Message.WhenUnitLossHealth':
            return self.pre_message

    # No pre message
    class AfterUnitHitPointReset(TriggerUnitMessage):
        def __init__(self, unit: 'Unit2', by_effect: 'Effect') -> None:
            # from game.message import OnEvent
            # ~~~
            # In this time, unit has been remove from the deck, but also isn't in play
            # So, if we render it then, it has no place the be render
            # ~~~
            # We change the order of this, it should work
            super().__init__(trigger=unit)
            if by_effect.this != unit:
                text = TransText("{unit} HP reset ({by_effect})", unit=unit, by_effect=by_effect.this)
            else:
                text = TransText("{unit} HP reset", unit=unit)
            self.Present(text, "", unit)
            # self.TriggerOnEvent(OnEvent.Health)

    # No pre message
    class AfterUnitHitPointSet(TriggerUnitMessage):
        def __init__(self, unit: 'Unit2', by_effect: 'Effect') -> None:
            super().__init__(trigger=unit)
            self.Present(None, "", unit)

    ################################################################################
    # Unit State
    ################################################################################
    class WhenStatusWouldCardPlaceOn(TriggerUnitMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, unit: 'CanStatus', name: "CardFace.STATUS", by_effect: 'Effect') -> None:
            from game.message import Message
            from game.card.face.base import Unit2
            self.status_name: Final = name
            self.by_effect: Final = by_effect
            unit = unit.CastTo(Unit2)
            super().__init__(trigger=unit, end_event=Message.AfterStatusCardPlaceOn)

    class AfterStatusCardPlaceOn(TriggerUnitMessage, HasPreEventMessage):
        def __init__(self, status: 'StatusCard', pre_message: 'Message.WhenStatusWouldCardPlaceOn') -> None:
            # from game.message import OnEvent
            self.status: Final = status
            self.by_effect: Final = pre_message.by_effect
            unit: Final = pre_message.trigger
            super().__init__(trigger=unit, pre_message=pre_message)
            text = TransText("{unit} gained {status} ({by_effect})", unit=unit, status=self.status.symbol_name, by_effect=self.by_effect.this)
            self.Present(text, "set", unit, self.status, self.by_effect.this)
            # self.TriggerOnEvent(OnEvent.Status)

    # No pre message
    class AfterStatusDiscardFrom(TriggerUnitMessage):
        def __init__(self, unit: 'Unit2', status: 'StatusCard', by_effect: 'Effect') -> None:
            # from game.message import OnEvent
            self.status: Final = status
            display_name = {
                'Tough': Symbol.tough,
                'Stunned': Symbol.stunned,
                'Confused': Symbol.confused
            }[status.name]
            super().__init__(trigger=unit)
            text = TransText("{unit} lost {status} ({by_effect})", unit=unit, status=display_name, by_effect=by_effect.this)
            self.Present(text, "", unit, status, by_effect.this)
            # self.TriggerOnEvent(OnEvent.Status)

    ################################################################################
    # Change form
    ################################################################################
    class WhenUnitWouldChangeForm(TriggerUnitMessage, CanBeInstead, HasEndEventMessage):
        def __init__(self, unit: 'Unit2', to_form: 'Unit2', change_additional_form: bool, effect: 'Effect') -> None:
            from game.message import Message
            self.from_form: Final = unit
            self.to_form: Final = to_form
            self.is_change_additional_form: Final = change_additional_form
            self.by_effect: Final = effect
            super().__init__(trigger=unit, end_event=Message.AfterUnitChangeForm)

    class AfterUnitChangeForm(TriggerUnitMessage, HasPreEventMessage, HasEndEventMessage):
        def __init__(self, unit: 'Unit2', to_additional_form: 'CardFace|None', effect: 'Effect', would_change_message: 'Message.WhenUnitWouldChangeForm') -> None:
            from game.message import Message
            # from game.message import OnEvent
            self.to_additional_form: Final = to_additional_form
            super().__init__(trigger=unit, pre_message=would_change_message, end_event=Message.AfterUnitChangeFormEnd)
            # self.TriggerOnEvent(OnEvent.Form)

        @property
        def would_change_message(self) -> 'Message.WhenUnitWouldChangeForm':
            return self.pre_message

    class AfterUnitChangeFormEnd(TriggerUnitMessage, HasPreEventMessage):
        def __init__(self, unit: 'Unit2', effect: 'Effect', after_change_message: 'Message.AfterUnitChangeForm') -> None:
            super().__init__(trigger=unit, pre_message=after_change_message)

        @property
        def after_change_message(self) -> 'Message.AfterUnitChangeForm':
            return self.pre_message

        @property
        def would_change_message(self) -> 'Message.WhenUnitWouldChangeForm':
            return self.after_change_message.would_change_message
