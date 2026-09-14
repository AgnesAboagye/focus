<template>
  <main class="species-comparison">
    <header class="page-header">
      <div>
        <p class="eyebrow">Ontology-based data comparison</p>
        <h1>Species Comparison</h1>
        <p class="subtitle">
          Compare measurements of the same ontology-defined trait across species.
        </p>
      </div>

      <button
        type="button"
        class="secondary-button"
        :disabled="loadingTraits || loadingComparison"
        @click="refresh"
      >
        Refresh data
      </button>
    </header>

    <section class="panel controls" aria-labelledby="comparison-options">
      <h2 id="comparison-options">Comparison options</h2>

      <div class="control-grid">
        <label class="field trait-field">
          <span>Comparable trait</span>
          <select
            v-model="selectedTraitIri"
            :disabled="loadingTraits || !compatibleTraits.length"
            @change="applyTraitSelection"
          >
            <option value="" disabled>Select a trait</option>
            <option
              v-for="trait in compatibleTraits"
              :key="trait.ontologyIri"
              :value="trait.ontologyIri"
            >
              {{ trait.traitName }} — {{ trait.traitCurie }} —
              {{ trait.speciesCount }} species
              ({{ formatInteger(trait.observationCount) }} observations)
            </option>
          </select>
        </label>

        <label class="checkbox-field">
          <input v-model="excludeZero" type="checkbox" />
          Exclude zero values
        </label>
      </div>

      <div v-if="selectedTrait" class="trait-summary">
        <div>
          <span class="summary-label">Trait</span>
          <strong>{{ selectedTrait.traitName }}</strong>
        </div>
        <div>
          <span class="summary-label">Ontology term</span>
          <a :href="selectedTrait.ontologyIri" target="_blank" rel="noopener">
            {{ selectedTrait.traitCurie }}
          </a>
        </div>
        <div>
          <span class="summary-label">Unit</span>
          <strong>{{ selectedTrait.canonicalUnit || "Unknown" }}</strong>
        </div>
        <div>
          <span class="summary-label">Available observations</span>
          <strong>{{ formatInteger(selectedTrait.observationCount) }}</strong>
        </div>
      </div>

      <fieldset v-if="availableSpecies.length" class="species-options">
        <legend>Select at least two species</legend>
        <label
          v-for="species in availableSpecies"
          :key="species.speciesIri"
          class="species-option"
        >
          <input
            v-model="selectedSpeciesIris"
            type="checkbox"
            :value="species.speciesIri"
          />
          <span>
            <em>{{ species.scientificName }}</em>
            <small>{{ formatInteger(species.observationCount) }} observations</small>
          </span>
        </label>
      </fieldset>

      <div class="actions">
        <button
          type="button"
          class="primary-button"
          :disabled="!canCompare || loadingComparison"
          @click="loadComparison"
        >
          {{ loadingComparison ? "Loading observations…" : "Compare species" }}
        </button>
        <span v-if="selectedSpeciesIris.length === 1" class="hint">
          Select one more species.
        </span>
      </div>
    </section>

    <div v-if="errorMessage" class="alert error" role="alert">
      <strong>Unable to load the comparison.</strong>
      <span>{{ errorMessage }}</span>
    </div>

    <div
      v-if="selectedTrait && !selectedTrait.unitsCompatible"
      class="alert warning"
      role="status"
    >
      This trait cannot be compared until its measurement units are compatible.
    </div>

    <section v-if="boxPlots.length" class="panel results" aria-labelledby="plot-title">
      <div class="results-header">
        <div>
          <p class="eyebrow">Comparison result</p>
          <h2 id="plot-title">{{ comparisonTitle }}</h2>
          <p>
            {{ formatInteger(observations.length) }} observations ·
            {{ comparisonUnit }}
          </p>
        </div>
      </div>

      <div class="chart-scroll">
        <svg
          class="box-plot"
          :viewBox="`0 0 ${chart.width} ${chart.height}`"
          role="img"
          :aria-label="`Box plot comparing ${comparisonTitle} across species`"
        >
          <g class="grid">
            <g v-for="tick in chart.ticks" :key="tick.value">
              <line
                :x1="chart.margin.left"
                :x2="chart.width - chart.margin.right"
                :y1="tick.y"
                :y2="tick.y"
              />
              <text
                :x="chart.margin.left - 12"
                :y="tick.y + 5"
                text-anchor="end"
              >
                {{ formatNumber(tick.value) }}
              </text>
            </g>
          </g>

          <line
            class="axis"
            :x1="chart.margin.left"
            :x2="chart.margin.left"
            :y1="chart.margin.top"
            :y2="chart.height - chart.margin.bottom"
          />

          <text
            class="axis-title"
            :x="18"
            :y="chart.height / 2"
            text-anchor="middle"
            :transform="`rotate(-90 18 ${chart.height / 2})`"
          >
            Value ({{ comparisonUnit }})
          </text>

          <g
            v-for="plot in chart.plots"
            :key="plot.speciesIri"
            class="box-group"
          >
            <title>
              {{ plot.scientificName }}: median {{ formatNumber(plot.median) }},
              n={{ plot.count }}
            </title>

            <line
              class="whisker"
              :x1="plot.x"
              :x2="plot.x"
              :y1="plot.upperWhiskerY"
              :y2="plot.lowerWhiskerY"
            />
            <line
              class="whisker-cap"
              :x1="plot.x - 18"
              :x2="plot.x + 18"
              :y1="plot.upperWhiskerY"
              :y2="plot.upperWhiskerY"
            />
            <line
              class="whisker-cap"
              :x1="plot.x - 18"
              :x2="plot.x + 18"
              :y1="plot.lowerWhiskerY"
              :y2="plot.lowerWhiskerY"
            />
            <rect
              class="box"
              :x="plot.x - 34"
              :y="plot.q3Y"
              width="68"
              :height="Math.max(2, plot.q1Y - plot.q3Y)"
            />
            <line
              class="median"
              :x1="plot.x - 34"
              :x2="plot.x + 34"
              :y1="plot.medianY"
              :y2="plot.medianY"
            />

            <circle
              v-for="(outlier, index) in plot.outliers"
              :key="`${plot.speciesIri}-${index}`"
              class="outlier"
              :cx="plot.x + outlier.offset"
              :cy="outlier.y"
              r="3"
            />

            <text
              class="species-label"
              :x="plot.x"
              :y="chart.height - 43"
              text-anchor="middle"
            >
              {{ plot.scientificName }}
            </text>
            <text
              class="sample-size"
              :x="plot.x"
              :y="chart.height - 22"
              text-anchor="middle"
            >
              n = {{ formatInteger(plot.count) }}
            </text>
          </g>
        </svg>
      </div>

      <div class="legend" aria-label="Box plot legend">
        Boxes show the interquartile range, the centre line shows the median,
        whiskers extend to 1.5 × IQR, and points represent outliers.
      </div>

      <div class="table-scroll">
        <table>
          <caption>Summary statistics</caption>
          <thead>
            <tr>
              <th>Species</th>
              <th>n</th>
              <th>Minimum</th>
              <th>Q1</th>
              <th>Median</th>
              <th>Q3</th>
              <th>Maximum</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="plot in boxPlots" :key="plot.speciesIri">
              <td><em>{{ plot.scientificName }}</em></td>
              <td>{{ formatInteger(plot.count) }}</td>
              <td>{{ formatNumber(plot.minimum) }}</td>
              <td>{{ formatNumber(plot.q1) }}</td>
              <td>{{ formatNumber(plot.median) }}</td>
              <td>{{ formatNumber(plot.q3) }}</td>
              <td>{{ formatNumber(plot.maximum) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section
      v-else-if="comparisonAttempted && !loadingComparison && !errorMessage"
      class="panel empty-state"
    >
      <h2>No numerical observations found</h2>
      <p>Try including zero values or selecting another comparable trait.</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/$/, "");

const traits = ref([]);
const selectedTraitIri = ref("");
const selectedSpeciesIris = ref([]);
const excludeZero = ref(true);
const observations = ref([]);
const comparisonMetadata = ref(null);
const loadingTraits = ref(false);
const loadingComparison = ref(false);
const comparisonAttempted = ref(false);
const errorMessage = ref("");

const compatibleTraits = computed(() =>
  traits.value.filter(
    (trait) => trait.speciesCount >= 2 && trait.unitsCompatible === true,
  ),
);

const selectedTrait = computed(() =>
  traits.value.find((trait) => trait.ontologyIri === selectedTraitIri.value),
);

const availableSpecies = computed(() => selectedTrait.value?.species || []);

const canCompare = computed(
  () =>
    Boolean(selectedTrait.value?.unitsCompatible) &&
    selectedSpeciesIris.value.length >= 2,
);

const comparisonUnit = computed(
  () =>
    comparisonMetadata.value?.canonicalUnit ||
    selectedTrait.value?.canonicalUnit ||
    "unit unknown",
);

const comparisonTitle = computed(
  () => selectedTrait.value?.traitName || "Selected trait",
);

function quantile(sortedValues, probability) {
  if (!sortedValues.length) return null;
  const position = (sortedValues.length - 1) * probability;
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.ceil(position);
  if (lowerIndex === upperIndex) return sortedValues[lowerIndex];
  const fraction = position - lowerIndex;
  return (
    sortedValues[lowerIndex] * (1 - fraction) +
    sortedValues[upperIndex] * fraction
  );
}

const boxPlots = computed(() => {
  const groups = new Map();

  for (const row of observations.value) {
    const value = Number(row.value);
    if (!row.speciesIri || !Number.isFinite(value)) continue;
    if (!groups.has(row.speciesIri)) {
      groups.set(row.speciesIri, {
        speciesIri: row.speciesIri,
        scientificName: row.scientificName || row.speciesIri,
        values: [],
      });
    }
    groups.get(row.speciesIri).values.push(value);
  }

  return [...groups.values()]
    .map((group) => {
      const values = group.values.sort((a, b) => a - b);
      const q1 = quantile(values, 0.25);
      const median = quantile(values, 0.5);
      const q3 = quantile(values, 0.75);
      const iqr = q3 - q1;
      const lowerFence = q1 - 1.5 * iqr;
      const upperFence = q3 + 1.5 * iqr;
      const included = values.filter(
        (value) => value >= lowerFence && value <= upperFence,
      );

      return {
        speciesIri: group.speciesIri,
        scientificName: group.scientificName,
        count: values.length,
        minimum: values[0],
        q1,
        median,
        q3,
        maximum: values[values.length - 1],
        lowerWhisker: included[0] ?? values[0],
        upperWhisker: included[included.length - 1] ?? values[values.length - 1],
        outlierValues: values.filter(
          (value) => value < lowerFence || value > upperFence,
        ),
      };
    })
    .sort((a, b) => a.scientificName.localeCompare(b.scientificName));
});

const chart = computed(() => {
  const margin = { top: 34, right: 30, bottom: 92, left: 82 };
  const width = Math.max(720, boxPlots.value.length * 230 + margin.left + margin.right);
  const height = 480;
  const plotHeight = height - margin.top - margin.bottom;
  const allValues = boxPlots.value.flatMap((plot) => [plot.minimum, plot.maximum]);
  let minimum = Math.min(...allValues);
  let maximum = Math.max(...allValues);

  if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {
    minimum = 0;
    maximum = 1;
  }
  if (minimum === maximum) {
    minimum -= 1;
    maximum += 1;
  }
  const padding = (maximum - minimum) * 0.08;
  const domainMin = minimum - padding;
  const domainMax = maximum + padding;
  const y = (value) =>
    margin.top + ((domainMax - value) / (domainMax - domainMin)) * plotHeight;
  const usableWidth = width - margin.left - margin.right;
  const slotWidth = usableWidth / Math.max(1, boxPlots.value.length);

  const plots = boxPlots.value.map((plot, index) => ({
    ...plot,
    x: margin.left + slotWidth * (index + 0.5),
    q1Y: y(plot.q1),
    medianY: y(plot.median),
    q3Y: y(plot.q3),
    lowerWhiskerY: y(plot.lowerWhisker),
    upperWhiskerY: y(plot.upperWhisker),
    outliers: plot.outlierValues.map((value, outlierIndex) => ({
      y: y(value),
      offset: ((outlierIndex % 7) - 3) * 4,
    })),
  }));

  const ticks = Array.from({ length: 6 }, (_, index) => {
    const value = domainMin + ((domainMax - domainMin) * index) / 5;
    return { value, y: y(value) };
  });

  return { width, height, margin, plots, ticks };
});

async function requestJson(path, parameters = new URLSearchParams()) {
  const response = await fetch(`${API_BASE_URL}${path}?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function firstText(...values) {
  return values.find(
    (value) =>
      typeof value === "string" &&
      value.trim() &&
      value.trim() !== "Trait name not provided",
  )?.trim() || "";
}

function normaliseCurie(value) {
  return String(value || "").trim().replace("_", ":").toUpperCase();
}

function buildTraitNameLookups(records) {
  const byIri = new Map();
  const byCurie = new Map();

  for (const record of records) {
    const info = record.additionalInfo || {};
    const ontology = record.ontologyReference || {};
    const iri = firstText(info.ontologyIRI, record.ontologyIri, record.ontologyIRI);
    const curie = firstText(
      info.ontologyCURIE,
      record.traitCurie,
      ontology.ontologyDbId,
      record.observationVariableDbId,
    );
    const name = firstText(
      record.phenotypeName,
      record.traitName,
      record.observationVariableName,
      info.phenotypeName,
      info.traitName,
      Array.isArray(record.traitNames) ? record.traitNames[0] : "",
      Array.isArray(info.phenotypeNames) ? info.phenotypeNames[0] : "",
    );

    if (!name) continue;
    if (iri) byIri.set(iri, name);
    if (curie) byCurie.set(normaliseCurie(curie), name);
  }

  return { byIri, byCurie };
}

async function loadTraits() {
  loadingTraits.value = true;
  errorMessage.value = "";
  try {
    const [speciesPayload, traitPayload] = await Promise.all([
      requestJson(
        "/brapi/v2/comparable-traits-by-species",
        new URLSearchParams({ page: "0", pageSize: "1000" }),
      ),
      requestJson(
        "/brapi/v2/comparable-traits",
        new URLSearchParams({ comparable_only: "false", limit: "1000" }),
      ),
    ]);

    const nameRecords = Array.isArray(traitPayload.result?.data)
      ? traitPayload.result.data
      : [];
    const nameLookups = buildTraitNameLookups(nameRecords);
    const records = Array.isArray(speciesPayload.result?.data)
      ? speciesPayload.result.data
      : [];
    traits.value = records.map((trait) => ({
      ...trait,
      traitName:
        nameLookups.byIri.get(trait.ontologyIri) ||
        nameLookups.byCurie.get(normaliseCurie(trait.traitCurie)) ||
        trait.traitName ||
        trait.phenotypeName ||
        trait.observationVariableName ||
        "Trait name not provided",
    }));
    if (!traits.value.length) {
      throw new Error("The API returned no comparable traits.");
    }
    if (!compatibleTraits.value.length) {
      throw new Error(
        "Comparable traits were found, but none currently have compatible units.",
      );
    }
    if (!compatibleTraits.value.some(
      (trait) => trait.ontologyIri === selectedTraitIri.value,
    )) {
      selectedTraitIri.value = compatibleTraits.value[0].ontologyIri;
    }
    applyTraitSelection();
  } catch (error) {
    errorMessage.value = error.message || "An unexpected error occurred.";
  } finally {
    loadingTraits.value = false;
  }
}

function applyTraitSelection() {
  selectedSpeciesIris.value = availableSpecies.value.map(
    (species) => species.speciesIri,
  );
  observations.value = [];
  comparisonMetadata.value = null;
  comparisonAttempted.value = false;
  errorMessage.value = "";
}

async function loadComparison() {
  if (!canCompare.value) return;

  loadingComparison.value = true;
  comparisonAttempted.value = true;
  observations.value = [];
  comparisonMetadata.value = null;
  errorMessage.value = "";

  try {
    let page = 0;
    let totalPages = 1;
    const collected = [];
    let resultMetadata = null;

    do {
      const parameters = new URLSearchParams({
        ontology_iri: selectedTraitIri.value,
        exclude_zero: String(excludeZero.value),
        page: String(page),
        pageSize: "10000",
      });
      for (const speciesIri of selectedSpeciesIris.value) {
        parameters.append("species_iri", speciesIri);
      }

      const payload = await requestJson("/brapi/v2/compare-species", parameters);
      const pagination = payload.metadata?.pagination || {};
      resultMetadata = payload.result || resultMetadata;
      collected.push(...(payload.result?.data || []));
      totalPages = Number(pagination.totalPages || 0);
      page += 1;
    } while (page < totalPages);

    comparisonMetadata.value = resultMetadata;
    observations.value = collected;

    if (resultMetadata?.unitsCompatible === false) {
      throw new Error(
        "The API reported incompatible units, so a combined box plot was not created.",
      );
    }
  } catch (error) {
    observations.value = [];
    errorMessage.value = error.message || "An unexpected error occurred.";
  } finally {
    loadingComparison.value = false;
  }
}

async function refresh() {
  await loadTraits();
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(
    Number(value || 0),
  );
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: 2,
  }).format(Number(value));
}

onMounted(loadTraits);
</script>

<style scoped>
.species-comparison {
  --ink: #24333c;
  --muted: #60717c;
  --border: #dbe3e7;
  --surface: #ffffff;
  --soft: #f5f8f9;
  --primary: #087f75;
  --primary-dark: #06665e;
  --accent: #e1f4f1;
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 24px 64px;
  color: var(--ink);
}

.page-header,
.results-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 8px;
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 1.08;
}

h2 {
  margin-bottom: 20px;
  font-size: 1.35rem;
}

.eyebrow {
  margin-bottom: 7px;
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.subtitle,
.results-header p {
  margin-bottom: 0;
  color: var(--muted);
}

.panel {
  margin-top: 28px;
  padding: 26px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: 0 8px 24px rgb(34 51 60 / 6%);
}

.control-grid {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) auto;
  align-items: end;
  gap: 22px;
}

.field,
.checkbox-field {
  display: grid;
  gap: 8px;
  font-weight: 700;
}

select {
  width: 100%;
  min-height: 46px;
  padding: 0 42px 0 13px;
  border: 1px solid #aebcc3;
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  font: inherit;
}

.checkbox-field,
.species-option {
  display: flex;
  align-items: center;
  gap: 10px;
}

input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--primary);
}

.trait-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
  padding: 16px;
  border-radius: 10px;
  background: var(--soft);
}

.trait-summary > div {
  display: grid;
  gap: 5px;
}

.summary-label {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 700;
}

a {
  color: var(--primary-dark);
  font-weight: 800;
}

.species-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  margin: 22px 0 0;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
}

.species-options legend {
  padding: 0 8px;
  font-weight: 800;
}

.species-option {
  padding: 11px;
  border-radius: 8px;
  background: var(--soft);
}

.species-option span {
  display: grid;
  gap: 3px;
}

.species-option small {
  color: var(--muted);
}

.actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 22px;
}

button {
  min-height: 44px;
  padding: 0 18px;
  border-radius: 8px;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.primary-button {
  border: 1px solid var(--primary);
  background: var(--primary);
  color: #fff;
}

.primary-button:hover:not(:disabled) {
  background: var(--primary-dark);
}

.secondary-button {
  border: 1px solid #aebcc3;
  background: #fff;
  color: var(--ink);
}

.hint,
.legend {
  color: var(--muted);
  font-size: 0.9rem;
}

.alert {
  display: grid;
  gap: 4px;
  margin-top: 22px;
  padding: 15px 18px;
  border-radius: 9px;
}

.alert.error {
  border: 1px solid #e4a8a8;
  background: #fff2f2;
  color: #852323;
}

.alert.warning {
  border: 1px solid #e5ca83;
  background: #fff9e8;
  color: #684f0b;
}

.chart-scroll,
.table-scroll {
  overflow-x: auto;
}

.box-plot {
  display: block;
  width: 100%;
  min-width: 720px;
  margin-top: 18px;
}

.grid line {
  stroke: #e5ebee;
  stroke-width: 1;
}

.grid text,
.sample-size {
  fill: var(--muted);
  font-size: 13px;
}

.axis {
  stroke: #71818a;
  stroke-width: 1.5;
}

.axis-title,
.species-label {
  fill: var(--ink);
  font-size: 14px;
  font-weight: 700;
}

.whisker,
.whisker-cap {
  stroke: #334952;
  stroke-width: 2;
}

.box {
  fill: #70c8bd;
  stroke: var(--primary-dark);
  stroke-width: 2;
}

.median {
  stroke: #173e47;
  stroke-width: 3;
}

.outlier {
  fill: #e07355;
  opacity: 0.7;
}

.legend {
  padding: 12px 15px;
  border-radius: 8px;
  background: var(--soft);
}

.table-scroll {
  margin-top: 24px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

caption {
  padding-bottom: 10px;
  text-align: left;
  font-size: 1.05rem;
  font-weight: 800;
}

th,
td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: right;
  white-space: nowrap;
}

th:first-child,
td:first-child {
  text-align: left;
}

th {
  background: var(--soft);
  color: #455963;
  font-size: 0.82rem;
  text-transform: uppercase;
}

.empty-state {
  text-align: center;
}

@media (max-width: 760px) {
  .species-comparison {
    padding: 22px 14px 48px;
  }

  .page-header,
  .results-header {
    display: grid;
  }

  .control-grid,
  .trait-summary {
    grid-template-columns: 1fr;
  }

  .panel {
    padding: 19px;
  }
}
</style>

