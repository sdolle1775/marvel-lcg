import { Lib } from './lib.js'
import { Game } from './game.js'
import { MouseSync } from './mouse.js';

const search_params = new URLSearchParams(window.location.search);

export class Setting {
    static is_debug = search_params.has('debug')
    static show_achievement = search_params.has('show_achievement') || Setting.is_debug
    static hide_bug_report = search_params.has('hide_bug_report')
    static show_res_id = Setting.is_debug
    static is_auto_test = search_params.has('auto_test')
    static ssr_bonus = search_params.has('ssr_bonus')
    static no_tilt = !search_params.has('3d_card')
    static statistics_off = search_params.has('notification') && search_params.get('notification') == '0'
    static statistics_first = !search_params.has('notification') || search_params.has('notification') && search_params.get('notification') == '1'
    static statistics_all = search_params.has('notification') && search_params.get('notification') == '2'
    static is_hot_seat = search_params.has('hot_seat')
    static is_watch = search_params.has('watch')
    static show_all_cards = search_params.has('show_all_cards')
    static show_card_id = search_params.has('show_card_id') || Setting.is_debug
    static player_id: number = search_params.has('p') ? Number(search_params.get('p') as string) : 0;
    static ver: number = 1
    static scene_3d: boolean = search_params.has('3d_scene') || search_params.has('3d')
    static fill_screen: boolean = search_params.has('fill_screen')
    static is_remote: boolean = search_params.has('remote')
    static {
        if( window.location.pathname == '/marvel2.html') {
            Setting.ver = 2
        };

        if( !Setting.is_hot_seat ) {
            MouseSync.init()
        }
    }

    static cheat_show_all_cards = false

    static auto_effect_black_list: string[] = [
        // "30010", "30009"
        // List of card IDs to exclude from auto effect
    ];

    // in "F" mode, these cards will always be shown
    static render_card_whitelist: Set<string> = new Set([]);
    // in "F" mode, these cards will not be shown
    static render_card_blacklist: Set<string> = new Set([]);
    static render_under_card_whitelist: Set<string> = new Set([]);

    static {
        // generate resources for other player
        Setting.render_card_whitelist = Lib.cookie.getSet("render_card_whitelist", ["32020", "36023", "16142"])
        Setting.render_under_card_whitelist = Lib.cookie.getSet("render_under_card_whitelist", ["53021"])
        Setting.render_card_blacklist = Lib.cookie.getSet("render_card_blacklist", ["03019"])
    }

    static {

        Game.forced_on_player = Setting.player_id

        const no_animation = search_params.has('disable_animations')
        if( no_animation ) {
            Setting.no_tilt = true
            Lib.loader.loadCSS('./public/css/disable-animation.css')
        }
    }

    static showAllCards() {
        return Setting.show_all_cards || Setting.cheat_show_all_cards
    }

    static getPlayerIds() {
        let player_ids = `${Setting.player_id}`
        if( Setting.is_hot_seat ) {
            function createList(X: number, Y: number) {
                let list = [];
                for (let i = X; i <= Y; i++) {
                    list.push(i);
                }
                return list;
            }
            player_ids = createList(0, Game.total_players-1).join(",");
        }
        return player_ids
    }
}

export class ButtonSetting {
    static enable_enhance_fx = Number(!search_params.has('disable_enhance_fx'))
    static sort_hand_cards = Number(search_params.has('sort_hand_cards') || Setting.is_debug)
    static sort_area_cards = 1
    static sort_discard_pile_cards = 0
    static new_badge = 1
    static enable_preview = Number(!search_params.has('disable_preview')) // || Setting.is_debug
    static auto_target = 1;
    static auto_target_forced = 0;
    static show_image_text = 0
    static is_replay = Number(search_params.has('replay'))
    static music_on = 1

    static show_all_players = 1
    static show_all_hand_cards = Setting.is_hot_seat ? 1 : 0
    static always_show_minions_belong = 1
    static hide_no_action_cards = 1
    static players_pin = 1

    static show_auto_activate = 0
    static auto_activate = 1

    static pause_when_reveal_or_boost = 1
    static card_tilt = 0
}

(window as any).Setting = Setting;
(window as any).ButtonSetting = ButtonSetting;

