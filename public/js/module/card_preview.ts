// @ts-check
"use strict";

import { Card } from './card_info.js';
import { CardImages } from './card_images.js';
import { copyToClipboard } from '../lib/clipboard.js'

export class CardPreview {
    private lastClickCardDiv: HTMLElement | null = null;
    private previewDiv: HTMLDivElement;
    private statisticsJson: Record<string, any>;
    private constCardDict: Record<string, Card>;

    private previewImg: HTMLImageElement;
    private previewCardIdDiv: HTMLDivElement;

    constructor(const_card_dict: Record<string, Card>) {
        this.statisticsJson = {};
        this.constCardDict = const_card_dict;

        // Create the image element
        this.previewImg = document.createElement('img') as HTMLImageElement;
        this.previewImg.id = 'preview-img';
        this.previewImg.src = ''; // Set the source as needed
        this.previewImg.alt = 'Preview';
        // Create the card ID div
        this.previewCardIdDiv = document.createElement('div') as HTMLDivElement;
        this.previewCardIdDiv.id = 'preview-card-id';
        
        this.previewDiv = this.createPreviewContainer();
    }

    private createPreviewContainer(): HTMLDivElement {
        const div = document.createElement('div');
        div.id = 'preview';
        div.setAttribute('tabindex', '0'); // Make the div focusable
        div.onkeydown = this.handleKeyDown.bind(this);
        div.onclick = this.killPreview.bind(this);
        document.body.appendChild(div);

        const previewContentDiv = document.createElement('div') as HTMLDivElement;
        previewContentDiv.id = 'preview-content';

        // Append the image and card ID to the preview content
        previewContentDiv.appendChild(this.previewImg);
        previewContentDiv.appendChild(this.previewCardIdDiv);

        // Create the next button
        const nextButton = this.createButton('next', 'fa-arrow-circle-o-right', this.showNextCard.bind(this));
        const prevButton = this.createButton('prev', 'fa-arrow-circle-o-left', this.showPreviousCard.bind(this));

        // Append all parts to the main preview div
        div.appendChild(prevButton);
        div.appendChild(previewContentDiv);
        div.appendChild(nextButton);

        return div;
    }

    private createButton(id: string, iconClass: string, onClick: (event: MouseEvent) => void): HTMLDivElement {
        const buttonDiv = document.createElement('div') as HTMLDivElement;
        buttonDiv.id = id;
        buttonDiv.onclick = onClick;
        buttonDiv.innerHTML = `<i class="fa ${iconClass}" aria-hidden="true"></i>`;
        return buttonDiv;
    }

    private handleKeyDown(event: KeyboardEvent): void {
        if (this.lastClickCardDiv) {
            if (event.key === 'ArrowLeft') {
                event.preventDefault();
                this.showPreviousCard();
            } else if (event.key === 'ArrowRight') {
                event.preventDefault();
                this.showNextCard();
            }
        }
        if (event.key === "Escape") {
            this.killPreview();
            event.preventDefault();
        }
    }

    private killPreview(): void {
        if (this.previewDiv) {
            this.previewDiv.style.display = 'none';
        }
    }

    private showPreviousCard(e: MouseEvent | null = null): void {
        if (e) {
            e.stopPropagation();
        }
        const div = this.lastClickCardDiv?.previousElementSibling as HTMLElement;
        this.previewCard(div);
    }

    private showNextCard(e: MouseEvent | null = null): void {
        if (e) {
            e.stopPropagation();
        }
        const div = this.lastClickCardDiv?.nextElementSibling as HTMLElement;
        this.previewCard(div);
    }

    private getDivIndex(divElement: HTMLElement): number {
        if (!(divElement instanceof HTMLDivElement)) {
            throw new Error("The provided element is not a valid <div> element.");
        }

        const parent = divElement.parentElement;
        if (!parent) {
            throw new Error("The provided <div> element has no parent.");
        }

        const children = Array.from(parent.children);
        return children.indexOf(divElement);
    }

    private previewCard(cardDiv?: HTMLElement, statisticsJson?: Record<string, any>): void {
        if( !cardDiv ) {
            return
        }
        if (statisticsJson) {
            this.statisticsJson = statisticsJson;
        } else {
            statisticsJson = this.statisticsJson;
        }
        const cardId = cardDiv.getAttribute('data-card-id') as string;
        const cardName = this.constCardDict[cardId].name;
        this.lastClickCardDiv = cardDiv;
        CardImages.setImage(this.previewImg, cardId);
        const fullLinkId = this.constCardDict[cardId].full_link_id;
        const index = `${this.getDivIndex(cardDiv) + 1}/${cardDiv.parentNode?.children.length}`;

        this.previewCardIdDiv.innerHTML = `
            <span class='preview-key'>(${index})</span><br/>
            <span class='preview-key' id='copy-card-name'>
                <i class="fa fa-clipboard preview-key" aria-hidden="true" style='padding-right: .4rem'></i>Name</span><br/>
            <span id='copy-card-id'>
                <i class="fa fa-clipboard preview-key" aria-hidden="true" style='padding-right: .4rem'></i>${cardId}</span><br/>
            <br/>
        `;

        if (fullLinkId) {
            this.previewCardIdDiv.innerHTML += `
                <span class='preview-key'>Related</span><br/>
                ${fullLinkId}<br/>
                <br/>
            `;
        }

        if (statisticsJson && cardId in statisticsJson) {
            this.previewCardIdDiv.innerHTML += `
                <hr style="color: black"/>
                <span class='preview-key'>Resolve</span><br/>
                ${statisticsJson[cardId].resolve}<br/>
                <span class='preview-key'>Play</span><br/>
                ${statisticsJson[cardId].play}<br/>
                <span class='preview-key'>Defeated</span><br/>
                ${statisticsJson[cardId].defeated}<br/>
            `;
        } else {
            // Uncomment if you want to show a message for new cards
            // this.previewCardIdDiv.innerHTML += `This card is New`;
        }

        // Add event listener for copying text to clipboard
        const copyCardNameElement = document.getElementById('copy-card-name');
        if (copyCardNameElement) {
            copyCardNameElement.onclick = (e) => {
                this.copyToClipboard(cardName);
            };
        }

        const copyCardIdElement = document.getElementById('copy-card-id');
        if (copyCardIdElement) {
            copyCardIdElement.onclick = (e) => {
                this.copyToClipboard(cardId);
            };
        }

        if (this.constCardDict[cardId].rotate) {
            this.previewImg.classList.add('rotate');
        } else {
            this.previewImg.classList.remove('rotate');
        }

        if( this.previewDiv ) {
            this.previewDiv.style.display = 'flex';
            this.previewDiv.focus();
        }
    }

    private copyToClipboard(text: string): void {
        copyToClipboard(text)
        // const textarea = document.createElement('textarea');
        // textarea.value = text;
        // document.body.appendChild(textarea);
        // textarea.select();
        // document.execCommand('copy');
        // document.body.removeChild(textarea);
    }
}
