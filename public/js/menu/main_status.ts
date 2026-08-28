interface StatusHero {
    name: string;
    player_id: number;
}

interface GameStatusAnswer {
    state: 'none' | 'created' | 'running' | 'over';
    scenario: string;
    round: number;
    heroes: StatusHero[];
    last_move_age_seconds: number | null;
    created_age_seconds: number | null;
}

class MainStatus {
    static readonly POLL_MS = 8000;
    static readonly QUIET_MS = 2 * 60 * 60 * 1000;
    static readonly CREATED_TTL_MS = 12 * 60 * 60 * 1000;

    static init(): void {
        const version = document.querySelector('#version');
        if (!version) {
            return;
        }

        MainStatus.addStyle();
        const panel = MainStatus.addPanel(version);

        MainStatus.update(panel);
        window.setInterval(() => MainStatus.update(panel), MainStatus.POLL_MS);
    }

    private static addStyle(): void {
        const style = document.createElement('style');
        style.textContent = [
            '#game-status{margin:1.5rem auto 0;max-width:340px;padding:14px 18px;',
            '  border:1px solid #ffffff1f;border-radius:12px;background:#00000026;',
            '  font-size:.95rem;line-height:1.55;text-align:center;}',
            '#game-status .gs-line{margin:.1rem 0;}',
            '#game-status .gs-scenario{font-weight:bold;color:#e6e6e6;font-size:1.05rem;}',
            '#game-status .gs-round{color:#bdbdbd;}',
            '#game-status .gs-heroes{margin:.35rem 0;}',
            '#game-status .gs-heroes a{color:#569AFE;text-decoration:none;font-weight:bold;}',
            '#game-status .gs-heroes a:hover{text-decoration:underline;}',
            '#game-status .gs-state{margin-top:.7rem;font-weight:bold;letter-spacing:.03em;}',
            '#game-status .gs-state.playing{color:#4caf50;}',
            '#game-status .gs-state.waiting{color:#e0b000;}',
            '#game-status .gs-state.quiet{color:#d98c2b;}',
            '#game-status .gs-state.idle{color:#888;}',
            '#game-status .gs-note{color:#777;font-size:.8rem;}',
        ].join('');
        document.head.appendChild(style);
    }

    private static addPanel(version: Element): HTMLElement {
        const existing = document.getElementById('game-status');
        if (existing) {
            return existing;
        }

        const panel = document.createElement('div');
        panel.id = 'game-status';
        panel.appendChild(MainStatus.buildState('idle', 'Checking the game'));

        const menu = document.querySelector('.menu');
        if (menu) {
            menu.appendChild(panel);
        } else {
            version.insertAdjacentElement('afterend', panel);
        }
        return panel;
    }

    private static async read(): Promise<GameStatusAnswer | null> {
        try {
            const response = await fetch('/game_status', { cache: 'no-store' });
            const type = response.headers.get('content-type') || '';
            if (!response.ok || type.indexOf('application/json') === -1) {
                return null;
            }
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    private static async update(panel: HTMLElement): Promise<void> {
        const status = await MainStatus.read();
        if (!status) {
            MainStatus.showNoGame(panel, 'the game cannot be reached');
            return;
        }

        if (status.state === 'running') {
            MainStatus.showGame(panel, status);
            return;
        }

        if (status.state === 'created' && MainStatus.isRecent(status.created_age_seconds)) {
            MainStatus.showGame(panel, status);
            return;
        }

        MainStatus.showNoGame(panel, status.state === 'over' ? 'the last game has finished' : '');
    }

    private static isRecent(created_age_seconds: number | null): boolean {
        if (created_age_seconds === null) {
            return false;
        }
        return created_age_seconds * 1000 < MainStatus.CREATED_TTL_MS;
    }

    private static showNoGame(panel: HTMLElement, note: string): void {
        panel.replaceChildren(MainStatus.buildState('idle', 'No game running'));
        if (note) {
            panel.appendChild(MainStatus.buildLine('gs-note', note));
        }
    }

    private static showGame(panel: HTMLElement, status: GameStatusAnswer): void {
        const waiting = status.state === 'created';
        const quiet_ms = MainStatus.getQuietTime(status);

        panel.replaceChildren(
            MainStatus.buildLine('gs-scenario', `Scenario: ${status.scenario || 'Unknown'}`),
            MainStatus.buildLine('gs-round', waiting
                ? 'Not started'
                : (status.round > 0 ? `Round ${status.round}` : 'Setup')),
            MainStatus.buildHeroes(status.heroes),
        );

        if (waiting) {
            panel.appendChild(MainStatus.buildState('waiting', 'Waiting for players'));
        } else if (quiet_ms !== null) {
            panel.appendChild(MainStatus.buildState('quiet', 'Game quiet'));
            panel.appendChild(MainStatus.buildLine('gs-note', `last move ${MainStatus.describeAge(quiet_ms)} ago`));
        } else {
            panel.appendChild(MainStatus.buildState('playing', 'Game running'));
        }
    }

    /** The time since the last move, but only once it is long enough to report. */
    private static getQuietTime(status: GameStatusAnswer): number | null {
        if (status.last_move_age_seconds === null) {
            return null;
        }
        const quiet_ms = status.last_move_age_seconds * 1000;
        return quiet_ms > MainStatus.QUIET_MS ? quiet_ms : null;
    }

    private static buildLine(kind: string, text: string): HTMLElement {
        const line = document.createElement('div');
        line.className = `gs-line ${kind}`;
        line.textContent = text;
        return line;
    }

    private static buildState(kind: string, text: string): HTMLElement {
        const state = document.createElement('div');
        state.className = `gs-state ${kind}`;
        state.textContent = text;
        return state;
    }

    private static buildHeroes(heroes: StatusHero[]): HTMLElement {
        const line = document.createElement('div');
        line.className = 'gs-line gs-heroes';

        const named = heroes.filter(hero => hero.name);
        if (named.length === 0) {
            const note = document.createElement('span');
            note.className = 'gs-note';
            note.textContent = 'No heroes';
            line.appendChild(note);
            return line;
        }

        named.forEach((hero, index) => {
            if (index > 0) {
                line.appendChild(document.createTextNode(', '));
            }
            const link = document.createElement('a');
            link.href = `/?p=${hero.player_id}`;
            link.title = `Play as player ${hero.player_id + 1}`;
            link.textContent = hero.name;
            line.appendChild(link);
        });
        return line;
    }

    static describeAge(elapsed_ms: number): string {
        const seconds = Math.max(0, Math.floor(elapsed_ms / 1000));
        if (seconds < 60) {
            return `${seconds}s`;
        }
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) {
            return `${minutes}m`;
        }
        const hours = Math.floor(minutes / 60);
        if (hours < 24) {
            return `${hours}h ${minutes % 60}m`;
        }
        return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => MainStatus.init());
} else {
    MainStatus.init();
}
