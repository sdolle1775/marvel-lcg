import types
from typing import Final, TypeAlias
from core import *

from game.card.face import *
from game.effect import *
from game.selector import *
from game.message import *
from game.player import *
from cards.paper import Paper

from game.element.cost import Cost
from game.element.resources import Resources
from game.ability.condition import Condition
from game.ability.condition import Condition2

TARGET_TYPE: TypeAlias = "Type['CardFace']|Sequence['CardFace']|'SELECT.HELPER_TYPE'|'CardFinder'|None"

class Ability:

    LABEL = Literal['attack', 'thwart', 'defense']

    FUNCTION_NAME: TypeAlias = 'Literal["", "Change Form", "DiscardPay", "Ask", "CheckPay", "Play", "CheckThisCanDropPay", "CanGenerateResources", "DoGenerateResources", "AttachToWhenEnterPlay", "ForChoiceAbilityWithCost", "TreatAttachedCardAsMinion", "CheckAllyLimit"]|CardFace.BASIC_POWER'

    def __init__(self,
                 ability_type: 'AbilityType',
                 when: Type[TM],
                 conditions: ConditionsType[TM],
                 operation: OperationType[TM],
                 *,
                 is_local: bool|None=None):
        self.is_initialized = False
        self.name = ""
        self.func_names: Set["Ability.FUNCTION_NAME"] = set()

        from game.ability.ability_ignore import AbilityIgnore

        self.type: Final = ability_type
        self.flags: Final = ability_type.flags
        self.second_type_internal: AbilityType|None = None
        self.priority: Final = self.flags.GetPriority()
        self.ignore = AbilityIgnore(self)

        self.can_work_also_in_hand = False
        self.can_work_only_in_hand = False
        self.any_player_can_trigger_this_when: List[Callable[['Effect'], bool]] = []

        self.labels: List['Ability.LABEL'] = []
        self.when = when
        self.is_choose: Final = self.when == Message.WhenPlayerChooseAbility
        self.is_paying: Final = self.when == Message.WhenPlayerPayingResources
        self.paper: Paper|None = None # Why not save the card face? Because card is dynamic, paper is static

        self.cannot_be_cancel = False
        # Internal marker for rules-reference keyword abilities that only
        # participate in the v1.8 timing workflow.  Legacy reveal checks use
        # this to distinguish printed When Revealed abilities from the v1.8
        # Surge/Incite equivalents.
        self.v18_timing_keyword = False

        # Mandatory bookkeeping that can run at its normal timing priority
        # without asking players to order it against other forced abilities.
        self.resolve_automatically = False

        self.cost_fn: Callable[['Effect', List['CardFace']], Cost]|None = None
        self.play_cost: Cost|None = None

        self.default_choose = False

        self.selectors: List['Selector|None'] = [] # Only use the first one, the others are used to check if it has the legal target, remove "Zero" in range
        self.cost_funcs: List[CostFunc.Base] = []
        self.const_condition: List[Callable[['Effect', when], bool]] = conditions
        self.conditions: List[Callable[['Effect', when], bool]] = conditions

        if is_local == None:
            is_local = False
            for condition in conditions:
                if condition == Condition2.ThisIsTrigger:
                    is_local = True

        self.operation = operation

        # For "30001a", can trigger x times in same event
        self.available_times_fn: Callable[['Effect', 'Message2'], int]|None = None

        from build import Build
        if not Build.release:
            if ability_type == AbilityType.PlayTurnOption:
                assert when == Message.WhenPlayerInTurn, f"{when=}"
            if ability_type in [AbilityType.Action,
                                AbilityType.AlterEgoAction,
                                AbilityType.HeroAction,
                                AbilityType.FirstPlayerAction,]:
                # assert when == Send.WhenPlayerInTurn, f"{when=}"
                pass

        if not Build.release:
            # from inspect import getframeinfo, stack
            # self.callers: List[str] = []
            # for i in range(1, 6):
            #     caller = getframeinfo(stack()[i][0])
            #     self.callers.append(f"{caller[0]}:{caller[1]}")
            pass

        self.is_local: Final = is_local
        self.on_event: 'OnEvent.Base|None' = None

        self.SetName("")

    @property
    def second_type(self) -> AbilityType:
        assert self.second_type_internal != None
        return self.second_type_internal

    @staticmethod
    def GetAbilityTypeCondition(ability_type: 'AbilityType') -> 'ConditionsType[Message2]':
        from game.card.face.card_type import Event
        conditions: ConditionsType[Message2] = []

        ability_type_flags = ability_type.flags
        if ability_type_flags.is_hero_type:
            def player_is_hero(effect: 'Effect', message: 'Message2') -> bool:
                # Quickstrike's printed "Forced Response (hero)" qualifier
                # refers to the player the minion just engaged, not to the
                # encounter card's controller/ability initiator.
                if isinstance(message, Message.AfterMinionEngagePlayer):
                    return message.engaged_player.IsHero()
                return effect.GetInitiator().IsHero()
            conditions.append(player_is_hero)
        if ability_type_flags.is_first_player_type:
            def is_first_player(effect: 'Effect', message: 'Message2') -> bool:
                return effect.GetInitiator().IsFirstPlayer()
            conditions.append(is_first_player)
        if ability_type_flags.is_alterego_type:
            def player_is_alter_ego(effect: 'Effect', message: 'Message2') -> bool:
                return effect.GetInitiator().IsAlterEgo()
            conditions.append(player_is_alter_ego)
        if ability_type_flags.is_delay_ability:
            def is_in_play_or_hand_or_temp_or_delay(effect: 'Effect', message: 'Message2') -> bool:
                # Fix "21123"
                if effect.is_temp:
                    return True
                # Fix "40057"
                if effect.ability.flags.is_delay_ability and \
                    effect.is_local and \
                    effect.ability.ignore.out_of_play:
                    return True
                this = effect.this
                # Fix "12030"
                # Fix ultron_facedown_drone
                if Event.IsType(this):
                    if effect.this.IsLikeInHand():
                        return True
                    elif not this.card.IsOnField():
                        return True
                    else:
                        return False

                return this.IsInPlay() and this.IsFaceUp() or \
                    this.IsInProcessingArea()
            conditions.append(is_in_play_or_hand_or_temp_or_delay)
        return conditions

    def Initialize(self, this: 'CardFace') -> None:
        from game.selector import Select
        from game.card.face.base import Enemy
        from game.card.face.card_type import Event
        from game.card.face.card_type import Ally
        from game.card.face.card_type import Hero
        from game.card.face.card_type import Upgrade

        if self.is_initialized:
            return

        self.is_initialized = True

        when = self.when

        conditions: ConditionsType[when] = []

        if Enemy.IsType(this):
            assert self.selectors == [], f"{this=}"

        def check_sub_type(labels: List['Ability.LABEL'], func_names: List["Ability.FUNCTION_NAME"]) -> bool:
            for label in self.labels:
                assert label in labels, f"{label=} {self=} {this=}"
            for func_name in self.func_names:
                assert func_name in func_names, f"{self.func_names=} {self=} {this=}"
            return True

        # if self.IsPlay():
        #     assert self.type in [AbilityType.PlayTurnOption, AbilityType.HeroAction, AbilityType.Interrupt]
        from build import Build
        if not Build.release and not self.flags.is_choose_ability:
            if self.flags.is_special:
                check_sub_type(['attack', 'thwart'], [])
            elif self.flags.is_discard_pay:
                check_sub_type([], ["DiscardPay", "DoGenerateResources"])
            elif self.flags.is_ask:
                check_sub_type([], ["Ask"])
            elif self.flags.is_play_turn_option:
                check_sub_type([], ["Change Form", "Play"])
            elif self.flags.is_basic_power:
                check_sub_type([], ["REC", "ATK", "THW", "DEF"])
            elif self.flags.IsType(AbilityType.HeroAction):
                check_sub_type(['attack', 'thwart'], ["Play"])
            elif self.flags.IsType(AbilityType.Action):
                check_sub_type(['thwart', 'attack'], ["Play"])
            elif self.flags.IsType(AbilityType.HeroInterrupt):
                check_sub_type(['attack', 'defense', 'thwart'], ["Play"])
            elif self.flags.IsType(AbilityType.Interrupt):
                check_sub_type(['defense', 'thwart'], ["Play", "DoGenerateResources", "DiscardPay"])
            elif self.flags.IsType(AbilityType.Response):
                check_sub_type(['thwart', 'attack'], ["Play"])
            elif self.flags.is_choose_ability:
                check_sub_type(['attack', 'thwart'], [])
            elif self.flags.IsType(AbilityType.HeroResponse):
                check_sub_type(['attack', 'thwart', 'defense'], ["Play"])
            elif self.flags.IsType(AbilityType.DelayAbility):
                pass
            elif self.flags.is_resource:
                check_sub_type([], ["DoGenerateResources"])
            elif self.flags.IsType(AbilityType.CheckResource):
                check_sub_type([], ["CheckPay", "CheckThisCanDropPay", "CanGenerateResources"])
            # elif self.type.is_temp:
            #     pass
            elif self.flags.IsType(AbilityType.AlterEgoAction):
                check_sub_type(['thwart'], ["Play"])
            elif self.is_play:
                check_sub_type([], ["Play"])
            elif self.when == Message.WhenCardPutIntoPlay:
                check_sub_type([], ["AttachToWhenEnterPlay"])
            elif self.when == Message.WhenCardEnterPlay:
                check_sub_type([], ["TreatAttachedCardAsMinion"])
            elif self.when == Message.CheckIfAllyCountLimit:
                check_sub_type([], ["CheckAllyLimit"])
            else:
                check_sub_type([], [])

        if self.is_play:
            def is_like_in_hand(effect: 'Effect', message: 'Message2') -> bool:
                return effect.ability.flags.is_delay_ability or \
                    effect.this.IsLikeInHand()
            conditions.append(is_like_in_hand)

        conditions += Ability.GetAbilityTypeCondition(self.flags.ability_type)

        from game.message import TriggerPlayerMessage, TriggerMessage
        if not self.ignore.game_area and not isinstance(self.on_event, OnEvent.GameArea): # Fix for "11004"
            def check_game_area(effect: 'Effect', message: 'Message2') -> bool:
                # Fix "43021" in Kang stage 2
                if isinstance(message, TriggerPlayerMessage) and message.to_player != None:
                    return effect.this.card.GetGameArea() == message.GetToPlayer().GetGameArea() or \
                        effect.this.card.area.flags.is_removed
                if isinstance(message, TriggerMessage):
                    return effect.this.card.GetGameArea() == message.trigger.card.GetGameArea()
                if isinstance(message, Message.CheckEffectCondition):
                    return effect.this.card.GetGameArea() == message.check_effect.this.card.GetGameArea()
                return True
            conditions = [check_game_area] + conditions
        if self.when == Message.WhenPlayerRevealCard:
            def check_peril(effect: 'Effect', message: 'Message2') -> bool:
                if isinstance(message, TriggerMessage) and \
                    isinstance(message, TriggerPlayerMessage):
                    face = message.trigger
                    from game.card.face.base import EncounterNonVillainCard
                    if EncounterNonVillainCard.IsType(face) and face.IsPeril():
                        return effect.initiator == message.to_player
                return True
            conditions = [check_peril] + conditions

        if self.is_like_defense:
            def can_defense_attack(effect: 'Effect', message: 'Message2') -> bool:
                if isinstance(message, AttackerMessage):
                    attacker = message.attacker
                    if not attacker:
                        # Fix "03005"
                        return True
                    # Comment out this for "21092"
                    # if attacker.IsDefeated():
                    #     return False
                    this = effect.this
                    if Event.IsType(this):
                        unit = effect.GetInitiator().GetIdentity()
                    elif Upgrade.IsType(this):
                        unit = this.GetBindFace()
                        # Hack for "48006"
                        if Enemy.IsType(unit):
                            unit = this.GetOwner().GetRoleCharacter()
                    else:
                        unit = this
                    if isinstance(unit, Ally|Hero):
                        return unit.IsCanDefense(attacker)
                    else:
                        return False
                else:
                    return True
            conditions = [can_defense_attack] + conditions

        self.conditions = conditions + self.conditions

        if self.selectors == [] and \
            not self.default_choose and \
            not self.flags.is_forced and \
            not self.flags.is_choose_ability and \
            not self.flags.is_action and \
            not self.is_play and \
            not self.IsFunction("Change Form", "REC") and \
            self.cost_fn == None:
            # and \
            # self.IsFunction("Change Form", "Basic Recover", "Basic Defense"):
            self.selectors.append(Select.From("This", not_move=True, not_shuffle=True))

        self.code_action: str = f"{self.operation.__code__.co_filename}:{self.operation.__code__.co_firstlineno}"
        self.code_conditions: List[str] = [f"{x.__code__.co_filename}:{x.__code__.co_firstlineno}" for x in self.conditions]

    def SetSecondType(self, ability_type: 'AbilityType') -> 'Ability':
        assert self.flags.ability_type in [AbilityType.CheckResource, AbilityType.DelayAbility]
        self.second_type_internal = ability_type
        return self

    def SetGenerateResourcesExOperation(self, operation: OperationType[Message.WhenPlayerPayingResources]|None=None) -> 'Ability':
        self.generate_resources_ex_operation = operation
        return self

    def SetCost(self, res: 'Cost|Callable[[Effect, List[CardFace]], Cost]', *, is_choose_ability: bool=False) -> 'Ability':
        if not is_choose_ability:
            assert not self.flags.is_choose_ability, f"Call `ForChoiceAbilityWithCost` instead"
        assert res != 0

        if isinstance(res, Cost):
            self.cost_fn = lambda effect, face: res
        else:
            self.cost_fn = res
        return self

    def SetPlayCost(self, cost: 'Cost') -> 'Ability':
        self.play_cost = cost
        return self

    def GetCost(self, effect: 'Effect', targets: List['CardFace']) -> 'Cost':
        if self.flags.is_delay_ability:
            return Cost("0")
        if self.cost_fn and self.play_cost:
            return self.cost_fn(effect, targets) + self.play_cost
        elif self.play_cost:
            return self.play_cost
        elif self.cost_fn:
            return self.cost_fn(effect, targets)
        else:
            assert False, f"Please set `SetCost` `SetPlayCost`"

    def NeedCost(self) -> bool:
        if self.flags.is_delay_ability:
            return False
        return self.cost_fn != None or self.play_cost != None

    def CheckAnyPlayerCanTriggerThis(self, effect: 'Effect') -> bool:
        if self.any_player_can_trigger_this_when:
            for condition in self.any_player_can_trigger_this_when:
                if not condition(effect):
                    return False
            return True
        else:
            return False

    @property
    def is_play(self) -> bool:
        return self.IsFunction("Play")

    ################################################################################
    #
    def SetLabel(self, *labels: 'Ability.LABEL') -> 'Ability':
        # self.sub_types.append(sub_type)
        # += will raise error
        # if sub_type == 'Thwart', add auto `has_threat=True` to TargetSelect
        assert self.selectors == [], f"Please call this before SetTarget"
        assert self.labels == []
        self.labels = list(labels)
        return self

    def IsOneOfLabel(self, label: 'Ability.LABEL|List[Ability.LABEL]') -> bool:
        if isinstance(label, list):
            labels = label
        else:
            labels = [label]
        for check_label in labels:
            if check_label in self.labels:
                return True
        return False

    def IsLabel(self, label: 'Ability.LABEL') -> bool:
        return label in self.labels

    def SetName(self, name: "str") -> 'Ability':
        self.name = name
        return self

    def SetFuncName(self, name: "Ability.FUNCTION_NAME") -> 'Ability':
        if name not in self.func_names:
            self.func_names.add(name)

            if name == "DiscardPay":
                self.CanWorkOnlyInHand()
            if name == "CheckPay":
                self.CanWorkAlsoInHand()
        return self

    def IsFunction(self, *func_names: "Ability.FUNCTION_NAME") -> bool:
        for func_name in func_names:
            if func_name in self.func_names:
                return True
        return False

    ################################################################################
    #
    # def SetIncludeAttack(self) -> 'Ability':
    #     self.include_attack = True
    #     return self

    @property
    def is_like_attack(self) -> bool:
        """
        It will not check Stunned when effect `Action`
        But it will check when `SpecialAttack`
        e.g. "08004" "35009"
        """
        # return self.include_attack or self.is_label_attack or self.IsFunction("ATK")
        return self.is_label_attack or self.IsFunction("ATK")

    @property
    def is_like_thwart(self) -> bool:
        return self.is_label_thwart or self.IsFunction("THW")

    @property
    def is_like_defense(self) -> bool:
        return self.is_label_defense or self.IsFunction("DEF")

    @property
    def is_label_attack(self) -> bool:
        """Has Attack keyword or unit use Attack power"""
        return self.IsLabel('attack')

    @property
    def is_label_thwart(self) -> bool:
        return self.IsLabel('thwart')

    @property
    def is_label_defense(self) -> bool:
        return self.IsLabel('defense')

    ################################################################################
    # TODO: Move to Select?
    def SetIgnoreKeyword(self, *keywords: 'CardFace.ABILITY_IGNORE_KEY', condition: Callable[['Effect'], bool]=lambda effect: True) -> 'Ability':
        for keyword in  keywords:
            self.ignore.keyword[keyword] = condition
        return self

    def SetCondition(self,
                    *,
                    only_if_your_identity_has_trait: "CardFace.TRAITS|None"=None,
                    only_if_your_hero_has_trait: "CardFace.TRAITS|None"=None,
                    hero_form_only: bool=False,
                    alter_ego_form_only: bool=False,
                    only_if_your_identity_has_at_least_printed_hp: int|None=None,
                    only_if_you_control_trait: "CardFace.TRAITS|None"=None,
                    only_if_you_control_3_character_with_trait: "CardFace.TRAITS|None"=None,
                    only_if_you_control_face: 'CardFinder|None'=None,
                    only_if_your_identity_has_one_of_traits: List["CardFace.TRAITS"]|None=None, # or
                    you_have_played_another_card_this_phase: bool|None=None,
                    only_if_there_is_side_scheme_in_victory: bool|None=None,
                    only_if_you_are_in_additional_from: 'Form.FORM_TYPE|None'=None,
                    only_if_you_are_the_player: 'Sequence[str]|None'=None,
                    each_your_characters_has_trait: "CardFace.TRAITS|None"=None,
                    ) -> 'Ability':
        from game.card.card_finder import CardFinder2

        if only_if_your_identity_has_trait == None and \
            hero_form_only == False and \
            alter_ego_form_only == False and \
            only_if_your_identity_has_at_least_printed_hp == None and \
            only_if_you_control_trait == None and \
            only_if_your_identity_has_one_of_traits == []:
            assert self.selectors == [], f"Please call this before SetTarget"

        if only_if_your_identity_has_trait:
            def check_only_if_your_identity_has_trait(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                identity = initiator.GetIdentity()
                return identity.HasTrait(only_if_your_identity_has_trait)
            self.conditions = [check_only_if_your_identity_has_trait] + self.conditions

        if only_if_your_hero_has_trait:
            def check_only_if_your_hero_has_trait(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                if not initiator.IsHero():
                    return False
                identity = initiator.GetIdentity()
                return identity.HasTrait(only_if_your_hero_has_trait)
            self.conditions = [check_only_if_your_hero_has_trait] + self.conditions

        if hero_form_only:
            def check_hero_form_only(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return initiator.IsHero()
            self.conditions = [check_hero_form_only] + self.conditions

        if alter_ego_form_only:
            def check_alter_ego_form_only(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return initiator.IsAlterEgo()
            self.conditions = [check_alter_ego_form_only] + self.conditions

        if only_if_your_identity_has_at_least_printed_hp:
            def check_your_identity_has_at_least_printed_hp(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                printed_health = initiator.GetIdentity().printed_health
                return printed_health >= only_if_your_identity_has_at_least_printed_hp
            self.conditions = [check_your_identity_has_at_least_printed_hp] + self.conditions

        if only_if_you_control_trait:
            def check_if_you_control_one_of_traits(effect: 'Effect', message: 'Message2') -> bool:
                assert only_if_you_control_trait
                initiator = effect.GetInitiator()
                return initiator.IsControl(CardFinder2(only_if_you_control_trait))

            self.conditions = [check_if_you_control_one_of_traits] + self.conditions

        if only_if_you_control_3_character_with_trait:
            def check_only_if_you_control_3_character_with_trait(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return len(initiator.GetControlCards2(CardFinder2(only_if_you_control_3_character_with_trait))) >= 3

            self.conditions = [check_only_if_you_control_3_character_with_trait] + self.conditions

        if only_if_you_control_face:
            def check_only_if_you_control_face(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return initiator.GetIdentity().GetInventoryDeck().FindCard(only_if_you_control_face) != None

            self.conditions = [check_only_if_you_control_face] + self.conditions

        if only_if_your_identity_has_one_of_traits != None:
            def check_if_your_identity_has_one_of_traits(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                identity = initiator.GetIdentity()
                for trait in only_if_your_identity_has_one_of_traits:
                    if identity.HasTrait(trait):
                        return True
                return False
            self.conditions = [check_if_your_identity_has_one_of_traits] + self.conditions

        if you_have_played_another_card_this_phase != None:
            def check_you_have_played_another_card_this_phase(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                first_played_card = initiator.stat.GetThisPhasePlayedCard(0)
                if you_have_played_another_card_this_phase:
                    return first_played_card != None
                else:
                    return first_played_card == None
            self.conditions = [check_you_have_played_another_card_this_phase] + self.conditions

        if only_if_there_is_side_scheme_in_victory != None:
            def check_only_if_there_is_side_scheme_in_victory(effect: 'Effect', message: 'Message2') -> bool:
                from game.card.face.base import SchemeSide2
                side_scheme = effect.world.victory_display.FindCard(card_type=SchemeSide2)
                if only_if_there_is_side_scheme_in_victory:
                    return side_scheme != None
                else:
                    return side_scheme == None
            self.conditions = [check_only_if_there_is_side_scheme_in_victory] + self.conditions

        if only_if_you_are_in_additional_from != None:
            def check_only_if_you_are_in_additionnal_from(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return initiator.form.IsFormInternal(only_if_you_are_in_additional_from)
            self.conditions = [check_only_if_you_are_in_additionnal_from] + self.conditions

        if only_if_you_are_the_player != None:
            def check_only_if_you_are_the_player(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                return initiator.IsName(*only_if_you_are_the_player)
            self.conditions = [check_only_if_you_are_the_player] + self.conditions

        if each_your_characters_has_trait != None:
            def check_each_your_characters_has_trait(effect: 'Effect', message: 'Message2') -> bool:
                initiator = effect.GetInitiator()
                assert each_your_characters_has_trait != None
                return all(x.HasTrait(each_your_characters_has_trait) for x in initiator.GetControlCharacters())
            self.conditions = [check_each_your_characters_has_trait] + self.conditions

        return self

    # Will add `IsLikeInHand`
    def SetPlay(self,
                *,
                only_if_your_identity_has_trait: "CardFace.TRAITS|None"=None,
                only_if_your_hero_has_trait: "CardFace.TRAITS|None"=None,
                hero_form_only: bool=False,
                alter_ego_form_only: bool=False,
                only_if_your_identity_has_at_least_printed_hp: int|None=None,
                only_if_you_control_trait: "CardFace.TRAITS|None"=None,
                only_if_you_control_3_character_with_trait: "CardFace.TRAITS|None"=None,
                only_if_you_control_face: 'CardFinder|None'=None,
                only_if_your_identity_has_one_of_traits: List["CardFace.TRAITS"]|None=None, # or
                you_have_played_another_card_this_phase: bool|None=None,
                only_if_there_is_side_scheme_in_victory: bool|None=None,
                only_if_you_are_in_additional_from: 'Form.FORM_TYPE|None'=None,
                only_if_you_are_the_player: 'Sequence[str]|None'=None,
                ) -> 'Ability':
        self.SetFuncName("Play")
        self.SetCondition(
            only_if_your_identity_has_trait=only_if_your_identity_has_trait,
            only_if_your_hero_has_trait=only_if_your_hero_has_trait,
            hero_form_only=hero_form_only,
            alter_ego_form_only=alter_ego_form_only,
            only_if_your_identity_has_at_least_printed_hp=only_if_your_identity_has_at_least_printed_hp,
            only_if_you_control_trait=only_if_you_control_trait,
            only_if_you_control_3_character_with_trait=only_if_you_control_3_character_with_trait,
            only_if_you_control_face=only_if_you_control_face,
            only_if_your_identity_has_one_of_traits=only_if_your_identity_has_one_of_traits,
            you_have_played_another_card_this_phase=you_have_played_another_card_this_phase,
            only_if_there_is_side_scheme_in_victory=only_if_there_is_side_scheme_in_victory,
            only_if_you_are_in_additional_from=only_if_you_are_in_additional_from,
            only_if_you_are_the_player=only_if_you_are_the_player,
        )
        return self

    def NoOutOfPlayLimit(self) -> 'Ability':
        self.ignore.out_of_play = True
        return self

    def CanWorkAlsoInHand(self) -> 'Ability':
        self.can_work_also_in_hand = True
        return self

    def CanWorkOnlyInHand(self) -> 'Ability':
        self.can_work_only_in_hand = True
        return self

    @property
    def is_ignore_out_of_play(self) -> bool:
        return self.flags.is_ignore_game_area or self.ignore.out_of_play

    # This means the Xth part of this effect doesn't need a target
    # def SetNoTarget3(self) -> 'Ability':
    #     return self.SetTarget2("This") # We will address this later, for now still use `SetTarget2`

    def SetHasNoTargetEffect(self) -> 'Ability':
        return self.SetTarget2("This")

    # This means the 1st part of effect doesn't need a target
    # (this effect can trigger without target)
    def SetNoTarget(self, *, select_this: bool=False) -> 'Ability':
        assert self.selectors == []
        if select_this:
            return self.SetTarget("This")
        else:
            return self.SetTarget(from_where=[])

    # Call `effect.targets2` to get the targets
    def SetTarget2(self, target: 'TARGET_TYPE'=None, is_optional: bool=True, condition: Callable[['Effect'], bool]|None=None, *args: Any, **kwargs: Any) -> 'Ability':
        if self.selectors == []:
            self.SetNoTarget()

        return self.SetTarget(
            target=target,
            is_second_internal=True,
            is_optional=is_optional,
            condition=condition,
            *args, **kwargs,
        )

    # Call `effect.targets2` to get the targets
    def SetTarget3(self, target: 'TARGET_TYPE'=None, is_optional: bool=True, *args: Any, **kwargs: Any) -> 'Ability':
        if self.selectors == []:
            self.SetNoTarget()

        return self.SetTarget(
            target=target,
            is_second_internal=True,
            is_optional=is_optional,
            *args, **kwargs
        )

    # Call `effect.targets` to get the targets
    def SetTarget(self, target: "TARGET_TYPE|Callable[['Effect'], Sequence['CardFace']]"=None,
                *,
                card_type           : Type['TC']|Literal["Ally|Support"]|None=None,     # `target` will overwrite this if it is a card type
                finder              : 'CardFinder|None'=None,   # `target` will overwrite this if it is a finder
                trait               : 'CardFace.TRAITS|None'=None,
                traits              : List['CardFace.TRAITS']|None=None,
                non_trait           : 'CardFace.TRAITS|None'=None,
                card_class          : 'ClassCard.CARD_CLASS|None'=None,
                form                : 'CardFace.FORM|None'=None,
                deck_building_class : 'ClassCard.DECK_BUILDING_CLASS|None'=None,
                has_printed_res     : "Resources.RBYG|None"=None,
                canbe_heal          : bool|None=None,
                sustained           : bool|None=None,
                canbe_stunned       : bool|None=None,
                canbe_tough         : bool|None=None,
                canbe_confused      : bool|None=None,
                canbe_ready         : bool|None=None,
                canbe_exhaust       : bool|None=None,
                canbe_play          : bool|None=None,
                is_confused         : bool|None=None,
                is_stunned          : bool|None=None,
                has_counter         : 'CardFace.COUNTER|Literal["all-purpose"]|None'=None,
                has_threat          : bool|None=None,
                can_place_threat    : bool|None=None,
                has_non_health      : bool|None=None,
                canbe_discard       : bool|None=None,
                canbe_flip          : bool|None=None,
                with_texts          : List[Literal["Hero Action", "Hero Response"]]|None=None,
                with_attach         : 'bool|CardFinder|Type[CardFace]|None'=None,
                not_with_attach     : 'CardFinder|Type[CardFace]|None'=None,
                has_status          : 'CardFace.STATUS|Literal["Any"]'|List['CardFace.STATUS']|None=None, # OR, also filter non-unit
                canbe_status        : 'CardFace.STATUS|Literal["Any"]'|List['CardFace.STATUS']|None=None, # OR
                name                : str|None=None,
                names               : List[str]|None=None,
                non_name            : str|None=None,
                bind_to             : 'CardFinder|CardFace|None'=None,
                engaged_with        : 'CardFinder|Player|None'=None,
                canbe_attach_by     : 'CardFace|None'=None,
                ####
                exclude                         : List['CardFace']|Literal["Trigger", "Attacker", "This", "Targets"]=[],
                another                         : bool|None=None,
                highest_cost                    : bool=False,
                least_threat                    : bool=False,
                share_trait_with_your_hero      : bool=False,
                share_trait_with_your_identity  : bool=False,
                fewest_remaining_hp             : bool=False,
                highest_atk                     : bool=False,
                highest_thw                     : bool=False,
                cost_equal_or_greater           : int|None=None,
                range                           : 'SELECT.RANGE_TYPE'="Default",
                from_where                      : List['SELECT.WHERE']=["Default"],
                combined_printed_cost           : Tuple[int, int]|None=None,
                combined_resource_icons         : Tuple[int, int]|None=None,
                select_rule                     : 'SELECT.RULE'="",
                repeat_rules                    : List['SELECT.REPEAT_RULE']|'SELECT.REPEAT_RULE'=[],
                check_fn                        : Callable[['Effect', 'CardFace'], bool]|None=None,
                by_search                       : bool=False, # will peek
                not_move                        : bool=False,
                not_shuffle                     : bool=False,
                display_in_target_order         : bool=False,
                check_again_fn                  : Callable[['Effect', Sequence['CardFace']], bool]|None=None,

                is_second_internal              : bool=False, # Only for debug
                is_optional                     : bool=True, # Set it to True means when there existed a `SetTarget2`, `SetTarget` will be ignore; Set it to False means both `SetTarget2` and `SetTarget` must have target, will be auto set False if `SetTarget2` is_optional=False
                condition                       : Callable[['Effect'], bool]|None=None, # enable this selector condition
        ) -> 'Ability':
        from game.selector import Select
        from game.card.card_finder import CardFinder
        # from game.card.face.card_face import CardFace
        from game.card.face.base import SchemeSide2
        from game.card.face.base import Scheme2
        from game.card.face.base import Friend
        from game.card.face.base import Villain
        from game.card.face.card_type import Minion
        from game.card.face.card_type import EncounterSideScheme
        from game.card.face.card_type import MainScheme
        from game.card.face.card_type import PlayerSideScheme
        from game.card.face.card_type import Upgrade
        from game.card.face.card_type import Support
        from game.card.face.card_type import Attachment
        from game.card.face.card_type import Environment
        from game.card.face.card_type import Obligation
        from game.card.face.card_type import Ally
        from game.card.face.card_type import Hero
        from game.card.face.card_type import AlterEgo
        from game.card.face.card_type import StatusCard

        if card_type == "Ally|Support":
            card_type = Ally|Support # type: ignore

        if from_where == ["Default"]:
            if target == Minion:                target = "Minion"
            if target == Villain:               target = "Villain"
            if target == EncounterSideScheme:   target = "EncounterSideScheme"
            if target == MainScheme:            target = "MainScheme"
            if target == PlayerSideScheme:      target = "PlayerSideScheme"
            if target == Upgrade:               target = "Upgrade"
            if target == Support:               target = "Support"
            if target == Attachment:            target = "Attachment"
            if target == Environment:           target = "Environment"
            if target == Obligation:            target = "Obligation"
            if target == Ally:                  target = "Ally"
            if target == Hero:                  target = "Hero"
            if target == AlterEgo:              target = "AlterEgo"
            if target == StatusCard:            target = "StatusCard"
            if target == Friend:                target = "Friend"
            if target == Scheme2:               target = "Scheme2"

            if names:
                if "Confused" in names or "Stunned" in names or "Tough" in names:
                    target = "StatusCard"
            if name in ["Confused", "Stunned", "Tough"]:
                target = "StatusCard"

        select_target: SELECT.HELPER_TYPE|None = None
        faces = None

        if isinstance(target, type) or isinstance(target, types.UnionType):
            card_type = Cast(Type, target)
        elif isinstance(target, str):
            select_target = Cast(SELECT.HELPER_TYPE, target)
        elif isinstance(target, list) or isinstance(target, Sequence):
            faces = target
        elif isinstance(target, CardFinder):
            finder = target
        elif isinstance(target, Callable):
            select_target = target

        if can_place_threat:
            has_threat = None
        elif card_type == EncounterSideScheme or \
            card_type == PlayerSideScheme or \
            card_type == MainScheme or \
            card_type == Scheme2 or \
            card_type == SchemeSide2 or \
            target == "EncounterSideScheme" or \
            target == "PlayerSideScheme" or \
            target == "MainScheme" or \
            target == "Scheme2" or \
            target == "SchemeSide2":
            has_threat = True

        if not finder:
            kwargs = {
                'card_type'             : card_type,
                'name'                  : name,
                'names'                 : names,
                'non_name'              : non_name,
                'trait'                 : trait,
                'traits'                : traits,
                'non_trait'             : non_trait,
                'card_class'            : card_class,
                'form'                  : form,
                'deck_building_class'   : deck_building_class,
                'has_printed_res'       : has_printed_res,
                'canbe_heal'            : canbe_heal,
                'sustained'             : sustained,
                'canbe_stunned'         : canbe_stunned,
                'canbe_tough'           : canbe_tough,
                'canbe_confused'        : canbe_confused,
                'is_confused'           : is_confused,
                'is_stunned'            : is_stunned,
                'has_counter'           : has_counter,
                'with_texts'            : with_texts,
                'canbe_ready'           : canbe_ready,
                'canbe_exhaust'         : canbe_exhaust,
                'canbe_play'            : canbe_play,
                'has_threat'            : has_threat,
                'has_non_health'        : has_non_health,
                'canbe_discard'         : canbe_discard,
                'canbe_flip'            : canbe_flip,
                'with_attach'           : with_attach,
                'not_with_attach'       : not_with_attach,
                'has_status'            : has_status,
                'canbe_status'          : canbe_status,
                'bind_to'               : bind_to,
                'engaged_with'          : engaged_with,
                'canbe_attach_by'       : canbe_attach_by,
                'cost_equal_or_greater' : cost_equal_or_greater,
                'check_effect_fn'       : check_fn,
            }
            if [x for x in kwargs.values() if x!=None]:
                finder = CardFinder(**kwargs)

        if not is_second_internal:
            assert self.selectors == []

        selector = None

        selector = Select.From(
            select_target,
            faces=faces,
            finder=finder,
            exclude=exclude,
            another=another,
            highest_cost=highest_cost,
            least_threat=least_threat,
            share_trait_with_your_hero=share_trait_with_your_hero,
            share_trait_with_your_identity=share_trait_with_your_identity,
            fewest_remaining_hp=fewest_remaining_hp,
            highest_atk=highest_atk,
            highest_thw=highest_thw,
            range=range,
            from_where=from_where,
            combined_printed_cost=combined_printed_cost,
            combined_resource_icons=combined_resource_icons,
            select_rule=select_rule,
            repeat_rules=repeat_rules,
            # check_fn=check_fn,
            by_search=by_search,
            not_move=not_move,
            not_shuffle=not_shuffle,
            display_in_target_order=display_in_target_order,
            check_again_fn=check_again_fn
        )
        # return selector

        selector.is_optional = is_optional
        if is_optional == False and is_second_internal:
            assert self.selectors[0]
            self.selectors[0].is_optional = False

        selector.condition = condition
        self.SetTargetInternal(selector)
        return self

    def SetTargetInternal(self, selector: 'Selector') -> 'Ability':
        from game.card.face.base import Scheme2
        from game.card.face.base import Unit2
        from game.card.face.card_type import Ally
        from game.card.face.card_type import Event
        from game.card.face.card_type import Hero
        from game.card.face.card_type import AlterEgo
        from game.card.face.card_type import Upgrade

        # assert self.selectors == []
        self.selectors.append(selector)
        if len(self.selectors) != 1:
            return self

        last_selector = self.selectors[-1]
        assert last_selector
        if last_selector.target_text == "TeamUp":
            return self

        # Only apply for first selector
        if self.is_like_attack:
            def can_be_attack_units(effect: 'Effect', target: 'CardFace') -> bool:
                if Unit2.IsType(target):
                    if target.IsDefeated():
                        return False
                    this = effect.this
                    if not Unit2.IsType(this):
                        assert Event.IsType(this) or Upgrade.IsType(this), f"{type(this)=}"
                    # Fix "54035"
                    if target.IsConsiderAs(card_type=Unit2):
                        return True
                    return target.CanBeAttackBy(effect)
                return True # Fix 18020
            last_selector.selector_filter.AddParameter(check_effect_fn=can_be_attack_units)

        if self.is_like_thwart:
            # Fix "01085"
            # assert self.select_fn, f"{self=}"
            def can_be_thwart_schemes(effect: 'Effect', target: 'CardFace') -> bool:
                if Scheme2.IsType(target):
                    if target.threat <= 0 or target.IsDefeated():
                        return False
                    # initiator = effect.GetInitiator()
                    this = effect.this
                    if isinstance(this, Ally|Hero|AlterEgo):
                        return target.CanBeThwartBy(effect)
                    else:
                        assert Event.IsType(this) or Upgrade.IsType(this), f"{type(this)=}"
                        return target.CanBeThwartBy(effect)
                return True
            last_selector.selector_filter.AddParameter(check_effect_fn=can_be_thwart_schemes)

        if self.is_play:

            # def max_per_unit(effect: 'Effect', target: 'CardFace') -> bool:
            #     this = effect.this
            #     if Upgrade.IsType(this) or Support.IsType(this):
            #         if target.IsDefeated():
            #             return True # Fix "45017"
            #         this = effect.this
            #         if Upgrade.IsType(this):
            #             return this.max_per_unit > target.GetUpgradeDeck().HasThisType(this)
            #         elif Support.IsType(this):
            #             return this.max_per_unit > target.GetControlByPlayer().supports.HasThisType(this)
            #         return True
            #     return True

            # self.selector.check_fns.append(max_per_unit)

            # "32013" Max 1 TRAINING upgrade per ally.
            def filter_training_upgrade_per_ally(effect: 'Effect', face: 'CardFace') -> bool:
                from game.card.card_finder import CardFinder2
                this = effect.this
                if Upgrade.IsType(this):
                    if not Ally.IsType(face):
                        return True
                    if not effect.this.HasTrait('TRAINING'):
                        return True
                    else:
                        return face.GetInventoryDeck().FindCardSize(CardFinder2("TRAINING", Upgrade)) == 0
                return True

            last_selector.selector_filter.AddParameter(check_effect_fn=filter_training_upgrade_per_ally)

        return self

    def SetCostFunc(self, cost_func: 'CostFunc.Base') -> 'Ability':
        self.cost_funcs.append(cost_func)
        return self

    def SetDefault(self) -> 'Ability':
        assert self.is_choose, f"{self.when=}"
        assert self.flags.is_choose_ability, f"{self.flags=}"
        self.default_choose = True
        return self

    def LimitOncePerRound(self) -> 'Ability':
        self.conditions = [Condition.LimitOncePerRound] + self.conditions
        return self

    def MaxOnePerRound(self):
        return self.LimitOncePerRound()

    def MaxOnePerPhase(self):
        return self.LimitOncePerPhase()

    def LimitOncePerRoundPerPlayer(self) -> 'Ability':
        self.conditions = [Condition.LimitOncePerRoundPerPlayer] + self.conditions
        return self

    def LimitOncePerPhasePerPlayer(self) -> 'Ability':
        self.conditions = [Condition.LimitOncePerPhasePerPlayer] + self.conditions
        return self

    def LimitOncePerPhase(self) -> 'Ability':
        self.conditions = [Condition.LimitOncePerPhase] + self.conditions
        return self

    def LimitOncePerEvent(self) -> 'Ability':
        self.conditions = [Condition.LimitOncePerEvent] + self.conditions
        return self

    def LimitCardNameOncePerEvent(self) -> 'Ability':
        self.conditions = [Condition.LimitOnceCardNamePerEvent] + self.conditions
        return self

    def NoGameAreaLimit(self) -> 'Ability':
        self.ignore.game_area = True
        return self

    # can trigger this ability
    def AnyPlayerCanDoThis(self,
                           *,
                           owner_has_trait: "CardFace.TRAITS|None"=None,
                           player_identity_has_trait: "CardFace.TRAITS|None"=None,
                           player_alter_ego_has_trait: "CardFace.TRAITS|None"=None) -> 'Ability':
        if player_identity_has_trait:
            def check_trigger_has_trait(effect: 'Effect') -> bool:
                return effect.GetInitiator().GetIdentity().HasTrait(player_identity_has_trait)
            self.any_player_can_trigger_this_when.append(check_trigger_has_trait)
        if player_alter_ego_has_trait:
            def check_trigger_has_trait(effect: 'Effect') -> bool:
                return effect.GetInitiator().GetIdentity().GetAlterEgoFace().HasTrait(player_alter_ego_has_trait)
            self.any_player_can_trigger_this_when.append(check_trigger_has_trait)
        elif owner_has_trait:
            def check_owner_has_trait(effect: 'Effect') -> bool:
                return effect.this.GetOwner().GetRoleCharacter().HasTrait(owner_has_trait)
            self.any_player_can_trigger_this_when.append(check_owner_has_trait)
        else:
            def return_true(effect: 'Effect') -> bool:
                return True
            self.any_player_can_trigger_this_when.append(return_true)
        return self

    ################################################################################
    #
    def SetToAvailableTimesFn(self, tiems_fn: Callable[['Effect', 'TM'], int]) -> 'Ability':
        self.available_times_fn = tiems_fn # type: ignore
        return self

    def SetCannotBeCancel(self) -> 'Ability':
        self.cannot_be_cancel = True
        return self

    ################################################################################
    #
    def __repr__(self) -> str:
        return self.GetName(True)

    def GetName(self, debug: bool) -> str:
        text = f'({self.flags.ability_type}'
        # if self.is_play:
        #     text += ',Play'
        if self.func_names:
            text += f',{",".join(self.func_names)}'
        if self.labels:
            text += f',{",".join(self.labels)}'
        text += ')'
        if self.name:
            text += f' "{self.name}"'
        if debug:
            if self.paper:
                text += f' [{self.paper.card_id}]'
            if type(self.when) is types.UnionType:
                for name in get_args(type(self.when)):
                    text += f' {name.__name__}'
            else:
                text += f' {self.when.__name__}'
        return text

    def CopyFromDelayEffect(self, effect: 'Effect') -> None:
        assert effect.ability.flags.is_delay_ability
        assert self.flags.is_interrupt or self.flags.is_response or self.flags.is_when_defeated or self.flags.is_temp or self.flags.is_nonkeyword or self.flags.is_action or self.flags.is_rule or self.flags.is_challenge

        for cost_func in effect.ability.cost_funcs:
            self.SetCostFunc(cost_func)
        if effect.ability.play_cost:
            self.SetPlayCost(effect.ability.play_cost)
        if effect.ability.cost_fn:
            self.SetCost(effect.ability.cost_fn)

        self.available_times_fn = effect.ability.available_times_fn
        self.any_player_can_trigger_this_when = effect.ability.any_player_can_trigger_this_when[:]
        self.labels = effect.ability.labels[:]
        self.func_names = set(effect.ability.func_names)
        # self.conditions += effect.ability.conditions
        for condition in [Condition.LimitOncePerRound,
                        Condition.LimitOncePerRoundPerPlayer,
                        Condition.LimitOncePerPhase,
                        Condition.LimitOncePerEvent,
                        Condition.LimitOnceCardNamePerEvent,]:
            if condition in effect.ability.conditions:
                self.conditions.append(condition)
        self.selectors = [x for x in effect.ability.selectors]
        effect.delay_ability = self
