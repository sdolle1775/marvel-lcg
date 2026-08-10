from cards.pack import *
from game.effect.rule import GameRule


AVATAR_OF_LOKI = CardFinder(trait="AVATAR OF LOKI", card_type=Villain)
TRUE_LOKI = CardFinder(name="Loki, God of Lies", card_type=Villain)


def FindAvatarOfLoki(effect: 'Effect') -> 'Villain|None':
    for villain in Worlds.GetVillains(effect):
        if villain.HasTrait("AVATAR OF LOKI"):
            return villain
    return None


def FindTrueLoki(effect: 'Effect') -> 'Villain|None':
    faces = Worlds.FindCardsOnField(effect, TRUE_LOKI)
    return faces[0].CastTo(Villain) if faces else None


def FindSynergyEnvironment(effect: 'Effect', name: str) -> 'Environment|None':
    face = Worlds.FindCardOnField(effect, name=name, card_type=Environment)
    return face.CastTo(Environment) if face else None


def ResolveStageTwoFocus(effect: 'Effect', player: 'Player') -> bool:
    """Resolve Loki II's focus instruction once an avatar is available."""
    avatar = FindAvatarOfLoki(effect)
    if not avatar:
        return False

    focus = next(
        (
            attachment
            for attachment in avatar.GetAttachedAttachments()
            if attachment.IsName("Intense Focus") or attachment.IsName("Total Focus")
        ),
        None,
    )
    if Worlds.IsExpert(effect):
        if focus and focus.IsName("Intense Focus"):
            # Loki II flips the attachment; Total Focus is not revealed.
            focus.card.Flip(effect, call_reveal=False)
    elif not focus:
        set_aside_focus = Worlds.GetSetAsideAreaCards(
            effect,
            CardFinder(name="Intense Focus", card_type=Attachment),
        )
        if set_aside_focus:
            set_aside_focus[0].Reveal(player, effect)
    return True


def PlaceSynergyCounters(name: str, size: int|Literal["1*"]) -> Callable[['Effect'], None]:
    def place(effect: 'Effect') -> None:
        environment = FindSynergyEnvironment(effect, name)
        if environment:
            maximum = Worlds.GetPlayerNumIcon(effect)
            Faces.PlaceCountersOn(
                [environment],
                size,
                'synergy',
                effect,
                maximum=maximum,
            )
    return place


def PlaceShatterCountersOnTheAvatarOfLokivillain(
    size: int|Literal["1*", "2*", "3*", "5*"],
    effect: 'Effect',
) -> int|None:
    avatar = FindAvatarOfLoki(effect)
    if avatar:
        return Faces.PlaceCountersOn([avatar], size, 'shatter', effect)
    return None


def WhenDefeatedPlaceShatterCountersOnTheAvatarOfLokivillain(
    size: int|Literal["1*", "2*", "3*", "5*"],
    action: Callable[['Effect', 'Message.WhenUnitBeDefeated'], None]|None=None,
) -> 'Ability':
    def when_defeated(effect: 'Effect', message: 'Message.WhenUnitBeDefeated') -> None:
        PlaceShatterCountersOnTheAvatarOfLokivillain(size, effect)
        if action:
            action(effect, message)

    return AbilityFactory.WhenUnitBeDefeated(
        AbilityType.WhenDefeated,
        "This",
        when_defeated,
    )


def WhenDefeatedPlaceShatterAndSynergy(
    shatter: int,
    synergy_name: str,
) -> 'Ability':
    def extra(effect: 'Effect', message: 'Message.WhenUnitBeDefeated') -> None:
        Unused(message)
        PlaceSynergyCounters(synergy_name, 1)(effect)

    return WhenDefeatedPlaceShatterCountersOnTheAvatarOfLokivillain(
        shatter,
        extra,
    )


def GetRandomSetAsideAvatar(effect: 'Effect') -> 'Villain|None':
    avatars = Worlds.GetSetAsideAreaCards(effect, AVATAR_OF_LOKI)
    if not avatars:
        return None
    return Rand.RandomChoice(avatars, effect).CastTo(Villain)


def _swap_physical_avatar(
    fading: 'Villain',
    next_avatar: 'Villain',
    effect: 'Effect',
    reset_health: bool = True
) -> 'Villain':
    """Swap both faces of two physical avatar cards while retaining attachments."""
    active_card = fading.card
    aside_card = next_avatar.card
    old_fading = fading
    old_fronts = [face for face in active_card.back_faces if face.HasTrait("AVATAR OF LOKI")]
    next_backs = list(aside_card.back_faces)
    assert old_fronts and next_backs
    old_front = old_fronts[0].CastTo(Villain)

    new_front = active_card.SwapCard(next_avatar, effect).CastTo(Villain)

    active_card.back_faces = next_backs
    active_card.printed_faces = [new_front, *next_backs]
    for face in [new_front, *next_backs]:
        face.card = active_card
    # Set-aside villain faces have not entered play, so their encounter-deck
    # references are uninitialized. Initialize both sides now that this
    # physical avatar is the active villain.
    new_front.SetEncounterDeck(fading.encounter_deck)

    aside_card.face = old_front
    aside_card.back_faces = [old_fading]
    aside_card.printed_faces = [old_front, old_fading]
    old_front.card = aside_card
    old_fading.card = aside_card

    if reset_health:
        new_front.ResetHealth(effect)
    for attachment in new_front.GetAttachedAttachments():
        if attachment.IsName("Intense Focus"):
            bonus = Worlds.ConvertPerPlayerIconToInt("2*", effect)
            new_front.GainHealthAndMaxHealth(bonus, effect)
        elif attachment.IsName("Total Focus"):
            bonus = Worlds.ConvertPerPlayerIconToInt("3*", effect)
            new_front.GainHealthAndMaxHealth(bonus, effect)
    new_front.SetActive(effect)
    return new_front


def SwapAvatarWithRandomSetAside(effect: 'Effect') -> 'Villain|None':
    active = Worlds.FindVillain(effect)
    next_avatar = GetRandomSetAsideAvatar(effect)
    if not active or not next_avatar:
        return None
    if active.HasTrait("ILLUSION"):
        return _swap_physical_avatar(active, next_avatar, effect)

    # Stories and Lies swaps an undefeated avatar. Flip the outgoing physical
    # card to its illusion face only long enough to use the same safe swap path.
    active.card.Flip(effect, call_reveal=False)
    fading = active.card.face.CastTo(Villain)
    return _swap_physical_avatar(fading, next_avatar, effect, reset_health=False)


def ShatterTheIllusion(effect: 'Effect') -> None:
    fading = effect.this.CastTo(Villain)
    shatter = fading.GetCounters('shatter')
    Faces.RemoveCountersOn([fading], "All", 'shatter', effect)
    # Counters belong to a face in this engine. Clear the just-flipped avatar
    # face as well so it does not retain stale shatter counters while set aside.
    for face in fading.card.back_faces:
        if face.HasTrait("AVATAR OF LOKI"):
            face.CastTo(CanPlaceCounter).SetCounters(0, 'shatter', effect)

    true_loki = FindTrueLoki(effect)
    if true_loki and shatter:
        # Shatter damage is dealt by the scenario, not by the player who
        # happened to reveal Fading Figment. A game-rule effect prevents
        # Worlds Collide's player-damage restriction from blocking it.
        true_loki.TakeDamage(fading, shatter, GameRule(fading))

    if not Worlds.IsGameOver(effect):
        next_avatar = GetRandomSetAsideAvatar(effect)
        if next_avatar and fading.IsInPlay():
            _swap_physical_avatar(fading, next_avatar, effect)

        # Shatter damage can reveal Loki II while the active physical card is
        # showing Fading Figment. Resolve his focus instruction after the new
        # avatar face is restored.
        if true_loki and true_loki.card.face.paper.card_id == "55027b":
            ResolveStageTwoFocus(effect, effect.world.GetFirstPlayer())

    if not Worlds.IsGameOver(effect):
        Players.ForEachPlayer(
            effect,
            lambda player: player.DealEncounterCards(1, effect),
        )


def AddDefeatShatterCounters(
    avatar: 'Villain',
    effect: 'Effect',
) -> int:
    PlaceShatterCountersOnTheAvatarOfLokivillain("5*", effect)
    # PlaceCountersOn returns only the number added by this operation. The
    # Fading Figment must inherit the Avatar's total, including counters that
    # were already present before the defeat interrupt resolved.
    total_shatter = avatar.GetCounters('shatter')
    for face in avatar.card.back_faces:
        if face.HasTrait("ILLUSION"):
            face.CastTo(CanPlaceCounter).SetCounters(
                total_shatter,
                'shatter',
                effect,
            )
    return total_shatter


def AvatarWouldBeDefeated() -> 'Ability':
    def avatar_defeated(effect: 'Effect', message: 'Message.WhenUnitWouldBeDefeated') -> None:
        avatar = effect.this.CastTo(Villain)
        message.SetBeInstead(effect)
        AddDefeatShatterCounters(avatar, effect)
        # The illusion face has infinite hit points, but Unit2 checks the
        # shared physical card's current health as it enters play. Keep that
        # value above zero so the flip does not recursively defeat the same
        # avatar before Fading Figment's reveal effect can resolve.
        avatar.SetHealth(1, effect)
        avatar.card.Flip(effect)

    return AbilityFactory.WhenUnitWouldBeDefeated(
        AbilityType.ForcedInterrupt,
        "This",
        avatar_defeated,
    )


def FadingFigment(synergy_name: str) -> Sequence['Ability']:
    def revealed(effect: 'Effect', message: 'Message.WhenCardRevealed') -> None:
        Unused(message)
        ShatterTheIllusion(effect)
        PlaceSynergyCounters(synergy_name, "1*")(effect)

    return [
        AbilityFactory.WhenThisRevealed(None, revealed),
    ]


def FocusAbilities(bonus_per_player: int, *, total: bool=False) -> Sequence['Ability']:
    def focus_revealed(effect: 'Effect', message: 'Message.WhenCardRevealed') -> None:
        count = Worlds.ConvertPerPlayerIconToInt("2*", effect)
        Worlds.DiscardEncounterCards(count, effect)
        Players.ForEachPlayer(
            effect,
            lambda player: player.DiscardDeckTopCards(5, effect),
        )

        if total:
            scepter = Search.EncounterCard(
                effect,
                include_discard_pile=True,
                name="Dark Scepter",
                card_type=Attachment,
            )
            if scepter:
                scepter.Reveal(message.GetToPlayer(), effect)
            avatar = FindAvatarOfLoki(effect)
            if avatar and (not scepter or not scepter.IsInPlay()):
                Faces.GiveStatus([avatar], "Tough", effect)

    return [
        AbilityFactory.AttachToFaceWhenPutIntoPlay(AVATAR_OF_LOKI),
        *AbilityFactory.GiveKeywordToAttached(
            AVATAR_OF_LOKI,
            health=lambda effect: Worlds.ConvertPerPlayerIconToInt(
                f"{bonus_per_player}*",
                effect,
            ),
            attack=1,
            scheme=1,
            steady=1,
        ),
        AbilityFactory.WhenThisRevealed(None, focus_revealed),
    ]
