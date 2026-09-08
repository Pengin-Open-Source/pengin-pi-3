// templates/js/dropdown-hover.js
// Makes any Bootstrap dropdown open on mouse-hover instead of only on
// click, for elements marked with the `.hover-dropdown` class (extracted
// from tobuwebprod's nav_bar.html, where it was inlined and only applied
// to one specific "Tools" dropdown - this version applies to any element
// with the class, so it's reusable for any hover-menu, not just nav).
// Include with:
//   <script src="{% static 'js/dropdown-hover.js' %}"></script>
// and mark the dropdown's wrapping <li>/<div> with class="hover-dropdown".
document.addEventListener('DOMContentLoaded', function () {
    var dropdowns = document.querySelectorAll('.hover-dropdown');
    dropdowns.forEach(function (dd) {
        var menu = dd.querySelector('.dropdown-menu');
        if (!menu) return;
        dd.addEventListener('mouseenter', function () { menu.classList.add('show'); });
        dd.addEventListener('mouseleave', function () { menu.classList.remove('show'); });
    });
});
