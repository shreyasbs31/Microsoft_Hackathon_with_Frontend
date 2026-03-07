/**
 * Honeypot Scam Detection — Frontend App
 * Chat, session management, intel dashboard, scammer scripts panel.
 */

(() => {
    'use strict';

    // ================================================================
    // Scammer Scripts Data
    // 5 fraud types × 10 pre-written turns each
    // ================================================================
    const SCAMMER_SCRIPTS = [
        {
            id: 'bank_fraud',
            icon: '🏦',
            label: 'Bank Fraud',
            turns: [
                "URGENT: Your SBI account has been compromised. Your account will be blocked in 2 hours. Share your account number and OTP immediately to verify your identity.",
                "I'm sorry we can't provide a public line, but you can reach us securely at +91-9876543210 – please send your account number and OTP immediately to avoid the block.",
                "The issue is being processed by our Mumbai Main Branch – to stop the block, please send your account number 1234567890123456 and the OTP you just received right away.",
                "Your case reference number is REF-2023-98765; please send your account number 1234567890123456 and the OTP you just received right away to avoid the block.",
                "Kindly email your verification documents to verification@fakebank.com along with your account number 1234567890123456 and the OTP you just received to complete the process immediately.",
                "Yes, verification@fakebank.com is correct, and for faster processing you can also send the details to our secure UPI ID scammer.fraud@fakebank; please forward your account number 1234567890123456 and the OTP right away.",
                "Please transfer the funds to account number 1234567890123456 right away and reply with the OTP you receive to confirm the transaction.",
                "It's a regular account with FakeBank's Mumbai Main Branch; please forward the OTP you just received to verification@fakebank.com right away so we can lift the block.",
                "You can call me directly at +91-9876543210; the case reference for your account block is REF-2023-4567. Please forward the OTP you receive to verification@fakebank.com immediately to lift the block.",
                "Please send any required documents to verification@fakebank.com and check the status of your block at https://fakebank.com/secure/status?ref=REF-2023-4567; kindly forward the OTP you just received right away to lift the block."
            ]
        },
        {
            id: 'kyc_fraud',
            icon: '📋',
            label: 'KYC Fraud',
            turns: [
                "URGENT: Your Aadhaar eKYC has expired. Your bank account linked to Aadhaar will be BLOCKED in 24 hours. Call us immediately at +91-8876543210 to re-verify.",
                "I am Officer Priya from the UIDAI helpdesk. Your account 556677889900 shows incomplete KYC. Please share your 12-digit Aadhaar number and the OTP you just received for re-verification.",
                "To avoid the freeze, you need to pay a KYC updating fee of Rs.500 via UPI. Use UPI ID: uidai.verify@ybl. Case reference: KYC-UIDAI-2024-44521.",
                "I'm sending you the official KYC update portal now. Please fill in your details at http://uidai-kyc-portal.in/verify?case=44521 to complete the process.",
                "Your KYC update is stuck due to a PAN mismatch. I need your PAN card number and bank account 556677889900 details to manually sync the records.",
                "Final step for KYC activation: email your Aadhaar front and back to kyc@uidai-verify.in and include your bank account number and IFSC code SBIN0001234 in the email.",
                "I will send you a verification call from +91-8876543210 in 2 minutes. In the meantime, send the OTP you receive to kyc@uidai-verify.in for our records.",
                "Your KYC update is almost complete. To confirm, send a WhatsApp message with your full name and account number 556677889900 to +91-8876543210.",
                "Case ID: KYC-UIDAI-44521 is now escalated. To avoid a Rs.10,000 penalty, transfer Rs.500 to HDFC account 887766554433 with IFSC HDFC0002345 by tonight.",
                "The block will be lifted once you click this link: http://kyc-update.uidai-india.in/complete?id=KYC44521 and enter your bank account number 556677889900 and OTP for final verification."
            ]
        },
        {
            id: 'lottery_fraud',
            icon: '🎰',
            label: 'Lottery Fraud',
            turns: [
                "CONGRATULATIONS! You have won Rs 50,00,000 in the National Digital India Lottery 2024! Ticket number LT-2024-77654. Call us now at +91-9988776655 to claim your prize.",
                "I am Mr. Vikram from the National Lottery Board. To transfer your prize of Rs 50 lakhs, I need your full bank account number and the name as on your account.",
                "There is a government tax clearance fee of Rs 5000 to release your prize. Pay to UPI ID: prizeclaim.india@paytm. Winner reference: WIN-NLBI-2024-77654.",
                "Your tax clearance payment has been received. Now email your bank details including account number 334455667788 confirmation to prizes@national-lottery.in.",
                "We need one more document. Please send your cancelled cheque and PAN card to claims@national-lottery.in. Prize release will happen within 2 hours of verification.",
                "Congratulations again! Your prize transfer will go to account 334455667788. Please confirm the IFSC code of your bank so we can process the NEFT transfer.",
                "Banker Ref: NLBI-2024-PRIZE-77654. Please visit http://national-lottery-claim.in/release?ref=77654 to enter your OTP and authorize the prize transfer.",
                "One small issue — the transfer bounced due to a name mismatch. Send Rs 1000 to lotteryboard@ybl via UPI for name-correction processing fee. Ref: WIN-77654.",
                "Updated banker email is transfer@nlbi-prizefund.in. Please email your OTP and account number 334455667788 one more time for re-verification. Almost done!",
                "FINAL STEP: Transfer Rs 2500 to UPI ID finaltax@paytm with note WIN-77654 to release your Rs 50 lakh prize. Check release status: http://prize-status.national-lottery.in?ref=77654"
            ]
        },
        {
            id: 'upi_refund',
            icon: '📱',
            label: 'UPI Refund Scam',
            turns: [
                "Hello sir/ma'am, I am calling from Amazon Customer Support. We noticed an unauthorized transaction of Rs 4,999 from your account. I will process your immediate refund.",
                "To initiate the refund, please share your registered UPI ID or phone number. Refund Order ID: REF-AMZ-2024-887754. I will credit the money in 2 minutes.",
                "I have initiated the refund to your UPI. Please accept the payment request I am sending to +91-7788990011. It will arrive as a collect request — just approve it.",
                "The refund of Rs 4999 is on its way. For our records, please confirm your account number 778899001122 linked to this UPI. Our support email: refund@amazon-support.in.",
                "Your UPI refund failed due to a technical error. I am resending — please scan this QR code or visit http://amzn-refund-portal.co/process?id=887754 to receive your money.",
                "I see your account is KYC-blocked which is why the refund is failing. Send Rs 99 to amazon.refund@okaxis as a KYC activation fee and your Rs 4999 will be released.",
                "Transaction ID: TXN-AMZ-887754. Your Rs 4999 is held at escrow. Email your UPI PIN confirmation to refund@amazon-support.in to release the funds to you.",
                "One more step: Accept the Google Pay request I sent to +91-7788990011 for Rs 1 verification. Once done, your Rs 4999 refund for order ORD-2024-887754 releases instantly.",
                "Thank you for the verification. Your full refund has been credited to UPI ID linked to account 778899001122. Login and check — it should reflect in 5 minutes.",
                "If you don't see the refund, visit http://amazon-escalation.in/refund?ordid=887754 and enter your Amazon credentials and account number 778899001122 to manually trigger the payout."
            ]
        },
        {
            id: 'tax_fraud',
            icon: '📝',
            label: 'Income Tax Fraud',
            turns: [
                "URGENT LEGAL NOTICE: This is the Income Tax Department, India. A tax evasion FIR number ITD-2024-CR-55321 has been registered against your PAN ABCPX1234Y. Call immediately: +91-9911223344.",
                "I am ITO Senior Inspector Rajesh Sharma, badge ID ITO-CBI-7823. Your PAN shows Rs 12 lakh undisclosed income in FY 2022-23. Please cooperate to avoid immediate arrest.",
                "To settle this case outside court, you need to pay a compliance fee of Rs 25,000 to government recovery account 445566778899. IFSC: SBIN0004567. Case Ref: ITD-FIR-55321.",
                "Make the payment via UPI ID: itax.recovery@hdfcbank or bank transfer to 445566778899. Email payment proof to compliance.officer@incometax-gov.in immediately.",
                "I am escalating your case to the CBI tomorrow unless payment is confirmed. Email your payment receipt and account details to ito.sharma@incometax-portal.in by 5 PM today.",
                "Your case file is live at http://incometax-dept.in/case/ITD-55321 — open this link and upload your bank statement and payment confirmation to avoid an arrest warrant.",
                "Time is running out. Wire Rs 25,000 to account 445566778899, IFSC SBIN0004567, or via UPI itax.recovery@hdfcbank. Reply here with your UTR transaction number.",
                "Final warning before the FIR is formally registered. Pay to account 445566778899 or UPI itax.recovery@hdfcbank before 6 PM tonight to avoid arrest tomorrow morning.",
                "Payment received but showing as incomplete in our system. Please send the OTP you received to compliance.officer@incometax-gov.in and confirm account number 445566778899.",
                "Case ITD-FIR-55321 will be filed tomorrow unless you act NOW: Transfer Rs 5000 additional compliance fee to UPI itax.recovery@hdfcbank and send confirmation to +91-9911223344."
            ]
        }
    ];

    // ================================================================
    // State
    // ================================================================
    let sessionId = null;
    let conversationHistory = [];
    let isSending = false;
    let sessionComplete = false;

    let scriptsOpen = false;
    let activeScriptIdx = 0;
    let scriptTurnIndex = 0;   // next turn to load
    let scriptSentTurns = [];  // which turns have been sent (per script)

    // ================================================================
    // DOM refs
    // ================================================================
    const $ = (sel) => document.querySelector(sel);
    const chatMessages = $('#chat-messages');
    const chatInput = $('#chat-input');
    const chatForm = $('#chat-form');
    const btnSend = $('#btn-send');
    const btnNewSession = $('#btn-new-session');
    const typingIndicator = $('#typing-indicator');
    const sessionIdValue = $('#session-id-value');
    const turnValue = $('#turn-value');
    const turnMax = $('#turn-max');
    const turnProgressFill = $('#turn-progress-fill');
    const chatStatus = $('#chat-status');
    const statusBadge = $('#status-badge');
    const scamTypeEl = $('#scam-type');
    const confidenceLevelEl = $('#confidence-level');
    const agentNotes = $('#agent-notes');
    const resultsTrigger = $('#results-trigger');
    const btnViewResults = $('#btn-view-results');
    const resultsModal = $('#results-modal');
    const resultsBody = $('#results-body');
    const modalClose = $('#modal-close');
    const charCount = $('#char-count');
    const resultsTeaser = $('#results-teaser');
    const btnScriptsToggle = $('#btn-scripts-toggle');
    const scriptsDrawer = $('#scripts-drawer');
    const scriptsTabs = $('#scripts-tabs');
    const scriptsMessages = $('#scripts-messages');
    const btnNextTurn = $('#btn-next-turn');
    const scriptCurrentTurn = $('#script-current-turn');
    const scriptTotalTurns = $('#script-total-turns');

    // ================================================================
    // Helpers
    // ================================================================
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    }
    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }
    function scrollToBottom() {
        requestAnimationFrame(() => { chatMessages.scrollTop = chatMessages.scrollHeight; });
    }
    function autoResize() {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    }

    // ================================================================
    // Session Management
    // ================================================================
    function initSession() {
        sessionId = generateUUID();
        conversationHistory = [];
        isSending = false;
        sessionComplete = false;
        scriptTurnIndex = 0;
        scriptSentTurns = SCAMMER_SCRIPTS.map(() => new Set());

        sessionIdValue.textContent = sessionId.slice(0, 8) + '…';
        turnValue.textContent = '0';
        turnMax.textContent = '10';
        turnProgressFill.style.width = '0%';
        chatStatus.textContent = 'Online • Ready to engage';
        statusBadge.textContent = 'NEUTRAL';
        statusBadge.className = 'status-badge';
        scamTypeEl.textContent = '—';
        confidenceLevelEl.textContent = '—';
        agentNotes.innerHTML = '<span class="empty-value">No notes yet</span>';
        resultsTrigger.style.display = 'none';
        resultsTeaser.style.display = 'none';

        const fields = [
            'phoneNumbers', 'bankAccounts', 'upiIds', 'urls', 'emailAddresses',
            'ifscCodes', 'caseIds', 'policyNumbers', 'orderNumbers', 'suspiciousKeywords'
        ];
        fields.forEach(f => {
            const c = $(`#count-${f}`);
            const v = $(`#values-${f}`);
            const fe = v?.closest('.intel-field');
            if (c) { c.textContent = '0'; c.classList.remove('active'); }
            if (v) v.innerHTML = '<span class="empty-value">None extracted</span>';
            if (fe) fe.classList.remove('has-data');
        });

        renderWelcome();
        updateScriptPanel();
        chatInput.disabled = false;
        chatInput.placeholder = 'Type your scammer message, or use the Scripts panel on the left →';
        btnSend.disabled = false;
        chatInput.focus();
    }

    function renderWelcome() {
        chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🕵️</div>
            <h3>Welcome to the Honeypot</h3>
            <p>You are role-playing as a <strong>scammer</strong>. Send scam messages and watch the AI agent extract your intelligence in real time.</p>
            <div class="welcome-cta-strip">
                <div class="cta-item">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/></svg>
                    <span>Use the <strong>Scripts</strong> button above for pre-written 10-turn scam conversations</span>
                </div>
                <div class="cta-item cta-highlight">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                    <span>After <strong>10 turns</strong>, unlock the full intelligence report!</span>
                </div>
            </div>
            <div class="welcome-quick-starts">
                <span class="example-label">Quick-start examples:</span>
                <button class="example-btn" data-message="URGENT: Your SBI account has been compromised. Your account will be blocked in 2 hours. Share your account number and OTP immediately to verify your identity.">🏦 Bank Fraud</button>
                <button class="example-btn" data-message="URGENT: Your Aadhaar eKYC has expired. Your bank account will be BLOCKED in 24 hours. Call us immediately at +91-8876543210 to re-verify.">📋 KYC Fraud</button>
                <button class="example-btn" data-message="CONGRATULATIONS! You have won Rs 50,00,000 in the National Digital India Lottery 2024! Ticket number LT-2024-77654. Call now at +91-9988776655 to claim.">🎰 Lottery Fraud</button>
                <button class="example-btn" data-message="URGENT LEGAL NOTICE: Income Tax Department. A tax evasion FIR ITD-2024-CR-55321 has been registered against your PAN. Call immediately: +91-9911223344.">📝 Tax Fraud</button>
            </div>
        </div>`;
        bindExampleButtons();
    }

    // ================================================================
    // Scripts Panel
    // ================================================================
    function buildScriptsPanel() {
        // Build tabs
        scriptsTabs.innerHTML = SCAMMER_SCRIPTS.map((s, i) =>
            `<button class="scripts-tab ${i === 0 ? 'active' : ''}" data-idx="${i}">
                <span class="scripts-tab-icon">${s.icon}</span>
                <span class="scripts-tab-label">${s.label}</span>
                <span class="scripts-tab-count">${s.turns.length}</span>
            </button>`
        ).join('');

        scriptsTabs.querySelectorAll('.scripts-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                activeScriptIdx = parseInt(btn.dataset.idx);
                scriptsTabs.querySelectorAll('.scripts-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderScriptMessages();
            });
        });

        renderScriptMessages();
    }

    function renderScriptMessages() {
        const script = SCAMMER_SCRIPTS[activeScriptIdx];
        const sentSet = scriptSentTurns[activeScriptIdx] || new Set();

        scriptsMessages.innerHTML = script.turns.map((text, i) => {
            const isSent = sentSet.has(i);
            const isNext = (i === getNextTurnIdx());
            return `
            <div class="script-turn-item ${isSent ? 'sent' : ''} ${isNext && !isSent ? 'active' : ''}"
                 data-turn="${i}" data-script="${activeScriptIdx}">
                <div>
                    <div class="turn-num">${i + 1}</div>
                    <div class="turn-sent-badge">✓ sent</div>
                </div>
                <div class="turn-text">${escapeHtml(text)}</div>
            </div>`;
        }).join('');

        scriptsMessages.querySelectorAll('.script-turn-item:not(.sent)').forEach(item => {
            item.addEventListener('click', () => {
                const turnIdx = parseInt(item.dataset.turn);
                const scriptIdx = parseInt(item.dataset.script);
                loadTurnIntoInput(scriptIdx, turnIdx);
            });
        });

        updateScriptPanel();
    }

    function getNextTurnIdx() {
        const sentSet = scriptSentTurns[activeScriptIdx] || new Set();
        const script = SCAMMER_SCRIPTS[activeScriptIdx];
        for (let i = 0; i < script.turns.length; i++) {
            if (!sentSet.has(i)) return i;
        }
        return -1; // all sent
    }

    function updateScriptPanel() {
        const sentSet = scriptSentTurns[activeScriptIdx] || new Set();
        const script = SCAMMER_SCRIPTS[activeScriptIdx];
        const nextIdx = getNextTurnIdx();
        const sentCount = sentSet.size;

        scriptCurrentTurn.textContent = sentCount;
        scriptTotalTurns.textContent = script.turns.length;
        btnNextTurn.disabled = nextIdx === -1 || isSending || sessionComplete;
    }

    function loadTurnIntoInput(scriptIdx, turnIdx) {
        const script = SCAMMER_SCRIPTS[scriptIdx];
        const text = script.turns[turnIdx];
        chatInput.value = text;
        chatInput.focus();
        charCount.textContent = `${text.length} / 2000`;
        autoResize();

        // Highlight active turn
        scriptsMessages.querySelectorAll('.script-turn-item').forEach(el => {
            el.classList.remove('active');
            if (parseInt(el.dataset.turn) === turnIdx) el.classList.add('active');
        });
    }

    function markTurnSent(turnIdx) {
        if (!scriptSentTurns[activeScriptIdx]) scriptSentTurns[activeScriptIdx] = new Set();
        scriptSentTurns[activeScriptIdx].add(turnIdx);
        renderScriptMessages();
    }

    function toggleScriptsDrawer() {
        scriptsOpen = !scriptsOpen;
        scriptsDrawer.classList.toggle('open', scriptsOpen);
        btnScriptsToggle.classList.toggle('active', scriptsOpen);
        if (scriptsOpen) renderScriptMessages();
    }

    // ================================================================
    // Chat
    // ================================================================
    function addMessage(role, text) {
        const welcome = chatMessages.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = `
            <span class="message-sender">${role === 'scammer' ? 'You (Scammer)' : '🤖 AI Honeypot'}</span>
            <div class="message-bubble">${escapeHtml(text)}</div>
            <span class="message-time">${formatTime(new Date())}</span>`;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function showTyping() { typingIndicator.classList.add('active'); scrollToBottom(); }
    function hideTyping() { typingIndicator.classList.remove('active'); }

    async function sendMessage(text) {
        if (!text.trim() || isSending || sessionComplete) return;

        // Detect if this text matches a script turn
        let matchedScriptIdx = null;
        let matchedTurnIdx = null;
        for (let si = 0; si < SCAMMER_SCRIPTS.length; si++) {
            const ti = SCAMMER_SCRIPTS[si].turns.indexOf(text.trim());
            if (ti !== -1) { matchedScriptIdx = si; matchedTurnIdx = ti; break; }
        }

        isSending = true;
        btnSend.disabled = true;
        chatInput.disabled = true;
        btnNextTurn.disabled = true;
        chatStatus.textContent = 'Processing message…';

        addMessage('scammer', text.trim());
        conversationHistory.push({ sender: 'scammer', text: text.trim() });
        chatInput.value = '';
        charCount.textContent = '0 / 2000';
        chatInput.style.height = 'auto';

        showTyping();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sessionId,
                    message: text.trim(),
                    conversationHistory,
                    language: 'English',
                }),
            });
            const data = await res.json();
            hideTyping();

            if (data.status === 'success') {
                if (data.sessionId) sessionId = data.sessionId;
                const reply = data.reply || 'I see, let me think about this...';
                addMessage('agent', reply);
                conversationHistory.push({ sender: 'user', text: reply });
                if (data.session) updateDashboard(data.session);

                // Mark script turn as sent
                if (matchedScriptIdx !== null) {
                    const prevActive = activeScriptIdx;
                    activeScriptIdx = matchedScriptIdx;
                    markTurnSent(matchedTurnIdx);
                    activeScriptIdx = prevActive;
                    if (scriptsOpen) renderScriptMessages();
                }
            } else {
                addMessage('agent', 'Something went wrong on my end…');
            }
        } catch (err) {
            hideTyping();
            addMessage('agent', 'Connection error. Please try again.');
        } finally {
            isSending = false;
            btnSend.disabled = false;
            chatInput.disabled = false;
            chatInput.focus();
            updateScriptPanel();
            if (!sessionComplete) chatStatus.textContent = 'Online • Ready to engage';
        }
    }

    // ================================================================
    // Dashboard
    // ================================================================
    function updateDashboard(session) {
        const turn = session.turnCount || 0;
        const max = session.maxTurns || 10;
        turnValue.textContent = turn;
        turnMax.textContent = max;
        turnProgressFill.style.width = `${Math.min((turn / max) * 100, 100)}%`;

        const status = session.status || 'NEUTRAL';
        statusBadge.textContent = status;
        statusBadge.className = 'status-badge';
        if (status === 'HONEYPOT') statusBadge.classList.add('honeypot');
        else if (status === 'LEGIT') statusBadge.classList.add('legit');

        scamTypeEl.textContent = session.scamType || '—';
        confidenceLevelEl.textContent = session.confidenceLevel
            ? `${(parseFloat(session.confidenceLevel) * 100).toFixed(0)}%` : '—';

        if (session.intelligence) {
            updateIntelField('phoneNumbers', session.intelligence.phoneNumbers);
            updateIntelField('bankAccounts', session.intelligence.bankAccounts);
            updateIntelField('upiIds', session.intelligence.upiIds);
            updateIntelField('urls', session.intelligence.urls);
            updateIntelField('emailAddresses', session.intelligence.emailAddresses);
            updateIntelField('ifscCodes', session.intelligence.ifscCodes);
            updateIntelField('caseIds', session.intelligence.caseIds);
            updateIntelField('policyNumbers', session.intelligence.policyNumbers);
            updateIntelField('orderNumbers', session.intelligence.orderNumbers);
            updateIntelField('suspiciousKeywords', session.intelligence.suspiciousKeywords, true);
        }

        if (session.agentNotes) agentNotes.textContent = session.agentNotes;

        // Show teaser at turn 5
        if (turn >= 5 && turn < max) {
            resultsTeaser.style.display = 'flex';
        }

        // Session complete
        if (turn >= max) {
            sessionComplete = true;
            chatStatus.textContent = '✅ Session complete — view your full report!';
            resultsTrigger.style.display = 'block';
            resultsTeaser.style.display = 'none';
            chatInput.disabled = true;
            chatInput.placeholder = 'Session complete — click "View Full Intelligence Report" →';
            btnSend.disabled = true;
        }
    }

    function updateIntelField(fieldName, values, isKeyword = false) {
        const countEl = $(`#count-${fieldName}`);
        const valEl = $(`#values-${fieldName}`);
        const fieldEl = valEl?.closest('.intel-field');
        if (!countEl || !valEl) return;

        const list = Array.isArray(values) ? values : [];
        countEl.textContent = list.length;
        if (list.length > 0) {
            countEl.classList.add('active');
            if (fieldEl) fieldEl.classList.add('has-data');
            valEl.innerHTML = list.map(v =>
                `<span class="value-chip ${isKeyword ? 'keyword' : ''}">${escapeHtml(v)}</span>`
            ).join('');
        } else {
            countEl.classList.remove('active');
            if (fieldEl) fieldEl.classList.remove('has-data');
            valEl.innerHTML = `<span class="empty-value">${isKeyword ? 'None detected' : 'None extracted'}</span>`;
        }
    }

    // ================================================================
    // Results Modal
    // ================================================================
    async function viewResults() {
        resultsModal.style.display = 'flex';
        resultsBody.innerHTML = '<div class="loading-spinner">Loading final intelligence report…</div>';
        try {
            const res = await fetch(`/api/session/${sessionId}/results`);
            const data = await res.json();
            if (data.status === 'success' && data.results) renderResults(data.results);
            else if (data.status === 'pending') resultsBody.innerHTML = `<div class="loading-spinner">${data.message}</div>`;
            else resultsBody.innerHTML = '<div class="loading-spinner">Could not load results.</div>';
        } catch {
            resultsBody.innerHTML = '<div class="loading-spinner">Failed to load results.</div>';
        }
    }

    function renderResults(r) {
        const intel = r.extractedIntelligence || {};
        const chips = (arr, cls = '') => {
            if (!arr || arr.length === 0) return '<span class="empty-value">None</span>';
            return `<div class="result-intel-list">${arr.map(v => `<span class="value-chip ${cls}">${escapeHtml(v)}</span>`).join('')}</div>`;
        };
        resultsBody.innerHTML = `
            <div class="results-section">
                <div class="results-section-title">📊 Session Overview</div>
                <div class="results-grid">
                    <div class="result-item"><div class="result-item-label">Session ID</div><div class="result-item-value highlight">${escapeHtml(r.sessionId || '—')}</div></div>
                    <div class="result-item"><div class="result-item-label">Scam Detected</div><div class="result-item-value" style="color:${r.scamDetected ? 'var(--accent-red)' : 'var(--accent-emerald)'}">${r.scamDetected ? '🔴 YES' : '🟢 NO'}</div></div>
                    <div class="result-item"><div class="result-item-label">Scam Type</div><div class="result-item-value">${escapeHtml(r.scamType || '—')}</div></div>
                    <div class="result-item"><div class="result-item-label">Confidence</div><div class="result-item-value highlight">${r.confidenceLevel != null ? (r.confidenceLevel * 100).toFixed(0) + '%' : '—'}</div></div>
                    <div class="result-item"><div class="result-item-label">Messages Exchanged</div><div class="result-item-value highlight">${r.totalMessagesExchanged || 0}</div></div>
                    <div class="result-item"><div class="result-item-label">Engagement Duration</div><div class="result-item-value highlight">${r.engagementDurationSeconds != null ? r.engagementDurationSeconds.toFixed(1) + 's' : '—'}</div></div>
                </div>
            </div>
            <div class="results-section">
                <div class="results-section-title">📡 Extracted Intelligence</div>
                <div class="results-grid">
                    <div class="result-item"><div class="result-item-label">📱 Phone Numbers</div>${chips(intel.phoneNumbers)}</div>
                    <div class="result-item"><div class="result-item-label">🏦 Bank Accounts</div>${chips(intel.bankAccounts)}</div>
                    <div class="result-item"><div class="result-item-label">💳 UPI IDs</div>${chips(intel.upiIds)}</div>
                    <div class="result-item"><div class="result-item-label">📧 Emails</div>${chips(intel.emailAddresses)}</div>
                    <div class="result-item"><div class="result-item-label">🔗 URLs</div>${chips(intel.phishingLinks || intel.urls)}</div>
                    <div class="result-item"><div class="result-item-label">🏛️ IFSC Codes</div>${chips(intel.ifscCodes)}</div>
                    <div class="result-item"><div class="result-item-label">🔖 Case IDs</div>${chips(intel.caseIds)}</div>
                    <div class="result-item"><div class="result-item-label">⚠️ Keywords</div>${chips(intel.suspiciousKeywords, 'keyword')}</div>
                </div>
            </div>
            <div class="results-section">
                <div class="results-section-title">📝 Agent Notes</div>
                <div class="result-notes">${escapeHtml(r.agentNotes || 'No notes.')}</div>
            </div>`;
    }

    // ================================================================
    // Event Listeners
    // ================================================================
    chatForm.addEventListener('submit', e => { e.preventDefault(); sendMessage(chatInput.value); });
    chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(chatInput.value); }
    });
    chatInput.addEventListener('input', () => {
        charCount.textContent = `${chatInput.value.length} / 2000`;
        autoResize();
    });
    btnNewSession.addEventListener('click', () => { if (!isSending) initSession(); });
    btnViewResults.addEventListener('click', viewResults);
    modalClose.addEventListener('click', () => { resultsModal.style.display = 'none'; });
    resultsModal.addEventListener('click', e => { if (e.target === resultsModal) resultsModal.style.display = 'none'; });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && resultsModal.style.display === 'flex') resultsModal.style.display = 'none';
    });
    btnScriptsToggle.addEventListener('click', toggleScriptsDrawer);
    btnNextTurn.addEventListener('click', () => {
        const nextIdx = getNextTurnIdx();
        if (nextIdx !== -1) loadTurnIntoInput(activeScriptIdx, nextIdx);
    });
    $('#session-id-display')?.addEventListener('click', () => {
        if (!sessionId) return;
        navigator.clipboard.writeText(sessionId).catch(() => { });
        const orig = sessionIdValue.textContent;
        sessionIdValue.textContent = 'Copied!';
        setTimeout(() => { sessionIdValue.textContent = orig; }, 1200);
    });

    function bindExampleButtons() {
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', () => { if (btn.dataset.message) sendMessage(btn.dataset.message); });
        });
    }

    // ================================================================
    // Bootstrap
    // ================================================================
    buildScriptsPanel();
    initSession();
})();
