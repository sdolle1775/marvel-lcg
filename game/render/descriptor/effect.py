from core import *

# data.ts
@dataclass
class EffectDescriptor:

    @dataclass
    class Payment:
        cost: str
        payment: List[Dict[int, str]] # `effect_id` `res_text`
        rule: List[str]

    id: int                         # game object id
    name: str
    bind_id: int                    # link `CardState.id`
    bind_player_id: int             # [0,1,2,3]
    all_legal_targets: List[int]    # link `CardState.id`
    target_num_range: List[int]     # target [min, max] number
    target_payment: Dict[int, Payment]

    select_rule: str
    select_rule_param: Tuple[int, int]
    target_must_include_traits: List[str] # For "26035"

    failure_reason: str             # not null if fail
    is_search: bool
    display_in_target_order: bool
    full_search_display_targets: List[int]
    # Timing-window choices may contain the same registered effect more than
    # once, bound to different triggering conditions.  Keep `id` as the real
    # effect id for card highlighting and use this optional opaque id only for
    # selecting the rendered option.
    choice_id: str = ""
    # Exact one-of-one targets are outcomes, not player choices.  The client
    # can submit the selected ability without opening a target-selection step.
    automatic_targets: List[int] = field(default_factory=list)
    # Most exact one-of-one outcomes can be submitted immediately. Optional
    # Interrupts, Responses, optional ability choices, and basic defense
    # declarations are exceptions: keep the sole target preselected, but let
    # the player explicitly confirm or cancel.
    automatic_submit: bool = True

    # is_ex_effect check `AskOption`
