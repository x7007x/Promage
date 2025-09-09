(function() {
    function showAlert(message, type) {
        var container = document.getElementById('alerts');
        if (!container) return;
        var colorBase = 'border-neutral-300 dark:border-neutral-700 bg-white/90 dark:bg-neutral-900/80';
        var colorText = 'text-neutral-900 dark:text-neutral-100';
        if (type === 'success') colorText = 'text-emerald-700 dark:text-emerald-400';
        if (type === 'error') colorText = 'text-rose-700 dark:text-rose-400';
        if (type === 'info') colorText = 'text-sky-700 dark:text-sky-400';

        var el = document.createElement('div');
        el.className = 'rounded-full border ' + colorBase + ' ' + colorText + ' px-4 py-2 text-sm shadow-none';
        el.textContent = message;

        container.appendChild(el);

        setTimeout(function() {
            el.classList.add('opacity-0');
            setTimeout(function() {
                if (el.parentNode) el.parentNode.removeChild(el);
            }, 200);
        }, 2400);

    }

    function setupTheme() {
        var root = document.documentElement;
        var saved = localStorage.getItem('theme');
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (saved === 'dark' || (!saved && prefersDark)) {
            root.classList.add('dark');
        }

        var themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', function() {
                var isDark = root.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
                if (window.lucide) window.lucide.createIcons();
            });
        }

    }

    function setupMobileMenu() {
        var mobileMenu = document.getElementById('mobileMenu');
        var menuToggle = document.getElementById('menuToggle');
        var closeMenu = document.getElementById('closeMenu');
        var menuIconOpen = document.getElementById('menuIconOpen');
        var menuIconClose = document.getElementById('menuIconClose');

        function openMenu() {
            if (!mobileMenu) return;
            mobileMenu.classList.remove('hidden');
            mobileMenu.classList.add('flex', 'open');
            if (menuIconOpen) menuIconOpen.classList.add('hidden');
            if (menuIconClose) menuIconClose.classList.remove('hidden');
            if (menuToggle) menuToggle.setAttribute('aria-expanded', 'true');
        }

        function hideMenu() {
            if (!mobileMenu) return;
            mobileMenu.classList.remove('open');
            setTimeout(() => {
                mobileMenu.classList.add('hidden');
                mobileMenu.classList.remove('flex');
            }, 300);
            if (menuIconOpen) menuIconOpen.classList.remove('hidden');
            if (menuIconClose) menuIconClose.classList.add('hidden');
            if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
        }

        if (menuToggle) {
            menuToggle.addEventListener('click', function() {
                var expanded = menuToggle.getAttribute('aria-expanded') === 'true';
                if (expanded) hideMenu();
                else openMenu();
            });
        }

        if (closeMenu) {
            closeMenu.addEventListener('click', hideMenu);
        }

        if (mobileMenu) {
            mobileMenu.addEventListener('click', function(e) {
                if (e.target === mobileMenu) hideMenu();
            });
        }

    }

    function setupLikes() {
        var likeButtons = document.querySelectorAll('.like-btn[data-like-id]');
        likeButtons.forEach(function(btn) {
            btn.addEventListener('click', async function() {
                var id = btn.getAttribute('data-like-id');
                var countEl = document.querySelector('[data-like-count="' + id + '"]');

                btn.disabled = true;

                try {
                    var res = await fetch('/api/like', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            id: id
                        })
                    });

                    var json = await res.json();

                    if (json.ok) {
                        if (countEl) countEl.textContent = json.likes;
                        var icon = btn.querySelector('svg');
                        if (icon) icon.classList.add('text-rose-600');
                        showAlert('Thanks for the like', 'success');
                    } else if (json.error === 'already_liked') {
                        showAlert('You already liked this image', 'info');
                    } else {
                        showAlert('Something went wrong', 'error');
                    }
                } catch (e) {
                    showAlert('Network error', 'error');
                } finally {
                    btn.disabled = false;
                }
            });
        });

    }

    function setupGalleryLightbox() {
        var cards = Array.from(document.querySelectorAll('figure[data-id]'));
        var lb = document.getElementById('lightbox');
        var lbImg = document.getElementById('lbImg');
        var lbInner = document.getElementById('lbInner');
        var lbClose = document.getElementById('lbClose');
        var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function openLightbox(src, alt) {
            if (!lb || !lbImg || !lbInner) return;

            lbImg.src = src;
            lbImg.alt = alt || 'Image preview';

            lb.classList.remove('hidden');
            lb.classList.add('flex', 'opacity-0');

            lbInner.classList.remove('scale-95');

            if (!reduceMotion) {
                requestAnimationFrame(function() {
                    lb.classList.add('transition-opacity', 'duration-300');
                    lb.classList.remove('opacity-0');
                    lb.classList.add('opacity-100');
                });
            } else {
                lb.classList.remove('opacity-0');
                lb.classList.add('opacity-100');
            }

            if (lbClose) lbClose.focus({
                preventScroll: true
            });

            document.addEventListener('keydown', onKeyClose);
            lb.addEventListener('click', onBackdrop);

            if (!reduceMotion) {
                lbInner.classList.add('transition-transform', 'duration-300');
                lbInner.classList.remove('scale-95');
                lbInner.classList.add('scale-100');
            } else {
                lbInner.classList.remove('scale-95');
                lbInner.classList.add('scale-100');
            }
        }

        function closeLightbox() {
            if (!lb || !lbInner || !lbImg) return;

            lb.classList.add('hidden');
            lb.classList.remove('flex', 'opacity-100', 'transition-opacity', 'duration-300');

            lbInner.classList.remove('transition-transform', 'duration-300', 'scale-100');
            lbInner.classList.add('scale-95');

            lbImg.src = '';

            document.removeEventListener('keydown', onKeyClose);
            lb.removeEventListener('click', onBackdrop);
        }

        function onKeyClose(e) {
            if (e.key === 'Escape') closeLightbox();
        }

        function onBackdrop(e) {
            if (e.target === lb) closeLightbox();
        }

        if (lbClose) lbClose.addEventListener('click', closeLightbox);

        cards.forEach(function(card) {
            var overlay = card.querySelector('[data-overlay]');

            card.addEventListener('pointerdown', function(e) {
                if (e.pointerType === 'touch') {
                    if (overlay) overlay.classList.add('opacity-100', 'translate-y-0');
                    card.dataset.skipNextClick = 'true';
                }
            }, {
                passive: true
            });

            card.addEventListener('pointerleave', function() {
                if (overlay) overlay.classList.remove('opacity-100', 'translate-y-0');
                card.dataset.skipNextClick = '';
            });

            card.addEventListener('click', function(e) {
                var promptLink = e.target.closest('a[href*="/prompt"]');
                if (promptLink) return;

                if (card.dataset.skipNextClick === 'true') {
                    card.dataset.skipNextClick = '';
                    return;
                }

                var src = card.getAttribute('data-src');
                var alt = card.getAttribute('data-alt');

                openLightbox(src, alt);
            });
        });

    }

    function setupBase() {
        var yearEl = document.getElementById('year');
        if (yearEl) yearEl.textContent = new Date().getFullYear();
        if (window.lucide) window.lucide.createIcons();

    }
    document.addEventListener('DOMContentLoaded', function() {
        window.showAlert = showAlert;
        setupTheme();

        setupMobileMenu();

        setupLikes();

        setupGalleryLightbox();

        setupBase();

    });
})();