(function () {
  const dataEl = document.getElementById("stats-data");
  if (!dataEl) return;

  const payload = JSON.parse(dataEl.textContent || "{}");
  const palette = {
    navy: "#1d2f63",
    ink: "#101827",
    muted: "#64748b",
    green: "#3d9161",
    amber: "#d7922f",
    red: "#dc4a4a",
    blue: "#3562ff",
    line: "#d9e2f0",
  };

  const bytesLabel = (value) => {
    const units = ["B", "KB", "MB", "GB", "TB", "PB"];
    let size = Number(value || 0);
    for (const unit of units) {
      if (Math.abs(size) < 1024 || unit === units[units.length - 1]) {
        return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(2)} ${unit}`;
      }
      size /= 1024;
    }
    return "0 B";
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { boxWidth: 10, color: palette.muted, font: { size: 11, weight: "700" } } },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: palette.muted, font: { size: 11 } } },
      y: { grid: { color: "rgba(148, 163, 184, 0.18)" }, ticks: { color: palette.muted, font: { size: 11 } } },
    },
  };

  function renderChart(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas || !window.Chart) return;
    return new Chart(canvas, config);
  }

  renderChart("nodeResourceChart", {
    type: "bar",
    data: {
      labels: payload.nodes || [],
      datasets: [
        { label: "CPU %", data: payload.cpu || [], backgroundColor: "rgba(53,98,255,.72)", borderRadius: 8 },
        { label: "RAM %", data: payload.memory || [], backgroundColor: "rgba(61,145,97,.72)", borderRadius: 8 },
        { label: "Disk %", data: payload.disk || [], backgroundColor: "rgba(215,146,47,.72)", borderRadius: 8 },
      ],
    },
    options: {
      ...baseOptions,
      scales: { ...baseOptions.scales, y: { ...baseOptions.scales.y, min: 0, max: 100 } },
    },
  });

  renderChart("userTrafficChart", {
    type: "bar",
    data: {
      labels: payload.users || [],
      datasets: [
        {
          label: "30d traffic",
          data: payload.userTraffic || [],
          backgroundColor: "rgba(29,47,99,.78)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        tooltip: { callbacks: { label: (ctx) => bytesLabel(ctx.raw) } },
      },
      scales: {
        ...baseOptions.scales,
        y: { ...baseOptions.scales.y, ticks: { callback: bytesLabel, color: palette.muted, font: { size: 11 } } },
      },
    },
  });

  renderChart("projectionChart", {
    type: "line",
    data: {
      labels: (payload.projections && payload.projections.labels) || [],
      datasets: [
        {
          label: "Projected traffic",
          data: (payload.projections && payload.projections.traffic) || [],
          borderColor: palette.green,
          backgroundColor: "rgba(61,145,97,.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 4,
        },
      ],
    },
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        tooltip: { callbacks: { label: (ctx) => bytesLabel(ctx.raw) } },
      },
      scales: {
        ...baseOptions.scales,
        y: { ...baseOptions.scales.y, ticks: { callback: bytesLabel, color: palette.muted, font: { size: 11 } } },
      },
    },
  });

  document.querySelectorAll("[data-filter-target]").forEach((input) => {
    const table = document.querySelector(input.dataset.filterTarget);
    if (!table) return;
    input.addEventListener("input", () => {
      const needle = input.value.trim().toLowerCase();
      table.querySelectorAll("tbody tr").forEach((row) => {
        row.hidden = needle && !row.textContent.toLowerCase().includes(needle);
      });
    });
  });
})();
