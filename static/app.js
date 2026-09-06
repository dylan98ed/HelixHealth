document.body.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.xhr.status === 422) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

// Retain the previous results when the connection fails and make that state clear.
function searchFeedback(event, failed) {
  const target = event.detail.target || event.detail.requestConfig?.target;
  if (target?.id !== "patient-directory") return;
  const feedback = document.getElementById("search-feedback");
  if (feedback) feedback.hidden = !failed;
}

document.body.addEventListener("htmx:afterRequest", (event) => {
  searchFeedback(event, event.detail.failed && event.detail.xhr.status !== 422);
});
document.body.addEventListener("htmx:sendError", (event) => searchFeedback(event, true));
document.body.addEventListener("htmx:timeout", (event) => searchFeedback(event, true));
