import { Lib } from './lib.js'
import { Setting, ButtonSetting, ClientPreferences } from './settings.js'
import { Game } from './game.js'
import { Cards } from './cards.js'
import { UI } from './ui.js'
import { HistoryLog } from './history.js'
import { SelectStep } from './select.js'
import { Effect } from './effect.js'
import { Notify } from './notify.js'
import { HoverCard } from './hover.js'
import { Music } from './music.js'
import { Replay } from './replay.js'
import { Client } from './client.js'
import { saveAsFile } from '../lib/save_file.js'
import { BtnOk } from './btn_ok.js'
import { CardAnimation } from './card_animation.js'
import { ErrorDialog } from './error_dialog.js'
import { Command } from './command.js'
import { FullSearchPresentation } from './full_search_presentation.js'

////////////////////////////////////////////////////////////////////////////////
//
export class Button{
    static goto_id = document.querySelector("#goto-id") as HTMLInputElement
    static goto_id_value = Button.goto_id?.previousElementSibling as HTMLOutputElement
    private static is_posting = false
    private static full_search_button: HTMLButtonElement|undefined

    static doToggleHistory() {
        HistoryLog.toggle()
    }

    static doGet() {
        Client.doSyncGame()
    }

    static doBtnCancel() {
        if( Game.is_lost_connect || Button.is_posting ||
            BtnOk.btn_end_div.disabled || Effect.isMandatoryHandSizeDiscard()
        ) {
            return
        }
        Button.disablePause()
        Button.doCancel()
    }

    static doBtnOk() {
        if( FullSearchPresentation.dismissIfActive() ) {
            return
        }
        if( Game.is_lost_connect || Button.is_posting || BtnOk.btn_ok_div.disabled || SelectStep.isCard() ) {
            return
        }
        Button.disablePause()
        Button.doPost()
    }

    // static doReplay() {
    //     if( Game.game_over ) {
    //         UI.doGet()
    //     } else {
    //         if( Game.prepared_replay ) {
    //             Button.doBtn()
    //         }
    //     }
    // }

    static doCancel() {
        if( Game.is_lost_connect ) {
            return
        }
        if( Effect.isMandatoryHandSizeDiscard() ) {
            // A player above their hand size must discard down. Keep the
            // mandatory selection open instead of posting an empty command.
            return
        }
        Replay.prepared_replay = false
        if( SelectStep.isCard() || Effect.isExEffect() ||
            Effect.is_in_event == 'response' ||
            Effect.is_in_event == 'interrupt' ||
            Effect.isEndPhaseOrResolveMulligans()
        ) {
            SelectStep.cancel()
            UI.selectCountClear()
            if( Effect.response_json_ask.options[Effect.response_json_ask.options.length-1].name_with_space == 'Cancel' ) {
                Effect.select_effect_obj = Effect.response_json_ask.options[Effect.response_json_ask.options.length-1]
            } else {
                Effect.select_effect_obj.clear()
            }
            Button.doPost(false)
        } else if( SelectStep.isEffect() || SelectStep.isTargets() || SelectStep.isCost() ) {
            Effect.onCancel()
        }
    }

    static doBtnHideOptions(e: HTMLButtonElement) {
        Effect.options_button_div.classList.toggle('hide')
        if( Effect.options_button_div.classList.contains('hide') ) {
            e.classList.add('clicked')
        } else {
            e.classList.remove('clicked')
        }
    }

    static clean() {
        CardAnimation.reset()
        Effect.reset()
        UI.update()
        SelectStep.reset()
    }

    static doPost(press_by_btn = true) {
        // Automatic full-search inspection uses the real selector client-side,
        // but its selections must never enter the gameplay/replay input route.
        if( FullSearchPresentation.isActive() ) {
            return
        }
        if( Game.is_lost_connect ) {
            return
        }
        Replay.prepared_replay = false
        // if( press_by_btn ) {
        //     Game.setGameOver(false)
        // }
        if( SelectStep.isCard() ) {
            return
        }
        else if( SelectStep.isTargets() ) {
            let need_resource = false
            console.log('resources:', Effect.select_effect_obj.getResources())
            if( Effect.select_effect_obj.getResources().length > 0 ) {
                for(const card_div of document.querySelectorAll<HTMLElement>('.card')) {
                    const object_id = Number(card_div.dataset.id!)
                    let effect_ids = Cards.getCard(object_id)!.resources
                    for( let id of effect_ids ) {
                        if(Effect.select_effect_obj.getResources().includes(id)) {
                            card_div.dataset.pay_effect_id = id.toString()
                            need_resource = true
                            break
                        }
                    }
                }
            }
            SelectStep.setCost(true)
            if( !need_resource && press_by_btn ) {
                Button.doPost(false)
            } else {
                Effect.updateHighLight()
            }
        }
        else if( SelectStep.isCost() ) {
            if( Button.is_posting ) {
                return
            }

            let selected_data_text = '{}'
            let bind_player_id = Setting.player_id
            if( Effect.select_effect_obj.id != -1 ) {
                let result_json = {
                    'id': Effect.select_effect_obj.choice_id || Effect.select_effect_obj.id,
                    // 'name': CardEffect.select_effect_obj.name,
                    // 'card': CardEffect.select_effect_obj.bind_id,
                    'targets': [] as number[],
                    'resources': [] as number[]
                }
                for( let x of Effect.select_effect_obj.selected_targets ) {
                    result_json['targets'].push(x)
                }
                for( let x of Effect.select_effect_obj.resources ) {
                    result_json['resources'].push(x)
                }
                selected_data_text = JSON.stringify(result_json)
            }
            if( Effect.select_effect_obj.bind_player_id != undefined ) {
                bind_player_id = Effect.select_effect_obj.bind_player_id
            }
            Effect.select_effect_obj.clear()

            var ajax = new XMLHttpRequest();
            ajax.onreadystatechange = function () {
                if (this.readyState == 4) {
                    Button.is_posting = false
                    if( this.status == 200 ) {
                        SelectStep.setBegin()
                        console.log('post', selected_data_text)
                        UI.update()
                    }
                }
            };

            Button.is_posting = true
            Button.clean()
            let showFullSearch = ClientPreferences.showDeckDuringFullSearch(bind_player_id) ? 1 : 0
            let text = `post?p=${bind_player_id}&show_deck_during_full_search=${showFullSearch}`
            console.log(text)
            ajax.open("POST", text, true);
            ajax.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
            ajax.send(selected_data_text);
        }
    }

    static doEliminate() {
        Button.doDebug(`Eliminate(${Setting.player_id})`)
    }

    static doRedo() {
        Button.doDebug("/skip 0", false)
    }

    static doAuto() {
        Button.doDebug("/step 99999");
    }

    static doNext() {
        Button.doDebug("/step 1", false)
        Replay.prepared_replay = false
    }

    static doDebug(cmd: string, do_sync=true) {
        Button.disablePause()
        BtnOk.setDisable(true)

        var ajax = new XMLHttpRequest();
        ajax.open("GET", "debug?" + cmd, true);
        // TODO: May be use this
        // Game.setGameOver(false)
        do_sync = true
        if( do_sync ) {
            ajax.onreadystatechange = function () {
                if (this.readyState == 4 && this.status == 200) {
                    const text = this.response
                    if( Setting.is_debug ) {
                        Notify.showResponse(text)
                    }
                    Button.clean();
                    Client.doSyncGame();
                }
            }
        }
        ajax.send();
    }

    static doLoad(solt: number) {
        Game.setGameOver(false)
        ErrorDialog.hideError()
        HistoryLog.close()
        Button.doDebug(`/load save_${solt}.json:-1`)
        UI.prompt.setPromptWait()
    }

    static openFile(accept: string='.json', callback: (text: string) => void) {
        // Create a file input element dynamically
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = accept;

        // Trigger the file input click
        fileInput.click();

        // Add an event listener for when a file is selected
        fileInput.addEventListener('change', (event) => {
            const input = event.target as HTMLInputElement;
            if (input.files && input.files.length > 0) {
                const file = input.files[0];
                const reader = new FileReader();

                reader.onload = async function(e) {
                    const fileContent = e.target?.result;
                    if (typeof fileContent === 'string') {
                        const data = fileContent
                        callback(fileContent)
                    }
                };

                reader.readAsText(file);
            }
        });
    }

    static doLoadFile() {
        Button.openFile(".json", (data) => {
            Game.setGameOver(false)
            ErrorDialog.hideError()
            HistoryLog.close()
            UI.prompt.setPromptWait()

            let url = 'load_replay_data'; // URL for the POST request

            if( ButtonSetting.is_replay ) {
                url += "?0"
            } else {
                url += "?-2"
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json', // Set the content type to JSON
                },
                body: JSON.stringify({ data }) // Send the data as JSON
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json(); // Parse the JSON response
            })
            .then(responseData => {
                console.log('Success:', responseData);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        })
    }

    private static doToggleAutoActivate(e: HTMLElement) {
        // HistoryLog.close()
        const class_name = 'no-auto-activate'
        if( e.classList.contains('clicked') ) {
            document.body.classList.remove(class_name)
        } else {
            document.body.classList.add(class_name)
        }
    }

    private static doToggleAutoActivateCheckbox(e: HTMLElement) {
        // HistoryLog.close()
        const class_name = 'hide-auto-activate'
        if( e.classList.contains('clicked') ) {
            document.body.classList.remove(class_name)
        } else {
            document.body.classList.add(class_name)
        }
    }

    static doSave(slot: number) {
        Button.doDebug(`/save save_${slot}.json`);
        const button = document.getElementById(`load-btn-${slot}`) as HTMLButtonElement;
        button.innerHTML = `Step ${Game.current_step_id}`
    }

    static async doSaveFile() {
        const response = await fetch(`save_replay_data`);
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }
        const data = await response.json();
        saveAsFile(data, `save.json`)
    }

    // static disableUndo() {
    //     UI.setPromptWait()
    //     document.querySelector<HTMLButtonElement>('#undo-btn')!.disabled = true
    // }

    // static enableUndo() {
    //     document.querySelector<HTMLButtonElement>('#undo-btn')!.disabled = false
    // }

    static doOldUndo() {
        Game.setGameOver(false)
        ErrorDialog.hideError()
        Button.doDebug("/undo 1", false)
    }

    static doUndo() {
        // document.querySelectorAll('.card').forEach( card_div => {
        //     card_div.classList.remove(ClassName.card_shuffle)
        // })
        Game.setGameOver(false)
        ErrorDialog.hideError()
        BtnOk.clean()
        Button.doDebug("/undo auto", false)
    }

    static disablePause(do_sync = false) {
        Game.is_pause = false
        UI.connection_manager.unpause()
        Button.updatePauseUI()
        Notify.unpause()
        CardAnimation.unpause()
        HoverCard.unPause()
        if( do_sync ) {
            Client.doSyncGame()
        }
    }

    static enablePause() {
        Game.is_pause = true
        UI.connection_manager.pause()
        Button.updatePauseUI()
        Notify.pause()
        CardAnimation.pause()
        HoverCard.pause()
    }

    static updatePauseUI() {
        let e =  document.querySelector("#pause-btn") as HTMLElement
        if( Game.is_pause ) {
            e.classList.add('clicked')
            document.body.classList.add('pause')
            // UI.hideAllTimerBar()
        } else {
            document.body.classList.remove('pause')
            e.classList.remove('clicked')
            Client.onUpdateFinished()
            // Client.doSyncGame();
        }
    }

    static togglePause() {
        if( Game.is_pause ) {
            Button.disablePause(true)
        } else {
            Button.enablePause()
        }
    }

    static doLoadCrash() {
        HistoryLog.close()
        Button.doDebug("/load crash.json:-2")
    }

    static gotoStep(e: HTMLElement) {
        if( Button.goto_id ) {
            HistoryLog.close()
            ErrorDialog.hideError()
            let step = Number(Button.goto_id.value)
            Button.doDebug(`/goto ${step}`)
            UI.prompt.setPromptWait()
        }
    }

    static doToEnd() {
        ErrorDialog.hideError()
        Button.doDebug("/goto end");
        UI.prompt.setPromptWait()
    }

    static backToTurnBegin() {
        ErrorDialog.hideError()
        HistoryLog.close()
        Button.doDebug("/goto turn_begin");
        UI.prompt.setPromptWait()
    }

    static doDebugStart() {
        Button.doDebug("/load debug.json:1");
    }

    static doRestart() {
        Button.doDebug("/restart -1", false)
        // "/undo 9999";
    }

    static doShow() {
        document.body.style.setProperty('--show-debug', `${Setting.showAllCards() ? 1 : 0}`)
        if( Setting.showAllCards() ) {
            document.body.classList.add('show-all-cards')
        } else {
            document.body.classList.remove('show-all-cards')
        }
    }

    static doPlayBGM() {
        Music.playBgm()
    }

    static focusPlayer(num: number) {
        UI.focusOnPlayer(num)
        Button.updateFullSearchButton()
    }

    // static toggleAllInOneHandCards(e: HTMLButtonElement) {
    //     e.classList.toggle('clicked')
    //     Setting.show_all_in_one_hand_cards = !Setting.show_all_in_one_hand_cards
    //     CardFace.UpdateAreaNames()
    //     CardFace.showPrintCards()
    //     CardEffect.updateHighLight()
    // }

    static nextFrame() {
        Client.onUpdateFinished(true)
    }

    static initializeButtons() {
        const parent_div1 = document.getElementById('ex-buttons-1') as HTMLElement
        // Button.createButton3(parent_div1, "block_thread", "debug-only", "", async () => {
        //     const response_block_thread = await fetch("block_thread?");
        //     const text = await response_block_thread.text();
        //     alert(text)
        // })
        // Button.createButton3(parent_div1, "error dialog", "debug-only", "", async () => {
        //     ErrorDialog.showError("This is a text error message")
        // })
        // Button.createButton3(parent_div1, "game over", "debug-only", "", async () => {
        //     Game.setGameOver(true)
        //     Message.showGameOverMessage("Test game over")
        // })

        Button.createButtonBase(parent_div1, {
            text: "Load Crash",
            onClick: () => {Button.doLoadCrash()}
        })

        const parent_div2 = document.getElementById('ex-buttons-2') as HTMLElement
        Button.createButtonBase(parent_div2, {
            text: "Card Tilt",
            property: 'card_tilt',
            onClick: (e) => {
                if( e.classList.contains('clicked') ) {
                    Setting.no_tilt = false
                    // e.classList.add('clicked')
                } else {
                    // window.location.reload();
                }
            },
            callWhenInit: true,
            cookie_name: 'btn_card_tilt'
        })
        Button.createButtonBase(parent_div2, {
            text: "Sound",
            property: 'music_on',
            cookie_name: 'btn_sound'
        })
        Button.createButtonBase(parent_div2, {
            text: "New Badge",
            property: 'new_badge',
            onClick: () => {
                if( ButtonSetting.new_badge ) {
                    document.querySelector('#scene')?.classList.remove('no-new')
                } else {
                    document.querySelector('#scene')?.classList.add('no-new')
                }
            },
            callWhenInit: true,
            cookie_name: 'btn_new_badge'
        })
        Button.createButtonBase(parent_div2, {
            text: "Enhance Fx",
            property: 'enable_enhance_fx',
            onClick: () => {
                UI.changeWeather(UI.weather, true)
            },
            callWhenInit: true,
            cookie_name: 'btn_enhance_fx'
        })
        Button.createButtonBase(parent_div1, {
            text: "Card Text",
            property: 'show_image_text',
            cookie_name: 'btn_image_text'
        })
        Button.createButtonBase(parent_div2, {
            text: "Preview",
            property: 'enable_preview',
            onClick: () => {
                if( ButtonSetting.enable_preview ) {
                    HoverCard.showPreview(true)
                    document.querySelector('#prompt-box-container')!.classList.remove('display-none')
                } else {
                    HoverCard.showPreview(false)
                    document.querySelector('#prompt-box-container')!.classList.add('display-none')
                }
            },
            callWhenInit: true,
            cookie_name: 'btn_preview'
        })

        const parent_div3 = document.getElementById('ex-buttons-3') as HTMLElement
        Button.createButtonBase(parent_div3, {
            text: "QLoad",
            class_name: "do-load",
            id: "load-btn-0",
            onClick: () => {Button.doLoad(0)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Load 1",
            class_name: "do-load",
            id: "load-btn-1",
            onClick: () => {Button.doLoad(1)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Load 2",
            class_name: "do-load",
            id: "load-btn-2",
            onClick: () => {Button.doLoad(2)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Load 3",
            class_name: "do-load",
            id: "load-btn-3",
            onClick: () => {Button.doLoad(3)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Save 1",
            class_name: "do-save",
            onClick: () => {Button.doSave(1)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Save 2",
            class_name: "do-save",
            onClick: () => {Button.doSave(2)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Save 3",
            class_name: "do-save",
            onClick: () => {Button.doSave(3)}
        })
        Button.createButtonBase(parent_div3, {
            text: "Load",
            class_name: "do-load",
            onClick: () => {Button.doLoadFile()}
        })
        Button.createButtonBase(parent_div3, {
            text: "Save",
            class_name: "do-save",
            onClick: () => {Button.doSaveFile()}
        })
        
        const parent_div4 = document.getElementById('ex-buttons-4') as HTMLElement
        Button.createButtonBase(parent_div4, {
            text: "Auto Targeting",
            property: 'auto_target',
            cookie_name: 'btn_auto_targeting'
        })
        Button.createButtonBase(parent_div4, {
            text: "Auto Activate",
            property: "auto_activate",
            onClick: Button.doToggleAutoActivate,
            callWhenInit: true,
            cookie_name: 'btn_auto_activate'
        })
        Button.createButtonBase(parent_div4, {
            text: "Show Auto Activate Checkbox",
            property: "show_auto_activate",
            onClick: Button.doToggleAutoActivateCheckbox,
            callWhenInit: true,
            cookie_name: 'btn_show_aa_checkbox'
        })
        Button.createButtonBase(parent_div4, {
            text: "Auto Pause",
            property: 'pause_when_reveal_or_boost',
            onClick: () => {
                if( ButtonSetting.pause_when_reveal_or_boost ) {
                    document.querySelector('#image-preview-div-center')!.classList.remove("display-none")
                } else {
                    document.querySelector('#image-preview-div-center')!.classList.add("display-none")
                }
                // HistoryLog.close()
            },
            callWhenInit: true,
            cookie_name: 'btn_pause_flip',
        })
        // Button.createButton3(parent_div4, "Load Auto Activate Config", "", "", () => {AutoActivate.doLoadAutoActivateConfig()})
        // Button.createButton3(parent_div4, "Save AA Config", "", "", () => {AutoActivate.saveConfig()})

        Button.createButtonBase(parent_div1, {
            class_name: 'sort-card-btn',
            property: 'sort_hand_cards',
            names: [
                'Sort Hand',
                'By ID',
                'By Type'
            ],
            onClick: () => {Cards.render.printCards()},
            cookie_name: 'btn_sort_hand'
        });
        Button.createButtonBase(parent_div1, {
            class_name: 'sort-card-btn',
            property: 'sort_area_cards',
            names: [
                'Sort Area',
                'By ID',
                'By Name'
            ],
            onClick: () => {Cards.render.printCards()},
            cookie_name: 'btn_sort_area'
        });
        Button.createButtonBase(parent_div1, {
            text: "Restart Turn",
            onClick: () => {Button.backToTurnBegin()}
        })

        // Button.createButton(parent_div1, 'sort-card-btn', '', 'sort_discard_pile_cards', [
        //     'Sort Discard Pile',
        //     'By ID',
        //     'By Type'
        // ], () => {Cards.printCards()});

        const parent_div_left = document.getElementById('left-side-bar') as HTMLElement
        Button.createButtonBase(parent_div_left, {
            text: "P1",
            class_name: "hide",
            id: "player-0-btn",
            onClick: () => {Button.focusPlayer(0)}
        })
        Button.createButtonBase(parent_div_left, {
            text: "P2",
            class_name: "hide",
            id: "player-1-btn",
            onClick: () => {Button.focusPlayer(1)}
        })
        Button.createButtonBase(parent_div_left, {
            text: "P3",
            class_name: "hide",
            id: "player-2-btn",
            onClick: () => {Button.focusPlayer(2)}
        })
        Button.createButtonBase(parent_div_left, {
            text: "P4",
            class_name: "hide",
            id: "player-3-btn",
            onClick: () => {Button.focusPlayer(3)}
        })
        Button.createButtonBase(parent_div_left, {
            text: "M",
            class_name: "hide hide2",
            id: 'always-show-minions-belong',
            property: 'always_show_minions_belong'
        })
        Button.createButtonBase(parent_div_left, {
            text: "A",
            class_name: "hide hide2",
            id: 'player-all-in-one',
            property: 'show_all_players',
            onClick: (e) => {
                Cards.render.printCards()
                Effect.updateHighLight()
            }
        })

        Button.createButtonBase(parent_div_left, {
            text: "H",
            class_name: "hide",
            id: 'all-hand-cards',
            property: 'show_all_hand_cards',
            onClick: (e) => {
                Cards.render.printCards()
                Effect.updateHighLight()
            }
        })
        Button.createButtonBase(parent_div_left, {
            names: ["A", "F", "P"],
            class_name: "hide",
            id: 'hide-no-action-cards',
            property: 'hide_no_action_cards',
            onClick: (e) => {
                console.log('hide_no_action_cards:', ButtonSetting.hide_no_action_cards)
                Cards.render.printCards()
                Effect.updateHighLight()
            }
        })

        Button.createButtonBase(parent_div_left, {
            text: `<i class="fa fa-lock" aria-hidden="true"></i>`,
            class_name: "hide lock",
            id: "players-pin",
            property: 'players_pin'
        })

        const parent_div_right = document.getElementById('right-side-bar') as HTMLElement
        Button.full_search_button = Button.createButtonBase(parent_div_right, {
            text: "Full Search",
            id: "show-deck-during-full-search-btn",
            onClick: () => {
                const playerId = Button.getFullSearchPreferencePlayerId()
                const enabled = !ClientPreferences.showDeckDuringFullSearch(playerId)
                ClientPreferences.setShowDeckDuringFullSearch(playerId, enabled)
                Button.updateFullSearchButton()
                FullSearchPresentation.onPreferenceChanged(playerId, enabled)
                Cards.render.printCards()
                Effect.updateHighLight()
                Client.syncFullSearchPreference(playerId, enabled)
            },
        })
        Button.updateFullSearchButton()
        Button.createButtonBase(parent_div_right, {
            text: "Log",
            onClick: () => {Button.doToggleHistory()}
        })
        Button.createButtonBase(parent_div_right, {
            text: "Pause",
            class_name: "release-only",
            id: "pause-btn",
            onClick: () => {Button.togglePause()}
        })
        Button.createButtonBase(parent_div_right, {
            text: "Undo",
            id: "undo-btn",
            onClick: () => {Button.doUndo()}
        })
        Button.createButtonBase(parent_div_right, {
            text: "Redo",
            onClick: () => {Button.doRedo()}
        })
        Button.createButtonBase(parent_div_right, {
            text: "Break",
            class_name: "debug-only",
            onClick: () => {Button.doDebug('/break')}
        })
        Button.createButtonBase(parent_div_right, {
            text: "QSave",
            onClick: () => {Button.doSave(0)}
        })

        // Fix replay mode, we need to create `#pause-btn` first
        Button.createButtonBase(parent_div3, {
            text: "Replay",
            property: 'is_replay',
            onClick: () => {
                if( ButtonSetting.is_replay ) {
                    Button.disablePause()
                    HistoryLog.close()

                    document.body.classList.add('replaying')
                    // document.querySelector('#replay-icon')?.classList.remove('hide')
                    if( Game.asking_players.length > 0 ) {
                        Replay.doReplay()
                    }
                    document.getElementById('replay-btn')?.classList.add('clicked')
                } else {
                    document.body.classList.remove('replaying')
                    // document.querySelector('#replay-icon')?.classList.add('hide')
                    document.getElementById('replay-btn')?.classList.remove('clicked')
                    Replay.prepared_replay = false
                    Replay.preparing_replay = false
                }
            },
            callWhenInit: true
        })
    }


    static updateFullSearchButton() {
        const button = Button.full_search_button
        if( !button ) {
            return
        }
        const playerId = Button.getFullSearchPreferencePlayerId()
        const enabled = ClientPreferences.showDeckDuringFullSearch(playerId)
        button.classList.toggle('clicked', enabled)
        const playerLabel = Setting.is_hot_seat ? `P${playerId + 1} ` : ''
        button.innerHTML = `${playerLabel}Full Search: ${enabled ? 'On' : 'Off'}`
    }

    static getFullSearchPreferencePlayerId(): number {
        if( Setting.is_hot_seat &&
            Game.forced_on_player >= 0 &&
            Game.forced_on_player < Game.total_players
        ) {
            return Game.forced_on_player
        }
        return Setting.player_id
    }

    static createButtonBase(parent: HTMLElement, options: {
        names?: string[];
        text?: string;
        class_name?: string;
        id?: string;
        property?: keyof typeof ButtonSetting;
        onClick?: (e: HTMLElement) => void;
        callWhenInit?: boolean;
        cookie_name?: string;
    }): HTMLButtonElement {
        const { names=[], text="", class_name, id="", property, onClick, callWhenInit=false, cookie_name="" } = options;
        const button = document.createElement('button');
        button.id = id

        button.className = class_name ? `button ${class_name}` : "button";

        const labels = names.length == 0 ? [text, text] : names

        // If a cookie_name is provided, try to load the saved value
        if (cookie_name && property) {
            const saved = parseInt(Lib.cookie.getBtnString(cookie_name), 10);
            if (!isNaN(saved)) {
                ButtonSetting[property] = saved;
            }
        }

        button.onclick = () => {
            if( property ) {
                let value = ButtonSetting[property] as number
                value += 1

                if( value >= labels.length ) {
                    value = 0
                }

                button.innerHTML = labels[value]
                if( value == 0 ) {
                    button.classList.remove('clicked')
                } else {
                    button.classList.add('clicked')
                }
                ButtonSetting[property] = value

                    // store to cookie if requested
                if (cookie_name) {
                    Lib.cookie.setBtnString(cookie_name, value.toString());
                }
            }

            if( onClick ) {
                onClick(button)
            }
        }

        if( property ) {
            const value = ButtonSetting[property] as number
            button.innerHTML = labels[value];
            if( value != 0 ) {
                button.classList.add('clicked')
            }
        }
        else {
            button.innerHTML = text;
        }

        if( callWhenInit && onClick ) {
            onClick(button)
        }

        parent.appendChild(button);
        return button
    }
}

// Attach the Button class to the global window object
(window as any).Button = Button;
