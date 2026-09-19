from . import *

class AbilityFactoryWhile:

    @staticmethod
    def WhenEvent(check_when: Type[TMP],
                   condition: ConditionType[TMP],
                   operation: OperationType[TMP]) -> 'Ability':
        from game.ability.factory import AbilityFactory
        from game.operate.effects import Effects

        def when_this_valid(effect: 'Effect', message: 'Message2') -> None:
            this = effect.this

            if condition(effect, message): # type: ignore
                operation(effect, message) # type: ignore

            loop_check_effects = this.effect.Registers(
                Ability(
                    AbilityType.Temp1,
                    check_when,
                    [
                        lambda effect, message:
                            not this.is_treat_as_if_blank and \
                            condition(effect, message)
                    ],
                    lambda effect, message:
                        operation(effect, message)
                )
            )

            def when_this_invalid(invalid_effect: 'Effect', message: 'Message2') -> None:
                Effects.UnRegister(loop_check_effects)

            this.effect.RegisterTemp(
                AbilityFactory.WhileThisStateUpdate(
                    AbilityType.Temp0,
                    when_this_invalid
                ),
                unregister_after_exec=True,
            )

        return AbilityFactory.WhenCardEnterPlay(
            AbilityType.NonKeyword,
            "This",
            when_this_valid,
            include_face_changes=True,
        )

    @staticmethod
    def WhileValid( change_on_event: EventType,
                    condition_fn: ConditionType[TM],
                    check_fn: Callable[['Effect', int], int|Tuple[int, bool]],
                    process_fn: Callable[['Effect', int, int], None],
                    *,
                    preserve_value_on_same_card_flip: bool=False,
                    ) -> 'Ability':
        from game.ability.factory import AbilityFactory
        from game.operate.effects import Effects

        def when_this_valid(effect: 'Effect', message: 'Message2') -> None:

            last_value = 0
            last_bind_face: 'CardFace|None' = None
            last_bind_card: 'Card|None' = None

            def invoke_check_value(effect: 'Effect') -> Tuple[int, bool]:
                effect.this.card.ui.ResetTempEffectBy(effect)
                if not this.IsInPlay():
                    return 0, False
                if this.card.state.is_leaving_play:
                    return 0, False
                if this.card.state.is_flipping:
                    return 0, False
                bind_face = this.bind_face
                if bind_face:
                    if bind_face.card.state.is_leaving_play:
                        return 0, False
                    # if bind_face.card.is_flipping:
                    #     return 0
                value = check_fn(effect, last_value)
                if isinstance(value, tuple):
                    return value
                else:
                    return value, False

            this = effect.this
            last_value, forced_update = invoke_check_value(effect)
            new_value: int

            if last_value != 0 or forced_update:
                if effect.this.bind_face:
                    last_bind_face = effect.this.bind_face
                    last_bind_card = last_bind_face.card
                process_fn(effect, last_value, last_value)

            def new_condition(message: Any) -> bool: # Hack
                nonlocal new_value
                nonlocal last_bind_face
                nonlocal last_bind_card
                nonlocal last_value

                # Fix "31001a"
                bind_face = effect.this.bind_face
                if bind_face and last_bind_face != bind_face:
                    same_card_flip = \
                        preserve_value_on_same_card_flip and \
                        last_bind_card is bind_face.card
                    last_bind_face = bind_face
                    last_bind_card = bind_face.card
                    if not same_card_flip:
                        last_value = 0

                effect.context.bind_message = message
                if condition_fn(effect, message):
                    new_value, forced_update = invoke_check_value(effect)
                    if new_value != last_value or forced_update:
                        return True
                    else:
                        return False
                else:
                    return False

            loop_check_effects = this.effect.Registers(
                *Condition.GetEventAbilities(
                    change_on_event,
                    AbilityType.Temp1,
                    lambda effect, message:
                        not this.is_treat_as_if_blank and \
                        new_condition(message),
                    lambda effect, message:
                        update_valid(message)
                )
            )

            def update_valid(message: 'Message2') -> None:
                nonlocal last_value
                nonlocal new_value
                diff_value = new_value - last_value
                last_value = new_value
                # if diff_value == 0:
                #     return None
                # assert diff_value != 0, f"{diff_value=}"
                effect.context.bind_message = message
                process_fn(effect, diff_value, new_value)

            def process_when_treat_as_blank(effect: 'Effect', message: 'Message.WhenCardTreatAsIfBlank') -> None:
                nonlocal new_value

                if effect.this.is_treat_as_if_blank or not effect.this.IsFaceUp():
                    new_value = 0
                    forced_update = False
                    # effect.this.card.ui.ResetTempEffectBy()
                else:
                    new_value, forced_update = invoke_check_value(effect)
                if new_value != last_value or forced_update:
                    update_valid(message)

            check_blank_effects = this.effect.Registers(
                AbilityFactory.WhenCardTreatAsIfBlank(
                    "This",
                    process_when_treat_as_blank,
                )
            )

            def when_this_invalid(invalid_effect: 'Effect', message: 'Message2') -> None:
                Effects.UnRegister(loop_check_effects)
                Effects.UnRegister(check_blank_effects)
                # if after_attach_defeated_effect:
                #     after_attach_defeated_effect.UnRegisterSelf()
                nonlocal last_value
                if last_value != 0:
                    old_last_value = last_value
                    last_value = 0
                    effect.context.bind_message = message
                    process_fn(effect, -1 * old_last_value, 0)

            this.effect.RegisterTemp(
                AbilityFactory.WhileThisStateUpdate(
                    AbilityType.Temp0,
                    when_this_invalid
                ),
                unregister_after_exec=True,
            )
            pass

        return AbilityFactory.WhenCardEnterPlay(
            AbilityType.NonKeyword,
            "This",
            when_this_valid,
            include_face_changes=True,
        )

