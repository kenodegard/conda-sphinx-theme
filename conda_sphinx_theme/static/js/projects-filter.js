(function () {
  "use strict";

  function init() {
    for (const menu of document.querySelectorAll(
      "#navbar-main-elements .dropdown-menu"
    )) {
      const bar = menu.querySelector(".conda-projects-filter");
      const input = bar && bar.querySelector("input");
      const empty = menu.querySelector(".conda-projects-empty");
      if (!input) continue;

      const items = Array.from(menu.querySelectorAll("li")).filter((li) =>
        li.querySelector(".dropdown-item.nav-external, .dropdown-item.nav-internal")
      );
      const headers = Array.from(menu.querySelectorAll(".dropdown-header"));
      const dividers = Array.from(
        menu.querySelectorAll(".conda-projects-divider")
      );

      const apply = () => {
        const query = input.value.trim().toLowerCase();
        let shown = 0;
        for (const li of items) {
          const match = !query || li.textContent.toLowerCase().includes(query);
          li.hidden = !match;
          if (match) shown += 1;
        }
        // a group header is only worth showing when its group still has entries
        const groupVisible = (group) =>
          items.some((li) => li.dataset.group === group && !li.hidden);
        for (const header of headers) {
          header.hidden = !groupVisible(header.dataset.group);
        }
        // a divider separates groups, so it needs both sides to be present
        for (const divider of dividers) {
          divider.hidden = !divider.dataset.groups
            .split(" ")
            .every(groupVisible);
        }
        if (empty) empty.hidden = shown > 0;
      };

      input.addEventListener("input", apply);
      input.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && input.value) {
          input.value = "";
          apply();
          event.stopPropagation();
        }
      });
      document.addEventListener("hidden.bs.dropdown", () => {
        input.value = "";
        apply();
      });

      // Only reveal the filter once it can actually filter something
      bar.hidden = false;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
