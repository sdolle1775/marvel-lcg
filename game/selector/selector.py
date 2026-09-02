from typing import Final
from core import *
from game.card.face import *
from game.effect import *
from game.selector import *

from game.selector.selector_target import SelectorTarget
from game.selector.selector_filter import SelectorFilter
from game.selector.selector_range import SelectorRange
from game.selector.selector_end import SelectorEnd
from game.selector.selector_rule import SelectorRule

CATEGORY_NAME = "SELECTOR"

class Selector(metaclass=Tracker.Meta):

    def __init__(self,
                selector_target : 'SelectorTarget',
                selector_rule   : 'SelectorRule',
                selector_filter : 'SelectorFilter',
                selector_range  : 'SelectorRange',
                selector_end    : 'SelectorEnd',
                *,
                after_select_fn : Callable[['Effect'], None]|None=None,
                check_again_fn  : Callable[['Effect', Sequence['CardFace']], bool]|None=None,
                target_text: 'CardFinderHelper.FINDER_TARGET|Literal["TeamUp"]|None'=None,
                ):
        self.selector_target    : Final = selector_target
        self.selector_rule      : Final = selector_rule
        self.selector_filter    : Final = selector_filter
        self.selector_range     : Final = selector_range
        self.selector_end       : Final = selector_end

        self.after_select_fn    : Final = after_select_fn
        self.check_again_fn     : Final = check_again_fn
        self.target_text        : Final = target_text

        self.peeked_faces: List['CardFace'] = []

        # Only work for `SetTarget2` `SetTarget3`
        # When False, SetTarget2 must have all illegal targets
        self.is_optional = True
        self.condition              : Callable[['Effect'], bool]|None = None

    @property
    def is_search(self) -> bool:
        return self.selector_end.peek

    @property
    def force_choose(self) -> bool:
        return self.selector_end.force_choose

    def GetRandomTarget(self, legal_faces: Sequence['CardFace'], effect: 'Effect') -> Sequence['CardFace']:
        from game.operate.rand import Rand
        return Rand.RandomChoice2(legal_faces, self.selector_range.GetTargetMax(effect, legal_faces), effect)

    def EnableFullSearchDisplay(self, effect: 'Effect', faces: Sequence['CardFace']) -> None:
        selector_end = self.selector_end
        selector_end.ResetDetectedFullSearchDisplay()
        if selector_end._full_search_display_is_explicit or \
            not self.is_search or \
            selector_end.not_move or \
            selector_end.not_shuffle or \
            selector_end.display_in_target_order:
            return

        candidate_decks = Types.RemoveDuplicates([
            face.card.area
            for face in faces
            if face.card.area.flags.is_deck
        ])
        full_search_display_decks = []
        for deck in candidate_decks:
            deck_faces = deck.Get(True)
            if deck_faces and all(face in faces for face in deck_faces):
                full_search_display_decks.append(deck)

        if full_search_display_decks:
            world = effect.world
            scene = getattr(world, "scene", None)
            controller_manager = getattr(world, "controller_manager", None)
            force_choose = bool(
                scene and
                controller_manager and
                scene.UseLegacyFullSearchPrompt(
                    controller_manager.replay.current_step_id
                )
            )
            selector_end.EnableFullSearchDisplay(
                full_search_display_decks,
                force_choose=force_choose,
            )

    def GetAllLegalTargets(self, effect: 'Effect', referential_effect: 'Effect|None'=None, *, just_check: bool=False) -> Sequence['CardFace']:
        from game.operate.referential import Referential

        legal_faces = self.selector_target.GetAllTarget(effect, self.selector_range)
        self.peeked_faces = legal_faces
        self.EnableFullSearchDisplay(effect, legal_faces)

        if referential_effect == None:
            referential_effect = effect
        # Fix "27030a"
        legal_faces = Referential.Filter(self.selector_filter.finder, legal_faces, referential_effect)
        legal_faces = self.selector_filter.FilterLegalTargets(legal_faces, effect)
        legal_faces = self.selector_rule.Process(legal_faces, effect, self.selector_range)

        if not legal_faces:
            return []

        # Should not run when only check has target
        if self.selector_rule.random and not just_check:
            return self.GetRandomTarget(legal_faces, effect)
        else:
            return legal_faces

    def GetTargetRange(self, effect: 'Effect', faces: Sequence['CardFace']) -> Tuple[int, int]|None:
        from game.effect.effect import EffectFailure

        # Legacy full-search confirmations allowed a recorded zero-target
        # choice. New inspection-only viewers never enter this path.
        if self.force_choose and faces == []:
            return (0, 0)

        target_range = [
            self.selector_range.GetTargetMin(effect, faces),
            self.selector_range.GetTargetMax(effect, faces)
        ]

        if len(faces) < target_range[0]:
            return None

        target_range[1] = min(len(faces), target_range[1])
        if target_range[1] == 0:
            if target_range[0] > target_range[1]:
                effect.failures.Set(effect.initiator, EffectFailure.MaxTargetsIsZero)
                return None

        if target_range[0] > target_range[1] > 0:
            target_range[0] = target_range[1]

        if faces == [] and target_range[0] > 0:
            # We can comment out this to let no target effect show in ask list
            effect.failures.Set(effect.initiator, EffectFailure.NoFilterTargets)
            return None

        return (target_range[0], target_range[1])

    def HasLegalTargets(self, effect: 'Effect') -> bool:
        faces = self.GetAllLegalTargets(effect, just_check=True)
        return len(faces) >= self.selector_range.GetTargetMin(effect, faces)

    ################################################################################
    #
    def AfterSelectTargets(self, effect: 'Effect', targets: Sequence['CardFace'], range: Tuple[int, int]) -> bool:
        if not self.selector_rule.AfterSelectTargets(effect, targets, range):
            return False

        if self.check_again_fn:
            if not self.check_again_fn(effect, targets):
                return False

        if self.after_select_fn:
            self.after_select_fn(effect)

        if self.selector_end:
            self.selector_end.Process(effect, targets)

        return True

    def IfSelectTargetFailure(self, effect: 'Effect') -> None:
        if self.selector_end:
            self.selector_end.OnSelectTargetFailure(effect, self.peeked_faces)

