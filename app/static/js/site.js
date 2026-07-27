(() => {
  let activeTrigger = null;

  function panelFor(trigger) {
    const panelId = trigger.getAttribute("aria-controls");
    return panelId ? document.getElementById(panelId) : null;
  }

  function closeDisclosure(trigger, returnFocus = false) {
    const panel = panelFor(trigger);
    const backdrop = document.querySelector("[data-disclosure-backdrop]");
    if (!panel) return;
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (backdrop) backdrop.hidden = true;
    if (returnFocus) trigger.focus();
    activeTrigger = null;
  }

  function openDisclosure(trigger) {
    const panel = panelFor(trigger);
    const backdrop = document.querySelector("[data-disclosure-backdrop]");
    if (!panel) return;
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    if (backdrop) backdrop.hidden = false;
    activeTrigger = trigger;
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-disclosure-button]");
    if (trigger) {
      event.preventDefault();
      if (trigger.getAttribute("aria-expanded") === "true") closeDisclosure(trigger, true);
      else openDisclosure(trigger);
      return;
    }
    if (event.target.closest("[data-disclosure-backdrop]") && activeTrigger) {
      closeDisclosure(activeTrigger, true);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeTrigger) closeDisclosure(activeTrigger, true);
  });
})();
