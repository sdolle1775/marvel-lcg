from . import *

class AbilityFactoryCardMove:

    @staticmethod
    def WhenCardWouldEnterPlay(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.WhenCardWouldMoveToArea],
                                ) -> 'Ability':
        ability = AbilityFactoryCardMove.WhenCardWouldMoveToArea(
            ability_type,
            which_card,
            operation,
            into_play=True,
        )
        if which_card == "This":
            ability.NoOutOfPlayLimit()
        return ability

    @staticmethod
    def WhenCardWouldBeTuckUnder(ability_type: 'AbilityType',
                                which_card: CardType,
                                under_where: CardType,
                                operation: OperationType[Message.WhenCardWouldMoveToArea],
                                *,
                                conditions: ConditionsType[Message.WhenCardWouldMoveToArea]=[],
                                ) -> 'Ability':

        def check_under_where(effect: 'Effect', message: 'Message.WhenCardWouldMoveToArea') -> bool:
            if not message.into_area.flags.is_place_card_area:
                return False
            if message.into_area.bind_card == None:
                return False
            if under_where == None:
                return True
            return Condition.CheckWhichCard(under_where, message.into_area.bind_card.face, effect)

        return AbilityFactoryCardMove.WhenCardWouldMoveToArea(
            ability_type,
            which_card,
            operation,
            conditions=[
                check_under_where,
                *conditions,
            ]
        )


    @staticmethod
    def WhenCardWouldMoveToArea(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.WhenCardWouldMoveToArea],
                                *,
                                from_play: bool|None=None,
                                into_play: bool|None=None,
                                into_discard_pile: bool|None=None,
                                conditions: ConditionsType[Message.WhenCardWouldMoveToArea]=[],
                                ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.WhenCardWouldMoveToArea') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_into_play(effect: 'Effect', message: 'Message.WhenCardWouldMoveToArea') -> bool:
            if into_play == None:
                return True
            return into_play == message.into_area.flags.is_in_play

        def check_from_play(effect: 'Effect', message: 'Message.WhenCardWouldMoveToArea') -> bool:
            if from_play == None:
                return True
            return from_play == message.from_area.flags.is_in_play

        def check_into_discard_pile(effect: 'Effect', message: 'Message.WhenCardWouldMoveToArea') -> bool:
            if into_discard_pile == None:
                return True
            return into_discard_pile == message.into_area.flags.is_discards

        return Ability(
            ability_type,
            Message.WhenCardWouldMoveToArea,
            [
                check_which_card,
                check_into_play,
                check_from_play,
                check_into_discard_pile,
                *conditions,
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def WhenCardEnterPlay(ability_type: 'AbilityType',
                          which_card: CardType,
                          operation: OperationType[Message.WhenCardEnterPlay],
                          *,
                          include_face_changes: bool=False,
                          conditions: ConditionsType[Message.WhenCardEnterPlay]=[],
                          ) -> 'Ability':
        # Continuous-effect helpers opt in to refreshing on face changes.
        # Printed entry abilities and keywords use actual entries only.
        def check_which_card(effect: 'Effect', message: 'Message.WhenCardEnterPlay') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.WhenCardEnterPlay|Message.WhenCardFaceActivated if include_face_changes else Message.WhenCardEnterPlay,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def AfterCardEnterPlay(ability_type: 'AbilityType',
                           which_card: CardType,
                           operation: OperationType[Message.AfterCardEnterPlay],
                           *,
                           include_face_changes: bool=False,
                           under_your_control: bool|None=None,
                           conditions: ConditionsType[Message.AfterCardEnterPlay]=[],
                           ) -> 'Ability':
        # See WhenCardEnterPlay: face changes are internal refreshes.
        def check_under_your_control(effect: 'Effect', message: 'Message.AfterCardEnterPlay') -> bool:
            if under_your_control == None:
                return True
            return message.trigger.GetControlBy() == effect.initiator

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardEnterPlay') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.AfterCardEnterPlay|Message.AfterCardFaceActivated if include_face_changes else Message.AfterCardEnterPlay,
            [
                check_which_card,
                check_under_your_control,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def AfterCardAttachTo(ability_type: 'AbilityType',
                           which_card: CardType,
                           to_which_card: CardType,
                           operation: OperationType[Message.AfterCardAttachTo],
                           *,
                           conditions: ConditionsType[Message.AfterCardAttachTo]=[],
                           ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.AfterCardAttachTo') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        def check_to_which_card(effect: 'Effect', message: 'Message.AfterCardAttachTo') -> bool:
            return Condition.CheckWhichCard(to_which_card, message.to_face, effect)

        return Ability(
            ability_type,
            Message.AfterCardAttachTo,
            [
                check_which_card,
                check_to_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This" or to_which_card == "This"
        )

    @staticmethod
    def AfterCardEnterHand(ability_type: 'AbilityType',
                           which_card: CardType,
                           operation: OperationType[Message.AfterCardEnterHand],
                           *,
                           conditions: ConditionsType[Message.AfterCardEnterHand]=[],
                           ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.AfterCardEnterHand') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        ability = Ability(
            ability_type,
            Message.AfterCardEnterHand,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )
        if which_card == "This":
            ability.CanWorkOnlyInHand()
        return ability

    @staticmethod
    def WhenCardWouldLeavePlay(ability_type: 'AbilityType',
                                which_card: CardType,
                                operation: OperationType[Message.WhenCardWouldLeavePlay],
                                *,
                                conditions: ConditionsType[Message.WhenCardWouldLeavePlay]=[],
                                ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.WhenCardWouldLeavePlay') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.WhenCardWouldLeavePlay,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def WhenCardLeavePlay(ability_type: 'AbilityType',
                          which_card: CardType,
                          operation: OperationType[Message.WhenCardLeavePlay],
                          *,
                          conditions: ConditionsType[Message.WhenCardLeavePlay]=[],
                          ) -> 'Ability':
        def check_which_card(effect: 'Effect', message: 'Message.WhenCardLeavePlay') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        return Ability(
            ability_type,
            Message.WhenCardLeavePlay,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    @staticmethod
    def AfterCardLeavePlayInternal(ability_type: 'AbilityType',
                                    which_card: CardType,
                                    operation: OperationType[Message.AfterCardLeavePlay],
                                    *,
                                    conditions: ConditionsType[Message.AfterCardLeavePlay]=[]
                                    ) -> 'Ability':
        set_out_of_play = False
        if which_card == "This":
            set_out_of_play = True

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardLeavePlay') -> bool:
            return Condition.CheckWhichCard(which_card, message.trigger, effect)

        ability = Ability(
            ability_type,
            Message.AfterCardLeavePlay,
            [
                check_which_card,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )
        if set_out_of_play:
            return ability.NoOutOfPlayLimit()
        else:
            return ability

    @staticmethod
    def AfterCardLeavePlay(ability_type: 'AbilityType',
                           which_card: CardType,
                           operation: OperationType[Message.AfterCardLeavePlay],
                           *,
                           conditions: ConditionsType[Message.AfterCardLeavePlay]=[]
                           ) -> 'Ability':
        if not isinstance(which_card, tuple):
            return AbilityFactoryCardMove.AfterCardLeavePlayInternal(
                ability_type,
                which_card,
                operation,
                conditions=conditions,
            )

        def action(effect: 'Effect', message: 'Message.WhenCardWouldLeavePlay') -> None:
            this = effect.this

            if Condition.CheckWhichCard(which_card, message.trigger, effect):
                ability = AbilityFactoryCardMove.AfterCardLeavePlayInternal(
                    ability_type,
                    message.trigger,
                    operation,
                    conditions=conditions,
                ).NoOutOfPlayLimit()
                ability.CopyFromDelayEffect(effect)
                this.effect.RegisterTemp(
                    ability,
                    unregister_after_exec=True,
                    until_event_end=message
                )

        return AbilityFactoryCardMove.WhenCardWouldLeavePlay(
            AbilityType.DelayAbility,
            which_card,
            action,
        ).SetSecondType(ability_type)

    @staticmethod
    def AfterCardsMoved(ability_type: 'AbilityType',
                        which_card: CardType,
                        operation: OperationType[Message.AfterCardsMoved],
                        *,
                        by_shuffle: bool|None=None,
                        conditions: ConditionsType[Message.AfterCardsMoved]=[]
                        ) -> 'Ability':

        def check_which_card(effect: 'Effect', message: 'Message.AfterCardsMoved') -> bool:
            return message.IsIncludeFace(which_card, effect) != None

        def check_by_shuffle(effect: 'Effect', message: 'Message.AfterCardsMoved'):
            if by_shuffle == None:
                return True
            return by_shuffle == message.by_shuffle

        return Ability(
            ability_type,
            Message.AfterCardsMoved,
            [
                check_which_card,
                check_by_shuffle,
                *conditions
            ],
            operation,
            is_local=which_card == "This"
        )

    # @staticmethod
    # def AfterThisWouldLeavePlay(ability_type: 'AbilityType',
    #                             condition: ConditionType[Send.WhenCardWouldMoveToArea],
    #                             operation: ActionFuncType[Send.WhenCardWouldMoveToArea]) -> 'Ability':
    #     return Ability(
    #         ability_type,
    #         Send.WhenCardWouldMoveToArea,
    #         lambda effect, message:
    #             effect.this == message.trigger and \
    #             condition(effect, message),
    #         operation
    #     )

