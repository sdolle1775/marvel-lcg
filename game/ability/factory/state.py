from . import *

class AbilityFactoryState:

    @staticmethod
    def AfterCardFlipToThisSide(ability_type: 'AbilityType',
                                # which_card: Literal["This"],
                                operation: OperationType[Message.AfterCardFlip],
                                *,
                                conditions: ConditionsType[Message.AfterCardFlip]=[]
                                ) -> 'Ability':
        return AbilityFactoryState.AfterFlipToThisFace(
            ability_type,
            # which_card,
            operation,
            conditions=conditions
        )

    @staticmethod
    def AfterFlipToThisFace(ability_type: 'AbilityType',
                            # which_card: Literal["This"],
                            operation: OperationType[Message.AfterCardFlip],
                            *,
                            conditions: ConditionsType[Message.AfterCardFlip]=[],
                            ) -> 'Ability':
        which_card = "This"

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardFlip') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.AfterCardFlip,
            [
                lambda effect, message:
                    # effect.this.card.face == message.trigger and \
                    effect.this == message.to_face and \
                    effect.this.card.IsOnField(),
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    # Also use to detach effects
    @staticmethod
    def WhileThisStateUpdate(ability_type: 'AbilityType',
                            operation: OperationType['TriggerMessage'],
                            # include_leave_play: bool=True,
                            include_flip: bool=True,
                            include_set_as: bool=True,
                            include_advance: bool=True,
                            include_enter_play: bool=False,
                            conditions: ConditionsType['TriggerMessage']=[]
                            ) -> 'Ability':
        which_card = "This"

        events: Any = Message.AfterCardLeavePlay

        # if include_leave_play:
        #     events |= Message.AfterCardLeavePlay
        if include_flip:
            events |= Message.WhenCardFlip
        if include_set_as:
            events |= Message.WhenCardSetAs
        if include_advance:
            events |= Message.WhenVillainAdvance
        if include_enter_play:
            events |= Message.WhenCardEnterPlay|Message.WhenCardFaceActivated

        def check_which_card(effect: 'Effect', message: 'TriggerMessage') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            events,
            [
                # message.trigger.IsInPlay() and \
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def WhenCardFlip(ability_type: 'AbilityType',
                    which_card: CardType,
                    operation: OperationType[Message.WhenCardFlip],
                    *,
                    conditions: ConditionsType[Message.WhenCardFlip]=[]
                    ) -> 'Ability':

        def check_which_card(effect: 'Effect', message: 'Message.WhenCardFlip') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        ability = Ability(
            ability_type,
            Message.WhenCardFlip,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )
        
        if which_card == "This":
            ability.NoOutOfPlayLimit()
        return ability

    @staticmethod
    def WhenCardFlipToThisSide(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.WhenCardFlip],
                                *,
                                conditions: ConditionsType[Message.WhenCardFlip]=[]
                                ) -> 'Ability':

        return AbilityFactoryState.WhenCardFlip(
            ability_type,
            which_card,
            operation,
            conditions=[
                lambda effect, message:
                    effect.this == message.to_face and \
                    effect.this.card.IsOnField(),
                *conditions
            ]
        )

    @staticmethod
    def WhenCardFlipOrLeavePlay(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.AfterCardLeavePlay|Message.WhenCardFlip],
                                *,
                                conditions: ConditionsType[Message.AfterCardLeavePlay|Message.WhenCardFlip]=[]
                                ) -> 'Ability':

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardLeavePlay|Message.WhenCardFlip') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_was_in_play(effect: 'Effect', message: 'Message.AfterCardLeavePlay|Message.WhenCardFlip') -> bool:
            if isinstance(message, Message.AfterCardLeavePlay):
                return True
            return message.trigger.IsInPlay()

        def check_no_swapping(effect: 'Effect', message: 'Message.AfterCardLeavePlay|Message.WhenCardFlip') -> bool:
            return not message.by_swapping

        return Ability(
            ability_type,
            Message.AfterCardLeavePlay|Message.WhenCardFlip,
            [
                check_which_card,
                check_was_in_play,
                check_no_swapping,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    # @staticmethod
    # def AfterCardLeavePlayFlip(ability_type: 'AbilityType',
    #                            which_card: Literal["This"],
    #                            operation: OperationType[Send.WhenCardLeavePlay|Send.WhenCardFlip],
    #                            *,
    #                            condition: ConditionType[Send.WhenCardLeavePlay|Send.WhenCardFlip]|None=None,
    #                            ) -> 'Ability':
    #     if condition == None:
    #         condition = lambda effect, message: True

    #     return Ability(
    #         ability_type,
    #         Send.WhenCardLeavePlay|Send.WhenCardFlip,
    #         lambda effect, message:
    #             effect.this == message.trigger and \
    #             condition(effect, message),
    #         operation
    #     )

    ################################################################################
    # Ready
    @staticmethod
    def WhenCardWouldReady(ability_type: 'AbilityType',
                            which_card: CardType,
                            operation: OperationType[Message.WhenCardWouldReady],
                            *,
                            control_by: PlayerType="AnyPlayer",
                            by_effect_face: 'CardFinder|None'=None,
                            conditions: ConditionsType[Message.WhenCardWouldReady]=[],
                           ) -> 'Ability':
        from game.effect.rule import DebugRule
        
        def check_which_card(effect: 'Effect', message: 'Message.WhenCardWouldReady'):
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_control_by(effect: 'Effect', message: 'Message.WhenCardWouldReady'):
            return Condition.CheckWhichPlayer(control_by, message.trigger.GetControlBy(), effect)

        def check_is_by_effect_face(effect: 'Effect', message: Message.WhenCardWouldReady) -> bool:
            if by_effect_face == None:
                return True
            if isinstance(message.by_effect, DebugRule):
                return False
            return by_effect_face.Check(message.by_effect.this)

        return Ability(
            ability_type,
            Message.WhenCardWouldReady,
            [
                check_which_card,
                check_control_by,
                check_is_by_effect_face,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def CardCannotReady(which_card: CardType,
                        *,
                        conditions: ConditionsType[Message.WhenCardWouldReady|Message.CheckIfFaceCanBeReadied]=[],
                        control_by: PlayerType="AnyPlayer",
                        by_effect_face: 'CardFinder|None'=None
                        ) -> List['Ability']:
        # from game.ability.rule import DebugRule

        def cannot_ready(effect: 'Effect', message: 'Message.WhenCardWouldReady'):
            message.SetBeInstead(effect)

        # def check_ready_what(effect: 'Effect', message: 'Message.CheckCanBeReadied') -> bool:
        #     return Condition.CheckWhichCard(which_card, message.which_face, effect)

        # def check_is_by_effect_face(effect: 'Effect', message: Message.CheckCanBeReadied) -> bool:
        #     if by_effect_face == None:
        #         return True
        #     if isinstance(message.by_effect, DebugRule):
        #         return False
        #     return by_effect_face.Check(message.by_effect.this)

        return [
            AbilityFactoryState.WhenCardWouldReady(
                AbilityType.NonKeyword,
                which_card,
                cannot_ready,
                conditions=[*conditions],
                control_by=control_by,
                by_effect_face=by_effect_face
            ),
            # Ability(
            #     AbilityType.NonKeyword,
            #     Message.CheckCanBeReadied,
            #     [
            #         check_ready_what,
            #         check_is_by_effect_face,
            #         *conditions,
            #     ],
            #     lambda effect, message:
            #         message.SetCannotBeReadied(effect)
            # )
        ]

    @staticmethod
    def AfterCardReady(ability_type: 'AbilityType',
                       which_card: CardType,
                       operation: OperationType[Message.AfterCardReady],
                       *,
                       conditions: ConditionsType[Message.AfterCardReady]=[],
                       by_player: Literal["You"],
                       ) -> 'Ability':

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardReady'):
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_by_player(effect: 'Effect', message: 'Message.AfterCardReady'):
            return Condition.ThisIsYou(effect, message.by_effect.initiator)

        return Ability(
            ability_type,
            Message.AfterCardReady,
            [
                check_which_card,
                check_by_player,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

