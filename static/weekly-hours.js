const selectWeekdays = document.getElementById("select-weekdays");
selectWeekdays.hidden = false;
selectWeekdays.addEventListener("click", () => {
  for (const checkbox of document.querySelectorAll('#weekly-days input[type="checkbox"]')) {
    checkbox.checked = Number(checkbox.value) < 5;
  }
});
