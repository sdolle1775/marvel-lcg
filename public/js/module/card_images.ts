interface ImageEntry {
    source: string;
    imageUrl: string;
    complete: boolean;
    failures: number;
    bindings: Set<ImageBinding>;
    timer?: number;
}

interface ImageBinding {
    element: HTMLElement;
    key: string;
    entry: ImageEntry;
    apply: (url: string) => void;
}

// Share downloads and recovery between duplicate cards, thumbnails and previews.
export class CardImages {
    private static entries = new Map<string, ImageEntry>();
    private static bindings = new WeakMap<HTMLElement, Map<string, ImageBinding>>();

    static setImage(image: HTMLImageElement, source: string): void {
        this.bind(image, 'src', source, url => image.src = url);
    }

    static setBackground(element: HTMLElement, property: string, source: string): void {
        this.bind(element, property, source, url => {
            element.style.setProperty(property, url ? `url("${url}")` : 'none');
        });
    }

    private static bind(element: HTMLElement, key: string, source: string, apply: (url: string) => void): void {
        let bindings = this.bindings.get(element);
        if (!bindings) {
            bindings = new Map();
            this.bindings.set(element, bindings);
        }
        const previous = bindings.get(key);
        if (!source) {
            if (previous) this.removeBinding(previous);
            if (key === 'src') (element as HTMLImageElement).removeAttribute('src');
            else apply('');
            return;
        }
        const url = new URL(source, document.baseURI).href;
        if (previous?.entry.source === url) {
            if (previous.entry.imageUrl || key !== 'src') apply(previous.entry.imageUrl);
            return;
        }
        if (previous) this.removeBinding(previous);

        let entry = this.entries.get(url);
        const start = !entry;
        if (!entry) {
            entry = { source: url, imageUrl: '', complete: false, failures: 0, bindings: new Set() };
            this.entries.set(url, entry);
        }
        const binding = { element, key, entry, apply };
        bindings.set(key, binding);
        if (!entry.complete) entry.bindings.add(binding);
        // Do not make a second, unmanaged request through the original img URL.
        if (entry.imageUrl || key !== 'src') apply(entry.imageUrl);
        else (element as HTMLImageElement).removeAttribute('src');
        if (start) void this.download(entry);
    }

    private static removeBinding(binding: ImageBinding): void {
        this.bindings.get(binding.element)?.delete(binding.key);
        const entry = binding.entry;
        entry.bindings.delete(binding);
        if (!entry.complete && entry.bindings.size === 0) {
            if (entry.timer !== undefined) window.clearTimeout(entry.timer);
            this.entries.delete(entry.source);
            if (entry.imageUrl) URL.revokeObjectURL(entry.imageUrl);
        }
    }

    private static prune(entry: ImageEntry): boolean {
        for (const binding of entry.bindings) {
            if (!binding.element.isConnected) this.removeBinding(binding);
        }
        return this.entries.get(entry.source) === entry && entry.bindings.size > 0;
    }

    private static async download(entry: ImageEntry): Promise<void> {
        let retrySeconds = 30;
        try {
            const response = await fetch(entry.source, { cache: 'no-store' });
            if (!response.ok || !response.headers.get('Content-Type')?.startsWith('image/')) {
                throw new Error('Card image unavailable');
            }
            const blob = await response.blob();
            if (!this.prune(entry)) return;
            const oldUrl = entry.imageUrl;
            entry.imageUrl = URL.createObjectURL(blob);
            for (const binding of entry.bindings) binding.apply(entry.imageUrl);
            if (oldUrl) URL.revokeObjectURL(oldUrl);

            const retryHeader = response.headers.get('X-Card-Image-Retry-After');
            const retry = Number(retryHeader);
            if (retryHeader === null || !Number.isFinite(retry) || retry <= 0) {
                entry.complete = true;
                entry.bindings.clear();
                return;
            }
            retrySeconds = retry;
        } catch {
            if (!this.prune(entry)) return;
        }
        // An extended outage should not hammer the image providers. The first
        // retry honors the server cooldown; repeated failures back off to 5 min.
        entry.failures++;
        const delay = Math.max(retrySeconds, Math.min(300, 30 * 2 ** (entry.failures - 1)));
        entry.timer = window.setTimeout(() => {
            entry.timer = undefined;
            if (this.prune(entry)) void this.download(entry);
        }, delay * 1000 + 100);
    }
}
