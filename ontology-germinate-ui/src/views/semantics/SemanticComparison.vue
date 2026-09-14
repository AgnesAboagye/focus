```vue
<template>
  <main class="semantic-page">
    <!-- =====================================================
         PAGE HEADER
    ====================================================== -->
    <header class="page-header">
      <div>
        <p class="eyebrow">Ontology-based data comparison</p>

        <h1>Semantic Comparison</h1>

        <p>
          Find traits that share the same ontology term across datasets.
        </p>
      </div>

      <button
        class="primary"
        type="button"
        :disabled="loading"
        @click="loadTraits"
      >
        {{ loading ? "Loading…" : "Refresh" }}
      </button>
    </header>

    <!-- =====================================================
         FILTERS
    ====================================================== -->
    <section class="filters">
      <label>
        <span>Search traits</span>

        <input
          v-model.trim="search"
          type="search"
          placeholder="Search by trait name, ontology ID or ontology"
        />
      </label>

      <label>
        <span>Trait availability</span>

        <select
          v-model="comparableOnly"
          :disabled="loading"
          @change="loadTraits"
        >
          <option :value="true">
            Multiple datasets only
          </option>

          <option :value="false">
            All mapped traits
          </option>
        </select>
      </label>
    </section>

    <!-- =====================================================
         ERROR
    ====================================================== -->
    <section
      v-if="errorMessage"
      class="error"
      role="alert"
    >
      <strong>Unable to load traits.</strong>
      {{ errorMessage }}
    </section>

    <!-- =====================================================
         SUMMARY
    ====================================================== -->
    <section class="summary">
      <article>
        <span>Ontology traits</span>
        <strong>
          {{ formatNumber(filteredTraits.length) }}
        </strong>
      </article>

      <article>
        <span>Comparable traits</span>
        <strong>
          {{ formatNumber(comparableCount) }}
        </strong>
      </article>

      <article>
        <span>Dataset connections</span>
        <strong>
          {{ formatNumber(datasetTotal) }}
        </strong>
      </article>

      <article>
        <span>Observations</span>
        <strong>
          {{ formatNumber(observationTotal) }}
        </strong>
      </article>
    </section>

    <!-- =====================================================
         MAIN WORKSPACE
    ====================================================== -->
    <section class="workspace">
      <!-- =========================
           TRAIT RESULTS
      ========================== -->
      <section class="results">
        <header class="panel-header">
          <div>
            <h2>Available ontology traits</h2>

            <p>
              Select a trait to inspect its comparison information.
            </p>
          </div>

          <span class="count">
            {{ filteredTraits.length }}
            {{ filteredTraits.length === 1 ? "trait" : "traits" }}
          </span>
        </header>

        <!-- Loading -->
        <div
          v-if="loading"
          class="state"
        >
          Loading ontology traits…
        </div>

        <!-- No results -->
        <div
          v-else-if="filteredTraits.length === 0"
          class="state"
        >
          No ontology traits matched your search.
        </div>

        <!-- Table -->
        <div
          v-else
          class="table-wrap"
        >
          <table>
            <thead>
              <tr>
                <th>Traits</th>
                <th>Ontology ID</th>
                <th>Datasets</th>
                <th>Observations</th>
              </tr>
            </thead>

            <tbody>
              <tr
                v-for="trait in filteredTraits"
                :key="trait.curie || trait.ontologyIRI || trait.name"
                :class="{ selected: isSelected(trait) }"
                @click="selectTrait(trait)"
              >
                <!-- TRAIT -->
                <td>
                  <strong class="trait-name">
                    {{ trait.name }}
                  </strong>

                  <span
                    class="badge"
                    :class="trait.comparable ? 'yes' : 'no'"
                  >
                    {{
                      trait.comparable
                        ? "Comparable"
                        : "One dataset"
                    }}
                  </span>
                </td>

                <!-- ONTOLOGY ID -->
                <td>
                  <a
                    v-if="trait.ontologyIRI"
                    :href="trait.ontologyIRI"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click.stop
                  >
                    {{ trait.curie || "Ontology term" }} ↗
                  </a>

                  <span v-else>
                    {{ trait.curie || "Not mapped" }}
                  </span>

                  <small
                    v-if="trait.ontologyName"
                    class="ontology-name"
                  >
                    {{ trait.ontologyName }}
                  </small>
                </td>

                <!-- DATASETS -->
                <td class="number">
                  {{ formatNumber(trait.datasetCount) }}
                </td>

                <!-- OBSERVATIONS -->
                <td class="number">
                  {{ formatNumber(trait.observationCount) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- =========================
           TRAIT DETAILS
      ========================== -->
      <aside class="details">
        <div v-if="selectedTrait">
          <p class="eyebrow">
            Selected trait
          </p>

          <h2>
            {{ selectedTrait.name }}
          </h2>

          <a
            v-if="selectedTrait.ontologyIRI"
            :href="selectedTrait.ontologyIRI"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ selectedTrait.curie || "Ontology term" }} ↗
          </a>

          <p
            v-else
            class="curie"
          >
            {{ selectedTrait.curie || "Not mapped" }}
          </p>

          <dl>
            <div>
              <dt>Ontology</dt>

              <dd>
                {{
                  selectedTrait.ontologyName ||
                  "Ontology not recorded"
                }}
              </dd>
            </div>

            <div>
              <dt>Datasets</dt>

              <dd>
                {{
                  formatNumber(
                    selectedTrait.datasetCount
                  )
                }}
              </dd>
            </div>

            <div>
              <dt>Observations</dt>

              <dd>
                {{
                  formatNumber(
                    selectedTrait.observationCount
                  )
                }}
              </dd>
            </div>

            <div>
              <dt>Status</dt>

              <dd>
                {{
                  selectedTrait.comparable
                    ? "Ready to compare"
                    : "One dataset only"
                }}
              </dd>
            </div>
          </dl>

          <div class="iri">
            <span>Ontology IRI</span>

            <code>
              {{
                selectedTrait.ontologyIRI ||
                "Not recorded"
              }}
            </code>
          </div>

          <button
            class="primary compare"
            type="button"
            :disabled="!selectedTrait.comparable"
            @click="prepareComparison"
          >
            Compare observations
          </button>

          <p
            v-if="comparisonNotice"
            class="notice"
          >
            {{ comparisonNotice }}
          </p>
        </div>

        <div
          v-else
          class="state"
        >
          Select a trait to view its comparison summary.
        </div>
      </aside>
    </section>
  </main>
</template>

<script setup>
import {
  computed,
  onMounted,
  ref
} from "vue";

/* =========================================================
   API
========================================================= */

const apiBase = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/$/, "");

/* =========================================================
   STATE
========================================================= */

const traits = ref([]);

const selectedTrait = ref(null);

const search = ref("");

const comparableOnly = ref(true);

const loading = ref(false);

const errorMessage = ref("");

const comparisonNotice = ref("");

/* =========================================================
   FILTERED TRAITS
========================================================= */

const filteredTraits = computed(() => {
  const query = search.value
    .trim()
    .toLowerCase();

  if (!query) {
    return traits.value;
  }

  return traits.value.filter((trait) => {
    const searchableValues = [
      trait.name,
      trait.curie,
      trait.ontologyIRI,
      trait.ontologyName
    ];

    return searchableValues
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
});

/* =========================================================
   SUMMARY VALUES
========================================================= */

const comparableCount = computed(() => {
  return filteredTraits.value.filter(
    (trait) => trait.comparable
  ).length;
});

const datasetTotal = computed(() => {
  return filteredTraits.value.reduce(
    (sum, trait) =>
      sum + Number(trait.datasetCount || 0),
    0
  );
});

const observationTotal = computed(() => {
  return filteredTraits.value.reduce(
    (sum, trait) =>
      sum + Number(trait.observationCount || 0),
    0
  );
});

/* =========================================================
   HELPERS
========================================================= */

/**
 * Returns the first non-empty value.
 */
function firstText(...values) {
  const value = values.find((item) => {
    return (
      typeof item === "string" &&
      item.trim().length > 0
    );
  });

  return value
    ? value.trim()
    : "";
}

/**
 * Detect ontology identifiers so that CURIEs and IRIs
 * are not accidentally shown as the trait name.
 */
function isOntologyIdentifier(value) {
  const text = String(value || "").trim();

  return (
    /^https?:\/\//i.test(text) ||
    /^[A-Za-z][A-Za-z0-9_-]*:\S+$/.test(text)
  );
}

/**
 * Find the trait name from the API response.
 *
 * This supports several possible field names because the
 * comparable-traits API may return either BrAPI-style names
 * or SPARQL/SQL aliases.
 */
function getTraitName(
  record,
  info = {},
  curie = ""
) {
  const values = [
    /* Most likely semantic API fields */
    record.label,
    record.traitLabel,
    record.trait_name,
    record.phenotypeLabel,
    record.phenotype_name,
    record.name,

    /* BrAPI-style fields */
    record.phenotypeName,
    record.traitName,
    record.observationVariableName,

    /* additionalInfo */
    info.label,
    info.traitLabel,
    info.trait_name,
    info.phenotypeLabel,
    info.phenotype_name,
    info.name,
    info.phenotypeName,
    info.traitName,
    info.observationVariableName,

    /* Nested trait object */
    record.trait?.traitName,
    record.trait?.name,
    record.trait?.label,

    /* Multi-name fields */
    record.phenotypeNames,
    record.traitNames,
    info.phenotypeNames,
    info.traitNames
  ];

  for (const value of values) {
    let candidates = [];

    if (Array.isArray(value)) {
      candidates = value;
    } else if (
      typeof value === "string"
    ) {
      candidates = value.split("|||");
    }

    const names = candidates
      .map((candidate) =>
        String(candidate).trim()
      )
      .filter((candidate) => {
        return (
          candidate &&
          candidate !== curie &&
          !isOntologyIdentifier(candidate)
        );
      });

    if (names.length > 0) {
      return [
        ...new Set(names)
      ].join(", ");
    }
  }

  /*
   * Do NOT display "Trait name not provided".
   * If the API genuinely has no label, use the ontology
   * CURIE as the final fallback.
   */
  return curie || "Unknown trait";
}

/**
 * Normalise API response into one predictable format
 * for the Vue interface.
 */
function normaliseTrait(record) {
  const info =
    record.additionalInfo || {};

  const ontology =
    record.ontologyReference || {};

  /* -----------------------------------------
     Ontology IRI
  ----------------------------------------- */

  const iri = firstText(
    record.ontologyIRI,
    record.ontologyIri,
    record.iri,
    record.termIRI,
    record.termIri,

    info.ontologyIRI,
    info.ontologyIri,
    info.iri,
    info.termIRI,
    info.termIri
  );

  /* -----------------------------------------
     Ontology CURIE / ID
  ----------------------------------------- */

  const curie = firstText(
    record.curie,
    record.ontologyCURIE,
    record.ontologyCurie,
    record.ontologyId,
    record.ontologyID,
    record.termId,
    record.termID,

    info.curie,
    info.ontologyCURIE,
    info.ontologyCurie,
    info.ontologyId,
    info.ontologyID,
    info.termId,
    info.termID,

    ontology.ontologyDbId,

    /*
     * BrAPI observationVariableDbId may occasionally
     * contain the ontology ID.
     */
    record.observationVariableDbId,

    iri
  );

  /* -----------------------------------------
     Trait name
  ----------------------------------------- */

  const name = firstText(
    record.label,
    record.traitLabel,
    record.trait_name,
    record.phenotypeLabel,
    record.phenotype_name,
    record.name,

    record.phenotypeName,
    record.traitName,
    record.observationVariableName,

    info.label,
    info.traitLabel,
    info.trait_name,
    info.phenotypeLabel,
    info.phenotype_name,
    info.name,
    info.phenotypeName,
    info.traitName,
    info.observationVariableName,

    getTraitName(
      record,
      info,
      curie
    )
  );

  /* -----------------------------------------
     Ontology source
  ----------------------------------------- */

  const ontologyName = firstText(
    record.ontologyName,
    record.ontologySource,
    record.ontologyAcronym,

    info.ontologyName,
    info.ontologySource,
    info.ontologyAcronym,

    ontology.ontologyName,

    "Ontology not recorded"
  );

  /* -----------------------------------------
     Dataset count
  ----------------------------------------- */

  const datasetCount = Number(
    record.datasetCount ??
    record.datasets ??
    record.numberOfDatasets ??
    record.number_of_datasets ??
    info.datasetCount ??
    info.datasets ??
    info.numberOfDatasets ??
    info.number_of_datasets ??
    0
  );

  /* -----------------------------------------
     Observation count
  ----------------------------------------- */

  const observationCount = Number(
    record.observationCount ??
    record.observations ??
    record.numberOfObservations ??
    record.number_of_observations ??
    info.observationCount ??
    info.observations ??
    info.numberOfObservations ??
    info.number_of_observations ??
    0
  );

  /* -----------------------------------------
     Comparable
  ----------------------------------------- */

  const comparableValue =
    record.comparable ??
    info.comparable;

  const comparable =
    comparableValue === true ||
    String(comparableValue)
      .toLowerCase() === "true" ||
    datasetCount > 1;

  return {
    name,
    curie,
    ontologyIRI: iri,
    ontologyName,

    bioPortalUrl:
      firstText(
        record.bioPortalUrl,
        record.bioportalUrl,
        info.bioPortalUrl,
        info.bioportalUrl
      ) || null,

    datasetCount,
    observationCount,
    comparable,

    /*
     * Keep the original row in case it is useful later
     * when building the comparison page.
     */
    raw: record
  };
}

/* =========================================================
   LOAD TRAITS
========================================================= */

async function loadTraits() {
  loading.value = true;

  errorMessage.value = "";

  comparisonNotice.value = "";

  const query =
    new URLSearchParams({
      comparable_only:
        String(comparableOnly.value),

      limit: "1000"
    });

  try {
    const response = await fetch(
      `${apiBase}/brapi/v2/comparable-traits?${query.toString()}`
    );

    if (!response.ok) {
      throw new Error(
        `API returned status ${response.status}`
      );
    }

    const payload =
      await response.json();

    /*
     * Standard BrAPI response:
     *
     * {
     *   result: {
     *     data: [...]
     *   }
     * }
     */
    const rows =
      payload?.result &&
      Array.isArray(
        payload.result.data
      )
        ? payload.result.data
        : [];

    traits.value =
      rows.map(normaliseTrait);

    /*
     * Automatically select first result.
     */
    selectedTrait.value =
      traits.value[0] || null;

    /*
     * Useful while debugging the API.
     * Open browser console to see exactly
     * what comparable-traits returned.
     */
    console.log(
      "Comparable traits API response:",
      payload
    );

    console.log(
      "Normalised traits:",
      traits.value
    );
  } catch (error) {
    console.error(
      "Unable to load comparable traits:",
      error
    );

    traits.value = [];

    selectedTrait.value = null;

    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Request failed.";
  } finally {
    loading.value = false;
  }
}

/* =========================================================
   SELECT TRAIT
========================================================= */

function selectTrait(trait) {
  selectedTrait.value = trait;

  comparisonNotice.value = "";
}

/* =========================================================
   SELECTED ROW
========================================================= */

function isSelected(trait) {
  if (!selectedTrait.value) {
    return false;
  }

  if (
    trait.ontologyIRI &&
    selectedTrait.value.ontologyIRI
  ) {
    return (
      selectedTrait.value.ontologyIRI ===
      trait.ontologyIRI
    );
  }

  if (
    trait.curie &&
    selectedTrait.value.curie
  ) {
    return (
      selectedTrait.value.curie ===
      trait.curie
    );
  }

  return (
    selectedTrait.value.name ===
    trait.name
  );
}

/* =========================================================
   PREPARE COMPARISON
========================================================= */

function prepareComparison() {
  if (
    !selectedTrait.value ||
    !selectedTrait.value.comparable
  ) {
    return;
  }

  comparisonNotice.value =
    `${selectedTrait.value.name} is available across ` +
    `${formatNumber(
      selectedTrait.value.datasetCount
    )} datasets.`;
}

/* =========================================================
   NUMBER FORMAT
========================================================= */

function formatNumber(value) {
  return new Intl.NumberFormat(
    "en-GB"
  ).format(
    Number(value || 0)
  );
}

/* =========================================================
   LOAD PAGE
========================================================= */

onMounted(() => {
  loadTraits();
});
</script>

<style scoped>
/* =========================================================
   PAGE
========================================================= */

.semantic-page {
  width: 100%;
  min-width: 0;
  min-height: 100vh;

  padding: 32px;

  color: #123f31;
  background: #f4f7f5;
}

/* =========================================================
   HEADERS
========================================================= */

.page-header,
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 20px;
}

.page-header {
  margin-bottom: 22px;
}

.page-header h1 {
  margin: 0 0 8px;

  font-size: clamp(
    2.2rem,
    4vw,
    3.2rem
  );
}

.page-header p,
.panel-header p {
  margin: 0;

  color: #66786f;
}

.eyebrow {
  margin: 0 0 7px !important;

  color: #287a55 !important;

  font-size: 0.78rem;
  font-weight: 800;

  letter-spacing: 0.09em;
  text-transform: uppercase;
}

/* =========================================================
   BUTTONS
========================================================= */

.primary {
  padding: 11px 18px;

  border: 0;
  border-radius: 9px;

  color: #ffffff;
  background: #246b4b;

  font: inherit;
  font-weight: 750;

  cursor: pointer;
}

.primary:hover:not(:disabled) {
  background: #1d5b3f;
}

.primary:disabled {
  opacity: 0.48;

  cursor: not-allowed;
}

/* =========================================================
   FILTERS
========================================================= */

.filters {
  display: grid;

  grid-template-columns:
    minmax(0, 2fr)
    minmax(230px, 1fr);

  gap: 18px;

  margin-bottom: 18px;

  padding: 20px;

  border: 1px solid #d4e0d9;
  border-radius: 14px;

  background: #ffffff;
}

.filters label span {
  display: block;

  margin-bottom: 8px;

  font-weight: 750;
}

.filters input,
.filters select {
  width: 100%;
  min-height: 48px;

  padding: 10px 14px;

  border: 1px solid #c4d4cb;
  border-radius: 9px;

  color: inherit;
  background: #ffffff;

  font: inherit;
}

/* =========================================================
   ERROR
========================================================= */

.error {
  margin-bottom: 18px;

  padding: 14px 16px;

  border: 1px solid #e7bcbc;
  border-radius: 11px;

  color: #842f2f;
  background: #fff1f1;
}

/* =========================================================
   SUMMARY
========================================================= */

.summary {
  display: grid;

  grid-template-columns:
    repeat(
      4,
      minmax(0, 1fr)
    );

  gap: 14px;

  margin-bottom: 18px;
}

.summary article {
  padding: 18px 20px;

  border: 1px solid #d4e0d9;
  border-radius: 13px;

  background: #ffffff;
}

.summary span,
.summary strong {
  display: block;
}

.summary span {
  color: #62756b;

  font-size: 0.8rem;
  font-weight: 700;
}

.summary strong {
  margin-top: 5px;

  font-size: 1.65rem;
}

/* =========================================================
   WORKSPACE
========================================================= */

.workspace {
  display: grid;

  grid-template-columns:
    minmax(0, 1fr)
    minmax(280px, 330px);

  gap: 18px;

  align-items: start;

  min-width: 0;
}

.results,
.details {
  min-width: 0;

  border: 1px solid #d4e0d9;
  border-radius: 15px;

  background: #ffffff;
}

.results {
  padding: 20px;
}

.details {
  position: sticky;

  top: 18px;

  padding: 22px;
}

/* =========================================================
   PANEL HEADER
========================================================= */

.panel-header {
  margin-bottom: 17px;
}

.panel-header h2,
.details h2 {
  margin: 0 0 5px;
}

.count {
  flex: none;

  padding: 7px 11px;

  border-radius: 999px;

  color: #1f6243;
  background: #e2f2e9;

  font-size: 0.8rem;
  font-weight: 800;
}

/* =========================================================
   TABLE
========================================================= */

.table-wrap {
  width: 100%;

  overflow-x: auto;

  border: 1px solid #dbe4df;
  border-radius: 11px;
}

table {
  width: 100%;

  table-layout: fixed;

  border-collapse: collapse;
}

th {
  padding: 13px 14px;

  border-bottom: 2px solid #d4dfd9;

  color: #365a49;
  background: #edf4f0;

  font-size: 0.73rem;

  text-align: left;
  text-transform: uppercase;
}

th:first-child {
  width: 43%;
}

th:nth-child(2) {
  width: 27%;
}

th:nth-child(3),
th:nth-child(4) {
  width: 15%;
}

td {
  padding: 15px 14px;

  border-bottom: 1px solid #e0e9e4;

  overflow-wrap: anywhere;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.selected {
  background: #edf7f1;
}

tbody tr.selected {
  box-shadow:
    inset 4px 0 #287a55;
}

/* =========================================================
   TRAIT
========================================================= */

.trait-name {
  display: block;

  font-size: 0.95rem;
}

.ontology-name {
  display: block;

  margin-top: 5px;

  color: #718279;

  font-size: 0.76rem;
}

/* =========================================================
   STATUS BADGE
========================================================= */

.badge {
  display: block;

  width: max-content;

  margin-top: 7px;

  padding: 4px 7px;

  border-radius: 999px;

  font-size: 0.66rem;
  font-weight: 800;
}

.badge.yes {
  color: #17603e;
  background: #dff4e8;
}

.badge.no {
  color: #77531f;
  background: #fff0ca;
}

/* =========================================================
   LINKS
========================================================= */

a,
.curie {
  color: #176946;

  font-weight: 750;

  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* =========================================================
   NUMBERS
========================================================= */

.number {
  text-align: center;

  font-weight: 800;
}

/* =========================================================
   DETAILS
========================================================= */

.details dl {
  margin: 16px 0;
}

.details dl div {
  display: grid;

  grid-template-columns:
    90px
    minmax(0, 1fr);

  gap: 12px;

  padding: 11px 0;

  border-bottom:
    1px solid #e3ebe7;
}

.details dt {
  color: #687970;
}

.details dd {
  margin: 0;

  font-weight: 800;

  text-align: right;
}

/* =========================================================
   ONTOLOGY IRI
========================================================= */

.iri {
  margin-bottom: 16px;

  padding: 13px;

  border-radius: 10px;

  background: #f1f5f3;
}

.iri span,
.iri code {
  display: block;
}

.iri span {
  margin-bottom: 6px;

  font-size: 0.72rem;
  font-weight: 800;
}

.iri code {
  overflow-wrap: anywhere;

  color: #255c44;
}

/* =========================================================
   COMPARE BUTTON
========================================================= */

.compare {
  width: 100%;
}

.notice {
  color: #5f7168;

  font-size: 0.82rem;
}

/* =========================================================
   STATES
========================================================= */

.state {
  padding: 48px 20px;

  color: #6c7c74;

  text-align: center;
}

/* =========================================================
   RESPONSIVE
========================================================= */

@media (
  max-width: 1120px
) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .details {
    position: static;
  }
}

@media (
  max-width: 760px
) {
  .semantic-page {
    padding: 18px;
  }

  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .filters,
  .summary {
    grid-template-columns:
      1fr 1fr;
  }

  .results {
    padding: 14px;
  }
}

@media (
  max-width: 520px
) {
  .filters,
  .summary {
    grid-template-columns: 1fr;
  }

  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
```


