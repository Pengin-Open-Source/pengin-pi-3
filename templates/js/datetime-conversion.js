// templates/js/datetime-conversion.js
// Converts a UTC ISO datetime string into the viewer's local timezone for
// display. tobuwebprod re-implemented this same small function inline,
// separately, in ~5 different templates (comment threads, ticket card
// feeds, reopen-request lists) instead of loading it once - this is the
// one copy. Include with:
//   <script src="{% static 'js/datetime-conversion.js' %}"></script>
// then, per timestamp element:
//   var el = document.getElementById('some-timestamp-id');
//   el.textContent = convertUTCToLocal(el.dataset.utc);
function convertUTCToLocal(utcString) {
    if (!utcString) return '';
    var date = new Date(utcString);
    if (isNaN(date.getTime())) return utcString;
    return date.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit'
    });
}
