import { HoverCard } from './hover.js';
import { Lib } from './lib.js';

interface WebkitFullscreenElement extends HTMLElement {
    webkitRequestFullscreen?: () => void;
}

interface WebkitFullscreenDocument extends Document {
    webkitFullscreenElement?: Element | null;
    webkitExitFullscreen?: () => void;
}

interface OrientationLockScreen extends ScreenOrientation {
    lock?: (orientation: 'landscape') => Promise<void>;
}

type HoverSet = (card_div: HTMLElement | null, is_log?: boolean, forced_bg_image?: string) => void;

export class Mobile {

    static readonly LONG_PRESS_MS = 350;
    static readonly MOVE_CANCEL_PX = 12;

    static is_touch: boolean = false;
    static last_pointer_touch: boolean = false;
    static preview_active: boolean = false;
    static suppress_click: boolean = false;
    static fullscreen_button: HTMLButtonElement | null = null;

    private static hover_patched: boolean = false;
    private static flushing: boolean = false;
    private static original_hover_set: HoverSet = HoverCard.set.bind(HoverCard);

    static init(): void {
        Mobile.is_touch =
            (window.matchMedia !== undefined && window.matchMedia('(pointer: coarse)').matches) ||
            ('ontouchstart' in window) ||
            (navigator.maxTouchPoints > 0);

        if (!Mobile.is_touch) {
            return;
        }

        Lib.loader.loadCSS("./css./marvel./mobile.css");
        document.body.classList.add('is-touch');

        Mobile.trackPointerType();
        Mobile.separateTapFromHold();
        Mobile.setupLongPress();
        Mobile.setupFullscreenButton();
        Mobile.setupRotatePrompt();
        Mobile.setupSideBars();
        Mobile.updateOrientation();

        window.addEventListener('resize', Mobile.updateOrientation);
        window.addEventListener('orientationchange', Mobile.updateOrientation);
    }

    private static trackPointerType(): void {
        const remember = (event: PointerEvent) => {
            Mobile.last_pointer_touch = (event.pointerType === 'touch');
        };
        window.addEventListener('pointermove', remember, true);
        window.addEventListener('pointerdown', remember, true);
    }

    private static separateTapFromHold(): void {
        if (Mobile.hover_patched) {
            return;
        }
        Mobile.hover_patched = true;

        const original = Mobile.original_hover_set;
        HoverCard.set = function (card_div: HTMLElement | null, is_log = false, forced_bg_image = ''): void {
            if (card_div && Mobile.last_pointer_touch && !Mobile.preview_active) {
                return;
            }
            original(card_div, is_log, forced_bg_image);
        };
    }

    private static setupLongPress(): void {
        let timer: number | null = null;
        let start_x = 0;
        let start_y = 0;
        let card: HTMLElement | null = null;

        const clearTimer = () => {
            if (timer !== null) {
                clearTimeout(timer);
                timer = null;
            }
        };

        document.addEventListener('touchstart', (event: TouchEvent) => {
            Mobile.suppress_click = false;
            const target = event.target instanceof Element ? event.target.closest<HTMLElement>('.card') : null;
            if (!target) {
                card = null;
                return;
            }
            card = target;
            start_x = event.touches[0].clientX;
            start_y = event.touches[0].clientY;
            clearTimer();
            timer = window.setTimeout(() => {
                timer = null;
                Mobile.preview_active = true;
                Mobile.suppress_click = true;
                Mobile.original_hover_set(card);
            }, Mobile.LONG_PRESS_MS);
        }, { capture: true, passive: true });

        document.addEventListener('touchmove', (event: TouchEvent) => {
            if (!card || timer === null) {
                return;
            }
            const moved_x = Math.abs(event.touches[0].clientX - start_x);
            const moved_y = Math.abs(event.touches[0].clientY - start_y);
            if (moved_x > Mobile.MOVE_CANCEL_PX || moved_y > Mobile.MOVE_CANCEL_PX) {
                clearTimer();
            }
        }, { capture: true, passive: true });

        const endPress = () => {
            clearTimer();
            if (Mobile.preview_active) {
                Mobile.preview_active = false;
                Mobile.original_hover_set(null);
            }
            card = null;
        };
        document.addEventListener('touchend', endPress, { capture: true, passive: true });
        document.addEventListener('touchcancel', endPress, { capture: true, passive: true });

        document.addEventListener('contextmenu', (event: MouseEvent) => {
            if (Mobile.last_pointer_touch) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }, { capture: true });

        document.addEventListener('click', (event: MouseEvent) => {
            if (Mobile.suppress_click) {
                Mobile.suppress_click = false;
                event.stopPropagation();
                event.preventDefault();
            }
            Mobile.flushHover();
        }, { capture: true });
    }

    static flushHover(): void {
        if (!Mobile.last_pointer_touch || Mobile.flushing) {
            return;
        }
        const element = document.getElementById('scene') ?? document.body;
        Mobile.flushing = true;
        element.style.pointerEvents = 'none';
        requestAnimationFrame(() => {
            element.style.pointerEvents = '';
            Mobile.flushing = false;
        });
    }

    private static setupSideBars(): void {
        const side_bar = document.getElementById('right-side-bar');
        const handle = document.getElementById('right-side-bar-handle');
        if (!side_bar || !handle) {
            return;
        }

        handle.addEventListener('click', event => {
            event.stopPropagation();
            side_bar.classList.toggle('touch-open');
        });

        document.addEventListener('click', event => {
            if (!side_bar.classList.contains('touch-open')) {
                return;
            }
            const target = event.target instanceof Node ? event.target : null;
            if (target && side_bar.contains(target)) {
                return;
            }
            side_bar.classList.remove('touch-open');
        });
    }

    private static setupFullscreenButton(): void {
        const root = document.documentElement as WebkitFullscreenElement;
        const button = document.createElement('button');
        button.id = 'mobile-fullscreen-btn';
        button.className = 'button';
        button.title = 'Fullscreen / Landscape';
        button.innerHTML = '<i class="fa fa-expand" aria-hidden="true"></i>';
        button.addEventListener('click', Mobile.toggleFullscreen);

        const side_bar = document.getElementById('right-side-bar');
        if (side_bar) {
            side_bar.prepend(button);
        } else {
            document.body.appendChild(button);
        }
        Mobile.fullscreen_button = button;

        if (!root.requestFullscreen && !root.webkitRequestFullscreen) {
            button.classList.add('hide');
        }

        document.addEventListener('fullscreenchange', Mobile.onFullscreenChange);
        document.addEventListener('webkitfullscreenchange', Mobile.onFullscreenChange);
    }

    static async toggleFullscreen(): Promise<void> {
        const root = document.documentElement as WebkitFullscreenElement;
        const owner = document as WebkitFullscreenDocument;
        const current = document.fullscreenElement ?? owner.webkitFullscreenElement ?? null;

        try {
            if (!current) {
                if (root.requestFullscreen) {
                    await root.requestFullscreen();
                } else if (root.webkitRequestFullscreen) {
                    root.webkitRequestFullscreen();
                }
                const orientation = screen.orientation as OrientationLockScreen | undefined;
                if (orientation && orientation.lock) {
                    try {
                        await orientation.lock('landscape');
                    } catch (error) {

                    }
                }
            } else {
                if (screen.orientation && screen.orientation.unlock) {
                    screen.orientation.unlock();
                }
                if (document.exitFullscreen) {
                    await document.exitFullscreen();
                } else if (owner.webkitExitFullscreen) {
                    owner.webkitExitFullscreen();
                }
            }
        } catch (error) {

        }
    }

    static onFullscreenChange(): void {
        const owner = document as WebkitFullscreenDocument;
        const current = document.fullscreenElement ?? owner.webkitFullscreenElement ?? null;
        document.body.classList.toggle('is-fullscreen', current !== null);

        if (Mobile.fullscreen_button) {
            Mobile.fullscreen_button.innerHTML = current
                ? '<i class="fa fa-compress" aria-hidden="true"></i>'
                : '<i class="fa fa-expand" aria-hidden="true"></i>';
        }

        window.dispatchEvent(new Event('resize'));
        Mobile.updateOrientation();
    }

    private static setupRotatePrompt(): void {
        const overlay = document.createElement('div');
        overlay.id = 'rotate-overlay';
        overlay.innerHTML =
            '<div class="rotate-inner">' +
            '<div class="rotate-icon">&#128241;</div>' +
            '<div class="rotate-title">Rotate to landscape</div>' +
            '<div class="rotate-sub">Turn the device sideways for the full table, ' +
            'or use the button below to play fullscreen.</div>' +
            '<button id="rotate-fs-btn">Enter Fullscreen</button>' +
            '</div>';
        document.body.appendChild(overlay);

        const button = overlay.querySelector<HTMLButtonElement>('#rotate-fs-btn');
        if (button) {
            button.addEventListener('click', Mobile.toggleFullscreen);
        }
    }

    static updateOrientation(): void {
        const portrait = window.matchMedia !== undefined
            ? window.matchMedia('(orientation: portrait)').matches
            : window.innerHeight > window.innerWidth;
        document.body.classList.toggle('is-portrait', portrait);
    }
}
