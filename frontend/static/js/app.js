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
        this.currentViewMode = 'notes'; // 'notes', 'admin', 'compaction', 'kg', 'comparison', 'audit', or 'json'
        this.cachedFragments = [];
        this.cachedAuditReport = null;
        this.cachedAgents = [];
        this.cachedAdminCase = null;

        this.initDOMElements();
        this.bindEvents();
        this.loadMemoryBank();
        this.loadAgentsRoster();
        this.loadAdminReviewCase();
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

        // Admin Oversight Widget elements
        this.adminConfidenceBadge = document.getElementById('admin-confidence-badge');
        this.adminVerificationSummary = document.getElementById('admin-verification-summary');
        this.simVerifyPassBtn = document.getElementById('sim-verify-pass-btn');
        this.simVerifyFailBtn = document.getElementById('sim-verify-fail-btn');
        this.adminApproveYesBtn = document.getElementById('admin-approve-yes-btn');
        this.adminRejectNoBtn = document.getElementById('admin-reject-no-btn');

        // View tabs
        this.viewNotesBtn = document.getElementById('view-notes-btn');
        this.viewAdminBtn = document.getElementById('view-admin-btn');
        this.viewCompactionBtn = document.getElementById('view-compaction-btn');
        this.viewKgBtn = document.getElementById('view-kg-btn');
        this.viewComparisonBtn = document.getElementById('view-comparison-btn');
        this.topComparisonBtn = document.getElementById('top-comparison-btn');
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

        // Admin Oversight simulation & decision buttons
        if (this.simVerifyPassBtn) {
            this.simVerifyPassBtn.addEventListener('click', () => {
                this.simulateChatVerification('PASSED');
            });
        }
        if (this.simVerifyFailBtn) {
            this.simVerifyFailBtn.addEventListener('click', () => {
                this.simulateChatVerification('FAILED');
            });
        }
        if (this.adminApproveYesBtn) {
            this.adminApproveYesBtn.addEventListener('click', () => {
                this.executeAdminDecision('APPROVED_YES');
            });
        }
        if (this.adminRejectNoBtn) {
            this.adminRejectNoBtn.addEventListener('click', () => {
                this.executeAdminDecision('REJECTED_NO');
            });
        }

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
        if (this.viewNotesBtn) {
            this.viewNotesBtn.addEventListener('click', () => {
                this.currentViewMode = 'notes';
                this.setActiveToggle(this.viewNotesBtn);
                this.renderMemoryBankFragments(this.cachedFragments);
            });
        }
        if (this.viewAdminBtn) {
            this.viewAdminBtn.addEventListener('click', () => {
                this.currentViewMode = 'admin';
                this.setActiveToggle(this.viewAdminBtn);
                this.renderAdminOversightView();
            });
        }
        if (this.viewCompactionBtn) {
            this.viewCompactionBtn.addEventListener('click', () => {
                this.currentViewMode = 'compaction';
                this.setActiveToggle(this.viewCompactionBtn);
                this.renderCompactionAndTokenomicsView();
            });
        }
        if (this.viewKgBtn) {
            this.viewKgBtn.addEventListener('click', () => {
                this.currentViewMode = 'kg';
                this.setActiveToggle(this.viewKgBtn);
                this.renderKnowledgeCatalogView();
            });
        }
        if (this.viewComparisonBtn) {
            this.viewComparisonBtn.addEventListener('click', () => {
                this.currentViewMode = 'comparison';
                this.setActiveToggle(this.viewComparisonBtn);
                this.renderComparisonView();
            });
        }
        if (this.topComparisonBtn) {
            this.topComparisonBtn.addEventListener('click', () => {
                this.currentViewMode = 'comparison';
                this.setActiveToggle(this.viewComparisonBtn);
                this.renderComparisonView();
            });
        }
        if (this.viewAuditBtn) {
            this.viewAuditBtn.addEventListener('click', () => {
                this.currentViewMode = 'audit';
                this.setActiveToggle(this.viewAuditBtn);
                this.renderAuditReportView();
            });
        }
        if (this.viewJsonBtn) {
            this.viewJsonBtn.addEventListener('click', () => {
                this.currentViewMode = 'json';
                this.setActiveToggle(this.viewJsonBtn);
                this.renderMemoryBankFragments(this.cachedFragments);
            });
        }
    }

    setActiveToggle(activeBtn) {
        [this.viewNotesBtn, this.viewAdminBtn, this.viewCompactionBtn, this.viewKgBtn, this.viewComparisonBtn, this.viewAuditBtn, this.viewJsonBtn].forEach(btn => {
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
            if (data.admin_review_case) {
                this.cachedAdminCase = data.admin_review_case;
                this.updateAdminWidget(this.cachedAdminCase);
            }

            // Reset visual states
            this.cardBadge.className = 'badge-status danger';
            this.cardBadge.innerText = 'RESTRICTED';
            this.visualCard.className = 'card-chip-preview';
            this.applePayStatus.className = 'apple-pay-badge-restricted';
            this.applePayStatus.innerText = 'Provisioning Blocked (Card Locked)';
            this.topMemoryStatus.innerText = 'Synchronized';
            this.validatorResult.style.display = 'none';

            this.appendTrace('MEMORY_RESET', 'Memory Bank & Admin Oversight Queue re-seeded with baseline scenario.', 'memory');
        } catch (err) {
            console.error('Failed to reseed Memory Bank:', err);
        }
    }

    async loadAdminReviewCase() {
        try {
            const res = await fetch(`/api/admin/card-review?customer_id=${this.customerId}`);
            const data = await res.json();
            this.cachedAdminCase = data.admin_review_case;
            this.updateAdminWidget(this.cachedAdminCase);
        } catch (err) {
            console.error('Failed to load Admin Review Case:', err);
        }
    }

    updateAdminWidget(caseObj) {
        if (!caseObj) return;
        const pct = Math.round((caseObj.confidence_score || 0.98) * 100);
        const passed = caseObj.verification_status === 'VERIFIED_PASSED';

        if (this.adminConfidenceBadge) {
            this.adminConfidenceBadge.className = passed ? 'badge-status success' : 'badge-status danger';
            this.adminConfidenceBadge.innerText = `Confidence: ${pct}% (${passed ? 'PASSED' : 'FAILED'})`;
        }

        if (this.adminVerificationSummary) {
            const statusText = caseObj.admin_decision === 'APPROVED_YES'
                ? '<span style="color:#34d399; font-weight:700;">✅ ADMIN APPROVED (CARD ENABLED)</span>'
                : caseObj.admin_decision === 'REJECTED_NO'
                    ? '<span style="color:#f87171; font-weight:700;">❌ ADMIN DENIED (CARD RESTRICTED)</span>'
                    : passed
                        ? '<span style="color:#fde047;">⏳ Verified in Chat — Awaiting Admin Approval (Click YES)</span>'
                        : '<span style="color:#f87171;">⚠️ Verification Failed — Recommended Action: Click NO</span>';

            this.adminVerificationSummary.innerHTML = `
                <strong>Flagged Tx:</strong> £185 London Heathrow Duty Free Decline<br>
                <strong>Chat Verification:</strong> ${caseObj.customer_chat_verification_transcript || ''}<br>
                <strong>Oversight Status:</strong> ${statusText}
            `;
        }

        if (caseObj.card_status === 'ACTIVE') {
            this.cardBadge.className = 'badge-status success';
            this.cardBadge.innerText = 'ACTIVE (UNLOCKED)';
            this.visualCard.className = 'card-chip-preview unlocked';
            this.applePayStatus.className = 'apple-pay-badge-active';
            this.applePayStatus.innerText = 'Apple Pay & POS Active (Admin Enabled)';
        } else {
            this.cardBadge.className = 'badge-status danger';
            this.cardBadge.innerText = caseObj.admin_decision === 'REJECTED_NO' ? 'RESTRICTED (DENIED)' : 'RESTRICTED';
            this.visualCard.className = 'card-chip-preview';
            this.applePayStatus.className = 'apple-pay-badge-restricted';
            this.applePayStatus.innerText = caseObj.admin_decision === 'REJECTED_NO'
                ? 'Blocked (Admin Denied Unlock Request)'
                : 'Provisioning Blocked (Card Locked)';
        }

        if (this.currentViewMode === 'admin') {
            this.renderAdminOversightView();
        }
    }

    async simulateChatVerification(scenario) {
        const sampleMsg = scenario === 'PASSED'
            ? "Hi Support, my card *4821 was declined at London Heathrow Duty Free for £185. I am traveling in London on my registered travel notice and completed FaceID verification on my iPhone 16 Pro. Please unlock my card."
            : "I was never in Chicago and never logged in from Chicago! I don't have my primary phone for FaceID, just unlock my card right now!";

        this.appendChatMessage('user', sampleMsg);
        this.appendTrace('CHAT_VERIFY_START', `Evaluating customer chat verification statements (${scenario})...`, 'thought');

        try {
            const res = await fetch('/api/admin/chat-verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: this.customerId,
                    scenario: scenario,
                    chat_message: sampleMsg,
                }),
            });
            const data = await res.json();
            this.cachedAdminCase = data.admin_review_case;
            this.updateAdminWidget(this.cachedAdminCase);

            if (data.customer_chat_reply) {
                this.appendChatMessage('agent', data.customer_chat_reply);
            }
            this.appendTrace(
                scenario === 'PASSED' ? 'VERIFY_PASSED' : 'VERIFY_FAILED',
                `Customer Chat Verification evaluated: Confidence ${Math.round(this.cachedAdminCase.confidence_score * 100)}% (${this.cachedAdminCase.verification_status}). Escalated to Dashboard Admin.`,
                scenario === 'PASSED' ? 'synthesis' : 'thought'
            );
        } catch (err) {
            console.error('Chat verification failed:', err);
        }
    }

    async executeAdminDecision(decision) {
        this.appendTrace('ADMIN_DECISION', `Dashboard Admin executing card decision: ${decision}...`, 'thought');
        try {
            const res = await fetch('/api/admin/card-decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: this.customerId,
                    decision: decision,
                }),
            });
            const data = await res.json();
            this.cachedAdminCase = data.admin_review_case;
            this.updateAdminWidget(this.cachedAdminCase);

            if (data.customer_notification_message) {
                this.appendChatMessage('agent', data.customer_notification_message);
            }
            if (data.fragments) {
                this.cachedFragments = data.fragments;
                if (this.currentViewMode === 'notes') {
                    this.renderMemoryBankFragments(this.cachedFragments);
                }
            }

            this.appendTrace(
                decision === 'APPROVED_YES' ? 'ADMIN_APPROVED' : 'ADMIN_REJECTED',
                `Dashboard Admin ${decision === 'APPROVED_YES' ? 'ENABLED Card *4821' : 'kept Card *4821 RESTRICTED'} and notified customer in chat.`,
                'synthesis'
            );
        } catch (err) {
            console.error('Admin card decision failed:', err);
        }
    }

    renderAdminOversightView() {
        const c = this.cachedAdminCase || {};
        const pct = Math.round((c.confidence_score || 0.98) * 100);
        const passed = c.verification_status === 'VERIFIED_PASSED';
        this.memoryBadge.innerText = `Admin Review (${pct}%)`;

        const checksHtml = (c.verification_checks || []).map(chk => `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(15,23,42,0.7); padding:6px 10px; border-radius:6px; margin-bottom:5px; border-left:3px solid ${chk.status === 'PASSED' ? '#34d399' : '#f87171'};">
                <div>
                    <div style="font-weight:700; color:#f8fafc; font-size:0.75rem;">${chk.check_name}</div>
                    <div style="font-size:0.7rem; color:#cbd5e1;">${chk.detail}</div>
                </div>
                <span class="badge-status ${chk.status === 'PASSED' ? 'success' : 'danger'}" style="font-size:0.65rem;">${chk.status}</span>
            </div>
        `).join('');

        this.memoryTerminal.innerHTML = `
            <div style="padding:12px; color:#e2e8f0; font-size:0.78rem;">
                <div style="background:rgba(30,41,59,0.9); border:1px solid rgba(56,189,248,0.4); border-radius:8px; padding:12px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-weight:700; color:#38bdf8; font-size:0.86rem;">👮‍♂️ DASHBOARD ADMIN CARD OVERSIGHT & VERIFICATION REVIEW</span>
                        <span class="badge-status ${c.card_status === 'ACTIVE' ? 'success' : 'danger'}">CARD *4821: ${c.card_status || 'RESTRICTED'}</span>
                    </div>
                    <div style="font-size:0.74rem; color:#cbd5e1; margin-bottom:8px;">
                        <strong>System Flagged Transaction:</strong> ${c.flagged_transaction_summary || ''}<br>
                        <strong>System Block Reason:</strong> ${c.system_flag_reason || ''}
                    </div>
                    <div style="background:rgba(15,23,42,0.85); padding:8px 10px; border-radius:6px; border:1px solid rgba(255,255,255,0.08); margin-bottom:10px;">
                        <div style="font-weight:700; color:#fde047; font-size:0.74rem; margin-bottom:4px;">💬 Customer Support Chat Verification Transcript:</div>
                        <div style="font-style:italic; color:#f1f5f9; font-size:0.73rem;">${c.customer_chat_verification_transcript || ''}</div>
                    </div>

                    <div style="font-weight:700; color:#38bdf8; font-size:0.76rem; margin-bottom:6px;">
                        🔍 Identity & Telemetry Verification Checks (Confidence Score: <span style="color:${passed ? '#34d399' : '#f87171'};">${pct}% — ${c.verification_status}</span>):
                    </div>
                    ${checksHtml}

                    <div style="margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.12);">
                        <div style="font-weight:700; color:#fde047; font-size:0.76rem; margin-bottom:6px;">
                            ⚡ Dashboard Admin Oversight Decision (Sends Instant Notification to Customer Chat):
                        </div>
                        <div style="display:flex; gap:10px;">
                            <button id="admin-modal-approve-btn" class="btn-primary" style="flex:1; background:#059669; border-color:#10b981; font-weight:700; padding:8px;">
                                ✅ YES — Approve & Enable Card Access
                            </button>
                            <button id="admin-modal-reject-btn" class="btn-primary" style="flex:1; background:#dc2626; border-color:#ef4444; font-weight:700; padding:8px;">
                                ❌ NO — Deny & Keep Card Restricted
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const modalApprove = document.getElementById('admin-modal-approve-btn');
        const modalReject = document.getElementById('admin-modal-reject-btn');
        if (modalApprove) modalApprove.addEventListener('click', () => this.executeAdminDecision('APPROVED_YES'));
        if (modalReject) modalReject.addEventListener('click', () => this.executeAdminDecision('REJECTED_NO'));
    }

    async executePreWriteValidation() {
        const channel = this.validatorChannelSelect.value;
        const claimText = this.validatorClaimInput.value.trim();
        if (!claimText) return;

        this.appendTrace('PRE_WRITE_VALIDATION', `ClaimVeracityValidatorAgent evaluating claim strictly against relevant ground-truth avenues in [${channel}]: "${claimText}"...`, 'thought');

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
            const relevantAvenues = evalObj.relevant_avenues_checked || [];

            const relevantHtml = relevantAvenues.map((av, idx) => `
                <div style="margin-bottom:5px; padding:5px 8px; background:rgba(15,23,42,0.6); border-left:3px solid ${av.corroborates_claim ? '#34d399' : '#f87171'}; border-radius:4px;">
                    <div><strong>${idx + 1}. ${av.avenue_title}</strong> <span style="font-size:0.65rem; color:#94a3b8;">(${av.why_relevant})</span></div>
                    <div style="color:${av.corroborates_claim ? '#a7f3d0' : '#fca5a5'}; font-size:0.7rem;">${av.finding_summary}</div>
                </div>
            `).join('');

            const avenueHtml = `
                <div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.12); font-size:0.71rem; line-height:1.45;">
                    <div style="font-weight:700; color:#38bdf8; margin-bottom:6px;">
                        🔍 CLAIM-SPECIFIC GROUND-TRUTH FORENSIC AUDIT (${relevantAvenues.length} Relevant Avenues Checked):
                    </div>
                    ${relevantHtml}
                    ${evalObj.recommended_remediation ? `<div style="margin-top:6px; padding:4px 6px; background:rgba(245,158,11,0.12); border-radius:4px; color:#fde047;">• <strong>Governing Policy Action:</strong> ${evalObj.recommended_remediation}</div>` : ''}
                </div>
            `;

            this.validatorResult.style.display = 'block';
            if (evalObj.veracity_status === 'VERIFIED_TRUE') {
                this.validatorResult.className = 'validator-result-box verified';
                this.validatorResult.innerHTML = `
                    <strong>✅ Claim Verified Against Ground Truth (Confidence: ${Math.round(evalObj.confidence_score * 100)}%)</strong><br>
                    <span>${evalObj.corroborating_telemetry.join('<br>• ')}</span>
                    ${avenueHtml}
                    <em style="color:#a7f3d0; font-size:0.68rem; display:block; margin-top:6px;">Committed to Memory Bank as verified ground-truth observation note.</em>
                `;
                this.appendTrace('VERACITY_TRUE', `Claim-Specific Audit PASSED (${relevantAvenues.length} avenues corroborated): ${evalObj.corroborating_telemetry[0] || 'Verified'}`, 'synthesis');
            } else {
                this.validatorResult.className = 'validator-result-box contradicted';
                this.validatorResult.innerHTML = `
                    <strong>⚠️ Claim Contradicted by Telemetry (${evalObj.veracity_status})</strong><br>
                    <span>${evalObj.discrepancy_details || 'Contradicted by authoritative ground-truth records.'}</span>
                    ${avenueHtml}
                    <em style="color:#fca5a5; font-size:0.68rem; display:block; margin-top:6px;">Written to Memory Bank with ANOMALY / CONTRADICTION flag for Audit Agent.</em>
                `;
                this.appendTrace('VERACITY_CONTRADICTED', `Claim-Specific Audit flagged contradiction: ${evalObj.discrepancy_details || 'Mismatch'}`, 'thought');
            }

            this.loadMemoryBank();
            this.loadAdminReviewCase();
        } catch (err) {
            console.error('Pre-write validation failed:', err);
        }
    }

    async renderCompactionAndTokenomicsView() {
        this.appendTrace('COMPACTION_REQUEST', 'Triggering Asynchronous Memory Compaction (Dreaming Service) & Tokenomics evaluation...', 'thought');
        try {
            const [compRes, standRes] = await Promise.all([
                fetch('/api/memory/compact', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ customer_id: this.customerId }),
                }),
                fetch('/api/standalone/external-agent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        customer_id: this.customerId,
                        query: 'Customer disputing $1,000 Chicago charge while traveling in London',
                        framework: 'LangGraph (External Python Runtime on AWS ECS)',
                    }),
                }),
            ]);
            const compData = await compRes.json();
            const standData = await standRes.json();
            const report = compData.compaction_report;
            const bundle = standData.standalone_bundle;

            this.cachedFragments = compData.fragments || this.cachedFragments;
            this.memoryBadge.innerText = `${this.cachedFragments.length} Notes (Compacted)`;

            this.memoryTerminal.innerHTML = `
                <div style="padding:12px; color:#e2e8f0; font-size:0.78rem;">
                    <div style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.35); border-radius:8px; padding:12px; margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-weight:700; color:#34d399; font-size:0.85rem;">⚡ ASYNCHRONOUS MEMORY COMPACTION ('DREAMING SERVICE')</span>
                            <span style="background:#059669; color:#fff; padding:2px 8px; border-radius:99px; font-size:0.68rem; font-weight:700;">-${report.token_reduction_pct}% TOKENS</span>
                        </div>
                        <p style="margin:0 0 8px 0; color:#cbd5e1; font-size:0.74rem;">
                            Consolidates 3 years of multi-channel customer history (${report.raw_fragments_processed} raw turns) into high-density semantic memory nodes without blocking user response latency.
                        </p>
                        <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px; background:rgba(15,23,42,0.6); padding:8px; border-radius:6px; text-align:center;">
                            <div>
                                <div style="font-size:0.65rem; color:#94a3b8;">RAW 3-YR TOKENS</div>
                                <div style="font-size:0.95rem; font-weight:700; color:#f87171;">${report.raw_token_count.toLocaleString()}</div>
                            </div>
                            <div>
                                <div style="font-size:0.65rem; color:#94a3b8;">COMPACTED TOKENS</div>
                                <div style="font-size:0.95rem; font-weight:700; color:#34d399;">${report.compacted_token_count.toLocaleString()}</div>
                            </div>
                            <div>
                                <div style="font-size:0.65rem; color:#94a3b8;">SAVINGS / 1M CALLS</div>
                                <div style="font-size:0.95rem; font-weight:700; color:#38bdf8;">$${report.estimated_cost_savings_per_1m_queries_usd.toLocaleString()}</div>
                            </div>
                        </div>
                    </div>

                    <div style="background:rgba(30,41,59,0.75); border:1px solid rgba(148,163,184,0.2); border-radius:8px; padding:10px; margin-bottom:12px;">
                        <div style="font-weight:700; color:#38bdf8; margin-bottom:6px; font-size:0.78rem;">💡 DISTILLED DURABLE CUSTOMER INSIGHTS (EXTRACTED BY DREAMING SERVICE):</div>
                        ${report.distilled_customer_insights.map(ins => `<div style="margin-bottom:5px; font-size:0.73rem; color:#f1f5f9;">• ${ins}</div>`).join('')}
                    </div>

                    <div style="background:rgba(139,92,246,0.12); border:1px solid rgba(139,92,246,0.35); border-radius:8px; padding:10px;">
                        <div style="font-weight:700; color:#c4b5fd; margin-bottom:4px; font-size:0.78rem;">🔌 STANDALONE / DECOUPLED CLIENT DEMO (EXTERNAL RUNTIME):</div>
                        <div style="font-size:0.72rem; color:#cbd5e1; margin-bottom:6px;">
                            <strong>Caller Framework:</strong> <code>${bundle.caller_agent_framework}</code><br>
                            ${bundle.integration_note}
                        </div>
                        <div style="font-size:0.68rem; color:#93c5fd; font-family:monospace; background:rgba(15,23,42,0.75); padding:6px; border-radius:4px;">
                            POST /api/v1/memory-bank/retrieve ➔ Returned ${bundle.retrieved_memories.length} vectors (${bundle.tokenomics.retrieved_context_tokens} tokens vs ${bundle.tokenomics.uncompacted_3yr_history_tokens} raw tokens = ${bundle.tokenomics.token_savings_pct}% saved)
                        </div>
                    </div>
                </div>
            `;
        } catch (err) {
            console.error('Failed to render Compaction view:', err);
        }
    }

    async renderKnowledgeCatalogView() {
        this.appendTrace('KNOWLEDGE_CATALOG_QUERY', 'Querying Enterprise Knowledge Catalog, Semantic Entity Graph & AWS/On-Prem Hybrid Bridge...', 'thought');
        try {
            const res = await fetch(`/api/knowledge-catalog/overview?customer_id=${this.customerId}`);
            const data = await res.json();
            const graph = data.entity_graph || {};
            const connector = data.hybrid_connector || {};
            const policies = data.policies || [];

            this.memoryBadge.innerText = `${graph.node_count} Graph Entities`;

            this.memoryTerminal.innerHTML = `
                <div style="padding:12px; color:#e2e8f0; font-size:0.78rem;">
                    <div style="background:rgba(56,189,248,0.12); border:1px solid rgba(56,189,248,0.35); border-radius:8px; padding:10px; margin-bottom:12px;">
                        <div style="font-weight:700; color:#38bdf8; margin-bottom:4px; font-size:0.82rem;">🕸️ ENTERPRISE SEMANTIC GRAPH & ENTITY MAPPING (${graph.node_count} Nodes, ${graph.edge_count} Relationships)</div>
                        <p style="margin:0 0 8px 0; font-size:0.72rem; color:#cbd5e1;">
                            Maps enduring structural ground truths: Customer ➔ Account ➔ Card Instrument (*4821) ➔ Digital Wallet Token ➔ Travel Notice (London, UK) ➔ Disputed Transaction ($1,000 Chicago) ➔ Governing Policies.
                        </p>
                        <div style="display:flex; flex-wrap:wrap; gap:6px;">
                            ${(graph.nodes || []).map(n => `
                                <span style="background:rgba(15,23,42,0.8); border:1px solid rgba(56,189,248,0.3); padding:3px 7px; border-radius:5px; font-size:0.68rem;">
                                    <strong style="color:#7dd3fc;">[${n.entity_type}]</strong> ${n.label}
                                </span>
                            `).join('')}
                        </div>
                    </div>

                    <div style="background:rgba(245,158,11,0.12); border:1px solid rgba(245,158,11,0.35); border-radius:8px; padding:10px; margin-bottom:12px;">
                        <div style="font-weight:700; color:#fbbf24; margin-bottom:6px; font-size:0.8rem;">📜 INSTITUTIONAL POLICIES IN KNOWLEDGE CATALOG:</div>
                        ${policies.map(p => `
                            <div style="margin-bottom:7px; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08);">
                                <div style="font-weight:700; color:#fde68a; font-size:0.74rem;">${p.policy_id}: ${p.title}</div>
                                <div style="font-size:0.7rem; color:#cbd5e1;">${p.description}</div>
                            </div>
                        `).join('')}
                    </div>

                    <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:10px;">
                        <div style="font-weight:700; color:#34d399; margin-bottom:4px; font-size:0.8rem;">☁️ AWS & ON-PREM HYBRID DATA BRIDGE (ZERO AGENT BUILDER LOCK-IN):</div>
                        <div style="font-size:0.71rem; color:#cbd5e1; margin-bottom:6px;">
                            <strong>Auth:</strong> ${connector.auth_mechanism}<br>
                            <strong>Transport:</strong> ${connector.network_transport}
                        </div>
                        ${(connector.data_sources || []).map(ds => `
                            <div style="display:flex; justify-content:space-between; background:rgba(15,23,42,0.65); padding:5px 8px; border-radius:4px; margin-bottom:4px; font-size:0.69rem;">
                                <span><strong>${ds.environment}:</strong> ${ds.service}</span>
                                <span style="color:#34d399; font-family:monospace;">p50: ${ds.p50_latency_ms}ms | ${ds.status}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        } catch (err) {
            console.error('Failed to render Knowledge Catalog view:', err);
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

    async renderComparisonView(customPrompt = null) {
        const defaultPrompt = customPrompt || 'Why was my Apple Pay declined in London and what about the $1,000 Chicago charge?';
        this.memoryBadge.innerText = 'ADK vs Custom';
        this.memoryTerminal.innerHTML = `
            <div style="padding:0.85rem; background:rgba(15,23,42,0.8); border-radius:8px; border:1px solid rgba(56,189,248,0.3); margin-bottom:0.85rem;">
                <div style="font-weight:700; color:#38bdf8; font-size:0.85rem; margin-bottom:0.35rem;">⚖️ Live Architectural & Execution Comparison: Google Native ADK vs. Custom Framework Agent</div>
                <div style="font-size:0.74rem; color:#cbd5e1; margin-bottom:0.65rem;">
                    Both agents connect to the exact same <strong>Google Cloud Vertex AI Memory Bank (reasoningEngines/915213137995628544)</strong> and <strong>Knowledge Catalog (text-embedding-005)</strong>.
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <input type="text" id="comparison-prompt-input" value="${defaultPrompt}" style="flex:1; background:#0f172a; border:1px solid #334155; color:#f8fafc; padding:0.45rem 0.65rem; border-radius:6px; font-size:0.75rem;" />
                    <button id="run-comparison-inline-btn" class="btn-primary btn-sm">⚡ Run Live Comparison</button>
                </div>
            </div>
            <div id="comparison-results-body" style="padding:1.2rem; text-align:center; color:#94a3b8; font-size:0.78rem;">
                <div class="pulse" style="color:#38bdf8; font-weight:600;">⏳ Executing Google Native ADK Agent (LlmAgent) & Custom State-Machine Agent (LangGraph) concurrently on Vertex AI...</div>
            </div>
        `;

        const runBtn = document.getElementById('run-comparison-inline-btn');
        const promptInput = document.getElementById('comparison-prompt-input');
        if (runBtn && promptInput) {
            runBtn.addEventListener('click', () => {
                this.renderComparisonView(promptInput.value.trim());
            });
        }

        this.appendTrace('COMPARISON_START', `Running side-by-side comparison: Google ADK Agent vs Custom Framework Agent on Vertex AI...`, 'thought');

        try {
            const res = await fetch('/api/comparison/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: this.customerId,
                    prompt: defaultPrompt,
                }),
            });
            const data = await res.json();
            const comp = data.comparison || {};
            const adk = comp.google_adk_agent_result || {};
            const cust = comp.custom_non_adk_agent_result || {};
            const matrix = comp.architectural_trade_off_matrix || [];

            const adkMetrics = adk.metrics || {};
            const custMetrics = cust.metrics || {};

            const matrixHtml = matrix.map(row => `
                <div style="background:rgba(15,23,42,0.65); border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:0.65rem; margin-bottom:0.5rem;">
                    <div style="font-weight:700; color:#f8fafc; font-size:0.76rem; margin-bottom:0.3rem;">${row.dimension}</div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; font-size:0.71rem; margin-bottom:0.35rem;">
                        <div style="background:rgba(59,130,246,0.12); padding:0.45rem; border-radius:4px; border-left:3px solid #3b82f6;">
                            <strong style="color:#60a5fa;">Google ADK Agent:</strong><br>${row.google_adk_agent}
                        </div>
                        <div style="background:rgba(168,85,247,0.12); padding:0.45rem; border-radius:4px; border-left:3px solid #a855f7;">
                            <strong style="color:#c084fc;">Custom Framework Agent:</strong><br>${row.custom_non_adk_agent}
                        </div>
                    </div>
                    <div style="font-size:0.71rem; color:#fde047;"><strong>Trade-Off Verdict:</strong> ${row.trade_off_verdict}</div>
                </div>
            `).join('');

            const resultsContainer = document.getElementById('comparison-results-body');
            if (resultsContainer) {
                resultsContainer.style.textAlign = 'left';
                resultsContainer.style.padding = '0';
                resultsContainer.innerHTML = `
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.65rem; margin-bottom:0.85rem;">
                        <div style="background:rgba(30,41,59,0.9); border:1px solid #3b82f6; border-radius:8px; padding:0.75rem;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.45rem;">
                                <span style="font-weight:700; color:#60a5fa; font-size:0.78rem;">🤖 Google Native ADK Agent</span>
                                <span class="badge-status success" style="font-size:0.65rem;">${adkMetrics.total_latency_ms || 0} ms</span>
                            </div>
                            <div style="font-size:0.68rem; color:#94a3b8; margin-bottom:0.5rem;">
                                • Memory Retrieval: <strong>${adkMetrics.memory_bank_retrieval_ms || 0} ms</strong> (${adkMetrics.memory_vectors_injected || 4} vectors)<br>
                                • Knowledge Catalog: <strong>${adkMetrics.knowledge_catalog_lookup_ms || 0} ms</strong> (${adkMetrics.policies_matched || 3} policies)<br>
                                • Tokens: <strong>${adkMetrics.prompt_tokens || 0} prompt / ${adkMetrics.completion_tokens || 0} completion</strong><br>
                                • Code Boilerplate: <strong>${adkMetrics.integration_code_lines_loc || 38} LOC</strong>
                            </div>
                            <div style="background:#0f172a; padding:0.55rem; border-radius:6px; font-size:0.72rem; color:#e2e8f0; max-height:180px; overflow-y:auto; white-space:pre-wrap;">${adk.response_text || ''}</div>
                        </div>

                        <div style="background:rgba(30,41,59,0.9); border:1px solid #a855f7; border-radius:8px; padding:0.75rem;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.45rem;">
                                <span style="font-weight:700; color:#c084fc; font-size:0.78rem;">⚙️ Custom Framework Agent (LangGraph)</span>
                                <span class="badge-status warning" style="font-size:0.65rem;">${custMetrics.total_latency_ms || 0} ms</span>
                            </div>
                            <div style="font-size:0.68rem; color:#94a3b8; margin-bottom:0.5rem;">
                                • Standalone Memory API: <strong>${custMetrics.memory_bank_retrieval_ms || 0} ms</strong> (${custMetrics.memory_vectors_injected || 4} vectors)<br>
                                • Embedding Vector Lookup: <strong>${custMetrics.knowledge_catalog_lookup_ms || 0} ms</strong> (${custMetrics.policies_matched || 3} policies)<br>
                                • Tokens: <strong>${custMetrics.prompt_tokens || 0} prompt / ${custMetrics.completion_tokens || 0} completion</strong><br>
                                • Code Boilerplate: <strong>${custMetrics.integration_code_lines_loc || 142} LOC</strong>
                            </div>
                            <div style="background:#0f172a; padding:0.55rem; border-radius:6px; font-size:0.72rem; color:#e2e8f0; max-height:180px; overflow-y:auto; white-space:pre-wrap;">${cust.response_text || ''}</div>
                        </div>
                    </div>

                    <div style="margin-top:0.75rem;">
                        <div style="font-weight:700; color:#38bdf8; font-size:0.8rem; margin-bottom:0.5rem;">📊 6-Dimension Fair Architectural Trade-Off Matrix</div>
                        ${matrixHtml}
                    </div>
                `;
            }
            this.appendTrace('COMPARISON_COMPLETE', `Comparison completed: ADK (${adkMetrics.total_latency_ms}ms, 38 LOC) vs Custom (${custMetrics.total_latency_ms}ms, 142 LOC).`, 'synthesis');
        } catch (err) {
            console.error('Comparison failed:', err);
            const resultsContainer = document.getElementById('comparison-results-body');
            if (resultsContainer) {
                resultsContainer.innerHTML = `<div style="color:#f87171;">Error executing comparison: ${err.message}</div>`;
            }
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
