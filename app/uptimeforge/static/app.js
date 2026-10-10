"use strict";
const dialog = document.querySelector("#monitor-dialog");
const form = document.querySelector("#monitor-form");
const formError = document.querySelector("#form-error");
const notice = document.querySelector("#notice");

async function api(path, method = "GET", body) {
  const response = await fetch(path, {
    method, credentials: "same-origin",
    headers: {"Content-Type": "application/json", "X-UptimeForge-Request": "1"},
    ...(body ? {body: JSON.stringify(body)} : {}),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const details = data.error?.details?.map(item => item.message).join("; ");
    throw new Error(details || data.error?.message || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}
function showError(error) {
  notice.textContent = error.message || "Something went wrong. Please try again.";
  notice.hidden = false;
  notice.scrollIntoView({behavior: "smooth", block: "nearest"});
}
function openForm(monitor) {
  form.reset(); formError.hidden = true;
  form.elements.id.value = monitor?.id || "";
  form.elements.name.value = monitor?.name || "";
  form.elements.url.value = monitor?.url || "";
  form.elements.interval_seconds.value = monitor?.interval_seconds || 60;
  document.querySelector("#dialog-title").textContent = monitor ? "Edit monitor" : "Add a monitor";
  dialog.showModal();
}
document.querySelectorAll("[data-add]").forEach(button => button.addEventListener("click", () => openForm()));
document.querySelectorAll("[data-close]").forEach(button => button.addEventListener("click", () => dialog.close()));
form.addEventListener("submit", async event => {
  event.preventDefault();
  const button = form.querySelector('[type="submit"]');
  button.disabled = true; button.textContent = "Saving…"; formError.hidden = true;
  const id = form.elements.id.value;
  try {
    await api(`/api/monitors${id ? `/${id}` : ""}`, id ? "PATCH" : "POST", {
      name: form.elements.name.value, url: form.elements.url.value,
      interval_seconds: Number(form.elements.interval_seconds.value),
    });
    window.location.reload();
  } catch (error) {formError.textContent = error.message; formError.hidden = false;}
  finally {button.disabled = false; button.textContent = "Save monitor";}
});
document.querySelectorAll("[data-check]").forEach(button => button.addEventListener("click", async () => {
  const label = button.textContent; button.disabled = true; button.textContent = "Checking…";
  try {await api(`/api/monitors/${button.dataset.check}/check`, "POST"); window.location.reload();}
  catch (error) {showError(error);}
  finally {button.disabled = false; button.textContent = label;}
}));
document.querySelectorAll("[data-edit]").forEach(button => button.addEventListener("click", async () => {
  button.disabled = true;
  try {openForm(await api(`/api/monitors/${button.dataset.edit}`));}
  catch (error) {showError(error);}
  finally {button.disabled = false;}
}));
document.querySelectorAll("[data-delete]").forEach(button => button.addEventListener("click", async () => {
  if (!window.confirm("Delete this monitor and all its check history? This cannot be undone.")) return;
  button.disabled = true;
  try {await api(`/api/monitors/${button.dataset.delete}`, "DELETE"); window.location.assign("/");}
  catch (error) {showError(error); button.disabled = false;}
}));
document.querySelector("#search")?.addEventListener("input", event => {
  const query = event.target.value.toLowerCase(); let visible = 0;
  document.querySelectorAll("[data-monitor-row]").forEach(row => {
    row.hidden = !row.dataset.name.includes(query); if (!row.hidden) visible++;
  });
  document.querySelector("#search-empty").hidden = visible !== 0;
});

// A small native canvas chart, with no external assets or frontend build step.
const canvas = document.querySelector("#response-chart");
const chart = JSON.parse(document.querySelector("#chart-data")?.textContent || "[]");
function drawChart() {
  if (!canvas) return;
  document.querySelector("#chart-empty").hidden = chart.length > 0;
  const ctx = canvas.getContext("2d"), rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = rect.width * ratio; canvas.height = rect.height * ratio; ctx.scale(ratio, ratio);
  const left = 50, top = 18, width = rect.width - 70, height = rect.height - 50;
  const maximum = Math.max(100, ...chart.map(point => point.response_time_ms)) * 1.15;
  ctx.font = "10px system-ui";
  for (let tick = 0; tick <= 4; tick++) {
    const y = top + height * tick / 4;
    ctx.strokeStyle = "#252a37"; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + width, y); ctx.stroke();
    ctx.fillStyle = "#788499"; ctx.fillText(`${Math.round(maximum * (1 - tick / 4))}`, 5, y + 3);
  }
  if (!chart.length) return;
  const points = chart.map((point, index) => [left + (chart.length === 1 ? width / 2 : width * index / (chart.length - 1)), top + height * (1 - point.response_time_ms / maximum)]);
  const gradient = ctx.createLinearGradient(0, top, 0, top + height);
  gradient.addColorStop(0, "#a492ff30"); gradient.addColorStop(1, "#a492ff00");
  ctx.beginPath(); ctx.moveTo(points[0][0], top + height);
  points.forEach(([x, y]) => ctx.lineTo(x, y)); ctx.lineTo(points.at(-1)[0], top + height); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath(); points.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.strokeStyle = "#b09cff"; ctx.lineWidth = 2; ctx.stroke();
  points.forEach(([x, y], index) => {ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fillStyle = chart[index].status === "DOWN" ? "#fa8293" : "#b09cff"; ctx.fill();});
  const label = point => new Date(point.checked_at).toISOString().slice(11, 19) + " UTC";
  ctx.fillStyle = "#788499"; ctx.fillText(label(chart[0]), left, rect.height - 8);
  if (chart.length > 1) {ctx.textAlign = "right"; ctx.fillText(label(chart.at(-1)), left + width, rect.height - 8); ctx.textAlign = "left";}
}
if (canvas) new ResizeObserver(drawChart).observe(canvas.parentElement);
