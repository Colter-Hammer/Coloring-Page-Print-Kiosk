// Progressive enhancement only — every form here works fine without JS.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const message = form.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
  const output = input.closest("[data-file-field]")?.querySelector("[data-file-summary]");
  if (!output) return;
  const count = input.files ? input.files.length : 0;
  if (count === 0) {
    output.textContent = output.dataset.default || "";
  } else if (count === 1) {
    output.textContent = input.files[0].name;
  } else {
    output.textContent = `${count} files selected`;
  }
});
