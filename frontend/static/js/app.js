/**
 * SYSTEM PATTERN: DYNAMIC CLIENT COMPONENT FACTORY & SSE PARSER ENGINE
 * Handles:
 * - Scale Memory Bank visualization with Veracity Evaluations
 * - Pre-Write Claim Veracity Validation Layer
 * - Consolidated Memory Bank Audit Sweeps & Anomaly Detection
 * - Real-Time JSON-RPC 2.0 streaming & A2UI component rendering
 * - Multi-Agent System Roster Modal (8 Agents)
 * Reference: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
 */

class MemoryBankUiEngine {
    constructor() {
        this.streamApiUrl = '/api/chat/stream';
        this.memoryApiUrl = '/api/memory/get';
        this.seedApiUrl = '/api/memory/seed';
        this.unlockApiUrl = '/api/card/unlock';
        this.agentsApiUrl = '/api/agents/list';
        this.validateClaimApiUrl = '/api/claims/validate-and-write';
        this.auditSweepApiUrl = '/api/audit/sweep';

        this.customerId = 'cust_jpmc_88329';
        this.sessionId = 'sess-live-trace-4821';
        this.currentViewMode = 'notes'; // 'notes', 'audit', or 'json'
        this.cachedFragments = [];
        this.cachedAuditReport = null;
        this.cachedAgents = [];

        this.initDOMElements();
        this.bindEvents();
        this.loadMemoryBank();
        this.loadAgentsRoster();
    }

    initDOMElements() {
        this.memoryTerminal = document.getElementById('memory-terminal-body');
        this.memoryBadge = document.getElementById('memory-count-badge');
        this.topMemoryStatus = document.getElementById('top-memory-status');
        this.topAuditStatus = document.getElementById('top-audit-status');
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

        // View tabs
        this.viewNotesBtn = document.getElementById('view-notes-btn');
        this.viewAuditBtn = document.getElementById('view-audit-btn');
        this.viewJsonBtn = document.getElementById('view-json-btn');

        // Agents modal
        this.viewAgentsBtn = document.getElementById('view-agents-btn');
        this.runAuditSweepBtn = document.getElementById('run-audit-sweep-btn');
        this.agentsModal = document.getElementById('agents-modal');
        this.closeModalBtn = document.getElementById('close-modal-btn');
        this.agentsRosterContainer = document.getElementById('agents-roster-container');

        // Pre-write veracity validator
        this.validatorChannelSelect = document.getElementById('validator-channel-select');
        this.validatorClaimInput = document.getElementById('validator-claim-input');
        this.validateWriteBtn = document.getElementById('validate-write-btn');
        this.validatorResult = document.getElementById('validator-result');
        this.claimChips = document.querySelectorAll('.claim-chip');

        this.promptChips = document.querySelectorAll('.quick-chip-btn');
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

        // Agents modal
        if (this.viewAgentsBtn && this.agentsModal) {
            this.viewAgentsBtn.addEventListener('click', () => {
                this.agentsModal.style.display = 'flex';
            });
        }
        if (this.closeModalBtn && this.agentsModal) {
            this.closeModalBtn.addEventListener('click', () => {
                this.agentsModal.style.display = 'none';
            });
        }
        window.addEventListener('click', (e) => {
            if (e.target === this.agentsModal) {
                this.agentsModal.style.display = 'none';
            }
        });

        // Audit Sweep top button
        if (this.runAuditSweepBtn) {
            this.runAuditSweepBtn.addEventListener('click', () => {
                this.executeAuditSweep();
            });
        }

        // Pre-write claim chips
        this.claimChips.forEach(chip => {
            chip.addEventListener('click', () => {
                this.validatorClaimInput.value = chip.dataset.claim;
            });
        });

        // Pre-write claim validator execution
        if (this.validateWriteBtn) {
            this.validateWriteBtn.addEventListener('click', () => {
                this.executePreWriteValidation();
            });
        }

        // View toggle buttons
        if (this.viewNotesBtn && this.viewJsonBtn && this.viewAuditBtn) {
            this.viewNotesBtn.addEventListener('click', () => {
                this.currentViewMode = 'notes';
                this.setActiveToggle(this.viewNotesBtn);
                this.renderMemoryBankFragments(this.cachedFragments);
            });

            this.viewAuditBtn.addEventListener('click', () => {
                this.currentViewMode = 'audit';
                this.setActiveToggle(this.viewAuditBtn);
                this.renderAuditReportView();
            });

            this.viewJsonBtn.addEventListener('click', () => {
                this.currentViewMode = 'json';
                this.setActiveToggle(this.viewJsonBtn);
                this.renderMemoryBankFragments(this.cachedFragments);
            });
        }
    }

    setActiveToggle(activeBtn) {
        [this.viewNotesBtn, this.viewAuditBtn, this.viewJsonBtn].forEach(btn => {
            if (btn) btn.classList.remove('active');
        });
        if (activeBtn) activeBtn.classList.add('active');
    }

    async loadAgentsRoster() {
        try {
            const res = await fetch(this.agentsApiUrl);
            const data = await res.json();
            this.cachedAgents = data.agents || [];
            this.renderAgentsRoster(this.cachedAgents);
        } catch (err) {
            console.error('Failed to load agents list:', err);
        }
    }

    renderAgentsRoster(agents) {
        if (!this.agentsRosterContainer) return;
        this.agentsRosterContainer.innerHTML = agents.map(agent => {
            let badgeClass = 'producer';
            if (agent.agent_type === 'PRE_WRITE_VALIDATOR') badgeClass = 'validator';
            if (agent.agent_type === 'CONSOLIDATED_AUDITOR') badgeClass = 'auditor';
            if (agent.agent_type === 'LEAD_SYNTHESIZER') badgeClass = 'synthesizer';

            return `
                <div class="agent-card">
                    <div class="agent-card-header">
                        <span class="agent-card-title">${agent.role}</span>
                        <span class="agent-type-badge ${badgeClass}">${agent.agent_type}</span>
                    </div>
                    <div style="font-size:0.72rem; color:#38bdf8; font-family:monospace;">${agent.name}</div>
                    <p class="agent-desc">${agent.description}</p>
                    <div class="agent-tools-box">
                        <strong>Tools:</strong> ${agent.tools.join(', ')}
                    </div>
                </div>
            `;
        }).join('');
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
            this.validatorResult.style.display = 'none';

            this.appendTrace('MEMORY_RESET', 'Memory Bank re-seeded with 3 baseline cross-system events.', 'memory');
        } catch (err) {
            console.error('Failed to reseed Memory Bank:', err);
        }
    }

    async executePreWriteValidation() {
        const channel = this.validatorChannelSelect.value;
        const claimText = this.validatorClaimInput.value.trim();
        if (!claimText) return;

        this.appendTrace('PRE_WRITE_VALIDATION', `ClaimVeracityValidatorAgent evaluating claim in [${channel}]: "${claimText}"...`, 'thought');

        try {
            const res = await fetch(this.validateClaimApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: this.customerId,
                    channel: channel,
                    claim_text: claimText,
                    summary: `Customer Session Claim: ${claimText}`,
                    day_label: 'Live Session - Just Now',
                    severity: 'MEDIUM',
                }),
            });
            const data = await res.json();
            const evalObj = data.veracity_evaluation;

            this.validatorResult.style.display = 'block';
            if (evalObj.veracity_status === 'VERIFIED_TRUE') {
                this.validatorResult.className = 'validator-result-box verified';
                this.validatorResult.innerHTML = `
                    <strong>✅ Claim Verified (Confidence: ${Math.round(evalObj.confidence_score * 100)}%)</strong><br>
                    <span>${evalObj.corroborating_telemetry.join('; ')}</span><br>
                    <em style="color:#a7f3d0; font-size:0.68rem;">Committed to Memory Bank as verified observation note.</em>
                `;
                this.appendTrace('VERACITY_TRUE', `Pre-write validation passed: ${evalObj.corroborating_telemetry[0] || 'Corroborated'}`, 'synthesis');
            } else {
                this.validatorResult.className = 'validator-result-box contradicted';
                this.validatorResult.innerHTML = `
                    <strong>⚠️ Claim Contradicted by Telemetry (${evalObj.veracity_status})</strong><br>
                    <span>${evalObj.discrepancy_details || 'Contradicted by authoritative ground-truth records.'}</span><br>
                    <em style="color:#fca5a5; font-size:0.68rem;">Written to Memory Bank with ANOMALY / CONTRADICTION flag for Audit Agent.</em>
                `;
                this.appendTrace('VERACITY_CONTRADICTED', `Pre-write validation flagged contradiction: ${evalObj.discrepancy_details || 'Mismatch'}`, 'thought');
            }

            this.loadMemoryBank();
        } catch (err) {
            console.error('Pre-write validation failed:', err);
        }
    }

    async executeAuditSweep() {
        this.appendTrace('AUDIT_SWEEP_START', 'MemoryBankAuditAgent executing consolidated sweep across customer Memory Banks...', 'thought');
        this.topAuditStatus.innerText = 'Sweeping...';

        try {
            const res = await fetch(this.auditSweepApiUrl, { method: 'POST' });
            const data = await res.json();
            this.cachedAuditReport = data.report;

            this.topAuditStatus.innerText = `${this.cachedAuditReport.anomalies_detected.length} Anomalies`;
            this.appendTrace('AUDIT_SWEEP_COMPLETE', `Scanned ${this.cachedAuditReport.total_fragments_scanned} memory fragments. Found ${this.cachedAuditReport.anomalies_detected.length} anomalies.`, 'synthesis');

            // Switch to audit tab
            this.currentViewMode = 'audit';
            this.setActiveToggle(this.viewAuditBtn);
            this.renderAuditReportView();
        } catch (err) {
            console.error('Audit sweep failed:', err);
        }
    }

    renderAuditReportView() {
        if (!this.cachedAuditReport) {
            this.memoryTerminal.innerHTML = `
                <div style="padding:1rem; color:#94a3b8; text-align:center;">
                    <p>No audit sweep executed yet.</p>
                    <button id="run-audit-inline-btn" class="btn-primary btn-sm" style="margin:0.75rem auto 0 auto;">⚡ Run Consolidated Memory Bank Sweep</button>
                </div>
            `;
            const inlineBtn = document.getElementById('run-audit-inline-btn');
            if (inlineBtn) inlineBtn.addEventListener('click', () => this.executeAuditSweep());
            return;
        }

        const rep = this.cachedAuditReport;
        this.memoryBadge.innerText = `${rep.anomalies_detected.length} Anomalies`;

        const anomaliesHtml = rep.anomalies_detected.map((a, i) => `
            <div class="audit-anomaly-card">
                <div class="audit-anomaly-header">
                    <span>⚠️ #${i+1} [${a.anomaly_type}]</span>
                    <span class="badge-status danger">${a.severity}</span>
                </div>
                <div class="audit-anomaly-desc">${a.description}</div>
                <div class="audit-anomaly-action"><strong>Recommended Action:</strong> ${a.recommended_action}</div>
                <div style="font-size:0.65rem; color:#64748b;">Customer: ${a.customer_id} | Channels: ${a.affected_channels.join(', ')}</div>
            </div>
        `).join('');

        this.memoryTerminal.innerHTML = `
            <div style="margin-bottom:0.75rem; padding-bottom:0.5rem; border-bottom:1px solid rgba(255,255,255,0.08);">
                <div style="color:#f87171; font-weight:700; font-size:0.82rem;">🔍 Consolidated Audit Sweep Report</div>
                <div style="font-size:0.72rem; color:#cbd5e1; margin-top:0.2rem;">${rep.summary}</div>
            </div>
            ${anomaliesHtml || '<div style="color:#34d399;">No active anomalies detected across audited Memory Banks.</div>'}
        `;
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

        this.memoryTerminal.innerHTML = fragments.map((f, i) => {
            let veracityBadge = '';
            if (f.veracity_evaluation) {
                const status = f.veracity_evaluation.veracity_status;
                const score = Math.round(f.veracity_evaluation.confidence_score * 100);
                if (status === 'VERIFIED_TRUE') {
                    veracityBadge = `<span class="veracity-badge true">✓ Verified (${score}%)</span>`;
                } else {
                    veracityBadge = `<span class="veracity-badge contradicted">⚠️ ${status} (${score}%)</span>`;
                }
            }

            return `
                <div class="memory-note-item" id="mem-item-${i}">
                    <div class="note-header">
                        <span>#${i+1} [${f.channel}]</span>
                        <span>${f.day_label}</span>
                    </div>
                    <div class="note-summary">${f.summary}</div>
                    <div class="note-meta" style="display:flex; justify-content:space-between; align-items:center;">
                        <span><strong>Severity:</strong> <span style="color:${f.severity === 'HIGH' ? '#f87171' : '#fbbf24'}">${f.severity}</span> | <strong>ID:</strong> ${f.fragment_id}</span>
                        ${veracityBadge}
                    </div>
                </div>
            `;
        }).join('');
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
        this.appendTrace('INGESTION_D1_0915', 'Fraud Monitoring Agent deposited note: Dual-City Logins -> Card *4821 Locked (Veracity: Verified).', 'memory');
        await new Promise(r => setTimeout(r, 900));

        // Step 2: Telephony IVR Event
        this.highlightSystemCard('ivr');
        this.appendTrace('INGESTION_D1_1432', 'Telephony IVR Agent deposited note: Target $142.50 Decline -> Call Dropped Before 2FA (Veracity: Verified).', 'memory');
        await new Promise(r => setTimeout(r, 900));

        // Step 3: Mobile Banking Event
        this.highlightSystemCard('mobile');
        this.appendTrace('INGESTION_D2_1120', 'Mobile Banking Agent deposited note: Apple Pay Setup Failed (CARD_STATUS_LOCKED_RESTRICTED).', 'memory');
        await new Promise(r => setTimeout(r, 600));

        this.appendTrace('SIMULATION_READY', 'All notes anchored in Scale Memory Bank. Ready for zero-question synthesis.', 'synthesis');
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
