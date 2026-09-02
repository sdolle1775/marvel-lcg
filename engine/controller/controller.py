from core import *
from build import Build
from engine.device import *
from engine.controller import *
from engine.lib import Json
from engine.log import Log, Notify
from game.ability import *
from game.message import *
from game.render import *
from game.scene.replay import *
from game.exceptions import *

CATEGORY_NAME = "CONTROLLER"

@dataclass
class ControllerPreferences:
    show_deck_during_full_search: bool = False

@dataclass
class ChoiceOneOverride:
    """Alternate rendered identities for timing-window effect candidates."""

    descriptors: Sequence['EffectDescriptor']
    replay_texts: Sequence[str]
    prepare: Callable[[int], 'Effect|None']
    convert_replay_id: Callable[[str], 'str|None']
    select_only: bool = False
    selected_index: int|None = None

class Controller:

    def __init__(self, player_id: int, devices: 'DeviceManager', manager: 'ControllerManager'):
        self.player_id = player_id
        self.preferences = ControllerPreferences()

        self.manager = manager
        self.render, self.input = devices.CreateDevices(self)

        devices.AddController(self)

    def SetShowDeckDuringFullSearch(self, enabled: bool) -> None:
        self.preferences.show_deck_during_full_search = enabled

    def PresentFullSearch(
        self,
        card_ids: Sequence[int],
        legal_target_ids: Sequence[int],
        target_range: Tuple[int, int],
        prompt_text: str,
    ) -> None:
        replay = self.manager.replay
        if not self.preferences.show_deck_during_full_search or \
            self.manager.skip.is_skipping or \
            replay.is_replay:
            return

        self.input.PresentFullSearch(
            list(card_ids),
            list(legal_target_ids),
            target_range,
            prompt_text,
        )

    @property
    def game(self):
        return self.manager.game

    @property
    def world(self):
        return self.manager.game.world

    def PrintStepID(self) -> str:
        return self.manager.replay.PrintStepID()

    ################################################################################
    #
    # GetInput
    @staticmethod
    def CanSubmitEmptyChoice(
        is_forced: bool|Literal["Forced_Action"],
        effect_descriptors: Sequence['EffectDescriptor'],
    ) -> bool:
        if not is_forced:
            return True
        return (
            len(effect_descriptors) == 1
            and effect_descriptors[0].target_num_range[0] == 0
        )

    def ChoiceOne(self, effect_list: Sequence['Effect'], by_effect: 'Effect|None', message: 'Message2', priority: 'TimingPriority', is_forced: bool|Literal["Forced_Action"], choice_override: 'ChoiceOneOverride|None'=None) -> Tuple['Effect|None', bool]:
        from game.scene.replay.operation import CardEffectInt

        controller_manager = self.manager

        if len(effect_list) == 0:
            return None, False
        if not self.game.state.is_running:
            return None, False

        # if DeviceManager.is_skipping:
        #     play_json = Render.ToPlayJson()
        #     DeviceManager.play_json_crc = CRC(str(play_json))
        # else:
        #     DeviceManager.play_json_crc = Render.last_render_crc
        controller_manager.replay.calculated_crc = message.world.render.CalculateCRC()

        if choice_override:
            choice_override.selected_index = None
            effect_descriptors = list(choice_override.descriptors)
            assert len(effect_descriptors) == len(effect_list)
        else:
            effect_descriptors = [effect.Render(by_effect, self.player_id) for effect in effect_list]

        # Load replay
        is_puzzle = message.world.scene.is_puzzle
        replay_input, read_ok = controller_manager.replay.GetReplayOperation(is_puzzle)
        if not read_ok:
            if controller_manager.skip.SetIsSkipping(False):
                message.world.render.PresentForceNoWait()

        if replay_input:
            replay_debug_cmd = replay_input.effect.GetDebugCommand()
        else:
            replay_debug_cmd = ""

        replay_inputs_max_size = controller_manager.replay.GetReplayOperationLen()

        if replay_input:
            fallthrough_input = Json.Dumps(replay_input.effect)
        else:
            fallthrough_input = "{}"

        from game.test import Test

        if Test.IsInTesting():
            test_text = f"\r{controller_manager.replay.current_step_id} / {replay_inputs_max_size}\r"
            Log.Test(test_text)
            # if DeviceManager.step_index == replay_inputs_max_size:
            #     Game.SetGameOver(True)
            #     return None, False
        elif controller_manager.skip.is_skipping:
            test_text = f"\r{controller_manager.replay.current_step_id} / {replay_inputs_max_size}\r"
            Log.Print(test_text, end="")
        else:
            # Log.Debug(
            #     CATEGORY_NAME,
            #     self.PrintStepID()
            # )
            pass

        # Check for current event, debug only
        if replay_input and controller_manager.replay.replay_step_id < controller_manager.skip.skip_to:
            event = replay_input.event
            if str(message) != event and not str(message).endswith(event) and str(message).split()[-1] != event.split()[-1]:
                Log.Warn(CATEGORY_NAME, f'Last message different, hope "{event}" but get "{message}"')
                # DebugBreak()

        select_cmd = CommandDescriptor()
        select_effect: 'Effect|None' = None

        fallthrough_cmd = Json.LoadsAs(fallthrough_input, CommandDescriptor)
        convert_fallthrough_input = fallthrough_input

        Notify.Clean()

        try:
            # Convert replay data
            def convert_replay_data(check_object: CommandDescriptor) -> str:
                found_effect: 'Effect|None' = None
                if choice_override:
                    new_effect_id = choice_override.convert_replay_id(check_object.id)
                    if new_effect_id == None:
                        raise LookupError(
                            f"Could not restore timing choice: {check_object.id}; "
                            f"available={list(choice_override.replay_texts)}"
                        )
                    for index, descriptor in enumerate(effect_descriptors):
                        choice_id = descriptor.choice_id or str(descriptor.id)
                        if choice_id == new_effect_id:
                            found_effect = choice_override.prepare(index)
                            break
                else:
                    new_effect_id = str(CommandDescriptor.FindNewEffectId(check_object.id, effect_list))
                    for check_effect in effect_list:
                        if check_effect.object_id == int(new_effect_id):
                            found_effect = check_effect
                            break
                assert found_effect
                resources_effects = found_effect.checker.cost_for_different_target.GetAllPayEffects()

                new_resource_ids: List[str] = []
                for resources_effect_str in check_object.resources:
                    new_resource_ids.append(str(CommandDescriptor.FindNewEffectId(resources_effect_str, resources_effects)))

                command = CommandDescriptor(
                    new_effect_id,
                    check_object.targets,
                    new_resource_ids
                )
                return Json.Dumps(command)
            if fallthrough_cmd.id and not replay_debug_cmd:
                convert_fallthrough_input = convert_replay_data(fallthrough_cmd)
        except Exception as exc:
            # A replay recorded before trigger-aware identities were stable
            # may be ambiguous after code changes. Stop fast-forwarding and
            # ask again rather than applying the original runtime id to the
            # wrong ability.
            if choice_override and fallthrough_cmd.id:
                Log.Warn(CATEGORY_NAME, str(exc))
                replay_input = None
                fallthrough_input = "{}"
                convert_fallthrough_input = "{}"
                controller_manager.skip.SetIsSkipping(False)

        if by_effect != None and by_effect.GetDisplayName() == 'End Phase':
            message_name = "End Turn"
        else:
            message_name = message.name

        while True:
            user_input = ''

            if not user_input:
                # if controller_manager.replay.replay_step_id >= controller_manager.skip.skip_to or not replay_input:
                #     controller_manager.skip.SetIsSkipping(False)
                #     if self.world:
                #         self.world.render.PresentForce()
                # if controller_manager.skip.skip_to:
                if controller_manager.replay.replay_step_id >= controller_manager.skip.skip_to or \
                    not replay_input: # Fix skip
                    if controller_manager.skip.SetIsSkipping(False):
                        if self.world:
                            self.world.render.PresentForceNoWait()

                if (controller_manager.skip.is_skipping or controller_manager.replay.replay_step_id < controller_manager.skip.skip_to) and replay_input:
                    user_input = convert_fallthrough_input
                    Log.DebugSilent("FAST_UNDO", f'{controller_manager.replay.current_step_id}, {user_input}, {len(effect_list)}')
                    
                    # Hack fix quickstrike
                    # if "Response" in fallthrough_input and \
                    #     "01066" in fallthrough_input and \
                    #     "WhenUnitBeingAttack" in message_name:
                    #     user_input = None
                    #     if controller_manager.skip.SetIsSkipping(False):
                    #         if self.world:
                    #             self.world.render.PresentForceNoWait()
                    #     from core.lib.beep import Beep
                    #     Beep.Warning()

            # Hack
            # if fallthrough_obj.id.startswith(":"):
            #     user_input = convert_fallthrough_input
            # else:
            #     user_input = ""
            #     if DeviceManager.is_skipping:
            #         DeviceManager.SetIsSkipping(False)
            #     DeviceManager.SetSkipTo(0)
            #     if not DeviceManager.is_skipping:
            #         Render.PresentForce() # For update UI
            #     pass

            if not user_input:
                # Tip, replay input
                if fallthrough_input or True:
                    
                    text = """    {}
    Effect: [{}]
    Target: {}
    Cost:   {}""".format(
                        replay_input.event if replay_input else None,
                        fallthrough_cmd.id,
                        [f"{card}" for card in fallthrough_cmd.targets],
                        [f"{effect}" for effect in fallthrough_cmd.resources])

                    from game.render.symbol import Symbol
                    text = Symbol.AddColor(text)
                    Log.Debug(CATEGORY_NAME, self.PrintStepID())
                    Log.Debug(CATEGORY_NAME, text)
                # for effect in effect_list:
                #     # Log.Debug("{:03} {:30} {} {}".format(
                #     #     effect.object_id,
                #     #     f'[{effect.ability.name if effect.ability.name else effect.this.name}]',
                #     #     [face.card.object_id for face in effect.for_select_targets],
                #     #     [pay.object_id for pay in effect.for_select_pay_resource_effects]))

                #     # Log.Debug(CATEGORY_NAME, "c{:<3} {:30} {}".format(
                #     #     effect.object_id,
                #     #     f'[{effect.ability.name if effect.ability.name else effect.this.name}]',
                #     #     [face.card.object_id for face in effect.all_legal_targets])
                #     # )
                #     pass
                check_message = message
                prompt_text = ""

                if isinstance(check_message, Message.WhenPlayerChooseAbility) and \
                    check_message.by_effect.bind_message:
                    if check_message.step[1] > 1:
                        prompt_text = f"({check_message.step[0]}/{check_message.step[1]})"
                    check_message = check_message.by_effect.bind_message

                if not prompt_text and check_message.prompt:
                    prompt_text = check_message.prompt.text_no_symbol

                # Get input here
                from engine.device.manager.base import AskOptionPayload
                user_input = self.input.GetInput(
                    AskOptionPayload(
                        options_json=Json.Dumps(effect_descriptors),
                        ability_type=priority.name,
                        event_name=message_name,
                        prompt_text=prompt_text,
                        show_cancel=is_forced == False,
                        replay_input=fallthrough_input,
                    )
                )

                if user_input == None:
                    return None, True

                if not Build.release:
                    if controller_manager.console.TryBreak(message.world):
                        continue

                if controller_manager.console.Execute(message.GetReplayText(), message.world, effect_list):
                    return None, True
                if controller_manager.replay.is_updated:
                    return None, True
                if message.world.is_game_over:
                    return None, False
                if not self.game.state.is_running:
                    return None, False

                # When click auto
                if controller_manager.skip.is_skipping or controller_manager.skip.skip_to > 0:
                    user_input = convert_fallthrough_input
                    controller_manager.console.SetCommand(replay_debug_cmd, message.world)
                    if controller_manager.console.Execute(message.GetReplayText(), message.world, effect_list):
                        return None, True
                Log.Debug(CATEGORY_NAME, "Input:", user_input)

            else:
                controller_manager.console.SetCommand(replay_debug_cmd, message.world)
                if controller_manager.console.Execute(message.GetReplayText(), message.world, effect_list):
                    return None, True

            try:
                input_effect = Json.LoadsAs(user_input, CommandDescriptor)
                if choice_override:
                    input_effect_id: int|str = str(input_effect.id)
                    is_empty_choice = input_effect_id in ("", "0")
                else:
                    input_effect_id = CardEffectInt(input_effect.id)
                    is_empty_choice = input_effect_id == 0
                if is_empty_choice:
                    if not Controller.CanSubmitEmptyChoice(is_forced, effect_descriptors):
                        # A stale replay or client can submit an empty command even
                        # though this forced choice still requires targets. Stop
                        # replaying that command and leave the prompt open.
                        replay_input = None
                        fallthrough_input = "{}"
                        convert_fallthrough_input = "{}"
                        if controller_manager.skip.SetIsSkipping(False):
                            if self.world:
                                self.world.render.PresentForceNoWait()
                        continue
                    break

                # Update selected
                selected_index = None
                for index, effect in enumerate(effect_descriptors):
                    descriptor_id: int|str = effect.choice_id or effect.id
                    if str(descriptor_id) == str(input_effect_id):
                        if choice_override:
                            select_effect = choice_override.prepare(index)
                            if select_effect == None:
                                return None, True
                            choice_override.selected_index = index
                        else:
                            select_effect = effect_list[index]
                        selected_index = index
                        break
                    else:
                        select_effect = None
                if select_effect == None and replay_debug_cmd:
                    continue
                # Hack
                if select_effect == None and len(effect_descriptors) == 1 and input_effect.resources == []:
                    selected_index = 0
                    if choice_override:
                        select_effect = choice_override.prepare(0)
                        if select_effect == None:
                            return None, True
                        choice_override.selected_index = 0
                    else:
                        select_effect = effect_list[0]

                assert select_effect != None, f"{select_effect=}"

                if choice_override and choice_override.select_only:
                    assert selected_index != None
                    select_cmd = CommandDescriptor(
                        choice_override.replay_texts[selected_index],
                        [],
                        [],
                    )
                    break

                select_effect.targets.clear()
                submitted_targets = list(input_effect.targets)
                if not submitted_targets and selected_index != None:
                    submitted_targets = list(
                        effect_descriptors[selected_index].automatic_targets
                    )
                for check_target in submitted_targets:
                    found = False
                    for target in select_effect.context.all_legal_targets:
                        if target.card.object_id == CardEffectInt(check_target):
                            select_effect.context.targets_internal.append(target)
                            found = True
                            break
                    # TODO, update to warning
                    assert found, f"{select_effect=}"
                if select_effect.targets == [] and select_effect.context.target_range[0] > 0:
                    assert False, f"{select_effect=} {select_effect.targets=} {select_effect.context.target_range=}"

                if len(select_effect.targets) < select_effect.context.target_range[0] and \
                    select_effect.ability.selectors[0] and \
                    not select_effect.ability.selectors[0].selector_range.select_rule.startswith('VillainAnd'):
                    assert False, f"{select_effect=} {select_effect.targets=} {select_effect.context.target_range=}"

                select_effect.context.paid_this_res_effects.clear()
                for resources in input_effect.resources:
                    taraget = select_effect.targets[0] if select_effect.targets != [] else None
                    effect = select_effect.checker.cost_for_different_target.FindPayEffect(taraget, CardEffectInt(resources))
                    assert effect, f"{select_effect=}"

                    select_effect.context.paid_this_res_effects.append(effect)

                select_cmd = CommandDescriptor(
                    choice_override.replay_texts[selected_index]
                    if choice_override and selected_index != None
                    else select_effect.GetReplayText(),
                    [x.GetReplayText() for x in select_effect.targets],
                    [x.GetReplayText() for x in select_effect.context.paid_this_res_effects])
                break

            except Exception as exc:
                if controller_manager.skip.SetIsSkipping(False):
                    if self.world:
                        self.world.render.PresentForceNoWait()

                info = Log.FailedTrace(CATEGORY_NAME, exc, no_take_as_error=True)
                message.world.render.ErrorOccurred(info + "UndoRequest\n")
                from core.lib.beep import Beep
                Beep.Warning()
                Log.Debug(CATEGORY_NAME, f'Input:  {user_input}')

        operation = OperationDescriptor(
            controller_manager.replay.current_step_id,
            message.GetReplayText(),
            select_cmd,
            controller_manager.replay.calculated_crc[0])
        controller_manager.replay.Push(operation)

        self.game.statistics.RecordValue("operation", 1)

        if controller_manager.replay.current_step_id > controller_manager.skip.skip_to:
            if controller_manager.skip.SetIsSkipping(False):
                if self.world:
                    self.world.render.PresentForceNoWait()

        return select_effect, False

    def Render(self):
        return self.render.Render()

