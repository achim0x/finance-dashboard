/* Finance Dashboard — vanilla JS: KPI detail toggle, expandable tranche
 * rows, value-history chart and per-position mini charts (Chart.js). */

/* KPI tiles: "more details" toggle */
document.addEventListener("click", function (ev) {
  const knopf = ev.target.closest("#details-umschalten");
  if (!knopf) return;
  const kacheln = document.getElementById("kpi-kacheln");
  const offen = kacheln.classList.toggle("details-offen");
  knopf.textContent = offen ? knopf.dataset.weniger : knopf.dataset.mehr;
});

/* Holdings: expand/collapse tranche rows */
document.addEventListener("click", function (ev) {
  const knopf = ev.target.closest(".aufklappen");
  if (!knopf) return;
  const ziel = document.getElementById(knopf.dataset.ziel);
  if (!ziel) return;
  ziel.hidden = !ziel.hidden;
  knopf.textContent = ziel.hidden ? "▸" : "▾";
});

/* Value-history line chart (dashboard) */
function fdWertverlaufInit() {
  const canvas = document.getElementById("wertverlauf");
  if (!canvas || typeof Chart === "undefined") return;
  fetch(canvas.dataset.url)
    .then((r) => r.json())
    .then((daten) => {
      new Chart(canvas, {
        type: "line",
        data: {
          labels: daten.labels,
          datasets: [{
            data: daten.werte,
            borderColor: "#134074",
            backgroundColor: "rgba(19, 64, 116, 0.08)",
            fill: true,
            pointRadius: 0,
            tension: 0.15,
          }],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: { x: { ticks: { maxTicksLimit: 10 } } },
          interaction: { intersect: false, mode: "index" },
        },
      });
    })
    .catch(() => {});
}

/* Per-position mini charts ("since purchase") */
function fdMiniChartsInit() {
  if (typeof Chart === "undefined") return;
  document.querySelectorAll("canvas.mini[data-url]").forEach(function (canvas) {
    fetch(canvas.dataset.url)
      .then((r) => r.json())
      .then((daten) => {
        if (!daten.werte || !daten.werte.length) return;
        const erste = daten.werte[0];
        const letzte = daten.werte[daten.werte.length - 1];
        const farbe = letzte >= erste ? "#1e7d32" : "#b3261e";
        new Chart(canvas, {
          type: "line",
          data: {
            labels: daten.labels,
            datasets: [{ data: daten.werte, borderColor: farbe, borderWidth: 1.5, pointRadius: 0 }],
          },
          options: {
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false } },
            animation: false,
            responsive: false,
          },
        });
      })
      .catch(() => {});
  });
}
