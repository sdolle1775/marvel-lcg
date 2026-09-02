from . import *
from typing import Final

class SenderDamage:
    
    ################################################################################
    # Attack
    class WhenAttackGainKeyword(Message2):
        def __init__(self, keyword: 'CardFace.ATTACK_KEYWORD', by_effect: 'Effect', would_atk_message: 'Message.WhenUnitWouldAttack|Message.CheckIfAttackMessageHasKeyword') -> None:
            self.would_atk_message: Final = would_atk_message
            self.by_effect: Final = by_effect
            self.keyword: Final = keyword
            super().__init__(world=by_effect.world)
            text = TransText("{this} gains {keyword} ({by_effect})", this=would_atk_message.attacker, keyword=keyword, by_effect=by_effect.this)
            self.Present(text, "", by_effect.this)

    class AfterUnitBecomeDefender(TriggerUnitMessage, AttackerMessage):
        def __init__(self, unit: 'Unit2', by_effect: 'Effect', would_atk_message: 'Message.WhenUnitWouldAttack', on_event: 'Message2') -> None:
            self.would_atk_message: Final = would_atk_message
            self.by_effect: Final = by_effect
            # self.on_event: Final = on_event
            super().__init__(trigger=unit, attacker=would_atk_message.attacker, attacked=[unit], would_atk_message=would_atk_message)

    class WhenUnitMakeKeyWordAttack(TriggerUnitMessage, AttackerMessage):
        def __init__(self, attacker: 'Unit2', would_atk_unit_message: 'Message.WhenUnitWouldAttackUnit') -> None:
            self.would_atk_unit_message: Final = would_atk_unit_message
            self.property: Final = would_atk_unit_message.property
            super().__init__(trigger=attacker, attacker=attacker, attacked=would_atk_unit_message.attacked_targets, would_atk_message=would_atk_unit_message.would_atk_message)

        def IsBasicAttack(self) -> bool:
            return self.would_atk_unit_message.IsBasicAttack()

        def DealAdditionalDamage(self, damage: int, by_effect: 'Effect'):
            return self.would_atk_unit_message.IncreaseDamage(damage, by_effect)

    class WhenUnitWouldAttack(TriggerUnitMessage, AttackerMessage, CanGainValueMessage, CanBeInstead):
        def __init__(self, attacker: 'Unit2', targets: List['Unit2'], by_effect: 'Effect', *, property: 'AttackProperty') -> None:
            from game.message import Message
            self.is_base_attack: Final = property.is_basic_power
            self.property = property
            self.by_effect: Final = by_effect
            self.defender: 'Unit2|None' = None
            self.has_declare_defender: bool = False
            self.has_resolves_defense_labeled_ability_internal: 'Player|None' = None

            self.indirect_damage = False
            self.does_not_take_consequential_damage = False
            self.be_prevent = False

            property_text: List[str] = []
            if property.overkill:
                property_text.append(TransText("overkill").text_symbol)
            if property.ranged:
                property_text.append(TransText("ranged").text_symbol)
            if property.piercing:
                property_text.append(TransText("piercing").text_symbol)

            self.has_defeated_target = False

            super().__init__(trigger=attacker, attacker=attacker, attacked=targets, player=self.against_player, would_atk_message=self, end_event=Message.AfterUnitAttackEnd)

            if self.property.additional_value and self.IsBasicAttack():
                damage = self.property.additional_value
                self.property.additional_value = 0
                # self.GainDamage(damage, by_effect)
                attacker.GainForThisActive(by_effect, self, attack=damage)

            if property_text:
                text = TransText("{attacker} will attack {targets} ({additional_value:+}), with ({property})", attacker=attacker, targets=targets, additional_value=property.additional_value, property=", ".join(property_text))
            else:
                text = TransText("{attacker} will attack {targets} ({additional_value:+})", attacker=attacker, targets=targets, additional_value=property.additional_value)
            self.Present(text, "target", attacker, *targets)

            if not attacker.IsInPlay():
                from game.effect.rule import GameRule
                self.SetBeInstead(GameRule(attacker))

        def HasTarget(self, unit: 'CardFace') -> bool:
            return unit.card in [x.card for x in self.attacked_targets]

        # also name add target
        def AlsoResolveThisAttackTo(self, units: Sequence['CardFace']):
            from game.card.face.base import Unit2
            if self.attacker:
                add_units: List[Unit2] = []
                for unit in units:
                    if unit not in self.attacked_targets:
                        if Unit2.IsType(unit):
                            add_units.append(unit)
                self.AddTarget(*add_units)

                text = TransText("Resolve this attack to {units}", units=add_units)
                self.Present_PointTo(text, "target", self.attacker, *units)

        def GainRanged(self, by_effect: 'Effect'):
            if not self.property.ranged:
                from game.message import Message
                self.property.ranged = True
                message = Message.WhenAttackGainKeyword('ranged', by_effect, self)
                message.Send()
        def GainOverKill(self, by_effect: 'Effect'):
            if not self.property.overkill:
                from game.message import Message
                self.property.overkill = True
                message = Message.WhenAttackGainKeyword('overkill', by_effect, self)
                message.Send()
        def GainPiercing(self, by_effect: 'Effect'):
            if not self.property.piercing:
                from game.message import Message
                self.property.piercing = True
                message = Message.WhenAttackGainKeyword('piercing', by_effect, self)
                message.Send()

        def GainATKForThisAttack(self, damage: int, by_effect: 'Effect'):
            assert self.IsBasicAttack()
            self.attacker.GainForThisActive(
                by_effect,
                self,
                attack=damage
            )

        def AddMatchingPowerToThisPerformance(self, face: 'CardFace', by_effect: 'Effect'):
            from game.card.face.attribute.can_attack import HasAttack
            assert self.IsBasicAttack()
            if HasAttack.IsType(face):
                self.GainATKForThisAttack(face.attack, by_effect)

        def DealAdditionalDamage(self, damage: int, by_effect: 'Effect'):
            self.property.additional_value += damage
            text = TransText("{this} gains {damage} additional damage ({by_effect})", this=self.by_effect.this, damage=damage, by_effect=by_effect.this)
            self.Present_Activate(text, by_effect)

        def PreventDamage(self, damage: int|Literal["All"], by_effect: 'Effect'):
            from game.ability.factory import AbilityFactory
            this = self.trigger
            def action(effect: 'Effect', message: 'Message.WhenUnitWouldTakeDamage'):
                message.PreventDamage(damage, by_effect)

            this.effect.RegisterTemp(
                AbilityFactory.WhenUnitWouldTakeDamage(
                    AbilityType.Temp0,
                    None,
                    action,
                    is_from_attack=self
                ),
                unregister_after_exec=True
            )

        def MustDefendWithAlly(self, by_effect: 'Effect'):
            self.property.must_defend_with_ally = True

        def SetDealIndirectDamage(self, by_effect: 'Effect'):
            self.property.deal_indirect_damage = True
            text = TransText("This attack deals indirect damage ({by_effect})", by_effect=by_effect.this)
            self.Present(text, "", by_effect.this)

        def GetDefender(self) -> 'Unit2|None':
            return self.defender

        def DeclareDefender(self, unit: 'Unit2', by_effect: 'Effect'):
            self.DeclareDefenderInternal(unit, by_effect, self, True)

        def DeclareDefenderInternal(self, unit: 'Unit2', by_effect: 'Effect', on_event: 'Message2', set_declare_defender: bool, *, no_send: bool=False):
            from game.message import Message
            from game.card.face.attribute.can_defense import CanDefense
            self.defender = unit
            if set_declare_defender:
                self.has_declare_defender = True
            if not no_send:
                message = Message.AfterUnitBecomeDefender(unit, by_effect, self, on_event)
                message.Send()
            if CanDefense.IsType(unit) and type(on_event) != Message.WhenUnitBeingAttack:
                unit.BasicDefenseLater(self, by_effect)

        def IsBasicAttack(self) -> bool:
            return self.is_base_attack

        def DoesNotTakeConsequentialDamage(self, by_effect: 'Effect'):
            self.does_not_take_consequential_damage = True

        def CancelThisAttack(self, by_effect: 'Effect'):
            self.SetBeInstead(by_effect)

        def IsBePrevent(self) -> bool:
            return self.be_prevent

        def IfThisAttackDealDamage(self, operation: Callable[['Unit2'], Any], by_effect: 'Effect'):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory

            this = by_effect.this
            this.effect.RegisterTemp(
                AbilityFactory.AfterUnitAttackUnitInternal(
                    AbilityType.Temp0UI,
                    None,
                    None,
                    lambda effect, message:
                        operation(message.attacked),
                    dealt_damage=True,
                    conditions=[
                        lambda effect, message:
                            self == message.would_atk_message
                    ],
                ),
                unregister_after_exec=True,
                until_event_end=self
            )

        def IfUnitTakeDamageFromThisAttack(self, operation: Callable[[List['Unit2']], Any], by_effect: 'Effect', *, which_unit: Condition.CARD_TYPE=None):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory

            this = by_effect.this
            this.effect.RegisterTemp(
                AbilityFactory.AfterUnitAttackUnitInternal(
                    AbilityType.Temp0UI,
                    None,
                    None,
                    lambda effect, message:
                        operation(message.took_damage_targets),
                    target_took_damage=True,
                    conditions=[
                        lambda effect, message:
                            self == message.would_atk_message and \
                            Condition.CheckWhichCard(which_unit, message.took_damage_targets, effect)
                    ],
                ),
                unregister_after_exec=True,
                until_event_end=self
            )

        def IfThisAttackDefeats(self, card_type: 'Type[TF]|CardFace', operation: Callable[['Unit2'], Any], by_effect: 'Effect'):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory

            this = by_effect.this
            this.effect.RegisterTemp(
                AbilityFactory.AfterUnitDefeatedUnit(
                    AbilityType.Temp0UI,
                    None,
                    card_type,
                    lambda effect, message:
                        operation(message.target),
                    conditions=[
                        lambda effect, message:
                            self == message.would_atk_message
                    ],
                ),
                unregister_after_exec=False,
                until_event_end=self,
            )

        def IgnoreBoost(self, by_effect: 'Effect', *, icon: bool=False, ability: bool=False):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory

            def action(effect: 'Effect', message: 'Message.WhenBoostCardTurnedFaceUp'):
                if icon:
                    message.CancelAllBoostIcons(by_effect)
                if ability:
                    message.CancelBoostAbility(by_effect)

            this = by_effect.this
            this.effect.RegisterTemp(
                AbilityFactory.WhenBoostCardTurnedFaceUp(
                    AbilityType.Temp0UI,
                    None,
                    action,
                    activate_message=self
                ),
                unregister_after_exec=False,
                until_turn_end=True,
                until_event_end=self
            )

        def GiveAdditionalBoostCardForThisActivation(self, num: int, by_effect: 'Effect'):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory
            self.trigger.effect.RegisterTemp(
                AbilityFactory.WhenEnemyActivateAgainstYou(
                    AbilityType.Temp0,
                    "This",
                    lambda effect, message:
                        message.GiveAdditionalBoostCardForThisActivation(num, by_effect),
                    conditions=[
                        lambda effect, message:
                            self == message.would_message
                    ]
                ),
                unregister_after_exec=True,
                until_phase_end=True,
            )

        def DoSchemeInstead(self, by_effect: 'Effect', operation: Callable[['Message.WhenUnitWouldScheme'], Any]|None=None):
            from game.card.face.base import Enemy
            self.SetBeInstead(by_effect)

            if Enemy.IsType(self.trigger):
                player = self.GetAgainstPlayer()
                self.trigger.DoSchemes(player, by_effect, operation=operation)

        def GetAgainstPlayer(self) -> 'Player':
            assert self.against_player
            return self.against_player

        @property
        def against_player(self) -> 'Player|None':
            return self.property.against_player

        # @override
        # def GetToPlayer(self) -> 'Player':
        #     assert False

    # class FakeWhenUnitWouldAttack(WhenUnitWouldAttack, LikeFakeMessage):
    #     pass

    class WhenUnitBeingAttack(TriggerUnitMessage, AttackerMessage, CanGainValueMessage):
        def __init__(self, trigger: 'Unit2', would_atk_message: 'Message.WhenUnitWouldAttack', **kwargs: Any) -> None:
            attacker: Final = would_atk_message.attacker
            self.would_atk_message: Final = would_atk_message
            self.would_message: Final = would_atk_message
            self.defense_messages: List['Message.AfterUnitDefenseInternal'] = []
            self.by_face: Final = attacker
            super().__init__(trigger=trigger, attacker=attacker, attacked=[trigger], would_atk_message=would_atk_message, **kwargs)
            text = TransText("{trigger} is being attacked by {attacker}", trigger=trigger, attacker=attacker, attacked=[trigger])
            self.Present(text, "target", trigger, attacker)

        def SetDefender(self, unit: 'Unit2|None', defense_message: 'Message.AfterUnitDefenseInternal', by_effect: 'Effect', on_event: 'Message2'):
            self.defense_messages.append(defense_message)
            if unit and self.defender != unit:
                self.DeclareDefenderInternal(unit, by_effect, on_event, False)

        def DeclareDefender(self, unit: 'Unit2', by_effect: 'Effect'):
            from game.card.face.attribute.can_defense import CanDefense
            self.DeclareDefenderInternal(unit, by_effect, self, True)
            if CanDefense.IsType(unit):
                unit.BasicDefense(self, by_effect)

        def DeclareDefenderInternal(self, unit: 'Unit2', by_effect: 'Effect', on_event: 'Message2', set_declare_defender: bool):
            self.would_atk_message.DeclareDefenderInternal(unit, by_effect, on_event, set_declare_defender)

        @property
        def has_declare_defender(self):
            return self.would_atk_message.has_declare_defender

        @property
        def defender(self) -> 'Unit2|None':
            return self.would_atk_message.defender

        def IsBasicAttack(self) -> bool:
            return self.would_atk_message.IsBasicAttack()

        def IsAttack(self) -> bool:
            return True

        def IsScheme(self) -> bool:
            return False

    class WhenUnitWouldAttackUnit(TriggerUnitMessage, AttackerMessage, HasEndEventMessage, CanGainValueMessage, CanBeInstead):
        def __init__(self, attacker: 'Unit2', target: 'Unit2', being_atk_message: 'Message.WhenUnitBeingAttack') -> None:
            from game.message import Message
            self.target = target # who be attacked
            self.being_atk_message: Final = being_atk_message
            would_atk_message = being_atk_message.would_atk_message
            self.property: Final = would_atk_message.property
            self.would_atk_message: Final = would_atk_message
            self.by_effect: Final = would_atk_message.by_effect
            self.temp_overkill = False
            self.temp_piercing = False
            self.temp_ranged = False
            self.temp_additional_value = 0
            super().__init__(trigger=attacker, attacker=attacker, attacked=[target], would_atk_message=self.would_atk_message, end_event=Message.AfterUnitAttackUnit)

        def HasKeywords(self) -> bool:
            return self.IsRanged() or \
                self.IsPiercing() or \
                self.IsOverKill()

        def IsOverKill(self) -> bool:
            return self.temp_overkill or self.property.overkill
        def IsPiercing(self) -> bool:
            return (self.temp_piercing or self.property.piercing) and not self.property.lost_piercing
        def IsRanged(self) -> bool:
            return (self.temp_ranged or self.property.ranged) and not self.property.lost_ranged
        def IsIgnoreRetaliate(self) -> bool:
            return self.property.ignore_retaliate

        def GainOverKill(self, by_effect: 'Effect'):
            if not self.IsOverKill():
                from game.message import Message
                self.temp_overkill = True
                message = Message.WhenAttackGainKeyword('overkill', by_effect, self.would_atk_message)
                message.Send()

        def GainPiercing(self, by_effect: 'Effect'):
            if not self.IsPiercing():
                from game.message import Message
                self.temp_piercing = True
                message = Message.WhenAttackGainKeyword('piercing', by_effect, self.would_atk_message)
                message.Send()

        def GainRanged(self, by_effect: 'Effect'):
            if not self.IsRanged():
                from game.message import Message
                self.temp_ranged = True
                message = Message.WhenAttackGainKeyword('ranged', by_effect, self.would_atk_message)
                message.Send()

        def ChangeTarget(self, unit: 'Unit2', by_effect: 'Effect'):
            self.target = unit
            self.Present_Activate(None, by_effect)

        def IncreaseDamage(self, value: int, by_effect: 'Effect'):
            self.temp_additional_value += value
            self.Present_Activate(None, by_effect)

        # def PreventDamage(self, damage: int|Literal["All"], by_effect: 'Effect'):
        #     from game.ability.factory import AbilityFactory
        #     this = self.trigger
        #     def action(effect: 'Effect', message: 'Message.WhenUnitWouldTakeDamage'):
        #         message.PreventDamage(damage, by_effect)

        #     this.effect.RegisterTemp(
        #         AbilityFactory.WhenUnitWouldTakeDamage(
        #             AbilityType.Temp0,
        #             None,
        #             action,
        #             is_from_attack=self.would_atk_message
        #         ),
        #         unregister_after_exec=True
        #     )

        def IsBasicAttack(self) -> bool:
            return self.property.is_basic_power

        def GainAttackForThisAttack(self, damage: int, by_effect: 'Effect'):
            if self.IsBasicAttack():
                self.attacker.GainForThisActive(by_effect, self, attack=damage)
            else:
                self.property.additional_value += damage
                text = TransText("{this} gains {damage} additional damage ({by_effect})", this=self.by_effect.this, damage=damage, by_effect=by_effect.this)
                self.Present_Activate(text, by_effect)

        def IfThisAttackDefeats(self, targets: Sequence['CardFace'], operation: Callable[['Unit2'], Any]):
            from game.ability.ability import AbilityType
            from game.ability.factory import AbilityFactory

            this = self.by_effect.this
            this.effect.RegisterTemp(
                AbilityFactory.AfterUnitDefeatedUnitInternal(
                    AbilityType.Temp0,
                    None,
                    targets,
                    lambda effect, message:
                        operation(message.target),
                    conditions=[
                        lambda effect, message:
                            self.would_atk_message == message.would_atk_message,
                    ]
                ),
                unregister_after_exec=True,
                until_turn_end=True
            )

        def GiveAdditionalBoostCardForThisActivation(self, num: int, by_effect: 'Effect'):
            from game.card.face.attribute.can_boost import CanBoost
            if CanBoost.IsType(self.attacker):
                self.attacker.GiveFacedownBoostCardsInternal(num, by_effect, self.would_atk_message)

    # class FakeWhenUnitWouldAttackUnit(WhenUnitWouldAttackUnit, LikeFakeMessage):
    #     pass

    class WhenUnitLikeBeingAttack(WhenUnitBeingAttack, LikeFakeMessage, NoSendMessage):
        def __init__(self, trigger: 'Unit2', would_atk_message: 'Message.WhenUnitWouldAttack', bing_atk_message: 'Message.WhenUnitBeingAttack') -> None:
            self.bing_atk_message: Final = bing_atk_message
            super().__init__(trigger=trigger, would_atk_message=would_atk_message)

        @override
        def SetDefender(self, unit: 'Unit2|None', defense_message: 'Message.AfterUnitDefenseInternal', by_effect: 'Effect', on_event: 'Message2'):
            self.bing_atk_message.SetDefender(unit, defense_message, by_effect, on_event)
            return super().SetDefender(unit, defense_message, by_effect, on_event)

    class WhenRecalculateAttackDamage(CalculateMessage, TriggerUnitMessage, AttackerMessage, DefenderNoneMessage, DamageMessage):
        def __init__(self, attacker: 'Unit2', target: 'Unit2', attack: int, would_atk_message: 'Message.WhenUnitWouldAttack') -> None:
            self.target: Final = target # who be attack
            self.would_atk_message: Final = would_atk_message
            # text = TransText("Recalculating {unit}'s attack damage vs {target}")
            # self.Present(text, "", unit, target)
            super().__init__(trigger=attacker, attacker=attacker, attacked=[target], defender=would_atk_message.defender, would_atk_message=would_atk_message, damage=attack)
            # text = TransText("Recalculated damange from {attack} to {damage}")
            # self.Present(text, "", unit)
            self.AddRelatedFace(attacker, target)

        def IncreaseDamage(self, damage: int, by_effect: 'Effect'):
            from game.card.face.base import Unit2
            self.UpdateDamageInternal(damage)
            # text = TransText("this attack gains {value} damage from {by_effect}")
            # self.Present2(text, "activate", this)
            this = self.trigger
            # This update just for UI
            this.CastTo(Unit2).GainForThisActive(by_effect, self.would_atk_message, attack=damage)

    class AfterUnitAttackUnit(TriggerUnitMessage, AttackerMessage, DefenderNoneMessage, TriggerNonePlayerMessage, HasPreEventMessage):
        def __init__(self, attacker: 'Unit2', target: 'Unit2', attacked_you: 'Player|None', overkill_target: 'Unit2|None', took_damage_targets: List['Unit2'], calculated_damage: int, taken_damage: int, excess_damage: int, boost_faces: Sequence['CardFace'], would_atk_unit_message: 'Message.WhenUnitWouldAttackUnit', defense_messages: List['Message.AfterUnitDefenseInternal']) -> None:
            self.dealt_damage: Final = calculated_damage
            self.taken_damage: Final = taken_damage
            self.attacked: Final = target
            self.took_damage_targets: Final = took_damage_targets
            self.excess_damage: Final = excess_damage
            self.boost_faces: Final = boost_faces
            would_atk_message = would_atk_unit_message.would_atk_message
            self.would_atk_message: Final = would_atk_message
            self.defense_messages: Final = defense_messages
            self.has_defeated_target: Final = would_atk_message.has_defeated_target
            self.by_effect: Final = would_atk_message.by_effect
            self.attacked_you: Final = attacked_you
            # Fix "32019" vs "32011" vs "01099"
            # if not self.defeated_target:
            #     assert self.excess_damage <= 0
            # Notify.WaitConfirm(f'{unit} attacked {target}, damage {damage}', unit)
            super().__init__(trigger=attacker, attacker=attacker, attacked=[target], defender=would_atk_message.defender, would_atk_message=would_atk_message, player=would_atk_message.property.against_player, pre_message=would_atk_unit_message)

        @property
        def would_atk_unit_message(self) -> 'Message.WhenUnitWouldAttackUnit':
            return self.pre_message

        @override
        def GetToPlayer(self) -> 'Player':
            from game.player import Player
            if type(self.attacked_you) is Player:
                return self.attacked_you
            else:
                # Hack "44014" "10026"
                from game.operate.worlds import Worlds
                assert self.by_effect.this.paper.card_id == "44014"
                return Worlds.GetCurrentPlayer(self.by_effect)

    # class FakeAfterUnitAttackUnit(AfterUnitAttackUnit, LikeFakeMessage):
    #     pass

    class AttackEndsBeforeDamageDealt(AttackerMessage):
        def __init__(self, attacker: 'Unit2', target: 'Unit2', being_atk_message: 'Message.WhenUnitBeingAttack') -> None:
            self.being_atk_message: Final = being_atk_message
            self.taken_damage: Final = 0
            self.attacked: Final = target
            self.dealt_damage: Final = 0
            self.defender: Final = None
            self.has_defeated_target: Final = False
            self.boost_faces: Sequence['CardFace'] = []
            self.took_damage_targets: Sequence['CardFace'] = []
            self.would_atk_message: Final = being_atk_message.would_atk_message
            super().__init__(attacker=attacker, attacked=[target], would_atk_message=self.would_atk_message)

        @property
        def would_atk_unit_message(self) -> 'None':
            return None

    class AfterUnitAttackEnd(TriggerUnitMessage, AttackerMessage, CanGainValueMessage):
        def __init__(self, attacker: 'Unit2', attacked_targets: Sequence['CardFace'], damage_targets: List['Unit2'], total_dealt_damage: int, by_effect: 'Effect', atk_messages: Sequence['Message.AfterUnitAttackUnit|Message.AttackEndsBeforeDamageDealt'], would_atk_message: 'Message.WhenUnitWouldAttack'):
            # self.targets: Final = targets
            self.by_effect: Final = by_effect
            self.atk_messages: Final = atk_messages
            self.total_dealt_damage: Final = total_dealt_damage
            self.damaged_targets: Final = damage_targets
            super().__init__(trigger=attacker, attacker=attacker, attacked=attacked_targets, would_atk_message=would_atk_message)

        def IsBasicAttack(self) -> bool:
            return len(self.would_atk_messages) == 1 and self.would_atk_messages[0].IsBasicAttack()

        def GetAgainstPlayer(self) -> 'Player|None':
            attacked_players: List['Player'] = []
            for atk_message in self.atk_messages:
                attacked_player = getattr(atk_message, 'attacked_you', None)
                if attacked_player is not None and all(attacked_player is not player for player in attacked_players):
                    attacked_players.append(attacked_player)

            if len(attacked_players) == 1:
                return attacked_players[0]
            if attacked_players:
                return None

            if len(self.would_atk_messages) == 1:
                return self.would_atk_messages[0].property.against_player
            return None

    # class FakeAfterUnitAttackEnd(AfterUnitAttackEnd, LikeFakeMessage):
    #     pass

    class AfterIgnoreKeywordOnCard(TriggerFaceMessage, TargetsMessage):
        def __init__(self, trigger: 'CardFace', targets: Sequence['CardFace'], keyword: 'CardFace.ABILITY_IGNORE_KEY|Literal["Retaliate"]') -> None:
            self.ignore_on_which_face: Final = targets
            self.keyword: Final = keyword
            super().__init__(trigger=trigger, targets=targets)
            text = TransText("{trigger} ignores {keyword} on {targets}", trigger=trigger, keyword=keyword, targets=targets)
            self.Present(text, "", trigger, *targets)

    class IconsActivate_Text(TextMessage):
        def __init__(self,  target: 'CardFace', faces: Sequence['CardFace'], keyword: 'CardFace.ABILITY_IGNORE_KEY|Literal["Retaliate"]') -> None:
            self.target: Final = target
            self.faces: Final = faces
            self.keyword: Final = keyword
            super().__init__(world=faces[0].card.world)
            text = TransText("{faces}'s {keyword} activates", faces=faces, keyword=keyword)
            self.Present(text, "", target, *faces)

    ################################################################################
    # Damage
    class WhenFaceWouldDealDamage(TriggerFaceMessage, AttackerMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, source: 'CardFace', target: 'CardFace', property: 'DamageProperty', by_effect: 'Effect', would_attack_unit_message: 'Message.WhenUnitWouldAttackUnit|None', from_atk_message: 'Message.WhenUnitWouldAttack|None') -> None:
            from game.message import Message
            self.source: Final = source
            self.target: Final = target # who would take damage
            self.property = property
            self.by_effect: Final = by_effect
            being_atk_message = would_attack_unit_message.being_atk_message if would_attack_unit_message else None
            self.would_attack_unit_message: Final = would_attack_unit_message
            self.being_atk_message: Final = being_atk_message
            self.would_atk_message: Final = from_atk_message
            attacker = being_atk_message.attacker if being_atk_message else source
            self.will_deal_damage = property.damage
            super().__init__(trigger=source, attacker=attacker, attacked=[target], would_atk_message=self.would_atk_message, end_event=Message.AfterFaceDealDamage)
            text = TransText("{unit} would deal {damage} damage to {target} ({effect})", unit=source, damage=property.damage, target=target, effect=by_effect.this)
            self.Present(text, "", source, target)
            self.AddRelatedFace(source, target, by_effect)

        def IsOverkill(self) -> bool:
            return self.property.is_from_overkill

        def IncreaseDamage(self, value: int, by_effect: 'Effect') -> None:
            from game.message import Message
            self.property.damage += value
            Message.WhenDamageUpdated_Text(value, by_effect)

        def IsBasicAttack(self) -> bool:
            if self.would_atk_message:
                return self.would_atk_message.IsBasicAttack()
            return False

        def DealThisDamageTo(self, face: 'CardFace', by_effect: 'Effect'):
            self.SetBeInstead(by_effect)
            damage = self.damage
            self.attacker.DealDamage([face], damage, by_effect)

        def PreventDamage(self, damage: int|Literal["All"], by_effect: 'Effect'):
            from game.ability.factory import AbilityFactory
            this = self.trigger
            def action(effect: 'Effect', message: 'Message.WhenUnitWouldTakeDamage'):
                message.PreventDamage(damage, by_effect)

            this.effect.RegisterTemp(
                AbilityFactory.WhenUnitWouldTakeDamage(
                    AbilityType.Temp0,
                    None,
                    action,
                    conditions=[
                        lambda effect, message:
                            message.would_deal_damage_message == self
                    ]
                ),
                unregister_after_exec=True
            )

        @property
        def damage(self) -> int:
            return self.property.damage

    class AfterFaceDealDamage(TriggerFaceMessage, AttackerNoneMessage, HasPreEventMessage):
        def __init__(self, would_deal_damage_message: 'Message.WhenFaceWouldDealDamage', dealt_damage_messages: List['Message.AfterUnitDefeatedUnit|Message.AfterUnitTookDamage'], by_effect: 'Effect') -> None:
            trigger = would_deal_damage_message.trigger
            self.target = would_deal_damage_message.target
            self.dealt_damage_messages: Final = dealt_damage_messages
            being_atk_message = would_deal_damage_message.being_atk_message
            self.by_effect: Final = by_effect
            dealt_damage = 0
            who_took_damage: List['Unit2'] = []
            for dealt_damage_message in dealt_damage_messages:
                dealt_damage += dealt_damage_message.deal_damage
                who_took_damage.append(dealt_damage_message.who_took_damage)
            self.dealt_damage: Final = dealt_damage
            self.who_took_damage: Final = who_took_damage
            self.would_atk_message: Final = would_deal_damage_message.would_atk_message
            super().__init__(trigger=trigger, being_atk_message=being_atk_message, pre_message=would_deal_damage_message)

        @property
        def would_deal_damage_message(self) -> 'Message.WhenFaceWouldDealDamage':
            return self.pre_message

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None

    class WhenPreventAllDamageFromAttack_Text(TextMessage):
        def __init__(self, effect: 'Effect', attacker: 'Unit2|None') -> None:
            super().__init__(world=effect.world)
            if attacker:
                text = TransText("This damage from {attacker}'s attack is prevented ({effect})", attacker=attacker, effect=effect.this)
                self.Present(text, "banished", effect.this)
            else:
                text = TransText("This damage from attack is prevented ({effect})", effect=effect.this)
                self.Present(text, "banished", effect.this)
            pass

    # TODO: Pre message
    class AfterDamageBePrevented(TriggerUnitMessage):
        def __init__(self, who_not_take_damage: 'Unit2', damage: int, property: DamageProperty, effect: 'Effect', would_atk_message: 'Message.WhenUnitWouldAttack|None') -> None:
            self.would_atk_message: Final = would_atk_message
            self.prevent_by_effect: Final = effect
            self.property: Final = property
            self.prevent_damage: Final = damage
            super().__init__(trigger=who_not_take_damage)
            text = TransText("Prevented {damage} of this damage ({effect})", damage=damage, effect=effect.this)
            self.Present(text, "banished", who_not_take_damage, effect.this)

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None

    class WhenDamageIsZero_Text(TextMessage):
        def __init__(self, unit: 'Unit2', source: 'CardFace', do_ui: bool) -> None:
            super().__init__(world=unit.card.world)
            # name = self.name if do_ui else ""
            text = TransText("{source}'s damage to {unit} is 0", source=source, unit=unit)
            self.Present(text, "banished", unit, source)

    class WhenDamageUpdated_Text(TextMessage):
        def __init__(self, diff_value: 'int', by_effect: 'Effect') -> None:
            super().__init__(world=by_effect.world)
            text = TransText("The value of this damage has been updated {diff_value:+} ({by_effect})", diff_value=diff_value, by_effect=by_effect.this)
            self.Present(text, "", by_effect.this)

    class WhenUnitWouldTakeDamage(TriggerUnitMessage, AttackerNoneMessage, DamageMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, unit: 'Unit2', source: 'CardFace', property: DamageProperty, effect: 'Effect', would_deal_damage_message: 'Message.WhenFaceWouldDealDamage') -> None:
            from game.message import Message
            self.source: Final = source
            self.by_effect: Final = effect
            self.would_deal_damage_message: Final = would_deal_damage_message
            self.would_atk_message: Final = would_deal_damage_message.would_atk_message
            being_atk_message = would_deal_damage_message.being_atk_message
            self.cannot_have_more_than_sustained = None
            self.property: Final = property
            self.total_prevent_damage = 0

            if self.would_atk_message:
                if self.would_atk_message.be_prevent:
                    self.PreventAllDamageInternal()
                else:
                    self.be_prevent = False
            else:
                self.be_prevent = False

            super().__init__(trigger=unit, being_atk_message=being_atk_message, damage=None, end_event=Message.AfterUnitTookDamage|Message.AfterUnitDefeatedUnit)
            text = TransText("{unit} will take {damage} damage from {source} ({effect})", unit=unit, damage=self.will_take_damage, source=source, effect=effect.this)
            self.Present(text, "target" if unit != source else "", unit, source)
            self.AddRelatedFace(unit, source, effect)

            if self.will_take_damage == 0 and not self.is_be_instead:
                Message.WhenDamageIsZero_Text(unit, source, False)

        @property
        @override
        def will_take_damage(self) -> int:
            if self.be_prevent:
                return 0
            else:
                return max(0, self.property.damage - self.total_prevent_damage)

        @property
        @override
        def be_dealt_damage(self) -> int:
            return self.property.damage

        @property
        @override
        def overkill_damage(self) -> int:
            if self.be_prevent:
                return self.property.damage - self.total_prevent_damage
            else:
                return 0

        def IsBePrevent(self) -> bool:
            return self.be_prevent

        def IncreaseDamage(self, value: int, by_effect: 'Effect', *, include_overkill: bool=False):
            if not include_overkill and self.IsOverkill():
                return
            assert value >= 0
            from game.message import Message
            self.property.damage += value
            Message.WhenDamageUpdated_Text(value, by_effect)

        def ReduceDamage(self, value: int, by_effect: 'Effect'):
            assert value >= 0 # Fix "24039"
            from game.message import Message
            self.property.damage -= value
            Message.WhenDamageUpdated_Text(-1 * value, by_effect)

        def ReduceDamageTo(self, value: int, by_effect: 'Effect'):
            from game.message import Message
            diff = self.property.damage - value
            self.property.damage = value
            Message.WhenDamageUpdated_Text(-1 * diff, by_effect)

        def PreventAllDamageInternal(self):
            from game.card.face.card_type import Minion
            from game.card.face.card_type import Ally
            if self.would_deal_damage_message.would_attack_unit_message and \
                self.would_deal_damage_message.would_attack_unit_message.IsOverKill() and \
                ( \
                    Minion.IsType(self.trigger) or \
                    Ally.IsType(self.trigger)
                ):
                prevent_damage = min(self.trigger.health, self.will_take_damage)
            else:
                prevent_damage = self.will_take_damage
            self.total_prevent_damage = prevent_damage
            self.be_prevent = True
            return prevent_damage

        def PreventDamage(self, value: int|Literal["All"], by_effect: 'Effect') -> int:
            from game.message import Message
            if value == "All":
                prevent_damage = self.PreventAllDamageInternal()
            else:
                assert value > 0
                prevent_damage = value
                self.total_prevent_damage += value
            from game.message import Message
            message = Message.AfterDamageBePrevented(self.trigger, prevent_damage, self.property, by_effect, self.would_atk_message)
            message.Send()
            return prevent_damage

        def SetCannotTakeMoreThanDamage(self, value: int, by_effect: 'Effect'):
            if value >= 0:
                prevent_damage = self.will_take_damage - value
                if prevent_damage > 0:
                    self.PreventDamage(prevent_damage, by_effect)

        def SetCannotHaveMoreThanSustained(self, value: int, by_effect: 'Effect'):
            assert self.cannot_have_more_than_sustained == None
            self.cannot_have_more_than_sustained = value

        def SetAtLeastHealth(self, value: int, by_effect: 'Effect'):
            assert self.cannot_have_more_than_sustained == None
            value = self.trigger.max_health - value
            self.cannot_have_more_than_sustained = value

        def IsBasicAttack(self) -> bool:
            if self.would_atk_message:
                return self.would_atk_message.IsBasicAttack()
            return False

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None

        def IsOverkill(self) -> bool:
            return self.would_atk_message != None and \
                self.property.is_from_overkill

        def ChangeDealtToTarget(self, target: 'CardFace', by_effect: 'Effect'):
            self.SetBeInstead(by_effect)
            if self.attacker:
                attacker = self.attacker
            else:
                attacker = by_effect.this
            attacker.DealDamage([target], self.will_take_damage, by_effect)

    class WhenUnitWouldBeDefeated(TriggerUnitMessage, AttackerNoneMessage, HasEndEventMessage, CanBeInstead):
        def __init__(self, trigger: 'Unit2', by_effect: 'Effect', killer: 'CardFace|None', being_atk_message: 'Message.WhenUnitBeingAttack|None') -> None:
            from game.message import Message
            self.by_effect: Final = by_effect
            self.killer: Final = killer
            self.being_message: Final = being_atk_message
            super().__init__(trigger=trigger, being_atk_message=being_atk_message, end_event=Message.AfterUnitBeDefeated)

        def IsByConsequentialDamage(self) -> bool:
            from game.effect.rule import Consequential
            return type(self.by_effect) is Consequential

    # class AfterDealDamage(TriggerMessage):
    #     def __init__(self, unit: 'CardFace', targets: List['Unit2'], deal_damage: int, by_effect: 'Effect') -> None:
    #         self.deal_damage: Final = deal_damage
    #         self.by_effect: Final = by_effect
    #         super().__init__(trigger=unit)

    # TODO: Pre message
    # class AfterUnitTakeZerodDamage(TriggerUnitMessage, AttackerMessage, HasPreEventMessage):
    #     def __init__(self, unit: 'Unit2', source: 'CardFace', by_effect: 'Effect', would_take_damage_message: 'Send.WhenUnitWouldTakeDamage', *, excess_damage: int) -> None:
    #         self.took_damage: Final = 0
    #         self.deal_damage: Final = would_take_damage_message.property.damage
    #         self.would_atk_message: Final = would_take_damage_message.would_atk_message
    #         self.source: Final = source
    #         self.by_effect: Final = by_effect
    #         self.excess_damage: Final = excess_damage
    #         attacker = self.would_atk_message.attacker if self.would_atk_message else None
    #         super().__init__(trigger=unit, attacker=attacker, pre_message=would_take_damage_message)

    #     @property
    #     def would_take_damage_message(self) -> 'Send.WhenUnitWouldTakeDamage':
    #         return self.pre_message

    class AfterUnitTookDamage(TriggerUnitMessage, AttackerNoneMessage, HasPreEventMessage):
        def __init__(self, unit: 'Unit2', source: 'CardFace', took_damage: int, by_effect: 'Effect', would_take_damage_message: 'Message.WhenUnitWouldTakeDamage', *, excess_damage: int) -> None:
            self.took_damage: Final = took_damage
            self.deal_damage: Final = would_take_damage_message.property.damage
            self.property: Final = would_take_damage_message.property
            self.would_atk_message: Final = would_take_damage_message.would_atk_message
            self.source: Final = source
            self.by_effect: Final = by_effect
            self.excess_damage: Final = excess_damage
            being_atk_message = would_take_damage_message.being_atk_message
            self.who_took_damage: Final = unit
            self.damaged_overkill_target: Final = None
            super().__init__(trigger=unit, being_atk_message=being_atk_message, pre_message=would_take_damage_message)
            self.AddRelatedFace(unit, unit.card.face, source, by_effect) # Fix "27074"

        @property
        def would_take_damage_message(self) -> 'Message.WhenUnitWouldTakeDamage':
            return self.pre_message

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None

        def IsOverkill(self) -> bool:
            return self.would_atk_message != None and \
                self.property.is_from_overkill

        def IsIndirectDamage(self) -> bool:
            return self.property.is_indirect_damage

        def GetByPlayer(self) -> 'Player|None':
            return self.by_effect.GetInitiator()

    class WhenCalcDealExcessDamage(TriggerFaceMessage, AttackerNoneMessage):
        def __init__(self, killer: 'CardFace', unit: 'Unit2', excess_damage: 'int', by_effect: 'Effect', would_atk_message: 'Message.WhenUnitWouldAttackUnit|None') -> None:
            self.target: Final = unit
            self.would_atk_message: Final = would_atk_message
            self.by_effect: Final = by_effect
            self.excess_damage = excess_damage
            # Render.Print(f'{killer} defeated {unit}', killer)
            being_atk_message = would_atk_message.being_atk_message if would_atk_message else None
            super().__init__(trigger=killer, being_atk_message=being_atk_message)

        def UpdateDamage(self, value: int, by_effect: 'Effect'):
            text = TransText("Excess damage {value:+} ({by_effect})", value=value, by_effect=by_effect.this)
            self.Present_Activate(text, by_effect)
            self.excess_damage += value

        def IncreaseDamage(self, value: int, by_effect: 'Effect'):
            text = TransText("Excess damage {value:+} ({by_effect})", value=value, by_effect=by_effect.this)
            self.Present_Activate(text, by_effect)
            self.excess_damage += value

    class AfterUnitDefeatedUnit(TriggerFaceMessage, AttackerNoneMessage, HasPreEventMessage):
        def __init__(self, killer: 'CardFace', unit: 'Unit2', took_damage: int, excess_damage: 'int', damaged_overkill_target: 'Unit2|None', by_effect: 'Effect', would_take_damage_message: 'Message.WhenUnitWouldTakeDamage') -> None:
            self.target: Final = unit
            self.took_damage: Final = took_damage
            self.deal_damage: Final = would_take_damage_message.property.damage
            self.excess_damage: Final = excess_damage
            self.would_atk_message: Final = would_take_damage_message.would_atk_message
            self.by_effect: Final = by_effect
            # Render.Print(f'{killer} defeated {unit}', killer)
            being_atk_message = would_take_damage_message.being_atk_message
            self.killer = killer
            self.who_took_damage: Final = unit
            self.damaged_overkill_target: Final = damaged_overkill_target
            super().__init__(trigger=killer, being_atk_message=being_atk_message, pre_message=would_take_damage_message)
            self.AddRelatedFace(killer, unit, by_effect)

        @property
        def would_take_damage_message(self) -> 'Message.WhenUnitWouldTakeDamage':
            return self.pre_message

        def GetWouldAtkMessage(self) -> 'Message.WhenUnitWouldAttack':
            assert self.would_atk_message
            return self.would_atk_message

        def IsFromAttack(self) -> bool:
            return self.would_atk_message != None
