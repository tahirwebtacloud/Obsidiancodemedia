// CRM Hub JavaScript Module
// Professional data-table UI + per-prospect draft persistence

document.addEventListener('DOMContentLoaded', () => {
    const crmRefreshBtn = document.getElementById('crm-refresh-btn');
    const crmLoading = document.getElementById('crm-loading');
    const crmEmpty = document.getElementById('crm-empty');
    const crmContactsList = document.getElementById('crm-contacts-list');
    const crmStats = document.getElementById('crm-stats');

    const crmStatTotal = document.getElementById('crm-stat-total');
    const crmStatWarm = document.getElementById('crm-stat-warm');
    const crmStatHot = document.getElementById('crm-stat-hot');

    let currentFilter = 'all';
    let currentMinWarmth = 0;
    let currentSearchQuery = '';
    let allContacts = [];
    let contactsLoadInFlight = false;
    let crmAutoRefreshInterval = null;
    let linkedinProcessingStatus = null;
    let isGenerating = false;    // blocks auto-refresh while LLM is running
    let activeDraftModal = null;  // prevents modal stacking

    const CRM_AUTO_REFRESH_MS = 15000;
    const PAGE_SIZE = 50;
    let currentPage = 1;
    const hasCoreElements = !!(crmLoading && crmEmpty && crmContactsList && crmStats && crmRefreshBtn);

    const tagColors = {
        hot:      { bg: 'rgba(239,68,68,0.16)', color: '#ef4444' },
        warm:     { bg: 'rgba(34,197,94,0.16)', color: '#22c55e' },
        cold:     { bg: 'rgba(148,163,184,0.2)', color: '#94a3b8' },
        ghosted:  { bg: 'rgba(107,114,128,0.2)', color: '#9ca3af' },
        client:   { bg: 'rgba(var(--brand-primary-rgb),0.18)', color: 'var(--brand-primary)' },
        prospect: { bg: 'rgba(168,85,247,0.16)', color: '#c084fc' },
        // Legacy compat
        warm_lead: { bg: 'rgba(34,197,94,0.16)', color: '#22c55e' },
        cold_pitch: { bg: 'rgba(148,163,184,0.2)', color: '#94a3b8' },
        prospect_no_dm: { bg: 'rgba(168,85,247,0.16)', color: '#c084fc' },
        referrer: { bg: 'rgba(59,130,246,0.16)', color: '#60a5fa' },
        dead: { bg: 'rgba(107,114,128,0.2)', color: '#9ca3af' },
        unanalyzed: { bg: 'rgba(251,191,36,0.16)', color: '#fbbf24' },
    };

    const tagLabels = {
        hot: 'Hot',
        warm: 'Warm',
        cold: 'Cold',
        ghosted: 'Ghosted',
        client: 'Client',
        prospect: 'Prospect',
        warm_lead: 'Warm Lead',
        cold_pitch: 'Cold Pitch',
        prospect_no_dm: 'Prospect',
        referrer: 'Referrer',
        dead: 'Dead',
        unanalyzed: 'Pending',
    };

    function isCRMTabActive() {
        return document.getElementById('tab-crm-hub')?.classList.contains('active');
    }

    function stopCRMAutoRefresh() {
        if (crmAutoRefreshInterval) {
            clearInterval(crmAutoRefreshInterval);
            crmAutoRefreshInterval = null;
        }
    }

    function startCRMAutoRefresh() {
        if (crmAutoRefreshInterval) return;

        crmAutoRefreshInterval = setInterval(() => {
            if (!isCRMTabActive() || isGenerating) return;
            loadContacts({ silent: true });
        }, CRM_AUTO_REFRESH_MS);
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function truncate(text, maxLen = 100) {
        const clean = String(text || '').trim();
        if (!clean) return '';
        return clean.length > maxLen ? `${clean.slice(0, maxLen - 3)}...` : clean;
    }

    function formatDate(value) {
        if (!value) return '-';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return String(value);
        return d.toLocaleDateString();
    }

    function getDraftMessage(contact) {
        return String(
            contact?.draft_message ||
            contact?.metadata?.draft_message ||
            ''
        );
    }

    function patchContact(contactId, patch = {}) {
        allContacts = allContacts.map(contact => {
            if (contact.id !== contactId) return contact;
            return { ...contact, ...patch };
        });
    }

    function getFilteredContacts() {
        let filtered = [...allContacts];

        if (currentFilter !== 'all') {
            filtered = filtered.filter(c => (c.tag || c.behavioral_tag) === currentFilter);
        }

        filtered = filtered.filter(c => Number(c.score || c.warmth_score || 0) >= currentMinWarmth);

        if (currentSearchQuery) {
            const q = currentSearchQuery.toLowerCase();
            filtered = filtered.filter(c => {
                const name = (c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || '').toLowerCase();
                const role = (c.title || c.position || '').toLowerCase();
                const comp = (c.company || '').toLowerCase();
                return name.includes(q) || role.includes(q) || comp.includes(q);
            });
        }

        filtered.sort((a, b) => Number(b.score || b.warmth_score || 0) - Number(a.score || a.warmth_score || 0));
        return filtered;
    }

    function renderContacts() {
        if (!crmContactsList) return;

        // Always make sure the container is visible before rendering
        crmContactsList.style.display = 'block';

        const filtered = getFilteredContacts();
        if (filtered.length === 0) {
            crmContactsList.innerHTML = '<p class="crm-table-empty">No contacts match current filters</p>';
            return;
        }

        // Pagination: compute page slice
        const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;
        const startIdx = (currentPage - 1) * PAGE_SIZE;
        const pageSlice = filtered.slice(startIdx, startIdx + PAGE_SIZE);

        const rows = pageSlice.map((contact) => {
            const tag = contact.tag || contact.behavioral_tag || 'prospect';
            const colors = tagColors[tag] || tagColors.prospect;
            const label = tagLabels[tag] || tag;
            const warmth = Number(contact.score || contact.warmth_score || 0);
            const messageCount = Number(contact.message_count || 0);

            // Build full name from first_name + last_name if full_name not present
            const fullName = contact.full_name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || 'Unknown';

            // Intent points from new schema, fallback to legacy fields
            const intentPts = Array.isArray(contact.intent_points) ? contact.intent_points : [];
            const reasonSummary = truncate(
                intentPts.join('; ') || contact.reason_summary || contact.summary || contact.intent_summary, 130
            ) || 'No intent captured';
            const evidenceTooltip = intentPts.length
                ? intentPts.map(e => `\u2022 ${e}`).join('\n')
                : (contact.intent_summary || '');
            const intentSummary = reasonSummary;
            const draftPreview = truncate(getDraftMessage(contact), 120) || 'No draft yet';
            // title field in new schema (was 'position' in old schema)
            const role = contact.title || contact.position || '';
            const company = contact.company || '';
            const lastMessageDate = formatDate(contact.connected_on || contact.last_message_date);
            const draftUpdatedAt = contact.updated_at ? formatDate(contact.updated_at) : '-';

            return `
                <tr>
                    <td>
                        <div class="crm-cell-name">${escapeHtml(fullName)}</div>
                        <div class="crm-cell-sub">${escapeHtml(contact.linkedin_url || contact.linkedin_conversation_id || '')}</div>
                    </td>
                    <td>${escapeHtml(role || '-')}</td>
                    <td>${escapeHtml(company || '-')}</td>
                    <td><span class="crm-tag-pill" style="background:${colors.bg};color:${colors.color};">${escapeHtml(label)}</span></td>
                    <td><span class="crm-warmth-badge">${warmth}</span></td>
                    <td>${messageCount}</td>
                    <td>${escapeHtml(lastMessageDate)}</td>
                    <td class="crm-intent-cell" title="${escapeHtml(evidenceTooltip)}">
                        <div>${escapeHtml(intentSummary)}</div>
                    </td>
                    <td>
                        <div class="crm-draft-preview" title="${escapeHtml(getDraftMessage(contact))}">${escapeHtml(draftPreview)}</div>
                        <div class="crm-cell-sub">${escapeHtml(draftUpdatedAt)}</div>
                    </td>
                    <td>
                        <div class="crm-table-actions">
                            <button class="crm-inline-btn crm-inline-btn-generate crm-generate-btn" data-contact-id="${contact.id}">Generate</button>
                            <button class="crm-inline-btn crm-inline-btn-secondary crm-edit-draft-btn" data-contact-id="${contact.id}">Draft</button>
                            <button class="crm-inline-btn crm-inline-btn-danger crm-delete-btn" data-contact-id="${contact.id}">Delete</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        crmContactsList.innerHTML = `
            <div class="crm-table-shell">
                <table class="crm-data-table">
                    <thead>
                        <tr>
                            <th>Prospect</th>
                            <th>Title</th>
                            <th>Company</th>
                            <th>Tag</th>
                            <th>Warmth</th>
                            <th>Msgs</th>
                            <th>Last Active</th>
                            <th>Intent</th>
                            <th>Draft</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            ${totalPages > 1 ? `
            <div class="crm-pagination" style="display:flex;align-items:center;justify-content:center;gap:12px;padding:12px 0;font-size:0.82rem;">
                <button class="crm-inline-btn crm-inline-btn-secondary crm-page-prev" ${currentPage <= 1 ? 'disabled' : ''} style="padding:4px 14px;font-size:0.78rem;">Prev</button>
                <span style="color:var(--text-secondary);">Page ${currentPage} of ${totalPages} <span style="color:var(--text-muted);">(${filtered.length} contacts)</span></span>
                <button class="crm-inline-btn crm-inline-btn-secondary crm-page-next" ${currentPage >= totalPages ? 'disabled' : ''} style="padding:4px 14px;font-size:0.78rem;">Next</button>
            </div>` : ''}
        `;
    }

    // Event delegation — one listener on the contacts list, not one per button
    if (crmContactsList) {
        crmContactsList.addEventListener('click', (e) => {
            // Pagination buttons
            if (e.target.classList.contains('crm-page-prev')) {
                if (currentPage > 1) { currentPage--; renderContacts(); }
                return;
            }
            if (e.target.classList.contains('crm-page-next')) {
                currentPage++; renderContacts();
                return;
            }

            const btn = e.target.closest('button[data-contact-id]');
            if (!btn) return;
            const contactId = btn.dataset.contactId;
            if (btn.classList.contains('crm-generate-btn'))  generateMessage(contactId);
            if (btn.classList.contains('crm-edit-draft-btn')) openDraftEditor(contactId);
            if (btn.classList.contains('crm-delete-btn'))    deleteContact(contactId);
        });
    }

    function updateStats() {
        const total = allContacts.length;
        const scoreOf = c => Number(c.score || c.warmth_score || 0);
        const hot = allContacts.filter(c => scoreOf(c) >= 80).length;
        const warm = allContacts.filter(c => scoreOf(c) >= 50 && scoreOf(c) < 80).length;
        const cold = allContacts.filter(c => scoreOf(c) < 50).length;
        const crmStatCold = document.getElementById('crm-stat-cold');

        if (crmStatTotal) crmStatTotal.textContent = total;
        if (crmStatHot) crmStatHot.textContent = hot;
        if (crmStatWarm) crmStatWarm.textContent = warm;
        if (crmStatCold) crmStatCold.textContent = cold;
    }

    async function loadContacts(options = {}) {
        const { silent = false } = options;
        if (!hasCoreElements || contactsLoadInFlight) return;
        contactsLoadInFlight = true;

        if (!silent) {
            crmLoading.style.display = 'block';
            crmEmpty.style.display = 'none';
            crmContactsList.style.display = 'none';
            crmStats.style.display = 'none';
            crmRefreshBtn.disabled = true;
        }

        try {
            // Always fetch ALL contacts — no server-side tag/warmth filter.
            // Filtering is done exclusively client-side so allContacts is never a stale subset.
            const res = await fetch('/api/crm/contacts', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });

            const data = await res.json();
            if (!data.success) {
                throw new Error(data.error || 'Failed to load contacts');
            }

            const previousCount = allContacts.length;
            allContacts = data.contacts || [];

            if (allContacts.length === 0) {
                crmEmpty.style.display = 'block';
                crmContactsList.style.display = 'none';
                crmStats.style.display = 'none';
            } else {
                renderContacts();   // sets crmContactsList.style.display = 'block' internally
                updateStats();
                crmStats.style.display = 'block';
                crmEmpty.style.display = 'none';
            }
            // Always update the output console
            renderCRMOutput();

            if (!silent) {
                addSystemLog(`Loaded ${allContacts.length} CRM contacts`, 'success');
            } else if (allContacts.length !== previousCount) {
                addSystemLog(`CRM contacts updated: ${allContacts.length}`, 'info');
            }
        } catch (err) {
            console.error(err);
            // On error: restore table if we already had contacts, otherwise show empty state
            if (allContacts.length > 0) {
                renderContacts();
                crmStats.style.display = 'block';
                crmEmpty.style.display = 'none';
            } else if (!silent) {
                crmEmpty.style.display = 'block';
            }
            if (!silent) {
                addSystemLog('Failed to load CRM contacts', 'error');
            }
        } finally {
            if (!silent) {
                crmLoading.style.display = 'none';
                crmRefreshBtn.disabled = false;
            }
            contactsLoadInFlight = false;
        }
    }

    async function saveDraft(contactId, draftMessage, { silent = false } = {}) {
        const res = await fetch(`/api/crm/contacts/${contactId}/draft`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': window.appUserId || 'default'
            },
            body: JSON.stringify({ draft_message: draftMessage || '' })
        });

        const data = await res.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to save draft');
        }

        patchContact(contactId, {
            draft_message: data.draft_message || '',
            draft_updated_at: new Date().toISOString()
        });

        if (!silent) {
            addSystemLog('Draft saved', 'success');
        }
    }

    function openDraftEditor(contactId) {
        const contact = allContacts.find(c => c.id === contactId);
        if (!contact) return;

        // Close any already-open draft modal before opening a new one
        if (activeDraftModal) {
            activeDraftModal.remove();
            activeDraftModal = null;
        }

        const backdrop = document.createElement('div');
        backdrop.className = 'crm-draft-modal-backdrop';
        activeDraftModal = backdrop;

        const modal = document.createElement('div');
        modal.className = 'crm-draft-modal';
        modal.innerHTML = `
            <div class="crm-draft-modal-head">
                <div>
                    <h4>${escapeHtml(contact.full_name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || 'Prospect Draft')}</h4>
                    <p>Conversation-aware draft for this prospect.</p>
                </div>
                <button type="button" class="crm-modal-close-btn" aria-label="Close">&times;</button>
            </div>
            <textarea class="crm-draft-textarea" placeholder="Generate a message, then edit and save it here...">${escapeHtml(getDraftMessage(contact))}</textarea>
            <div class="crm-draft-modal-actions">
                <button type="button" class="crm-inline-btn crm-inline-btn-secondary crm-copy-draft-btn">Copy</button>
                <button type="button" class="crm-inline-btn crm-inline-btn-generate crm-save-draft-btn">Save Draft</button>
            </div>
        `;

        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        const closeModal = () => { backdrop.remove(); activeDraftModal = null; };
        const closeBtn = modal.querySelector('.crm-modal-close-btn');
        const textarea = modal.querySelector('.crm-draft-textarea');
        const copyBtn = modal.querySelector('.crm-copy-draft-btn');
        const saveBtn = modal.querySelector('.crm-save-draft-btn');

        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        backdrop.addEventListener('click', (event) => {
            if (event.target === backdrop) closeModal();
        });

        if (copyBtn && textarea) {
            copyBtn.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(textarea.value || '');
                    addSystemLog('Draft copied to clipboard', 'success');
                } catch (err) {
                    console.error(err);
                    addSystemLog('Unable to copy draft', 'error');
                }
            });
        }

        if (saveBtn && textarea) {
            saveBtn.addEventListener('click', async () => {
                saveBtn.disabled = true;
                saveBtn.textContent = 'Saving...';
                try {
                    await saveDraft(contactId, textarea.value || '');
                    renderContacts();
                } catch (err) {
                    console.error(err);
                    addSystemLog('Failed to save draft', 'error');
                } finally {
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Save Draft';
                }
            });
        }
    }

    async function generateMessage(contactId) {
        if (isGenerating) return;  // prevent double-trigger
        isGenerating = true;

        const btn = document.querySelector(`.crm-generate-btn[data-contact-id="${contactId}"]`);
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Generating...';
        }

        try {
            const res = await fetch(`/api/crm/contacts/${contactId}/generate-message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': window.appUserId || 'default'
                }
            });

            const data = await res.json();
            if (!data.success) {
                throw new Error(data.error || 'Generation failed');
            }

            patchContact(contactId, {
                draft_message: String(data.message || ''),
                draft_updated_at: new Date().toISOString()
            });

            renderContacts();
            addSystemLog('Message generated and saved to draft', 'success');
            openDraftEditor(contactId);
        } catch (err) {
            console.error(err);
            addSystemLog('Failed to generate message: ' + (err.message || err), 'error');
            // Restore the button if renderContacts() wasn't called
            const errBtn = document.querySelector(`.crm-generate-btn[data-contact-id="${contactId}"]`);
            if (errBtn) { errBtn.disabled = false; errBtn.textContent = 'Generate'; }
        } finally {
            isGenerating = false;
        }
    }

    async function deleteContact(contactId) {
        if (!confirm('Delete this contact?')) return;

        try {
            const res = await fetch(`/api/crm/contacts/${contactId}`, {
                method: 'DELETE',
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });

            const data = await res.json();
            if (!data.success) {
                throw new Error(data.error || 'Delete failed');
            }

            allContacts = allContacts.filter(c => c.id !== contactId);
            renderContacts();
            updateStats();
            addSystemLog('Contact deleted', 'success');
        } catch (err) {
            console.error(err);
            addSystemLog('Failed to delete contact', 'error');
        }
    }

    // Search input — debounced event delegation
    let searchDebounce = null;
    document.addEventListener('input', (e) => {
        if (e.target && e.target.id === 'crm-search-input') {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                currentSearchQuery = e.target.value.trim();
                currentPage = 1;
                renderContacts();
                renderCRMOutput();
                // Re-focus and restore cursor position
                const inp = document.getElementById('crm-search-input');
                if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
            }, 250);
        }
    });

    // Filter dropdown — event delegation
    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'crm-filter-dropdown') {
            currentFilter = e.target.value;
            currentPage = 1;
            renderContacts();
            renderCRMOutput();
        }
    });

    // Document-level delegation — bulletproof against lucide.createIcons() DOM replacement
    document.addEventListener('click', (e) => {
        // Search clear button
        if (e.target.closest('#crm-search-clear')) {
            currentSearchQuery = '';
            currentPage = 1;
            renderContacts();
            renderCRMOutput();
            const inp = document.getElementById('crm-search-input');
            if (inp) inp.focus();
            return;
        }

        // Refresh / Load Contacts button
        if (e.target.closest('#crm-refresh-btn')) {
            loadContacts();
            return;
        }

        // Re-analyze unanalyzed contacts
        if (e.target.closest('#crm-reanalyze-btn')) {
            const btn = document.getElementById('crm-reanalyze-btn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="ct-spinner"></span> Analyzing...';
            }
            const token = localStorage.getItem('supabase_access_token') || '';
            fetch('/api/crm/reanalyze', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    if (typeof addSystemLog === 'function') addSystemLog(`Re-analyzing ${data.count} contact(s) in background`, 'success');
                    // Start polling for updates
                    setTimeout(() => loadContacts({ silent: true }), 5000);
                    setTimeout(() => loadContacts({ silent: true }), 15000);
                    setTimeout(() => loadContacts({ silent: true }), 30000);
                } else {
                    if (typeof addSystemLog === 'function') addSystemLog('Re-analyze failed: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch(err => {
                console.error('[CRM] Reanalyze error:', err);
                if (typeof addSystemLog === 'function') addSystemLog('Re-analyze request failed', 'error');
            })
            .finally(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Re-analyze';
                }
            });
            return;
        }
    });

    // ── CRM Output Console — Professional Data Table ────────────────────────
    function renderCRMOutput() {
        const outputSlot = document.getElementById('crm-output-slot');
        if (!outputSlot) return;

        if (allContacts.length === 0) {
            outputSlot.innerHTML = `
                <div class="ct-empty">
                    <div class="ct-empty-icon">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--brand-primary)" stroke-width="1.5"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    </div>
                    <h3 class="ct-empty-title">No CRM Contacts Yet</h3>
                    <p class="ct-empty-desc">Upload your LinkedIn data export to populate the CRM with AI-scored contacts, intent analysis, and personalized outreach drafts.</p>
                    <div class="ct-empty-steps">
                        <div class="ct-step"><span class="ct-step-num">1</span><span>Upload LinkedIn ZIP</span></div>
                        <div class="ct-step"><span class="ct-step-num">2</span><span>AI Scores &amp; Tags</span></div>
                        <div class="ct-step"><span class="ct-step-num">3</span><span>Generate Messages</span></div>
                    </div>
                </div>`;
            return;
        }

        const scoreOf = c => Number(c.score || c.warmth_score || 0);
        const total = allContacts.length;
        const hot   = allContacts.filter(c => scoreOf(c) >= 80).length;
        const warm  = allContacts.filter(c => scoreOf(c) >= 50 && scoreOf(c) < 80).length;
        const cold  = allContacts.filter(c => scoreOf(c) < 50).length;
        const drafts = allContacts.filter(c => getDraftMessage(c)).length;

        // Use filtered contacts for the table rows
        const filtered = getFilteredContacts();
        const sorted = [...filtered].sort((a, b) => scoreOf(b) - scoreOf(a));

        const rows = sorted.map(c => {
            const name = escapeHtml(c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unknown');
            const initials = name.split(/\s+/).filter(Boolean).map(w => w[0]).join('').toUpperCase().slice(0,2) || '?';
            const tag = c.tag || c.behavioral_tag || 'prospect';
            const tc = tagColors[tag] || tagColors.prospect;
            const tl = tagLabels[tag] || tag;
            const score = scoreOf(c);
            const scoreColor = score >= 80 ? '#ef4444' : score >= 50 ? '#22c55e' : score >= 30 ? '#f59e0b' : '#64748b';
            const role = escapeHtml(c.title || c.position || '');
            const comp = escapeHtml(c.company || '');
            const roleCompany = [role, comp].filter(Boolean).join(' · ') || '-';
            const intentArr = Array.isArray(c.intent_points) ? c.intent_points : [];
            const intentText = escapeHtml(truncate(intentArr.join('; ') || c.reason_summary || c.intent_summary || '-', 50));
            const connDate = escapeHtml(c.connected_on || '-');
            const hasDraft = getDraftMessage(c) ? true : false;

            return `<tr class="ct-row" data-contact-id="${c.id}">
                <td class="ct-cell ct-cell-name">
                    <div class="ct-avatar">${initials}</div>
                    <div class="ct-name-col">
                        <div class="ct-name-row">
                            <span class="ct-name-text">${name}</span>
                            ${c.linkedin_url ? `<a href="${escapeHtml(c.linkedin_url)}" target="_blank" rel="noopener" class="ct-li-link" title="Open LinkedIn">in</a>` : ''}
                        </div>
                        <div class="ct-role-text">${roleCompany}</div>
                    </div>
                </td>
                <td class="ct-cell ct-cell-tag"><span class="ct-tag" style="background:${tc.bg};color:${tc.color};">${escapeHtml(tl)}</span></td>
                <td class="ct-cell ct-cell-score"><span class="ct-score-badge" style="color:${scoreColor};border-color:${scoreColor}30;">${score}</span></td>
                <td class="ct-cell ct-cell-intent" title="${escapeHtml(intentArr.join('\n'))}">${intentText}</td>
                <td class="ct-cell ct-cell-date">${connDate}</td>
                <td class="ct-cell ct-cell-draft">${hasDraft ? '<span class="ct-draft-yes">Draft</span>' : '<span class="ct-draft-no">-</span>'}</td>
                <td class="ct-cell ct-cell-actions">
                    <button class="ct-btn ct-btn-view" data-contact-id="${c.id}" title="Full View">View</button>
                </td>
            </tr>`;
        }).join('');

        // Build filter dropdown options
        const unanalyzedCount = allContacts.filter(c => (c.tag || c.behavioral_tag) === 'unanalyzed').length;
        const filterTags = [
            { key: 'all', label: 'All Contacts', count: total },
            { key: 'hot', label: 'Hot', count: hot },
            { key: 'warm', label: 'Warm', count: warm },
            { key: 'cold', label: 'Cold', count: cold },
            { key: 'ghosted', label: 'Ghosted', count: allContacts.filter(c => (c.tag || c.behavioral_tag) === 'ghosted').length },
            { key: 'client', label: 'Clients', count: allContacts.filter(c => (c.tag || c.behavioral_tag) === 'client').length },
            { key: 'prospect', label: 'Prospects', count: allContacts.filter(c => (c.tag || c.behavioral_tag) === 'prospect').length },
        ];
        if (unanalyzedCount > 0) {
            filterTags.push({ key: 'unanalyzed', label: 'Pending AI', count: unanalyzedCount });
        }
        const optionsHtml = filterTags.map(t =>
            `<option value="${t.key}"${currentFilter === t.key ? ' selected' : ''}>${t.label} (${t.count})</option>`
        ).join('');

        const filteredCount = filtered.length;
        const reanalyzeBtn = unanalyzedCount > 0
            ? `<button id="crm-reanalyze-btn" class="ct-reanalyze-btn" title="Re-run AI analysis on ${unanalyzedCount} pending contact(s)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                Re-analyze (${unanalyzedCount})
               </button>`
            : '';

        outputSlot.innerHTML = `
            <div class="ct-wrap">
                <div class="ct-toolbar">
                    <div class="ct-toolbar-row">
                        <div class="ct-toolbar-left">
                            <div class="ct-filter-dropdown-wrap">
                                <svg class="ct-filter-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
                                <select id="crm-filter-dropdown" class="ct-filter-dropdown">${optionsHtml}</select>
                            </div>
                            <span class="ct-result-count">${filteredCount} result${filteredCount !== 1 ? 's' : ''}</span>
                            ${reanalyzeBtn}
                        </div>
                        <div class="ct-toolbar-right">
                            <div class="ct-search-wrap">
                                <svg class="ct-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                                <input type="text" id="crm-search-input" class="ct-search-input" placeholder="Search contacts..." value="${escapeHtml(currentSearchQuery)}" spellcheck="false" autocomplete="off">
                                ${currentSearchQuery ? '<button id="crm-search-clear" class="ct-search-clear" title="Clear">&times;</button>' : ''}
                            </div>
                        </div>
                    </div>
                </div>
                <div class="ct-table-wrap">
                    <table class="ct-table">
                        <thead>
                            <tr>
                                <th class="ct-th ct-th-name">Contact</th>
                                <th class="ct-th">Tag</th>
                                <th class="ct-th ct-th-score">Score</th>
                                <th class="ct-th ct-th-intent">Intent</th>
                                <th class="ct-th">Connected</th>
                                <th class="ct-th">Draft</th>
                                <th class="ct-th ct-th-actions"></th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>`;

        // Delegate clicks on View buttons
        outputSlot.querySelectorAll('.ct-btn-view').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                openContactModal(btn.dataset.contactId);
            });
        });
        // Row click also opens modal
        outputSlot.querySelectorAll('.ct-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('.ct-btn') || e.target.closest('a')) return;
                openContactModal(row.dataset.contactId);
            });
        });
    }

    // ── Double-Side Contact Modal ─────────────────────────────────────────────
    let activeContactModal = null;

    function openContactModal(contactId) {
        const contact = allContacts.find(c => c.id === contactId);
        if (!contact) return;
        if (activeContactModal) { activeContactModal.remove(); activeContactModal = null; }

        const name = escapeHtml(contact.full_name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || 'Unknown');
        const initials = name.split(/\s+/).filter(Boolean).map(w => w[0]).join('').toUpperCase().slice(0,2) || '?';
        const tag = contact.tag || contact.behavioral_tag || 'prospect';
        const tc = tagColors[tag] || tagColors.prospect;
        const tl = tagLabels[tag] || tag;
        const score = Number(contact.score || contact.warmth_score || 0);
        const scoreColor = score >= 80 ? '#ef4444' : score >= 50 ? '#22c55e' : score >= 30 ? '#f59e0b' : '#64748b';
        const intentArr = Array.isArray(contact.intent_points) ? contact.intent_points : [];
        const draft = getDraftMessage(contact);

        const backdrop = document.createElement('div');
        backdrop.className = 'cm-backdrop';
        activeContactModal = backdrop;

        backdrop.innerHTML = `
            <div class="cm-modal">
                <button class="cm-close" aria-label="Close">&times;</button>

                <!-- LEFT: Profile Details -->
                <div class="cm-left">
                    <div class="cm-profile-head">
                        <div class="cm-avatar">${initials}</div>
                        <div>
                            <h2 class="cm-name">${name}</h2>
                            <p class="cm-role">${escapeHtml(contact.title || contact.position || '')}${contact.company ? ' @ ' + escapeHtml(contact.company) : ''}</p>
                        </div>
                    </div>

                    <div class="cm-meta-row">
                        <span class="cm-tag" style="background:${tc.bg};color:${tc.color};">${escapeHtml(tl)}</span>
                        <span class="cm-score" style="color:${scoreColor};border-color:${scoreColor}30;">${score}</span>
                    </div>

                    <div class="cm-fields">
                        ${_cmField('Company', contact.company)}
                        ${_cmField('Industry', contact.industry)}
                        ${_cmField('Experience', contact.years_of_experience ? contact.years_of_experience + ' years' : '')}
                        ${_cmField('Connected', contact.connected_on)}
                        ${_cmField('Source', contact.source)}
                        ${contact.linkedin_url ? `<div class="cm-field"><span class="cm-field-label">LinkedIn</span><a href="${escapeHtml(contact.linkedin_url)}" target="_blank" rel="noopener" class="cm-field-link">${escapeHtml(truncate(contact.linkedin_url, 40))}</a></div>` : ''}
                    </div>

                    ${intentArr.length ? `
                    <div class="cm-section">
                        <h4 class="cm-section-title">Intent Signals</h4>
                        <ul class="cm-intent-list">
                            ${intentArr.map(p => `<li class="cm-intent-item">${escapeHtml(p)}</li>`).join('')}
                        </ul>
                    </div>` : ''}
                </div>

                <!-- RIGHT: Actions & Draft -->
                <div class="cm-right">
                    <div class="cm-section">
                        <h4 class="cm-section-title">Outreach Draft</h4>
                        <textarea class="cm-draft-area" placeholder="Generate a personalized message or write your own draft...">${escapeHtml(draft)}</textarea>
                        <div class="cm-draft-actions">
                            <button class="cm-btn cm-btn-primary cm-gen-btn">Generate Message</button>
                            <button class="cm-btn cm-btn-secondary cm-save-btn">Save Draft</button>
                            <button class="cm-btn cm-btn-ghost cm-copy-btn">Copy</button>
                        </div>
                        ${contact.draft_is_sent ? '<p class="cm-sent-badge">Message sent</p>' : ''}
                    </div>

                    <div class="cm-right-footer">
                        <button class="cm-btn cm-btn-danger cm-delete-btn">Delete Contact</button>
                        <span class="cm-footer-meta">Updated ${formatDate(contact.updated_at)}</span>
                    </div>
                </div>
            </div>`;

        document.body.appendChild(backdrop);

        // ── Wire modal interactions ──
        const modal = backdrop.querySelector('.cm-modal');
        const closeBtn = modal.querySelector('.cm-close');
        const textarea = modal.querySelector('.cm-draft-area');
        const genBtn = modal.querySelector('.cm-gen-btn');
        const saveBtn = modal.querySelector('.cm-save-btn');
        const copyBtn = modal.querySelector('.cm-copy-btn');
        const delBtn = modal.querySelector('.cm-delete-btn');

        const closeModal = () => { backdrop.remove(); activeContactModal = null; };
        closeBtn.addEventListener('click', closeModal);
        backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeModal(); });

        genBtn.addEventListener('click', async () => {
            genBtn.disabled = true; genBtn.textContent = 'Generating...';
            try {
                const res = await fetch(`/api/crm/contacts/${contactId}/generate-message`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-User-ID': window.appUserId || 'default' }
                });
                const data = await res.json();
                if (!data.success) throw new Error(data.error || 'Generation failed');
                textarea.value = data.message || '';
                patchContact(contactId, { draft_message: data.message || '', draft_updated_at: new Date().toISOString() });
                renderContacts(); renderCRMOutput();
                addSystemLog('Message generated', 'success');
            } catch (err) {
                console.error(err);
                addSystemLog('Generation failed: ' + err.message, 'error');
            } finally { genBtn.disabled = false; genBtn.textContent = 'Generate Message'; }
        });

        saveBtn.addEventListener('click', async () => {
            saveBtn.disabled = true; saveBtn.textContent = 'Saving...';
            try {
                await saveDraft(contactId, textarea.value || '', { silent: true });
                renderContacts(); renderCRMOutput();
                addSystemLog('Draft saved', 'success');
            } catch (err) {
                addSystemLog('Failed to save draft', 'error');
            } finally { saveBtn.disabled = false; saveBtn.textContent = 'Save Draft'; }
        });

        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(textarea.value || '');
                addSystemLog('Copied to clipboard', 'success');
            } catch (err) { addSystemLog('Copy failed', 'error'); }
        });

        delBtn.addEventListener('click', async () => {
            if (!confirm('Delete this contact permanently?')) return;
            try {
                const res = await fetch(`/api/crm/contacts/${contactId}`, {
                    method: 'DELETE', headers: { 'X-User-ID': window.appUserId || 'default' }
                });
                const data = await res.json();
                if (!data.success) throw new Error(data.error);
                allContacts = allContacts.filter(c => c.id !== contactId);
                renderContacts(); updateStats(); renderCRMOutput();
                closeModal();
                addSystemLog('Contact deleted', 'success');
            } catch (err) { addSystemLog('Delete failed', 'error'); }
        });
    }

    function _cmField(label, value) {
        if (!value) return '';
        return `<div class="cm-field"><span class="cm-field-label">${escapeHtml(label)}</span><span class="cm-field-value">${escapeHtml(String(value))}</span></div>`;
    }

    // When called from tab switch: be silent if contacts are already loaded
    window.loadCRMHubContacts = (opts = {}) => loadContacts({
        silent: allContacts.length > 0,
        ...opts
    });

    window.addEventListener('linkedin-processing-status', (event) => {
        linkedinProcessingStatus = event?.detail?.processingStatus || null;

        if (linkedinProcessingStatus === 'processing') {
            startCRMAutoRefresh();
            if (isCRMTabActive()) {
                loadContacts({ silent: true });
            }
            return;
        }

        stopCRMAutoRefresh();
        if (linkedinProcessingStatus === 'completed' && isCRMTabActive()) {
            loadContacts({ silent: true });
        }
    });

    window.addEventListener('app-user-ready', () => {
        if (isCRMTabActive()) {
            loadContacts();
        }
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopCRMAutoRefresh();
        } else if (linkedinProcessingStatus === 'processing') {
            startCRMAutoRefresh();
        }
    });

    window.addEventListener('beforeunload', stopCRMAutoRefresh);
});
