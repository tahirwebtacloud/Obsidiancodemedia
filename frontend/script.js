document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('generator-form');
    const resultsSection = document.getElementById('results-content');
    const captionPreview = document.getElementById('caption-preview');
    const submitBtn = document.getElementById('submit-btn');
    const approveBtn = document.getElementById('approve-btn');
    const regenerateCaptionBtn = document.getElementById('regenerate-caption-btn');
    const regenerateImageBtn = document.getElementById('regenerate-image-btn');
    const resultsPanel = document.getElementById('results-panel');
    const orchStatus = document.getElementById('orchestrator-status');
    const orchStatusText = document.getElementById('orchestrator-status-text');

    // Modal Elements
    const fullPostModal = document.getElementById('full-post-modal');
    const modalPostTitle = document.getElementById('modal-post-title');
    const modalPostText = document.getElementById('modal-post-text');
    const modalPostMeta = document.getElementById('modal-post-meta');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalRepurposeBtn = document.getElementById('modal-repurpose-btn');

    let currentResult = null;
    let currentModalItem = null;

    // Profile Tracker Elements
    const trackedProfileUrlInput = document.getElementById('tracked-profile-url');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const profileSaveStatus = document.getElementById('profile-save-status');

    if (trackedProfileUrlInput && saveProfileBtn) {
        // Enable save only when modified
        trackedProfileUrlInput.addEventListener('input', () => {
             saveProfileBtn.disabled = false;
             saveProfileBtn.textContent = 'Save';
             if (profileSaveStatus) profileSaveStatus.style.opacity = '0';
        });

        // Save URL
        saveProfileBtn.addEventListener('click', async () => {
            const newUrl = trackedProfileUrlInput.value.trim();
            saveProfileBtn.disabled = true;
            saveProfileBtn.textContent = 'Saving...';
            
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify({ trackedProfileUrl: newUrl })
                });
                
                if (res.ok) {
                    saveProfileBtn.textContent = 'Saved';
                    if (profileSaveStatus) {
                        profileSaveStatus.style.opacity = '1';
                        setTimeout(() => profileSaveStatus.style.opacity = '0', 3000);
                    }
                    addSystemLog('Updated tracked profile URL successfully.', 'success');
                } else {
                     addSystemLog('Failed to save profile URL.', 'error');
                     saveProfileBtn.disabled = false;
                     saveProfileBtn.textContent = 'Save';
                }
            } catch (err) {
                 console.error(err);
                 addSystemLog('Network error saving profile URL.', 'error');
                 saveProfileBtn.disabled = false;
                 saveProfileBtn.textContent = 'Save';
            }
        });
    }

    // Load Initial Settings
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const data = await res.json();
            if (trackedProfileUrlInput && data.trackedProfileUrl) {
                trackedProfileUrlInput.value = data.trackedProfileUrl;
            }
        } catch (e) {
            console.error('Failed to load settings', e);
        }
    }
    // Defer until auth is ready — auth.js triggers via window.loadSettings()
    window.loadSettings = loadSettings;

    // Global loading state manager
    let safetyTimeout = null;
    function setGlobalLoading(isLoading) {
        if (safetyTimeout) clearTimeout(safetyTimeout);

        try {
            // Target specific generation/action buttons only
            const actionSelectors = [
                '#submit-btn',
                '#repurpose-confirm-btn',
                '#regenerate-caption-btn',
                '#regenerate-image-btn',
                '#hunt-competitors-btn',
                '#viral-search-btn',
                '#search-youtube-btn',
                '#approve-btn'
            ];

            const actionButtons = document.querySelectorAll(actionSelectors.join(','));

            actionButtons.forEach(btn => {
                if (btn) {
                    btn.disabled = isLoading;
                    if (isLoading) {
                        btn.classList.add('opacity-50', 'cursor-not-allowed');
                    } else {
                        btn.classList.remove('opacity-50', 'cursor-not-allowed');
                    }
                }
            });

            // Safety valve: Auto-enable after 60s in case of crash/hang
            if (isLoading) {
                safetyTimeout = setTimeout(() => {
                    console.warn("Safety timeout triggered: Re-enabling buttons");
                    setGlobalLoading(false);
                }, 60000);
            }

        } catch (e) {
            console.error("UI State Error:", e);
        }
    }

    function setOrchestratorStatus(running) {
        if (!orchStatus || !orchStatusText) return;
        if (running) {
            orchStatus.classList.add('active');
            orchStatusText.textContent = 'Orchestrator Running';
        } else {
            orchStatus.classList.remove('active');
            orchStatusText.textContent = 'Orchestrator Idle';
        }
    }

    // System Log Helper - Mad Scientist Edition
    function playSystemSound(type) {
        try {
            if (!window.speechSynthesis) return;
            
            const utterance = new SpeechSynthesisUtterance();
            utterance.volume = 1;
            
            if (type === 'success') {
                utterance.text = 'Task Completed Successfully';
                utterance.rate = 1.0;
                utterance.pitch = 1.1;
            } else if (type === 'error') {
                utterance.text = 'Error. Error.';
                utterance.rate = 0.8;
                utterance.pitch = 0.3;
            }
            
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.warn("Speech synthesis failed:", e);
        }
    }

    function addSystemLog(message, type = 'info') {
        const logTerminal = document.querySelector('.log-terminal');
        if (!logTerminal) return;

        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        const typeLabels = {
            info: 'SYS',
            script: 'EXEC',
            success: 'OK',
            error: 'ERR',
            api: 'HTTP',
            process: 'PROC',
            neural: 'AI'
        };
        const label = typeLabels[type] || 'SYS';

        const logLine = document.createElement('p');
        logLine.className = 'log-line';
        logLine.innerHTML = `<span class="time">[${timestamp}]</span><span class="log-type log-type-${type}">${label}</span> ${message}`;
        logTerminal.appendChild(logLine);
        logTerminal.scrollTop = logTerminal.scrollHeight;
        
        // Trigger sound for specific types
        if (type === 'success' || type === 'error') {
            playSystemSound(type);
        }
    }

    // Verbose logging helpers
    function logProcess(step) { addSystemLog(step, 'process'); }
    function logNeural(step) { addSystemLog(step, 'neural'); }

    // Mad Scientist Fake Log Stream
    const madScienceMessages = [
        ['process', 'Spawning async worker threads...'],
        ['api', 'Establishing secure tunnel → remote node'],
        ['neural', 'Loading transformer weights [2.4GB]'],
        ['process', 'Parsing DOM tree... 847 nodes found'],
        ['neural', 'Running semantic embeddings...'],
        ['api', 'Chunk 1/5 received [204 OK]'],
        ['process', 'Tokenizing content stream...'],
        ['neural', 'Cross-referencing attention layers'],
        ['api', 'WebSocket handshake complete'],
        ['process', 'Extracting metadata vectors...'],
        ['neural', 'Clustering similar patterns...'],
        ['process', 'Decoding base64 payload...'],
        ['api', 'Rate limit check: 847/1000 remaining'],
        ['neural', 'Applying sentiment analysis...'],
        ['process', 'Building adjacency matrix...'],
        ['neural', 'Calibrating output neurons...'],
        ['api', 'Chunk 3/5 received [204 OK]'],
        ['process', 'Decompressing gzip stream...'],
        ['neural', 'Scoring relevance vectors...'],
        ['process', 'Validating JSON schema...'],
    ];
    let fakeLogInterval = null;
    function startMadScienceLogs() {
        let idx = 0;
        fakeLogInterval = setInterval(() => {
            if (idx < madScienceMessages.length) {
                addSystemLog(madScienceMessages[idx][1], madScienceMessages[idx][0]);
                idx++;
            } else {
                idx = 0; // Loop
            }
        }, 800);
    }
    function stopMadScienceLogs() {
        if (fakeLogInterval) clearInterval(fakeLogInterval);
    }

    // ================================================
    // SSE PROGRESS TRACKER
    // ================================================
    const progressEl = document.getElementById('generation-progress');
    const stageResearchEl = document.getElementById('stage-research');
    const stagePatternEl = document.getElementById('stage-pattern');
    const stageTextEl = document.getElementById('stage-text');
    const stageImageEl = document.getElementById('stage-image');
    
    const stageResearchStatus = document.getElementById('stage-research-status');
    const stagePatternStatus = document.getElementById('stage-pattern-status');
    const stageTextStatus = document.getElementById('stage-text-status');
    const stageImageStatus = document.getElementById('stage-image-status');
    
    const connector1 = document.getElementById('connector-1');
    const connector2 = document.getElementById('connector-2');
    const connector3 = document.getElementById('connector-3');
    
    const progressTitle = document.getElementById('progress-title');

    function resetProgress() {
        if (!progressEl) return;
        [stageResearchEl, stagePatternEl, stageTextEl, stageImageEl].forEach(el => {
            if (el) el.className = 'progress-stage';
        });
        
        [connector1, connector2, connector3].forEach(el => {
           if (el) el.style.transform = 'scaleX(0)';
        });

        if (stageResearchStatus) stageResearchStatus.textContent = 'Waiting';
        if (stagePatternStatus) stagePatternStatus.textContent = 'Waiting';
        if (stageTextStatus) stageTextStatus.textContent = 'Waiting';
        if (stageImageStatus) stageImageStatus.textContent = 'Waiting';
        
        if (progressTitle) progressTitle.textContent = 'Generating Content...';
    }

    function showProgress(hasImage = true) {
        resetProgress();
        
        if (stageImageEl) {
            stageImageEl.style.display = hasImage ? 'flex' : 'none';
        }
        if (connector3 && connector3.parentElement) {
            connector3.parentElement.style.display = hasImage ? 'block' : 'none';
        }

        if (progressEl) progressEl.classList.remove('hidden');
        if (document.getElementById('empty-state')) document.getElementById('empty-state').style.display = 'none';
        if (resultsSection) resultsSection.classList.add('hidden');
        if (window.lucide) lucide.createIcons();
    }

    function hideProgress() {
        if (progressEl) progressEl.classList.add('hidden');
    }

    function setStage(stage) {
        if (stage === 'research_start') {
            if (stageResearchEl) stageResearchEl.className = 'progress-stage active';
            if (stageResearchStatus) stageResearchStatus.textContent = 'Processing...';
            addSystemLog('Research started...', 'neural');
        } else if (stage === 'research_done') {
            if (stageResearchEl) stageResearchEl.className = 'progress-stage done';
            if (stageResearchStatus) stageResearchStatus.textContent = 'Complete';
            if (connector1) connector1.style.transform = 'scaleX(1)';
            addSystemLog('Research complete ✓', 'info');
        } else if (stage === 'pattern_start') {
            if (stagePatternEl) stagePatternEl.className = 'progress-stage active';
            if (stagePatternStatus) stagePatternStatus.textContent = 'Processing...';
            addSystemLog('Pattern analysis started...', 'neural');
        } else if (stage === 'pattern_done') {
            if (stagePatternEl) stagePatternEl.className = 'progress-stage done';
            if (stagePatternStatus) stagePatternStatus.textContent = 'Complete';
            if (connector2) connector2.style.transform = 'scaleX(1)';
            addSystemLog('Pattern analysis complete ✓', 'info');
        } else if (stage === 'text_start') {
            if (stageTextEl) stageTextEl.className = 'progress-stage active';
            if (stageTextStatus) stageTextStatus.textContent = 'Processing...';
            addSystemLog('Text generation started...', 'neural');
        } else if (stage === 'text_done') {
            if (stageTextEl) stageTextEl.className = 'progress-stage done';
            if (stageTextStatus) stageTextStatus.textContent = 'Complete';
            if (connector3) connector3.style.transform = 'scaleX(1)';
            addSystemLog('Text generation complete ✓', 'info');
        } else if (stage === 'image_start') {
            if (stageImageEl) stageImageEl.className = 'progress-stage active';
            if (stageImageStatus) stageImageStatus.textContent = 'Processing...';
            addSystemLog('Visual generation started...', 'neural');
        } else if (stage === 'image_done') {
            if (stageImageEl) stageImageEl.className = 'progress-stage done';
            if (stageImageStatus) stageImageStatus.textContent = 'Complete';
            addSystemLog('Visual generation complete ✓', 'info');
        }
    }

    /**
     * Shared SSE-based generation function.
     * Posts data to /api/generate-stream and reads SSE events for real-time progress.
     * @param {Object} data - The payload to send
     * @param {Object} options - { onSuccess, onError, onFinally }
     */
    function generateWithSSE(data, { onSuccess, onError, onFinally }) {
        setOrchestratorStatus(true);
        setGlobalLoading(true);
        startMadScienceLogs();
        
        const hasImage = data.visual_aspect && data.visual_aspect !== 'none';
        showProgress(hasImage);

        // Inject user_id
        data.user_id = window.appUserId || null;

        fetch('/api/generate-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': window.appUserId || 'default'
            },
            body: JSON.stringify(data)
        }).then(response => {
            if (!response.ok) {
                return response.text().then(t => { throw new Error(t || 'Stream request failed'); });
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processChunk() {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        // If no image stage was triggered, mark image as skipped
                        if (!hasImage && stageImageEl && !stageImageEl.classList.contains('done')) {
                            stageImageEl.className = 'progress-stage skipped';
                            if (stageImageStatus) stageImageStatus.textContent = 'Skipped';
                        }
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // keep incomplete line in buffer

                    let currentEvent = null;
                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            currentEvent = line.substring(7).trim();
                        } else if (line.startsWith('data: ') && currentEvent) {
                            const dataStr = line.substring(6);
                            try {
                                const parsed = JSON.parse(dataStr);
                                if (currentEvent === 'stage') {
                                    setStage(parsed.stage);
                                } else if (currentEvent === 'result') {
                                    stopMadScienceLogs();
                                    // Mark remaining stages as done
                                    if (stageTextEl && !stageTextEl.classList.contains('done')) {
                                        stageTextEl.className = 'progress-stage done';
                                        if (stageTextStatus) stageTextStatus.textContent = 'Complete';
                                    }
                                    if (hasImage && stageImageEl && !stageImageEl.classList.contains('done')) {
                                        stageImageEl.className = 'progress-stage done';
                                        if (stageImageStatus) stageImageStatus.textContent = 'Complete';
                                    }
                                    if (!hasImage && stageImageEl && !stageImageEl.classList.contains('skipped')) {
                                        stageImageEl.className = 'progress-stage skipped';
                                        if (stageImageStatus) stageImageStatus.textContent = 'Skipped';
                                    }
                                    if (progressTitle) progressTitle.textContent = 'Generation Complete!';
                                    addSystemLog('Neural generation sequence complete ✓', 'success');
                                    // Brief delay to show completed state before showing results
                                    setTimeout(() => {
                                        hideProgress();
                                        if (onSuccess) onSuccess(parsed);
                                    }, 800);
                                } else if (currentEvent === 'error') {
                                    stopMadScienceLogs();
                                    if (progressTitle) progressTitle.textContent = 'Generation Failed';
                                    // Mark active stages as error
                                    [stageTextEl, stageImageEl].forEach(el => {
                                        if (el && el.classList.contains('active')) {
                                            el.className = 'progress-stage error';
                                        }
                                    });
                                    const errMsg = parsed.error || 'Unknown error';
                                    addSystemLog(`Generation error: ${errMsg}`, 'error');
                                    setTimeout(() => {
                                        hideProgress();
                                        if (document.getElementById('empty-state')) document.getElementById('empty-state').style.display = 'flex';
                                        if (onError) onError(errMsg);
                                    }, 1500);
                                }
                            } catch (parseErr) {
                                console.warn('SSE parse error:', parseErr, dataStr);
                            }
                            currentEvent = null;
                        }
                    }

                    return processChunk();
                });
            }

            return processChunk();
        }).catch(err => {
            stopMadScienceLogs();
            addSystemLog(`Network error: ${err.message}`, 'error');
            hideProgress();
            if (document.getElementById('empty-state')) document.getElementById('empty-state').style.display = 'flex';
            if (onError) onError(err.message);
        }).finally(() => {
            stopMadScienceLogs();
            setOrchestratorStatus(false);
            setGlobalLoading(false);
            if (onFinally) onFinally();
        });
    }

    /**
     * Show progress tracker for non-SSE operations (regenerate flows).
     * @param {string} mode - 'text' | 'image' | 'both' - which stage to activate
     */
    function showSimpleProgress(mode) {
        resetProgress();
        if (progressEl) progressEl.classList.remove('hidden');
        if (document.getElementById('empty-state')) document.getElementById('empty-state').style.display = 'none';
        if (resultsSection) resultsSection.classList.add('hidden');
        if (window.lucide) lucide.createIcons();

        if (mode === 'text' || mode === 'both') {
            if (stageTextEl) {
                stageTextEl.className = 'progress-stage active';
                if (stageTextStatus) stageTextStatus.textContent = 'Processing...';
            }
        }
        if (mode === 'image' || mode === 'both') {
            if (stageImageEl) {
                stageImageEl.className = 'progress-stage active';
                if (stageImageStatus) stageImageStatus.textContent = 'Processing...';
            }
        }
        if (progressTitle) progressTitle.textContent = mode === 'both' ? 'Generating Content...' : (mode === 'text' ? 'Regenerating Text...' : 'Regenerating Image...');
    }

    /**
     * Mark progress stages as complete for non-SSE operations.
     * @param {string} mode - 'text' | 'image' | 'both' | 'error'
     */
    function completeSimpleProgress(mode) {
        if (mode === 'text' || mode === 'both') {
            if (stageTextEl) {
                stageTextEl.className = 'progress-stage done';
                if (stageTextStatus) stageTextStatus.textContent = 'Complete';
            }
        }
        if (mode === 'image' || mode === 'both') {
            if (stageImageEl) {
                stageImageEl.className = 'progress-stage done';
                if (stageImageStatus) stageImageStatus.textContent = 'Complete';
            }
        }
        if (mode === 'error') {
            [stageTextEl, stageImageEl].forEach(el => {
                if (el && el.classList.contains('active')) {
                    el.className = 'progress-stage error';
                }
            });
        }
        if (progressTitle) progressTitle.textContent = mode === 'error' ? 'Generation Failed' : 'Complete!';
        
        setTimeout(() => {
            hideProgress();
        }, mode === 'error' ? 1500 : 800);
    }

    // Purpose Options Definition
    const purposeOptions = [
        { value: 'educational', label: 'Breakdown' },
        { value: 'storytelling', label: 'Announcement' },
        { value: 'authority', label: 'Money Math' },
        { value: 'promotional', label: 'ID-Challenge' }
    ];

    // Visual Style options based on Visual Aspect
    const visualStyleOptions = {
        image: [
            { value: 'minimal', label: 'Minimal' },
            { value: 'infographic', label: 'Infographic' },
            { value: 'ugc', label: 'UGC' },
            { value: 'mockup', label: 'Mockup' }
        ],
        video: [
            { value: 'talking_head', label: 'Talking Head' },
            { value: 'screen_record', label: 'Screen Recording' },
            { value: 'cinematic', label: 'Cinematic B-Roll' },
            { value: 'motion_graphics', label: 'Motion Graphics' }
        ],
        carousel: [
            { value: 'lystical', label: 'Lystical' },
            { value: 'pie', label: 'P.I.E' }
        ]
    };

    // Style Type options — sub-types per visual style (keyed by style value)
    const styleTypeOptions = {
        infographic: [
            { value: 'glassmorphic_venn', label: 'Glassmorphic Venn' },
            { value: 'minimalist_framework', label: 'Minimalist Framework' },
            { value: 'comparison', label: 'Comparison' },
            { value: 'bento_grid', label: 'Bento-Grid' },
            { value: 'whiteboard_style', label: 'Whiteboard' }
        ],
        ugc: [
            { value: 'lifestyle_post', label: 'Lifestyle' },
            { value: 'relatable_meme', label: 'Relatable Meme' },
            { value: 'visual_hook', label: 'Visual Hook' },
            { value: 'informative_ugc', label: 'Informative UGCs' }
        ]
    };

    // Helper: update a Type dropdown based on selected style value
    function updateStyleTypeDropdown(styleValue, typeGroup, typeSelect) {
        const types = styleTypeOptions[styleValue];
        if (types && types.length > 0) {
            typeSelect.innerHTML = '';
            types.forEach(t => {
                const o = document.createElement('option');
                o.value = t.value;
                o.textContent = t.label;
                typeSelect.appendChild(o);
            });
            typeGroup.style.display = 'block';
        } else {
            typeGroup.style.display = 'none';
            typeSelect.innerHTML = '';
        }
    }

    // Custom Select Component
    class CustomSelect {
        constructor(originalSelect) {
            this.originalSelect = originalSelect;
            // Prevent double initialization
            if (this.originalSelect.dataset.customized) return;
            this.originalSelect.dataset.customized = "true";

            this.wrapper = document.createElement('div');
            this.wrapper.className = 'custom-select-container';
            this.originalSelect.style.display = 'none';

            this.originalSelect.parentNode.insertBefore(this.wrapper, this.originalSelect);
            this.wrapper.appendChild(this.originalSelect);

            this.trigger = document.createElement('div');
            this.trigger.className = 'custom-select-trigger';
            this.triggerText = document.createElement('span');
            this.trigger.appendChild(this.triggerText);
            
            const arrow = document.createElement('div');
            arrow.innerHTML = `<svg class="custom-select-arrow" viewBox="0 0 24 24" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
            this.trigger.appendChild(arrow.firstChild);
            
            this.optionsContainer = document.createElement('div');
            this.optionsContainer.className = 'custom-select-options';

            this.wrapper.appendChild(this.trigger);
            this.wrapper.appendChild(this.optionsContainer);

            this.updateOptions();

            this.trigger.addEventListener('click', (e) => {
                const isOpen = this.wrapper.classList.contains('open');
                // Close all other instances first
                document.querySelectorAll('.custom-select-container').forEach(c => c.classList.remove('open'));
                if (!isOpen) this.wrapper.classList.add('open');
                e.stopPropagation();
            });

            this.originalSelect.addEventListener('change', () => this.updateSelection());

            // Listen for dynamic DOM modifications to options (e.g. updateStyleTypeDropdown)
            this.observer = new MutationObserver(() => this.updateOptions());
            this.observer.observe(this.originalSelect, { childList: true });
        }

        updateOptions() {
            this.optionsContainer.innerHTML = '';
            Array.from(this.originalSelect.options).forEach(option => {
                const optEl = document.createElement('div');
                optEl.className = 'custom-select-option';
                optEl.textContent = option.textContent;
                if (option.selected) optEl.classList.add('selected');
                
                optEl.addEventListener('click', (e) => {
                    this.originalSelect.value = option.value;
                    this.originalSelect.dispatchEvent(new Event('change'));
                    this.wrapper.classList.remove('open');
                    e.stopPropagation();
                });
                this.optionsContainer.appendChild(optEl);
            });
            this.updateSelection();
        }

        updateSelection() {
            const selectedOption = this.originalSelect.options[this.originalSelect.selectedIndex];
            if (selectedOption) {
                this.triggerText.textContent = selectedOption.textContent;
                Array.from(this.optionsContainer.children).forEach(child => {
                    if (child.textContent === selectedOption.textContent) child.classList.add('selected');
                    else child.classList.remove('selected');
                });
            } else {
                this.triggerText.textContent = 'Select...';
            }
        }
    }

    // Close options when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.custom-select-container').forEach(c => c.classList.remove('open'));
    });

    // Auto-init all select boxes that exist in sidebar or modals
    const initCustomSelects = () => {
        document.querySelectorAll('.select-wrapper select, select.dark-input').forEach(select => {
            new CustomSelect(select);
        });
    };
    initCustomSelects();

    // Tab Navigation
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Helper to switch right-hand main content views based on tab
    function switchMainView(tabId) {
        const emptyState = document.getElementById('empty-state');
        const resultsContent = document.getElementById('results-content');
        const expansionPanel = document.getElementById('research-expansion-panel');
        const surveillanceView = document.getElementById('surveillance-view');
        const historyView = document.getElementById('history-view');
        
        // Hide all secondary right-panel views
        if(surveillanceView) surveillanceView.classList.add('hidden');
        if(expansionPanel) expansionPanel.classList.add('hidden');
        if(historyView) historyView.classList.add('hidden');
        
        if (tabId === 'dashboard') {
            if(emptyState) emptyState.style.display = 'none';
            if(resultsContent) resultsContent.classList.add('hidden');
            if(surveillanceView) surveillanceView.classList.remove('hidden');
            loadSurveillanceData();
        } else if (tabId === 'generate') {
            const progress = document.getElementById('generation-progress');
            if (resultsContent && !resultsContent.classList.contains('hidden')) {
               // keep results Content showing
            } else if (progress && !progress.classList.contains('hidden')) {
               // keep progress showing
            } else {
               if(emptyState) emptyState.style.display = 'flex';
            }
        } else if (tabId === 'competitor') {
            if(emptyState) emptyState.style.display = 'flex'; 
            if(resultsContent) resultsContent.classList.add('hidden');
        }
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `tab-${tabId}`) {
                    pane.classList.add('active');
                }
            });
            if (tabId === 'history') {
                loadHistory();
            } else {
                switchMainView(tabId);
            }
        });
    });

    // Mode Dropdown Logic (Studio / Win Lab)
    const modeDropdownBtn = document.getElementById('mode-dropdown-btn');
    const modeDropdownPanel = document.getElementById('mode-dropdown-panel');
    const modeDropdownLabel = document.getElementById('mode-dropdown-label');

    const modeIcons = {
        generate: { icon: 'sparkles', label: 'Studio' },
        competitor: { icon: 'trophy', label: 'Win Lab' }
    };

    if (modeDropdownBtn && modeDropdownPanel) {
        modeDropdownBtn.addEventListener('click', (e) => {
            const isOpen = modeDropdownPanel.style.display === 'block';
            modeDropdownPanel.style.display = isOpen ? 'none' : 'block';
            e.stopPropagation();
        });

        document.addEventListener('click', (e) => {
            if (!modeDropdownPanel.contains(e.target) && e.target !== modeDropdownBtn) {
                modeDropdownPanel.style.display = 'none';
            }
        });

        document.querySelectorAll('.mode-option').forEach(opt => {
            opt.addEventListener('click', () => {
                const tabId = opt.dataset.tab;

                // Update dropdown label
                const meta = modeIcons[tabId];
                if (meta && modeDropdownLabel) {
                    modeDropdownLabel.innerHTML = `<i data-lucide="${meta.icon}" style="width:16px;height:16px;color:var(--brand-primary);flex-shrink:0;"></i>${meta.label}`;
                    if (window.lucide) lucide.createIcons();
                }

                // Close panel
                modeDropdownPanel.style.display = 'none';

                // Switch sidebar pane (reuse existing logic)
                tabPanes.forEach(pane => {
                    pane.classList.remove('active');
                    if (pane.id === `tab-${tabId}`) pane.classList.add('active');
                });

                // Remove active from dashboard icon btn, keep dropdown as "active" visually
                tabBtns.forEach(b => b.classList.remove('active'));

                switchMainView(tabId);
            });
        });
    }

    // Sub-tab Navigation (Competitor Hub)
    const subTabBtns = document.querySelectorAll('.sub-tab-btn');
    const subTabPanes = document.querySelectorAll('.sub-tab-pane');

    subTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const subTabId = btn.dataset.subTab;
            subTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            subTabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `sub-tab-${subTabId}`) {
                    pane.classList.add('active');
                }
            });
        });
    });

    // Dynamic URL Logic
    function setupDynamicUrls(btnId, containerId, placeholder) {
        const btn = document.getElementById(btnId);
        const container = document.getElementById(containerId);

        if (!btn || !container) return;

        btn.addEventListener('click', () => {
            const row = document.createElement('div');
            row.className = 'input-row';
            row.innerHTML = `
                <input type="url" name="urls[]" placeholder="${placeholder}" class="dark-input" required>
                <button type="button" class="add-btn remove-btn">-</button>
            `;

            row.querySelector('.remove-btn').addEventListener('click', () => {
                row.remove();
            });

            container.appendChild(row);
        });
    }

    setupDynamicUrls('add-comp-url', 'comp-url-list', 'https://linkedin.com/in/...');
    setupDynamicUrls('add-yt-url', 'yt-url-list', 'https://youtube.com/watch?v=...');

    async function handleResearch(formId, endpoint, dataMapper) {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            setGlobalLoading(true); // Disable immediately
            setOrchestratorStatus(true);

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalHTML = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<div class="loader" style="display:block"></div> Processing...';

            const formData = new FormData(form);
            const data = dataMapper(formData);

            const scriptName = formId.replace('-form', '').replace('-research', '');
            addSystemLog(`Initializing ${scriptName.toUpperCase()} research module...`, 'script');
            startMadScienceLogs(); // Start dramatic logs

            try {
                addSystemLog(`POST → ${endpoint}`, 'api');
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify(data)
                });
                const result = await response.json();

                if (response.ok) {
                    stopMadScienceLogs();
                    addSystemLog(`Pipeline complete ✓ ${result.length || 0} items extracted`, 'success');
                    console.log("Research Result for Main Console:", result);
                    renderResearchInConsole(formId.replace('-research-form', '').replace('-form', ''), result);
                } else {
                    stopMadScienceLogs();
                    addSystemLog(`FATAL: ${result.error || 'Execution failed'}`, 'error');
                    console.error("Research Error: " + (result.error || "Execution failed"));
                }
            } catch (err) {
                stopMadScienceLogs();
                addSystemLog(`Connection dropped: ${err.message}`, 'error');
                console.error("Network error during research:", err);
            } finally {
                stopMadScienceLogs();
                setOrchestratorStatus(false);
                setGlobalLoading(false);
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;
            }
        });
    }


    function renderResearchInConsole(type, items) {
        const expansionPanel = document.getElementById('research-expansion-panel');
        const expansionContent = document.getElementById('expansion-content');
        const expansionTitle = document.getElementById('expansion-title');
        const expansionActions = document.getElementById('expansion-actions');
        const emptyState = document.getElementById('empty-state');
        const resultsContent = document.getElementById('results-content');

        if (!expansionPanel || !expansionContent) {
            console.error("Critical: Research panel elements not found in DOM.");
            return;
        }

        console.log(`Rendering ${type} research with ${items.length} items.`);
        expansionContent.innerHTML = '';
        expansionActions.innerHTML = '';

        const displayItems = Array.isArray(items) ? items : []; // Show all items
        if (displayItems.length === 0) {
            console.warn("No research items found to display.");
            alert("No relevant results found. Try adjusting your parameters or checking the URLs.");
            return;
        }

        // ONLY HIDE OTHER VIEWS AND SHOW PANEL IF WE ACTUALLY HAVE DATA
        if (emptyState) emptyState.style.display = 'none';
        if (resultsContent) resultsContent.classList.add('hidden');
        expansionPanel.classList.remove('hidden');

        try {
            if (type === 'viral') {
                expansionTitle.textContent = "Viral Trends Identified";
                displayItems.forEach((item, index) => {
                    const card = createResearchCard(item, true); // Made selectable too!
                    expansionContent.appendChild(card);
                });
                const repurposedActionGroup = document.createElement('div');
                repurposedActionGroup.className = 'action-group';
                repurposedActionGroup.style.gap = '10px';
                repurposedActionGroup.innerHTML = `
                    <button class="action-btn success-btn" id="repurpose-selected-btn">
                        <i data-lucide="zap" class="btn-icon"></i> Repurpose Selected
                    </button>
                `;
                repurposedActionGroup.querySelector('#repurpose-selected-btn').addEventListener('click', (e) => {
                    handleRepurposeSelection('.yt-card.selected');
                });
                expansionActions.appendChild(repurposedActionGroup);
                if (window.lucide) lucide.createIcons();
            } else if (type === 'competitor') {
                expansionTitle.textContent = "Competitor Research Analysis (Ranked by Engagement)";
                
                // Calculate engagement score
                displayItems.forEach(item => {
                    item.engagement_score = (item.reactions_count || 0) + (item.comments_count || 0);
                });
                
                // Sort by highest engagement
                displayItems.sort((a,b) => b.engagement_score - a.engagement_score);
                
                // Assign Rank-based Tiers
                const tiers = { 'A': [], 'B': [], 'C': [] };
                const totalPosts = displayItems.length;
                displayItems.forEach((item, i) => {
                    const percentile = (i + 1) / totalPosts;
                    if (percentile <= 0.20) item.tier = 'A';
                    else if (percentile <= 0.60) item.tier = 'B';
                    else item.tier = 'C';
                    
                    tiers[item.tier].push(item);
                });
                
                // Keep the expansion content as a block for vertical sections
                expansionContent.style.display = 'block';

                Object.keys(tiers).forEach(tierName => {
                    if (tiers[tierName].length === 0) return;
                    
                    const tierSection = document.createElement('section');
                    tierSection.style.marginBottom = '40px';
                    
                    const tierHeader = document.createElement('h4');
                    let tierSymbolColor = 'var(--text-tertiary)';
                    if (tierName === 'A') tierSymbolColor = 'var(--success)';
                    if (tierName === 'B') tierSymbolColor = '#60A5FA';
                    
                    tierHeader.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${tierSymbolColor}; margin-right:8px;" aria-hidden="true"></span>Tier ${tierName} Posts`;
                    tierHeader.style.fontSize = '1.15rem';
                    tierHeader.style.fontWeight = '600';
                    tierHeader.style.color = 'var(--text-primary)';
                    tierHeader.style.marginBottom = '20px';
                    tierHeader.style.paddingBottom = '8px';
                    tierHeader.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
                    tierHeader.style.display = 'flex';
                    tierHeader.style.alignItems = 'center';
                    tierSection.appendChild(tierHeader);
                    
                    const tierGrid = document.createElement('div');
                    tierGrid.style.display = 'grid';
                    tierGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(360px, 1fr))';
                    tierGrid.style.gap = '20px';
                    tierSection.appendChild(tierGrid);
                    
                    tiers[tierName].forEach((item) => {
                        const card = document.createElement('article');
                        card.className = 'surv-card-3d-wrapper';
                        card.tabIndex = 0;
                        
                        const tierColor = item.tier === 'A' ? 'var(--success)' : (item.tier === 'B' ? 'var(--warning)' : 'var(--text-tertiary)');
                        
                        let frontBg = 'var(--bg-main)';
                        let frontBorder = 'var(--border)';
                        let frontBorderHover = 'var(--border-hover)';
                        
                        if (item.tier === 'A') {
                            frontBg = 'linear-gradient(to bottom right, rgba(249, 199, 79, 0.08), var(--bg-main))';
                            frontBorder = 'rgba(249, 199, 79, 0.15)';
                            frontBorderHover = 'rgba(249, 199, 79, 0.4)';
                        } else if (item.tier === 'B') {
                            frontBg = 'linear-gradient(to bottom right, rgba(96, 165, 250, 0.06), var(--bg-main))';
                            frontBorder = 'rgba(96, 165, 250, 0.15)';
                            frontBorderHover = 'rgba(96, 165, 250, 0.4)';
                        }
                        
                        card.addEventListener('mouseenter', () => {
                            card.style.transform = 'translateY(-4px)';
                            const front = card.querySelector('.surv-card-front');
                            if (front) front.style.borderColor = frontBorderHover;
                        });
                        card.addEventListener('mouseleave', () => {
                            card.style.transform = 'translateY(0)';
                            const front = card.querySelector('.surv-card-front');
                            if (front) front.style.borderColor = frontBorder;
                        });
                        
                        const thumbSrc = item.preview_image_url || item.video_thumbnail || (item.image_urls && item.image_urls.length > 0 ? (Array.isArray(item.image_urls) ? item.image_urls[0] : item.image_urls.split(',')[0]) : '');
                        const postType = item.type || 'text';
                        const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';
                        
                        const showFallback = "this.style.display='none';var n=this.nextElementSibling;if(n)n.classList.remove('hidden');";
                        const thumbHtml = thumbSrc
                            ? `<div class="yt-thumb">
                                    <img src="${thumbSrc}" alt="Thumbnail for post" class="yt-thumb-img" onerror="${showFallback}">
                                    <div class="yt-thumb-fallback hidden" aria-hidden="true"><i data-lucide="${typeIcon}"></i></div>
                               </div>`
                            : `<div class="yt-thumb yt-thumb--empty" aria-hidden="true">
                                    <i data-lucide="${typeIcon}" style="width:36px;height:36px;opacity:0.4;"></i>
                               </div>`;

                        const fullText = item.text || "";
                        const textPreview = fullText.length > 130 ? fullText.substring(0, 130).trim() + '…' : fullText;
                        
                        // Format Date
                        let dateStr = item.time_since_posted || '';
                        if (item.posted_at) {
                            try {
                                const d = new Date(item.posted_at);
                                dateStr = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                            } catch(e) {}
                        }
                        
                        const authorAvatar = item.author_profile_pic ? `<img src="${item.author_profile_pic}" referrerpolicy="no-referrer" crossorigin="anonymous" style="width:24px; height:24px; border-radius:50%; object-fit:cover; border:1px solid rgba(255,255,255,0.1);" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><div style="width:24px; height:24px; border-radius:50%; background:var(--bg-elevated); display:none; align-items:center; justify-content:center;"><i data-lucide="user" style="width:14px; height:14px; opacity:0.5;"></i></div>` : `<div style="width:24px; height:24px; border-radius:50%; background:var(--bg-elevated); display:flex; align-items:center; justify-content:center;"><i data-lucide="user" style="width:14px; height:14px; opacity:0.5;"></i></div>`;
                        
                        card.innerHTML = `
                            <div class="surv-card-inner">
                                <div class="surv-card-front" style="background: ${frontBg}; border-color: ${frontBorder}; transition: border-color 0.2s ease-out; padding: 20px;">
                                    <div style="position: absolute; top: -12px; left: -12px; width: 34px; height: 34px; border-radius: 50%; background: var(--bg-surface); border: 2px solid ${tierColor}; color: ${tierColor}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.95rem; z-index: 10;">
                                        ${item.tier}
                                    </div>
                                    <div class="yt-body" style="flex-grow: 1;">
                                        <div class="yt-body-right" style="padding-left: 2px; display: flex; flex-direction: column; justify-content: flex-start; height: 100%;">
                                            
                                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
                                                ${authorAvatar}
                                                <div style="display:flex; flex-direction:column; line-height:1.2;">
                                                    <span style="font-size:0.85rem; font-weight:600; color:var(--text-primary);">${item.author_name || 'Anonymous'}</span>
                                                    <span style="font-size:0.75rem; color:var(--text-tertiary);">${dateStr}</span>
                                                </div>
                                            </div>

                                            <div class="yt-title" style="text-wrap: balance; font-size: 1.05rem; line-height: 1.4;">${item.title || 'LinkedIn Post'}</div>
                                            <div class="yt-meta" style="margin-top: 6px; font-variant-numeric: tabular-nums;">
                                                <span><i data-lucide="thumbs-up" style="width:12px;height:12px;margin-right:2px;display:inline-block;vertical-align:middle;"></i>${item.engagement_score || 0}</span>
                                                <span class="yt-meta-dot" aria-hidden="true">·</span>
                                                <span class="yt-type-chip"><i data-lucide="${typeIcon}" aria-hidden="true"></i> ${postType}</span>
                                            </div>
                                            <div class="yt-text-preview" style="text-wrap: pretty; flex-grow: 1; margin-top: 12px; font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5;">${textPreview}</div>
                                        </div>
                                    </div>
                                    <div class="yt-actions" style="margin-top: 16px; padding: 0;">
                                        <button class="yt-action-btn expand-surv-btn"><i data-lucide="maximize-2"></i> Expand</button>
                                        ${item.url ? `<a href="${item.url}" target="_blank" class="yt-action-btn"><i data-lucide="external-link"></i> Link</a>` : ''}
                                        <button class="yt-action-btn repurpose-surv-btn" style="color: var(--accent); border-color: rgba(249, 199, 79, 0.3);"><i data-lucide="zap"></i> Repurpose</button>
                                    </div>
                                </div>
                                <div class="surv-card-back">
                                    ${thumbHtml}
                                </div>
                            </div>
                        `;
                        
                        card.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter') card.click();
                        });
                        card.addEventListener('click', () => openFullPostModal(item));
                        card.querySelector('.expand-surv-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            openFullPostModal(item);
                        });
                        card.querySelector('.repurpose-surv-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            // Pass competitor items using 'competitor' sourcetype similar to surveillance logic
                            openRepurposeModal(item.text || item.title || "Selected Post", 'competitor', [item]);
                        });
                        
                        tierGrid.appendChild(card);
                    });
                    
                    tierSection.appendChild(tierGrid);
                    expansionContent.appendChild(tierSection);
                });

                if (window.lucide) lucide.createIcons();
            } else if (type === 'youtube') {
                expansionTitle.textContent = "YouTube Content Analysis";
                displayItems.forEach((item, index) => {
                    const card = createYoutubeCard(item);
                    expansionContent.appendChild(card);
                });
            }
        } catch (err) {
            console.error("Error during research rendering loop:", err);
        }

        console.log(`Successfully appended ${expansionContent.children.length} cards to expansion-content.`);
        if (window.lucide) {
            lucide.createIcons();
        } else {
            console.warn("Lucide not loaded - icons may be missing.");
        }
    }

    // Helper: parse image_urls from backend (array or legacy comma-separated string)
    function _parseImageUrls(raw) {
        if (Array.isArray(raw)) return raw.filter(Boolean);
        if (typeof raw === 'string' && raw.trim()) return raw.split(', ').filter(Boolean);
        return [];
    }

    const historyModalBackdrop = document.getElementById('history-modal-backdrop');

    function createResearchCard(item, selectable) {
        const card = document.createElement('div');
        card.className = 'yt-card';
        card.dataset.fullText = item.text || "";
        card._itemData = item; // Store full item for batch repurpose

        const postType = item.type || 'text';
        const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';

        // Parse image URLs (supports array from new backend or legacy comma string)
        const parsedImageUrls = _parseImageUrls(item.image_urls);
        const imageCount = item.image_count || parsedImageUrls.length;
        const carouselPageCount = item.carousel_page_count || 0;

        // Thumbnail: cascading priority — NO profile pic (that's only for the avatar circle)
        const thumbnailSrc = item.preview_image_url || item.video_thumbnail || (parsedImageUrls.length ? parsedImageUrls[0] : '');

        // onerror: hide broken img, show fallback sibling
        const showFallback = "this.style.display='none';var n=this.nextElementSibling;if(n)n.classList.remove('hidden');";

        // Text preview (first ~150 chars)
        const fullText = item.text || "";
        const textPreview = fullText.length > 150 ? fullText.substring(0, 150).trim() + '…' : fullText;

        // Author info
        const authorName = item.author_name || 'Unknown';
        const authorPic = item.author_profile_pic || '';

        // Engagement
        const reactions = item.reactions_count || 0;
        const comments = item.comments_count || 0;

        // Type-specific overlay badge on thumbnail
        let thumbOverlay = '';
        if (postType === 'video') {
            thumbOverlay = '<span class="yt-thumb-badge yt-thumb-badge--video"><i data-lucide="play"></i></span>';
        } else if (postType === 'carousel') {
            thumbOverlay = `<span class="yt-thumb-badge yt-thumb-badge--carousel"><i data-lucide="layers"></i>${carouselPageCount > 0 ? ' ' + carouselPageCount : ''}</span>`;
        } else if (postType === 'image' && imageCount > 1) {
            thumbOverlay = `<span class="yt-thumb-badge yt-thumb-badge--images"><i data-lucide="images"></i> ${imageCount}</span>`;
        }

        // Thumbnail area: always rendered at fixed aspect ratio
        const thumbHtml = thumbnailSrc
            ? `<div class="yt-thumb" ${item.url ? `onclick="window.open('${item.url}','_blank')"` : ''}>
                    <img src="${thumbnailSrc}" class="card-thumbnail" onerror="${showFallback}">
                    <div class="yt-thumb-fallback hidden"><i data-lucide="${typeIcon}" style="width:36px;height:36px;"></i></div>
                    ${thumbOverlay}
               </div>`
            : `<div class="yt-thumb yt-thumb--empty" ${item.url ? `onclick="window.open('${item.url}','_blank')"` : ''}>
                    <i data-lucide="${typeIcon}" style="width:36px;height:36px;opacity:0.4;"></i>
                    ${thumbOverlay}
               </div>`;

        // Author avatar
        const avatarHtml = authorPic
            ? `<img src="${authorPic}" alt="" class="yt-avatar" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
               <div class="yt-avatar-fallback" style="display:none;">${authorName.charAt(0).toUpperCase()}</div>`
            : `<div class="yt-avatar-fallback">${authorName.charAt(0).toUpperCase()}</div>`;

        card.innerHTML = `
            ${selectable ? '<input type="checkbox" class="yt-checkbox">' : ''}
            ${thumbHtml}
            <div class="yt-body">
                <div class="yt-body-left">
                    ${avatarHtml}
                </div>
                <div class="yt-body-right">
                    <div class="yt-title">${item.title || item.url || 'Post'}</div>
                    <div class="yt-meta">${authorName}</div>
                    <div class="yt-meta"><span>${reactions} reactions</span><span class="yt-meta-dot">·</span><span>${comments} comments</span><span class="yt-meta-dot">·</span><span class="yt-type-chip"><i data-lucide="${typeIcon}"></i> ${postType}</span></div>
                    ${textPreview ? `<div class="yt-text-preview">${textPreview}</div>` : ''}
                </div>
            </div>
            <div class="yt-actions">
                <button class="yt-action-btn expand-btn"><i data-lucide="maximize-2"></i> Expand</button>
                ${item.url ? `<a href="${item.url}" target="_blank" class="yt-action-btn"><i data-lucide="external-link"></i> Open</a>` : ''}
                ${!selectable ? '<button class="yt-action-btn repurpose-btn"><i data-lucide="zap"></i> Use</button>' : ''}
            </div>
        `;

        // Expand logic
        card.querySelector('.expand-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openFullPostModal(item);
        });

        if (selectable) {
            card.addEventListener('click', () => {
                const cb = card.querySelector('.yt-checkbox');
                const selectedCount = document.querySelectorAll('.yt-card.selected').length;
                if (!card.classList.contains('selected') && selectedCount >= 3) return;
                card.classList.toggle('selected');
                if (cb) cb.checked = card.classList.contains('selected');
            });
        } else {
            const repBtn = card.querySelector('.repurpose-btn');
            if (repBtn) repBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openRepurposeModal(item.text || item.title || "Selected Post", 'linkedin');
            });
        }
        return card;
    }

    // Helper for asset downloads (PDF, image, video)
    function _downloadAsset(url, filename) {
        if (!url) return;
        fetch(url)
            .then(response => response.blob())
            .then(blob => {
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = filename || `linkedin-asset-${Date.now()}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(blobUrl);
                document.body.removeChild(a);
            })
            .catch(() => {
                window.open(url, '_blank');
            });
    }

    function openFullPostModal(item) {
        // Cleanup previous carousel keyboard handler
        if (fullPostModal._carouselCleanup) { fullPostModal._carouselCleanup(); fullPostModal._carouselCleanup = null; }

        currentModalItem = item;
        modalPostTitle.textContent = item.title || "Full LinkedIn Post";
        modalPostText.textContent = item.text || "No content available.";

        const meta = item.reactions_count !== undefined ? `${item.reactions_count} reactions` : "";
        const postType = item.type || 'text';
        const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';

        // 1. Handle Visual Preview (Top of Modal)
        const visualContainer = document.getElementById('modal-visual-preview');
        visualContainer.innerHTML = ''; // Clear previous
        visualContainer.className = 'modal-visual-box'; // Reset class

        const parsedModalImages = _parseImageUrls(item.image_urls);
        const thumbSrc = item.preview_image_url || item.video_thumbnail || (parsedModalImages.length ? parsedModalImages[0] : '');
        
        if (postType === 'video') {
            visualContainer.classList.remove('hidden');
            modalTabContent.classList.remove('no-visual');
            if (item.video_url) {
                visualContainer.innerHTML = `
                    <video controls class="modal-video-player" poster="${thumbSrc}">
                        <source src="${item.video_url}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>`;
            } else if (thumbSrc) {
                visualContainer.innerHTML = `
                    <div style="position:relative; width:100%; display:flex; justify-content:center; align-items:center;">
                        <img src="${thumbSrc}" class="modal-visual-content">
                        <div style="position:absolute;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);width:72px;height:72px;border-radius:50%;"><i data-lucide="play" style="width:36px;height:36px;color:#fff;"></i></div>
                    </div>`;
            } else {
                 visualContainer.innerHTML = `
                    <div class="modal-visual-placeholder">
                        <i data-lucide="video-off"></i>
                        <p>Video preview unavailable.<br>Open original post to view.</p>
                        ${item.url ? `<a href="${item.url}" target="_blank" class="action-btn ghost-btn" style="margin-top:10px;">Open on LinkedIn</a>` : ''}
                    </div>`;
            }
        } else if (postType === 'image') {
            // Show ALL images from the post at full width
            const allImages = parsedModalImages.length ? parsedModalImages : (thumbSrc ? [thumbSrc] : []);
            if (allImages.length > 0) {
                visualContainer.classList.remove('hidden');
                modalTabContent.classList.remove('no-visual');
                const imgsHtml = allImages.map((src, i) =>
                    `<img src="${src}" class="modal-visual-content" alt="Post Image ${i+1}" style="background:#fff;">`
                ).join('');
                visualContainer.innerHTML = imgsHtml;
            } else {
                visualContainer.classList.add('hidden');
                modalTabContent.classList.add('no-visual');
            }
        } else if (postType === 'carousel') {
            visualContainer.classList.remove('hidden');
            modalTabContent.classList.remove('no-visual');
            const carouselSlides = Array.isArray(item.carousel_slide_urls) ? item.carousel_slide_urls.filter(Boolean) : [];
            const slideImages = carouselSlides.length ? carouselSlides : (parsedModalImages.length ? parsedModalImages : (item.carousel_preview_url ? [item.carousel_preview_url] : (thumbSrc ? [thumbSrc] : [])));
            if (slideImages.length > 0) {
                let currentSlide = 0;
                const sliderId = 'carousel-slider-' + Date.now();

                const updateSlider = (idx) => {
                    currentSlide = (idx + slideImages.length) % slideImages.length;
                    const slideView = document.querySelector(`#${sliderId} .carousel-slide-view`);
                    const badge = document.querySelector(`#${sliderId} .slide-counter-badge`);
                    if (slideView) slideView.style.transform = `translateX(-${currentSlide * 100}%)`;
                    if (badge) badge.textContent = `${currentSlide + 1} / ${slideImages.length}`;
                };

                visualContainer.innerHTML = `
                    <div class="carousel-slider-container" id="${sliderId}">
                        <div class="carousel-slide-view">
                            ${slideImages.map(src => `<img src="${src}" alt="Slide">`).join('')}
                        </div>
                        <div class="slide-counter-badge">1 / ${slideImages.length}</div>
                        ${slideImages.length > 1 ? `
                            <button class="slide-nav-btn slide-nav-prev"><i data-lucide="chevron-left"></i></button>
                            <button class="slide-nav-btn slide-nav-next"><i data-lucide="chevron-right"></i></button>
                        ` : ''}
                        <div class="carousel-bottom-bar">
                            ${item.document_title ? `<span class="carousel-doc-title">${item.document_title}</span>` : ''}
                            ${item.document_url ? `<button class="download-overlay-btn" id="carousel-download-btn"><i data-lucide="download"></i> Download PDF</button>` : ''}
                        </div>
                    </div>
                `;

                // Wire up prev/next buttons
                const prevBtn = document.querySelector(`#${sliderId} .slide-nav-prev`);
                const nextBtn = document.querySelector(`#${sliderId} .slide-nav-next`);
                if (prevBtn) prevBtn.addEventListener('click', (e) => { e.stopPropagation(); updateSlider(currentSlide - 1); });
                if (nextBtn) nextBtn.addEventListener('click', (e) => { e.stopPropagation(); updateSlider(currentSlide + 1); });

                // Keyboard navigation
                const _carouselKeyHandler = (e) => {
                    if (fullPostModal.classList.contains('hidden')) return;
                    if (e.key === 'ArrowRight') updateSlider(currentSlide + 1);
                    if (e.key === 'ArrowLeft') updateSlider(currentSlide - 1);
                };
                window.addEventListener('keydown', _carouselKeyHandler);
                // Cleanup on modal close
                const _origClose = fullPostModal._carouselCleanup;
                fullPostModal._carouselCleanup = () => { window.removeEventListener('keydown', _carouselKeyHandler); if (_origClose) _origClose(); };

                // Download button
                const dlBtn = document.getElementById('carousel-download-btn');
                if (dlBtn && item.document_url) {
                    dlBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _downloadAsset(item.document_url, `linkedin-carousel-${Date.now()}.pdf`);
                    });
                }
            } else {
                visualContainer.innerHTML = `
                    <div class="modal-visual-placeholder">
                        <i data-lucide="layers"></i>
                        <p>${item.document_title || 'Carousel Document'}</p>
                        ${item.document_url ? `<button class="action-btn success-btn" onclick="_downloadAsset('${item.document_url}', 'linkedin-carousel.pdf')" style="margin-top:10px;"><i data-lucide="download"></i> Download PDF</button>` : ''}
                        ${item.url ? `<a href="${item.url}" target="_blank" class="action-btn ghost-btn" style="margin-top:10px;">View Carousel on LinkedIn</a>` : ''}
                    </div>`;
            }
        } else {
            // Text posts or unknown types - hide the box
            visualContainer.classList.add('hidden');
            modalTabContent.classList.add('no-visual');
        }

        // 2. Meta Stats (Bottom) - Removed the bottom asset section
        modalPostMeta.innerHTML = `
            <div class="stat-item"><i data-lucide="thumbs-up" style="width: 18px; height: 18px;"></i> ${meta}</div>
            <div class="stat-item"><i data-lucide="${typeIcon}" style="width: 18px; height: 18px;"></i> ${postType}</div>
            <div class="stat-item"><i data-lucide="user" style="width: 18px; height: 18px;"></i> ${item.author_name || 'Unknown'}</div>
            ${item.url ? `<a href="${item.url}" target="_blank" style="margin-left:auto; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; color: var(--brand-primary); transition: opacity 0.2s, transform 0.2s;" onmouseover="this.style.opacity='0.8'; this.style.transform='scale(1.1)'" onmouseout="this.style.opacity='1'; this.style.transform='scale(1)'" title="View Original Post"><i data-lucide="external-link" style="width: 22px; height: 22px;"></i></a>` : ''}
        `;
        
        modalPostMeta.style.display = 'flex';
        fullPostModal.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
        
        // Reset tabs to Content view
        if (typeof resetModalTabs === 'function') resetModalTabs();
    }

    function closeFullPostModal() {
        // Cleanup carousel keyboard handler
        if (fullPostModal._carouselCleanup) { fullPostModal._carouselCleanup(); fullPostModal._carouselCleanup = null; }
        fullPostModal.classList.add('hidden');
        fullPostModal.classList.remove('full-view'); // Reset full screen mode
        currentModalItem = null;
    }

    closeModalBtn.addEventListener('click', closeFullPostModal);
    fullPostModal.addEventListener('click', (e) => {
        if (e.target === fullPostModal) closeFullPostModal();
    });

    const repurposeModal = document.getElementById('repurpose-modal');
    const closeRepurposeBtn = document.getElementById('close-repurpose-btn');
    const repurposeSourcePreview = document.getElementById('repurpose-source-preview');
    const repurposeConfirmBtn = document.getElementById('repurpose-confirm-btn');
    const repurposeVisualAspect = document.getElementById('repurpose-visual-aspect');
    const repurposeVisualStyleGroup = document.getElementById('repurpose-visual-style-group');
    const repurposeVisualStyle = document.getElementById('repurpose-visual-style');
    const repurposeStyleTypeGroup = document.getElementById('repurpose-style-type-group');
    const repurposeStyleTypeSelect = document.getElementById('repurpose-style-type');

    let _repurposeItems = []; // Stores the full item(s) being repurposed

    modalRepurposeBtn.addEventListener('click', () => {
        if (currentModalItem) {
            openRepurposeModal(currentModalItem.text, 'linkedin', [currentModalItem]);
            closeFullPostModal();
        }
    });

    let _repurposeSourceType = 'linkedin';

    function openRepurposeModal(text, sourceType, items = []) {
        console.log(`Opening Repurpose Modal for ${sourceType} with ${items.length} item(s)`);
        if (!repurposeModal) {
            console.error("CRITICAL: repurpose-modal element not found in DOM!");
            return alert("UI Error: Repurpose modal missing.");
        }
        _repurposeItems = items || [];
        _repurposeSourceType = sourceType || 'linkedin';
        repurposeSourcePreview.value = text;
        const topicInput = document.getElementById('repurpose-topic-input');
        if (topicInput) topicInput.value = '';

        // Show visual context indicator — aggregate from all items
        const vizIndicator = document.getElementById('repurpose-visual-indicator');
        if (vizIndicator) {
            const mediaItems = _repurposeItems.filter(it => it && (it.type === 'image' || it.type === 'carousel' || it.type === 'video'));
            if (mediaItems.length > 0) {
                const imgCount = mediaItems.filter(it => it.type === 'image').length;
                const carCount = mediaItems.filter(it => it.type === 'carousel').length;
                const vidCount = mediaItems.filter(it => it.type === 'video').length;
                const parts = [];
                if (imgCount) parts.push(`${imgCount} image${imgCount > 1 ? 's' : ''} analyzed`);
                if (carCount) parts.push(`${carCount} carousel${carCount > 1 ? 's' : ''} analyzed`);
                if (vidCount) parts.push(`${vidCount} video${vidCount > 1 ? 's' : ''} transcribed`);
                vizIndicator.innerHTML = `<i data-lucide="eye"></i> ${parts.join(' · ')}`;
                vizIndicator.classList.remove('hidden');
            } else {
                vizIndicator.classList.add('hidden');
            }
        }

        repurposeModal.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
    }

    closeRepurposeBtn.addEventListener('click', () => repurposeModal.classList.add('hidden'));

    repurposeVisualAspect.addEventListener('change', () => {
        const aspect = repurposeVisualAspect.value;
        const aspectRatioGroup = document.getElementById('repurpose-aspect-ratio-group');
        const repurposeColorPaletteGroup = document.getElementById('repurpose-color-palette-group');
        if (aspect === 'none') {
            repurposeVisualStyleGroup.style.display = 'none';
            if (aspectRatioGroup) aspectRatioGroup.style.display = 'none';
            if (repurposeStyleTypeGroup) repurposeStyleTypeGroup.style.display = 'none';
            if (repurposeColorPaletteGroup) repurposeColorPaletteGroup.style.display = 'none';
        } else {
            repurposeVisualStyleGroup.style.display = 'block';
            repurposeVisualStyle.innerHTML = '';
            const options = visualStyleOptions[aspect] || [];
            options.forEach(opt => {
                const o = document.createElement('option');
                o.value = opt.value;
                o.textContent = opt.label;
                repurposeVisualStyle.appendChild(o);
            });
            // Show aspect ratio only for image
            if (aspectRatioGroup) {
                aspectRatioGroup.style.display = aspect === 'image' ? 'grid' : 'none';
            }
            // Show color palette for image
            if (repurposeColorPaletteGroup) {
                repurposeColorPaletteGroup.style.display = aspect === 'image' ? 'block' : 'none';
            }
            // Update Type dropdown for the selected style
            if (repurposeStyleTypeGroup && repurposeStyleTypeSelect) {
                updateStyleTypeDropdown(repurposeVisualStyle.value, repurposeStyleTypeGroup, repurposeStyleTypeSelect);
            }
        }
    });

    // Style change inside repurpose modal → update Type dropdown
    if (repurposeVisualStyle) {
        repurposeVisualStyle.addEventListener('change', () => {
            if (repurposeStyleTypeGroup && repurposeStyleTypeSelect) {
                updateStyleTypeDropdown(repurposeVisualStyle.value, repurposeStyleTypeGroup, repurposeStyleTypeSelect);
            }
        });
    }

    repurposeConfirmBtn.addEventListener('click', async () => {
        const topicInput = document.getElementById('repurpose-topic-input');
        const customTopic = topicInput && topicInput.value.trim() ? topicInput.value.trim() : "";
        const topic = customTopic || `Repurpose: ${repurposeSourcePreview.value.substring(0, 50)}...`;

        // Aggregate visual context from ALL selected items
        const allImageUrls = [];
        const allCarouselSlides = [];
        const allVideoUrls = [];
        let aggregatedPostType = null;
        for (const it of _repurposeItems) {
            if (!it) continue;
            if (it.type === 'image' && it.image_urls) {
                const urls = Array.isArray(it.image_urls) ? it.image_urls : [it.image_urls];
                allImageUrls.push(...urls.filter(u => u));
            }
            if (it.type === 'carousel') {
                const slides = it.carousel_slide_urls || it.image_urls || [];
                const urls = Array.isArray(slides) ? slides : [slides];
                allCarouselSlides.push(...urls.filter(u => u));
            }
            if (it.type === 'video' && it.video_url) {
                allVideoUrls.push(it.video_url);
            }
        }
        // Determine aggregated post type for backend routing
        if (allVideoUrls.length > 0 && (allImageUrls.length > 0 || allCarouselSlides.length > 0)) {
            aggregatedPostType = 'mixed';
        } else if (allVideoUrls.length > 0) {
            aggregatedPostType = 'video';
        } else if (allCarouselSlides.length > 0) {
            aggregatedPostType = 'carousel';
        } else if (allImageUrls.length > 0) {
            aggregatedPostType = 'image';
        }

        // Map frontend source types to valid orchestrator --source values
        // Orchestrator only accepts: topic, news, competitor, blog, youtube, surveillance
        const SOURCE_MAP = {
            'linkedin': 'competitor',
            'mix': 'competitor',
            'competitor': 'competitor',
            'surveillance': 'surveillance',
            'youtube': 'youtube',
            'news': 'news',
            'blog': 'blog',
            'topic': 'topic'
        };
        const mappedSource = SOURCE_MAP[_repurposeSourceType] || 'competitor';

        const data = {
            action: 'develop_post',
            source: mappedSource,
            topic: topic,
            custom_topic: customTopic,
            type: document.getElementById('repurpose-type').value,
            purpose: document.getElementById('repurpose-purpose').value,
            visual_aspect: repurposeVisualAspect.value,
            visual_style: repurposeVisualStyle.value,
            style_type: (repurposeStyleTypeGroup && repurposeStyleTypeGroup.style.display !== 'none' && repurposeStyleTypeSelect) ? repurposeStyleTypeSelect.value : null,
            aspect_ratio: document.getElementById('repurpose-aspect-ratio') ? document.getElementById('repurpose-aspect-ratio').value : '1:1',
            color_palette: document.getElementById('repurpose-color-palette') ? document.getElementById('repurpose-color-palette').value : 'brand',
            source_content: repurposeSourcePreview.value,
            // Aggregated visual context from all selected items
            source_post_type: aggregatedPostType,
            source_image_urls: allImageUrls,
            source_carousel_slides: allCarouselSlides,
            source_video_url: allVideoUrls.length === 1 ? allVideoUrls[0] : null,
            source_video_urls: allVideoUrls.length > 0 ? allVideoUrls : null,
            user_id: window.appUserId || null
        };

        repurposeModal.classList.add('hidden');
        addSystemLog(`Initiating advanced repurpose generation...`, 'neural');

        generateWithSSE(data, {
            onSuccess: (result) => {
                addSystemLog('Repurposed draft ready!', 'success');
                showResults(result, data);
            },
            onError: (errMsg) => {
                addSystemLog(`Drafting failed: ${errMsg}`, 'error');
            },
            onFinally: () => {
                submitBtn.disabled = false;
            }
        });
    });

    // Remove old handleInSituDrafting as it's replaced by the more robust modal flow

    function createYoutubeCard(item) {
        const card = document.createElement('div');
        card.className = 'console-research-card';
        card.style.gridColumn = 'span 2';

        // CRITICAL: Store full text for the repurpose selector
        const fullContent = item.transcript && !item.transcript.includes("No transcript") ? item.transcript : (item.description || "");
        card.dataset.fullText = fullContent;

        const thumbSrc = item.thumbnail || item.thumbnailUrl || '';
        const linksHtml = (item.links || []).map(l => `<a href="${l}" target="_blank" class="resource-link" style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-bottom:4px;">${l}</a>`).join('');

        // Helper for formatting numbers
        const fmt = (n) => {
            if (!n || n === 'N/A') return 'N/A';
            const num = parseInt(String(n).replace(/[^0-9]/g, ''));
            if (isNaN(num)) return n;
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
            return num.toString();
        };

        card.innerHTML = `
            <div class="yt-header" style="display:flex; gap:12px; align-items:flex-start;">
                <div style="position:relative; width: 120px; flex-shrink:0;">
                    <img src="${thumbSrc}" class="card-thumbnail" style="width: 100%; height: auto; aspect-ratio:16/9; object-fit: cover; border-radius: 6px;" onerror="this.src='https://via.placeholder.com/140x80?text=No+Thumbnail'">
                    <a href="${thumbSrc}" target="_blank" class="icon-btn" style="position:absolute; top:4px; right:4px; background:rgba(0,0,0,0.6); color:white; padding:4px; border-radius:4px; width:20px; height:20px; display:flex; align-items:center; justify-content:center; text-decoration:none;" title="Open Thumbnail"><i data-lucide="download" style="width:12px; height:12px;"></i></a>
                </div>
                <div style="flex:1;">
                    <div class="research-card-title" style="font-size:1rem; font-weight:600; margin-bottom:0.25rem; line-height:1.3;">${item.title}</div>
                    <div class="card-stats" style="color:var(--text-secondary); font-size:0.75rem;">
                        <div class="stat-item"><i data-lucide="user" style="width:14px; height:14px;"></i> ${item.channelName || 'Unknown'}</div>
                    </div>
                </div>
            </div>

            <div class="yt-content-tabs" style="margin-top:10px;">
                <div class="yt-tab-nav" style="display:flex; gap:0.5rem; margin-bottom:8px; flex-wrap:wrap;">
                    <button class="yt-sub-tab active" style="padding:6px 12px; font-weight:600; font-size:0.8rem;" data-target="stats">Stats</button>
                    <button class="yt-sub-tab" style="padding:6px 12px; font-weight:600; font-size:0.8rem;" data-target="res">Resources</button>
                    <button class="yt-sub-tab" style="padding:6px 12px; font-weight:600; font-size:0.8rem;" data-target="desc">Description</button>
                    <button class="yt-sub-tab" style="padding:6px 12px; font-weight:600; font-size:0.8rem;" data-target="trans">Transcript</button>
                    <button class="yt-sub-tab" style="padding:6px 12px; font-weight:600; font-size:0.8rem;" data-target="draft">Draft Post</button>
                </div>
                
                <div class="yt-tab-pane-container" style="background:var(--bg-app); padding:10px; border-radius:8px; font-size:0.85rem; max-height:250px; overflow-y:auto; border:1px solid var(--border);">
                    <!-- Stats Grid -->
                    <div class="yt-sub-pane stats">
                         <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
                            <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px; text-align:center;">
                                <div style="font-size:1.1rem; font-weight:700; color:var(--text-primary); margin-bottom:2px;">${fmt(item.viewCount)}</div>
                                <div style="font-size:0.65rem; text-transform:uppercase; letter-spacing:0.5px; opacity:0.6;">Views</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px; text-align:center;">
                                <div style="font-size:1.1rem; font-weight:700; color:var(--text-primary); margin-bottom:2px;">${fmt(item.likes)}</div>
                                <div style="font-size:0.65rem; text-transform:uppercase; letter-spacing:0.5px; opacity:0.6;">Likes</div>
                            </div>
                            <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px; text-align:center;">
                                <div style="font-size:1.1rem; font-weight:700; color:var(--text-primary); margin-bottom:2px;">${fmt(item.commentsCount)}</div>
                                <div style="font-size:0.65rem; text-transform:uppercase; letter-spacing:0.5px; opacity:0.6;">Comments</div>
                            </div>
                             <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:6px; text-align:center;">
                                <div style="font-size:1.1rem; font-weight:700; color:var(--text-primary); margin-bottom:2px;">${fmt(item.subscribers)}</div>
                                <div style="font-size:0.65rem; text-transform:uppercase; letter-spacing:0.5px; opacity:0.6;">Subs</div>
                            </div>
                         </div>
                    </div>

                    <div class="yt-sub-pane res" style="display:none; line-height:1.6;">
                        ${linksHtml || '<span style="opacity:0.5">No external links found in description.</span>'}
                    </div>
                    <div class="yt-sub-pane desc" style="display:none; position:relative;">
                        <button class="icon-btn expand-desc-btn" style="position:absolute; top:0; right:0; padding:4px;" title="Expand Description"><i data-lucide="maximize-2" style="width:16px; height:16px;"></i></button>
                        <div style="white-space:pre-wrap; line-height:1.6; padding-right:30px;">${item.description || 'No description.'}</div>
                    </div>
                    <div class="yt-sub-pane trans" style="display:none; position:relative;">
                        <button class="icon-btn expand-trans-btn" style="position:absolute; top:0; right:0; padding:4px;" title="Expand Transcript"><i data-lucide="maximize-2" style="width:16px; height:16px;"></i></button>
                        <div style="white-space:pre-wrap; font-family:monospace; font-size:0.85rem; line-height:1.6; color:var(--text-secondary); padding-right:30px; max-height: 250px; overflow-y: auto;">${item.transcript || 'No transcript.'}</div>
                    </div>
                    <div class="yt-sub-pane draft" style="display:none; text-align:center; padding:1rem;">
                        <p style="margin-bottom:1rem; font-size:0.9rem;">Repurpose this video into a post:</p>
                        <button class="action-btn success-btn repurpose-yt-btn" style="width:100%"><i data-lucide="zap" style="width:18px; height:18px; vertical-align:middle; margin-right:6px;"></i> Draft Now</button>
                    </div>
                </div>
            </div>
        `;

        // Tab switching logic
        card.querySelectorAll('.yt-sub-tab').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                card.querySelectorAll('.yt-sub-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                card.querySelectorAll('.yt-sub-pane').forEach(p => p.style.display = 'none');
                card.querySelector(`.yt-sub-pane.${btn.dataset.target}`).style.display = 'block';
            });
        });

        // Expand Description Logic
        card.querySelector('.expand-desc-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openFullPostModal({
                title: `Description: ${item.title}`,
                text: item.description || "No description available.",
                type: 'text',
                author_name: item.channelName,
                reactions_count: item.viewCount !== undefined ? `${fmt(item.viewCount)} views` : ''
            });
        });

        // Expand Transcript Logic
        card.querySelector('.expand-trans-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openFullPostModal({
                title: `Transcript: ${item.title}`,
                text: item.transcript || "No transcript available.",
                type: 'text',
                author_name: item.channelName,
                reactions_count: item.viewCount !== undefined ? `${fmt(item.viewCount)} views` : ''
            });
        });

        card.querySelector('.repurpose-yt-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            console.log("Repurpose button clicked on YT card");
            // Intelligent source selection
            let source = item.transcript;
            if (!source || source.includes("No transcript") || source.includes("requires advanced")) {
                source = item.description;
            }
            
            // Create visual item with thumbnail if available
            const visualItems = [];
            if (item.thumbnail && item.thumbnail.startsWith && item.thumbnail.startsWith('http')) {
                visualItems.push({
                    type: 'image',
                    image_urls: [item.thumbnail],
                    title: item.title || 'YouTube Video',
                    author_name: item.channelName || 'Unknown Channel'
                });
            }
            
            console.log('Opening repurpose modal with visual items:', visualItems);
            openRepurposeModal(source || "YouTube Content", 'youtube', visualItems);
        });

        if (window.lucide) lucide.createIcons();
        return card;
    }


    function handleRepurposeSelection(selector, targetType) {
        const selected = document.querySelectorAll(selector);
        if (selected.length === 0) return alert("Please select at least one post.");

        const items = [];
        const combinedText = Array.from(selected).map(c => {
            const text = c.dataset.fullText || (c.querySelector('.yt-title') || c.querySelector('.research-card-title') || {}).textContent || '';
            const typeChip = c.querySelector('.yt-type-chip') || c.querySelector('.type-chip');
            const mediaType = typeChip ? typeChip.textContent.trim() : '';
            // Collect full item data if available
            if (c._itemData) items.push(c._itemData);
            return mediaType && mediaType !== 'text'
                ? `[Content Type: ${mediaType}]\n${text}`
                : text;
        }).join('\n---\n');

        openRepurposeModal(combinedText, 'mix', items);
    }

    // Close Expansion
    const closeExpansionBtn = document.getElementById('close-expansion-btn');
    if (closeExpansionBtn) {
        closeExpansionBtn.addEventListener('click', () => {
            document.getElementById('research-expansion-panel').classList.add('hidden');
            document.getElementById('empty-state').style.display = 'flex';
        });
    }

    handleResearch('viral-research-form', '/api/research/viral', (fd) => ({ topic: fd.get('topic') }));
    handleResearch('competitor-research-form', '/api/research/competitor', (fd) => ({ urls: fd.getAll('urls[]') }));
    handleResearch('youtube-research-form', '/api/research/youtube', (fd) => ({
        urls: fd.getAll('urls[]'),
        deep_search: false // User explicitly requested local scraper
    }));

    // Visual Aspect / Visual Style / Style Type Logic
    const visualAspect = document.getElementById('visual-aspect');
    const visualStyleGroup = document.getElementById('visual-style-group');
    const visualStyle = document.getElementById('visual-style');
    const aspectRatioGroup = document.getElementById('aspect-ratio-group');
    const styleTypeGroup = document.getElementById('style-type-group');
    const styleTypeSelect = document.getElementById('style-type');

    function updateVisualStyle() {
        const aspect = visualAspect.value;
        const purposeSelect = document.getElementById('purpose');
        
        // 1. UPDATE PURPOSE OPTIONS
        // Save current selection (if possible)
        const currentPurpose = purposeSelect.value;
        purposeSelect.innerHTML = ''; // Clear existing
        
        let availablePurposes = purposeOptions;
        if (aspect === 'carousel') {
             // Filter: Only How-to (educational) & Authority
             availablePurposes = purposeOptions.filter(p => ['educational', 'authority'].includes(p.value));
        }

        availablePurposes.forEach(p => {
             const opt = document.createElement('option');
             opt.value = p.value;
             opt.textContent = p.label;
             purposeSelect.appendChild(opt);
        });

        // Restore selection if valid, else pick first
        if (availablePurposes.some(p => p.value === currentPurpose)) {
             purposeSelect.value = currentPurpose;
        } else if (availablePurposes.length > 0) {
             purposeSelect.value = availablePurposes[0].value;
        }


        // 2. COLOR PALETTE - only show for image aspect
        const colorPaletteGroup = document.getElementById('color-palette-group');
        if (colorPaletteGroup) {
            colorPaletteGroup.style.display = (aspect === 'image') ? 'block' : 'none';
        }

        // 2b. REFERENCE IMAGE - only show for image aspect
        const referenceImageGroup = document.getElementById('reference-image-group');
        if (referenceImageGroup) {
            referenceImageGroup.style.display = (aspect === 'image') ? 'block' : 'none';
        }

        // 3. VISUAL STYLE & ASPECT RATIO LOGIC
        if (aspect === 'none') {
            visualStyleGroup.style.display = 'none';
            if (aspectRatioGroup) aspectRatioGroup.style.display = 'none';
            if (styleTypeGroup) styleTypeGroup.style.display = 'none';
        } else {
            visualStyleGroup.style.display = 'block';
            
            // HIDE ASPECT RATIO FOR CAROUSEL (FORCE 4:5)
            if (aspect === 'carousel') {
                if (aspectRatioGroup) aspectRatioGroup.style.display = 'none';
            } else {
                if (aspectRatioGroup) aspectRatioGroup.style.display = 'flex';
            }
            
            visualStyle.innerHTML = '';

            const options = visualStyleOptions[aspect] || [];
            options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;
                visualStyle.appendChild(option);
            });

            // Update Type dropdown based on first style option
            if (styleTypeGroup && styleTypeSelect) {
                updateStyleTypeDropdown(visualStyle.value, styleTypeGroup, styleTypeSelect);
            }
        }
    }

    visualAspect.addEventListener('change', updateVisualStyle);
    if (visualStyle) {
        visualStyle.addEventListener('change', () => {
            if (styleTypeGroup && styleTypeSelect) {
                updateStyleTypeDropdown(visualStyle.value, styleTypeGroup, styleTypeSelect);
            }
        });
    }
    updateVisualStyle(); // Initial state

    // Color Palette Dropdown - render swatch preview on change
    const paletteSwatchMap = {
        brand:     ['#0E0E0E','#F9C74F','#FCF0D5','#F9F9F9','#FFFFFF'],
        executive: ['#0F1A2E','#1B2A4A','#D4A853','#F0F2F5','#FFFFFF'],
        coral:     ['#E8634A','#F4A261','#2D2D2D','#FFF5F0','#FFFFFF'],
        emerald:   ['#0E3B22','#1A5632','#C8A96E','#F5EDE0','#FAF7F2'],
        slate:     ['#1E293B','#334155','#3B82F6','#F1F5F9','#FFFFFF'],
        midnight:  ['#0A0A0A','#1C1C1C','#7C3AED','#EDEDED','#F5F5F5']
    };
    function renderPalettePreviewTo(previewEl, id) {
        if (!previewEl) return;
        const colors = paletteSwatchMap[id] || paletteSwatchMap.brand;
        previewEl.innerHTML = colors.map(c => {
            const needsBorder = ['#FFFFFF','#F9F9F9','#FCF0D5','#F0F2F5','#FFF5F0','#F5EDE0','#FAF7F2','#F1F5F9','#EDEDED','#F5F5F5'].includes(c);
            return `<span class="swatch" style="background:${c};${needsBorder ? 'border:1px solid rgba(255,255,255,0.15);' : ''}"></span>`;
        }).join('');
    }
    // Wire up all palette dropdowns
    function setupPaletteDropdown(selectId, previewId) {
        const sel = document.getElementById(selectId);
        const prev = document.getElementById(previewId);
        if (sel && prev) {
            renderPalettePreviewTo(prev, sel.value);
            sel.addEventListener('change', () => renderPalettePreviewTo(prev, sel.value));
        }
    }
    setupPaletteDropdown('color-palette', 'palette-preview');
    setupPaletteDropdown('repurpose-color-palette', 'repurpose-palette-preview');
    setupPaletteDropdown('regen-tweak-color-palette', 'regen-tweak-palette-preview');
    setupPaletteDropdown('regen-refine-color-palette', 'regen-refine-palette-preview');

    // --- REFERENCE IMAGE UPLOAD LOGIC ---
    // Helper: wire up a checkbox + file upload pair
    function setupReferenceImageUpload(toggleId, uploadId, fileId, btnId, nameId) {
        const toggle = document.getElementById(toggleId);
        const uploadZone = document.getElementById(uploadId);
        const fileInput = document.getElementById(fileId);
        const btn = document.getElementById(btnId);
        const nameSpan = document.getElementById(nameId);
        if (!toggle || !uploadZone || !fileInput) return;

        toggle.addEventListener('change', () => {
            uploadZone.style.display = toggle.checked ? 'flex' : 'none';
            if (!toggle.checked) {
                fileInput.value = '';
                if (nameSpan) nameSpan.textContent = '';
            }
        });
        if (btn) btn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => {
            if (nameSpan) nameSpan.textContent = fileInput.files[0] ? fileInput.files[0].name : '';
        });
    }
    // Main form reference image
    setupReferenceImageUpload('reference-image-toggle', 'reference-image-upload', 'reference-image-file', 'reference-image-btn', 'reference-image-name');
    // Regen modal reference image
    setupReferenceImageUpload('regen-reference-image-toggle', 'regen-reference-image-upload', 'regen-reference-image-file', 'regen-reference-image-btn', 'regen-reference-image-name');

    // Helper: read a file input as base64 data URL
    function readFileAsBase64(fileInput) {
        return new Promise((resolve) => {
            if (!fileInput || !fileInput.files || !fileInput.files[0]) return resolve(null);
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(fileInput.files[0]);
        });
    }

    // Form Submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (resultsPanel) resultsPanel.classList.remove('glow-success'); // Reset

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // Ensure checkboxes or specific selects are mapped if needed
        data.visual_style = document.getElementById('visual-style').value;
        const _styleTypeEl = document.getElementById('style-type');
        if (_styleTypeEl && _styleTypeEl.value && styleTypeGroup && styleTypeGroup.style.display !== 'none') {
            data.style_type = _styleTypeEl.value;
        }

        // Map visual_aspect to type for backend compatibility - REMOVED to fix database type issues
        // if (data.visual_aspect && data.visual_aspect !== 'none') {
        //     data.type = data.visual_aspect;
        // }

        // FORCE CAROUSEL ASPECT RATIO
        if (data.visual_aspect === 'carousel') {
            data.aspect_ratio = '4:5';
        }

        // REFERENCE IMAGE: Read file as base64 if provided
        const refToggle = document.getElementById('reference-image-toggle');
        const refFileInput = document.getElementById('reference-image-file');
        if (refToggle && refToggle.checked && refFileInput && refFileInput.files[0]) {
            data.reference_image = await readFileAsBase64(refFileInput);
        }
        data.user_id = window.appUserId || null;

        console.log('Form Submitted:', data);
        addSystemLog(`Starting content generation for: "${data.topic}"`, 'script');

        submitBtn.disabled = true;
        submitBtn.querySelector('.btn-content').textContent = 'Generating...';

        generateWithSSE(data, {
            onSuccess: (result) => showResults(result, data),
            onError: (errMsg) => console.error('Error: ' + errMsg),
            onFinally: () => {
                submitBtn.disabled = false;
                submitBtn.querySelector('.btn-content').textContent = 'Generate Content';
                if (window.lucide) lucide.createIcons();
            }
        });
    });

    function showResults(result, inputs = {}) {
        currentResult = { ...result, ...inputs };
        console.log("Result to be saved:", currentResult);

        if (resultsPanel) resultsPanel.classList.remove('hidden');

        // Hide empty state
        const emptyState = document.getElementById('empty-state');
        if (emptyState) emptyState.style.display = 'none';

        // Fix: Detect if caption is accidentally valid JSON string
        // History entries store the caption in 'full_caption', while fresh generations return 'caption'
        let displayCaption = result.caption || result.full_caption;
        if (typeof displayCaption === 'string' && displayCaption.trim().startsWith('{')) {
            try {
                // Attempt to parse strictly
                const parsed = JSON.parse(displayCaption);
                if (parsed.caption) displayCaption = parsed.caption;
            } catch (e) {
                // Not JSON, keep original
            }
        }
        captionPreview.textContent = displayCaption;
        resultsSection.classList.remove('hidden');

        approveBtn.disabled = false;
        approveBtn.textContent = 'Approve & Send to Baserow';

        // Logic for Text-Only vs Text+Image Layout
        const assetCol = document.querySelector('.asset-col');
        const regenImageBtn = document.getElementById('regenerate-image-btn');
        const resultsLayout = document.querySelector('.results-layout');
        const imagePromptContainer = document.getElementById('image-prompt-container');
        const assetPreview = document.getElementById('asset-preview');

        // Reset state
        assetPreview.innerHTML = '';
        if (imagePromptContainer) imagePromptContainer.innerHTML = '';

        if (result.asset_url) {
            // SHOW Image Section
            if (assetCol) {
                assetCol.style.display = 'flex';
                assetCol.style.flex = '2';
            }
            const captionCol = document.querySelector('.caption-col');
            if (captionCol) captionCol.style.flex = '3';

            if (regenImageBtn) regenImageBtn.style.display = 'inline-flex';

            const img = document.createElement('img');
            // Ensure unique load by appending timestamp, but respect original URL
            const cacheBuster = new Date().getTime();
            const sep = result.asset_url.includes('?') ? '&' : '?';
            img.src = `${result.asset_url}${sep}t=${cacheBuster}`;
            img.alt = 'Generated Asset Preview';
            img.id = 'preview-image';
            img.style.maxWidth = '100%';
            img.style.borderRadius = '12px';
            img.style.marginTop = '1rem';

            img.onerror = function () {
                console.error("Failed to load image:", img.src);
                const errText = document.createElement('div');
                errText.style.color = 'red';
                errText.textContent = '❌ Failed to load image. Check console.';
                assetPreview.appendChild(errText);
            };

            assetPreview.appendChild(img);

            // Add Expand Button
            const expandBtn = document.createElement('button');
            expandBtn.className = 'expand-image-btn';
            expandBtn.innerHTML = '<i data-lucide="maximize-2" style="width:16px; height:16px;"></i>';
            expandBtn.title = 'View Full Size';
            
            expandBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                // reuse the full post modal logic but simpler? 
                // actually let's just use openFullPostModal but we need to tweak it to support image mode or just make a simple one here.
                // Let's create a quick image modal on the fly or reuse existing structure.
                
                const modalParams = {
                    title: 'Generated Visual Asset',
                    text: '', // No text
                    type: 'image',
                    author_name: 'LinkedIn Autopilot',
                    reactions_count: ''
                };
                
                // Hack: We want to show the IMAGE in the body, not text.
                // Current openFullPostModal only puts text in #modal-post-text.
                // Let's modify openFullPostModal to accept an image or handle it here.
                
                // cleaner to just manipulate the modal directly since we are here.
                const fullPostModal = document.getElementById('full-post-modal');
                const modalPostTitle = document.getElementById('modal-post-title');
                const modalPostText = document.getElementById('modal-post-text');
                
                if (fullPostModal && modalPostText) {
                    modalPostTitle.textContent = "Full Resolution Asset";
                    modalPostText.innerHTML = ''; // Clear text
                    const fullImg = document.createElement('img');
                    fullImg.src = img.src;
                    fullImg.style.maxWidth = '100%';
                    fullImg.style.height = 'auto';
                    fullImg.style.borderRadius = '8px';
                    fullImg.style.boxShadow = '0 4px 20px rgba(0,0,0,0.5)';
                    modalPostText.appendChild(fullImg);
                    
                    // Hide metadata for cleaner view
                    const meta = document.getElementById('modal-post-meta');
                    if(meta) meta.style.display = 'none';
                    
                    fullPostModal.classList.add('full-view'); // Enable full screen mode
                    fullPostModal.classList.remove('hidden');
                }
            });
            
            assetPreview.appendChild(expandBtn);

            if (result.final_image_prompt) {
                // Populate full width prompt container
                if (imagePromptContainer) {
                    const promptLabel = document.createElement('div');
                    promptLabel.textContent = "Image Prompt:";
                    promptLabel.style.fontSize = '0.75rem';
                    promptLabel.style.textTransform = 'uppercase';
                    promptLabel.style.color = '#666';
                    promptLabel.style.marginBottom = '0.4rem';
                    promptLabel.style.marginLeft = '0.2rem';
                    imagePromptContainer.appendChild(promptLabel);

                    const promptText = document.createElement('div');
                    promptText.textContent = result.final_image_prompt;
                    promptText.id = 'prompt-text';
                    imagePromptContainer.appendChild(promptText);
                }
            }
        } else {
            // HIDE Image Section (Text Only Mode)
            if (assetCol) assetCol.style.display = 'none';
            if (regenImageBtn) regenImageBtn.style.display = 'none';

            const captionCol = document.querySelector('.caption-col');
            if (captionCol) captionCol.style.flex = '1';
        }

        // CAROUSEL SLIDE RENDERING
        const carouselSlidesPanel = document.getElementById('carousel-slides-panel');
        const carouselSlidesContainer = document.getElementById('carousel-slides-container');
        
        if (result.type === 'carousel' && result.carousel_layout && result.carousel_layout.slides) {
            // Show carousel panel and populate slides
            if (carouselSlidesPanel) carouselSlidesPanel.classList.remove('hidden');
            if (carouselSlidesContainer) {
                carouselSlidesContainer.innerHTML = ''; // Clear previous
                
                // Use clean_caption if available, otherwise split the caption
                if (result.clean_caption) {
                    captionPreview.textContent = result.clean_caption;
                }
                
                // Render each slide as a separate panel
                result.carousel_layout.slides.forEach((slide, index) => {
                    const slidePanel = document.createElement('div');
                    slidePanel.className = 'carousel-slide-panel';
                    
                    const slideHeader = document.createElement('div');
                    slideHeader.className = 'slide-header';
                    slideHeader.innerHTML = `<strong>Slide ${slide.number}</strong> <span class="slide-type-badge">${slide.type.toUpperCase()}</span>`;
                    
                    const slideContent = document.createElement('div');
                    slideContent.className = 'slide-content';
                    
                    if (slide.title) {
                        const titleEl = document.createElement('div');
                        titleEl.className = 'slide-field';
                        titleEl.innerHTML = `<strong>Title:</strong> ${slide.title}`;
                        slideContent.appendChild(titleEl);
                    }
                    
                   if (slide.subtitle) {
                        const subtitleEl = document.createElement('div');
                        subtitleEl.className = 'slide-field';
                        subtitleEl.innerHTML = `<strong>Subtitle:</strong> ${slide.subtitle}`;
                        slideContent.appendChild(subtitleEl);
                    }
                    
                    if (slide.body) {
                        const bodyEl = document.createElement('div');
                        bodyEl.className = 'slide-field';
                        bodyEl.innerHTML = `<strong>Body:</strong> ${slide.body}`;
                        slideContent.appendChild(bodyEl);
                    }
                    
                    slidePanel.appendChild(slideHeader);
                    slidePanel.appendChild(slideContent);
                    carouselSlidesContainer.appendChild(slidePanel);
                });
            }
        } else {
            // Hide carousel panel for non-carousel types
            if (carouselSlidesPanel) carouselSlidesPanel.classList.add('hidden');
        }

        // Add glow effect to Output Console
        if (resultsPanel) {
            resultsPanel.classList.add('glow-success');

            // Remove glow after animation completes (e.g., 2s) or keep it? User said "light up briefly".
            setTimeout(() => {
                resultsPanel.classList.remove('glow-success');
            }, 2000);
        }

        setTimeout(() => {
            resultsSection.classList.remove('hidden'); // Ensure logic handles hidden class logic correctly
            // resultsSection is actually #results-content which is inside the panel.
            // But we want to show the content.
        }, 10);

        window.scrollTo({
            top: resultsSection.offsetTop - 50,
            behavior: 'smooth'
        });
    }

    // Approve Button
    approveBtn.addEventListener('click', async () => {
        if (!currentResult) return;

        approveBtn.disabled = true;
        approveBtn.textContent = 'Saving...';

        try {
            const response = await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    post_data: currentResult,
                    user_id: window.appUserId || null
                })
            });

            const resData = await response.json();

            if (response.ok) {
                approveBtn.innerHTML = '<i data-lucide="check-circle" style="width:16px; height:16px; vertical-align:middle; margin-right:4px;"></i> Saved';
                if (window.lucide) lucide.createIcons();
            } else {
                console.error('Error saving: ' + (resData.error || 'Unknown error'));
                approveBtn.disabled = false;
                approveBtn.textContent = 'Approve & Send to Baserow';
            }
        } catch (err) {
            console.error('Network error saving post.');
            approveBtn.disabled = false;
            approveBtn.textContent = 'Approve & Send to Baserow';
        }
    });

    // ============================================
    // DRAFTS SYSTEM
    // ============================================

    const saveDraftBtn = document.getElementById('save-draft-btn');
    const repurposeSaveDraftBtn = document.getElementById('repurpose-save-draft-btn');
    const refreshDraftsBtn = document.getElementById('refresh-drafts-btn');
    const draftsGrid = document.getElementById('drafts-grid');
    const draftsEmptyState = document.getElementById('drafts-empty-state');
    const draftsCountBadge = document.getElementById('drafts-count-badge');
    const draftsView = document.getElementById('drafts-view');
    const draftEditModal = document.getElementById('draft-edit-modal');
    const closeDraftEditBtn = document.getElementById('close-draft-edit-btn');
    const draftEditSaveBtn = document.getElementById('draft-edit-save-btn');
    const draftEditDeleteBtn = document.getElementById('draft-edit-delete-btn');
    const draftEditRepurposeBtn = document.getElementById('draft-edit-repurpose-btn');

    let _currentDraftFilter = 'all';

    async function saveDraft(resultData) {
        if (!resultData) return;
        const btn = saveDraftBtn || repurposeSaveDraftBtn;
        const origText = btn ? btn.innerHTML : '';
        if (btn) { btn.disabled = true; btn.innerHTML = '<i data-lucide="loader" class="btn-icon" style="animation: spin 1s linear infinite;"></i> Saving...'; }

        try {
            const res = await fetch('/api/drafts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' },
                body: JSON.stringify({ post_data: resultData, user_id: window.appUserId || null })
            });
            const data = await res.json();
            if (res.ok) {
                if (btn) btn.innerHTML = '<i data-lucide="check" class="btn-icon"></i> Saved!';
                addSystemLog('Draft saved successfully.', 'success');
                setTimeout(() => { if (btn) { btn.innerHTML = origText; btn.disabled = false; } if (window.lucide) lucide.createIcons(); }, 2000);
            } else {
                throw new Error(data.error || 'Failed to save draft');
            }
        } catch (err) {
            console.error('Save draft error:', err);
            addSystemLog(`Draft save failed: ${err.message}`, 'error');
            if (btn) { btn.innerHTML = origText; btn.disabled = false; }
        }
        if (window.lucide) lucide.createIcons();
    }

    if (saveDraftBtn) {
        saveDraftBtn.addEventListener('click', () => {
            if (currentResult) saveDraft(currentResult);
        });
    }

    if (repurposeSaveDraftBtn) {
        repurposeSaveDraftBtn.addEventListener('click', () => {
            const repurposeSourcePreview = document.getElementById('repurpose-source-preview');
            const draftData = {
                caption: repurposeSourcePreview ? repurposeSourcePreview.value : '',
                type: document.getElementById('repurpose-type') ? document.getElementById('repurpose-type').value : 'text',
                purpose: document.getElementById('repurpose-purpose') ? document.getElementById('repurpose-purpose').value : '',
                topic: document.getElementById('repurpose-topic-input') ? document.getElementById('repurpose-topic-input').value : '',
            };
            saveDraft(draftData);
            const repurposeModal = document.getElementById('repurpose-modal');
            if (repurposeModal) repurposeModal.classList.add('hidden');
        });
    }

    async function loadDrafts(statusFilter) {
        if (statusFilter !== undefined) _currentDraftFilter = statusFilter;
        const filter = _currentDraftFilter === 'all' ? '' : `?status=${_currentDraftFilter}`;
        
        try {
            const res = await fetch(`/api/drafts${filter}`, {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const data = await res.json();
            const drafts = data.drafts || [];
            
            if (draftsCountBadge) draftsCountBadge.textContent = drafts.length > 0 ? `(${drafts.length})` : '';
            
            if (!draftsGrid) return;
            draftsGrid.innerHTML = '';

            if (drafts.length === 0) {
                if (draftsEmptyState) draftsEmptyState.style.display = 'block';
                return;
            }
            if (draftsEmptyState) draftsEmptyState.style.display = 'none';

            drafts.forEach(draft => {
                const card = createDraftCard(draft);
                draftsGrid.appendChild(card);
            });

            if (window.lucide) lucide.createIcons();
        } catch (err) {
            console.error('Load drafts error:', err);
            addSystemLog(`Failed to load drafts: ${err.message}`, 'error');
        }
    }

    function createDraftCard(draft) {
        const wrapper = document.createElement('div');
        wrapper.className = 'draft-book-wrapper';
        wrapper.setAttribute('role', 'listitem');

        const caption = draft.caption || '';
        const statusClass = `status-${draft.status || 'draft'}`;
        const statusLabel = (draft.status || 'draft').charAt(0).toUpperCase() + (draft.status || 'draft').slice(1);
        const typeLabel = (draft.type || 'text').toUpperCase();
        const topicLabel = (draft.topic || 'Untitled').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        const captionSafe = caption.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        const dateStr = draft.created_at ? new Date(draft.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';

        const thumbHtml = draft.asset_url
            ? `<img class="draft-book-thumb" src="${draft.asset_url}" alt="Draft visual" onerror="this.style.display='none'">`
            : `<div class="draft-book-thumb-placeholder"><i data-lucide="file-text" style="width:22px;height:22px;color:rgba(249,199,79,0.35);"></i></div>`;

        wrapper.innerHTML = `
            <div class="draft-book">
                <div class="cover">
                    ${thumbHtml}
                    <div class="draft-book-topic">${topicLabel}</div>
                    <div style="display:flex;gap:5px;flex-wrap:wrap;justify-content:center;">
                        <span class="draft-status-badge ${statusClass}">${statusLabel}</span>
                        <span class="draft-type-badge">${typeLabel}</span>
                    </div>
                    <div class="draft-book-date">${dateStr}</div>
                </div>
                <div class="inner">
                    <div class="draft-book-caption">${captionSafe}</div>
                    <div class="draft-book-actions">
                        <button class="draft-edit-book-btn" title="Edit">
                            <i data-lucide="edit-3"></i> Edit
                        </button>
                        <button class="draft-delete-book-btn" title="Delete">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        wrapper.querySelector('.draft-edit-book-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            openDraftEditModal(draft);
        });

        wrapper.querySelector('.draft-delete-book-btn').addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('Delete this draft?')) return;
            await deleteDraft(draft.id);
        });

        wrapper.querySelector('.draft-book').addEventListener('click', () => openDraftEditModal(draft));

        return wrapper;
    }

    function openDraftEditModal(draft) {
        if (!draftEditModal) return;
        document.getElementById('draft-edit-id').value = draft.id;
        document.getElementById('draft-edit-caption').value = draft.caption || '';
        document.getElementById('draft-edit-topic').textContent = draft.topic || 'Untitled';

        const statusBadge = document.getElementById('draft-edit-status-badge');
        if (statusBadge) {
            const s = draft.status || 'draft';
            statusBadge.textContent = s.charAt(0).toUpperCase() + s.slice(1);
            statusBadge.className = `draft-status-badge status-${s}`;
        }

        const imgPreview = document.getElementById('draft-edit-image-preview');
        const imgEl = document.getElementById('draft-edit-image');
        if (draft.asset_url && imgPreview && imgEl) {
            imgEl.src = draft.asset_url;
            imgPreview.style.display = 'block';
        } else if (imgPreview) {
            imgPreview.style.display = 'none';
        }

        draftEditModal.classList.remove('hidden');
        draftEditModal._currentDraft = draft;
        if (window.lucide) lucide.createIcons();
    }

    if (closeDraftEditBtn) {
        closeDraftEditBtn.addEventListener('click', () => draftEditModal.classList.add('hidden'));
    }

    if (draftEditSaveBtn) {
        draftEditSaveBtn.addEventListener('click', async () => {
            const draftId = document.getElementById('draft-edit-id').value;
            const newCaption = document.getElementById('draft-edit-caption').value;
            draftEditSaveBtn.disabled = true;
            draftEditSaveBtn.textContent = 'Saving...';

            try {
                const res = await fetch(`/api/drafts/${draftId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' },
                    body: JSON.stringify({ data: { caption: newCaption } })
                });
                if (res.ok) {
                    addSystemLog('Draft updated.', 'success');
                    draftEditModal.classList.add('hidden');
                    loadDrafts();
                } else {
                    const err = await res.json();
                    addSystemLog(`Draft update failed: ${err.error}`, 'error');
                }
            } catch (err) {
                addSystemLog(`Draft update error: ${err.message}`, 'error');
            }
            draftEditSaveBtn.disabled = false;
            draftEditSaveBtn.innerHTML = '<i data-lucide="check" class="btn-icon"></i> Update Draft';
            if (window.lucide) lucide.createIcons();
        });
    }

    if (draftEditDeleteBtn) {
        draftEditDeleteBtn.addEventListener('click', async () => {
            const draftId = document.getElementById('draft-edit-id').value;
            if (!confirm('Delete this draft permanently?')) return;
            await deleteDraft(draftId);
            draftEditModal.classList.add('hidden');
        });
    }

    if (draftEditRepurposeBtn) {
        draftEditRepurposeBtn.addEventListener('click', () => {
            const draft = draftEditModal._currentDraft;
            if (draft && typeof openRepurposeModal === 'function') {
                openRepurposeModal(draft.caption || '', 'linkedin', [draft.source_data || draft]);
                draftEditModal.classList.add('hidden');
            }
        });
    }

    async function deleteDraft(draftId) {
        try {
            const res = await fetch(`/api/drafts/${draftId}`, {
                method: 'DELETE',
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            if (res.ok) {
                addSystemLog('Draft deleted.', 'success');
                loadDrafts();
            } else {
                addSystemLog('Failed to delete draft.', 'error');
            }
        } catch (err) {
            addSystemLog(`Delete error: ${err.message}`, 'error');
        }
    }

    if (refreshDraftsBtn) {
        refreshDraftsBtn.addEventListener('click', () => loadDrafts());
    }

    // Drafts filter pills
    const filterPills = document.querySelectorAll('.draft-filter-pill');
    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            filterPills.forEach(p => {
                p.style.background = 'transparent';
                p.style.color = 'rgba(255,255,255,0.5)';
                p.style.borderColor = 'rgba(255,255,255,0.1)';
                p.classList.remove('active');
            });
            pill.style.background = 'rgba(249,199,79,0.15)';
            pill.style.color = 'var(--brand-primary)';
            pill.style.borderColor = 'rgba(255,255,255,0.15)';
            pill.classList.add('active');
            loadDrafts(pill.dataset.filter);
        });
    });

    // Wire Drafts sub-tab switching to show/hide drafts view
    const dashboardSubTabBtns = document.querySelectorAll('#tab-dashboard .sub-tab-btn');
    dashboardSubTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.subTab;
            // Toggle sub-tab button active state
            dashboardSubTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Toggle sidebar sub-panes
            document.querySelectorAll('#tab-dashboard .sub-tab-pane').forEach(pane => {
                pane.style.display = 'none';
                pane.classList.remove('active');
            });
            const targetPane = document.getElementById(`sub-tab-${target}`);
            if (targetPane) {
                targetPane.style.display = 'flex';
                targetPane.classList.add('active');
            }
            // Toggle main content views
            const survView = document.getElementById('surveillance-view');
            const dView = document.getElementById('drafts-view');
            if (target === 'drafts') {
                if (survView) survView.classList.add('hidden');
                if (dView) { dView.classList.remove('hidden'); loadDrafts(); }
            } else {
                if (dView) dView.classList.add('hidden');
                if (survView) survView.classList.remove('hidden');
            }
        });
    });

    // ============================================
    // SETTINGS MODAL + BLOTATO CONNECTION
    // ============================================

    const settingsModal = document.getElementById('settings-modal');
    const openSettingsBtn = document.getElementById('open-settings-btn');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const blotatoKeyInput = document.getElementById('settings-blotato-key');
    const saveBlotatoBtn = document.getElementById('settings-save-blotato-btn');
    const testBlotatoBtn = document.getElementById('settings-test-blotato-btn');
    const blotatoStatus = document.getElementById('settings-blotato-status');
    const blotatoAccountDiv = document.getElementById('settings-blotato-account');
    const blotatoAccountName = document.getElementById('settings-blotato-account-name');

    if (openSettingsBtn) {
        openSettingsBtn.addEventListener('click', async () => {
            if (settingsModal) settingsModal.classList.remove('hidden');
            if (window.lucide) lucide.createIcons();
            // Load existing key
            try {
                const res = await fetch('/api/settings', { headers: { 'X-User-ID': window.appUserId || 'default' } });
                const data = await res.json();
                if (blotatoKeyInput && data.blotatoApiKey) {
                    blotatoKeyInput.value = data.blotatoApiKey;
                }
            } catch (e) { /* ignore */ }
        });
    }

    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
    }

    if (saveBlotatoBtn) {
        saveBlotatoBtn.addEventListener('click', async () => {
            const key = blotatoKeyInput ? blotatoKeyInput.value.trim() : '';
            saveBlotatoBtn.disabled = true;
            saveBlotatoBtn.textContent = 'Saving...';
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' },
                    body: JSON.stringify({ blotatoApiKey: key })
                });
                saveBlotatoBtn.textContent = 'Saved!';
                addSystemLog('Blotato API key saved.', 'success');
                setTimeout(() => { saveBlotatoBtn.textContent = 'Save'; saveBlotatoBtn.disabled = false; }, 2000);
            } catch (e) {
                saveBlotatoBtn.textContent = 'Save';
                saveBlotatoBtn.disabled = false;
                addSystemLog('Failed to save Blotato key.', 'error');
            }
        });
    }

    if (testBlotatoBtn) {
        testBlotatoBtn.addEventListener('click', async () => {
            if (blotatoStatus) { blotatoStatus.textContent = 'Testing...'; blotatoStatus.style.color = 'var(--text-tertiary)'; }
            if (blotatoAccountDiv) blotatoAccountDiv.style.display = 'none';
            try {
                const res = await fetch('/api/blotato/accounts', { headers: { 'X-User-ID': window.appUserId || 'default' } });
                const data = await res.json();
                if (data.connected) {
                    if (blotatoStatus) { blotatoStatus.textContent = 'Connected!'; blotatoStatus.style.color = 'var(--success)'; }
                    if (blotatoAccountDiv && data.linkedin) {
                        blotatoAccountDiv.style.display = 'block';
                        if (blotatoAccountName) blotatoAccountName.textContent = `LinkedIn: ${data.linkedin.fullname || 'Connected'}`;
                    }
                    addSystemLog('Blotato connection verified.', 'success');
                } else {
                    if (blotatoStatus) { blotatoStatus.textContent = data.error || 'Connection failed'; blotatoStatus.style.color = 'var(--danger)'; }
                }
            } catch (e) {
                if (blotatoStatus) { blotatoStatus.textContent = 'Connection error'; blotatoStatus.style.color = 'var(--danger)'; }
            }
            if (window.lucide) lucide.createIcons();
        });
    }

    // ============================================
    // DRAFT PUBLISH / SCHEDULE (Blotato)
    // ============================================

    async function publishDraft(draftId, scheduledTime = null, force = false) {
        addSystemLog(`Publishing draft ${draftId.substring(0, 8)}...`, 'neural');
        try {
            const res = await fetch(`/api/drafts/${draftId}/publish`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' },
                body: JSON.stringify({ scheduled_time: scheduledTime, force: force })
            });
            const data = await res.json();

            if (res.status === 422 && data.status === 'blocked') {
                const reason = data.reason === 'quality_gate'
                    ? `Quality gate blocked (${data.quality_score}/${data.threshold}). ${(data.feedback || []).join('; ')}`
                    : `Schedule conflict: ${data.conflict?.reason || 'Unknown'}`;
                addSystemLog(reason, 'error');
                alert(`Publishing blocked:\n${reason}\n\nUse "Force Publish" to override.`);
                return data;
            }

            if (data.status === 'published') {
                addSystemLog(`Post published! ${data.public_url || ''}`, 'success');
            } else if (data.status === 'scheduled') {
                addSystemLog(`Post scheduled via Blotato.`, 'success');
            } else if (data.status === 'error' || data.error) {
                addSystemLog(`Publish failed: ${data.error || data.reason || 'Unknown'}`, 'error');
            }

            loadDrafts();
            return data;
        } catch (err) {
            addSystemLog(`Publish error: ${err.message}`, 'error');
            return { status: 'error', error: err.message };
        }
    }

    // Add Publish Now button to draft edit modal footer (dynamically)
    const draftEditFooter = draftEditModal ? draftEditModal.querySelector('.modal-footer') : null;
    if (draftEditFooter && draftEditSaveBtn) {
        const publishNowBtn = document.createElement('button');
        publishNowBtn.className = 'action-btn success-btn';
        publishNowBtn.style.cssText = 'background: linear-gradient(135deg, #22C55E, #16A34A); border-color: rgba(34,197,94,0.3);';
        publishNowBtn.innerHTML = '<i data-lucide="send" class="btn-icon"></i> Publish Now';
        publishNowBtn.addEventListener('click', async () => {
            const draftId = document.getElementById('draft-edit-id').value;
            if (!confirm('Publish this draft to LinkedIn immediately via Blotato?')) return;
            publishNowBtn.disabled = true;
            publishNowBtn.textContent = 'Publishing...';
            const result = await publishDraft(draftId);
            publishNowBtn.disabled = false;
            publishNowBtn.innerHTML = '<i data-lucide="send" class="btn-icon"></i> Publish Now';
            if (result.status === 'published' || result.status === 'scheduled') {
                draftEditModal.classList.add('hidden');
            }
            if (window.lucide) lucide.createIcons();
        });
        draftEditFooter.appendChild(publishNowBtn);
        if (window.lucide) lucide.createIcons();
    }

    // ============================================
    // REGENERATE CAPTION MODAL LOGIC
    // ============================================

    const regenCaptionModal = document.getElementById('regenerate-caption-modal');
    const closeRegenCaptionBtn = document.getElementById('close-regen-caption-btn');
    const cancelRegenCaptionBtn = document.getElementById('cancel-regen-caption-btn');
    const confirmRegenCaptionBtn = document.getElementById('confirm-regen-caption-btn');
    const regenCaptionInstructions = document.getElementById('regen-caption-instructions');
    const regenCaptionStyle = document.getElementById('regen-caption-style');
    const regenCaptionPreview = document.getElementById('regen-caption-preview');

    function openRegenCaptionModal() {
        if (!currentResult) return;
        regenCaptionInstructions.value = ''; // Reset instructions
        
        // Populate current caption
        if (regenCaptionPreview) {
            regenCaptionPreview.textContent = currentResult.caption || "No caption found.";
        }

        regenCaptionModal.classList.remove('hidden');
    }

    function closeRegenCaptionModal() {
        regenCaptionModal.classList.add('hidden');
    }

    // Event Listeners for Modal
    if (closeRegenCaptionBtn) closeRegenCaptionBtn.addEventListener('click', closeRegenCaptionModal);
    if (cancelRegenCaptionBtn) cancelRegenCaptionBtn.addEventListener('click', closeRegenCaptionModal);

    // Open Modal on Button Click
    regenerateCaptionBtn.addEventListener('click', () => {
         openRegenCaptionModal();
    });

    // Confirm Regeneration
    if (confirmRegenCaptionBtn) {
        confirmRegenCaptionBtn.addEventListener('click', async () => {
             if (!currentResult) return;
             
             closeRegenCaptionModal();

             regenerateCaptionBtn.innerHTML = 'Generating...';
             regenerateCaptionBtn.disabled = true;
             setGlobalLoading(true);
             setOrchestratorStatus(true);

             const instructions = regenCaptionInstructions.value;
             const style = regenCaptionStyle.value || 'minimal';

            // Get context params
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            const topic = data.topic || "Modern AI";
            const purpose = data.purpose || "storytelling";
            const type = data.type || "text";

             try {
                showSimpleProgress('text');
                const response = await fetch('/api/regenerate-caption', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify({ 
                        topic, 
                        purpose, 
                        type, 
                        style,
                        instructions,
                        user_id: window.appUserId || null
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    completeSimpleProgress('text');
                    currentResult.caption = result.caption;
                    captionPreview.textContent = result.caption;
                    // Re-show results section (hidden by showSimpleProgress)
                    if (resultsSection) resultsSection.classList.remove('hidden');
                    if (resultsPanel) resultsPanel.classList.remove('hidden');
                    
                    if (window.lucide) lucide.createIcons();
                } else {
                    completeSimpleProgress('error');
                    console.error('Error: ' + (result.error || 'Failed to regenerate caption'));
                }
             } catch (err) {
                completeSimpleProgress('error');
                console.error(err);
             } finally {
                regenerateCaptionBtn.innerHTML = '<i data-lucide="refresh-cw" class="btn-icon"></i> Regen Text';
                regenerateCaptionBtn.disabled = false;
                setOrchestratorStatus(false);
                setGlobalLoading(false);
                if (window.lucide) lucide.createIcons();
             }
        });
    }

    // Regenerate Image - keeps caption, regenerates image only
    // Image Regeneration Modal Elements
    const regenImageModal = document.getElementById('regenerate-image-modal');
    const closeRegenImageBtn = document.getElementById('close-regen-image-btn');
    const cancelRegenImageBtn = document.getElementById('cancel-regen-image-btn'); // For Refine tab
    const confirmRegenImageBtn = document.getElementById('confirm-regen-image-btn'); // For Refine tab
    const regenImageInstructions = document.getElementById('regen-image-instructions');
    const regenVisualStyle = document.getElementById('regen-visual-style');

    // New Tabs support
    const regenTabBtns = document.querySelectorAll('[data-regen-tab]');
    const regenTabPanes = document.querySelectorAll('.regen-tab-pane');
    
    // Tweak Tab Elements
    const regenTweakPrompt = document.getElementById('regen-tweak-prompt');
    const cancelRegenTweakBtn = document.getElementById('cancel-regen-tweak-btn');
    const confirmRegenTweakBtn = document.getElementById('confirm-regen-tweak-btn');

    // Tab Switching Logic
    regenTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.regenTab;
            
            // Toggle Buttons
            regenTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Toggle Panes
            regenTabPanes.forEach(p => {
                if (p.id === `regen-tab-${target}`) {
                    p.classList.remove('hidden');
                    p.classList.add('active');
                } else {
                    p.classList.add('hidden');
                    p.classList.remove('active');
                }
            });
        });
    });

    let regenOriginalAssetUrl = null;

    function openRegenImageModal() {
        if (!currentResult) return;
        regenOriginalAssetUrl = currentResult.asset_url; // Capture original state
        
        regenImageInstructions.value = ''; // Reset instructions
        
        // Populate Tweak Prompt
        if (regenTweakPrompt) {
            regenTweakPrompt.value = currentResult.final_image_prompt || currentResult.image_prompt || '';
        }
        
        // Populate Aspect Ratios
        const tweakAspectRatio = document.getElementById('regen-tweak-aspect-ratio');
        if (tweakAspectRatio && currentResult.aspect_ratio) {
            tweakAspectRatio.value = currentResult.aspect_ratio;
        }
        const refineAspectRatio = document.getElementById('regen-refine-aspect-ratio');
        if (refineAspectRatio && currentResult.aspect_ratio) {
            refineAspectRatio.value = currentResult.aspect_ratio;
        }

        // Set Preview Image (for Refine tab)
        const mainPreviewImg = document.getElementById('preview-image');
        const modalPreviewImg = document.getElementById('regen-source-preview');
        if (mainPreviewImg && modalPreviewImg) {
            modalPreviewImg.src = mainPreviewImg.src;
        }

        // Set style to current result's style or default
        if (currentResult.visual_style) {
            regenVisualStyle.value = currentResult.visual_style;
        }
        regenImageModal.classList.remove('hidden');
    }

    function closeRegenImageModal() {
        regenImageModal.classList.add('hidden');
    }

    if (closeRegenImageBtn) closeRegenImageBtn.addEventListener('click', closeRegenImageModal);
    if (cancelRegenImageBtn) cancelRegenImageBtn.addEventListener('click', closeRegenImageModal);
    if (cancelRegenTweakBtn) cancelRegenTweakBtn.addEventListener('click', closeRegenImageModal);
    
    // Regenerate Image Button - Opens Modal
    regenerateImageBtn.addEventListener('click', () => {
         openRegenImageModal();
    });

    // Handle Tweak Confirmation (New Text-to-Image Generation)
    if (confirmRegenTweakBtn) {
        confirmRegenTweakBtn.addEventListener('click', async () => {
             if (!currentResult) return;
             closeRegenImageModal();

             regenerateImageBtn.textContent = 'Generating...';
             regenerateImageBtn.disabled = true;
             setGlobalLoading(true);
             setOrchestratorStatus(true);
             
             // Optimistically dim the image
             const img = document.getElementById('preview-image');
             if (img) img.style.opacity = '0.5';

             const newPrompt = regenTweakPrompt.value;
             const aspectRatioEl = document.getElementById('regen-tweak-aspect-ratio');
             const aspectRatio = aspectRatioEl ? aspectRatioEl.value : (currentResult.aspect_ratio || "16:9");

             // Reference image for regen tweak
             const regenRefToggle = document.getElementById('regen-reference-image-toggle');
             const regenRefFile = document.getElementById('regen-reference-image-file');
             let regenRefBase64 = null;
             if (regenRefToggle && regenRefToggle.checked && regenRefFile && regenRefFile.files[0]) {
                 regenRefBase64 = await readFileAsBase64(regenRefFile);
             }

             try {
                showSimpleProgress('image');
                const tweakColorPaletteEl = document.getElementById('regen-tweak-color-palette');
                const tweakPayload = {
                    mode: 'tweak',
                    prompt: newPrompt,
                    aspect_ratio: aspectRatio,
                    color_palette: tweakColorPaletteEl ? tweakColorPaletteEl.value : 'brand',
                    history_entry: {
                        ...currentResult,
                        id: crypto.randomUUID(),
                        timestamp: Date.now(),
                        approved: false
                    },
                    user_id: window.appUserId || null
                };
                if (regenRefBase64) tweakPayload.reference_image = regenRefBase64;

                // Reuse regenerate-image endpoint but with specific flag
                const response = await fetch('/api/regenerate-image', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify(tweakPayload)
                });

                const result = await response.json();
                if (response.ok) {
                    completeSimpleProgress('image');
                    currentResult.asset_url = result.asset_url;
                    currentResult.final_image_prompt = newPrompt; 
                    showResults(currentResult);
                } else {
                    completeSimpleProgress('error');
                     console.error('Error: ' + (result.error || 'Failed to regenerate'));
                     alert('Error: ' + (result.error || 'Failed to regenerate image. Check console for details.'));
                }

             } catch (err) {
                 completeSimpleProgress('error');
                 console.error(err);
                 alert('Error in script: ' + err.message);
             } finally {
                 regenerateImageBtn.innerHTML = '<i data-lucide="image" class="btn-icon"></i> Regen Image';
                 regenerateImageBtn.disabled = false;
                 setGlobalLoading(false);
                 setOrchestratorStatus(false);
                 if (img) img.style.opacity = '1';
             }
        });
    }

    // Confirm Regeneration (Refine / IDM)
    if (confirmRegenImageBtn) {
        confirmRegenImageBtn.addEventListener('click', async () => {
            if (!currentResult) return;
            closeRegenImageModal(); // Close first

            const img = document.getElementById('preview-image');
            if (img) img.style.opacity = '0.3';

            regenerateImageBtn.textContent = 'Generating...';
            regenerateImageBtn.disabled = true;
            setGlobalLoading(true);
            setOrchestratorStatus(true);

            // Capture inputs from modal
            const instructions = regenImageInstructions.value;
            const style = regenVisualStyle.value;
            const aspectRatioEl = document.getElementById('regen-refine-aspect-ratio');
            const aspectRatio = aspectRatioEl ? aspectRatioEl.value : (currentResult.aspect_ratio || "16:9");

            const refineColorPaletteEl = document.getElementById('regen-refine-color-palette');
            const payload = {
                user_id: window.appUserId || null,
                mode: 'refine', // Explicit mode
                caption: currentResult.caption,
                topic: currentResult.topic, // Add topic
                purpose: currentResult.purpose, // Add purpose
                type: currentResult.type, // Add type
                style: style,
                aspect_ratio: aspectRatio,
                color_palette: refineColorPaletteEl ? refineColorPaletteEl.value : 'brand',
                instructions: instructions,
                source_image: regenOriginalAssetUrl || currentResult.asset_url,
                history_entry: {
                    ...currentResult,
                    id: crypto.randomUUID(),
                    timestamp: Date.now(),
                    approved: false
                } 
            };
            
            try {
                showSimpleProgress('image');
                const response = await fetch('/api/regenerate-image', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();

                if (response.ok && result.asset_url) {
                    completeSimpleProgress('image');
                    // Update current result
                    currentResult.asset_url = result.asset_url;
                    currentResult.final_image_prompt = result.final_image_prompt;
                    currentResult.visual_style = style; // Update style if changed

                    // Update image
                    if (img) {
                        img.src = result.asset_url + '?t=' + new Date().getTime();
                        img.onload = () => { img.style.opacity = '1'; };
                        img.onerror = () => { img.style.opacity = '1'; };
                    }
                    // Update prompt text
                    const promptText = document.getElementById('prompt-text');
                    if (promptText && result.final_image_prompt) {
                        promptText.textContent = result.final_image_prompt;
                    }
                } else {
                    completeSimpleProgress('error');
                    console.error("Regeneration Failed:", result.error);
                    alert("Failed to regenerate image: " + (result.error || "Unknown error"));
                    if (img) img.style.opacity = '1';
                }
            } catch (err) {
                completeSimpleProgress('error');
                console.error(err);
                if (img) img.style.opacity = '1';
                alert("Network error during regeneration.");
            } finally {
                regenerateImageBtn.innerHTML = '<i data-lucide="image" class="btn-icon"></i> Regen Image';
                regenerateImageBtn.disabled = false;
                setOrchestratorStatus(false);
                setGlobalLoading(false);
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    // Copy Caption
    document.getElementById('copy-btn').addEventListener('click', () => {
        if (currentResult && currentResult.caption) {
            navigator.clipboard.writeText(currentResult.caption);
            const copyBtn = document.getElementById('copy-btn');
            const originalHTML = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i data-lucide="check"></i> Copied!';
            setTimeout(() => { copyBtn.innerHTML = originalHTML; if (window.lucide) lucide.createIcons(); }, 2000);
        }
    });

    // Toggle URL field visibility based on source
    const sourceSelect = document.getElementById('source');
    const urlGroup = document.getElementById('url-group');

    function updateUrlVisibility() {
        const selected = sourceSelect.value;
        const showUrl = selected !== 'topic' && selected !== 'competitor';
        urlGroup.style.display = showUrl ? 'flex' : 'none';
    }

    sourceSelect.addEventListener('change', updateUrlVisibility);
    updateUrlVisibility();

    // History Modal Toggles
    const viewHistoryBtn = document.getElementById('view-history-btn');
    const closeHistoryBtn = document.getElementById('close-history-btn');
    const historyView = document.getElementById('history-view');
    
    // Clicking backdrop closes modal
    if (historyModalBackdrop) {
        historyModalBackdrop.addEventListener('click', closeHistoryModal);
    }
    
    // Accessibility: Escape key closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && historyView && !historyView.classList.contains('hidden')) {
            closeHistoryModal();
        }
    });

    function openHistoryModal() {
        if (!historyView) return;
        
        // Ensure Backdrop is visible
        if (historyModalBackdrop) {
            historyModalBackdrop.classList.remove('hidden');
            historyModalBackdrop.setAttribute('aria-hidden', 'false');
            setTimeout(() => historyModalBackdrop.classList.add('visible'), 10);
        }
        
        // Show Modal
        historyView.classList.remove('hidden');
        historyView.setAttribute('aria-hidden', 'false');
        setTimeout(() => {
            historyView.classList.add('visible');
            historyView.focus();
        }, 10);
        
        loadHistory();
    }

    function closeHistoryModal() {
        if (!historyView) return;
        
        historyView.classList.remove('visible');
        historyView.setAttribute('aria-hidden', 'true');
        
        if (historyModalBackdrop) {
            historyModalBackdrop.classList.remove('visible');
            historyModalBackdrop.setAttribute('aria-hidden', 'true');
        }
        
        // Wait for CSS transition logic before hiding element display
        setTimeout(() => {
            historyView.classList.add('hidden');
            if (historyModalBackdrop) historyModalBackdrop.classList.add('hidden');
        }, 300);
    }

    if (viewHistoryBtn) {
        viewHistoryBtn.addEventListener('click', () => {
             openHistoryModal();
        });
    }

    if (closeHistoryBtn) {
        closeHistoryBtn.addEventListener('click', () => {
             closeHistoryModal();
        });
    }

    // Function to load and render history table
    async function loadHistory() {
        const historyTableBody = document.getElementById('history-table-body');
        if (!historyTableBody) return;

        try {
            const url = window.appUserId ? `/api/history?userId=${window.appUserId}` : '/api/history';
            const response = await fetch(url, {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const history = await response.json();

            if (history.length === 0) {
                historyTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-tertiary);">No generations found.</td></tr>';
                return;
            }

            historyTableBody.innerHTML = '';

            history.forEach(entry => {
                const tr = document.createElement('tr');

                // Format Status
                const statusClass = entry.approved ? 'status-approved' : 'status-draft';
                const statusText = entry.approved ? 'Approved' : 'Draft';

                // Format Tokens and Cost correctly
                let totalTokens = 0;
                let tokenCost = 0;
                let scrapingCost = 0;
                let hasCostData = false;

                if (entry.costs && Array.isArray(entry.costs) && entry.costs.length > 0) {
                    hasCostData = true;
                    entry.costs.forEach(c => {
                        if (c.service === 'Apify') {
                            scrapingCost += c.cost;
                        } else {
                            tokenCost += c.cost;
                            totalTokens += (c.input_tokens || 0) + (c.output_tokens || 0);
                        }
                    });
                } else if (entry.total_cost !== undefined) {
                     tokenCost = entry.total_cost;
                     hasCostData = true;
                }

                const tokensDisp = totalTokens > 0 ? totalTokens.toLocaleString() : entry.total_tokens ? entry.total_tokens.toLocaleString() : '-';
                const formattedTokenCost = hasCostData || tokenCost > 0 ? '$' + tokenCost.toFixed(4) : entry.total_cost !== undefined ? '$' + Number(entry.total_cost).toFixed(4) : '-';
                const formattedScrapingCost = hasCostData || scrapingCost > 0 ? '$' + scrapingCost.toFixed(4) : '-';

                // Format Date
                const dateText = new Date(entry.timestamp).toLocaleString([], {
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                });

                tr.innerHTML = `
                    <td title="${entry.topic}" style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.9rem; font-weight: 500; color: var(--text-primary); max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${entry.topic}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-secondary); text-transform: capitalize;">${entry.type || 'Text'}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-secondary); text-transform: capitalize;">${entry.purpose || 'N/A'}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-tertiary);">${dateText}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-secondary); tabular-nums;">${tokensDisp}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-secondary); font-family: monospace;">${formattedTokenCost}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border); font-size: 0.85rem; color: var(--text-secondary); font-family: monospace;">${formattedScrapingCost}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid var(--border);"><span class="status-chip ${statusClass}" style="display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">${statusText}</span></td>
                `;

                tr.style.cursor = 'pointer';
                tr.style.transition = 'background-color 0.2s ease';
                tr.addEventListener('mouseenter', () => tr.style.backgroundColor = 'rgba(255, 255, 255, 0.03)');
                tr.addEventListener('mouseleave', () => tr.style.backgroundColor = 'transparent');

                tr.addEventListener('click', () => {
                    if (['viral_research', 'competitor_research', 'youtube_research'].includes(entry.type)) {
                        const typeMap = {
                            'viral_research': 'viral',
                            'competitor_research': 'competitor',
                            'youtube_research': 'youtube'
                        };
                        renderResearchInConsole(typeMap[entry.type], entry.full_results || []);
                    } else {
                        showResults(entry, entry);
                    }
                    closeHistoryModal();
                });

                historyTableBody.appendChild(tr);
            });

            if (window.lucide) lucide.createIcons();
        } catch (err) {
            console.error("Error loading history:", err);
            historyTableBody.innerHTML = '<tr><td colspan="8" style="color: var(--danger); text-align: center; padding: 2rem;">Error loading history.</td></tr>';
        }
    }

    // ============================================
    // SURVEILLANCE TAB LOGIC
    // ============================================
    const refreshSurvBtn = document.getElementById('refresh-surveillance-btn');
    const survBoard = document.getElementById('surveillance-analytics-board');
    const survList = document.getElementById('surveillance-post-list');
    const survSortFilter = document.getElementById('surv-sort-filter');
    const survTimeRangeSelect = document.getElementById('surveillance-time-range');
    const survActiveDesc = document.getElementById('surveillance-active-desc');
    const survTimeLabel = document.getElementById('surv-time-label');
    let _survCachedPosts = []; // cached for re-sorting without re-fetching

    async function loadSurveillanceData() {
        if (!survBoard || !survList) return;
        
        try {
            survBoard.innerHTML = '<div style="color: var(--text-tertiary); font-size: 0.9rem;">Loading analytics...</div>';
            survList.innerHTML = '';
            
            // Re-fetch tracked profile URL in case it changed elsewhere
            const settingsRes = await fetch('/api/settings', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const settingsData = await settingsRes.json();
            const urlInput = document.getElementById('tracked-profile-url');
            if (urlInput && settingsData.trackedProfileUrl) {
                 urlInput.value = settingsData.trackedProfileUrl;
            }

            const res = await fetch('/api/surveillance/data', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const data = await res.json();
            
            if (!data || !data.posts || data.posts.length === 0) {
                survBoard.innerHTML = '<div style="color: var(--warning); font-size: 0.9rem;">No surveillance data available yet. Scraper may still be running.</div>';
                return;
            }
            
            const summary = data.summary || {};
            
            // Calculate ring fills appropriately for 7 days span
            const maxPosts = 30; 
            const postAngle = Math.max(Math.min(((summary.total_posts || 0) / maxPosts) * 360, 360), 5);
            
            const maxEng = 5000;
            const engAngle = Math.max(Math.min(((summary.total_engagements || 0) / maxEng) * 360, 360), 5);
            
            const maxAvg = 200;
            const avgAngle = Math.max(Math.min(((summary.avg_engagement || 0) / maxAvg) * 360, 360), 5);

            // Render Analytics Board
            survBoard.innerHTML = `
                <div style="display: flex; gap: 20px; margin-bottom: 30px;" role="group" aria-label="Key Performance Indicators">
                    <div class="stat-widget">
                        <button class="stat-pill" tabindex="0" aria-label="Total Posts: ${summary.total_posts || 0}">
                            <div class="ring-wrap">
                                <div class="ring" style="background-image: conic-gradient(var(--brand-primary) 0deg, var(--brand-primary) ${postAngle}deg, rgba(255, 255, 255, 0.08) ${postAngle}deg 360deg);">
                                    <div class="core">
                                        <i data-lucide="file-text" style="width:20px;height:20px;"></i>
                                    </div>
                                </div>
                            </div>
                            <div class="meta">
                                <div class="value">${summary.total_posts || 0}</div>
                                <div class="label">Total Posts</div>
                            </div>
                            <div class="ground-shadow"></div>
                        </button>
                        <button class="stat-pill" tabindex="0" aria-label="Total Engagements: ${summary.total_engagements || 0}">
                            <div class="ring-wrap">
                                <div class="ring" style="background-image: conic-gradient(var(--brand-primary) 0deg, var(--brand-primary) ${engAngle}deg, rgba(255, 255, 255, 0.08) ${engAngle}deg 360deg);">
                                    <div class="core">
                                        <i data-lucide="zap" style="width:20px;height:20px;"></i>
                                    </div>
                                </div>
                            </div>
                            <div class="meta">
                                <div class="value">${summary.total_engagements || 0}</div>
                                <div class="label">Total Engagements</div>
                            </div>
                            <div class="ground-shadow"></div>
                        </button>
                        <button class="stat-pill" tabindex="0" aria-label="Average Engagement: ${summary.avg_engagement || 0}">
                            <div class="ring-wrap">
                                <div class="ring" style="background-image: conic-gradient(var(--brand-primary) 0deg, var(--brand-primary) ${avgAngle}deg, rgba(255, 255, 255, 0.08) ${avgAngle}deg 360deg);">
                                    <div class="core">
                                        <i data-lucide="activity" style="width:20px;height:20px;"></i>
                                    </div>
                                </div>
                            </div>
                            <div class="meta">
                                <div class="value">${summary.avg_engagement || 0}</div>
                                <div class="label">Avg Engagement</div>
                            </div>
                            <div class="ground-shadow"></div>
                        </button>
                    </div>
                    
                    <div id="surv-top-performer" style="flex: 1; background: var(--bg-surface); padding: 24px 28px; border-radius: 48px; border: 1px solid var(--border); box-shadow: 0 8px 18px rgba(0, 0, 0, 0.03); position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: center; transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out; cursor: pointer;" tabindex="0" role="button" aria-label="Top Performer: ${summary.best_post_title ? summary.best_post_title.replace(/"/g, '&quot;') : 'None'}">
                        <div style="position: absolute; top: -15px; right: -15px; opacity: 0.04; pointer-events: none;"><i data-lucide="zap" style="width: 100px; height: 100px; color: var(--brand-primary);" aria-hidden="true"></i></div>
                        <div style="font-size: 1.15rem; font-weight: 600; color: var(--text-primary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-wrap: balance; margin-bottom: 8px; line-height: 1.4;" title="${summary.best_post_title ? summary.best_post_title.replace(/"/g, '&quot;') : 'N/A'}">${summary.best_post_title || 'N/A'}</div>
                        <div style="font-size: 0.85rem; color: var(--brand-primary); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; opacity: 0.9; display: flex; align-items: center; gap: 4px;">Top Performer <i data-lucide="arrow-right" style="width: 14px; height: 14px;" aria-hidden="true"></i></div>
                    </div>
                </div>
            `;
            
            // Add click listener and hover effect to top performer
            const topPerformerEl = document.getElementById('surv-top-performer');
            if (topPerformerEl && summary.best_post_title) {
                const bestPost = data.posts.find(p => p.title === summary.best_post_title) || data.posts[0];
                topPerformerEl.addEventListener('mouseenter', () => {
                    topPerformerEl.style.transform = 'translateY(-2px)';
                    topPerformerEl.style.backgroundColor = 'rgba(249, 199, 79, 0.05)';
                });
                topPerformerEl.addEventListener('mouseleave', () => {
                    topPerformerEl.style.transform = 'translateY(0)';
                    topPerformerEl.style.backgroundColor = 'var(--bg-surface)';
                });
                topPerformerEl.addEventListener('click', () => {
                    if (bestPost) openFullPostModal(bestPost);
                });
                topPerformerEl.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') topPerformerEl.click();
                });
            }

                    // Assign tiers then render
                    data.posts.forEach(p => {
                        p.engagement_score = (p.reactions_count || 0) + (p.comments_count || 0);
                    });
                    // Sort by engagement to assign tier ranks
                    const engSorted = [...data.posts].sort((a,b) => b.engagement_score - a.engagement_score);
                    const totalPosts = engSorted.length;
                    engSorted.forEach((post, i) => {
                        const percentile = (i + 1) / totalPosts;
                        if (percentile <= 0.20) post.tier = 'A';
                        else if (percentile <= 0.60) post.tier = 'B';
                        else post.tier = 'C';
                    });

                    _survCachedPosts = data.posts;
                    renderSurvPosts(); // delegated rendering

            if (window.lucide) lucide.createIcons();
            
        } catch (e) {
            console.error("Failed to load surveillance data:", e);
            survBoard.innerHTML = '<div style="color: var(--danger); font-size: 0.9rem;">Failed to load data.</div>';
        }
    }

    // ── Sort + Filter + Render Posts ────────────────────────────
    function renderSurvPosts() {
        if (!survList || _survCachedPosts.length === 0) return;
        survList.innerHTML = '';

        // Helper to safely parse dates OR time_since strings into milliseconds
        function getPostTime(p) {
            if (p.posted_at) {
                const t = new Date(p.posted_at).getTime();
                if (!isNaN(t)) return t;
            }
            const tsStr = (p.time_since_posted || "").toLowerCase();
            const match = tsStr.match(/(\d+)\s*([a-z]+)/);
            if (match) {
                const num = parseInt(match[1]);
                const unit = match[2];
                const now = new Date().getTime();
                const dayMs = 86400000;
                
                if (unit.startsWith('s')) return now - (num * 1000);
                if (unit.startsWith('m') && !unit.startsWith('mo')) return now - (num * 60000);
                if (unit.startsWith('h')) return now - (num * 3600000);
                if (unit.startsWith('d')) return now - (num * dayMs);
                if (unit.startsWith('w')) return now - (num * dayMs * 7);
                if (unit.startsWith('mo')) return now - (num * dayMs * 30);
                if (unit.startsWith('y')) return now - (num * dayMs * 365);
            }
            return 0;
        }

        // --- 1. Date filter from time range dropdown ---
        const days = survTimeRangeSelect ? parseInt(survTimeRangeSelect.value) || 30 : 30;
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        cutoff.setHours(0, 0, 0, 0);
        const cutoffMs = cutoff.getTime();

        const filtered = _survCachedPosts.filter(p => {
            const pTime = getPostTime(p);
            if (pTime === 0) return true; // Keep if truly unknown
            return pTime >= cutoffMs;
        });

        if (filtered.length === 0) {
            survList.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-tertiary);font-size:0.95rem;">
                No posts found within the last <strong style="color:var(--brand-primary);">${days} days</strong>.<br>
                <span style="font-size:0.82rem;">Try a wider range or click <strong>Refresh Data</strong> to re-scrape.</span>
            </div>`;
            return;
        }

        // --- 2. Sort ---
        const sortMode = survSortFilter ? survSortFilter.value : 'engagement-desc';
        const sorted = [...filtered];

        switch (sortMode) {
            case 'date-desc':
                sorted.sort((a, b) => getPostTime(b) - getPostTime(a));
                break;
            case 'date-asc':
                sorted.sort((a, b) => getPostTime(a) - getPostTime(b));
                break;
            case 'likes-desc':
                sorted.sort((a, b) => (b.reactions_count || 0) - (a.reactions_count || 0));
                break;
            case 'comments-desc':
                sorted.sort((a, b) => (b.comments_count || 0) - (a.comments_count || 0));
                break;
            case 'engagement-desc':
            default:
                sorted.sort((a, b) => (b.engagement_score || 0) - (a.engagement_score || 0));
                break;
        }

        // --- 3. Render: tier-grouped for engagement sort, flat list otherwise ---
        const useTiers = (sortMode === 'engagement-desc');
        survList.style.display = 'block';

        // Helper: build a single post card
        function _buildSurvCard(item) {
                            const card = document.createElement('article');
                            card.className = 'surv-card-3d-wrapper';
                            card.role = 'listitem';
                            card.tabIndex = 0;
                            card.setAttribute('aria-label', `Post titled ${item.title ? item.title.replace(/"/g, '') : 'Untitled'} with ${item.engagement_score || 0} engagements. Tier ${item.tier || 'C'}`);

                            const tierColor = item.tier === 'A' ? 'var(--success)' : (item.tier === 'B' ? '#60A5FA' : 'var(--text-tertiary)');
                            
                            let frontBg = 'var(--bg-main)';
                            let frontBorder = 'var(--border)';
                            let frontBorderHover = 'var(--border-hover)';
                            
                            if (item.tier === 'A') {
                                frontBg = 'linear-gradient(to bottom right, rgba(249, 199, 79, 0.08), var(--bg-main))';
                                frontBorder = 'rgba(249, 199, 79, 0.15)';
                                frontBorderHover = 'rgba(249, 199, 79, 0.4)';
                            } else if (item.tier === 'B') {
                                frontBg = 'linear-gradient(to bottom right, rgba(96, 165, 250, 0.06), var(--bg-main))';
                                frontBorder = 'rgba(96, 165, 250, 0.15)';
                                frontBorderHover = 'rgba(96, 165, 250, 0.4)';
                            }
                            
                            card.addEventListener('mouseenter', () => {
                                card.style.transform = 'translateY(-4px)';
                                const front = card.querySelector('.surv-card-front');
                                if (front) front.style.borderColor = frontBorderHover;
                            });
                            card.addEventListener('mouseleave', () => {
                                card.style.transform = 'translateY(0)';
                                const front = card.querySelector('.surv-card-front');
                                if (front) front.style.borderColor = frontBorder;
                            });
                            
                            const parsedImgUrls = _parseImageUrls(item.image_urls);
                            const thumbSrc = item.preview_image_url || item.video_thumbnail || (parsedImgUrls.length ? parsedImgUrls[0] : (item.carousel_preview_url || ''));
                            const postType = item.type || 'text';
                            const typeIcon = { poll: 'bar-chart-2', carousel: 'layers', image: 'image', video: 'video', text: 'file-text' }[postType] || 'file-text';
                            
                            const showFallback = "this.style.display='none';var n=this.nextElementSibling;if(n)n.classList.remove('hidden');";
                            const thumbHtml = thumbSrc
                                ? `<div class="yt-thumb">
                                        <img src="${thumbSrc}" alt="" class="yt-thumb-img" onerror="${showFallback}">
                                        <div class="yt-thumb-fallback hidden" aria-hidden="true"><i data-lucide="${typeIcon}"></i></div>
                                   </div>`
                                : `<div class="yt-thumb yt-thumb--empty" aria-hidden="true">
                                        <i data-lucide="${typeIcon}" style="width:36px;height:36px;opacity:0.4;"></i>
                                   </div>`;

                            const fullText = item.text || "";
                            const textPreview = fullText.length > 130 ? fullText.substring(0, 130).trim() + '…' : fullText;
                            
                            let dateStr = item.time_since_posted || '';
                            if (item.posted_at) {
                                try {
                                    const d = new Date(item.posted_at);
                                    dateStr = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                                } catch(e) {}
                            }
                            
                            const authorAvatar = item.author_profile_pic ? `<img src="${item.author_profile_pic}" referrerpolicy="no-referrer" crossorigin="anonymous" style="width:24px; height:24px; border-radius:50%; object-fit:cover; border:1px solid rgba(255,255,255,0.1);" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><div style="width:24px; height:24px; border-radius:50%; background:var(--bg-elevated); display:none; align-items:center; justify-content:center;"><i data-lucide="user" style="width:14px; height:14px; opacity:0.5;"></i></div>` : `<div style="width:24px; height:24px; border-radius:50%; background:var(--bg-elevated); display:flex; align-items:center; justify-content:center;"><i data-lucide="user" style="width:14px; height:14px; opacity:0.5;"></i></div>`;
                            
                            card.innerHTML = `
                                <div class="surv-card-inner">
                                    <div class="surv-card-front" style="background: ${frontBg}; border-color: ${frontBorder}; transition: border-color 0.2s ease-out; padding: 20px;">
                                        <div style="position: absolute; top: -12px; left: -12px; width: 34px; height: 34px; border-radius: 50%; background: var(--bg-surface); border: 2px solid ${tierColor}; color: ${tierColor}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.95rem; z-index: 10;" aria-hidden="true">
                                            ${item.tier}
                                        </div>
                                        <div class="yt-body" style="flex-grow: 1;">
                                            <div class="yt-body-right" style="padding-left: 2px; display: flex; flex-direction: column; justify-content: flex-start; height: 100%;">
                                                
                                                <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
                                                    ${authorAvatar}
                                                    <div style="display:flex; flex-direction:column; line-height:1.2;">
                                                        <span style="font-size:0.85rem; font-weight:600; color:var(--text-primary);">${item.author_name || 'Anonymous'}</span>
                                                        <span style="font-size:0.75rem; color:var(--text-tertiary);">${dateStr}</span>
                                                    </div>
                                                </div>

                                                <h3 class="yt-title" style="text-wrap: balance; font-size: 1.05rem; line-height: 1.4; margin:0;">${item.title || 'LinkedIn Post'}</h3>
                                                <div class="yt-meta" style="margin-top: 6px; font-variant-numeric: tabular-nums;">
                                                    <span><i data-lucide="thumbs-up" style="width:12px;height:12px;margin-right:2px;display:inline-block;vertical-align:middle;"></i>${item.engagement_score || 0}</span>
                                                    <span class="yt-meta-dot" aria-hidden="true">·</span>
                                                    <span class="yt-type-chip"><i data-lucide="${typeIcon}" aria-hidden="true"></i> ${postType}</span>
                                                </div>
                                                <div class="yt-text-preview" style="text-wrap: pretty; flex-grow: 1; margin-top: 12px; font-size: 0.9rem; color: var(--text-secondary); line-height: 1.5;">${textPreview}</div>
                                            </div>
                                        </div>
                                        <div class="yt-actions" style="margin-top: 16px; padding: 0;">
                                            <button class="yt-action-btn expand-surv-btn" aria-label="Expand post details"><i data-lucide="maximize-2"></i> Expand</button>
                                            ${item.url ? `<a href="${item.url}" target="_blank" class="yt-action-btn" aria-label="Open original post in new tab"><i data-lucide="external-link"></i> Link</a>` : ''}
                                            <button class="yt-action-btn repurpose-surv-btn" style="color: var(--accent); border-color: rgba(249, 199, 79, 0.3);" aria-label="Repurpose this post"><i data-lucide="zap"></i> Repurpose</button>
                                        </div>
                                    </div>
                                    <div class="surv-card-back" aria-hidden="true">
                                        ${thumbHtml}
                                    </div>
                                </div>
                            `;
                    
                    card.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter') card.click();
                    });
                    card.addEventListener('click', () => openFullPostModal(item));
                    card.querySelector('.expand-surv-btn').addEventListener('click', (e) => {
                        e.stopPropagation();
                        openFullPostModal(item);
                    });
                    card.querySelector('.repurpose-surv-btn').addEventListener('click', (e) => {
                        e.stopPropagation();
                        openRepurposeModal(item.text || item.title || "Selected Post", 'surveillance', [item]);
                    });
                    return card;
        }

        if (useTiers) {
            // Engagement sort: group by tier
            const tiers = { 'A': [], 'B': [], 'C': [] };
            sorted.forEach(p => tiers[p.tier || 'C'].push(p));

            Object.keys(tiers).forEach(tierName => {
                if (tiers[tierName].length === 0) return;
                const tierSection = document.createElement('section');
                tierSection.style.marginBottom = '40px';
                tierSection.setAttribute('aria-labelledby', `tier-${tierName}-header`);
                
                const tierHeader = document.createElement('h4');
                tierHeader.id = `tier-${tierName}-header`;
                let tierSymbolColor = 'var(--text-tertiary)';
                if (tierName === 'A') tierSymbolColor = 'var(--success)';
                if (tierName === 'B') tierSymbolColor = '#60A5FA';
                
                tierHeader.innerHTML = `<span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${tierSymbolColor}; margin-right:8px;" aria-hidden="true"></span>Tier ${tierName} Posts`;
                tierHeader.style.fontSize = '1.15rem';
                tierHeader.style.fontWeight = '600';
                tierHeader.style.color = 'var(--text-primary)';
                tierHeader.style.marginBottom = '20px';
                tierHeader.style.paddingBottom = '8px';
                tierHeader.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
                tierHeader.style.display = 'flex';
                tierHeader.style.alignItems = 'center';
                tierSection.appendChild(tierHeader);
                
                const tierGrid = document.createElement('div');
                tierGrid.style.display = 'grid';
                tierGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(360px, 1fr))';
                tierGrid.style.gap = '20px';
                tierGrid.role = 'list';
                tierSection.appendChild(tierGrid);
                
                tiers[tierName].forEach(item => tierGrid.appendChild(_buildSurvCard(item)));
                survList.appendChild(tierSection);
            });
        } else {
            // Non-engagement sort: flat list respecting sort order
            const flatGrid = document.createElement('div');
            flatGrid.style.display = 'grid';
            flatGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(360px, 1fr))';
            flatGrid.style.gap = '20px';
            flatGrid.role = 'list';
            sorted.forEach(item => flatGrid.appendChild(_buildSurvCard(item)));
            survList.appendChild(flatGrid);
        }
            
            if (window.lucide) lucide.createIcons();
    }

    // Wire sort dropdown
    if (survSortFilter) {
        survSortFilter.addEventListener('change', () => {
            renderSurvPosts();
        });
    }

    // Time Range Dropdown Logic (declarations moved above with other surv vars)

    function updateSurvTimeLabels() {
        const days = survTimeRangeSelect ? survTimeRangeSelect.value : '30';
        if (survActiveDesc) survActiveDesc.textContent = `Monitoring your LinkedIn profile performance over the last ${days} days.`;
        if (survTimeLabel) survTimeLabel.textContent = `(Past ${days} Days)`;
    }
    if (survTimeRangeSelect) {
        survTimeRangeSelect.addEventListener('change', () => {
            updateSurvTimeLabels();
            renderSurvPosts(); // instantly filter posts by new date range
        });
    }

    if (refreshSurvBtn) {
        refreshSurvBtn.addEventListener('click', async () => {
            const icon = refreshSurvBtn.querySelector('i');
            if (icon) icon.classList.add('spin');
            const days = survTimeRangeSelect ? parseInt(survTimeRangeSelect.value) : 30;
            
            try {
                await fetch('/api/surveillance/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify({ days: days })
                });
                addSystemLog(`Surveillance refresh requested (${days} days)`, 'info');
                // Auto-reload data after 5 seconds to show any cached/intermediate results
                setTimeout(loadSurveillanceData, 5000);
            } catch (e) {
                console.error(e);
            } finally {
                if (icon) setTimeout(() => icon.classList.remove('spin'), 1000);
            }
        });
    }

    // ═══════════════════════════════════════════════════════
    // POST CRM & TABS — Phase 2
    // ═══════════════════════════════════════════════════════

    const modalTabBtns = document.querySelectorAll('.modal-tab-btn');
    const modalTabContent = document.getElementById('modal-tab-content');
    const modalTabCrm = document.getElementById('modal-tab-crm');

    window.resetModalTabs = function() {
        modalTabBtns.forEach(btn => {
            if (btn.dataset.target === 'modal-tab-content') {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
            // Remove the inline styles so CSS can take over
            btn.style.background = '';
            btn.style.border = '';
            btn.style.color = '';
        });
        if (modalTabContent) modalTabContent.classList.remove('hidden');
        if (modalTabCrm) modalTabCrm.classList.add('hidden');
    };

    modalTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            
            modalTabBtns.forEach(b => {
                if (b === btn) {
                    b.classList.add('active');
                } else {
                    b.classList.remove('active');
                }
                // Clear inline styles to let CSS take over
                b.style.background = '';
                b.style.border = '';
                b.style.color = '';
            });
            
            if (modalTabContent) modalTabContent.classList.add('hidden');
            if (modalTabCrm) modalTabCrm.classList.add('hidden');
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.remove('hidden');
        });
    });

    const modalScanLeadsBtn = document.getElementById('modal-scan-leads-btn');
    const modalLeadScanLoading = document.getElementById('modal-lead-scan-loading');
    const modalLeadEmptyState = document.getElementById('modal-lead-empty-state');
    const modalLeadTableContainer = document.getElementById('modal-lead-table-container');
    const modalLeadTableBody = document.getElementById('modal-lead-table-body');

    if (modalScanLeadsBtn) {
        modalScanLeadsBtn.addEventListener('click', async () => {
            if (!currentModalItem || !currentModalItem.url) {
                addSystemLog('Error: No valid post URL found to scan.', 'error');
                return;
            }
            
            // UI Loading State
            modalScanLeadsBtn.disabled = true;
            modalScanLeadsBtn.innerHTML = '<i data-lucide="loader-2" style="width:16px;height:16px;animation:spin 1s linear infinite;"></i> Scanning...'; if (window.lucide) lucide.createIcons();
            if (modalLeadEmptyState) modalLeadEmptyState.style.display = 'none';
            if (modalLeadTableContainer) modalLeadTableContainer.classList.add('hidden');
            if (modalLeadScanLoading) modalLeadScanLoading.classList.remove('hidden');
            
            addSystemLog(`Initiating targeted CRM scan for selected post...`, 'info');
            
            try {
                // Ensure we add the Firebase UID to requests
                const reqHeaders = { 
                    'Content-Type': 'application/json',
                    'X-User-ID': window.appUserId || 'default'
                };
                
                const res = await fetch('/api/run-lead-scan', {
                    method: 'POST',
                    headers: reqHeaders,
                    body: JSON.stringify({ post_urls: [currentModalItem.url] })
                });
                
                if (res.ok) {
                    addSystemLog('Targeted lead scan initiated — polling mechanism started...', 'info');
                    
                    let attempts = 0;
                    const MAX_ATTEMPTS = 40; // ~120s max at 3s intervals
                    
                    const pollTimer = setInterval(async () => {
                        attempts++;
                        try {
                            const pRes = await fetch('/api/leads/data', { headers: reqHeaders });
                            if (!pRes.ok) return; // Silent retry
                            const data = await pRes.json();
                            
                            // Check if this data payload matches our scanning URL and has a terminal status
                            const isMyScan = data.summary && 
                                             data.summary.scanned_urls && 
                                             data.summary.scanned_urls.includes(currentModalItem.url);
                                             
                            if (isMyScan && (data.status === 'completed' || data.status === 'error' || data.summary.status === 'error')) {
                                clearInterval(pollTimer);
                                
                                // Reset UI
                                if (modalLeadScanLoading) modalLeadScanLoading.classList.add('hidden');
                                modalScanLeadsBtn.disabled = false;
                                modalScanLeadsBtn.innerHTML = '<i data-lucide="scan" style="width:16px;height:16px;margin-right:6px;display:inline-block;vertical-align:middle;"></i> Rescan Post';
                                
                                if (data.status === 'completed' || !data.error) {
                                    const leads = data.leads || [];
                                    addSystemLog(`Lead scan complete for post: ${leads.length} leads found ✓`, 'success');
                                    
                                    if (leads.length === 0) {
                                        if (modalLeadEmptyState) modalLeadEmptyState.style.display = 'flex';
                                    } else {
                                        if (modalLeadTableContainer) modalLeadTableContainer.classList.remove('hidden');
                                        if (modalLeadTableBody) {
                                            modalLeadTableBody.innerHTML = leads.map(lead => {
                                                const picHtml = lead.profile_picture
                                                    ? `<img src="${lead.profile_picture}" class="crm-avatar" alt="${lead.name}" referrerpolicy="no-referrer">`
                                                    : `<div class="crm-avatar-fallback">${(lead.name || '?')[0].toUpperCase()}</div>`;

                                                const tierClass = `tier-${(lead.tier || 'C').toLowerCase()}`;
                                                const tierLabel = lead.tier || 'C';

                                                const reactionEmojis = { 'LIKE': '👍 Like', 'EMPATHY': '❤️ Love', 'INTEREST': '🤔 Curious', 'PRAISE': '👏 Praise', 'ENTERTAINMENT': '😄 Funny', 'APPRECIATION': '🙏 Support', 'COMMENT': '💬 Comment' };
                                                const rtRaw = lead.reactionType || 'LIKE';
                                                let reactionLabel = reactionEmojis[rtRaw.toUpperCase()] || rtRaw;
                                                
                                                if (!lead.reactionType && lead.comment_excerpt && lead.comment_excerpt.startsWith('Reaction: ')) {
                                                    reactionLabel = reactionEmojis[lead.comment_excerpt.replace('Reaction: ', '').toUpperCase()] || lead.comment_excerpt.replace('Reaction: ', '');
                                                }

                                                const hasComment = (lead.interaction_type === 'comment' || lead.interaction_type === 'reaction+comment') && lead.text && lead.text.trim().length > 0;
                                                const commentHtml = hasComment
                                                    ? `<div class="crm-comment-preview" title="${lead.text.replace(/"/g, '&quot;')}">${lead.text}</div>`
                                                    : `<span class="crm-no-comment">No comment</span>`;

                                                return `
                                                    <tr class="crm-row">
                                                        <td>
                                                            <div class="crm-avatar-wrapper">
                                                                ${picHtml}
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div class="crm-lead-identity">
                                                                <div class="crm-lead-info">
                                                                    ${lead.profile_url ? `<a href="${lead.profile_url}" target="_blank" class="crm-lead-name">${lead.name}</a>` : `<span class="crm-lead-name">${lead.name}</span>`}
                                                                    <span class="crm-lead-headline" title="${lead.headline || ''}">${lead.headline || 'LinkedIn Member'}</span>
                                                                </div>
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div class="crm-stats-cell">
                                                                <span class="crm-tier-badge ${tierClass}">${tierLabel}</span>
                                                                <span class="crm-score-label">Score: ${lead.score !== undefined ? lead.score : '—'}</span>
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div class="crm-activity-pill">${reactionLabel}</div>
                                                        </td>
                                                        <td>
                                                            ${commentHtml}
                                                        </td>
                                                    </tr>
                                                `;
                                            }).join('');
                                        }
                                    }
                                } else {
                                    addSystemLog(`Lead scan completed with errors: ${data.message || data.error}`, 'error');
                                    if (modalLeadEmptyState) modalLeadEmptyState.style.display = 'flex';
                                }
                                if (window.lucide) lucide.createIcons();
                            } else if (attempts >= MAX_ATTEMPTS) {
                                clearInterval(pollTimer);
                                addSystemLog('Lead scan timed out.', 'error');
                                modalScanLeadsBtn.disabled = false;
                                modalScanLeadsBtn.innerHTML = '<i data-lucide="scan" style="width:16px;height:16px;margin-right:6px;display:inline-block;vertical-align:middle;"></i> Fetch Leads';
                                if (modalLeadScanLoading) modalLeadScanLoading.classList.add('hidden');
                                if (modalLeadEmptyState) modalLeadEmptyState.style.display = 'flex';
                                if (window.lucide) lucide.createIcons();
                            }
                        } catch(pollErr) {
                            console.warn("Polling error:", pollErr);
                        }
                    }, 3000);

                } else {
                    throw new Error(`Server error ${res.status}`);
                }
            } catch(e) {
                addSystemLog(`Lead scan request failed: ${e.message}`, 'error');
                modalScanLeadsBtn.disabled = false;
                modalScanLeadsBtn.innerHTML = '<i data-lucide="scan" style="width:16px;height:16px;margin-right:6px;display:inline-block;vertical-align:middle;"></i> Fetch Leads';
                if (modalLeadScanLoading) modalLeadScanLoading.classList.add('hidden');
                if (modalLeadEmptyState) modalLeadEmptyState.style.display = 'flex';
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    // Call on load and on tab switch
    // Note: Tab switch is handled by switchMainView now!
    // Initialize Dashboard data if active on load
    if (document.querySelector('.tab-btn[data-tab="dashboard\"]')?.classList.contains('active')) {
        switchMainView('dashboard');
    }
    
});
