// Brand Assets JavaScript Module
// Handles brand extraction, preview, and saving functionality

// --- Color Utilities (global scope so auth.js can trigger loadBrand) ---
function _hexToRgb(hex) {
    const n = parseInt(hex.replace('#', ''), 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}
function _adjustHex(hex, amount) {
    const { r, g, b } = _hexToRgb(hex);
    const clamp = v => Math.min(255, Math.max(0, v + amount));
    return '#' + [clamp(r), clamp(g), clamp(b)].map(v => v.toString(16).padStart(2, '0')).join('');
}
function _hexAlpha(hex, a) {
    const { r, g, b } = _hexToRgb(hex);
    return `rgba(${r},${g},${b},${a})`;
}

function applyBrandToUI(brand) {
    const root = document.documentElement;
    const theme = brand.ui_theme || {};
    const font  = brand.font_family || 'Montserrat';

    // Apply every key from ui_theme as a CSS variable
    // Key format: "brand_primary" → CSS var "--brand-primary"
    const keyToCssVar = k => '--' + k.replace(/_/g, '-');

    for (const [key, value] of Object.entries(theme)) {
        if (value) root.style.setProperty(keyToCssVar(key), value);
    }

    // Also set convenience aliases used elsewhere in CSS
    const p = theme.brand_primary || brand.primary_color || '#F9C74F';
    const s = brand.secondary_color || theme.brand_obsidian || '#0E0E0E';
    const a = brand.accent_color || '#FCF0D5';
    const { r, g, b } = _hexToRgb(p);
    root.style.setProperty('--brand-secondary', s);
    root.style.setProperty('--brand-accent', a);
    root.style.setProperty('--brand-primary-rgb', `${r}, ${g}, ${b}`);
    root.style.setProperty('--brand-tint-primary', _hexAlpha(p, 0.08));
    root.style.setProperty('--brand-tint-accent',  _hexAlpha(a, 0.12));

    // Shared glow aliases for legacy CSS blocks
    root.style.setProperty('--brand-glow-soft', `rgba(${r}, ${g}, ${b}, 0.18)`);
    root.style.setProperty('--brand-glow-medium', `rgba(${r}, ${g}, ${b}, 0.28)`);
    root.style.setProperty('--brand-glow-strong', `rgba(${r}, ${g}, ${b}, 0.42)`);

    // Dynamic logo + brand title in sidebar header
    const logoEl = document.getElementById('app-brand-logo');
    const nameEl = document.getElementById('app-brand-name');
    if (logoEl && brand.logo_url) {
        logoEl.src = brand.logo_url;
        logoEl.alt = `${brand.brand_name || 'Brand'} Logo`;
        logoEl.onerror = () => { logoEl.src = 'logo.png'; };
    }
    if (nameEl) {
        nameEl.textContent = brand.brand_name || 'Obsidian Logic';
    }

    // Typography
    if (font && font !== 'Montserrat') {
        root.style.setProperty('--font-heading', `'${font}', 'Montserrat', sans-serif`);
        root.style.setProperty('--font-body',    `'${font}', 'Montserrat', sans-serif`);
    }
}

// Expose globally so auth.js can call it after user ID is set
window.loadBrandAssets = null; // will be assigned below

document.addEventListener('DOMContentLoaded', () => {
    // Brand Assets Elements
    const brandUrlInput = document.getElementById('brand-url-input');
    const extractBrandBtn = document.getElementById('extract-brand-btn');
    const brandExtractLoading = document.getElementById('brand-extract-loading');
    const brandPreviewPanel = document.getElementById('brand-preview-panel');
    const saveBrandBtn = document.getElementById('save-brand-btn');
    const resetBrandBtn = document.getElementById('reset-brand-btn');
    const brandSaveStatus = document.getElementById('brand-save-status');

    // Brand input fields
    const brandNameInput = document.getElementById('brand-name-input');
    const primaryColorPicker = document.getElementById('primary-color-picker');
    const primaryColorText = document.getElementById('primary-color-text');
    const secondaryColorPicker = document.getElementById('secondary-color-picker');
    const secondaryColorText = document.getElementById('secondary-color-text');
    const accentColorPicker = document.getElementById('accent-color-picker');
    const accentColorText = document.getElementById('accent-color-text');
    const fontFamilyInput = document.getElementById('font-family-input');
    const visualStyleInput = document.getElementById('visual-style-input');
    const toneOfVoiceInput = document.getElementById('tone-of-voice-input');
    const logoUrlInput = document.getElementById('logo-url-input');
    const brandLivePreview = document.getElementById('brand-live-preview');
    const extractedColorsList = document.getElementById('extracted-colors-list');
    const extractedFontsList = document.getElementById('extracted-fonts-list');

    const productsList = document.getElementById('products-services-list');
    const addProductBtn = document.getElementById('add-product-btn');

    // Current brand state
    // Default UI theme (must match DEFAULT_UI_THEME in brand_extractor.py)
    const DEFAULT_UI_THEME = {
        brand_primary: '#F9C74F', brand_primary_hover: '#f0b829',
        brand_primary_light: 'rgba(249,199,79,0.15)',
        brand_obsidian: '#0E0E0E', brand_obsidian_soft: '#1a1a1a',
        bg_main: '#1a1a1a', bg_paper: '#111111', bg_elevated: '#252525', bg_sidebar: '#0E0E0E',
        text_primary: '#F0F0F0', text_secondary: '#A0A0A0', text_tertiary: '#6B6B6B',
        text_muted: '#4B4B4B', text_inverse: '#FCF0D5',
        border: 'rgba(255,255,255,0.1)', border_hover: 'rgba(255,255,255,0.2)', border_focus: '#F9C74F',
        shadow_glow: '0 0 20px rgba(249,199,79,0.3)', shadow_glow_strong: '0 0 30px rgba(249,199,79,0.5)',
        brand_gradient: 'linear-gradient(135deg, #F9C74F 0%, #F59E0B 100%)',
        brand_gradient_dark: 'linear-gradient(135deg, #0E0E0E 0%, #1a1a1a 100%)',
        brand_gradient_hover: 'linear-gradient(135deg, #f0b829 0%, #e5a608 100%)'
    };

    let currentBrandAssets = {
        brand_name: '',
        primary_color: '#F9C74F',
        secondary_color: '#0E0E0E',
        accent_color: '#FCF0D5',
        font_family: 'Inter',
        logo_url: '',
        visual_style: '',
        tone_of_voice: '',
        products_services: [],
        extracted_colors: [],
        extracted_fonts: [],
        ui_theme: { ...DEFAULT_UI_THEME }
    };

    function getCurrentBrandKitPalette() {
        const primary = (currentBrandAssets.primary_color || '#F9C74F').toUpperCase();
        const secondary = (currentBrandAssets.secondary_color || '#0E0E0E').toUpperCase();
        const accent = (currentBrandAssets.accent_color || '#FCF0D5').toUpperCase();
        const theme = currentBrandAssets.ui_theme || {};
        return {
            id: 'brand_kit',
            name: 'Brand Kit (My Brand)',
            description: `User-isolated palette for ${currentBrandAssets.brand_name || 'current brand'}`,
            primary,
            secondary,
            accent,
            neutral: theme.bg_paper || '#111111',
            dark: theme.bg_sidebar || secondary,
            light: theme.text_primary || '#F0F0F0',
            color_theory: 'Derived from the active user brand settings for consistent visual identity.',
            emotional_context: currentBrandAssets.tone_of_voice || 'Brand-authentic and user-specific',
            best_for: 'Any generation that should strictly follow the current user brand kit',
            usage_guidelines: {
                primary_use: 'Primary emphasis, highlights, and key visual anchors',
                secondary_use: 'Supporting color blocks, secondary text, and structural accents',
                accent_use: 'Callouts, CTA highlights, and focal points',
                neutral_use: 'Background surfaces, spacing, and subtle containers'
            }
        };
    }

    function emitBrandKitUpdated() {
        window.dispatchEvent(new CustomEvent('brand-kit-updated', {
            detail: { palette: getCurrentBrandKitPalette() }
        }));
    }

    window.getCurrentBrandKitPalette = getCurrentBrandKitPalette;

    function renderExtractedColors(colors) {
        if (!extractedColorsList) return;
        const palette = (colors || []).filter(c => /^#[0-9A-F]{6}$/i.test(String(c || '').trim()));
        if (!palette.length) {
            extractedColorsList.innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted);">Analyze a URL to load full palette</span>';
            return;
        }
        extractedColorsList.innerHTML = palette.map(c => {
            const hex = c.toUpperCase();
            return `<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid var(--border);border-radius:999px;background:var(--bg-elevated);font-size:0.7rem;color:var(--text-secondary);font-family:monospace;">
                <span style="width:10px;height:10px;border-radius:50%;background:${hex};border:1px solid rgba(255,255,255,0.25);"></span>${hex}
            </span>`;
        }).join('');
    }

    function getDisplayPalette(brand) {
        const fromExtracted = Array.isArray(brand?.extracted_colors) ? brand.extracted_colors : [];
        const fallbackCore = [brand?.primary_color, brand?.secondary_color, brand?.accent_color].filter(Boolean);
        const source = fromExtracted.length ? fromExtracted : fallbackCore;
        return [...new Set(source.map(c => String(c || '').trim().toUpperCase()))];
    }

    function renderExtractedFonts(fonts) {
        if (!extractedFontsList) return;
        const list = (fonts || [])
            .map(f => String(f || '').trim())
            .filter(Boolean);

        if (!list.length) {
            extractedFontsList.innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted);">Analyze a URL to load detected fonts</span>';
            return;
        }

        extractedFontsList.innerHTML = [...new Set(list)].map(font =>
            `<span style="display:inline-flex;align-items:center;padding:4px 8px;border:1px solid var(--border);border-radius:999px;background:var(--bg-elevated);font-size:0.7rem;color:var(--text-secondary);">${font}</span>`
        ).join('');
    }

    function buildThemeFromManualColors(primary, secondary, accent, baseTheme) {
        const p = (primary || '#F9C74F').toUpperCase();
        const s = (secondary || '#0E0E0E').toUpperCase();
        const a = (accent || '#FCF0D5').toUpperCase();
        const theme = { ...DEFAULT_UI_THEME, ...(baseTheme || {}) };

        theme.brand_primary = p;
        theme.brand_primary_hover = _adjustHex(p, -18);
        theme.brand_primary_light = _hexAlpha(p, 0.15);
        theme.border_focus = p;
        theme.shadow_glow = `0 0 20px ${_hexAlpha(p, 0.3)}`;
        theme.shadow_glow_strong = `0 0 30px ${_hexAlpha(p, 0.48)}`;
        theme.brand_gradient = `linear-gradient(135deg, ${p} 0%, ${a} 100%)`;
        theme.brand_gradient_hover = `linear-gradient(135deg, ${_adjustHex(p, -12)} 0%, ${_adjustHex(a, -10)} 100%)`;

        theme.brand_obsidian = s;
        theme.brand_obsidian_soft = _adjustHex(s, 18);
        theme.bg_sidebar = s;

        return theme;
    }

    // Render products/services list
    function renderProductsList(items) {
        if (!productsList) return;
        if (!items || items.length === 0) {
            productsList.innerHTML = `<div style="padding: 10px 12px; background: rgba(255,255,255,0.03); border: 1px dashed rgba(255,255,255,0.1); border-radius: 8px; text-align: center;"><span style="font-size: 0.75rem; color: var(--text-tertiary);">Analyze a URL to auto-detect offerings</span></div>`;
            return;
        }
        productsList.innerHTML = items.map((item, i) => `
            <div class="product-item" style="display: flex; gap: 8px; padding: 8px 10px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; align-items: flex-start;">
                <div style="flex: 1; min-width: 0;">
                    <input type="text" class="product-name dark-input" value="${_escAttr(item.name || '')}" placeholder="Product/Service name" style="width: 100%; margin-bottom: 4px; padding: 4px 8px !important; height: auto !important; font-size: 0.78rem; font-weight: 600;">
                    <input type="text" class="product-desc dark-input" value="${_escAttr(item.description || '')}" placeholder="One-line description" style="width: 100%; padding: 4px 8px !important; height: auto !important; font-size: 0.75rem; color: var(--text-secondary);">
                </div>
                <button type="button" onclick="this.closest('.product-item').remove()" style="padding: 4px; background: none; border: none; color: var(--text-tertiary); cursor: pointer; flex-shrink: 0; margin-top: 2px;" title="Remove">
                    <i data-lucide="x" style="width: 13px; height: 13px;"></i>
                </button>
            </div>`).join('');
        if (window.lucide) lucide.createIcons();
    }

    function _escAttr(str) {
        return String(str).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    function collectProductsList() {
        if (!productsList) return [];
        return Array.from(productsList.querySelectorAll('.product-item')).map(el => ({
            name: el.querySelector('.product-name')?.value.trim() || '',
            description: el.querySelector('.product-desc')?.value.trim() || ''
        })).filter(p => p.name);
    }

    function addBlankProduct() {
        const items = collectProductsList();
        items.push({ name: '', description: '' });
        renderProductsList(items);
        const inputs = productsList.querySelectorAll('.product-name');
        if (inputs.length) inputs[inputs.length - 1].focus();
    }

    if (addProductBtn) addProductBtn.addEventListener('click', addBlankProduct);

    // Sync color picker with text input
    function syncColorInputs() {
        if (primaryColorPicker && primaryColorText) {
            primaryColorPicker.addEventListener('input', () => {
                primaryColorText.value = primaryColorPicker.value.toUpperCase();
                updateBrandPreview();
            });
            primaryColorText.addEventListener('input', () => {
                if (/^#[0-9A-F]{6}$/i.test(primaryColorText.value)) {
                    primaryColorPicker.value = primaryColorText.value;
                    updateBrandPreview();
                }
            });
        }

        if (secondaryColorPicker && secondaryColorText) {
            secondaryColorPicker.addEventListener('input', () => {
                secondaryColorText.value = secondaryColorPicker.value.toUpperCase();
                updateBrandPreview();
            });
            secondaryColorText.addEventListener('input', () => {
                if (/^#[0-9A-F]{6}$/i.test(secondaryColorText.value)) {
                    secondaryColorPicker.value = secondaryColorText.value;
                    updateBrandPreview();
                }
            });
        }

        if (accentColorPicker && accentColorText) {
            accentColorPicker.addEventListener('input', () => {
                accentColorText.value = accentColorPicker.value.toUpperCase();
                updateBrandPreview();
            });
            accentColorText.addEventListener('input', () => {
                if (/^#[0-9A-F]{6}$/i.test(accentColorText.value)) {
                    accentColorPicker.value = accentColorText.value;
                    updateBrandPreview();
                }
            });
        }
    }

    // Update live preview
    function updateBrandPreview() {
        if (!brandLivePreview) return;

        const primary = primaryColorText?.value || '#F9C74F';
        const secondary = secondaryColorText?.value || '#0E0E0E';
        const accent = accentColorText?.value || '#FCF0D5';

        brandLivePreview.style.background = primary;
        brandLivePreview.style.color = secondary === '#FFFFFF' || secondary === '#F9F9F9' ? '#1A1A2E' : '#FFFFFF';

        const sampleBtn = brandLivePreview.querySelector('button');
        if (sampleBtn) {
            sampleBtn.style.background = accent;
            sampleBtn.style.color = '#1A1A2E';
        }
    }

    // Extract brand from URL
    if (extractBrandBtn) {
        extractBrandBtn.addEventListener('click', async () => {
            const url = brandUrlInput?.value.trim();
            if (!url) {
                addSystemLog('Please enter a website URL.', 'error');
                return;
            }

            brandExtractLoading.style.display = 'block';
            brandPreviewPanel.style.display = 'none';
            extractBrandBtn.disabled = true;

            try {
                const res = await fetch('/api/preview-brand', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify({ url })
                });

                const data = await res.json();

                if (data.success && data.brand_assets) {
                    currentBrandAssets = data.brand_assets;

                    // Populate form fields
                    if (brandNameInput) brandNameInput.value = data.brand_assets.brand_name || '';
                    if (primaryColorPicker) primaryColorPicker.value = data.brand_assets.primary_color;
                    if (primaryColorText) primaryColorText.value = data.brand_assets.primary_color.toUpperCase();
                    if (secondaryColorPicker) secondaryColorPicker.value = data.brand_assets.secondary_color;
                    if (secondaryColorText) secondaryColorText.value = data.brand_assets.secondary_color.toUpperCase();
                    if (accentColorPicker) accentColorPicker.value = data.brand_assets.accent_color;
                    if (accentColorText) accentColorText.value = data.brand_assets.accent_color.toUpperCase();
                    if (fontFamilyInput) fontFamilyInput.value = data.brand_assets.font_family || 'Inter';
                    if (visualStyleInput) visualStyleInput.value = data.brand_assets.visual_style || '';
                    if (toneOfVoiceInput) toneOfVoiceInput.value = data.brand_assets.tone_of_voice || '';
                    if (logoUrlInput) logoUrlInput.value = data.brand_assets.logo_url || '';
                    renderProductsList(data.brand_assets.products_services || []);
                    renderExtractedColors(getDisplayPalette(data.brand_assets));
                    renderExtractedFonts(data.brand_assets.extracted_fonts || [data.brand_assets.font_family || 'Inter']);

                    // Apply full LLM-generated UI theme to every surface
                    applyBrandToUI(data.brand_assets);
                    emitBrandKitUpdated();

                    brandPreviewPanel.style.display = 'block';
                    updateBrandPreview();
                    addSystemLog('Brand extracted successfully!', 'success');
                } else {
                    addSystemLog(data.error || 'Failed to extract brand.', 'error');
                }
            } catch (err) {
                console.error(err);
                addSystemLog('Network error extracting brand.', 'error');
            } finally {
                brandExtractLoading.style.display = 'none';
                extractBrandBtn.disabled = false;
            }
        });
    }

    // Save brand assets
    if (saveBrandBtn) {
        saveBrandBtn.addEventListener('click', async () => {
            const primary = (primaryColorText?.value || '#F9C74F').toUpperCase();
            const secondary = (secondaryColorText?.value || '#1A1A1A').toUpperCase();
            const accent = (accentColorText?.value || '#FCF0D5').toUpperCase();
            const syncedTheme = buildThemeFromManualColors(primary, secondary, accent, currentBrandAssets.ui_theme);

            const brandAssets = {
                brand_name: brandNameInput?.value || '',
                primary_color: primary,
                secondary_color: secondary,
                accent_color: accent,
                font_family: fontFamilyInput?.value || 'Inter',
                visual_style: visualStyleInput?.value || '',
                tone_of_voice: toneOfVoiceInput?.value || '',
                logo_url: logoUrlInput?.value || '',
                products_services: collectProductsList(),
                extracted_colors: currentBrandAssets.extracted_colors || [],
                extracted_fonts: currentBrandAssets.extracted_fonts || [],
                ui_theme: syncedTheme
            };

            saveBrandBtn.disabled = true;
            saveBrandBtn.innerHTML = '<i data-lucide="loader-2" style="width: 14px; height: 14px;"></i> Saving...';

            try {
                const res = await fetch('/api/save-brand', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-ID': window.appUserId || 'default'
                    },
                    body: JSON.stringify({ brand_assets: brandAssets })
                });

                const data = await res.json();

                if (data.success) {
                    currentBrandAssets = { ...currentBrandAssets, ...brandAssets };
                    // Apply full brand palette to CSS variables
                    applyBrandToUI(currentBrandAssets);
                    emitBrandKitUpdated();

                    if (brandSaveStatus) {
                        brandSaveStatus.innerHTML = '<span style="color: var(--success);">✓ Brand saved and applied!</span>';
                        brandSaveStatus.style.opacity = '1';
                        setTimeout(() => brandSaveStatus.style.opacity = '0', 3000);
                    }
                    addSystemLog('Brand assets saved successfully!', 'success');
                } else {
                    throw new Error(data.error || 'Save failed');
                }
            } catch (err) {
                console.error(err);
                if (brandSaveStatus) {
                    brandSaveStatus.innerHTML = '<span style="color: var(--error);">✗ Save failed</span>';
                    brandSaveStatus.style.opacity = '1';
                }
                addSystemLog('Failed to save brand assets.', 'error');
            } finally {
                saveBrandBtn.disabled = false;
                saveBrandBtn.innerHTML = '<i data-lucide="save" style="width: 14px; height: 14px;"></i> Save & Apply';
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    // Reset brand to defaults
    if (resetBrandBtn) {
        resetBrandBtn.addEventListener('click', () => {
            if (brandNameInput) brandNameInput.value = '';
            if (primaryColorPicker) primaryColorPicker.value = '#F9C74F';
            if (primaryColorText) primaryColorText.value = '#F9C74F';
            if (secondaryColorPicker) secondaryColorPicker.value = '#0E0E0E';
            if (secondaryColorText) secondaryColorText.value = '#0E0E0E';
            if (accentColorPicker) accentColorPicker.value = '#FCF0D5';
            if (accentColorText) accentColorText.value = '#FCF0D5';
            if (fontFamilyInput) fontFamilyInput.value = 'Inter';
            if (visualStyleInput) visualStyleInput.value = '';
            if (toneOfVoiceInput) toneOfVoiceInput.value = '';
            if (logoUrlInput) logoUrlInput.value = '';
            renderProductsList([]);
            renderExtractedColors([]);
            renderExtractedFonts([]);
            currentBrandAssets.primary_color = '#F9C74F';
            currentBrandAssets.secondary_color = '#0E0E0E';
            currentBrandAssets.accent_color = '#FCF0D5';
            currentBrandAssets.brand_name = '';
            currentBrandAssets.tone_of_voice = '';
            currentBrandAssets.ui_theme = { ...DEFAULT_UI_THEME };

            // Apply default Obsidian Logic theme back to entire UI
            applyBrandToUI({ ui_theme: DEFAULT_UI_THEME, font_family: 'Montserrat' });
            emitBrandKitUpdated();
            updateBrandPreview();
            addSystemLog('Brand reset to defaults.', 'info');
        });
    }

    // File upload functionality
    const brandFileUploadZone = document.getElementById('brand-file-upload-zone');
    const brandFileInput = document.getElementById('brand-file-input');
    const brandFileList = document.getElementById('brand-file-list');

    if (brandFileUploadZone && brandFileInput) {
        brandFileUploadZone.addEventListener('click', () => brandFileInput.click());
        
        brandFileUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            brandFileUploadZone.style.borderColor = 'var(--brand-primary)';
            brandFileUploadZone.style.background = 'rgba(249,199,79,0.05)';
        });

        brandFileUploadZone.addEventListener('dragleave', () => {
            brandFileUploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
            brandFileUploadZone.style.background = 'transparent';
        });

        brandFileUploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            brandFileUploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
            brandFileUploadZone.style.background = 'transparent';
            handleBrandFiles(e.dataTransfer.files);
        });

        brandFileInput.addEventListener('change', (e) => {
            handleBrandFiles(e.target.files);
        });
    }

    function handleBrandFiles(files) {
        if (!brandFileList) return;

        const validTypes = ['.svg', '.png', '.jpg', '.jpeg', '.pdf', '.json'];
        let html = '';

        Array.from(files).forEach(file => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (validTypes.includes(ext)) {
                html += `<div style="display: flex; align-items: center; gap: 8px; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 6px; margin-bottom: 4px;">
                    <i data-lucide="file" style="width: 16px; height: 16px; color: var(--brand-primary);"></i>
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">${file.name}</span>
                    <span style="font-size: 0.7rem; color: var(--text-muted); margin-left: auto;">${(file.size / 1024).toFixed(1)} KB</span>
                </div>`;
            }
        });

        brandFileList.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    }

    // Load existing brand on page load
    async function loadBrand() {
        try {
            const res = await fetch('/api/brand', {
                headers: { 'X-User-ID': window.appUserId || 'default' }
            });
            const data = await res.json();

            if (data.success && data.brand_assets) {
                const brand = data.brand_assets;
                currentBrandAssets = brand;
                
                // Apply full brand palette (all CSS variables from ui_theme)
                applyBrandToUI(brand);
                emitBrandKitUpdated();

                // If we have a brand name, show the preview panel with data
                if (brand.brand_name) {
                    if (brandNameInput) brandNameInput.value = brand.brand_name;
                    if (primaryColorPicker) primaryColorPicker.value = brand.primary_color;
                    if (primaryColorText) primaryColorText.value = brand.primary_color.toUpperCase();
                    if (secondaryColorPicker) secondaryColorPicker.value = brand.secondary_color;
                    if (secondaryColorText) secondaryColorText.value = brand.secondary_color.toUpperCase();
                    if (accentColorPicker) accentColorPicker.value = brand.accent_color;
                    if (accentColorText) accentColorText.value = brand.accent_color.toUpperCase();
                    if (fontFamilyInput) fontFamilyInput.value = brand.font_family;
                    if (visualStyleInput) visualStyleInput.value = brand.visual_style || '';
                    if (toneOfVoiceInput) toneOfVoiceInput.value = brand.tone_of_voice || '';
                    if (logoUrlInput) logoUrlInput.value = brand.logo_url || '';
                    renderProductsList(brand.products_services || []);
                    renderExtractedColors(getDisplayPalette(brand));
                    renderExtractedFonts(brand.extracted_fonts || [brand.font_family || 'Inter']);

                    brandPreviewPanel.style.display = 'block';
                    updateBrandPreview();
                }
            }
        } catch (e) {
            console.error('Failed to load brand', e);
        }
    }

    // Initialize
    syncColorInputs();
    // Only load brand if auth is already available; otherwise auth.js
    // will call window.loadBrandAssets() after sign-in completes.
    if (window.appAccessToken) loadBrand();

    // Expose globally so auth.js can re-trigger after appUserId is set
    window.loadBrandAssets = loadBrand;
});
