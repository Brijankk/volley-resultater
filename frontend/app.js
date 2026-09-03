const DATA_ROOT = "../data/json";
const DATA_VERSION = "2026-08-28T013000";
const DATA_CACHE = "volley-data-v5";

const state = {
  metadata: null,
  poolData: null,
  selectedSeason: "",
  selectedGender: "",
  selectedLeagueId: "",
  selectedPoolId: "",
  chartMode: "game",
  scheduleRange: "nearby",
  selectedScheduleTeam: "",
  scheduleSide: "all",
  selectedPair: null,
  installPrompt: null,
};

const colors = [
  "#0b6b78",
  "#b63446",
  "#d49b2a",
  "#13795b",
  "#6146a6",
  "#c45f22",
  "#2f6db3",
  "#7a5b3a",
  "#4e7d36",
  "#a13e7a",
];

const teamAbbreviations = [
  ["Aalborg Volleyball", "AAV"],
  ["Aarhus 1900", "1900"],
  ["ASV Aarhus", "ASV"],
  ["ASV Elite", "ASV"],
  ["DHV Odense", "DHV"],
  ["DSIO Odense", "DSIO"],
  ["Fortuna Odense Volley", "Fortuna"],
  ["Frederiksberg", "Fr.berg"],
  ["Lyngby-Gladsaxe Volley", "LGV"],
  ["Lynge Uggeløse IF", "LUIF"],
  ["Marienlyst-Fortuna", "Marienlyst"],
  ["Nordenskov UIF", "NUIF"],
  ["Nordenskov Ungdoms-og IF", "NUIF"],
  ["UVS-Nordenskov", "Nordenskov"],
  ["Vendsyssel", "Vends."],
  ["Vestsjælland", "Vestsj."],
  ["Wildcard", "WC"],
  [" Volleyball", ""],
  [" Volley", ""],
  [" KFUM", ""],
  [" VK", ""],
  [" IF", ""],
  [" FIF", ""],
  [" FVK", ""],
  [" G&I", ""],
  [" G & I", ""],
  [" I&G", ""],
  [" GF", ""],
  [" EV", ""],
  [" VBC", ""],
  ["Volleyball ", ""],
  ["IF ", ""],
  ["VK ", ""],
  ["SGF ", ""],
  ["SIK ", ""],
  ["RS ", ""],
  ["Team ", ""],
];

const els = {
  status: document.querySelector("#status"),
  seasonSelect: document.querySelector("#seasonSelect"),
  genderControl: document.querySelector("#genderControl"),
  leagueSelect: document.querySelector("#leagueSelect"),
  poolField: document.querySelector("#poolField"),
  poolSelect: document.querySelector("#poolSelect"),
  connectionStatus: document.querySelector("#connectionStatus"),
  updatedStatus: document.querySelector("#updatedStatus"),
  validationMeta: document.querySelector("#validationMeta"),
  scheduleRangeControl: document.querySelector("#scheduleRangeControl"),
  scheduleTeamSelect: document.querySelector("#scheduleTeamSelect"),
  scheduleSideControl: document.querySelector("#scheduleSideControl"),
  scheduleBody: document.querySelector("#scheduleBody"),
  scheduleEmpty: document.querySelector("#scheduleEmpty"),
  standingsBody: document.querySelector("#standingsBody"),
  chartModeControl: document.querySelector("#chartModeControl"),
  chart: document.querySelector("#pointsChart"),
  legend: document.querySelector("#chartLegend"),
  matrixWrap: document.querySelector("#matrixWrap"),
  matchDetailContent: document.querySelector("#matchDetailContent"),
  installButton: document.querySelector("#installButton"),
};

async function init() {
  try {
    state.metadata = await fetchJson(dataUrl(`${DATA_ROOT}/leagues.json`));
    initializeSelection();
    bindEvents();
    await loadSelectedPool();
    els.status.textContent = "Ready";
    prefetchAllPoolData();
  } catch (error) {
    els.status.textContent = "Kunne ikke indlæse data";
    console.error(error);
  }
}

function initializeSelection() {
  const seasons = unique(state.metadata.leagues.map((league) => league.season_id)).sort((a, b) =>
    b.localeCompare(a, "da"),
  );
  state.selectedSeason = seasons[0] || "";
  fillSelect(els.seasonSelect, seasons.map((season) => ({ value: season, label: seasonLabel(season) })));

  const genders = unique(state.metadata.leagues.map((league) => league.gender));
  state.selectedGender = genders.includes("Mand") ? "Mand" : genders[0] || "";
  renderGenderButtons(genders);
  updateLeagueOptions();
  updatePoolOptions();
}

function bindEvents() {
  els.seasonSelect.addEventListener("change", async () => {
    state.selectedSeason = els.seasonSelect.value;
    updateLeagueOptions();
    updatePoolOptions();
    await loadSelectedPool();
  });

  els.leagueSelect.addEventListener("change", async () => {
    state.selectedLeagueId = els.leagueSelect.value;
    updatePoolOptions();
    await loadSelectedPool();
  });

  els.poolSelect.addEventListener("change", async () => {
    state.selectedPoolId = els.poolSelect.value;
    await loadSelectedPool();
  });

  els.scheduleRangeControl.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.scheduleRange = button.dataset.range;
    setActiveButton(els.scheduleRangeControl, button);
    renderSchedule();
  });

  els.scheduleTeamSelect.addEventListener("change", () => {
    state.selectedScheduleTeam = els.scheduleTeamSelect.value;
    if (!state.selectedScheduleTeam) {
      state.scheduleSide = "all";
      setActiveButtonByData(els.scheduleSideControl, "side", "all");
    }
    renderScheduleControls();
    renderSchedule();
  });

  els.scheduleSideControl.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.scheduleSide = button.dataset.side;
    setActiveButton(els.scheduleSideControl, button);
    renderSchedule();
  });

  els.chartModeControl.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.chartMode = button.dataset.mode;
    setActiveButton(els.chartModeControl, button);
    renderChart();
  });

  els.matrixWrap.addEventListener("click", (event) => {
    const cell = event.target.closest("[data-home-team]");
    if (!cell) return;
    state.selectedPair = { home: cell.dataset.homeTeam, away: cell.dataset.awayTeam };
    renderMatrix();
    renderMatchDetail();
  });
  els.matrixWrap.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const cell = event.target.closest("[data-home-team]");
    if (!cell) return;
    event.preventDefault();
    state.selectedPair = { home: cell.dataset.homeTeam, away: cell.dataset.awayTeam };
    renderMatrix();
    renderMatchDetail();
  });

  window.addEventListener("online", renderDataMeta);
  window.addEventListener("offline", renderDataMeta);
  window.addEventListener("resize", debounce(renderChart, 120));

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    state.installPrompt = event;
    els.installButton.classList.remove("hidden");
  });

  window.addEventListener("appinstalled", () => {
    state.installPrompt = null;
    els.installButton.classList.add("hidden");
  });

  els.installButton.addEventListener("click", async () => {
    if (!state.installPrompt) return;
    const promptEvent = state.installPrompt;
    state.installPrompt = null;
    els.installButton.classList.add("hidden");
    promptEvent.prompt();
    await promptEvent.userChoice;
  });
}

function renderGenderButtons(genders) {
  const row = document.createElement("div");
  row.className = "segment-row";
  const sortedGenders = [...genders].sort((a, b) => genderLabel(a).localeCompare(genderLabel(b), "da"));
  for (const gender of sortedGenders) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = genderLabel(gender);
    button.classList.toggle("active", gender === state.selectedGender);
    button.addEventListener("click", async () => {
      state.selectedGender = gender;
      for (const item of row.querySelectorAll("button")) {
        item.classList.toggle("active", item === button);
      }
      updateLeagueOptions();
      updatePoolOptions();
      await loadSelectedPool();
    });
    row.append(button);
  }
  els.genderControl.append(row);
}

function updateLeagueOptions() {
  const leagues = state.metadata.leagues
    .filter((league) => league.season_id === state.selectedSeason && league.gender === state.selectedGender)
    .sort((a, b) => divisionWeight(a.division) - divisionWeight(b.division));

  if (!leagues.some((league) => league.id === state.selectedLeagueId)) {
    state.selectedLeagueId = leagues[0]?.id || "";
  }
  fillSelect(
    els.leagueSelect,
    leagues.map((league) => ({ value: league.id, label: league.division })),
  );
  els.leagueSelect.value = state.selectedLeagueId;
}

function updatePoolOptions() {
  const pools = poolsForLeague(state.selectedLeagueId);
  if (!pools.some((pool) => pool.id === state.selectedPoolId)) {
    state.selectedPoolId = pools[0]?.id || "";
  }
  fillSelect(
    els.poolSelect,
    pools.map((pool) => ({ value: pool.id, label: pool.name })),
  );
  els.poolSelect.value = state.selectedPoolId;
  els.poolField.classList.toggle("hidden", pools.length <= 1);
}

async function loadSelectedPool() {
  if (!state.selectedPoolId) return;
  els.status.textContent = "Indlæser række";
  state.selectedPair = null;
  state.poolData = await fetchJson(dataUrl(`${DATA_ROOT}/${safeFilename(state.selectedPoolId)}.json`));
  normalizeScheduleFilters();
  renderAll();
  els.status.textContent = "Ready";
}

function renderAll() {
  renderDataMeta();
  renderScheduleControls();
  renderSchedule();
  renderStandings();
  renderChart();
  renderMatrix();
  renderMatchDetail();
}

function renderDataMeta() {
  if (!state.metadata || !state.poolData) return;
  const metadata = state.metadata.metadata || {};
  const validation = state.poolData.metadata?.validation || poolValidationFor(state.selectedPoolId);
  const exported = metadata.exported_at ? formatDateTime(metadata.exported_at) : "Ukendt";

  els.connectionStatus.textContent = navigator.onLine ? "Online" : "Offline - viser gemte data";
  els.connectionStatus.className = `status-pill ${navigator.onLine ? "data-online" : "data-offline"}`;
  els.updatedStatus.textContent = `Senest opdateret: ${exported}`;
  els.updatedStatus.className = "status-pill";

  const hasWarning = validation.mismatch_count > 0;
  els.validationMeta.className = `validation-meta ${hasWarning ? "data-warning" : "data-ok"}`;
  els.validationMeta.textContent = hasWarning
    ? `Officiel stilling og beregnet udvikling afviger i ${validation.mismatch_count} felter.`
    : "Officiel stilling og beregnet udvikling stemmer overens.";
}

function renderScheduleControls() {
  const teams = scheduleTeams();
  const options = [{ value: "", label: "Alle hold" }, ...teams.map((team) => ({ value: team, label: team }))];
  fillSelect(els.scheduleTeamSelect, options);
  els.scheduleTeamSelect.value = state.selectedScheduleTeam;
  els.scheduleSideControl.classList.toggle("hidden", !state.selectedScheduleTeam);
  setActiveButtonByData(els.scheduleRangeControl, "range", state.scheduleRange);
  setActiveButtonByData(els.scheduleSideControl, "side", state.scheduleSide);
}

function renderSchedule() {
  const rows = filteredScheduleMatches();
  els.scheduleBody.innerHTML = rows.map((match) => renderScheduleRow(match)).join("");
  els.scheduleEmpty.classList.toggle("hidden", rows.length > 0);
}

function renderScheduleRow(match) {
  const result = formatScheduleResult(match);
  return `
    <tr>
      <td data-label="Dato" class="schedule-date-cell">${renderScheduleDateTime(match)}</td>
      <td data-label="Hjemme" class="team-cell" title="${escapeHtml(match.home_team)}">${escapeHtml(match.home_team)}</td>
      <td data-label="Ude" class="team-cell" title="${escapeHtml(match.away_team)}">${escapeHtml(match.away_team)}</td>
      <td data-label="Spillested">${formatScheduleVenue(match)}</td>
      <td data-label="Resultat" class="schedule-result ${result ? "" : "pending"}">${escapeHtml(result)}</td>
    </tr>
  `;
}

function filteredScheduleMatches() {
  let matches = sortedMatches(state.poolData?.matches || []);
  if (state.selectedScheduleTeam) {
    matches = matches.filter((match) => {
      if (state.scheduleSide === "home") return match.home_team === state.selectedScheduleTeam;
      if (state.scheduleSide === "away") return match.away_team === state.selectedScheduleTeam;
      return match.home_team === state.selectedScheduleTeam || match.away_team === state.selectedScheduleTeam;
    });
  }
  if (state.scheduleRange === "nearby") {
    const now = Date.now();
    const latest = matches.filter((match) => matchDateValue(match) <= now).slice(-5);
    const next = matches.filter((match) => matchDateValue(match) > now).slice(0, 5);
    matches = sortedMatches([...latest, ...next]);
  }
  return matches;
}

function normalizeScheduleFilters() {
  const teams = scheduleTeams();
  if (!teams.includes(state.selectedScheduleTeam)) {
    state.selectedScheduleTeam = "";
    state.scheduleSide = "all";
  }
}

function scheduleTeams() {
  if (!state.poolData) return [];
  const standingsTeams = state.poolData.source_standings.map((row) => row.team_name);
  const matchTeams = (state.poolData.matches || []).flatMap((match) => [match.home_team, match.away_team]);
  return unique([...standingsTeams, ...matchTeams]).filter(Boolean);
}

function sortedMatches(matches) {
  return [...matches].sort(compareMatches);
}

function compareMatches(left, right) {
  return matchDateValue(left) - matchDateValue(right) || (left.match_number || 0) - (right.match_number || 0);
}

function matchDateValue(match) {
  return match.starts_at ? new Date(match.starts_at).getTime() : Number.POSITIVE_INFINITY;
}

function renderStandings() {
  const rows = state.poolData.source_standings;
  els.standingsBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.rank}</td>
          <td>${escapeHtml(row.team_name)}</td>
          <td>${row.points}</td>
          <td>${row.games_played}</td>
          <td>${row.games_won}</td>
          <td>${row.games_lost}</td>
          <td>${row.sets_won}-${row.sets_lost}</td>
          <td>${row.balls_won}-${row.balls_lost}</td>
        </tr>
      `,
    )
    .join("");
}

function renderChart() {
  if (!state.poolData) return;
  const canvas = els.chart;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(600, Math.floor(rect.width * ratio));
  canvas.height = Math.max(340, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  const width = canvas.width / ratio;
  const height = canvas.height / ratio;
  ctx.clearRect(0, 0, width, height);

  const chartData = buildChartData(state.poolData.cumulative_points, state.chartMode);
  const dataByTeam = chartData.byTeam;
  const teams = state.poolData.source_standings.map((row) => row.team_name);
  const maxY = yAxisMax(Math.max(1, ...Object.values(dataByTeam).flat().map((point) => point.y)));
  const minX = chartData.minX;
  const maxX = chartData.maxX;
  const pad = { left: 42, right: 14, top: 18, bottom: 34 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  drawGrid(ctx, width, height, pad, maxY, chartData);
  teams.forEach((team, index) => {
    const points = dataByTeam[team] || [];
    if (points.length === 0) return;
    ctx.beginPath();
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = colors[index % colors.length];
    points.forEach((point, pointIndex) => {
      const x = pad.left + ((point.x - minX) / Math.max(1, maxX - minX)) * plotW;
      const y = pad.top + plotH - (point.y / maxY) * plotH;
      if (pointIndex === 0) ctx.moveTo(x, y);
      else if (state.chartMode === "date") {
        const previous = points[pointIndex - 1];
        const previousX = pad.left + ((previous.x - minX) / Math.max(1, maxX - minX)) * plotW;
        const previousY = pad.top + plotH - (previous.y / maxY) * plotH;
        ctx.lineTo(x, previousY);
        ctx.lineTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    ctx.fillStyle = colors[index % colors.length];
    points.forEach((point) => {
      const x = pad.left + ((point.x - minX) / Math.max(1, maxX - minX)) * plotW;
      const y = pad.top + plotH - (point.y / maxY) * plotH;
      ctx.beginPath();
      ctx.arc(x, y, 3.2, 0, Math.PI * 2);
      ctx.fill();
    });
  });

  ctx.fillStyle = "#60707a";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(state.chartMode === "game" ? "Spillede kampe" : "Sæsonforløb", pad.left, height - 8);
  ctx.save();
  ctx.translate(12, pad.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Point", 0, 0);
  ctx.restore();

  els.legend.innerHTML = teams
    .map(
      (team, index) => `
        <span class="legend-item" title="${escapeHtml(team)}">
          <span class="swatch" style="background:${colors[index % colors.length]}"></span>
          ${escapeHtml(shortTeam(team))}
        </span>
      `,
    )
    .join("");
}

function drawGrid(ctx, width, height, pad, maxY, chartData) {
  const plotH = height - pad.top - pad.bottom;
  const plotW = width - pad.left - pad.right;
  ctx.strokeStyle = "#d9e2e4";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#60707a";
  ctx.font = "11px system-ui, sans-serif";

  for (const tick of chartData.xTicks) {
    const x = pad.left + ((tick.value - chartData.minX) / Math.max(1, chartData.maxX - chartData.minX)) * plotW;
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, pad.top + plotH);
    ctx.stroke();
    ctx.save();
    ctx.translate(x, height - 21);
    ctx.rotate(-Math.PI / 5);
    ctx.textAlign = "right";
    ctx.fillText(tick.label, 0, 0);
    ctx.restore();
  }

  for (const value of yTicks(maxY)) {
    const y = pad.top + plotH - (value / maxY) * plotH;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + plotW, y);
    ctx.stroke();
    ctx.fillText(String(value), 8, y + 4);
  }
  ctx.strokeStyle = "#8fa0a8";
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(width - pad.right, pad.top + plotH);
  ctx.stroke();
}

function renderMatrix() {
  const matrix = state.poolData.result_matrix;
  const teams = state.poolData.source_standings.map((row) => row.team_name);
  const header = `<tr><th scope="col"></th>${teams.map((team) => `<th scope="col" title="${escapeHtml(team)}">${escapeHtml(shortTeam(team))}</th>`).join("")}</tr>`;
  const body = teams
    .map((home) => {
      const cells = teams
        .map((away) => {
          const value = matrix[home]?.[away] ?? "";
          const className = [matrixClass(value), home === away ? "diagonal" : ""].filter(Boolean).join(" ");
          const matches = findMatrixMatches(home, away);
          const selected = state.selectedPair?.home === home && state.selectedPair?.away === away ? " selected" : "";
          const attrs = matches.length ? ` data-home-team="${escapeHtml(home)}" data-away-team="${escapeHtml(away)}" tabindex="0"` : "";
          return `<td class="${className}${selected}"${attrs}>${escapeHtml(value || "")}</td>`;
        })
        .join("");
      return `<tr><th scope="row" title="${escapeHtml(home)}">${escapeHtml(shortTeam(home))}</th>${cells}</tr>`;
    })
    .join("");
  els.matrixWrap.innerHTML = `<table class="matrix-table">${header}${body}</table>`;
}

function renderMatchDetail() {
  if (!state.selectedPair) {
    els.matchDetailContent.className = "match-detail-empty";
    els.matchDetailContent.textContent = "Vælg en kamp i matrixen.";
    return;
  }
  const matches = findMatrixMatches(state.selectedPair.home, state.selectedPair.away);
  if (!matches.length) return;
  els.matchDetailContent.className = "match-detail";
  els.matchDetailContent.innerHTML = `
    <div class="match-detail-heading">
      <strong>${escapeHtml(state.selectedPair.home)} - ${escapeHtml(state.selectedPair.away)}</strong>
      <span>${matches.length} ${matches.length === 1 ? "kamp" : "kampe"}</span>
    </div>
    ${matches.map((match) => renderMatchDetailItem(match)).join("")}
  `;
}

function renderMatchDetailItem(match) {
  const sets = state.poolData.set_results
    .filter((set) => set.kamp_id === match.kamp_id && set.home_points !== null && set.away_points !== null)
    .sort((a, b) => a.set_number - b.set_number);
  const hasResult = match.result_home_sets !== null && match.result_away_sets !== null;
  return `
    <article class="match-detail-card">
      <div class="match-detail-main">
        <span>${formatMatchDateTime(match)}</span>
        <span>${formatVenue(match)}</span>
      </div>
      <div class="match-detail-score ${hasResult ? "" : "pending"}">${
        hasResult ? `${match.result_home_sets}-${match.result_away_sets}` : "Ikke spillet"
      }</div>
      ${
        sets.length
          ? `<table class="set-table">
              <tbody>
                <tr>
                  <th>Sæt</th>
                  ${sets.map((set) => `<td>${set.set_number}</td>`).join("")}
                </tr>
                <tr>
                  <th>Hjemme</th>
                  ${sets.map((set) => `<td>${set.home_points}</td>`).join("")}
                </tr>
                <tr>
                  <th>Ude</th>
                  ${sets.map((set) => `<td>${set.away_points}</td>`).join("")}
                </tr>
              </tbody>
            </table>`
          : ""
      }
    </article>
  `;
}

function findMatrixMatches(home, away) {
  return state.poolData.matches
    .filter((match) => match.home_team === home && match.away_team === away)
    .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
}

function buildChartData(events, mode) {
  const datedValues = events.filter((event) => event.date).map((event) => new Date(event.date).getTime());
  const rawMinDate = datedValues.length ? Math.min(...datedValues) : 0;
  const rawMaxDate = datedValues.length ? Math.max(...datedValues) : 1;
  const dateMin = mode === "date" ? firstDayOfMonth(rawMinDate).getTime() : 0;
  const dateMax = mode === "date" ? rawMaxDate : 1;
  const byTeam = {};
  const allX = [];
  for (const event of events) {
    if (!byTeam[event.team]) byTeam[event.team] = [];
    const x =
      mode === "game"
        ? event.game_number
        : event.date
          ? new Date(event.date).getTime()
          : dateMin;
    allX.push(x);
    byTeam[event.team].push({ x, y: event.cumulative_points });
  }
  const minX = mode === "game" ? 0 : dateMin;
  const maxX = mode === "game" ? Math.max(1, ...allX) : dateMax;
  return {
    byTeam,
    minX,
    maxX,
    xTicks: mode === "game" ? gameTicks(maxX) : monthTicks(minX, maxX),
  };
}

function poolsForLeague(leagueId) {
  return state.metadata.pools
    .filter((pool) => pool.league_id === leagueId)
    .sort((a, b) => poolWeight(a.name) - poolWeight(b.name) || a.name.localeCompare(b.name, "da"));
}

function poolValidationFor(poolId) {
  return state.metadata.pool_validation?.[poolId] || {
    mismatch_count: 0,
    affected_teams: 0,
    affected_fields: [],
  };
}

async function fetchJson(path) {
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Kunne ikke indlæse ${path}`);
    await cacheJsonResponse(path, response.clone());
    return response.json();
  } catch (error) {
    const cached = await cachedJsonResponse(path);
    if (cached) return cached.json();
    throw error;
  }
}

async function prefetchAllPoolData() {
  if (!("caches" in window) || !state.metadata?.pools) return;
  const paths = state.metadata.pools.map((pool) => dataUrl(`${DATA_ROOT}/${safeFilename(pool.id)}.json`));
  for (const path of paths) {
    fetch(path)
      .then((response) => {
        if (response.ok) return cacheJsonResponse(path, response);
        return null;
      })
      .catch(() => null);
  }
}

async function cacheJsonResponse(path, response) {
  if (!("caches" in window)) return;
  const cache = await caches.open(DATA_CACHE);
  await cache.put(new Request(path), response);
}

async function cachedJsonResponse(path) {
  if (!("caches" in window)) return null;
  const cache = await caches.open(DATA_CACHE);
  return cache.match(new Request(path));
}

function fillSelect(select, options) {
  select.innerHTML = options
    .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
    .join("");
}

function unique(values) {
  return [...new Set(values)];
}

function seasonLabel(season) {
  const start = Number.parseInt(season, 10);
  if (!Number.isFinite(start)) return season;
  return `${start}-${start + 1}`;
}

function gameTicks(maxX) {
  const ticks = [];
  for (let value = 0; value <= maxX; value += 3) {
    ticks.push({ value, label: String(value) });
  }
  if (ticks[ticks.length - 1]?.value !== maxX) {
    ticks.push({ value: maxX, label: String(maxX) });
  }
  return ticks;
}

function monthTicks(minX, maxX) {
  const formatter = new Intl.DateTimeFormat("da-DK", { month: "short", year: "2-digit" });
  const date = new Date(minX);
  date.setDate(1);
  date.setHours(0, 0, 0, 0);
  const ticks = [];
  while (date.getTime() <= maxX) {
    ticks.push({ value: date.getTime(), label: formatter.format(date) });
    date.setMonth(date.getMonth() + 1);
  }
  return ticks;
}

function yAxisMax(maxY) {
  return Math.max(3, Math.ceil(maxY / 3) * 3);
}

function yTicks(maxY) {
  const ticks = [];
  for (let value = 0; value <= maxY; value += 3) {
    ticks.push(value);
  }
  return ticks;
}

function firstDayOfMonth(value) {
  const date = new Date(value);
  date.setDate(1);
  date.setHours(0, 0, 0, 0);
  return date;
}

function divisionWeight(division) {
  if (division === "Volleyligaen") return 0;
  const number = Number.parseInt(division, 10);
  return Number.isFinite(number) ? number : 99;
}

function poolWeight(pool) {
  return { "Række 1": 0, Øst: 1, Vest: 2, Syd: 3, Nord: 4 }[pool] ?? 20;
}

function safeFilename(value) {
  return value.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function dataUrl(path) {
  return `${path}?v=${encodeURIComponent(DATA_VERSION)}`;
}

function shortTeam(team) {
  return teamAbbreviations.reduce((name, [from, to]) => name.replace(from, to), team).trim();
}

function genderLabel(gender) {
  return gender === "Mand" ? "Herrer" : gender === "Kvinde" ? "Kvinder" : gender;
}

function matrixClass(value) {
  const match = /^(\d+)-(\d+)/.exec(value || "");
  if (!match) return "";
  return Number(match[1]) > Number(match[2]) ? "win" : "loss";
}

function formatDateTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("da-DK", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMatchDateTime(match) {
  if (!match.starts_at) return "Dato ikke fastlagt";
  if (match.starts_at_time_known === false) {
    const date = new Intl.DateTimeFormat("da-DK", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(new Date(match.starts_at));
    return `${date}, tidspunkt ikke fastlagt`;
  }
  return formatDateTime(match.starts_at);
}

function formatVenue(match) {
  const venue = escapeHtml(match.venue || "Spillested ikke fastlagt");
  return `${venue}${match.court ? `, bane ${escapeHtml(match.court)}` : ""}`;
}

function renderScheduleDateTime(match) {
  if (!match.starts_at) return "";
  const date = formatScheduleDate(match.starts_at);
  if (match.starts_at_time_known === false) {
    return `<span class="schedule-date-part">${escapeHtml(date)}</span>`;
  }
  return `
    <span class="schedule-date-part">${escapeHtml(date)}</span>
    <span class="schedule-time-part">${escapeHtml(formatScheduleTime(match.starts_at))}</span>
  `;
}

function formatScheduleDate(value) {
  return new Intl.DateTimeFormat("da-DK", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatScheduleTime(value) {
  return new Intl.DateTimeFormat("da-DK", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatScheduleVenue(match) {
  return escapeHtml(match.venue || "Spillested ikke fastlagt");
}

function formatScheduleResult(match) {
  if (!Number.isFinite(match.result_home_sets) || !Number.isFinite(match.result_away_sets)) return "";
  return `${match.result_home_sets}-${match.result_away_sets}`;
}

function formatMatchResult(match) {
  if (match.result_home_sets === null || match.result_away_sets === null) return "Ikke spillet";
  return `${match.result_home_sets}-${match.result_away_sets}`;
}

function setActiveButton(container, activeButton) {
  for (const item of container.querySelectorAll("button")) {
    item.classList.toggle("active", item === activeButton);
  }
}

function setActiveButtonByData(container, key, value) {
  for (const item of container.querySelectorAll("button")) {
    item.classList.toggle("active", item.dataset[key] === value);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(callback, delay) {
  let timer = 0;
  return () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(callback, delay);
  };
}

init();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch((error) => {
      console.warn("Service worker kunne ikke registreres.", error);
    });
  });
}
