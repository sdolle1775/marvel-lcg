import { MoveCard } from './move-card.js';
import { Setting } from './settings.js';
import { adjustSceneScale } from './scene.js';


export class FillScreen {
    static readonly DESIGN_WIDTH = 1920;
    static readonly DESIGN_HEIGHT = 1080;
    static readonly MIN_WIDTH = 1280;

    static readonly RIGHT_CLUSTER: { [selector: string]: number } = {
        '#area-schemes-main': 1880,
        '#area-schemes-side': 1880,
        '#victory-display': 1250,
        '#removed-pool': 1400,
        '#area-removed': 1400,
        '#nemesis-pool': 1550,
        '#area-advanced': 1700,
    };

    static init(): void {
        if (!Setting.fill_screen) {
            return;
        }

        document.body.classList.add('fill-screen');

        const reflow = () => FillScreen.reflow();
        window.addEventListener('resize', reflow);
        window.addEventListener('orientationchange', reflow);
        document.addEventListener('fullscreenchange', reflow);
        document.addEventListener('webkitfullscreenchange', reflow);

        reflow();

        setTimeout(reflow, 300);
        setTimeout(reflow, 1200);
    }

    static getSceneWidth(viewportWidth: number, viewportHeight: number): number {
        const width = Math.round((viewportWidth / viewportHeight) * FillScreen.DESIGN_HEIGHT);
        return Math.max(width, FillScreen.MIN_WIDTH);
    }

    static reflow(): void {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        if (viewportWidth <= 0 || viewportHeight <= 0) {
            return;
        }

        const sceneWidth = FillScreen.getSceneWidth(viewportWidth, viewportHeight);
        document.documentElement.style.setProperty('--scene-width', String(sceneWidth));

        for (const selector in FillScreen.RIGHT_CLUSTER) {
            const from_right = FillScreen.DESIGN_WIDTH - FillScreen.RIGHT_CLUSTER[selector];
            const x = sceneWidth - from_right;
            document.querySelectorAll<HTMLElement>(selector).forEach(element => {
                element.style.setProperty('--x', String(x));
            });
        }

        adjustSceneScale();

        try {
            MoveCard.doMoveFirstTime();
        } catch (error) {

        }
    }
}
