/**
 * SYSTEM PATTERN: DYNAMIC CLIENT COMPONENT FACTORY & SSE PARSER ENGINE
 * Handles real-time JSON-RPC 2.0 streaming, Memory Bank visualization, and A2UI component rendering.
 */

class MemoryBankUiEngine {
    constructor() {
        this.streamApiUrl = '/api/chat/stream';
        this.memoryApiUrl = '/api/memory/get';
        this.seedApiUrl = '/api/memory/seed';
        this.unlockApiUrl = '/api/card/unlock';
        this.customerId = 'cust_jpmc_88329';
        this.sessionId = 'sess-live-trace-4821';
        this.currentViewMode = 'notes'; // 'notes' or 'json'
        this.cachedFragments = [];

        this.initDOMElements();
        this.bindEvents();
        this.loadMemoryBank();
    }

    initDOMElements() {
        this.memoryTerminal = document.getElementById('memory-terminal-body');
        this.memoryBadge = document.getElementById('memory-count-badge');
        this.topMemoryStatus = document.getElementById('top-memory-status');
        this.traceLogs = document.getElementById('agent-trace-logs');
        this.chatViewport = document.getElementById('chat-viewport');
        this.a2uiContainer = document.getElementById('a2ui-presentation-container');
        this.chatForm = document.getElementById('chat-form');
        this.chatInput = document.getElementById('chat-input');
        this.reseedBtn = document.getElementById('reseed-btn');
        this.playSimBtn = document.getElementById('play-sim-btn');
        this.cardBadge = document.getElementById('card-badge');
        this.visualCard = document.getElementById('visual-card-preview');
        this.applePayStatus = document.getElementById('apple-pay-status-text');
        this.viewNotesBtn = document.getElementById('view-notes-btn');
        this.viewJsonBtn = document.getElementById('view-json-btn');
        this.promptChips = document.querySelectorAll('.quick-chip-btn');
        this.miniSendBtns = document.querySelectorAll('.mini-send-btn');
    }

    bindEvents() {
        // Chat submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = this.chatInput.value.trim();
            if (text) {
                this.executeChatWorkflow(text);
            }
        });

        // Quick prompt chips
        this.promptChips.forEach(chip => {
            chip.addEventListener('click', () => {
                this.promptChips.forEach(c => c.classList.remove('active-chip'));
                chip.classList.add('active-chip');
                const promptText = chip.dataset.prompt;
                this.chatInput.value = promptText;
                this.executeChatWorkflow(promptText);
            });
        });

        // Simulation playback
        if (this.playSimBtn) {
            this.playSimBtn.addEventListener('click', () => {
                this.playSimulationSequence();
            });
        }

        // Reseed / Reset
        if (this.reseedBtn) {
            this.reseedBtn.addEventListener('click', () => {
                this.reseedMemoryBank();
            });
        }

        // View toggle
        if (this.viewNotesBtn && this.viewJsonBtn) {
            this.viewNotesBtn.addEventListener('click', () => {
                this.currentViewMode = 'notes';
                this.viewNotesBtn.classList.add('active');
                this.viewJsonBtn.classList.remove('active');
                this.renderMemoryBankFragments(this.cachedFragments);
            });

            this.viewJsonBtn.addEventListener('click', () => {
                this.currentViewMode = 'json';
                this.viewJsonBtn.classList.add('active');
                this.viewNotesBtn.classList.remove('active');
                this.renderMemoryBankFragments(this.cachedFragments);
            });
        }

        // Mini deposit buttons on subsystem cards
        this.miniSendBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const system = btn.dataset.system;
                this.highlightSystemCard(system);
                this.appendTrace('EVENT_DEPOSITED', `System [${system.toUpperCase()}] deposited note to Memory Bank.`, 'memory');
            });
        });
    }

    async loadMemoryBank() {
        try {
            const res = await fetch(`${this.memoryApiUrl}?customer_id=${this.customerId}`);
            const data = await res.json();
            this.cachedFragments = data.fragments || [];
            this.renderMemoryBankFragments(this.cachedFragments);
        } catch (err) {
            console.error('Failed to load Memory Bank state:', err);
        }
    }

    async reseedMemoryBank() {
        try {
            const res = await fetch(this.seedApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ customer_id: this.customerId }),
            });
            const data = await res.json();
            this.cachedFragments = data.fragments || [];
            this.renderMemoryBankFragments(this.cachedFragments);

            // Reset visual states
            this.cardBadge.className = 'badge-status danger';
            this.cardBadge.innerText = 'RESTRICTED';
            this.visualCard.className = 'card-chip-preview';
            this.applePayStatus.className = 'apple-pay-badge-restricted';
            this.applePayStatus.innerText = 'Provisioning Blocked (Card Locked)';
            this.topMemoryStatus.innerText = 'Synchronized';

            this.appendTrace('MEMORY_RESET', 'Memory Bank re-seeded with 3 baseline cross-system events.', 'memory');
        } catch (err) {
            console.error('Failed to reseed Memory Bank:', err);
        }
    }

    renderMemoryBankFragments(fragments) {
        if (!fragments || fragments.length === 0) {
            this.memoryTerminal.innerHTML = '<div class="note-summary" style="color:#64748b;">No active memory notes in vault.</div>';
            this.memoryBadge.innerText = '0 Notes Loaded';
            return;
        }

        this.memoryBadge.innerText = `${fragments.length} Notes Loaded`;

        if (this.currentViewMode === 'json') {
            this.memoryTerminal.innerHTML = `<pre style="color:#a5f3fc; font-size:0.7rem;">${JSON.stringify(fragments, null, 2)}</pre>`;
            return;
        }

        this.memoryTerminal.innerHTML = fragments.map((f, i) => `
            <div class="memory-note-item" id="mem-item-${i}">
                <div class="note-header">
                    <span>#${i+1} [${f.channel}]</span>
                    <span>${f.day_label}</span>
                </div>
                <div class="note-summary">${f.summary}</div>
                <div class="note-meta">
                    <strong>Severity:</strong> <span style="color:${f.severity === 'HIGH' ? '#f87171' : '#fbbf24'}">${f.severity}</span> | <strong>ID:</strong> ${f.fragment_id}
                </div>
            </div>
        `).join('');
    }

    highlightSystemCard(systemKey) {
        const idMap = {
            fraud: 'card-fraud',
            ivr: 'card-ivr',
            mobile: 'card-mobile',
        };
        const card = document.getElementById(idMap[systemKey]);
        if (card) {
            card.classList.add('pulsing');
            setTimeout(() => card.classList.remove('pulsing'), 1200);
        }
    }

    async playSimulationSequence() {
        this.appendTrace('SIMULATION_START', 'Replaying 2-day cross-system event ingestion timeline...', 'thought');

        // Step 1: Fraud Event
        this.highlightSystemCard('fraud');
        this.appendTrace('INGESTION_D1_0915', 'Fraud Velocity Engine deposited note: Dual-City Logins -> Card *4821 Locked.', 'memory');
        await new Promise(r => setTimeout(r, 900));

        // Step 2: Telephony IVR Event
        this.highlightSystemCard('ivr');
        this.appendTrace('INGESTION_D1_1432', 'Contact Center IVR deposited note: Target $142.50 Decline -> Call Dropped Before 2FA.', 'memory');
        await new Promise(r => setTimeout(r, 900));

        // Step 3: Mobile Banking Event
        this.highlightSystemCard('mobile');
        this.appendTrace('INGESTION_D2_1120', 'Mobile App deposited note: Apple Pay Setup Failed (CARD_STATUS_LOCKED_RESTRICTED).', 'memory');
        await new Promise(r => setTimeout(r, 600));

        this.appendTrace('SIMULATION_READY', 'All 3 notes anchored in Memory Bank. Ready for zero-question synthesis.', 'synthesis');
    }

    appendTrace(badge, message, type = 'thought') {
        const item = document.createElement('div');
        item.className = `trace-item ${type}`;
        item.innerHTML = `
            <span class="trace-badge">${badge}</span>
            <span class="trace-msg">${message}</span>
        `;
        this.traceLogs.appendChild(item);
        this.traceLogs.scrollTop = this.traceLogs.scrollHeight;
    }

    appendChatMessage(sender, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${sender}`;
        
        // Format markdown & bold tokens
        const formattedText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:0.1rem 0.3rem;border-radius:3px;color:#38bdf8;">$1</code>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');

        msgDiv.innerHTML = `<div class="msg-bubble">${formattedText}</div>`;
        this.chatViewport.appendChild(msgDiv);
        this.chatViewport.scrollTop = this.chatViewport.scrollHeight;
        return msgDiv;
    }

    executeChatWorkflow(prompt) {
        // Append customer user message
        this.appendChatMessage('user', prompt);
        this.chatInput.value = '';

        // Clear dynamic A2UI container
        this.a2uiContainer.innerHTML = '';

        // Append loading placeholder bubble
        const agentMessageDiv = this.appendChatMessage('agent', 'Connecting to Gemini Enterprise Memory Bank...');
        const bubble = agentMessageDiv.querySelector('.msg-bubble');

        this.appendTrace('USER_DISPATCH', `Received prompt: "${prompt}"`, 'thought');

        // Connect to SSE stream
        const queryUrl = `${this.streamApiUrl}?prompt=${encodeURIComponent(prompt)}&session_id=${encodeURIComponent(this.sessionId)}&customer_id=${encodeURIComponent(this.customerId)}`;
        const eventSource = new EventSource(queryUrl);

        eventSource.onmessage = (event) => {
            try {
                const rpc = JSON.parse(event.data);
                this.routeRpcFrame(rpc, bubble);
            } catch (err) {
                console.error('Error parsing SSE frame:', err);
            }
        };

        eventSource.onerror = (err) => {
            eventSource.close();
        };
    }

    routeRpcFrame(rpc, bubble) {
        const { method, params } = rpc;

        switch (method) {
            case 'onAgentThought':
                this.appendTrace('AGENT_REASONING', params.message, 'thought');
                break;

            case 'onMemoryBankAccess':
                this.appendTrace('MEMORY_RETRIEVAL', `Retrieved ${params.fragment_count} cross-system notes for ${params.customer_id}.`, 'memory');
                break;

            case 'onAgentSynthesis':
                this.appendTrace('SYNTHESIS_DELIVERED', 'Reconstructed full causal chain. Zero questions asked.', 'synthesis');
                bubble.innerHTML = params.narrative
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:0.1rem 0.3rem;border-radius:3px;color:#38bdf8;">$1</code>')
                    .replace(/\n\n/g, '<br><br>')
                    .replace(/\n/g, '<br>');
                this.chatViewport.scrollTop = this.chatViewport.scrollHeight;
                break;

            case 'onUiComponentDelivery':
                this.buildA2UiWidget(params.payload);
                break;

            default:
                console.warn('Unhandled method:', method);
        }
    }

    buildA2UiWidget(payload) {
        if (!payload || payload.type !== 'MemorySynthesisCard') return;

        const timelineHtml = (payload.timeline || []).map(step => `
            <div class="a2ui-timeline-step">
                <div class="step-time">${step.day}<br>${step.time}</div>
                <div class="step-content">
                    <div class="step-title">${step.title} <span class="badge-status ${step.badge_color}">${step.status_badge}</span></div>
                    <div class="step-desc">${step.detail}</div>
                </div>
            </div>
        `).join('');

        const widget = document.createElement('div');
        widget.className = 'a2ui-card';
        widget.innerHTML = `
            <div class="a2ui-card-header">
                <span class="a2ui-card-title">🔍 ${payload.title}</span>
                <span class="meta-chip">Trigger: ${payload.root_cause}</span>
            </div>
            <div class="a2ui-timeline">
                ${timelineHtml}
            </div>
            <div class="a2ui-action-box" id="a2ui-action-box">
                <div class="action-info">
                    <h4>${payload.resolution.label}</h4>
                    <p>${payload.resolution.description}</p>
                </div>
                <button class="btn-resolve" id="execute-unlock-btn">⚡ Unlock Card *4821</button>
            </div>
        `;

        this.a2uiContainer.innerHTML = '';
        this.a2uiContainer.appendChild(widget);

        // Bind 1-click resolution button
        const unlockBtn = widget.querySelector('#execute-unlock-btn');
        if (unlockBtn) {
            unlockBtn.addEventListener('click', () => {
                this.executeUnlockAction(widget);
            });
        }
    }

    async executeUnlockAction(widget) {
        try {
            const res = await fetch(this.unlockApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ customer_id: this.customerId }),
            });
            const data = await res.json();
            
            // Visual state transformation to Emerald Active
            this.cardBadge.className = 'badge-status success';
            this.cardBadge.innerText = 'ACTIVE';
            this.visualCard.classList.add('active-green');

            this.applePayStatus.className = 'apple-pay-badge-active';
            this.applePayStatus.innerText = '✅ Active & Ready in Apple Wallet';

            const actionBox = widget.querySelector('#a2ui-action-box');
            if (actionBox) {
                actionBox.innerHTML = `
                    <div class="action-info">
                        <h4 style="color: #34d399;">✅ Card Unlocked & Apple Pay Tokenized</h4>
                        <p>${data.message}</p>
                    </div>
                `;
            }

            this.appendTrace('RESOLUTION_COMPLETE', 'Biometric identity verified. Restriction lifted. Apple Pay active.', 'synthesis');
            this.loadMemoryBank();
        } catch (err) {
            console.error('Failed to execute unlock action:', err);
        }
    }
}

// Bootstrap UI on page load
document.addEventListener('DOMContentLoaded', () => {
    window.uiEngine = new MemoryBankUiEngine();
});
