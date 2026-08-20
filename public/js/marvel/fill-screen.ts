import { MoveCard } from './move-card.js';
import { Setting } from './settings.js';
import { Lib } from './lib.js';
import { adjustSceneScale } from './scene.js';


export class FillScreen {
    static readonly DESIGN_WIDTH = 1920;
    static readonly DESIGN_HEIGHT = 1080;
    static readonly MIN_WIDTH = 1280;

    static init(): void {
        if (!Setting.fill_screen) {
            return;
        }

        Lib.loader.loadCSS("./css./marvel./fill-screen.css");
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

        adjustSceneScale();

        try {
            MoveCard.doMoveFirstTime();
        } catch (error) {
            
        }
    }
}
