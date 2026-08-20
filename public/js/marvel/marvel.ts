if( Setting.is_debug ) {
    // const { Debug } = await import('./debug/debug.js'); 
    // Debug.Fetch();
    import('./debug/debug.js').then(async (module) => {
        const { Debug } = module;
        await Debug.Fetch();
    });

    Lib.loader.loadCSS('./public/css/debug/debug.css')
    Lib.loader.loadCSS('./public/css/debug/debug-cmd.css')
    Lib.loader.loadCSS('./public/css/debug/card-debug.css')
    Lib.loader.loadCSS('./public/css/debug/debug-card.css')
    Lib.loader.loadCSS('./public/css/debug/debug-window.css')
    Lib.loader.loadCSS('./public/css/debug/debug-profile.css')
    document.body.classList.add('is-debug')

    document.querySelector('#debug-window')?.classList.remove('hide')

    if( false ) {
        const originalLog = console.log;
        console.log = (...args: any[]) => {
            // Add custom behavior, e.g., a timestamp
            const formatTime = (date: Date) => {
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                return `${hours}:${minutes}:${seconds}`;
            };
            const timestamp = formatTime(new Date());
        
            // Get original callsite using Error stack
            const err = new Error();
            let callSite = '';
            if (err.stack) {
                // Chrome/Edge: lines look like "    at func (file:line:col)"
                const stackLines = err.stack.split('\n');
                // stackLines[0] is "Error", stackLines[1] is this function, stackLines[2] is caller
                if (stackLines.length >= 3) {
                    // This will look like: "    at myFunc (effect.ts:652:13)"
                    // or "    at effect.ts:652:13"
                    callSite = stackLines[2].trim().replace(/^at\s+/, '');
                }
            }
        
            // Print with callsite and timestamp
            originalLog(`[${timestamp}] [${callSite}]\n`, ...args);
        };
    }
} else {
    console.log = (...args: any[]) => { };
}

import { Lib } from './lib.js';
import { Setting } from './settings.js';
Setting

import { UI } from './ui.js';
import { Button } from './buttons.js';
import { SwipeDetector } from './window.js';
import { Client } from './client.js';

import { Scene } from './scene.js';
import { FillScreen } from './fill-screen.js';
import { Mobile } from './mobile.js';
import { AutoActivate } from './auto_activate.js';
import { ErrorDialog } from './error_dialog.js';
import { Message } from './message.js';
Scene.init()
FillScreen.init()
Mobile.init()

UI.init()
ErrorDialog.init()
Message.init()
UI.update()
Button.initializeButtons()
Button.doShow()

// Usage
SwipeDetector.attachSwipeListeners();
Client.doConnect()

AutoActivate.loadConfig(true)

// document.addEventListener('click', async function() {
//     document.documentElement.requestFullscreen();

//     // Request fullscreen
//     if (document.documentElement.requestFullscreen) {
//         await document.documentElement.requestFullscreen();
//         } else if (document.documentElement.webkitRequestFullscreen) {
//         await document.documentElement.webkitRequestFullscreen();
//         }
//         // Lock orientation (landscape)
//         if (screen.orientation && screen.orientation.lock) {
//         try {
//             await screen.orientation.lock('landscape');
//         } catch(e) {
//             console.log('Orientation lock failed:', e);
//         }
//         }
// }, { once: true })

// window.addEventListener('message', function(e) {
//     if (e.data === 'goFullScreen') {
//       document.documentElement.requestFullscreen();
//     }
// });

// document.getElementById('fullscreen')!.addEventListener('click', async function() {

// });
