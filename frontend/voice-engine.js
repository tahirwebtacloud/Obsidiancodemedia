// User Profile JavaScript Module (formerly Voice Engine)
// Handles LinkedIn ZIP upload, persona display, and voice context search

document.addEventListener('DOMContentLoaded', () => {
    // User Profile Elements
    const linkedinUploadZone = document.getElementById('linkedin-upload-zone');
    const linkedinFileInput = document.getElementById('linkedin-file-input');
    const voiceUploadProgress = document.getElementById('voice-upload-progress');
    const voiceProgressBar = document.getElementById('voice-progress-bar');
    const voiceUploadSection = document.getElementById('voice-upload-section');
    const voiceImportStatus = document.getElementById('voice-import-status');
    const voiceStatusMessage = document.getElementById('voice-status-message');
    const voiceProgressLabel = document.getElementById('voice-progress-label');
    const linkedinFileList = document.getElementById('linkedin-file-list');

    // LinkedIn Profile Scrape elements (use fresh lookups to survive lucide.createIcons() replacement)
    function getVoiceScrapeBtn() { return document.getElementById('voice-scrape-btn'); }
    function getVoiceLinkedinUrl() { return document.getElementById('voice-linkedin-url'); }

    let personaPollActive = false;
    let pendingReload = false;
    let lazyPollTimer = null;      // low-frequency background poll after fast poll gives up

    // ── Progress tracking (survives page refresh via sessionStorage) ──
    const _PROC_START_KEY = 'lp_proc_start';
    let _progressPct = 0;

    function _estimateProgress(crmCount, voiceCount) {
        // Initialize start time, backdating if counts suggest processing started earlier
        if (!sessionStorage.getItem(_PROC_START_KEY)) {
            const backdateMs = (crmCount * 2 + voiceCount) * 1000;
            sessionStorage.setItem(_PROC_START_KEY, String(Date.now() - backdateMs));
        }
        const elapsed = (Date.now() - Number(sessionStorage.getItem(_PROC_START_KEY))) / 1000;

        // Time curve: asymptotic to 92% (~8% at 1min, 34% at 5min, 56% at 10min, 78% at 20min)
        const timePct = 92 * (1 - Math.exp(-elapsed / 700));

        // Data curve: driven by real server counts
        const dataPct = Math.min(90, 5 + crmCount * 0.035 + voiceCount * 0.07);

        // Use whichever is higher, never go backwards, cap at 95%
        _progressPct = Math.min(95, Math.max(timePct, dataPct, _progressPct));
        return Math.round(_progressPct);
    }

    function _clearProgress() {
        sessionStorage.removeItem(_PROC_START_KEY);
        _progressPct = 0;
    }

    function emitLinkedInProcessingStatus(processingStatus, data = {}) {
        window.dispatchEvent(new CustomEvent('linkedin-processing-status', {
            detail: {
                processingStatus: processingStatus || null,
                crmContactsCount: Number(data.crm_contacts_count || 0),
                voiceChunksCount: Number(data.voice_chunks_count || 0),
                linkedinImported: data.linkedin_imported === true
            }
        }));
    }

    // Re-upload ZIP button — show upload section again
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#voice-reupload-btn')) return;
        if (voiceUploadSection) voiceUploadSection.style.display = 'block';
        if (voiceImportStatus)  voiceImportStatus.style.display = 'none';
        if (linkedinUploadZone) linkedinUploadZone.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    // LinkedIn Profile Scrape handler — document-level delegation (bulletproof against DOM replacement)
    document.addEventListener('click', async (e) => {
        const scrapeBtn = e.target.closest('#voice-scrape-btn');
        if (!scrapeBtn) return;

        const urlInput = getVoiceLinkedinUrl();
        const url = urlInput ? urlInput.value.trim() : '';
        if (!url || !url.includes('linkedin.com')) {
            showVoiceStatus('Enter a valid LinkedIn profile URL', 'error');
            return;
        }
        scrapeBtn.disabled = true;
        scrapeBtn.textContent = 'Scraping...';
        // Clear existing profile card to show full-screen scraping state
        const _slot = document.getElementById('voice-output-slot');
        if (_slot) {
            _slot.classList.remove('ve-has-profile-card');
            _slot.innerHTML = `<div class="ve-scrape-loader">
                <div class="ve-loader-ring"></div>
                <h3 class="ve-loader-title">Scraping LinkedIn Profile</h3>
                <p class="ve-loader-sub">Connecting to Apify and extracting profile data...</p>
                <div class="ve-loader-steps">
                    <div class="ve-step ve-step-active" id="ve-step-scrape"><span class="ve-step-dot"></span> Scraping profile via Apify</div>
                    <div class="ve-step" id="ve-step-analyze"><span class="ve-step-dot"></span> Analyzing with AI</div>
                    <div class="ve-step" id="ve-step-store"><span class="ve-step-dot"></span> Building voice profile</div>
                </div>
                <p class="ve-loader-time">This typically takes 30\u201390 seconds</p>
                <style>
                    .ve-scrape-loader{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:calc(100vh - 200px);padding:40px 24px;text-align:center;animation:ve-fadeIn 0.4s ease;}
                    @keyframes ve-fadeIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
                    .ve-loader-ring{width:64px;height:64px;border:3px solid rgba(249,199,79,0.12);border-top-color:var(--brand-primary);border-radius:50%;animation:ve-spin 0.9s linear infinite;margin-bottom:28px;}
                    @keyframes ve-spin{to{transform:rotate(360deg)}}
                    .ve-loader-title{color:rgba(255,255,255,0.92);font-size:22px;font-weight:700;margin:0 0 8px;letter-spacing:-0.01em;}
                    .ve-loader-sub{color:rgba(255,255,255,0.45);font-size:14px;margin:0 0 32px;max-width:380px;line-height:1.5;}
                    .ve-loader-steps{display:flex;flex-direction:column;gap:14px;text-align:left;margin-bottom:32px;}
                    .ve-step{display:flex;align-items:center;gap:10px;color:rgba(255,255,255,0.25);font-size:14px;font-weight:500;transition:color 0.4s;}
                    .ve-step-active{color:rgba(255,255,255,0.75);}
                    .ve-step-done{color:rgba(110,231,183,0.85);}
                    .ve-step-dot{width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,0.1);flex-shrink:0;transition:background 0.4s,box-shadow 0.4s;}
                    .ve-step-active .ve-step-dot{background:var(--brand-primary);box-shadow:0 0 8px rgba(249,199,79,0.4);animation:ve-pulse 1.5s ease-in-out infinite;}
                    .ve-step-done .ve-step-dot{background:rgba(110,231,183,0.85);box-shadow:0 0 6px rgba(110,231,183,0.3);}
                    @keyframes ve-pulse{0%,100%{opacity:1}50%{opacity:0.5}}
                    .ve-loader-time{color:rgba(255,255,255,0.22);font-size:12px;margin:0;}
                </style>
            </div>`;
        }
        // Animate step progression
        const _advanceStep = (currentId, nextId) => {
            const cur = document.getElementById(currentId);
            const nxt = document.getElementById(nextId);
            if (cur) { cur.classList.remove('ve-step-active'); cur.classList.add('ve-step-done'); }
            if (nxt) { nxt.classList.add('ve-step-active'); }
        };
        // Persist the URL to settings so it survives page refresh
        saveLinkedInUrl(url);
        // Use AbortController for 120s timeout
        const _ctrl = new AbortController();
        const _timeout = setTimeout(() => _ctrl.abort(), 120000);
        try {
            const res = await fetch('/api/voice/scrape-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' },
                body: JSON.stringify({ linkedin_url: url }),
                signal: _ctrl.signal
            });
            clearTimeout(_timeout);
            if (!res.ok) {
                let errMsg = `Server error (${res.status})`;
                try { const errData = await res.json(); errMsg = errData.error || errMsg; } catch(_) {}
                throw new Error(errMsg);
            }
            _advanceStep('ve-step-scrape', 've-step-analyze');
            const data = await res.json();
            _advanceStep('ve-step-analyze', 've-step-store');
            if (data.success) {
                showVoiceStatus('Profile scraped successfully!', 'success');
                addSystemLog('LinkedIn profile scraped via Apify', 'success');
                // Small delay for visual step completion, then render card
                await new Promise(r => setTimeout(r, 600));
                if (data.profile) {
                    renderProfileCard(data.profile);
                } else {
                    // Scrape succeeded but no profile data — reload to fetch
                    window.loadVoicePersona && await window.loadVoicePersona();
                }
            } else {
                throw new Error(data.error || 'Scrape failed');
            }
        } catch (err) {
            clearTimeout(_timeout);
            console.error('[VoiceEngine] Scrape error:', err);
            const isTimeout = err.name === 'AbortError';
            const msg = isTimeout ? 'Request timed out — please try again' : err.message;
            showVoiceStatus('Scrape failed: ' + msg, 'error');
            addSystemLog('Profile scrape failed: ' + msg, 'error');
            // Clear spinner and show error in output slot
            if (_slot) {
                _slot.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:calc(100vh - 200px);padding:40px 24px;text-align:center;">
                    <div style="width:56px;height:56px;border-radius:50%;background:rgba(239,68,68,0.1);display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(239,68,68,0.8)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                    </div>
                    <h3 style="color:rgba(255,255,255,0.85);font-size:18px;font-weight:600;margin:0 0 8px;">Scrape Failed</h3>
                    <p style="color:rgba(255,255,255,0.45);font-size:13px;margin:0 0 20px;max-width:360px;line-height:1.6;">${msg}</p>
                    <p style="color:rgba(255,255,255,0.25);font-size:12px;margin:0;">Try again or upload a LinkedIn ZIP export instead.</p>
                </div>`;
            }
        } finally {
            scrapeBtn.disabled = false;
            scrapeBtn.innerHTML = '<i data-lucide="scan" style="width: 14px; height: 14px;"></i> Scrape';
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    });

    // File upload handling
    if (linkedinUploadZone && linkedinFileInput) {
        linkedinUploadZone.addEventListener('click', () => linkedinFileInput.click());
        
        linkedinUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            linkedinUploadZone.style.borderColor = 'var(--brand-primary)';
            linkedinUploadZone.style.background = 'rgba(249,199,79,0.05)';
        });

        linkedinUploadZone.addEventListener('dragleave', () => {
            linkedinUploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
            linkedinUploadZone.style.background = 'transparent';
        });

        linkedinUploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            linkedinUploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
            linkedinUploadZone.style.background = 'transparent';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleLinkedInUpload(files);
            }
        });

        linkedinFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleLinkedInUpload(e.target.files);
            }
        });
    }

    // Handle LinkedIn ZIP upload (accepts FileList for multi-file)
    async function handleLinkedInUpload(files) {
        const fileArr = Array.from(files);
        // Validate all are .zip
        for (const f of fileArr) {
            if (!f.name.toLowerCase().endsWith('.zip')) {
                showVoiceStatus(`'${f.name}' is not a ZIP file. All files must be .zip`, 'error');
                return;
            }
        }

        // Show file list
        if (linkedinFileList) {
            linkedinFileList.style.display = 'block';
            linkedinFileList.innerHTML = fileArr.map((f, i) =>
                `<span style="display:inline-block;padding:3px 10px;margin:2px 4px;background:rgba(249,199,79,0.10);border-radius:6px;font-size:0.75rem;color:var(--brand-primary);">${f.name} <span style="color:var(--text-muted);">(${(f.size / 1024).toFixed(0)} KB)</span></span>`
            ).join('');
        }

        // Show progress
        voiceUploadProgress.style.display = 'block';
        voiceProgressBar.style.width = '0%';
        
        const formData = new FormData();
        fileArr.forEach((f, i) => formData.append(`file_${i}`, f));

        try {
            // Simulate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 10;
                if (progress <= 90) {
                    voiceProgressBar.style.width = progress + '%';
                }
            }, 500);

            const res = await fetch('/api/upload-linkedin', {
                method: 'POST',
                headers: {
                    'X-User-ID': window.appUserId || 'default'
                },
                body: formData
            });

            clearInterval(progressInterval);
            voiceProgressBar.style.width = '100%';

            const data = await res.json();

            if (data.success) {
                const fileLabel = fileArr.length > 1 ? `${fileArr.length} LinkedIn exports` : 'LinkedIn data';
                showVoiceStatus(`${fileLabel} uploaded successfully! Processing...`, 'success');
                addSystemLog(`${fileLabel} uploaded. Persona building in progress.`, 'info');
                if (linkedinFileList) linkedinFileList.style.display = 'none';
                pendingReload = true;
                sessionStorage.setItem(_PROC_START_KEY, String(Date.now()));
                if (window.setProcessingLock) {
                    window.setProcessingLock(true, { message: 'LinkedIn import running. Tabs are still available.' });
                }

                // Show long-processing notice in the main output panel
                const outputSlot = document.getElementById('voice-output-slot');
                if (outputSlot) {
                    outputSlot.innerHTML = `
                        <div style="padding:32px 24px;text-align:center;max-width:540px;margin:0 auto;">
                            <div style="font-size:40px;margin-bottom:16px;">⚙️</div>
                            <h3 style="color:var(--brand-primary);margin:0 0 12px;font-size:18px;font-weight:600;">
                                Your LinkedIn data is being processed
                            </h3>
                            <p style="color:rgba(255,255,255,0.65);font-size:14px;line-height:1.7;margin:0 0 16px;">
                                ${fileArr.length > 1 ? `Merging <strong style="color:rgba(255,255,255,0.9);">${fileArr.length} ZIP exports</strong> and deduplicating contacts. ` : ''}
                                For large networks (1,000+ contacts), this typically takes
                                <strong style="color:rgba(255,255,255,0.9);">45 minutes to 2 hours</strong>
                                to fully analyze every conversation and build your AI persona.
                            </p>
                            <div id="voice-diagnostics-panel" style="display:none;"></div>
                            <p style="color:rgba(255,255,255,0.45);font-size:13px;margin:0;">
                                Feel free to close this tab and come back later —
                                your data will be ready and waiting for you automatically.
                            </p>
                        </div>`;
                }

                // Hide upload section, show import status
                setTimeout(() => {
                    voiceUploadSection.style.display = 'none';
                    voiceImportStatus.style.display = 'block';
                }, 1000);

                // Poll persona status until backend background processing is done
                await waitForPersonaReady({ triggerReload: true });

                if (voiceUploadProgress) {
                    voiceUploadProgress.style.display = 'none';
                }
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (err) {
            console.error(err);
            voiceUploadProgress.style.display = 'none';
            showVoiceStatus('Upload failed: ' + err.message, 'error');
            addSystemLog('LinkedIn upload failed: ' + err.message, 'error');
            if (window.setProcessingLock) {
                window.setProcessingLock(false);
            }
            pendingReload = false;
        }
    }

    // Smart polling: fast phase (2 min) → slow phase (20 min) → lazy background poll
    async function waitForPersonaReady({ triggerReload = false } = {}) {
        if (personaPollActive) return false;
        personaPollActive = true;

        // Cancel any existing lazy poll — we are now fast-polling
        if (lazyPollTimer) { clearTimeout(lazyPollTimer); lazyPollTimer = null; }

        const FAST_ATTEMPTS = 60;   // 60 × 2s  = 2 min
        const SLOW_ATTEMPTS = 120;  // 120 × 10s = 20 min
        const TOTAL = FAST_ATTEMPTS + SLOW_ATTEMPTS;

        for (let attempt = 1; attempt <= TOTAL; attempt++) {
            const ready = await loadPersona({ suppressEmptyState: true, emitSuccessLog: false });
            if (ready) {
                showVoiceStatus('LinkedIn processing complete!', 'success');
                addSystemLog('User profile persona is ready.', 'success');
                personaPollActive = false;
                pendingReload = false;
                _clearProgress();
                if (window.setProcessingLock) window.setProcessingLock(false);
                if (voiceUploadProgress) voiceUploadProgress.style.display = 'none';
                // Force-render persona in the output panel
                await loadPersona({ suppressEmptyState: false, emitSuccessLog: true });
                return true;
            }

            // Progress bar is now driven by loadPersona() via _estimateProgress()
            if (voiceUploadProgress) voiceUploadProgress.style.display = 'block';

            // End of fast phase: downgrade to info log, NOT error
            if (attempt === FAST_ATTEMPTS) {
                showVoiceStatus('Still processing\u2026 large networks can take 10\u201315 min.', 'info');
                addSystemLog('LinkedIn import still running \u2014 large networks take 10\u201315 min. Switching to slow poll (10s).', 'process');
            }

            const delay = attempt < FAST_ATTEMPTS ? 2000 : 10000;
            await new Promise(resolve => setTimeout(resolve, delay));

            // Skip this tick if the tab is hidden — don't hammer the server from background tabs
            if (document.visibilityState === 'hidden') {
                await new Promise(resolve => {
                    const resume = () => { document.removeEventListener('visibilitychange', resume); resolve(); };
                    document.addEventListener('visibilitychange', resume);
                });
            }
        }

        // All attempts exhausted — hand off to lazy background poll
        personaPollActive = false;
        pendingReload = false;
        if (voiceUploadProgress) voiceUploadProgress.style.display = 'none';
        showVoiceStatus('Import is taking very long. Will notify you automatically when done.', 'info');
        addSystemLog('LinkedIn import: switching to background check every 30s. You will be notified when ready.', 'process');
        if (window.setProcessingLock) window.setProcessingLock(false);
        startLazyPersonaPoll();   // keep checking in the background
        return false;
    }

    // Low-frequency background poll (every 30s) — runs after fast poll gives up
    function startLazyPersonaPoll() {
        if (lazyPollTimer) return;   // already running
        const check = async () => {
            const ready = await loadPersona({ suppressEmptyState: false, emitSuccessLog: false });
            if (!ready) {
                lazyPollTimer = setTimeout(check, 30000);
            } else {
                lazyPollTimer = null;
                showVoiceStatus('LinkedIn processing complete!', 'success');
                addSystemLog('User profile persona ready \u2014 detected via background check.', 'success');
                emitLinkedInProcessingStatus('completed');
            }
        };
        lazyPollTimer = setTimeout(check, 30000);
    }

    // Load persona data
    async function loadPersona(options = {}) {
        const { suppressEmptyState = false, emitSuccessLog = false } = options;
        try {
            const res = await fetch('/api/persona', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            
            const data = await res.json();
            const processingStatus = data.processing_status || null;
            const isProcessing = processingStatus === 'processing';
            const isComplete = processingStatus === 'completed' || data.linkedin_imported === true;

            emitLinkedInProcessingStatus(processingStatus, data);

            // ── Persona check comes FIRST ──────────────────────────────────────────
            // Persona presence is the ground truth. If it exists, show it regardless
            // of what processing_status says (stale 'processing' flag is a known bug).
            if (data.success && data.persona) {
                // Persona exists — hide upload section, show import status
                if (voiceUploadSection)  voiceUploadSection.style.display = 'none';
                if (voiceImportStatus)   voiceImportStatus.style.display = 'block';

                // Ensure the User Profile output panel is visible in the main content area
                const voiceOutputView = document.getElementById('output-view-voice-engine');
                const sidePanel = document.getElementById('side-only-panel');
                if (voiceOutputView && sidePanel && !sidePanel.classList.contains('hidden')) {
                    document.querySelectorAll('#side-only-panel .tab-output-view').forEach(v => v.classList.add('hidden'));
                    voiceOutputView.classList.remove('hidden');
                }
                
                _clearProgress();
                if (emitSuccessLog) {
                    addSystemLog('Persona loaded successfully', 'success');
                }
                if (window.setProcessingLock) {
                    window.setProcessingLock(false);
                }
                return true;
            } else {
                // No persona yet — check why
                if (processingStatus === 'error') {
                    showVoiceStatus('LinkedIn import failed. Please try again.', 'error');
                    addSystemLog('LinkedIn import failed during processing.', 'error');
                    if (window.setProcessingLock) window.setProcessingLock(false);
                    pendingReload = false;
                    if (!suppressEmptyState) {
                        if (voiceUploadSection)  voiceUploadSection.style.display = 'block';
                        if (voiceImportStatus)   voiceImportStatus.style.display = 'none';
                    }
                    return false;
                }

                if (isProcessing) {
                    const crmCount  = Number(data.crm_contacts_count || 0);
                    const voiceCount = Number(data.voice_chunks_count || 0);
                    const phase = data.processing_phase || '';
                    if (window.setProcessingLock) {
                        window.setProcessingLock(true, { message: 'LinkedIn import running. Tabs are still available.' });
                    }
                    if (voiceUploadSection)  voiceUploadSection.style.display = 'none';
                    if (voiceImportStatus)   voiceImportStatus.style.display = 'block';
                    if (voiceUploadProgress) {
                        voiceUploadProgress.style.display = 'block';
                        // Set progress bar from real data (survives refresh)
                        const pct = _estimateProgress(crmCount, voiceCount);
                        if (voiceProgressBar) voiceProgressBar.style.width = `${pct}%`;
                        if (voiceProgressLabel) {
                            const parts = [];
                            if (crmCount > 0)  parts.push(`${crmCount} contacts`);
                            if (voiceCount > 0) parts.push(`${voiceCount} voice chunks`);
                            if (phase && phase !== 'completed') {
                                voiceProgressLabel.textContent = phase + (parts.length ? ` · ${parts.join(' · ')}` : '');
                            } else {
                                voiceProgressLabel.textContent = parts.length
                                    ? `Processing… ${parts.join(' · ')} so far`
                                    : 'Processing your LinkedIn data...';
                            }
                        }
                    }

                    // Re-render the output slot so it survives page refresh
                    const outputSlot = document.getElementById('voice-output-slot');
                    if (outputSlot && !outputSlot.querySelector('#voice-diagnostics-panel')) {
                        const progressParts = [];
                        if (crmCount > 0)  progressParts.push(`<strong style="color:rgba(255,255,255,0.9);">${crmCount}</strong> contacts`);
                        if (voiceCount > 0) progressParts.push(`<strong style="color:rgba(255,255,255,0.9);">${voiceCount}</strong> voice chunks`);
                        const progressLine = progressParts.length
                            ? `<p style="color:rgba(255,255,255,0.65);font-size:13px;margin:0 0 12px;">Progress so far: ${progressParts.join(' · ')}</p>`
                            : '';
                        const phaseLine = phase && phase !== 'completed'
                            ? `<p style="color:var(--brand-primary);font-size:13px;font-weight:500;margin:0 0 12px;">${phase}</p>`
                            : '';

                        outputSlot.innerHTML = `
                            <div style="padding:32px 24px;text-align:center;max-width:540px;margin:0 auto;">
                                <div style="font-size:40px;margin-bottom:16px;">\u2699\ufe0f</div>
                                <h3 style="color:var(--brand-primary);margin:0 0 12px;font-size:18px;font-weight:600;">
                                    Your LinkedIn data is being processed
                                </h3>
                                ${phaseLine}
                                ${progressLine}
                                <p style="color:rgba(255,255,255,0.65);font-size:14px;line-height:1.7;margin:0 0 16px;">
                                    For large networks (1,000+ contacts), this typically takes
                                    <strong style="color:rgba(255,255,255,0.9);">45 minutes to 2 hours</strong>
                                    to fully analyze every conversation and build your AI persona.
                                </p>
                                <div id="voice-diagnostics-panel" style="display:none;"></div>
                                <p style="color:rgba(255,255,255,0.45);font-size:13px;margin:0;">
                                    This is going to take a while \u2014 feel free to close this tab and come back later.
                                    Your data will be ready and waiting for you automatically.
                                </p>
                            </div>`;
                    }
                    // Update live counters inside existing output slot
                    else if (outputSlot) {
                        const livePhase = outputSlot.querySelector('.voice-live-phase');
                        const liveProgress = outputSlot.querySelector('.voice-live-progress');
                        // Inject live-updating elements if not present
                        if (!livePhase) {
                            const h3 = outputSlot.querySelector('h3');
                            if (h3 && phase) {
                                const phaseEl = document.createElement('p');
                                phaseEl.className = 'voice-live-phase';
                                phaseEl.style.cssText = 'color:var(--brand-primary);font-size:13px;font-weight:500;margin:0 0 12px;';
                                phaseEl.textContent = phase;
                                h3.insertAdjacentElement('afterend', phaseEl);
                            }
                        } else if (phase) {
                            livePhase.textContent = phase;
                        }
                    }

                    // Ensure User Profile output panel is visible
                    const voiceOutputView = document.getElementById('output-view-voice-engine');
                    const sidePanel = document.getElementById('side-only-panel');
                    if (voiceOutputView && sidePanel && !sidePanel.classList.contains('hidden')) {
                        document.querySelectorAll('#side-only-panel .tab-output-view').forEach(v => v.classList.add('hidden'));
                        voiceOutputView.classList.remove('hidden');
                    }

                    // Render diagnostics if available
                    renderDiagnostics(data.ingestion_diagnostics);
                    if (!personaPollActive) {
                        waitForPersonaReady({ triggerReload: true });
                    }
                    return false;
                }

                // Not processing, not error, no persona — show upload form
                if (!suppressEmptyState) {
                    if (voiceUploadSection)  voiceUploadSection.style.display = 'block';
                    if (voiceImportStatus)   voiceImportStatus.style.display = 'none';
                }
                if (isComplete && pendingReload) {
                    pendingReload = false;
                    if (window.setProcessingLock) window.setProcessingLock(false);
                }
                return false;
            }
        } catch (e) {
            console.error('Failed to load persona', e);
            return false;
        }
    }

    // Render ingestion diagnostics panel in the output slot
    function renderDiagnostics(diag) {
        if (!diag || typeof diag !== 'object') return;
        const panel = document.getElementById('voice-diagnostics-panel');
        if (!panel) return;

        const filesFound = diag.files_found || [];
        const rowsPerFile = diag.rows_per_file || {};
        const missingReq = diag.missing_required || [];
        const missingOpt = diag.missing_optional || [];
        const dedup = diag.dedup_stats || {};
        const zipCount = diag.zip_count || 0;

        if (filesFound.length === 0 && missingReq.length === 0) return; // no data yet

        let html = `<div style="text-align:left;margin:16px 0;padding:16px 20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;font-size:13px;">`;
        html += `<div style="font-weight:600;color:var(--brand-primary);margin-bottom:10px;font-size:14px;">Ingestion Diagnostics${zipCount > 1 ? ` (${zipCount} ZIPs merged)` : ''}</div>`;

        // Files found with row counts
        if (filesFound.length > 0) {
            html += `<div style="margin-bottom:8px;"><span style="color:var(--text-secondary);font-weight:500;">Files found:</span></div>`;
            html += `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">`;
            for (const f of filesFound) {
                const rows = rowsPerFile[f];
                html += `<span style="padding:3px 10px;background:rgba(52,211,153,0.12);color:#6ee7b7;border-radius:6px;font-size:0.75rem;">${f}${rows != null ? ` (${rows} rows)` : ''}</span>`;
            }
            html += `</div>`;
        }

        // Missing required files — with guidance
        if (missingReq.length > 0) {
            html += `<div style="margin-bottom:8px;"><span style="color:var(--error);font-weight:500;">Missing required files:</span></div>`;
            for (const f of missingReq) {
                html += `<div style="padding:6px 12px;margin-bottom:4px;background:rgba(239,68,68,0.08);border-left:3px solid var(--error);border-radius:4px;color:rgba(255,255,255,0.75);font-size:0.78rem;">`;
                html += `<strong>${f}</strong> &mdash; this file is important for full analysis. `;
                if (f === 'Profile.csv') html += `Re-export from LinkedIn with &ldquo;Profile&rdquo; selected.`;
                if (f === 'Connections.csv') html += `Re-export with &ldquo;Connections&rdquo; selected to get contact titles and companies.`;
                html += `</div>`;
            }
        }

        // Missing optional — collapsed hint
        if (missingOpt.length > 0) {
            html += `<div style="margin-top:8px;font-size:0.73rem;color:var(--text-muted);">Optional files not found: ${missingOpt.join(', ')} (won't block import)</div>`;
        }

        // Dedup stats (only for multi-ZIP)
        if (dedup.connections_total > 0) {
            const connDupes = dedup.connections_total - dedup.connections_after_dedup;
            const msgDupes = dedup.messages_total - dedup.messages_after_dedup;
            html += `<div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.06);font-size:0.78rem;color:var(--text-secondary);">`;
            html += `Dedup: <strong>${dedup.connections_after_dedup}</strong> unique connections`;
            if (connDupes > 0) html += ` (${connDupes} duplicates removed)`;
            html += ` · <strong>${dedup.threads_after_dedup || 0}</strong> conversation threads`;
            if (msgDupes > 0) html += ` (${msgDupes} duplicate messages removed)`;
            html += `</div>`;
        }

        html += `</div>`;
        panel.innerHTML = html;
        panel.style.display = 'block';
    }

    // Show status message
    function showVoiceStatus(message, type) {
        if (!voiceStatusMessage) return;
        const colorMap = { error: 'var(--error)', success: 'var(--success)', info: 'var(--text-secondary)' };
        const color = colorMap[type] || 'var(--text-secondary)';
        voiceStatusMessage.innerHTML = `<span style="color: ${color};">${message}</span>`;
        voiceStatusMessage.style.opacity = '1';
        
        const hideAfter = type === 'info' ? 8000 : 5000;
        setTimeout(() => {
            voiceStatusMessage.style.opacity = '0';
        }, hideAfter);
    }

    // ── LinkedIn URL persistence ──────────────────────────────────────────────
    // Load saved LinkedIn URL from settings on init, save it when scraping
    async function loadSavedLinkedInUrl() {
        try {
            const res = await fetch('/api/settings', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const data = await res.json();
            const urlInput = getVoiceLinkedinUrl();
            if (urlInput && data.trackedProfileUrl && !urlInput.value.trim()) {
                urlInput.value = data.trackedProfileUrl;
            }
        } catch (e) {
            console.error('[VoiceEngine] Failed to load saved LinkedIn URL:', e);
        }
    }

    async function saveLinkedInUrl(url) {
        if (!url || !url.includes('linkedin.com')) return;
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': window.appUserId || 'default'
                },
                body: JSON.stringify({ trackedProfileUrl: url })
            });
        } catch (e) {
            console.error('[VoiceEngine] Failed to save LinkedIn URL:', e);
        }
    }

    // ── Profile Card (Argon Dashboard-Inspired, Dark Theme) ─────────────────
    function renderProfileCard(profile) {
        const outputSlot = document.getElementById('voice-output-slot');
        if (!outputSlot) return;
        if (outputSlot.querySelector('#voice-diagnostics-panel')) return;

        // Helper: return non-empty array or null (fixes [] truthy bug)
        const _a = (v) => Array.isArray(v) && v.length > 0 ? v : null;

        // ── Data extraction ──
        const analyzed = profile.analyzed_profile || profile.summary || {};
        const raw = profile.raw_json || {};
        const hasData = (analyzed && (analyzed.bio || analyzed.first_name || _a(analyzed.experiences)))
                     || (raw && Object.keys(raw).length > 2);

        const firstName = analyzed.first_name || profile.first_name || raw.firstName || '';
        const lastName  = analyzed.last_name  || profile.last_name  || raw.lastName  || '';
        let fullName = raw.fullName || `${firstName} ${lastName}`.trim();
        if (!fullName && profile.linkedin_url) {
            const slug = profile.linkedin_url.replace(/\/$/, '').split('/').pop() || '';
            fullName = slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        }
        fullName = fullName || 'LinkedIn Profile';

        const headline    = analyzed.headline || profile.headline || raw.headline || raw.jobTitle || '';
        const company     = analyzed.current_company || profile.company || raw.companyName || raw.currentCompany || '';
        const location    = analyzed.location || profile.location || raw.jobLocation || raw.location || '';
        const industry    = analyzed.industry || profile.industry || raw.companyIndustry || raw.industry || '';
        const bio         = analyzed.bio || raw.about || raw.summary || '';
        const picUrl      = analyzed.profile_picture_url || profile.profile_pic_url || raw.profilePic || raw.profilePicture || '';
        const linkedinUrl = analyzed.linkedin_url || profile.linkedin_url || raw.linkedinUrl || '';
        const followers   = Number(analyzed.followers || raw.followers || raw.followersCount || 0);
        const connections = Number(analyzed.connections || raw.connections || raw.connectionsCount || 0);

        // Arrays: use _a() to skip empty arrays and fall through to raw
        // Merge experiences: analyzed has title+company, raw has all Apify fields
        let experiences = [];
        const analyzedExp = _a(analyzed.experiences) || [];
        const rawExp = _a(raw.experiences) || _a(raw.positions) || [];
        if (analyzedExp.length && rawExp.length) {
            experiences = analyzedExp.map((aExp, i) => {
                // Match by index first (same order), then by title
                const match = rawExp[i] || rawExp.find(r =>
                    (r.title || r.jobTitle || '').toLowerCase() === (aExp.title || '').toLowerCase()
                ) || {};
                return { ...match, ...aExp,
                    // Prefer raw for detailed fields the LLM may have left empty
                    description: aExp.description || match.jobDescription || match.description || '',
                    location: aExp.location || match.jobLocation || match.location || '',
                    duration: aExp.duration || match.duration || '',
                    employment_type: aExp.employment_type || match.employmentType || match.employment_type || '',
                    location_type: aExp.location_type || match.locationType || match.location_type || '',
                    is_current: aExp.is_current || match.jobStillWorking || match.is_current || false,
                    company: aExp.company || match.companyName || match.company || '',
                };
            });
        } else {
            experiences = analyzedExp.length ? analyzedExp : rawExp;
        }
        const education   = _a(analyzed.education)   || _a(raw.educations) || _a(raw.education)  || [];
        const skills      = _a(analyzed.skills)      || _a(raw.skills)     || [];
        const keyInsights = _a(analyzed.key_insights) || [];

        // ── Helpers ──
        const initials = fullName.split(/\s+/).filter(Boolean).map(w => w[0]).join('').toUpperCase().slice(0, 2) || 'LP';

        // Bio truncation
        const BIO_LIMIT = 220;
        const bioShort = bio.length > BIO_LIMIT ? bio.substring(0, BIO_LIMIT).replace(/\s+\S*$/, '') + '…' : bio;
        const bioNeedsTruncate = bio.length > BIO_LIMIT;

        // Avatar
        const avatarHTML = picUrl
            ? `<img src="${_esc(picUrl)}" class="ap-avatar-img" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
               <div class="ap-avatar-fallback" style="display:none">${initials}</div>`
            : `<div class="ap-avatar-fallback">${initials}</div>`;

        // ── Build experience cards (Uiverse-inspired stacked card design) ──
        let expHTML = '';
        if (experiences.length) {
            const cards = experiences.slice(0, 8).map((exp, idx) => {
                const t = _esc(exp.title || exp.jobTitle || exp.role || 'Role');
                const c = _esc(exp.company || exp.companyName || exp.organization || '');
                const loc = _esc(exp.location || exp.jobLocation || '');
                const empType = _esc(exp.employment_type || exp.employmentType || '');
                const locType = _esc(exp.location_type || exp.locationType || '');
                const isCurrent = exp.is_current || exp.isCurrent || exp.jobStillWorking || false;

                // Duration: prefer pre-formatted string, else build from start/end
                let dur = exp.duration || exp.dateRange || '';
                if (!dur) {
                    // jobStartedOn can be "9-2025" or {month:"Sep", year:2025} or "Sep 2025"
                    const sd = exp.jobStartedOn || exp.start_date || exp.startDate || '';
                    const ed = exp.jobEndedOn || exp.end_date || exp.endDate || '';
                    const fmtDate = (d) => {
                        if (!d) return '';
                        if (typeof d === 'string') {
                            // "9-2025" → "Sep 2025"
                            const m = d.match(/^(\d{1,2})-(\d{4})$/);
                            if (m) { const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m[1])-1] || m[1]; return `${mn} ${m[2]}`; }
                            return d;
                        }
                        if (d.month) return `${d.month} ${d.year || ''}`.trim();
                        if (d.year) return String(d.year);
                        return '';
                    };
                    const sStr = fmtDate(sd);
                    const eStr = isCurrent ? 'Present' : fmtDate(ed);
                    if (sStr || eStr) dur = [sStr, eStr].filter(Boolean).join(' — ');
                }
                dur = _esc(dur);

                const desc = _esc(exp.description || exp.jobDescription || '');
                const descShort = desc.length > 80 ? desc.substring(0, 80).replace(/\s+\S*$/, '') + '…' : desc;

                const chips = [empType, locType].filter(Boolean).map(ch => `<span class="ap-xp-chip">${ch}</span>`).join('');

                return `<div class="ap-xp-card${isCurrent ? ' ap-xp-current' : ''}">
                    <div class="ap-xp-rank">${String(idx + 1).padStart(2, '0')}</div>
                    <div class="ap-xp-title">${t}</div>
                    <div class="ap-xp-company">${c || '—'}</div>
                    ${dur ? `<div class="ap-xp-dur"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:4px;opacity:0.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>${dur}</div>` : ''}
                    ${chips ? `<div class="ap-xp-chips">${chips}</div>` : ''}
                    ${descShort ? `<div class="ap-xp-desc">${descShort}</div>` : ''}
                    <div class="ap-xp-bar"><div class="ap-xp-bar-empty"></div><div class="ap-xp-bar-fill"></div></div>
                </div>`;
            }).join('');
            expHTML = `<div class="ap-section">
                <div class="ap-section-hdr"><span class="ap-section-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg></span>Experience<span class="ap-xp-count">${experiences.length}</span></div>
                <div class="ap-xp-strip">${cards}</div>
            </div>`;
        }

        // ── Build skills HTML ──
        let skillsHTML = '';
        if (skills.length) {
            const pills = skills.slice(0, 20).map(s => {
                const name = typeof s === 'string' ? s : (s.title || s.name || s.skill || '');
                return name ? `<span class="ap-pill">${_esc(name)}</span>` : '';
            }).filter(Boolean).join('');
            if (pills) skillsHTML = `<div class="ap-section">
                <div class="ap-section-hdr"><span class="ap-section-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></span>Skills</div>
                <div class="ap-pills-wrap">${pills}</div>
            </div>`;
        }

        // ── Build education HTML ──
        let eduHTML = '';
        if (education.length) {
            const items = education.slice(0, 4).map(edu => {
                const school = _esc(edu.school || edu.schoolName || edu.institution || edu.name || '');
                const degree = _esc(edu.degree || edu.degreeName || '');
                const field  = _esc(edu.field || edu.fieldOfStudy || edu.major || '');
                const dates  = _esc(edu.dates || edu.dateRange || [edu.startDate, edu.endDate].filter(Boolean).join(' – ') || '');
                return `<div class="ap-edu-row">
                    <div class="ap-edu-school">${school}</div>
                    ${degree || field ? `<div class="ap-edu-degree">${[degree, field].filter(Boolean).join(' — ')}</div>` : ''}
                    ${dates ? `<div class="ap-edu-date">${dates}</div>` : ''}
                </div>`;
            }).join('');
            eduHTML = `<div class="ap-section">
                <div class="ap-section-hdr"><span class="ap-section-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m4 6 8-4 8 4"/><path d="m18 10 4 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8l4-2"/><path d="M14 22v-4a2 2 0 0 0-4 0v4"/><path d="M18 5v17"/><path d="M6 5v17"/></svg></span>Education</div>
                ${items}
            </div>`;
        }

        // ── Build insights HTML ──
        let insightsHTML = '';
        if (keyInsights.length) {
            const items = keyInsights.slice(0, 6).map(i => `<li class="ap-insight-item">${_esc(i)}</li>`).join('');
            insightsHTML = `<div class="ap-section">
                <div class="ap-section-hdr"><span class="ap-section-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v8l4 4"/><circle cx="12" cy="12" r="10"/></svg></span>Key Insights</div>
                <ul class="ap-insights-list">${items}</ul>
            </div>`;
        }

        // ── Status badge text ──
        const badgeClass = hasData ? 'ap-badge-ok' : 'ap-badge-muted';
        const badgeText  = (analyzed.bio || analyzed.first_name) ? 'AI Analyzed' : (Object.keys(raw).length > 2 ? 'Data Scraped' : 'Linked');

        // ══════════════════════════════════════════════════════════════════════
        //  RENDER — Polished Argon-inspired single-scroll layout
        // ══════════════════════════════════════════════════════════════════════
        outputSlot.innerHTML = `
        <div class="ap-scroll">

          <!-- ▸ HEADER BANNER -->
          <div class="ap-banner">
            <div class="ap-banner-bg"></div>
            <div class="ap-banner-content">
              <div class="ap-avatar-zone">${avatarHTML}</div>
              <div class="ap-id-zone">
                <h2 class="ap-name">${_esc(fullName)}</h2>
                ${headline ? `<p class="ap-headline">${_esc(headline)}</p>` : ''}
                <div class="ap-meta-row">
                  ${company  ? `<span class="ap-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/></svg>${_esc(company)}</span>` : ''}
                  ${location ? `<span class="ap-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>${_esc(location)}</span>` : ''}
                  ${industry ? `<span class="ap-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>${_esc(industry)}</span>` : ''}
                </div>
              </div>
              <span class="ap-badge ${badgeClass}">${badgeText}</span>
            </div>
          </div>

          <!-- ▸ STATS BAR -->
          <div class="ap-stats-bar">
            ${followers   ? `<div class="ap-stat"><span class="ap-stat-val">${followers.toLocaleString()}</span><span class="ap-stat-lbl">Followers</span></div>` : ''}
            ${connections ? `<div class="ap-stat"><span class="ap-stat-val">${connections.toLocaleString()}</span><span class="ap-stat-lbl">Connections</span></div>` : ''}
            ${experiences.length ? `<div class="ap-stat"><span class="ap-stat-val">${experiences.length}</span><span class="ap-stat-lbl">Positions</span></div>` : ''}
            ${skills.length ? `<div class="ap-stat"><span class="ap-stat-val">${skills.length}</span><span class="ap-stat-lbl">Skills</span></div>` : ''}
            ${linkedinUrl ? `<a href="${_esc(linkedinUrl)}" target="_blank" rel="noopener" class="ap-stat ap-stat-link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg><span class="ap-stat-lbl">LinkedIn</span></a>` : ''}
          </div>

          <!-- ▸ BODY: two-column grid -->
          <div class="ap-body">

            <!-- LEFT COL: About + Skills -->
            <div class="ap-col-left">
              ${bio ? `<div class="ap-card">
                <div class="ap-section">
                  <div class="ap-section-hdr"><span class="ap-section-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg></span>About</div>
                  <p class="ap-bio" id="ap-bio-text">${_esc(bioShort)}</p>
                  ${bioNeedsTruncate ? `<button class="ap-show-more" id="ap-bio-toggle" data-full="${_esc(bio).replace(/"/g, '&quot;')}" data-short="${_esc(bioShort).replace(/"/g, '&quot;')}" data-expanded="false">Show more</button>` : ''}
                </div>
              </div>` : ''}
              ${skillsHTML ? `<div class="ap-card">${skillsHTML}</div>` : ''}
              ${eduHTML ? `<div class="ap-card">${eduHTML}</div>` : ''}
              ${insightsHTML ? `<div class="ap-card">${insightsHTML}</div>` : ''}
            </div>

            <!-- RIGHT COL: Experience -->
            <div class="ap-col-right">
              ${expHTML || ''}
              ${!expHTML && !skillsHTML && !eduHTML ? `<div class="ap-card" style="padding:32px;text-align:center;">
                <p style="color:rgba(255,255,255,0.4);font-size:13px;margin:0 0 12px;">Minimal data available. Try re-scraping.</p>
                <button id="ve-rescrape-btn" class="ap-btn-outline">Re-scrape Profile</button>
              </div>` : ''}
            </div>
          </div>
        </div>

        <style>
          /* ── Scroll container ── */
          .ap-scroll{width:100%;max-width:1100px;margin:0 auto;overflow-y:auto;overflow-x:hidden;max-height:calc(100vh - 120px);padding:0 8px 24px;box-sizing:border-box;}
          .ap-scroll::-webkit-scrollbar{width:5px}.ap-scroll::-webkit-scrollbar-track{background:transparent}.ap-scroll::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:4px;}

          /* ── Banner ── */
          .ap-banner{position:relative;border-radius:18px;overflow:hidden;margin-bottom:0;}
          .ap-banner-bg{position:absolute;inset:0;background:linear-gradient(135deg,rgba(249,199,79,0.08) 0%,rgba(14,14,14,0.95) 60%);z-index:0;}
          .ap-banner-content{position:relative;z-index:1;display:flex;align-items:center;gap:24px;padding:30px 36px;}
          .ap-avatar-zone{flex-shrink:0;}
          .ap-avatar-img{width:104px;height:104px;border-radius:50%;object-fit:cover;border:3px solid rgba(249,199,79,0.3);box-shadow:0 4px 20px rgba(0,0,0,0.4);}
          .ap-avatar-fallback{width:104px;height:104px;border-radius:50%;background:linear-gradient(135deg,rgba(249,199,79,0.2),rgba(249,199,79,0.06));border:3px solid rgba(249,199,79,0.3);display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:700;color:var(--brand-primary);}
          .ap-id-zone{flex:1;min-width:0;}
          .ap-name{color:#fff;margin:0 0 4px;font-size:26px;font-weight:700;line-height:1.3;}
          .ap-headline{color:rgba(255,255,255,0.55);font-size:14px;margin:0 0 10px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
          .ap-meta-row{display:flex;flex-wrap:wrap;gap:8px;}
          .ap-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:6px;font-size:12.5px;color:rgba(255,255,255,0.55);}
          .ap-chip svg{color:rgba(249,199,79,0.6);flex-shrink:0;}
          .ap-badge{position:absolute;top:24px;right:28px;padding:6px 16px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:0.3px;}
          .ap-badge-ok{background:rgba(76,175,80,0.15);color:#6ee7b7;}
          .ap-badge-muted{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.45);}

          /* ── Stats bar ── */
          .ap-stats-bar{display:flex;gap:0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 18px 18px;margin-bottom:20px;overflow:hidden;}
          .ap-stat{flex:1;text-align:center;padding:18px 10px;border-right:1px solid rgba(255,255,255,0.05);}
          .ap-stat:last-child{border-right:none;}
          .ap-stat-val{display:block;font-size:22px;font-weight:700;color:rgba(255,255,255,0.92);}
          .ap-stat-lbl{font-size:11.5px;color:rgba(255,255,255,0.38);text-transform:uppercase;letter-spacing:0.6px;}
          .ap-stat-link{text-decoration:none;display:flex;flex-direction:column;align-items:center;gap:4px;transition:background 0.2s;}
          .ap-stat-link:hover{background:rgba(249,199,79,0.06)!important;}
          .ap-stat-link svg{color:var(--brand-primary);}

          /* ── Body grid ── */
          .ap-body{display:grid;grid-template-columns:1fr 1.5fr;gap:20px;}
          .ap-col-left,.ap-col-right{min-width:0;overflow:hidden;}

          /* ── Cards ── */
          .ap-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:24px;margin-bottom:16px;}
          .ap-card:last-child{margin-bottom:0;}

          /* ── Sections ── */
          .ap-section{margin-bottom:0;}
          .ap-section-hdr{display:flex;align-items:center;gap:8px;margin-bottom:16px;font-size:14px;font-weight:700;color:rgba(255,255,255,0.7);text-transform:uppercase;letter-spacing:0.5px;}
          .ap-section-icon{display:flex;color:var(--brand-primary);opacity:0.7;}

          /* ── About / Bio ── */
          .ap-bio{color:rgba(255,255,255,0.6);font-size:14px;line-height:1.7;margin:0;}
          .ap-show-more{background:none;border:none;color:var(--brand-primary);font-size:13px;font-weight:600;cursor:pointer;padding:6px 0 0;opacity:0.8;transition:opacity 0.2s;}
          .ap-show-more:hover{opacity:1;}

          /* ── Experience cards (Uiverse-inspired stacked) ── */
          .ap-xp-count{margin-left:auto;font-size:11px;font-weight:600;color:rgba(255,255,255,0.3);background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:10px;text-transform:none;letter-spacing:0;}
          .ap-xp-strip{display:flex;padding:12px 0 20px 14px;overflow-x:auto;scroll-snap-type:x proximity;}
          .ap-xp-strip::-webkit-scrollbar{height:4px;}
          .ap-xp-strip::-webkit-scrollbar-track{background:transparent;}
          .ap-xp-strip::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:4px;}
          .ap-xp-card{flex:0 0 215px;min-height:240px;background:linear-gradient(165deg,rgba(38,28,58,0.92) 0%,rgba(22,18,35,0.95) 100%);border:1px solid rgba(255,255,255,0.07);border-radius:14px;box-shadow:-1rem 0 2.5rem rgba(0,0,0,0.35);position:relative;left:0;transition:all 0.4s ease-out;padding:20px 18px 32px;display:flex;flex-direction:column;scroll-snap-align:start;cursor:default;}
          .ap-xp-card:not(:first-child){margin-left:-40px;}
          .ap-xp-card:hover{transform:translateY(-18px);z-index:10;box-shadow:0 14px 36px rgba(0,0,0,0.55),0 0 0 1px rgba(249,199,79,0.15);text-shadow:1px 1px 8px rgba(249,199,79,0.1);}
          .ap-xp-card:hover~.ap-xp-card{position:relative;left:40px;transition:all 0.4s ease-out;}
          .ap-xp-current{border-color:rgba(249,199,79,0.18);}
          .ap-xp-current .ap-xp-bar-fill{width:60%;}
          .ap-xp-rank{position:absolute;top:14px;right:14px;font-size:10px;font-weight:800;color:rgba(255,255,255,0.1);letter-spacing:0.5px;}
          .ap-xp-title{font-size:16px;font-weight:800;color:#fff;line-height:1.25;margin-bottom:6px;}
          .ap-xp-company{font-size:13px;font-weight:600;color:var(--brand-primary);margin-bottom:6px;}
          .ap-xp-dur{font-size:11.5px;color:rgba(255,255,255,0.38);margin-bottom:7px;line-height:1.3;}
          .ap-xp-chips{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px;}
          .ap-xp-chip{padding:3px 8px;background:rgba(249,199,79,0.07);border:1px solid rgba(249,199,79,0.12);border-radius:5px;font-size:10.5px;color:rgba(249,199,79,0.65);font-weight:600;text-transform:uppercase;letter-spacing:0.3px;}
          .ap-xp-desc{font-size:12px;color:rgba(255,255,255,0.35);line-height:1.5;flex:1;}
          .ap-xp-bar{position:absolute;bottom:0;left:0;right:0;height:4px;border-radius:0 0 12px 12px;overflow:hidden;}
          .ap-xp-bar-empty{width:100%;height:100%;background:rgba(255,255,255,0.03);}
          .ap-xp-bar-fill{position:absolute;top:0;left:0;width:0;height:100%;background:linear-gradient(90deg,rgba(249,199,79,0.35),rgba(249,199,79,0.85));transition:0.6s ease-out;}
          .ap-xp-card:hover .ap-xp-bar-fill{width:100%;transition:0.4s ease-out;}

          /* ── Skills pills ── */
          .ap-pills-wrap{display:flex;flex-wrap:wrap;gap:8px;}
          .ap-pill{padding:6px 14px;background:rgba(249,199,79,0.07);color:var(--brand-primary);border:1px solid rgba(249,199,79,0.14);border-radius:8px;font-size:13px;font-weight:600;}

          /* ── Education ── */
          .ap-edu-row{padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);}
          .ap-edu-row:last-child{border-bottom:none;padding-bottom:0;}
          .ap-edu-row:first-child{padding-top:0;}
          .ap-edu-school{color:rgba(255,255,255,0.82);font-size:14px;font-weight:600;}
          .ap-edu-degree{color:rgba(255,255,255,0.45);font-size:13px;margin-top:3px;}
          .ap-edu-date{color:rgba(255,255,255,0.28);font-size:12px;margin-top:3px;}

          /* ── Key Insights ── */
          .ap-insights-list{list-style:none;padding:0;margin:0;}
          .ap-insight-item{padding:8px 0;color:rgba(255,255,255,0.6);font-size:13.5px;line-height:1.55;border-bottom:1px solid rgba(255,255,255,0.04);}
          .ap-insight-item:last-child{border-bottom:none;}
          .ap-insight-item::before{content:'\\25B8';color:var(--brand-primary);margin-right:8px;}

          /* ── Buttons ── */
          .ap-btn-outline{background:transparent;color:var(--brand-primary);border:1px solid rgba(249,199,79,0.25);padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;}
          .ap-btn-outline:hover{background:rgba(249,199,79,0.1);}

          /* ── Responsive ── */
          @media(max-width:860px){
            .ap-body{grid-template-columns:1fr;}
            .ap-banner-content{padding:20px;gap:16px;}
            .ap-avatar-img,.ap-avatar-fallback{width:72px;height:72px;font-size:24px;}
            .ap-name{font-size:20px;}
            .ap-stats-bar{flex-wrap:wrap;}
            .ap-stat{flex:1 1 30%;min-width:0;padding:10px 6px;}
          }
          @media(max-width:560px){
            .ap-scroll{padding:0 2px 16px;}
            .ap-banner-content{flex-direction:column;align-items:flex-start;padding:16px;gap:12px;}
            .ap-avatar-img,.ap-avatar-fallback{width:60px;height:60px;font-size:20px;}
            .ap-name{font-size:18px;}
            .ap-headline{font-size:11.5px;-webkit-line-clamp:3;}
            .ap-badge{top:12px;right:12px;font-size:10px;padding:4px 10px;}
            .ap-stat{padding:8px 4px;}
            .ap-stat-val{font-size:15px;}
            .ap-stat-lbl{font-size:9px;}
            .ap-card{padding:14px;border-radius:10px;}
            .ap-xp-card{flex:0 0 160px;min-height:190px;padding:14px 12px 26px;}
            .ap-xp-card:not(:first-child){margin-left:-30px;}
            .ap-xp-title{font-size:13px;}
            .ap-xp-company{font-size:11px;}
            .ap-pill{padding:4px 9px;font-size:10.5px;}
          }
        </style>`;

        outputSlot.classList.add('ve-has-profile-card');

        // Wire bio show more/less toggle
        const bioToggle = outputSlot.querySelector('#ap-bio-toggle');
        if (bioToggle) {
            bioToggle.addEventListener('click', () => {
                const bioEl = outputSlot.querySelector('#ap-bio-text');
                const expanded = bioToggle.dataset.expanded === 'true';
                if (expanded) {
                    bioEl.textContent = bioToggle.dataset.short.replace(/&quot;/g, '"');
                    bioToggle.textContent = 'Show more';
                    bioToggle.dataset.expanded = 'false';
                } else {
                    bioEl.textContent = bioToggle.dataset.full.replace(/&quot;/g, '"');
                    bioToggle.textContent = 'Show less';
                    bioToggle.dataset.expanded = 'true';
                }
            });
        }

        // Wire re-scrape button
        const rescrapeBtn = outputSlot.querySelector('#ve-rescrape-btn');
        if (rescrapeBtn) {
            rescrapeBtn.addEventListener('click', () => {
                const scrapeBtn = document.getElementById('voice-scrape-btn');
                if (scrapeBtn) scrapeBtn.click();
            });
        }
    }

    function _esc(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }

    // ── User Profile output slot empty state ─────────────────────────────────
    function renderOutputEmptyState() {
        const outputSlot = document.getElementById('voice-output-slot');
        if (!outputSlot || outputSlot.querySelector('.voice-persona-loaded')) return;
        // Don't overwrite processing content or profile card
        if (outputSlot.querySelector('#voice-diagnostics-panel')) return;
        if (outputSlot.querySelector('.ve-profile-card')) return;
        outputSlot.innerHTML = `
            <div style="padding:48px 24px;text-align:center;max-width:520px;margin:0 auto;">
                <div style="width:64px;height:64px;border-radius:16px;background:rgba(249,199,79,0.1);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--brand-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>
                    </svg>
                </div>
                <h3 style="color:rgba(255,255,255,0.9);margin:0 0 10px;font-size:17px;font-weight:600;">No Profile Data Yet</h3>
                <p style="color:rgba(255,255,255,0.5);font-size:13.5px;line-height:1.7;margin:0 0 20px;">
                    Upload your LinkedIn data export or scrape your profile to build your AI persona.
                    Once built, your persona, writing style, and voice context will appear here.
                </p>
                <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
                    <div style="padding:10px 16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;font-size:12px;color:rgba(255,255,255,0.45);">
                        <strong style="color:rgba(255,255,255,0.7);">Step 1</strong><br>Enter LinkedIn URL &amp; Scrape
                    </div>
                    <div style="padding:10px 16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;font-size:12px;color:rgba(255,255,255,0.45);">
                        <strong style="color:rgba(255,255,255,0.7);">Step 2</strong><br>Upload LinkedIn ZIP Export
                    </div>
                    <div style="padding:10px 16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;font-size:12px;color:rgba(255,255,255,0.45);">
                        <strong style="color:rgba(255,255,255,0.7);">Step 3</strong><br>AI Persona &amp; CRM Built
                    </div>
                </div>
            </div>`;
    }

    // Initialize - auth.js calls window.loadVoicePersona() when auth resolves.
    // Do NOT call loadPersona() here — appUserId is not set yet at DOMContentLoaded,
    // which causes the request to use uid='default' and may trigger spurious progress bar.
    window.loadVoicePersona = async (opts = {}) => {
        // Load saved LinkedIn URL into the input field
        await loadSavedLinkedInUrl();
        // Load persona (populates sidebar bio/skills/tone)
        const ready = await loadPersona(opts);

        // ALWAYS try to render the profile card in the output console.
        // Persona lives in the sidebar; profile card lives in the output panel.
        try {
            const profRes = await fetch('/api/voice/profile', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const profData = await profRes.json();
            if (profData.success && profData.profile && profData.profile.linkedin_url) {
                renderProfileCard(profData.profile);
            } else if (!ready) {
                renderOutputEmptyState();
            }
        } catch (_e) {
            if (!ready) renderOutputEmptyState();
        }
        return ready;
    };
});
