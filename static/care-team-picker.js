(() => {
  const picker = document.getElementById("care-professional-picker");
  const select = document.getElementById("professional_dni");
  const label = document.getElementById("care-professional-label");
  const input = document.getElementById("care-professional-search");
  const list = document.getElementById("care-professional-options");
  const popup = picker.querySelector("[data-professional-popup]");
  const noResults = picker.querySelector("[data-professional-no-results]");

  function normalize(value) {
    return value.trim().normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  }

  const professionals = Array.from(select.options).slice(1).map((option) => ({
    dni: option.value,
    label: option.text,
    surname: normalize(option.dataset.surname),
    registration: normalize(option.dataset.registration),
  }));
  let matches = [];
  let activeIndex = -1;

  function activate(index) {
    list.children[activeIndex]?.classList.remove("active");
    activeIndex = index;
    const option = list.children[index];
    if (option) {
      option.classList.add("active");
      input.setAttribute("aria-activedescendant", option.id);
      option.scrollIntoView({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function showOptions() {
    const query = select.value ? "" : normalize(input.value);
    const dniQuery = /^[\d.\s]+$/.test(query) ? query.replace(/\D/g, "") : "";
    matches = professionals.filter((professional) =>
      professional.surname.includes(query) || professional.registration.includes(query) ||
      (dniQuery && professional.dni.includes(dniQuery))
    );
    activate(-1);
    list.replaceChildren(...matches.map((professional, index) => {
      const option = document.createElement("li");
      option.id = `care-professional-option-${index}`;
      option.className = "list-group-item list-group-item-action";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(professional.dni === select.value));
      option.dataset.index = index;
      option.textContent = professional.label;
      return option;
    }));
    noResults.hidden = matches.length > 0;
    list.scrollTop = 0;
    popup.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function closeOptions() {
    activate(-1);
    popup.hidden = true;
    input.setAttribute("aria-expanded", "false");
  }

  function choose(index) {
    const professional = matches[index];
    select.value = professional.dni;
    input.value = professional.label;
    input.setCustomValidity("");
    closeOptions();
  }

  select.required = false;
  select.hidden = true;
  picker.hidden = false;
  label.htmlFor = input.id;
  input.required = true;
  input.setCustomValidity("Choose a professional from the list.");

  input.addEventListener("focus", showOptions);
  input.addEventListener("click", () => {
    if (popup.hidden) showOptions();
  });
  input.addEventListener("blur", closeOptions);
  input.addEventListener("input", () => {
    select.value = "";
    input.setCustomValidity("Choose a professional from the list.");
    showOptions();
  });
  input.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (popup.hidden) showOptions();
      if (matches.length === 0) return;
      if (event.key === "ArrowDown") {
        activate(Math.min(activeIndex + 1, matches.length - 1));
      } else {
        activate(activeIndex < 0 ? matches.length - 1 : Math.max(activeIndex - 1, 0));
      }
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0) choose(activeIndex);
    } else if (event.key === "Escape" && !popup.hidden) {
      event.preventDefault();
      closeOptions();
    }
  });
  list.addEventListener("mousedown", (event) => {
    if (event.target.closest("[role=option]")) event.preventDefault();
  });
  list.addEventListener("click", (event) => {
    const option = event.target.closest("[role=option]");
    if (option) choose(Number(option.dataset.index));
  });
})();
