from typing import Final
from core import *
from game.card.face import *
from game.effect import *
from game.deck import *

class SelectorEnd:
    def __init__(self,
                # Process rule
                peek: bool=False,
                not_move: bool=False,
                not_shuffle: bool=False,
                display_in_target_order: bool=False,
                full_search_display_faces: Sequence['CardFace']=(),
                full_search_decks: Sequence['Deck']=(),
                force_choose: bool=False,
                ):
        self.peek       = peek
        self.not_move   = not_move
        self.not_shuffle: Final = not_shuffle
        self.display_in_target_order: Final = display_in_target_order
        self.full_search_display_faces = list(full_search_display_faces)
        self.full_search_decks = list(full_search_decks)
        self.force_choose = force_choose
        self._full_search_display_is_explicit = bool(
            full_search_display_faces or full_search_decks
        )

    def ResetDetectedFullSearchDisplay(self) -> None:
        if self._full_search_display_is_explicit:
            return
        self.full_search_display_faces = []
        self.full_search_decks = []
        self.force_choose = False

    def EnableFullSearchDisplay(
        self,
        decks: Sequence['Deck'],
        *,
        force_choose: bool=False,
    ) -> None:
        if force_choose:
            self.full_search_decks = Types.RemoveDuplicates([
                *self.full_search_decks,
                *[deck for deck in decks if not deck.flags.is_discards],
            ])
        for deck in decks:
            for face in deck.Get(True):
                if face not in self.full_search_display_faces:
                    self.full_search_display_faces.append(face)
        self.force_choose = force_choose and bool(self.full_search_display_faces)

    def Process(self, effect: 'Effect', targets: Sequence['CardFace']) -> bool:
        # Shuffle
        do_move = True
        if self.not_move:
            do_move = False
        if not self.not_shuffle:
            SelectorEnd.DoShuffle(
                effect,
                targets,
                do_move,
                False,
                additional_decks=self.full_search_decks,
            )
        elif do_move:
            SelectorEnd.DoMove(effect, targets, do_move)
        return True

    def OnSelectTargetFailure(self, effect: 'Effect', peeked_faces: Sequence['CardFace']) -> None:
        if self.peek and peeked_faces:
            SelectorEnd.DoShuffle(
                effect,
                peeked_faces,
                False,
                True,
                additional_decks=self.full_search_decks,
            )

    @staticmethod
    def DoMove(effect: 'Effect', faces: Sequence['CardFace'], need_move: bool) -> List['Deck']:
        from game.operate.faces import Faces

        places: List[Deck] = []
        moved_faces: List['CardFace'] = []

        for face in faces:
            deck = face.card.area
            if deck.flags.is_deck:
                if not face.card.IsFaceUp():
                    moved_faces.append(face)
                    places.append(face.card.area)

        if need_move:
            if moved_faces:
                Faces.MoveAllToProcessingArea(moved_faces, effect)
        else:
            # if moved_faces:
            #     CardFace.PeekCards(moved_faces, effect)
            pass

        return places

    @staticmethod
    def DoShuffle(effect: 'Effect',
                  faces: Sequence['CardFace'],
                  need_move: bool,
                  is_failure: bool,
                  *,
                  additional_decks: Sequence['Deck']=(),
                  ) -> None:
        from game.deck.deck import Deck

        places: List[Deck] = SelectorEnd.DoMove(effect, faces, need_move)
        places.extend(additional_decks)

        if need_move or is_failure or additional_decks:
            for deck in Types.RemoveDuplicates(places):
                if deck.GetSize() == 0:
                    # Send.AfterDeckRunOut(deck)
                    # deck.ShuffleWithDiscardPile(True, effect)
                    pass
                else:
                    deck.Shuffle(effect)
