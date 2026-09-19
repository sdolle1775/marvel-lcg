from . import *

class AbilityFactoryEnhanceSelf:

    @staticmethod
    def ThisGainTraitsOfEachCardInPlay(
        which_card: 'CardType',
        ) -> 'Ability':
        from game.ability.factory import AbilityFactory
        from game.operate.worlds import Worlds
        from game.operate.effects import Effects

        change_on_event = OnEvent.Trait(which_card)

        def process(effect: 'Effect', traits: List['CardFace.TRAITS'], diff: Literal[1, -1]):
            this = effect.this
            Unused(this)

            if traits:
                this.GainTraits(diff, traits, effect)

        def when_this_valid(effect: 'Effect', message: 'Message2') -> None:
            this = effect.this

            class SaveTraits:

                def __init__(self) -> None:
                    self.last_face_traits: Dict['CardFace', List['CardFace.TRAITS']] = {}
                    self.curr_face_traits: Dict['CardFace', List['CardFace.TRAITS']] = {}
                    self.can_update = True

                def ShiftTraits(self):
                    self.last_face_traits = self.curr_face_traits.copy()
                    self.curr_face_traits = {}
                    self.can_update = True

                @property
                def curr_traits(self) -> List['CardFace.TRAITS']:
                    return [x for y in self.curr_face_traits for x in self.curr_face_traits[y]]

                @property
                def last_traits(self) -> List['CardFace.TRAITS']:
                    return [x for y in self.last_face_traits for x in self.last_face_traits[y]]

                @property
                def gain_traits(self) -> List['CardFace.TRAITS']:
                    traits: List['CardFace.TRAITS'] = []
                    for trait in self.curr_traits:
                        if trait not in self.last_traits:
                            traits.append(trait)
                    return traits

                @property
                def lose_traits(self) -> List['CardFace.TRAITS']:
                    traits: List['CardFace.TRAITS'] = []
                    for trait in self.last_traits:
                        if trait not in self.curr_traits:
                            traits.append(trait)
                    return traits

            store = SaveTraits()

            effect.this.card.ui.ResetTempEffectBy(effect)
            for face in Worlds.GetOnFieldCards(effect):
                if Condition.CheckWhichCard(which_card, face, effect):
                    store.last_face_traits[face] = face.traits
                    effect.this.card.ui.SetTempEffectBy(effect, face)
                    process(effect, store.last_face_traits[face], +1)

            def update_valid() -> None:
                effect.this.card.ui.ResetTempEffectBy(effect)

                process(effect, store.lose_traits, -1)
                process(effect, store.gain_traits, +1)

                store.ShiftTraits()

            def try_update_valid(valid_effect: 'Effect', message: 'Message2') -> None:
                assert isinstance(message, Message.AfterCardGainTrait|Message.AfterCardLoseTrait|Message.AfterCardLeavePlay|Message.AfterCardEnterPlay|Message.AfterCardFaceActivated)
                face = message.trigger

                if isinstance(message, Message.AfterCardLeavePlay):
                    traits = []
                # elif isinstance(message, Message.AfterCardEnterPlay):
                #     traits = face.traits
                else:
                    traits = face.traits

                assert store.can_update
                store.curr_face_traits[face] = traits

                # Fix flip
                for back_face in face.card.back_faces:
                    if back_face in store.curr_face_traits:
                        store.curr_face_traits[back_face] = []

                if face not in store.last_face_traits or \
                    store.last_face_traits[face] != store.curr_face_traits[face]:
                    store.can_update = False

                    # We immediately update
                    update_valid()
                else:
                    store.can_update = True

            loop_check_effects = this.effect.Registers(
                *Condition.GetEventAbilities(
                    change_on_event,
                    AbilityType.Temp0,
                    lambda effect, message: True,
                    try_update_valid
                )
            )

            def when_this_invalid(invalid_effect: 'Effect', message: 'Message2') -> None:
                Effects.UnRegister(loop_check_effects)
                effect.this.card.ui.ResetTempEffectBy(effect)
                store.last_face_traits = {}
                process(effect, store.curr_traits, -1)

            this.effect.RegisterTemp(
                AbilityFactory.WhileThisStateUpdate(
                    AbilityType.Temp0,
                    when_this_invalid
                ),
                unregister_after_exec=True,
            )

        return AbilityFactory.WhenCardEnterPlay(
            AbilityType.Temp0,
            "This",
            when_this_valid,
            include_face_changes=True,
        )

    ################################################################################
    #
    @staticmethod
    def ThisGainKeywordWhileFaceIsInPlay(
        while_face_is_in_play: 'CardFinder|None'=None,
        *,
        patrol: int|None=None,
        health: int|None=None,
        quickstrike: int|None=None,
        amplify: int|None=None,
        crisis: int|None=None,
        hazard: int|None=None,
        change_on_event: EventType=OnEvent.NONE,
        ) -> 'Ability':
        from game.operate.worlds import Worlds

        if change_on_event == OnEvent.NONE:
            change_on_event = OnEvent.CardInPlay(while_face_is_in_play)

        def check(effect: 'Effect', ui: List['CardFace']) -> int:
            face = Worlds.FindCardOnField(
                effect,
                while_face_is_in_play,
                game_area=effect.this.card.game_area
            )
            if face:
                ui.append(face)
                return 1
            else:
                return 0

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            unit.Gain(effect, diff,
                health=health,
                quickstrike=quickstrike,
                amplify=amplify,
                crisis=crisis,
                patrol=patrol,
                hazard=hazard,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check,
            process,
        )

    @staticmethod
    def IfCardIsNotInPlay(
        ability_type: 'AbilityType',
        while_face_is_not_in_play: 'CardFinder',
        operation: Callable[['Effect'], None],
        ) -> 'Ability':
        from game.operate.worlds import Worlds

        change_on_event = OnEvent.CardInPlay(while_face_is_not_in_play)

        assert ability_type == AbilityType.NonKeyword

        def check(effect: 'Effect', ui: List['CardFace']) -> int:
            face = Worlds.FindCardOnField(
                effect,
                while_face_is_not_in_play,
                game_area=effect.this.card.game_area
            )
            if face:
                return 0
            else:
                return 1

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            if curr:
                operation(effect)

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check,
            process,
        )

    @staticmethod
    def ThisGainKeywordWhileFaceIsNotInPlay(
        while_face_is_not_in_play: 'CardFinder|None'=None,
        *,
        acceleration_icon: int|None=None,
        ) -> 'Ability':
        from game.operate.worlds import Worlds

        change_on_event = OnEvent.CardInPlay(while_face_is_not_in_play)

        def check(effect: 'Effect', ui: List['CardFace']) -> int:
            face = Worlds.FindCardOnField(
                effect,
                while_face_is_not_in_play,
                game_area=effect.this.card.game_area
            )
            if face:
                return 0
            else:
                return 1

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            unit.Gain(effect, diff,
                acceleration_icon=acceleration_icon,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check,
            process,
        )

    @staticmethod
    def ThisGainKeywordWhileFaceIsInVictoryDisplay(
        while_face_is_in_victory_display: 'CardFinder|None'=None,
        *,
        acceleration_icon: int|None=None,
        villainous:  int|None=None,
        ) -> 'Ability':
        from game.operate.worlds import Worlds

        change_on_event = OnEvent.Victory(while_face_is_in_victory_display)

        def check(effect: 'Effect', ui: List['CardFace']) -> int:
            faces = Worlds.VictoryDisplay(effect).FindCards(
                while_face_is_in_victory_display,
            )
            if faces:
                ui.extend(faces)
                return 1
            else:
                return 0

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            unit.Gain(effect, diff,
                acceleration_icon=acceleration_icon,
                villainous=villainous,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check,
            process,
        )

    @staticmethod
    def ThisGainKeywordForEachFaceInPlay(
        for_each_face_in_play: 'CardFinder|None'=None,
        *,
        thwart: int|None=None,
        retaliate: int|None=None,
        attack: int|None=None,
        scheme: int|None=None,
        change_on_event: EventType=OnEvent.NONE,
        ) -> 'Ability':
        from game.operate.worlds import Worlds

        if change_on_event == OnEvent.NONE:
            change_on_event = OnEvent.CardInPlay(for_each_face_in_play)

        def check(effect: 'Effect', ui: List['CardFace']) -> int:
            faces = Worlds.FindCardsOnField(
                effect,
                for_each_face_in_play,
                game_area=effect.this.card.game_area
            )
            if faces:
                ui.extend(faces)
                return len(faces)
            else:
                return 0

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            unit.Gain(effect, diff,
                thwart=thwart,
                retaliate=retaliate,
                attack=attack,
                scheme=scheme,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check,
            process,
        )

    ################################################################################
    #
    @staticmethod
    def ThisGainIncite(check_fn: Callable[['Effect'], int]=lambda effect: 1,
                        *,
                        incite: int|None=None,
                        change_on_event: EventType=OnEvent.NONE,
                        ) -> List['Ability']:
        # def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:

        #     if unit.card.state.is_discarding: # Fix for "27124"
        #         return

        #     unit.Gain(effect, diff,
        #             incite=incite
        #     )

        def operation(effect: 'Effect', message: 'Message.WhenCardResetKeyword') -> None:
            from game.card.face.base import EncounterNonVillainCard

            this = effect.this
            assert EncounterNonVillainCard.IsType(this)
            if incite != None:
                diff = check_fn(effect)
                this.GainIncite(diff * incite, effect)

        # from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return [
            Ability(
                AbilityType.NonKeyword,
                Message.WhenCardResetKeyword,
                [
                    Condition2.ThisIsTrigger,
                ],
                operation
            ).NoOutOfPlayLimit().NoGameAreaLimit(),
            # ThisGainKeywordInternal(
            #     change_on_event,
            #     check_fn,
            #     process,
            # )
        ]

    # Sustainable
    @staticmethod
    def ThisGainKeyword(check_fn: Callable[['Effect', List['CardFace']], int]=lambda effect, ui: 1,
                        *,
                        attack: int|None=None,
                        thwart: int|None=None,
                        scheme: int|None=None,
                        health: int|Literal["2*", "3*"]|Callable[['Effect'], int]|None=None,
                        recover: int|None=None,
                        trait: "CardFace.TRAITS|None"=None,
                        retaliate: int|None=None,
                        restricted: int|None=None,
                        # ally_limit: int|None=None,
                        hand_size: int|None=None,
                        consider_as: Tuple["CardFace.TRAITS", Type['TC']]|None=None,
                        quickstrike :int|None=None,
                        stalwart: int|None=None,
                        patrol: int|None=None,
                        amplify: int|None=None,
                        crisis: int|None=None,
                        surge: int|None=None,
                        hinder: int|Literal["2*"]|None=None,
                        target_threat: int|None=None,
                        # incite: int|None=None, see "50094"
                        toughness: int|None=None,
                        additional_cost_for_basic_attack: 'CostFunc.Base|None'=None,
                        attack_consequential_damage: int|None=None,
                        thwart_consequential_damage: int|None=None,
                        acceleration_icon: int|None=None,
                        hazard: int|None=None,
                        control_additional_restricted: 'CardFinder|None'=None,
                        change_on_event: EventType=OnEvent.NONE,
                        ) -> 'Ability':
        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:

            # if unit.card.state.is_discarding and consider_as: # Hack: for "27124"
            #     return

            unit.Gain(effect, diff,
                attack=attack,
                thwart=thwart,
                health=health,
                recover=recover,
                trait=trait,
                retaliate=retaliate,
                restricted=restricted,
                # ally_limit=ally_limit,
                hand_size=hand_size,
                scheme=scheme,
                consider_as=consider_as,
                quickstrike=quickstrike,
                stalwart=stalwart,
                amplify=amplify,
                crisis=crisis,
                patrol=patrol,
                surge=surge,
                hinder=hinder,
                target_threat=target_threat,
                # incite=incite,
                toughness=toughness,
                additional_cost_for_basic_attack=additional_cost_for_basic_attack,
                attack_consequential_damage=attack_consequential_damage,
                thwart_consequential_damage=thwart_consequential_damage,
                acceleration_icon=acceleration_icon,
                hazard=hazard,
                control_additional_restricted=control_additional_restricted,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check_fn,
            process,
        )

    @staticmethod
    def ThisSetKeyword(check_fn: Callable[['Effect', List['CardFace']], Tuple[int, bool]]=lambda effect, ui: (1, False), # value, is_need_forced_update
                        *,
                        attack: int|None=None,
                        scheme: int|None=None,
                        change_on_event: EventType,
                        ) -> 'Ability':

        def process(effect: 'Effect', unit: 'CardFace', diff: int, curr: int) -> None:
            unit.FaceSet(effect, curr,
                attack=attack,
                scheme=scheme,
            )

        from game.ability.factory.enhance_self_helper import ThisGainKeywordInternal
        return ThisGainKeywordInternal(
            change_on_event,
            check_fn,
            process,
        )

