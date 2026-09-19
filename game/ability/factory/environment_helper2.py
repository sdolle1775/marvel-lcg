from . import *

CardTypeMin = Condition.CARD_TYPE_MIN

class StoreValueDiff:
    def __init__(self, diff: int=0, lst_add: Sequence[str]=[], lst_del: Sequence[str]=[]) -> None:
        self.diff = diff
        self.lst_add = list(lst_add)
        self.lst_del = list(lst_del)

    def is_empty(self) -> bool:
        return self.diff == 0 and \
                not self.lst_add and \
                not self.lst_del

    def is_lt_0(self) -> bool:
        return self.diff < 0 or bool(self.lst_del)

    def __mul__(self, num: int) -> 'StoreValueDiff':
        if num == +1:
            return StoreValueDiff(self.diff, self.lst_add, self.lst_del)
        if num == -1:
            return StoreValueDiff(-1 * self.diff, self.lst_del, self.lst_add)
        assert False

    def __repr__(self) -> str:
        return f"{self.diff}, {self.lst_add}, {self.lst_del}"

class StoreValue:

    def __init__(self, num: int=0, lst: Sequence[str]=[]) -> None:
        self.num = num
        self.lst = list(lst)

    def clear(self):
        self.num = 0
        self.lst.clear()

    def update(self, diff: int, lst_add: Sequence[str], lst_del: Sequence[str]):

        def update_list(main_list: List[str], list_to_add: Sequence[str], list_to_remove: Sequence[str]) -> None:
            remove_set = set(list_to_remove)  # O(q) where q = len(list_to_remove)
            main_list[:] = [item for item in main_list if item not in remove_set]  # O(n)
            main_list.extend(list_to_add)

        self.num += diff
        update_list(self.lst, lst_add, lst_del)

    def __eq__(self, other: 'object') -> bool:
        if isinstance(other, StoreValue):
            return self.num == other.num and \
                set(self.lst) == set(other.lst)
        return False

    def __ne__(self, other: 'object') -> bool:
        return not self.__eq__(other)

    def add(self, other: 'StoreValueDiff'):
        self.update(other.diff, other.lst_del, other.lst_add)

    def __sub__(self, other: 'StoreValue') -> 'StoreValueDiff':

        def list_diff(list1: List[str], list2: List[str]) -> Tuple[List[str], List[str]]:
            set1 = set(list1)  # Convert list1 to set for faster lookups
            set2 = set(list2)  # Convert list2 to set for faster lookups

            # Calculate items to add and remove
            to_add = list(set1 - set2)  # Items in list2 but not in list1
            to_remove = list(set2 - set1)  # Items in list1 but not in list2
            return to_add, to_remove

        return StoreValueDiff(self.num - other.num, *list_diff(self.lst, other.lst))

    def __mul__(self, num: int) -> 'StoreValueDiff':
        if num == +1:
            return StoreValueDiff(self.num, self.lst, [])
        if num == -1:
            return StoreValueDiff(-1 * self.num, [], self.lst)
        assert False

    def __repr__(self) -> str:
        return f"{self.num}, {self.lst}"

# condition "21015"
def WhenFaceApplyThisInternal(card_finder: CardTypeMin,
                            condition: Callable[['Effect'], bool],
                            get_new_value: Callable[['Effect', 'CardFace'], StoreValue],
                            apply: Callable[['Effect','CardFace', 'StoreValueDiff', bool], None],
                            ignore_flip: bool,
                            change_on_event: EventType,
                            works_for_all_cards: bool=False,
                            works_in_the_victory_display: bool=False, # 40006
                            incite_only: int|None=None,
                            abilities: List[Ability]|None=None,
                            buffs: List[Type['Buff']]|None=None,
                            ) -> 'Ability':
    from game.ability.factory import AbilityFactory
    from game.operate.worlds import Worlds
    from game.operate.effects import Effects
    from game.card.face.card_type import Treachery

    def when_this_in_play(effect: 'Effect', message: 'Message.WhenCardEnterPlay') -> Any:
        # this = effect.this.CastTo(Environment|Attachment|Villain|SideScheme|Support)
        this = effect.this
        apply_faces: Dict['CardFace', StoreValue] = {}
        unapply_effects: Dict['CardFace', List['Effect']] = {}

        def get_old_value(face: 'CardFace') -> 'StoreValue':
            # if not new_card_finder.Check(face):
            #     return 0
            if ignore_flip:
                for check_face in [face] + face.card.back_faces:
                    if check_face in apply_faces:
                        return apply_faces[check_face]
                return StoreValue()
            else:
                if face not in apply_faces:
                    return StoreValue()
                return apply_faces[face]

        def unapply_environment(face: 'CardFace', diff: 'StoreValueDiff') -> Any:
            unapply_environment_internal(face, diff)
            Message.AfterCardApply_Text([face], effect, -1)

        def unapply_environment_internal(face: 'CardFace', diff: 'StoreValueDiff') -> Any:
            nonlocal unapply_effects
            nonlocal apply_faces
            if diff.is_empty():
                return

            assert diff.is_lt_0()

            Effects.UnRegister(unapply_effects[face])
            unapply_effects[face] = []
            apply_faces[face].update(diff.diff, [], diff.lst_del)
            # Fix "01140"
            # Fix 1704384860, ally limit
            if face.IsThisFaceUp() or ignore_flip:
                apply(effect, face, diff, False)

        def apply_environment_internal(face: 'CardFace', diff: 'StoreValueDiff') -> Any:
            nonlocal unapply_effects
            nonlocal apply_faces

            if diff.is_empty():
                return None

            if face not in apply_faces:
                apply_faces[face] = StoreValue()
            apply_faces[face].update(diff.diff, diff.lst_add, [])
            
            apply(effect, face, diff * +1, True)

            # assert face not in unapply_effects
            if face in unapply_effects:
                # Fix "45103b"
                # assert unapply_effects[face] == []
                Effects.UnRegister(unapply_effects[face])
                # for unapply_effect in unapply_effects[face]:
                #     unapply_effect.UnRegisterSelf()
            unapply_effects[face] = []


            if ignore_flip:
                unapply_effect = face.effect.Registers(
                    AbilityFactory.WhenCardLeavePlay(
                        AbilityType.Temp0,
                        "This",
                        lambda check_effect, check_message:
                            unapply_environment(check_message.trigger, diff * -1),
                    )
                )
            else:
                unapply_effect = face.effect.Registers(
                    AbilityFactory.WhileThisStateUpdate(
                        AbilityType.Temp0,
                        lambda check_effect, check_message:
                            unapply_environment(check_message.trigger, diff * -1),
                    )
                )
            unapply_effects[face] += unapply_effect

        ################################################################################
        #
        def try_apply_environment(face: 'CardFace|Literal["All"]', message: 'Message2'):
            apply_face: List['CardFace'] = []
            unapply_face: List['CardFace'] = []
            def process(face: 'CardFace'):
                if face.card.state.is_leaving_play:
                    return
                if face.card.state.is_flipping:
                    return
                if face.card.state.is_setting_as:
                    return

                new_val = get_new_value(effect, face)
                old_val = get_old_value(face)

                if new_val != old_val:
                    diff = new_val - old_val
                    if diff.diff < 0 or diff.lst_del:
                        # Fix "03024"
                        unapply_environment_internal(face, diff)
                        unapply_face.append(face)
                    if diff.diff > 0 or diff.lst_add:
                        apply_environment_internal(face, diff)
                        apply_face.append(face)
                pass

            # update = False
            if abilities != None:
                # Fix for "50070"
                if OnEvent.Faceup in message.on_events:
                    assert isinstance(message, TriggerMessage)
                    process(message.trigger)
            elif incite_only:
                # Fix for "39035"
                if OnEvent.Reveal in message.on_events:
                    assert isinstance(message, TriggerMessage)
                    if Treachery.IsType(message.trigger) and \
                        message.trigger.card.area.flags.is_revealing:
                        diff = get_new_value(effect, message.trigger) - StoreValue()
                        apply(effect, message.trigger, diff, True)
                        message.trigger.effect.RegisterTemp(
                            AbilityFactory.AfterCardsMoved(
                                AbilityType.Temp0,
                                message.trigger,
                                lambda moved_effect, moved_message:
                                    apply(effect, message.trigger, diff * -1, False),
                            ),
                            unregister_after_exec=True
                        )
            elif face == "All":
                if works_for_all_cards:
                    faces = [x.face for x in this.card.world.object_manager.card_dict.values()]
                else:
                    faces = [x for x in unapply_effects if len(unapply_effects[x]) > 0] + \
                        [x for x in Worlds.GetOnFieldCards(effect) if \
                            Condition.CheckWhichCard(card_finder, x, effect)
                        ]

                    faces = [x for x in faces if x.IsThisFaceUp() and x.IsInPlay()]

                for face in Types.RemoveDuplicates(faces):
                    process(face)
            else:
                process(face)
            if apply_face:
                Message.AfterCardApply_Text(apply_face, effect, +1)
            if unapply_face:
                Message.AfterCardApply_Text(unapply_face, effect, -1)

        if condition(effect) and not this.is_treat_as_if_blank:
            try_apply_environment("All", message)

        def check_this_is_in_play() -> bool:
            if works_in_the_victory_display:
                return this.card.area.flags.is_victory_display
            else:
                return this.IsInPlay()

        def new_condition(check_effect: 'Effect', message: 'Message2'):
            # Not from `Operation.FaceGain`
            # message.by_message != None and \
            # check_effect != message.by_effect and \
            return not this.is_treat_as_if_blank and \
                check_this_is_in_play() and \
                condition(check_effect)

        # check_when_events.append(
        #     Message.WhenCardEnterPlay, Message.WhenCardLeavePlay, Message.AfterCardEnterPlay, Message.AfterCardLeavePlay, Message.WhenVillainWouldAdvance
        # )
        # check_when_events = list(set(check_when_events))
        try_apply_all_effects = this.effect.Registers(
            *Condition.GetEventAbilities(
                change_on_event,
                AbilityType.Temp0,
                new_condition,
                lambda check_effect, message:
                    try_apply_environment("All", message)
            )
        )

        def unapply_all_environment():
            update_faces: List['CardFace'] = []
            # Fix "49037" "41018" "33020", dictionary changed size during iteration
            for face in list(apply_faces.keys()):
                # if face in unapply_effects:
                diff = apply_faces[face]
                if diff != 0:
                    unapply_environment_internal(face, diff * -1)
                    update_faces.append(face)
            if update_faces:
                Message.AfterCardApply_Text(update_faces, effect, -1)

        undo_apply_effects = this.effect.Registers(
            *Condition.GetEventAbilities(
                change_on_event,
                AbilityType.Temp0,
                lambda check_effect, message:
                    not condition(check_effect),
                lambda check_effect, message:
                    unapply_all_environment()
            )
        )

        def process_when_treat_as_blank(effect: 'Effect', message: 'Message.WhenCardTreatAsIfBlank') -> None:
            if effect.this.is_treat_as_if_blank or not effect.this.IsFaceUp():
                unapply_all_environment()
            elif condition(effect):
                try_apply_environment("All", message)

        check_blank_effects = this.effect.Registers(
            AbilityFactory.WhenCardTreatAsIfBlank(
                "This",
                process_when_treat_as_blank,
            )
        )

        def when_this_leave_play() -> Any:
            Effects.UnRegister(undo_apply_effects, try_apply_all_effects, check_blank_effects)
            unapply_all_environment()

        if works_in_the_victory_display:

            this.effect.RegisterTemp(
                AbilityFactory.WhileThisStateUpdate(
                    AbilityType.Temp0,
                    lambda effect, message:
                        when_this_leave_play(),
                    conditions=[
                        lambda effect, message:
                            not this.card.area.flags.is_victory_display
                    ],
                    include_enter_play=True
                ),
                unregister_after_exec=True,
            )

        else:

            this.effect.RegisterTemp(
                AbilityFactory.WhileThisStateUpdate(
                    AbilityType.Temp0,
                    lambda effect, message:
                        when_this_leave_play(),
                ),
                unregister_after_exec=True,
            )

    return AbilityFactory.WhenCardEnterPlay(
        AbilityType.NonKeyword,
        "This",
        when_this_in_play,
        include_face_changes=True,
    )

