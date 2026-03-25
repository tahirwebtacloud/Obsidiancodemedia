// frontend/auth.js — Supabase Auth

const SUPABASE_URL = 'https://bsaggewiyjaikkkbvgpr.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzYWdnZXdpeWphaWtra2J2Z3ByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyMTg0OTAsImV4cCI6MjA4Nzc5NDQ5MH0.i1AqmdPJe7e-5cq-Wdpia25ibz-jR9PCWn6cFfEoXLc';

const { createClient } = window.supabase;
const sbClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
window.sbClient = sbClient;

let currentUser = null;
let hasHydratedSignedIn = false;
window.appAccessToken = null;

// Auto-inject Authorization header on all /api/ fetch calls
const _originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    if (typeof url === 'string' && url.startsWith('/api/')) {
        if (!options.headers) {
            options.headers = {};
        }
        if (window.appAccessToken) {
            if (options.headers instanceof Headers) {
                options.headers.set('Authorization', `Bearer ${window.appAccessToken}`);
            } else {
                options.headers['Authorization'] = `Bearer ${window.appAccessToken}`;
            }
        }
    }
    return _originalFetch.call(this, url, options);
};

document.addEventListener('DOMContentLoaded', () => {
    const loginOverlay = document.getElementById('login-overlay');
    const mainApp = document.getElementById('main-app');
    const loginBtn = document.getElementById('firebase-login-btn');
    const signupBtn = document.getElementById('firebase-signup-btn');
    const emailSignupBtn = document.getElementById('email-signup-btn');
    const emailSigninBtn = document.getElementById('email-signin-btn');

    const signupName = document.getElementById('signup-name');
    const signupEmail = document.getElementById('signup-email');
    const signupPassword = document.getElementById('signup-password');
    
    const signinEmail = document.getElementById('signin-email');
    const signinPassword = document.getElementById('signin-password');
    const userInfoDisplay = document.getElementById('user-info-display');

    const googleSvg = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width:20px;height:20px;flex-shrink:0;"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/><path d="M1 1h22v22H1z" fill="none"/></svg>';

    // Google OAuth handler (shared by sign-in and sign-up)
    async function handleGoogleAuth(btn, label) {
        try {
            btn.disabled = true;
            btn.innerHTML = '<span style="opacity:0.7;">Connecting...</span>';
            const { error } = await sbClient.auth.signInWithOAuth({
                provider: 'google',
                options: { redirectTo: window.location.origin }
            });
            if (error) throw error;
        } catch (error) {
            console.error("Login failed:", error);
            alert("Login failed: " + error.message);
            btn.disabled = false;
            btn.innerHTML = googleSvg + ' ' + label;
        }
    }

    if (loginBtn) {
        loginBtn.addEventListener('click', () => handleGoogleAuth(loginBtn, 'Sign in with Google'));
    }
    if (signupBtn) {
        signupBtn.addEventListener('click', () => handleGoogleAuth(signupBtn, 'Sign up with Google'));
    }

    // Email Sign Up
    if (emailSignupBtn) {
        emailSignupBtn.addEventListener('click', async () => {
            const email = signupEmail.value.trim();
            const password = signupPassword.value.trim();
            const name = signupName.value.trim();

            if (!email || !password) {
                alert('Please enter an email and password.');
                return;
            }

            try {
                emailSignupBtn.disabled = true;
                emailSignupBtn.textContent = 'Signing up...';

                const { data, error } = await sbClient.auth.signUp({
                    email,
                    password,
                    options: {
                        data: {
                            full_name: name
                        }
                    }
                });

                if (error) throw error;
                alert('Signup successful! Please check your email to verify your account.');
                // Switch to login view or proceed based on auto-confirm settings
                const container = document.getElementById('login-container');
                if (container) container.classList.remove('right-panel-active');
            } catch (error) {
                console.error("Signup failed:", error);
                alert("Signup failed: " + error.message);
            } finally {
                emailSignupBtn.disabled = false;
                emailSignupBtn.textContent = 'Sign Up';
            }
        });
    }

    // Email Sign In
    if (emailSigninBtn) {
        emailSigninBtn.addEventListener('click', async () => {
            const email = signinEmail.value.trim();
            const password = signinPassword.value.trim();

            if (!email || !password) {
                alert('Please enter your email and password.');
                return;
            }

            try {
                emailSigninBtn.disabled = true;
                emailSigninBtn.textContent = 'Signing in...';

                const { data, error } = await sbClient.auth.signInWithPassword({
                    email,
                    password
                });

                if (error) throw error;
                // successful sign in will be caught by onAuthStateChange
            } catch (error) {
                console.error("Login failed:", error);
                alert("Login failed: " + error.message);
                emailSigninBtn.disabled = false;
                emailSigninBtn.textContent = 'Sign In';
            }
        });
    }

    // Google "G" circle icons also trigger OAuth
    document.querySelectorAll('.google-social-btn').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const fallbackBtn = loginBtn || signupBtn;
            if (fallbackBtn) handleGoogleAuth(fallbackBtn, 'Sign in with Google');
        });
    });

    // --- XSS Prevention Helpers ---
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function sanitizePhotoUrl(url) {
        if (!url || typeof url !== 'string') return '';
        const trimmed = url.trim();
        if (!trimmed.startsWith('https://')) return '';
        // Block injection characters that could break out of attribute context
        if (/['"<>]/.test(trimmed)) return '';
        return trimmed;
    }

    function showSignedIn(user) {
        if (hasHydratedSignedIn && currentUser && currentUser.id === user.id) {
            return;
        }

        currentUser = user;
        hasHydratedSignedIn = true;
        window.appUserId = user.id;
        // Store access token for API auth (updated on every auth state change / token refresh)
        sbClient.auth.getSession().then(({ data: { session } }) => {
            window.appAccessToken = session?.access_token || null;
        });
        console.log("User signed in:", user.id);

        if (loginOverlay) loginOverlay.style.display = 'none';
        if (mainApp) mainApp.style.display = 'grid';

        // Swap loading skeleton for real empty state
        const skel = document.getElementById('initial-skeleton');
        const empty = document.getElementById('empty-state');
        if (skel) skel.style.display = 'none';
        if (empty) empty.style.display = '';

        const meta = user.user_metadata || {};
        const rawDisplayName = meta.full_name || meta.name || user.email || 'User';
        const displayName = escapeHtml(rawDisplayName);
        const photoURL = sanitizePhotoUrl(meta.avatar_url || meta.picture || '');

        if (userInfoDisplay) {
            // Build avatar safely — photoURL is validated, displayName is escaped
            let avatarHtml;
            if (photoURL) {
                avatarHtml = `<img src="${photoURL}" alt="Profile" style="width: 40px; height: 40px; border-radius: 50%; border: 2px solid var(--brand-primary); object-fit: cover; flex-shrink:0;">`;
            } else {
                const initial = escapeHtml(rawDisplayName.charAt(0).toUpperCase());
                avatarHtml = `<div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,rgba(249,199,79,0.25),rgba(249,199,79,0.08));display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:var(--brand-primary);flex-shrink:0;">${initial}</div>`;
            }
            userInfoDisplay.innerHTML = `
                ${avatarHtml}
                <span style="font-size: 0.95rem; color: var(--text-primary); font-weight: 500; font-family: 'Outfit', sans-serif; line-height: 1; white-space: nowrap;">${displayName}</span>
                <i data-lucide="chevron-down" style="width:14px;height:14px;color:var(--text-tertiary);flex-shrink:0;transition:transform 0.2s;"></i>
            `;
            if (window.lucide) lucide.createIcons();

            // Wire user dropdown toggle
            const udMenu = document.getElementById('user-dropdown-menu');
            userInfoDisplay.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!udMenu) return;
                const open = udMenu.style.display === 'block';
                udMenu.style.display = open ? 'none' : 'block';
            });
            document.addEventListener('click', (e) => {
                if (udMenu && !udMenu.contains(e.target) && !userInfoDisplay.contains(e.target)) {
                    udMenu.style.display = 'none';
                }
            });

            // Dropdown menu actions
            const udLogout = document.getElementById('ud-logout-btn');
            if (udLogout) {
                udLogout.addEventListener('click', async () => {
                    await sbClient.auth.signOut();
                });
            }
            const udSettings = document.getElementById('ud-settings-btn');
            if (udSettings) {
                udSettings.addEventListener('click', () => {
                    if (udMenu) udMenu.style.display = 'none';
                    const settingsBtn = document.getElementById('open-settings-btn');
                    if (settingsBtn) settingsBtn.click();
                });
            }
            const udProfile = document.getElementById('ud-user-profile-btn');
            if (udProfile) {
                udProfile.addEventListener('click', () => {
                    if (udMenu) udMenu.style.display = 'none';
                    // Trigger User Profile (voice-engine) tab via custom event
                    window.dispatchEvent(new CustomEvent('switch-to-user-profile'));
                });
            }
        }

        if (typeof window.loadHistory === 'function') {
            window.loadHistory();
        }
        if (typeof window.loadBrandAssets === 'function') {
            window.loadBrandAssets();
        }
        if (typeof window.loadVoicePersona === 'function') {
            window.loadVoicePersona();
        }
        if (typeof window.loadCRMHubContacts === 'function') {
            window.loadCRMHubContacts();
        }

        window.dispatchEvent(new CustomEvent('app-user-ready', {
            detail: { userId: user.id }
        }));
    }

    function showSignedOut() {
        currentUser = null;
        hasHydratedSignedIn = false;
        window.appUserId = null;
        window.appAccessToken = null;
        console.log("User signed out");

        if (loginOverlay) loginOverlay.style.display = 'flex';
        if (mainApp) mainApp.style.display = 'none';
        if (userInfoDisplay) userInfoDisplay.innerHTML = '';

        // Reset both Google OAuth buttons
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerHTML = googleSvg + ' Sign in with Google';
        }
        if (signupBtn) {
            signupBtn.disabled = false;
            signupBtn.innerHTML = googleSvg + ' Sign up with Google';
        }
        
        if (emailSigninBtn) {
            emailSigninBtn.disabled = false;
            emailSigninBtn.textContent = 'Sign In';
        }
        if (emailSignupBtn) {
            emailSignupBtn.disabled = false;
            emailSignupBtn.textContent = 'Sign Up';
        }
    }

    // Listen for auth state changes (also fires on TOKEN_REFRESHED)
    sbClient.auth.onAuthStateChange((event, session) => {
        if (session && session.user) {
            window.appAccessToken = session.access_token || null;
            showSignedIn(session.user);
        } else {
            showSignedOut();
        }
    });

    // Check existing session on load
    sbClient.auth.getSession().then(({ data: { session } }) => {
        if (session && session.user) {
            window.appAccessToken = session.access_token || null;
            showSignedIn(session.user);
        } else {
            showSignedOut();
        }
    });
});
