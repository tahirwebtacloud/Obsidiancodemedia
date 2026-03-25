// frontend/login.js — Interactive Login Page: Panel Toggle + Particle Background

(function () {
    // --- Panel Toggle Logic ---
    const signUpBtn = document.getElementById('login-signUp');
    const signInBtn = document.getElementById('login-signIn');
    const container = document.getElementById('login-container');

    if (signUpBtn && container) {
        signUpBtn.addEventListener('click', () => {
            container.classList.add('right-panel-active');
        });
    }
    if (signInBtn && container) {
        signInBtn.addEventListener('click', () => {
            container.classList.remove('right-panel-active');
        });
    }

    // Mobile toggle buttons
    document.querySelectorAll('.mobile-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            if (container) container.classList.toggle('right-panel-active');
        });
    });

    // --- Background Particle Effect ---
    const canvas = document.getElementById('login-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();

    let particlesArray = [];
    const mouse = { x: null, y: null, radius: 0 };

    function calcRadius() {
        mouse.radius = (canvas.height / 100) * (canvas.width / 100);
    }
    calcRadius();

    window.addEventListener('mousemove', (e) => {
        mouse.x = e.x;
        mouse.y = e.y;
    });

    window.addEventListener('resize', () => {
        resize();
        calcRadius();
        init();
    });

    window.addEventListener('mouseout', () => {
        mouse.x = undefined;
        mouse.y = undefined;
    });

    // Brand colors for particles
    const particleColors = [
        'rgba(249, 199, 79, 0.5)',   // Signal Yellow 50%
        'rgba(249, 199, 79, 0.3)',   // Signal Yellow 30%
        'rgba(212, 160, 48, 0.4)',   // Dark Gold 40%
        'rgba(255, 255, 255, 0.08)', // White ghost
        'rgba(249, 199, 79, 0.15)', // Yellow faint
    ];

    class Particle {
        constructor(x, y, directionX, directionY, size, color) {
            this.x = x;
            this.y = y;
            this.directionX = directionX;
            this.directionY = directionY;
            this.size = size;
            this.color = color;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
            ctx.fillStyle = this.color;
            ctx.fill();
        }
        update() {
            if (this.x > canvas.width || this.x < 0) this.directionX = -this.directionX;
            if (this.y > canvas.height || this.y < 0) this.directionY = -this.directionY;

            const dx = mouse.x - this.x;
            const dy = mouse.y - this.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < mouse.radius + this.size) {
                if (mouse.x < this.x && this.x < canvas.width - this.size * 10) this.x += 3;
                if (mouse.x > this.x && this.x > this.size * 10) this.x -= 3;
                if (mouse.y < this.y && this.y < canvas.height - this.size * 10) this.y += 3;
                if (mouse.y > this.y && this.y > this.size * 10) this.y -= 3;
            }
            this.x += this.directionX;
            this.y += this.directionY;
            this.draw();
        }
    }

    function init() {
        particlesArray = [];
        const count = Math.min((canvas.height * canvas.width) / 12000, 150);
        for (let i = 0; i < count; i++) {
            const size = (Math.random() * 2.5) + 0.5;
            const x = Math.random() * (canvas.width - size * 4) + size * 2;
            const y = Math.random() * (canvas.height - size * 4) + size * 2;
            const dirX = (Math.random() * 1.5) - 0.75;
            const dirY = (Math.random() * 1.5) - 0.75;
            const color = particleColors[Math.floor(Math.random() * particleColors.length)];
            particlesArray.push(new Particle(x, y, dirX, dirY, size, color));
        }
    }

    function connect() {
        for (let a = 0; a < particlesArray.length; a++) {
            for (let b = a; b < particlesArray.length; b++) {
                const dx = particlesArray[a].x - particlesArray[b].x;
                const dy = particlesArray[a].y - particlesArray[b].y;
                const distance = dx * dx + dy * dy;
                const threshold = (canvas.width / 8) * (canvas.height / 8);
                if (distance < threshold) {
                    const opacity = 1 - (distance / 25000);
                    ctx.strokeStyle = 'rgba(249, 199, 79,' + (opacity * 0.15) + ')';
                    ctx.lineWidth = 0.6;
                    ctx.beginPath();
                    ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                    ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                    ctx.stroke();
                }
            }
        }
    }

    let _animFrameId = null;

    function animate() {
        // Stop if login overlay is hidden (user signed in)
        const overlay = document.getElementById('login-overlay');
        if (overlay && overlay.style.display === 'none') {
            _animFrameId = null;
            return;
        }
        _animFrameId = requestAnimationFrame(animate);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < particlesArray.length; i++) {
            particlesArray[i].update();
        }
        connect();
    }

    // Expose stop for external callers (e.g. auth.js)
    window._stopLoginParticles = function() {
        if (_animFrameId) { cancelAnimationFrame(_animFrameId); _animFrameId = null; }
    };

    init();
    animate();
})();
