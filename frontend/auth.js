// frontend/auth.js — Supabase Auth

const SUPABASE_URL = 'https://bsaggewiyjaikkkbvgpr.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzYWdnZXdpeWphaWtra2J2Z3ByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyMTg0OTAsImV4cCI6MjA4Nzc5NDQ5MH0.i1AqmdPJe7e-5cq-Wdpia25ibz-jR9PCWn6cFfEoXLc';

const { createClient } = window.supabase;
const sbClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
window.sbClient = sbClient;

let currentUser = null;

document.addEventListener('DOMContentLoaded', () => {
    const loginOverlay = document.getElementById('login-overlay');
    const mainApp = document.getElementById('main-app');
    const loginBtn = document.getElementById('firebase-login-btn');
    const userInfoDisplay = document.getElementById('user-info-display');

    // Google OAuth sign-in
    if (loginBtn) {
        loginBtn.addEventListener('click', async () => {
            try {
                loginBtn.disabled = true;
                loginBtn.innerHTML = '<i data-lucide="loader" class="btn-icon spinning"></i> Signing in...';
                if (window.lucide) lucide.createIcons();

                const { error } = await sbClient.auth.signInWithOAuth({
                    provider: 'google',
                    options: { redirectTo: window.location.origin }
                });
                if (error) throw error;
            } catch (error) {
                console.error("Login failed:", error);
                alert("Login failed: " + error.message);
                loginBtn.disabled = false;
                loginBtn.innerHTML = '<i data-lucide="log-in" class="btn-icon"></i> Sign in with Google';
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    function showSignedIn(user) {
        currentUser = user;
        window.appUserId = user.id;
        console.log("User signed in:", user.id);

        if (loginOverlay) loginOverlay.style.display = 'none';
        if (mainApp) mainApp.style.display = 'grid';

        const meta = user.user_metadata || {};
        const displayName = meta.full_name || meta.name || user.email || 'User';
        const photoURL = meta.avatar_url || meta.picture || '';

        if (userInfoDisplay) {
            userInfoDisplay.innerHTML = `
                ${photoURL ? `<img src="${photoURL}" alt="Profile" style="width: 44px; height: 44px; border-radius: 50%; border: 2px solid var(--brand-primary); object-fit: cover;">` : ''}
                <div style="display: flex; flex-direction: column; justify-content: center; align-items: flex-start; gap: 4px;">
                    <span style="font-size: 1.05rem; color: var(--text-primary); font-weight: 500; font-family: 'Outfit', sans-serif; line-height: 1;">${displayName}</span>
                    <button id="supabase-logout-btn" style="background: transparent; border: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary); cursor: pointer; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; display: flex; align-items: center; gap: 4px; transition: all 0.2s; line-height: 1;" onmouseover="this.style.color='var(--brand-primary)'; this.style.borderColor='var(--brand-primary)'" onmouseout="this.style.color='var(--text-secondary)'; this.style.borderColor='rgba(255,255,255,0.1)'">
                        <i data-lucide="log-out" style="width: 12px; height: 12px;"></i> Logout
                    </button>
                </div>
            `;

            const logoutBtn = document.getElementById('supabase-logout-btn');
            if (logoutBtn) {
                logoutBtn.addEventListener('click', async () => {
                    await sbClient.auth.signOut();
                });
            }
            if (window.lucide) lucide.createIcons();
        }

        if (typeof window.loadHistory === 'function') {
            window.loadHistory();
        }
    }

    function showSignedOut() {
        currentUser = null;
        window.appUserId = null;
        console.log("User signed out");

        if (loginOverlay) loginOverlay.style.display = 'flex';
        if (mainApp) mainApp.style.display = 'none';
        if (userInfoDisplay) userInfoDisplay.innerHTML = '';

        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<div class="flex-row"><span><svg viewBox="0 0 24 24" style="width: 24px; height: 24px; margin-right: 10px;" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/><path d="M1 1h22v22H1z" fill="none"/></svg></span><span>Sign in with Google</span></div>';
        }
    }

    // Listen for auth state changes
    sbClient.auth.onAuthStateChange((event, session) => {
        if (session && session.user) {
            showSignedIn(session.user);
        } else {
            showSignedOut();
        }
    });

    // Check existing session on load
    sbClient.auth.getSession().then(({ data: { session } }) => {
        if (session && session.user) {
            showSignedIn(session.user);
        } else {
            showSignedOut();
        }
    });
});
