const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(process.argv[2], 'utf8').replace(/^export /gm, '');

function client() {
    const timers = new Map();
    const requests = [];
    const revoked = [];
    const replies = [];
    let nextId = 0;
    class ImageURL extends URL {
        static createObjectURL(blob) { return 'blob:' + blob.name; }
        static revokeObjectURL(url) { revoked.push(url); }
    }
    const context = vm.createContext({
        URL: ImageURL, document: { baseURI: 'http://localhost/deck' },
        window: {
            setTimeout(callback, delay) { const id = ++nextId; timers.set(id, { callback, delay }); return id; },
            clearTimeout(id) { timers.delete(id); },
        },
        async fetch(url, options) {
            requests.push({ url, options });
            if (!replies.length) throw new Error('No more responses');
            const reply = replies.shift();
            if (reply instanceof Error) throw reply;
            return await reply;
        },
    });
    vm.runInContext(source + '\nglobalThis.images = CardImages;', context);
    return {
        images: context.images, context, requests, replies, timers, revoked,
        async flush() { for (let i = 0; i < 10; i++) await Promise.resolve(); },
        async retry() {
            assert.equal(timers.size, 1, 'Only one retry per shared image');
            const [id, timer] = timers.entries().next().value;
            timers.delete(id);
            timer.callback();
            await this.flush();
            return timer.delay;
        },
    };
}

function image() {
    const properties = new Map();
    const classes = new Set();
    return {
        isConnected: true, src: '', dataset: {}, innerHTML: '',
        classList: {add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name)},
        removeAttribute(name) { if (name === 'src') this.src = ''; },
        style: {
            setProperty(name, value) { properties.set(name, value); },
            getPropertyValue(name) { return properties.get(name) || ''; },
        },
    };
}

function response(name, retry = null, contentType = 'image/png') {
    return {
        ok: true, headers: { get(key) {
            return key === 'Content-Type' ? contentType : key === 'X-Card-Image-Retry-After' ? retry : null;
        } },
        async blob() { return { name }; },
    };
}

(async () => {
    // Actual HTTP-200 placeholders must be replaced without a reload. Copies,
    // previews and CSS backgrounds share both the request and recovered bytes.
    const c = client();
    c.replies.push(response('placeholder', '30'), response('artwork'));
    const copies = [image(), image(), image()];
    copies.forEach(img => c.images.setImage(img, '37007'));
    const card = image();
    c.images.setBackground(card, '--bg-image-true', '37007');
    c.images.setBackground(card, '--bg-image', '37007');
    await c.flush();
    assert.equal(c.requests.length, 1);
    assert.equal(copies[0].src, 'blob:placeholder');
    assert.equal(c.timers.size, 1);
    assert.equal(await c.retry(), 30100);
    assert.equal(c.requests.length, 2);
    assert(copies.every(img => img.src === 'blob:artwork'));
    assert.equal(card.style.getPropertyValue('--bg-image'), 'url("blob:artwork")');
    assert.equal(c.timers.size, 0, 'Successful artwork must stop retrying');
    const preview = image();
    c.images.setImage(preview, '/37007');
    assert.equal(preview.src, 'blob:artwork');
    assert.equal(c.requests.length, 2, 'Opening a preview reuses finished artwork');
    assert.deepEqual(c.revoked, ['blob:placeholder']);
    assert(c.requests.every(request => request.options.cache === 'no-store'));

    // A delayed download of the previous preview may never replace the new one.
    const switched = client();
    let finishOld;
    switched.replies.push(new Promise(resolve => finishOld = resolve), response('new-card'));
    const changing = image();
    switched.images.setImage(changing, '37007');
    switched.images.setImage(changing, '35015');
    await switched.flush();
    finishOld(response('old-card', '30'));
    await switched.flush();
    assert.equal(changing.src, 'blob:new-card');
    assert.equal(switched.timers.size, 0);

    // Removed cards should not keep making requests during an outage.
    const removed = client();
    removed.replies.push(response('missing', '30'));
    const detached = image();
    removed.images.setImage(detached, '35018');
    await removed.flush();
    detached.isConnected = false;
    await removed.retry();
    assert.equal(removed.requests.length, 1);
    assert.equal(removed.timers.size, 0);
    assert.deepEqual(removed.revoked, ['blob:missing']);
    detached.isConnected = true;
    removed.replies.push(response('restored'));
    removed.images.setImage(detached, '35018');
    await removed.flush();
    assert.equal(detached.src, 'blob:restored');

    // Extended failures back off, keep the existing placeholder visible, and
    // recover even after network errors or HTML authentication/error responses.
    const outage = client();
    const waiting = image();
    outage.replies.push(response('text-card', '30'), new Error('Offline'), response('error', null, 'text/html'), response('recovered'));
    outage.images.setImage(waiting, '37001b');
    await outage.flush();
    assert.equal(await outage.retry(), 30100);
    assert.equal(waiting.src, 'blob:text-card');
    assert.equal(await outage.retry(), 60100);
    assert.equal(waiting.src, 'blob:text-card');
    assert.equal(await outage.retry(), 120100);
    assert.equal(waiting.src, 'blob:recovered');
    assert.equal(outage.timers.size, 0);

    // Source changes on a card back must not overwrite the new face on recovery.
    const flipped = client();
    const face = image();
    flipped.replies.push(response('back-missing', '30'), response('face-art'));
    flipped.images.setBackground(face, '--bg-image', 'encounter');
    await flipped.flush();
    flipped.images.setBackground(face, '--bg-image', '37007');
    await flipped.flush();
    assert.equal(face.style.getPropertyValue('--bg-image'), 'url("blob:face-art")');
    assert.equal(flipped.timers.size, 0);
    flipped.images.setBackground(face, '--bg-image', '');
    assert.equal(face.style.getPropertyValue('--bg-image'), 'none');
    assert.equal(flipped.requests.length, 2, 'An absent image must not request the HTML page');

    // Exercise the actual gameplay hover/flip controller. It must keep looking
    // up the card's ID even though the displayed image is a recovered blob URL.
    const h = client();
    const nodes = new Map();
    function node(selector) {
        if (!nodes.has(selector)) {
            const element = image();
            element.parentElement = {classList: image().classList, querySelector: node};
            element.querySelector = node;
            nodes.set(selector, element);
        }
        return nodes.get(selector);
    }
    const textIds = [];
    const gameCard = {name:'Royal Flush', card_type:'Event', down_card_ids:['37001b'], isVisible:() => true};
    Object.assign(h.context, {
        Lib: {client:{getOffsetClient:() => ({left:0,top:0,width:100,height:100})},
              game:{cleanResText:text => text, removeTypeClasses() {}, addTypeClass() {}}},
        Cards: {getCard:() => gameCard, getText(id) {
            assert(['37007','37001b'].includes(id), 'Hover metadata must use the original card ID');
            textIds.push(id);
            return 'Text for ' + id;
        }},
        ButtonSetting: {show_image_text:true}, Setting:{is_debug:false},
        CardAnimation:{animation_name:''},
        getComputedStyle:() => ({getPropertyValue:() => '0'}),
    });
    h.context.document.querySelector = node;
    const hoverSource = fs.readFileSync(path.resolve(path.dirname(process.argv[2]), '../marvel/hover.js'), 'utf8')
        .replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '');
    vm.runInContext(hoverSource + '\nglobalThis.hover = HoverCard;', h.context);
    const cardDiv = node('card');
    cardDiv.dataset.id = '42';
    cardDiv.style.setProperty('--bg-image-true', 'url("37007")');
    cardDiv.style.setProperty('--bg-image-false', 'url("37001b")');
    h.replies.push(response('front-art'), response('back-art'));
    h.context.hover.set2(cardDiv, cardDiv.style.getPropertyValue('--bg-image-true'));
    await h.flush();
    const previewElement = h.context.hover.getPreview();
    assert.equal(previewElement.style.getPropertyValue('--bg-image'), 'url("blob:front-art")');
    h.context.hover.hover_card = cardDiv;
    h.context.hover.flip();
    await h.flush();
    assert.equal(previewElement.style.getPropertyValue('--bg-image'), 'url("blob:back-art")');
    h.context.hover.flip();
    await h.flush();
    assert.equal(previewElement.style.getPropertyValue('--bg-image'), 'url("blob:front-art")');
    assert.deepEqual(textIds, ['37007','37001b','37007']);
    assert.equal(h.requests.length, 2);
    console.log('Card image UI recovery checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
