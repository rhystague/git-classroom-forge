(() => {
  const provisionForm = document.getElementById("provision_form");
  const provisionButton = document.getElementById("provision_button");
  const provisionButtonLabel = document.getElementById("provision_button_label");
  const provisionButtonSpinner = document.getElementById("provision_button_spinner");
  const provisionProgress = document.getElementById("provision_progress");

  if (!provisionForm || !provisionButton || !provisionButtonLabel || !provisionButtonSpinner || !provisionProgress) {
    return;
  }

  provisionForm.addEventListener("submit", () => {
    provisionButton.disabled = true;
    provisionButtonLabel.textContent = "Provisioning...";
    provisionButtonSpinner.classList.remove("hidden");
    provisionProgress.classList.remove("hidden");
  });
})();
