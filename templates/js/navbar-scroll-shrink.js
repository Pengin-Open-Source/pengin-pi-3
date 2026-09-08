// templates/js/navbar-scroll-shrink.js
// Shrinks a fixed navbar's padding/logo/margins once the page scrolls past
// a threshold, and restores them back at the top. Extracted from
// tobuwebprod's nav_bar.html (where it was inlined and hardcoded to that
// page's exact element ids) into a small, parameterized helper - call it
// once with the element ids your nav actually uses:
//   <script src="{% static 'js/navbar-scroll-shrink.js' %}"></script>
//   <script>
//     initNavbarScrollShrink({
//       navId: 'mainNav', shieldId: 'desktopBrandShield',
//       linksId: 'desktopNavLinks', authZoneId: 'desktopAuthZone',
//     });
//   </script>
function initNavbarScrollShrink(opts) {
    opts = opts || {};
    var nav = document.getElementById(opts.navId);
    var shield = document.getElementById(opts.shieldId);
    var links = document.getElementById(opts.linksId);
    var authZone = opts.authZoneId ? document.getElementById(opts.authZoneId) : null;
    if (!nav || !shield || !links) return;

    var shrunk = opts.shrunk || { navPad: 'py-1', shieldSize: 145, shieldPad: 8, marginLeft: 160, authOpacity: 0.85 };
    var full = opts.full || { navPad: 'py-4', shieldSize: 195, shieldPad: 16, marginLeft: 215, authOpacity: 1 };
    var threshold = opts.threshold || 60;

    function toggle() {
        var isShrunk = window.scrollY > threshold;
        var state = isShrunk ? shrunk : full;
        nav.classList.remove(isShrunk ? full.navPad : shrunk.navPad);
        nav.classList.add(state.navPad);
        shield.style.width = state.shieldSize + 'px';
        shield.style.height = (state.shieldSize * 0.846) + 'px';
        shield.style.padding = state.shieldPad + 'px';
        links.style.marginLeft = state.marginLeft + 'px';
        if (authZone) authZone.style.opacity = state.authOpacity;
    }

    toggle();
    window.addEventListener('scroll', toggle);
    window.addEventListener('DOMContentLoaded', toggle);
}
