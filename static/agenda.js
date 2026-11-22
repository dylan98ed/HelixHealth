// Keep an open agenda usable as appointments start, using elapsed time since
// the server rendered it. The server checks the start again on every submission.
const agenda = document.querySelector("[data-agenda-time]");
if (agenda) {
  const serverTime = Date.parse(agenda.dataset.agendaTime);
  const loadedAt = performance.now();
  for (const button of agenda.querySelectorAll("button[data-absence-start]")) {
    const delay = Date.parse(button.dataset.absenceStart) - serverTime;
    function enableWhenDue() {
      const remaining = delay - (performance.now() - loadedAt);
      if (remaining > 0) {
        window.setTimeout(enableWhenDue, Math.min(remaining, 2147483647));
      } else {
        button.disabled = false;
        button.removeAttribute("title");
      }
    }
    enableWhenDue();
  }
}
