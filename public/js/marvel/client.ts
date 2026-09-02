import { ButtonSetting, ClientPreferences, Setting } from './settings.js'
import { Game } from './game.js'
import { Cards } from './cards.js'
import { WorldDescriptor } from './descriptor.js'
import { Effect } from './effect.js'
import { Button } from './buttons.js'
import { Music } from './music.js'
import { Notify } from './notify.js'
import { HistoryLog } from './history.js'
import { AskOptionPayload } from './data.js'
import { Replay } from './replay.js'
import { UI } from './ui.js'
import { CardAnimation } from './card_animation.js'
import { Lib } from './lib.js'
import { ErrorDialog } from './error_dialog.js'
import { MouseSync } from './mouse.js'
import { FullSearchPresentation } from './full_search_presentation.js'

function showRes() {
    let resource_div = ""
    for( let i = 0; i<Game.world_descriptor.players.length; i++ ) {
        let player_json = Game.world_descriptor.players[i]
        const resources = player_json.resources
        for (const c of resources) {
            resource_div += `<div class='res-${c.toLowerCase()}'></div>`
        }
    }
    document.querySelector(`#player-all-resources`)!.innerHTML = resource_div
}

export class Client {
    private static last_turn_id    = -2
    private static last_notify_id = 0
    private static first_start_ui  = true

    static ws = class WebSocketHandler {
        static ws: WebSocket | null = null;
        static messageQueue: string[] = [];
        static isProcessing: boolean = false;

        static init(): void {
            function getUrlParameters(url: string): string {
                const params = url.split('?')[1];
                return params ? params : '';
            }

            const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
            const url = `${protocol}://${window.location.host}/ws?${getUrlParameters(window.location.href)}`;
            WebSocketHandler.ws = new WebSocket(url);
    
            WebSocketHandler.ws.onmessage = async (event: MessageEvent) => {
                if (event.data) {
                    WebSocketHandler.messageQueue.push(event.data);
                    await WebSocketHandler.processQueue();
                }
            };
    
            WebSocketHandler.ws.onopen = () => {
                UI.onConnected()
                WebSocketHandler.ws?.send(ClientPreferences.connectionSettings())
                Client.doSyncGame();
            };
    
            WebSocketHandler.ws.onerror = (error: Event) => {
                console.error("WebSocket error:", error);
                UI.onLostConnect();
            };
    
            WebSocketHandler.ws.onclose = () => {
                WebSocketHandler.ws = null;
                UI.onLostConnect();
            };
        }
    
        static async processQueue(): Promise<void> {
            if (WebSocketHandler.isProcessing) return;
            WebSocketHandler.isProcessing = true;
    
            while (WebSocketHandler.messageQueue.length > 0) {
                // const message = WebSocketHandler.messageQueue.shift();
                const message = WebSocketHandler.messageQueue.pop()
                WebSocketHandler.messageQueue.length = 0
                if (message) {
                    const parsedMessage = JSON.parse(message);
                    // Check if the message contains mouse position data
                    if (parsedMessage.mouse_position) {
                        MouseSync.handle(parsedMessage)
                    } else {
                        // Handle other types of messages
                        await Client.handleGetId(parsedMessage);
                    }
                }
            }
    
            WebSocketHandler.isProcessing = false;
        }
    
        static doSyncGame(): void {
            if (WebSocketHandler.ws) {
                WebSocketHandler.ws.send(`Connected ${window.location.href}`);
            } else {
                WebSocketHandler.init();
            }
        }
    }

    static doSyncGame() {
        Client.ws.doSyncGame()
    }

    static doConnect() {
        UI.last_game_id = -1
        // Game.setGameOver(false)
        if( Setting.is_hot_seat ) {
            Setting.player_id = 0
        }
        Client.ws.init()
    }

    static doReconnect(e: HTMLButtonElement) {
        e.classList.add('reconnecting')
        e.disabled = true
        Client.doConnect()
    }

    static async syncFullSearchPreference(playerId: number, enabled: boolean) {
        await fetch(`client_settings?p=${playerId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                show_deck_during_full_search: enabled,
            }),
        })
    }

    private static tryGetAsk() {
        if( Game.asking_players.length > 0 ) {
            if( Setting.is_watch ) {
                if( !Game.asking_players.includes(Game.forced_on_player) ) {
                    UI.focusOnPlayer(Game.asking_players[0])
                }
            }
            else if( Game.asking_players.includes(Setting.player_id) || Setting.is_hot_seat ) {
                CardAnimation.cleanEvent()
                Client.doGetAsk()
            }
        }
    }

    private static async handleGetId(original_data: any) {
        if( Game.is_pause ) {
            return
        }

        interface NotifyDescriptor {
            id: number;
            level: string;
            category: string;
            text: string;
        }

        interface FrameDescriptor {
            render_id: number;
            game_id: number;
            ask_players: number[];
            full_search_presentation_players: number[];
            remaining_time: number;
            max_timeout: number;
            notify_texts: NotifyDescriptor[];
            current_step_id: number;
            max_replay_step_id: number;
            debug_message: string;
            player_id: number;
            total_players: number;
            show_deck_during_full_search: boolean;
            // is_skipping: boolean;
        }

        const notifyData = (obj: any): NotifyDescriptor => {
            return {
                id: obj['id'],
                level: obj['level'],
                category: obj['category'],
                text: obj['text'],
            };
        };

        const data: FrameDescriptor = {
            render_id           : original_data['render_id'],
            game_id             : original_data['game_id'],
            ask_players         : original_data['ask_players'],
            full_search_presentation_players: original_data['full_search_presentation_players'] ?? [],
            remaining_time      : original_data['remaining_time'],
            max_timeout         : original_data['max_timeout'],
            notify_texts        : original_data['notify_texts'].map((y: string) => notifyData(JSON.parse(y))),
            current_step_id     : original_data['current_step_id'],
            max_replay_step_id  : original_data['max_replay_step_id'],
            debug_message       : original_data['debug_message'],
            player_id           : original_data['player_id'],
            total_players       : original_data['total_players'],
            show_deck_during_full_search: original_data['show_deck_during_full_search'] ?? false,
            // is_skipping      : original_data['is_skipping'],
        };

        // if( Setting.is_hot_seat && data.ask_players.length > 0 ) {
        //     UI.updateCurrentPlayer(data.ask_players[0])
        // }

        Game.total_players = data.total_players

        if( UI.last_game_id == data.game_id &&
            Game.current_step_id == data.current_step_id &&
            Client.last_turn_id == data.render_id &&
            Lib.array.equals(Game.asking_players, data.ask_players) &&
            Lib.array.equals(
                Game.full_search_presentation_players,
                data.full_search_presentation_players,
            ) &&
            data.full_search_presentation_players.length == 0 &&
            ClientPreferences.showDeckDuringFullSearch(data.player_id) == data.show_deck_during_full_search &&
            // Game.asking_players == data.ask_players &&
            data.notify_texts.length == 0
        ) {
            return
        }

        Game.current_step_id = data.current_step_id

        let notify_texts: NotifyDescriptor[] = [];
        if( data.notify_texts.length > 0 ) {
            notify_texts = data.notify_texts;
        }

        UI.setDebugMessage('debug', data.debug_message)

        Game.asking_players = data.ask_players
        Game.full_search_presentation_players = data.full_search_presentation_players
        const fullSearchPreferenceChanged = (
            ClientPreferences.showDeckDuringFullSearch(data.player_id) !=
            data.show_deck_during_full_search
        )
        ClientPreferences.setShowDeckDuringFullSearch(
            data.player_id,
            data.show_deck_during_full_search,
        )
        FullSearchPresentation.closeIfInactive(
            data.full_search_presentation_players,
        )
        Button.updateFullSearchButton()
        console.log(`render: ${data['render_id']} game_id: ${data['game_id']} ask: ${Game.asking_players}`)
        if( data.render_id == -1 ) {
            UI.prompt.setPromptGameOver()
            return
        }
        if( UI.last_game_id != data.game_id ) {
            // Game.setGameOver(false)
            console.log("forced_on_player", Game.forced_on_player, UI.last_game_id)
            Client.last_turn_id = -2
            Game.forced_on_player = -1
            UI.global_first_create = true
            if( Game.world_descriptor ) {
                Game.world_descriptor.render_id = 0
            }
            UI.last_game_id = data.game_id
            UI.firstGameSync()
            // Lib.alert("!!!")
            // when server restart, the `last_notify_id` will be 1
            Client.last_notify_id = 0
        }
        let remaining_time = data.remaining_time
        let max_timeout = data.max_timeout

        if( Client.last_turn_id != data.render_id ) {
            // if( !UI.global_first_create && Client.last_turn_id <= data.render_id-5 ) {
            //     UI.global_first_create = true
            // }
            UI.hideAllTimerBar()
            Client.last_turn_id = data.render_id
            await Client.doGetWorld()
            // if( !data.is_skipping ) {
            //     await Client.doGetWorld()
            // } else {
            //     await Client.doGetWorld()
            //     UI.setPromptWait()
            // }
            Button.clean()

            const step = data.current_step_id
            const max_step = Math.max(data.max_replay_step_id, step)
            if( Button.goto_id ) {
                Button.goto_id.style.width = `${(max_step-1)*20}px`
                Button.goto_id.max = max_step.toString()
                Button.goto_id.value = step.toString()
                Button.goto_id_value.value = step.toString()
            }
        }

        for( let notify_text of notify_texts ) {
            
            if( notify_text.id <= Client.last_notify_id ) {
                continue
            }

            Client.last_notify_id = notify_text.id

            if( notify_text.category == 'STATISTICS' ) {
                if( notify_text.text.startsWith("Achievement: ") ) {
                    let text = notify_text.text.replace("Achievement: ", "")
                    text = text.replaceAll("_", " ")
                    Notify.showAchievement(text)
                }
                else {
                    if( notify_text.text.includes(" -> ") ){
                        if( Setting.statistics_all || Setting.is_debug ) {
                            let the_notify_text = notify_text.text.replace(" -> ", ":<br/>-&gt; ")
                            Notify.showStatisticsText(the_notify_text)
                        }
                    }
                    else {
                        let params = notify_text.text.split(" ")
                        Notify.showStatistics(params[0], params[1], Number(params[2].replace(/[^\d]/g, '')))
                    }
                }
            } else {
                if( notify_text.category == "COMMAND" ) {
                    Notify.showCommand(notify_text.text)
                } else {
                    Notify.create(notify_text.category, notify_text.level, notify_text.text)
                }
            }
        }

        if( fullSearchPreferenceChanged && Game.world_descriptor ) {
            Cards.render.printCards()
            Effect.updateHighLight()
        }

        if( Game.asking_players.length > 0 ) {
            UI.updateTimerBar(remaining_time, max_timeout, Game.world_descriptor.round_id, Game.current_step_id)
            Client.tryGetAsk()
        }
        if( Game.full_search_presentation_players.length > 0 && !Setting.is_watch ) {
            let presentationPlayer = Setting.player_id
            if( Setting.is_hot_seat ) {
                presentationPlayer = Game.full_search_presentation_players[0]
                Setting.player_id = presentationPlayer
                UI.focusOnPlayer(presentationPlayer)
                Button.updateFullSearchButton()
            }
            if( Game.full_search_presentation_players.includes(presentationPlayer) ) {
                FullSearchPresentation.fetch(presentationPlayer)
            }
        }
    }

    private static clean_render_info(renderInfo: string) {
        renderInfo = renderInfo.replace(/\[\(\d+,(\w+)(,\w+)*\) ([^\]]+) \?\]/g, "<span class='log-card'>???</span>");
        renderInfo = renderInfo.replace(/\[\((\d+),(\w+)(,\w+)*\) ([^\]]+)\]/g, 
            (match, p1, p2, p3, p4) => {
                let span = Cards.getSpanTextHelp(p1, p2, p4)
                // `<span class='log-card' 
                //     onmouseover='HoverCard.showLogImage(${p1}, "${p2}")' 
                //     onmouseleave='HoverCard.set(null)' 
                //     onclick='Debug.clicked_card_id.value = "${p2}"' 
                //     data-id='${p2}' 
                //     oncontextmenu=__oncontextmenu__
                //     >${p4}</span>`;
                return span
            }
        );
        return Lib.game.cleanResText(renderInfo)
    }

    private static async doGetWorld() {
        // if( Game.game_over ) {
        //     return true
        // }
        // else if( !UI.ctrl_key && (!UI.can_get || CardFace.has_anime) || Game.is_pause) {
        //     return false
        // }

        Effect.select_effect_obj.clear()
        UI.selectCountClear()

        const response = await fetch(`get_world?p=0`);
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }
        const data = await response.json();

        Game.world_descriptor = new WorldDescriptor(data)
        console.log("world_state render_id:", Game.world_descriptor.render_id)

        if( true || Client.last_turn_id == Game.world_descriptor.render_id )
        {
            if( Game.world_descriptor.prompt_last_text.startsWith("\n--- Game Over ---") ) {
                Game.setGameOver(true)
            } else {
                Game.setGameOver(false)
            }
            let ms = 0
            ms = UI.setTurnId(Game.world_descriptor.round_id, Game.current_step_id)

            let should_play_sound = ""

            if (Game.asking_players.length === 0) {
                // Play sound if it exists
                const sound_name = Game.world_descriptor.sound_name;
                if (sound_name) {
                    should_play_sound = sound_name
                }
            }

            if( should_play_sound == "phase" ) {
                Music.doPlaySound(`${should_play_sound}.wav`);
                should_play_sound = ""
            }

            function render() {

                UI.setDebugMessage('world', `${Game.world_descriptor.render_id}`)

                if( Setting.is_hot_seat && Game.world_descriptor.active_card_ids.length > 0 ) {
                    const object_id = Game.world_descriptor.active_card_ids[0]
                    const card_div = Cards.getDiv(object_id)
       
                    function checkPlayerClasses(div: HTMLElement): number {
                        const playerClasses: { [key: string]: number } = {
                            'player-0': 0,
                            'player-1': 1,
                            'player-2': 2,
                            'player-3': 3
                        };
                    
                        // Iterate over the keys of the playerClasses object
                        for (let class_name of Object.keys(playerClasses)) {
                            if (div.classList.contains(class_name)) {
                                return playerClasses[class_name];
                            }
                        }
                        return -1; // Return -1 if none of the classes are found
                    }
                    if( card_div != null && card_div.parentElement != null ) {
                        let player = checkPlayerClasses(card_div.parentElement!)
                        if( player != -1 && player != Game.forced_on_player ) {
                            UI.focusOnPlayer(player)
                        }
                    }
                }

                if( should_play_sound ) {
                    Music.doPlaySound(`${should_play_sound}.wav`);
                }

                let prompt_text = Game.world_descriptor.prompt
                UI.event_name = Game.world_descriptor.event_name

                if( Game.world_descriptor.render_id <= 1 ) {
                    Game.forced_on_player = -1
                }
                if( Game.world_descriptor.render_id >= 0 ) {
                    if( Game.total_players != Game.world_descriptor.players.length || 
                        Game.forced_on_player == -1
                    ) {
                        Game.forced_on_player = -1
                        function updateLeftSideBar() {
                            for (let j = 0; j <= 3; j++) {
                                const playerBtn = document.querySelector(`#player-${j}-btn`)!;
                                if( Game.total_players == 1 ) {
                                    playerBtn.classList.add("hide")
                                }
                                else
                                if( j < Game.total_players ) {
                                    playerBtn.classList.remove("hide")
                                } else {
                                    playerBtn.classList.add("hide")
                                }
                            }
                            const playersPin = document.querySelector(`#players-pin`)!
                            const playersAllInOne = document.querySelector(`#player-all-in-one`)!
                            const hideNoActionCards = document.querySelector(`#hide-no-action-cards`)!
                            const allHandCards = document.querySelector(`#all-hand-cards`)!
                            const alwaysShowMinions = document.querySelector(`#always-show-minions-belong`)!

                            // Hand filtering and pinning are useful in solo play
                            // too. Only controls that switch or combine players
                            // are multiplayer-specific.
                            playersPin.classList.remove('hide');
                            hideNoActionCards.classList.remove('hide')
                            allHandCards.classList.remove('hide');

                            if( Game.total_players > 1 ) {
                                if( !Setting.is_hot_seat ) {
                                    playersPin.classList.add('clicked');
                                }
                                playersAllInOne.classList.remove('hide');
                                alwaysShowMinions.classList.remove('hide')
                                // playersAllInOneHandCards.classList.remove('hide');
                            } else {
                                playersAllInOne.classList.add('hide');
                                alwaysShowMinions.classList.add('hide')
                                // playersAllInOneHandCards.classList.add('hide');
                            }
                        }
                        updateLeftSideBar()
                    }
                    if( Game.forced_on_player == -1 ) {
                        UI.focusOnPlayer(Setting.player_id)
                    }
                }

                Client.first_start_ui = false

                Cards.max_card_object_id = Game.world_descriptor.max_card_object_id

                if (Game.asking_players.length === 0) {
                    // else if( UI.event_name == 'AfterCardRemovedCounter' ) {
                    //     // scheme remove threat will cause thwart unit move 2 times
                    //     // Client.current_event = "attack"
                    // }

                    console.log("UI.event_name", UI.event_name);

                    CardAnimation.setEvent(UI.event_name, prompt_text)

                } else {
                    CardAnimation.cleanEvent()
                }

                if( !prompt_text.startsWith("--") ) {
                    let div_prompt_text = Game.world_descriptor.prompt_last_text

                    if( div_prompt_text.startsWith("\n--- Game Over ---") ) {
                        Game.setGameOver(true)
                        div_prompt_text = ""
                    } else {
                        Game.setGameOver(false)
                    }

//                     const text = `Error occurred (Please undo):
// Traceback (most recent call last):
//   File "D:\Repository\marvel-lcg\.\game\ability\effect_invoke.py", line 229, in ResolveSelfInternal
//     self.InvokeOperation(message)
//   File "D:\Repository\marvel-lcg\.\game\ability\effect_invoke.py", line 70, in InvokeOperation
//     raise exc
//   File "D:\Repository\marvel-lcg\.\game\ability\effect_invoke.py", line 64, in InvokeOperation
//     effect.ability.operation(effect, message) # type: ignore
//   File "D:\Repository\marvel-lcg\.\game\ability\factory\resources.py", line 353, in generate_resource
//     raise GameSignal_UndoRequest()
// game.exceptions.exceptions.GameSignal_UndoRequest: UndoRequest
// `
//                     ErrorDialog.showError(text)

                    if( div_prompt_text.startsWith("Error occurred") ) {
                        ErrorDialog.showError(div_prompt_text)
                    }
                    else {
                        UI.prompt.setPromptText(Client.clean_render_info(div_prompt_text))
                        HistoryLog.addText(Game.world_descriptor.render_id, Client.clean_render_info(prompt_text))
                    }
                }

                CardAnimation.active_card_object_ids = Game.world_descriptor.active_card_ids
                // card
                Cards.render.update(Game.world_descriptor)

                UI.setPhaseText(Game.world_descriptor.phase)
                showRes()

                wait_next_frame()
            }

            ms = Math.max(ms, CardAnimation.rest_anime_time())
            console.log("Anime: anime_time", ms)

            if (ms === 0 || Client.first_start_ui || UI.hold_ctrl) {
                render();
            } else {
                setTimeout(render, ms);
            }
        } else {
            wait_next_frame()
        }

        function wait_next_frame() {
            if( UI.hold_ctrl ) {
                Client.onUpdateFinished()
            } else {
                setTimeout(() => {
                    Client.onUpdateFinished()
                }, CardAnimation.rest_anime_time());
            }
            console.log("Anime: wait_next_frame", CardAnimation.rest_anime_time())
        }
        UI.resetDelayTime()
    }

    private static doGetAsk() {
        // if( Game.game_over ) {
        //     return
        // }
        // console.log('get_ask')
        Effect.select_effect_obj.clear()
        UI.selectCountClear()

        var ajax = new XMLHttpRequest();
        ajax.onreadystatechange = function () {
            if (this.readyState == 4 && this.status == 200) {
                if( this.responseText == undefined || this.responseText == "" ) {
                    return
                }
                // console.log(this.responseText)
                Effect.response_json_ask = new AskOptionPayload(JSON.parse(this.responseText))
                if( Effect.response_json_ask.options.length > 0 )
                {
                    if( Setting.is_hot_seat ) {
                        // The returned option is authoritative when multiple
                        // hotseat players are waiting for input. The asking-player
                        // list alone cannot identify which prompt was returned.
                        const prompt_player_id = Effect.response_json_ask.options[0].bind_player_id
                        if( prompt_player_id != undefined ) {
                            Setting.player_id = prompt_player_id
                            if( Game.forced_on_player != prompt_player_id ) {
                                UI.focusOnPlayer(prompt_player_id)
                            }
                        }
                        else if( !Game.asking_players.includes(Game.forced_on_player) ) {
                            UI.focusOnPlayer(Game.asking_players[0])
                        }
                        Button.updateFullSearchButton()
                    }

                    // effect
                    const div_prompt_text = Effect.response_json_ask.prompt_text
                    UI.prompt.setPromptText(Client.clean_render_info(div_prompt_text))
                    UI.event_name = Effect.response_json_ask.event_name
                    UI.is_in_play_turn = UI.event_name == "WhenPlayerInTurn"
                    Effect.setOptions()

                    // CardEffect.updateButtons(options)
                    Cards.render.update(Game.world_descriptor)

                    UI.setPhaseText(Game.world_descriptor.phase)
                    showRes()

                    // Replay
                    if( Setting.is_auto_test && UI.error_occurred_text ) {
                        Replay.doReplay(true, 1, true)
                        setTimeout(() => {
                            window.location.reload()
                        }, 1000);
                    }
                    else if( Effect.response_json_ask.replay_input && ButtonSetting.is_replay ) {
                        Replay.doReplay()
                    }

                }
            }
        };
        if( Setting.is_hot_seat && Game.asking_players.length > 0 ) {
            // TODO: FIX when has multiple asking player
            Setting.player_id = Game.asking_players[0]
        }
        ajax.open("GET", `get_ask?p=${Setting.getPlayerIds()}`, true);
        ajax.send();
    }

    static onUpdateFinished(forced: boolean=false) {

        if( Game.world_descriptor && (forced || !Setting.is_watch && !Game.is_pause && !Setting.cheat_show_all_cards) ) {
            // if( CardFace.has_anime ) {
            //     Lib.alert("!!!")
            // }
            let render_id = Game.world_descriptor.render_id
            let ajax = new XMLHttpRequest();
            let text = `client_updated?p=${Setting.getPlayerIds()}&r=${render_id}&g=${UI.last_game_id}`
            ajax.open("GET", text, true);
            console.log("sync:", text)
            // ajax.onreadystatechange = function () {
            //     if (this.readyState == 4 && this.status == 200) {
            //     }
            // }
            ajax.send();
        }
    }
}
