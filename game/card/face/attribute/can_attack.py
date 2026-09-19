from . import *


def _ShouldResolvePiercing(
    calculated_damage: int,
    attack_message: 'Message.WhenUnitWouldAttackUnit',
) -> bool:
    return calculated_damage > 0 and attack_message.IsPiercing()


def _TakeIndirectAttackDamage(
    atk_target: 'Unit2',
    attacker: 'Unit2',
    calculated_damage: int,
    by_effect: 'Effect',
    would_atk_message: 'Message.WhenUnitWouldAttack',
    attack_timing_occurrence: 'TimingOccurrence|None',
):
    if calculated_damage == 0:
        # AssignDamage has nothing to assign in this case, so emit the same
        # presentation-only event used by the standard damage path.
        Message.WhenDamageIsZero_Text(atk_target, attacker, True)

    return atk_target.TakeIndirectDamage(
        attacker,
        calculated_damage,
        by_effect,
        from_atk_message=would_atk_message,
        timing_occurrence=attack_timing_occurrence,
    )


@dataclass
class AttackProperty(PowerProperty):
    additional_boost_card: int = field(default=0) # Only for basic attack
    do_not_give_boost: bool = field(default=False)

    overkill: bool = field(default=False)
    ranged: bool = field(default=False) # ignore retaliate
    lost_ranged: bool = field(default=False)
    piercing: bool = field(default=False) # discard tough
    other_characters_cannot_defend: bool = field(default=False)
    must_defend_with_ally: bool = field(default=False)
    deal_indirect_damage: bool = field(default=False)
    ignore_retaliate: bool = field(default=False)
    lost_piercing: bool = field(default=False)
    attack_in_event: bool = field(default=False) # "08004"
    # An attack repeated during another attack's response window must finish
    # here instead of deferring completion to the original ability.
    resolve_separately: bool = field(default=False)
    divide_damage_among_each_character_attacked_player_control: bool = field(default=False) # "31031"

    against_player: 'Player|None' = field(default=None)

    would_act_message: 'Message.WhenEnemyWouldActivate|None' = field(default=None)

    def HasKeyWord(self):
        return self.overkill or self.ranged or self.piercing

    def GetDamage(self, this: 'CardFace') -> int:
        value = 0
        if self.divided_evenly:
            value = 0
        elif self.is_basic_power:
            if HasAttack.IsType(this):
                value = this.attack
        return self.additional_value + value


def _divide_damage_for_attacked_player(atk_target: 'Unit2', damage: int, by_effect: 'Effect') -> Tuple[List['Unit2'], int, List['Unit2']]:
    attacked_player = atk_target.GetControlByPlayer()
    player_units = attacked_player.GetControlCharacters()
    divide_damage, divide_remainder = Math.DivideEvenly(damage, player_units)
    if divide_remainder:
        remainder_units = attacked_player.AskChooseFaces(
            player_units,
            (divide_remainder, divide_remainder),
            by_effect,
        )
    else:
        remainder_units = []
    return player_units, divide_damage, remainder_units


################################################################################
#
class HasAttack(HasAttribute):
    @override
    def __init__(self, paper: 'Paper') -> None:
        self.base_attack = 0

        self.printed_attack = 0
        self.printed_attack_consequential_damage = 0

        super().__init__(paper)

        def parse(value: str):
            if '*' in value:
                consequential_damage = value.count('*')
                self.printed_attack_consequential_damage = consequential_damage
                value = value.replace('*', '')
            self.printed_attack = int(value)
        self.RegisterAttribute("ATK", parse)
        self.RegisterInfoDict('attack')

    @final
    @property
    def attack(self) -> int:
        from game.buff import BuffUseDefenseForAttackAndThwart
        if self.GetBuff(BuffUseDefenseForAttackAndThwart):
            from game.card.face.attribute.can_defense import HasDefense
            if HasDefense.IsType(self):
                return self.CastTo(HasDefense).defense
            return 0
        # After all active modifiers have been taken into account, if a value is below zero, it is treated as zero: a card cannot have “negative” icons, attributes, traits, cost, or keywords.
        return max(0, self.GetKeyword('ATK'))

    @override
    def OnResetKeywords(self, by_effect: 'Effect'):
        self.base_attack = self.printed_attack
        self.GainAttack(self.base_attack, by_effect)
        return super().OnResetKeywords(by_effect)

    @final
    def GainAttack(self, diff: int, by_effect: 'Effect', *, render_ui: bool=False) -> None:
        self.GainKeyword(diff, 'ATK', by_effect, render_ui=render_ui)

    @final
    def SetBaseAttack(self, value: int, by_effect: 'Effect') -> None:
        if self.base_attack != value:
            diff = value - self.base_attack
            self.base_attack = value
            self.GainAttack(diff, by_effect)

################################################################################
#
class CanAttack(CardFace):

    @staticmethod
    def OnDealDamageInternal(this: 'Unit2|CanAttack', units: List['Unit2'], damage: 'int|DamageProperty', by_effect: 'Effect', *, property: 'AttackProperty|None'=None, attack_in_event: bool) -> int|None:
        has_damage = True

        if attack_in_event or by_effect.ability.is_like_attack:
            if not property:
                property = AttackProperty(is_basic_power=False, attack_in_event=attack_in_event)
            if isinstance(damage, int):
                damage = DamageProperty(damage)
            property.additional_value = damage.damage
            attack_message = CanAttack.SpecialAttack(this, units, by_effect, property=property)
            if attack_message:
                total_damage = attack_message.total_dealt_damage
                has_damage = True
            else:
                total_damage = 0
            if has_damage:
                return total_damage
            else:
                return None
        else:
            # boost damage
            return this.DefaultDealDamageTo(this, units, damage, by_effect)

    @override
    def OnDealDamage(self, units: List['Unit2'], damage: 'int|DamageProperty', by_effect: 'Effect', *, property: 'AttackProperty|None'=None, attack_in_event: bool) -> int|None:
        # Fix "44013"
        # Fix "40038"
        # if not self.IsInPlay():
        #     return None
        return CanAttack.OnDealDamageInternal(self, units, damage, by_effect, property=property, attack_in_event=attack_in_event)

    ################################################################################
    #
    @staticmethod
    def AttackInternal(this: 'Unit2|CanAttack', units: List['Unit2'], by_effect: 'Effect',
                        *, property: 'AttackProperty',
                        if_this_defeat_unit: Callable[['CardFace'], None]|None=None,
                        ) -> Message.AfterUnitAttackEnd|None:
        from game.message import Message
        from game.card.face.base import Unit2
        from game.card.face.attribute.can_boost import CanBoost
        from game.card.face.base import Enemy
        from game.effect.rule import GameRule
        from game.operate.worlds import Worlds
        from game.operate.effects import Effects

        def gain_value_when_divided_for_this_target(gain_value_message: 'Message.WhenUnitBeingAttack|Message.WhenUnitWouldAttackUnit') -> int:
            if gain_value_message.gain_atk > 0 and property.is_divided:
                return gain_value_message.gain_atk
            return 0

        def gain_value_when_divided(gain_value_message: 'Message.WhenUnitWouldAttack'):
            if gain_value_message.gain_atk > 0 and property.is_divided:
                gain_value = gain_value_message.gain_atk
                player = unit.GetControlByPlayer()
                new_added_targets = player.AskChooseFaces(units, (gain_value, gain_value), GameRule(unit), prompt="Assign", repeat_rules="Any")
                for check_unit in new_added_targets:
                    if Unit2.IsType(check_unit):
                        gain_value_message.AddTarget(check_unit)

        is_base_attack = property.is_basic_power
        world = this.card.world
        this = this.card.CastTo(Unit2)

        # Q: If Ebony Maw is prevented from attacking or scheming by a status card, he removes the status gard instead of resolving his activation.
        would_atk_message = Message.WhenUnitWouldAttack(this, units, by_effect, property=property)
        would_atk_message.Send()
        if would_atk_message.is_be_instead:
            return None

        if Enemy.IsType(this):
            activate_message = Message.WhenEnemyActivateAgainstYou(this, property.against_player, by_effect, would_atk_message, property.would_act_message)
            activate_message.Send()
        else:
            activate_message = None

        if is_base_attack:
            unit = this.card.CastTo(Unit2)
            use_basic_power_message = Message.WhenUnitUseBasicPower(unit, "ATK", would_atk_message)
            use_basic_power_message.Send()
        else:
            use_basic_power_message = None

        # We not check for `use_basic_power_message` as it make `would_atk_message` update gain_atk
        # And that's why we check `would_atk_message` after it
        gain_value_when_divided(would_atk_message)

        is_not_delay = activate_message or use_basic_power_message or \
            property.resolve_separately or not by_effect.ability.IsLabel('attack')
        timing_occurrence = (
            world.event_manager.BeginTimingOccurrence()
            if is_not_delay
            else None
        )
        if not is_not_delay and by_effect.context.timing_occurrence == None:
            by_effect.context.timing_occurrence = (
                world.event_manager.BeginTimingOccurrence()
            )
        attack_timing_occurrence = (
            timing_occurrence
            if timing_occurrence != None
            else by_effect.context.timing_occurrence
        )

        attacked_targets: List['CardFace'] = []
        damage_targets: List['Unit2'] = []
        total_dealt_damage = 0
        atk_end_messages: List['Message.AfterUnitAttackUnit|Message.AttackEndsBeforeDamageDealt'] = []

        from game.operate.faces_helper import FacesHelper
        unit_dict = FacesHelper.ListToDict(would_atk_message.attacked_targets)

        divided_rest_damage = this.attack if HasAttack.IsType(this) else 0
        if unit_dict:
            divided_evenly_damage = int(divided_rest_damage / len(unit_dict) + .5)
        else:
            divided_evenly_damage = 0

        temp_effects: List['Effect'] = []
        if if_this_defeat_unit:
            from game.ability.factory import AbilityFactory
            temp_effects += this.effect.RegisterTemp(
                AbilityFactory.AfterUnitDefeatedUnit(
                    AbilityType.Temp0,
                    "This",
                    None,
                    lambda effect, message:
                        if_this_defeat_unit(message.target),
                    is_from_attack=True,
                ),
                unregister_after_exec=False
            )

        basic_defense_messages: List['Message.AfterUnitDefenseInternal'] = []
        attacker_is_defeated = 0

        for target in unit_dict:

            gain_divided_attack = 0

            if not this.IsInPlay():
                break

            this = this.card.CastTo(Unit2)

            if not Unit2.IsType(target):
                continue

            if is_base_attack and not property.do_not_give_boost:
                can_boost = this
                if CanBoost.IsType(can_boost):
                    can_boost.GiveFacedownBoostCardsInternal(can_boost.GetBoostCardNum(would_atk_message) + property.additional_boost_card, GameRule(this), would_atk_message)

            # choose defender
            being_atk_message = Message.WhenUnitBeingAttack(target, would_atk_message)
            being_atk_message.Send()
            gain_divided_attack = gain_value_when_divided_for_this_target(being_atk_message)
            defender = being_atk_message.defender
            defense_messages = being_atk_message.defense_messages
            basic_defense_messages += [x for x in defense_messages if x.use_basic_power_message]

            defense = 0
            if defense_messages and defender:
                for defense_message in defense_messages:
                    defense += defense_message.property.GetDefense(defender)

            attacked_you = None
            def update_atk_target(target: 'Unit2'):
                nonlocal attacked_you
                attacked_you = target.GetControlByOrOwner()
                return target

            if defender:
                atk_target = update_atk_target(defender)
            else:
                atk_target = update_atk_target(target.card.CastTo(Unit2))

            if not this.IsInPlay():
                atk_end_message = Message.AttackEndsBeforeDamageDealt(this, atk_target, being_atk_message)
                atk_end_messages.append(atk_end_message)
                break

            # Put this after check is in play to Fix "27012" vs "01140"
            this = this.card.CastTo(Unit2)

            would_attack_unit_message = Message.WhenUnitWouldAttackUnit(this, atk_target, being_atk_message)
            would_attack_unit_message.Send()
            gain_divided_attack = gain_value_when_divided_for_this_target(would_attack_unit_message)
            atk_target = update_atk_target(would_attack_unit_message.target)

            # If the target of an ally’s basic power leaves play
            # before that ally deals damage equal to its ATK or
            # removes threat equal to its THW, the ally does not
            # take consequential damage
            if atk_target.IsDefeated():
                # Fix "40097"
                # If the defending ally leaves play prior to damage
                # from the attack being dealt, the attack is
                # considered to have no character defending
                if Enemy.IsType(atk_target):
                    continue

            boost_cards: List['CardFace'] = []

            if is_base_attack:
                # We resolve boost first to
                # Fix "27073" attack "27078" as boost
                # assert property.base_value == self.attack

                if CanBoost.IsType(this):
                    def gain_att(face: CardFace, boost_value: int) -> None:
                        attacker = this.card.CastTo(Unit2)
                        nonlocal boost_cards
                        boost_cards.append(face)
                        attacker.GainForThisActive(
                            GameRule(face),
                            would_atk_message,
                            attack=boost_value,
                            render_ui=True
                        )
                    this.ResolveBoostCards(being_atk_message, gain_att)
                    if Worlds.IsGameOver(by_effect):
                        world.event_manager.EndTimingOccurrence(timing_occurrence)
                        return None

                this = this.card.CastTo(Unit2)
                assert CanAttack.IsType(this), f"{this=}"

                if being_atk_message.defender:
                    atk_target = update_atk_target(being_atk_message.defender)

                if defender and defender.IsDefeated():
                    defense = 0
                    atk_target = update_atk_target(target)

            has_keyword_message = Message.CheckIfAttackMessageHasKeyword(would_attack_unit_message, by_effect)
            has_keyword_message.Send()
            Unused(has_keyword_message)

            if would_attack_unit_message.HasKeywords():
                keywords_attack_message = Message.WhenUnitMakeKeyWordAttack(this, would_attack_unit_message)
                keywords_attack_message.Send()

            if is_base_attack:
                this = this.card.CastTo(Unit2)
                if property.is_divided:
                    damage = 1
                elif property.divided_evenly:
                    damage = property.GetDamage(this) + divided_evenly_damage
                    divided_rest_damage -= divided_evenly_damage
                    if divided_rest_damage <= divided_evenly_damage:
                        divided_evenly_damage = divided_rest_damage
                else:
                    damage = property.GetDamage(this)
                value = unit_dict[target] * damage + would_attack_unit_message.temp_additional_value + gain_divided_attack
                recalculate = Message.WhenRecalculateAttackDamage(this, atk_target, value, would_atk_message)
                recalculate.Send()
                calculated_damage = recalculate.will_take_damage
            else:
                calculated_damage = unit_dict[target] * property.GetDamage(this) + would_attack_unit_message.temp_additional_value
                recalculate = Message.WhenRecalculateAttackDamage(this, atk_target, calculated_damage, would_atk_message)
                recalculate.Send()
                calculated_damage = recalculate.will_take_damage

            calculated_damage = max(0, calculated_damage - defense)

            # unit_health = target.health

            excess_damage = 0
            # Piercing only discards tough if the attack would actually deal
            # damage to the attacked character (Rules Reference v1.8).
            if _ShouldResolvePiercing(calculated_damage, would_attack_unit_message):
                if atk_target.IsTough():
                    atk_target.DiscardTough(by_effect, rule="All")

            from game.card.face.card_type import Ally
            from game.card.face.card_type import Minion

            overkill_target = None
            damaged_overkill_target = None
            if would_attack_unit_message.IsOverKill():
                if Minion.IsType(atk_target):
                    overkill_target = Worlds.FindVillain(by_effect)
                elif Ally.IsType(atk_target):
                    overkill_target = atk_target.GetControlByPlayer().GetIdentity()

            took_damage_targets: List['Unit2'] = []

            # Send.WhenUnitAttacksUnit(target, calculated_damage, atk_message)
            if property.deal_indirect_damage:
                #  and atk_target == atk_target.GetControlByPlayer().GetIdentity():
                damage_messages = _TakeIndirectAttackDamage(
                    atk_target,
                    this,
                    calculated_damage,
                    by_effect,
                    would_atk_message,
                    attack_timing_occurrence,
                )
                took_damage = 0
                for damage_message in damage_messages:
                    took_damage += damage_message.took_damage
                    took_damage_targets.append(damage_message.who_took_damage)
            elif property.divide_damage_among_each_character_attacked_player_control and \
                atk_target.GetControlByOrOwner().IsPlayer():
                player_units, divide_damage, remainder_units = _divide_damage_for_attacked_player(
                    atk_target,
                    calculated_damage,
                    by_effect,
                )

                divide_damage_messages: List['Message.AfterUnitDefeatedUnit|Message.AfterUnitTookDamage|None'] = []
                for divide_target in player_units:
                    if divide_target in remainder_units:
                        deal_divide_damage = 1+divide_damage
                    else:
                        deal_divide_damage = divide_damage
                    if deal_divide_damage:
                        divide_damage_messages.append(divide_target.TakeDamage(
                            this,
                            deal_divide_damage,
                            by_effect,
                            timing_occurrence=attack_timing_occurrence,
                        ))

                took_damage = 0
                excess_damage = 0
                for damage_message in divide_damage_messages:
                    if damage_message:
                        took_damage += damage_message.took_damage
                        excess_damage += damage_message.excess_damage
                        if took_damage > 0:
                            took_damage_targets.append(damage_message.who_took_damage)
                    else:
                        took_damage += 0
                        excess_damage += 0
            else:
                # original_health = atk_target.health
                damage_messages = atk_target.TakeDamageWithOverkillTarget(
                    this,
                    calculated_damage,
                    by_effect,
                    would_attack_unit_message,
                    overkill_target,
                    timing_occurrence=attack_timing_occurrence,
                )
                if damage_messages:
                    took_damage = damage_messages[0].took_damage
                    excess_damage = damage_messages[0].excess_damage
                    if took_damage > 0:
                        took_damage_targets.append(damage_messages[0].who_took_damage)
                    damaged_overkill_target = damage_messages[0].damaged_overkill_target
                    if damaged_overkill_target:
                        took_damage_targets.append(damaged_overkill_target)
                else:
                    took_damage = 0
                    excess_damage = 0

            # Fix facedown DRONE
            if atk_target.card.face != atk_target and Unit2.IsType(atk_target.card.face):
                atk_target = update_atk_target(atk_target.card.CastTo(Unit2))

            attacked_targets.append(atk_target)
            total_dealt_damage += calculated_damage

            if is_not_delay:
                if not bool(world.rule.v18_timing):
                    retaliate_message = atk_target.ResolveRetaliate(would_attack_unit_message)
                    attacker_is_defeated += retaliate_message != None and isinstance(retaliate_message, Message.AfterUnitDefeatedUnit)

                if being_atk_message.defense_messages:
                    defend_against_message = Message.AfterUnitDefendEnd(being_atk_message.defense_messages, would_atk_message, calculated_damage, took_damage)
                    defend_against_message.Send()
            else:
                assert being_atk_message.defense_messages == []

            atk_end_message = Message.AfterUnitAttackUnit(this, atk_target, attacked_you, damaged_overkill_target, took_damage_targets, calculated_damage, took_damage, excess_damage, boost_cards, would_attack_unit_message, being_atk_message.defense_messages)
            if is_not_delay:
                atk_end_message.Send()
            atk_end_messages.append(atk_end_message)

            damage_targets += took_damage_targets

        Effects.UnRegister(temp_effects)

        this = this.CastTo(Unit2)
        end_message = Message.AfterUnitAttackEnd(this, attacked_targets, damage_targets, total_dealt_damage, by_effect, atk_end_messages, would_atk_message)

        if is_not_delay:
            end_message.Send()

            if atk_end_messages:
                if activate_message:
                    assert Enemy.IsType(this)
                    after_activate_message = Message.AfterEnemyActivationEnd(this, end_message, activate_message)
                    after_activate_message.Send()

                if use_basic_power_message and \
                    not this.IsDefeated() and \
                    not attacker_is_defeated:
                    unit = this.card.CastTo(Unit2)
                    after_use_basic_power_message = Message.AfterUnitUseBasicPower(unit, "ATK", end_message, use_basic_power_message)
                    after_use_basic_power_message.Send()

                world.stat.RecordAttack(end_message)
            # If an ability triggers after a character uses a basic
            # power, that ability triggers after an attack in which
            # a character made a basic defense resolves.
            for basic_defense_message in basic_defense_messages:
                if basic_defense_message.IsBasicDefense() and basic_defense_message.use_basic_power_message:
                    after_use_def_power_message = Message.AfterUnitUseBasicPower(basic_defense_message.defender, "DEF", basic_defense_message, basic_defense_message.use_basic_power_message)
                    after_use_def_power_message.Send()
            world.event_manager.EndTimingOccurrence(timing_occurrence)
        else:
            # For event cards, or "08004"
            by_effect.context.AddAtkMessage(end_message)
        return end_message

    @staticmethod
    # Cannot use `Filter.FilterByType(units, Unit2)` because of ultron facedown drone
    def GetUnits(units: Sequence['CardFace']) -> List['Unit2']:
        from game.card.face.base import Unit2
        targets: List['Unit2'] = []
        for unit in units:
            target = unit.card.face
            if not Unit2.IsType(target) or target.IsDefeated():
                continue
            targets.append(target)
        return targets

    @staticmethod
    def SpecialAttack(this: 'Unit2|CanAttack', units: Sequence['CardFace'], by_effect: 'Effect', *, property: 'AttackProperty') -> 'Message.AfterUnitAttackEnd|None':
        targets = CanAttack.GetUnits(units)

        message = CanAttack.AttackInternal(this, targets, by_effect, property=property)
        return message

    def BasicAttack(self, units: Sequence['CardFace'], by_effect: 'Effect',
                    *,
                    property: 'AttackProperty|None'=None,
                    if_this_defeat_unit: Callable[['CardFace'], None]|None=None,
                    if_no_character_takes_damage: Callable[[], None]|None=None,
                    if_characters_damaged_by_this: Callable[[List['Unit2']], None|int]|None=None,
                    for_each_damage_dealt_by_this: Callable[[int], None|Any]|None=None,
                    if_no_attack_was_made: Callable[[], None]|None=None,
                    if_unit_defends_against: Callable[['Unit2', int], None]|None=None,
                    if_undefended: Callable[[], None]|None=None,
                    ) -> 'Message.AfterUnitAttackEnd|None':
        if not units:
            if if_no_attack_was_made:
                if_no_attack_was_made()
            return None

        if not self.IsCanAttack(by_effect):
            return None
        if property == None:
            property = AttackProperty(is_basic_power=True)
        else:
            property.is_basic_power = True

        controller = units[0].GetControlBy()
        if Player.IsType(controller):
            property.against_player = controller

        targets = CanAttack.GetUnits(units)

        message = CanAttack.AttackInternal(self, targets, by_effect,
                                            property=property,
                                            if_this_defeat_unit=if_this_defeat_unit,
                                            )

        if if_no_attack_was_made and message == None:
            if_no_attack_was_made()

        if if_no_character_takes_damage and message and message.damaged_targets == []:
            if_no_character_takes_damage()

        if if_characters_damaged_by_this and message:
            if_characters_damaged_by_this(message.damaged_targets)

        if for_each_damage_dealt_by_this and message and message.total_dealt_damage > 0:
            for_each_damage_dealt_by_this(message.total_dealt_damage)

        if if_unit_defends_against and message:
            for attack_message in message.atk_messages:
                if attack_message.defender:
                    if_unit_defends_against(attack_message.defender, attack_message.taken_damage)

        if if_undefended and message:
            for atk_message in message.atk_messages:
                if atk_message.defender == None:
                    if_undefended()

        return message

    def IsCanAttack(self, by_effect: 'Effect') -> bool:
        from game.card.face.base import Unit2

        if not self.IsInPlay():
            return False
        if not Unit2.IsType(self):
            return False
        check_message = Message.CheckIfUnitCanAttack(self, by_effect)
        check_message.Send()
        return check_message.can_attack
