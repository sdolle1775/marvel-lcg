from . import *

from game.ability.factory.setup import AbilityFactorySetup
from game.ability.factory.turn_phase import AbilityFactoryTurnPhase
from game.ability.factory.do_attack import AbilityFactoryDoAttack
from game.ability.factory.recovery import AbilityFactoryRecovery
from game.ability.factory.thwart import AbilityFactoryThwart
from game.ability.factory.resources import AbilityFactoryResources
from game.ability.factory.card_move import AbilityFactoryCardMove
from game.ability.factory.state import AbilityFactoryState
from game.ability.factory.defeated import AbilityFactoryDefeated
from game.ability.factory.reveal import AbilityFactoryReveal
from game.ability.factory.do_scheme import AbilityFactoryDoScheme
from game.ability.factory.do_thwart import AbilityFactoryDoThwart
from game.ability.factory.activate import AbilityFactoryActivate
from game.ability.factory.minion import AbilityFactoryMinion
from game.ability.factory.boost import AbilityFactoryBoost
from game.ability.factory.damage import AbilityFactoryDamage
from game.ability.factory.scheme import AbilityFactoryScheme
from game.ability.factory.on_while import AbilityFactoryWhile
from game.ability.factory.asset import AbilityFactoryAsset
from game.ability.factory.attachment import AbilityFactoryAttachment
from game.ability.factory.play import AbilityFactoryPlay
from game.ability.factory.counter import AbilityFactoryCounter
from game.ability.factory.deck import AbilityFactoryDeck
from game.ability.factory.discard import AbilityFactoryDiscard
from game.ability.factory.enemy import AbilityFactoryEnemy
from game.ability.factory.expert import AbilityFactoryExpert
from game.ability.factory.friend import AbilityFactoryFriend
from game.ability.factory.get import AbilityFactoryGet
from game.ability.factory.player import AbilityFactoryPlayer
from game.ability.factory.resolve import AbilityFactoryResolve
from game.ability.factory.environment import AbilityFactoryEnvironment
from game.ability.factory.environment2 import AbilityFactoryEnvironment2
from game.ability.factory.for_choice import AbilityFactoryForChoice
from game.ability.factory.status import AbilityFactoryStatus
from game.ability.factory.token import AbilityTokenFactory
from game.ability.factory.form import AbilityFactoryForm
from game.ability.factory.challenge import AbilityFactoryChallenge
from game.ability.factory.additional_cost import AbilityFactoryAdditionalCost
from game.ability.factory.enhance_self import AbilityFactoryEnhanceSelf
from game.ability.factory.treat import AbilityFactoryTreat

class AbilityFactory(AbilityFactorySetup, AbilityFactoryTurnPhase, AbilityFactoryDoAttack, AbilityFactoryRecovery, AbilityFactoryThwart, AbilityFactoryResources, AbilityFactoryCardMove, AbilityFactoryState, AbilityFactoryDefeated, AbilityFactoryReveal, AbilityFactoryDoScheme, AbilityFactoryDoThwart, AbilityFactoryActivate, AbilityFactoryMinion, AbilityFactoryBoost, AbilityFactoryDamage, AbilityFactoryScheme, AbilityFactoryWhile, AbilityFactoryAsset, AbilityFactoryAttachment, AbilityFactoryPlay, AbilityFactoryCounter, AbilityFactoryDeck, AbilityFactoryDiscard, AbilityFactoryEnemy, AbilityFactoryExpert, AbilityFactoryFriend, AbilityFactoryGet, AbilityFactoryPlayer, AbilityFactoryResolve, AbilityFactoryEnvironment, AbilityFactoryEnvironment2, AbilityFactoryForChoice, AbilityFactoryStatus, AbilityTokenFactory, AbilityFactoryForm, AbilityFactoryChallenge, AbilityFactoryAdditionalCost, AbilityFactoryEnhanceSelf, AbilityFactoryTreat, ):

    ################################################################################
    #
    @staticmethod
    def AfterUnitHitPointReset(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.AfterUnitHitPointReset],) -> 'Ability':
        def check_which_card(effect: 'Effect', message: Message.AfterUnitHitPointReset) -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.AfterUnitHitPointReset,
            [
                check_which_card
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def UniqueRuleNotApplyTo(which_card: Literal["This"]|None=None,
                             name: str|None=None) -> 'Ability':
        # The Stronghold side of the Avengers Tower environment card reads: “The unique rule does not apply to Avengers Tower.” This constant ability allows each player to play the Avengers Tower support card and use its ability while the Avengers Tower environment card Stronghold side is in play
        def check_which_card(effect: 'Effect', message: 'Message.CheckIfFaceApplyUniqueRule') -> bool:
            if which_card == "This":
                return effect.this == message.which_face
            if name != None:
                return message.which_face.IsName(name)
            assert False

        return Ability(
            AbilityType.NonKeyword,
            Message.CheckIfFaceApplyUniqueRule,
            [check_which_card],
            lambda effect, message:
                message.IgnoreUniqueRule(effect),
            is_local=which_card == "This"
        )

    @staticmethod
    def TheVillainMatchesAttachedSchemeIsActive() -> 'Ability':
        from game.card.face.card_type import MainScheme

        def check(effect: 'Effect', scheme: 'CardFace', ui: List['CardFace']) -> int:
            if not MainScheme.IsType(scheme):
                return 0
            if scheme.corresponding_villain_name:
                villain = scheme.FindCorrespondingVillain()
                if villain:
                    ui.append(villain)
                    return 1
            return 0

        def operation(effect: 'Effect', scheme: 'CardFace', diff: int) -> None:
            if diff <= 0:
                return
            if MainScheme.IsType(scheme):
                villain = scheme.FindCorrespondingVillain()
                if villain:
                    villain.SetActive(effect)

        from game.ability.factory.asset_helper import GiveKeywordToAttachWhenApplyThisInternal

        return GiveKeywordToAttachWhenApplyThisInternal(
            MainScheme,
            ignore_flip=False,
            get_new_value=check,
            apply=operation,
        )

    # @staticmethod
    # def WhenCardBeCreated(ability_type: 'AbilityType',
    #                     which_card: CardType,
    #                     operation: OperationType[Message.WhenCardBeCreated],) -> 'Ability':
    #     def check_which_card(effect: 'Effect', message: 'Message.WhenCardBeCreated') -> bool:
    #         return Condition.CheckWhichCard(which_card, message.trigger, effect)
        
    #     return Ability(
    #         ability_type,
    #         Message.WhenCardBeCreated,
    #         [
    #             check_which_card(effect, message),
    #         operation
    #     )

    @staticmethod
    def WhenScenarioEvent(ability_type: 'AbilityType',
                        text: str,
                        operation: OperationType[Message.WhenScenarioEvent],) -> 'Ability':
        def check_text(effect: 'Effect', message: 'Message.WhenScenarioEvent') -> bool:
            return text == message.text
        
        return Ability(
            ability_type,
            Message.WhenScenarioEvent,
            [
                check_text
            ],
            operation
        )

    @staticmethod
    def DiscardThisWhenRoundEnd(ability_type: 'AbilityType',
                                *,
                                conditions: ConditionsType[Message.AfterRoundEnd]=[]
                                ) -> 'Ability':
        from game.operate.faces import Faces

        def discard_this(effect: 'Effect', message: 'Message2') -> None:
            Faces.DiscardAll([effect.this], effect)

        return AbilityFactory.AfterRoundEnd(
            ability_type,
            discard_this,
            conditions=conditions
        )

    @staticmethod
    def ThisCannotHaveEncounterCardsAttached() -> 'Ability':
        return Ability(
            AbilityType.NonKeyword,
            Message.CheckIfFaceCanAttachTo,
            [
                lambda effect, message:
                    effect.this == message.to_face and \
                    EncounterCard.IsType(message.upgrade)
            ],
            lambda effect, message:
                message.SetCannotAttachTo(effect)
        )

    @staticmethod
    def ThisCannotHaveCardsAttached() -> 'Ability':
        # Discard all cards on this?
        return Ability(
            AbilityType.NonKeyword,
            Message.CheckIfFaceCanAttachTo,
            [
                lambda effect, message:
                    effect.this == message.to_face
            ],
            lambda effect, message:
                message.SetCannotAttachTo(effect)
        )

    @staticmethod
    def ThisDoesNotCountTowardHandSize() -> 'Ability':
        return Ability(
            AbilityType.NonKeyword,
            Message.CheckIfFaceCountHandSize,
            [
                Condition2.ThisIsTrigger
            ],
            lambda effect, message:
                message.SetNotCountHandSize(effect)
        ).CanWorkOnlyInHand()

    @staticmethod
    def ThisGainEachTraitOnYourIdentity() -> List['Ability']:
        return [
            AbilityFactory.ThisGainTraitsOfEachCardInPlay(
                "YourIdentity",
            ),
        ]

    @staticmethod
    def YouCannotFlipCards(which_card: CardType) -> 'Ability':

        def check_which_card(effect: 'Effect', message: Message.WhenCardWouldFlip) -> bool:
            return message.trigger in Select.GetYou(effect).GetControlCards() and \
                Condition.CheckWhichCard(which_card, message.trigger, effect)

        def action(effect: 'Effect', message: Message.WhenCardWouldFlip) -> None:
            message.SetBeInstead(effect)

        return Ability(
            AbilityType.NonKeyword,
            Message.WhenCardWouldFlip,
            [
                check_which_card
            ],
            action
        )

    @staticmethod
    def ThisCannotRemoveFromPlay() -> 'Ability':
        return Ability(
            AbilityType.NonKeyword,
            Message.WhenCardWouldRemoveFromGame,
            [
                Condition2.ThisIsTrigger
            ],
            lambda effect, message:
                message.SetBeInstead(effect)
        )
    
    @staticmethod
    def FirstCardPlayerRevealsGain(which_card: CardType,
                                      who_reveal: PlayerType,
                                      each_phase_round: Literal["VillainPhase", "Round", "Phase", None]=None,
                                      gain_surge: int|None=None) -> 'Ability':
        from game.card.face.attribute.can_surge import CanSurge

        def action(effect: 'Effect', message: 'Message.WhenPlayerRevealCard|Message.WhenCardRevealed') -> None:
            if gain_surge and CanSurge.IsType(message.trigger):
                message.trigger.GainSurge(+1, effect)

        def check_each_phase(effect: 'Effect', message: 'Message.WhenPlayerRevealCard|Message.WhenCardRevealed') -> bool:
            if each_phase_round == None or each_phase_round == "Phase" or each_phase_round == "Round":
                return True
            if each_phase_round == "VillainPhase":
                return effect.world.phase.IsVillainPhase()

        if who_reveal == "AnyPlayer":
            ability = AbilityFactory.WhenCardRevealed(
                AbilityType.NonKeyword,
                which_card,
                action,
                conditions=[check_each_phase]
            )
        else:
            # See also "16088"
            ability = AbilityFactory.WhenPlayerRevealCard(
                AbilityType.NonKeyword,
                who_reveal,
                which_card,
                None,
                action,
                conditions=[check_each_phase]
                    # is_first_treachery_reveal_in_villain_phase(effect),
            )

        if each_phase_round == "VillainPhase" or each_phase_round == "Phase":
            ability.LimitOncePerPhase()

        if each_phase_round == "Round":
            ability.LimitOncePerRound()

        return ability

    @staticmethod
    def UnitCannotHaveUpgradeAttached(which_card: CardType) -> List['Ability']:
        from game.card.face.card_type import Upgrade
        from game.operate.faces import Faces
        def check_which_card(effect: 'Effect', message: 'Message.CheckIfFaceCanAttachTo|Message.WhenCardWouldAttachTo') -> bool:
            return Condition.CheckWhichCard(which_card, message.to_face, effect)

        def check_is_upgrade(effect: 'Effect', message: 'Message.CheckIfFaceCanAttachTo|Message.WhenCardWouldAttachTo') -> bool:
            return Upgrade.IsType(message.upgrade)

        def discard(effect: 'Effect', message: 'Message.WhenCardWouldAttachTo') -> None:
            message.SetBeInstead(effect)
            Faces.DiscardAll([message.upgrade], effect)


        return [
            Ability(
                AbilityType.NonKeyword,
                Message.CheckIfFaceCanAttachTo,
                [
                    check_is_upgrade,
                    check_which_card
                ],
                lambda effect, message:
                    message.SetCannotAttachTo(effect)
            ),
            Ability(
                AbilityType.NonKeyword,
                Message.WhenCardWouldAttachTo,
                [
                    check_is_upgrade,
                    check_which_card
                ],
                discard
            )
        ]

    # TODO: Swap `which_upgrade` and `attached_to`
    @staticmethod
    def AfterCardGainUpgrade(ability_type: 'AbilityType',
                              which_upgrade: CardType,
                              attached_to: CardType,
                              operation: OperationType[Message.AfterCardAttachTo],
                              ) -> 'Ability':
        def check_which_upgrade(effect: 'Effect', message: 'Message.AfterCardAttachTo') -> bool:
            return Condition.CheckWhichCard(which_upgrade, message.upgrade, effect)

        def check_attached_to(effect: 'Effect', message: 'Message.AfterCardAttachTo') -> bool:
            return Condition.CheckWhichCard(attached_to, message.to_face, effect)

        return Ability(
            ability_type,
            Message.AfterCardAttachTo,
            [
                check_which_upgrade,
                check_attached_to,
            ],
            operation
        )

    ################################################################################
    #
    @staticmethod
    def IgnoreAbilityOnCard(which_card: CardType,
                            which_ability: AbilitiesType,
                            ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: Message.CheckEffectCondition) -> bool:
            return Condition.CheckWhichCard(which_card, message.check_effect.this, effect)

        def check_which_ability(effect: 'Effect', message: 'Message.CheckEffectCondition') -> bool:
            ability = message.check_effect.ability
            return Condition.CheckWhichAbility(which_ability, ability)

        return Ability(
            AbilityType.NonKeyword,
            Message.CheckEffectCondition,
            [
                check_which_card,
                check_which_ability,
            ],
            lambda effect, message:
                message.SetEffectInvalid(effect),
            is_local=which_card == "This"
        )

    @staticmethod
    def ThisCannotBeTreatedAsBlank() -> 'Ability':
        return Ability(
            AbilityType.NonKeyword,
            Message.WhenCardWouldTreatAsIfBlank,
            [
                Condition2.ThisIsTrigger,
            ],
            lambda effect, message:
                message.SetBeInstead(effect)
        )

    @staticmethod
    def AfterIgnoreKeywordOnCard(ability_type: 'AbilityType',
                                who_ignore: CardType|Literal["You"],
                                ignore_on_which_card: CardType,
                                keywords: List['CardFace.ABILITY_IGNORE_KEY'],
                                operation: OperationType[Message.AfterIgnoreKeywordOnCard],) -> 'Ability':
        def check_who_ignore(effect: 'Effect', message: Message.AfterIgnoreKeywordOnCard) -> bool:
            rule = Condition.GetYouRule(who_ignore, identity=True)
            return Condition.CheckWhichCard(rule, message.trigger, effect)

        def check_which_card(effect: 'Effect', message: Message.AfterIgnoreKeywordOnCard) -> bool:
            return Condition.CheckWhichCard(ignore_on_which_card, message.ignore_on_which_face, effect)

        def check_which_keyword(effect: 'Effect', message: 'Message.AfterIgnoreKeywordOnCard') -> bool:
            return message.keyword in keywords

        return Ability(
            ability_type,
            Message.AfterIgnoreKeywordOnCard,
            [
                check_who_ignore,
                check_which_card,
                check_which_keyword,
            ],
            operation,
            is_local=who_ignore == "This" or ignore_on_which_card == "This"
        )

    @staticmethod
    def YouAreStateWhileThisInPlay(get_target: Callable[['Effect'], 'CardFace'],
                                    status: "CardFace.STATUS"
                                    ) -> 'Ability':
        from game.operate.faces import Faces

        def action(effect: 'Effect', message: 'Message2'):
            this = effect.this

            target = get_target(effect)

            def give_confused():
                Faces.GiveStatus([target], status, effect)

            give_confused()

            this.effect.RegisterTemp(
                AbilityFactory.AfterStatusDiscardFrom(
                    AbilityType.Temp0,
                    target,
                    status,
                    lambda effect, message:
                        give_confused(),
                ),
                unregister_after_exec=False,
                until_this_leave_play=True,
            )

        return AbilityFactory.AfterCardEnterPlay(
            AbilityType.Temp0,
            "This",
            action,
        )


    @staticmethod
    def WhenCountingResourcesOnCards(face: CardType,
                                    operation: OperationType[Message.WhenCountingResourcesOnCards],
                                    *,
                                    from_where: Callable[['Effect'], 'Deck']|'Deck|None|DeckType'=None,
                                    conditions: ConditionsType[Message.WhenCountingResourcesOnCards]=[]
                                    ) -> 'Ability':
        from game.deck import Deck2, DeckType

        def check_face(effect: 'Effect', message: 'Message.WhenCountingResourcesOnCards') -> bool:
            if face == None:
                return True
            return Condition.CheckWhichCard(face, message.face, effect)

        def check_from_where(effect: 'Effect', message: 'Message.WhenCountingResourcesOnCards') -> bool:
            if from_where == None:
                return True
            if isinstance(from_where, Deck2):
                return from_where == message.from_deck
            if isinstance(from_where, DeckType):
                return message.from_deck != None and message.from_deck.deck_type == from_where
            else:
                return from_where(effect) == message.from_deck

        return Ability(
            AbilityType.NonKeyword,
            Message.WhenCountingResourcesOnCards,
            [
                check_face,
                check_from_where,
                *conditions
            ],
            operation,
        )

    @staticmethod
    def ResolveEachWhenRevealedAbilityAdditionalTime(trigger_player: Literal["You", "AnyPlayer"],
                                                    additional_time: Literal[1]
                                                    ) -> 'Ability':
        def action(effect: 'Effect', message: 'Message.AfterEffectResolved') -> None:
            player = message.GetToPlayer()
            message.effect.this.ResolveAbility(player, AbilityType.WhenRevealed, effect)

        return AbilityFactory.AfterPlayerResolveAbility(
            AbilityType.NonKeyword,
            trigger_player,
            None,
            action,
            which_abilities=["WhenRevealed"],
            conditions=[
                lambda effect, message:
                    effect != message.by_effect
            ]
        )

    @staticmethod
    def WhenCardTreatAsIfBlank(which_card: Literal["This"],
                                operation: OperationType[Message.WhenCardTreatAsIfBlank],
                                *,
                                conditions: ConditionsType[Message.WhenCardTreatAsIfBlank]=[]
                                ) -> 'Ability':

        return Ability(
            AbilityType.Temp0,
            Message.WhenCardTreatAsIfBlank,
            [
                lambda effect, message:
                    effect.this == message.trigger,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def IncreaseAllDamageUnitTakeBy(ability_type: 'AbilityType',
                                    which_unit: CardType,
                                    increase: int,
                                    is_from_attack: bool|None=None,
                                    ) -> 'Ability':
        return AbilityFactory.WhenUnitWouldTakeDamage(
            ability_type,
            which_unit,
            lambda effect, message:
                message.IncreaseDamage(increase, effect, include_overkill=True),
            is_from_attack=is_from_attack,
        )

    @staticmethod
    def WhileUnitIsDefending(ability_type: 'AbilityType',
                            which_unit: CardType,
                            operation: OperationType[Message.WhenUnitWouldDefend],
                            ) -> 'Ability':
        return AbilityFactory.WhenUnitDefendAgainstAttack(
            ability_type,
            which_unit,
            operation
        )

    @staticmethod
    def WhenResolvePreparationAbility(which_card: Literal["This"],
                                    operation: OperationType[Message.WhenResolvePreparationAbility],
                                    *,
                                    conditions: ConditionsType[Message.WhenResolvePreparationAbility]=[]
                                    ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.WhenResolvePreparationAbility') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            AbilityType.Preparation,
            Message.WhenResolvePreparationAbility,
            conditions + [check_which_card],
            operation,
            is_local=which_card == "This"
        ).NoOutOfPlayLimit()

    @staticmethod
    def WhenResolvePreparationAbility2(ability_type: 'AbilityType',
                                    which_card: CardType,
                                    operation: OperationType[Message.WhenResolvePreparationAbility],
                                    *,
                                    conditions: ConditionsType[Message.WhenResolvePreparationAbility]=[]
                                    ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.WhenResolvePreparationAbility') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.WhenResolvePreparationAbility,
            conditions + [check_which_card],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def UnitBasicThwartCanOnlyRemoveThreatFromMostThreatScheme(which_card: CardType,
                                                                *,
                                                                conditions: ConditionsType[Message.WhenResolvePreparationAbility]=[]
                                                                ) -> 'Ability':
        from game.operate.filter import Filter
        from game.operate.worlds import Worlds

        def retinal_display(effect: 'Effect', message: 'Message.WhenSchemeBeingThwart') -> None:
            this = effect.this
            Unused(this)

            faces = Filter.All(Worlds.GetOnFieldSchemes(effect), most_threat=True)
            if message.scheme not in faces:
                this.effect.RegisterTemp(
                    AbilityFactory.WhenSchemeWouldRemoveThreat(
                        AbilityType.Temp0,
                        message.scheme,
                        lambda effect, message:
                            message.SetBeInstead(effect),
                        who_make_thwart=message.who_make_thwart,
                        thwart_event=message.would_thw_message
                    ),
                    unregister_after_exec=True
                )

        return AbilityFactory.WhenUnitThwartScheme(
            AbilityType.NonKeyword,
            which_card,
            retinal_display,
            is_basic_thwart=True,
        )

    @staticmethod
    def AsAdditionalCostToPlayThis(operation: OperationType[Message.WhenPlayerWouldPlayCard]) -> 'Ability':

        return AbilityFactory.WhenPlayerWouldPlayCard(
            AbilityType.NonKeywordStar,
            "AnyPlayer",
            "This",
            operation,
        )

    @staticmethod
    def AfterCardGainTrait(ability_type: 'AbilityType',
                            which_card: CardType,
                            trait: "CardFace.TRAITS",
                            operation: OperationType[Message.AfterCardGainTrait],
                            *,
                            gives_by_revealed: bool|None=None,
                            conditions: ConditionsType[Message.AfterCardGainTrait]=[]
                            ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: Message.AfterCardGainTrait) -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_trait(effect: 'Effect', message: Message.AfterCardGainTrait) -> bool:
            return trait in message.traits

        def check_gives_by_revealed(effect: 'Effect', message: Message.AfterCardGainTrait) -> bool:
            if gives_by_revealed == None:
                return True
            check_message = message.by_effect.bind_message
            assert isinstance(check_message, Message.AfterCardEnterPlay|Message.WhenCardEnterPlay)
            return check_message.trigger.card.state.is_revealing

        return Ability(
            ability_type,
            Message.AfterCardGainTrait,
            [
                check_which_card,
                check_trait,
                check_gives_by_revealed,
                *conditions,
            ],
            operation,
            is_local=which_card == "This"
        )

