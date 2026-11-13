(() => {
  const markerTtlMs = 120000;
  const maxMarkerLifetimeMs = markerTtlMs;

  function consumeMarker(key) {
    if (!key) return false;

    try {
      const raw = window.sessionStorage.getItem(key);
      window.sessionStorage.removeItem(key);
      if (!raw) return false;

      const marker = JSON.parse(raw);
      return (
        marker &&
        Number.isFinite(marker.expiresAt) &&
        marker.expiresAt > Date.now() &&
        marker.expiresAt <= Date.now() + maxMarkerLifetimeMs
      );
    } catch {
      return false;
    }
  }

  function startFreshLogin() {
    const link = document.querySelector("[data-knora-reset-success-link]");
    if (!link) return;

    const key = link.getAttribute("data-knora-reset-success-key");
    const href = link.getAttribute("href");
    if (!key || !href) return;

    try {
      window.sessionStorage.setItem(
        key,
        JSON.stringify({ expiresAt: Date.now() + markerTtlMs }),
      );
      window.location.replace(href);
    } catch {
      // The server-rendered CTA remains usable when storage or navigation is blocked.
    }
  }

  function revealPasswordUpdatedNotice() {
    const notice = document.getElementById("knora-password-updated-notice");
    if (!notice) return;

    const key = notice.getAttribute("data-knora-reset-success-key");
    if (consumeMarker(key)) notice.hidden = false;
  }

  function bindSubmitLoading() {
    if (!document.querySelectorAll) return;

    document
      .querySelectorAll("#kc-form-login, #kc-register-form")
      .forEach((form) => {
        const submit = form.querySelector(
          "button[type='submit'], input[type='submit']",
        );
        if (!submit) return;
        const initiallyDisabled = submit.disabled;
        const reset = () => {
          form.removeAttribute("data-knora-pending");
          submit.disabled = initiallyDisabled;
          submit.removeAttribute("aria-busy");
          submit.classList.remove("knora-loading");
        };
        window.addEventListener("pageshow", reset);
        form.addEventListener("submit", (event) => {
          if (form.getAttribute("data-knora-pending") === "true") {
            event.preventDefault();
            return;
          }
          if (event.defaultPrevented) return;
          form.setAttribute("data-knora-pending", "true");
          submit.disabled = true;
          submit.setAttribute("aria-busy", "true");
          submit.classList.add("knora-loading");
          // A later validator can cancel; accepted navigation may suspend timers.
          setTimeout(() => {
            if (event.defaultPrevented) reset();
          }, 0);
        });
      });
  }

  startFreshLogin();
  revealPasswordUpdatedNotice();
  bindSubmitLoading();
})();
