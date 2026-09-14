<template>
  <main class="ontology-search" data-view="ontology-term-search">
    <header class="page-header">
      <div>
        <p class="eyebrow">Semantic data</p>
        <h1>Ontology Term Search</h1>
        <p class="subtitle">
          Search ontology terms used to describe Germinate phenotypic data.
        </p>
      </div>

      <button
        type="button"
        class="secondary-button"
        :disabled="loading"
        @click="refresh"
      >
        {{ loading ? "Loading…" : "Refresh" }}
      </button>
    </header>

    <section class="panel search-panel" aria-labelledby="search-heading">
      <h2 id="search-heading">Find an ontology term</h2>

      <form class="search-form" @submit.prevent="applySearch">
        <label class="field search-field">
          <span>Traits</span>
          <input
            v-model.trim="searchInput"
            type="search"
            maxlength="200"
            placeholder="For example: plant height or TO:0000207"
            autocomplete="off"
            @keydown.esc="clearSearch"
          />
        </label>

        <label class="field ontology-field">
          <span>Ontology</span>
          <select v-model="ontologyInput">
            <option value="">All ontologies</option>
            <option
              v-for="option in ontologyOptions"
              :key="option.code"
              :value="option.code"
            >
              {{ option.code }} — {{ option.name }}
            </option>
          </select>
        </label>

        <label class="exact-option">
          <input
            v-model="exactInput"
            type="checkbox"
            :disabled="!searchInput"
          />
          Exact match
        </label>

        <div class="form-actions">
          <button type="submit" class="primary-button" :disabled="loading">
            Search
          </button>
          <button
            v-if="hasActiveFilters"
            type="button"
            class="secondary-button"
            :disabled="loading"
            @click="clearSearch"
          >
            Clear
          </button>
        </div>
      </form>
    </section>

    <div v-if="errorMessage" class="alert" role="alert">
      <strong>Unable to search ontology terms.</strong>
      <span>{{ errorMessage }}</span>
    </div>

    <section class="panel results-panel" aria-labelledby="results-heading">
      <div class="results-heading">
        <div>
          <h2 id="results-heading">Ontology terms</h2>
          <p>{{ resultDescription }}</p>
        </div>

        <div class="results-tools">
          <label class="page-size-control">
            <span>Rows</span>
            <select v-model.number="pageSize" :disabled="loading" @change="changePageSize">
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>

          <span class="result-count">
            {{ formatInteger(totalCount) }}
            {{ totalCount === 1 ? "term" : "terms" }}
          </span>
        </div>
      </div>

      <div v-if="loading" class="state-message" aria-live="polite">
        <span class="spinner" aria-hidden="true"></span>
        Searching ontology terms…
      </div>

      <div v-else-if="terms.length === 0" class="state-message">
        <strong>No ontology terms found.</strong>
        <span>Try a different keyword or search all ontologies.</span>
      </div>

      <div v-else class="table-container">
        <table>
          <thead>
            <tr>
              <th>Traits</th>
              <th>Source ontology</th>
              <th><span class="visually-hidden">Actions</span></th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="term in terms" :key="term.ontologyTermDbId">
              <td>
                <strong class="term-name">
                  {{ term.ontologyTermName }}
                </strong>
              </td>

              <td>
                <a
                  v-if="ontologySourceUrl(term)"
                  :href="ontologySourceUrl(term)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ontology-badge ontology-source-link"
                >
                  {{ term.ontologyName }}
                  <span aria-hidden="true">↗</span>
                </a>
                <span v-else class="ontology-badge">
                  {{ term.ontologyName }}
                </span>
              </td>

              <td class="action-cell">
                <button
                  type="button"
                  class="copy-button"
                  :disabled="!term.ontologyTermIRI"
                  @click="copyIri(term)"
                >
                  {{ copiedIri === term.ontologyTermIRI ? "Copied" : "Copy IRI" }}
                </button>

                <a
                  v-if="term.bioPortalUrl"
                  :href="term.bioPortalUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="view-button"
                >
                  View in BioPortal <span aria-hidden="true">↗</span>
                </a>
                <a
                  v-else-if="termLink(term)"
                  :href="termLink(term)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="view-button"
                >
                  Open term <span aria-hidden="true">↗</span>
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer v-if="totalPages > 1" class="pagination">
        <button
          type="button"
          class="secondary-button"
          :disabled="page === 0 || loading"
          @click="previousPage"
        >
          Previous
        </button>

        <span>Page {{ page + 1 }} of {{ totalPages }}</span>

        <button
          type="button"
          class="secondary-button"
          :disabled="page + 1 >= totalPages || loading"
          @click="nextPage"
        >
          Next
        </button>
      </footer>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/$/, "");

const ontologyOptions = [
  { code: "TO", name: "Trait Ontology" },
  { code: "PO", name: "Plant Ontology" },
  { code: "CO", name: "Crop Ontology" },
  { code: "UO", name: "Units of Measurement Ontology" },
  { code: "PECO", name: "Plant Experimental Conditions Ontology" },
  { code: "PATO", name: "Phenotype and Trait Ontology" },
  { code: "ENVO", name: "Environment Ontology" },
  { code: "CDNO", name: "Compositional Dietary Nutrition Ontology" },
  { code: "NCBITAXON", name: "NCBI Taxonomy" },
  { code: "AGRO", name: "Agronomy Ontology" },
];

const terms = ref([]);
const loading = ref(false);
const errorMessage = ref("");

const searchInput = ref("");
const ontologyInput = ref("");
const exactInput = ref(false);

const appliedSearch = ref("");
const appliedOntology = ref("");
const appliedExact = ref(false);

const page = ref(0);
const pageSize = ref(20);
const totalCount = ref(0);
const totalPages = ref(0);
const copiedIri = ref("");
let activeController = null;

const hasActiveFilters = computed(
  () =>
    Boolean(
      searchInput.value ||
        ontologyInput.value ||
        appliedSearch.value ||
        appliedOntology.value ||
        exactInput.value,
    ),
);

const resultDescription = computed(() => {
  if (appliedSearch.value && appliedOntology.value) {
    return `Results for “${appliedSearch.value}” in ${appliedOntology.value}.`;
  }
  if (appliedSearch.value) {
    return `Results for “${appliedSearch.value}”.`;
  }
  if (appliedOntology.value) {
    return `Terms from ${appliedOntology.value}.`;
  }
  return "Browse ontology terms exposed through the semantic graph.";
});

async function loadTerms() {
  if (activeController) {
    activeController.abort();
  }
  const controller = new AbortController();
  activeController = controller;

  loading.value = true;
  errorMessage.value = "";

  const parameters = new URLSearchParams({
    page: String(page.value),
    pageSize: String(pageSize.value),
    exact: String(appliedExact.value),
  });

  if (appliedSearch.value) {
    parameters.set("search", appliedSearch.value);
  }
  if (appliedOntology.value) {
    parameters.set("ontology", appliedOntology.value);
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/brapi/v2/ontology-terms?${parameters.toString()}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      },
    );

    if (!response.ok) {
      let detail = `API request failed with status ${response.status}`;
      try {
        const payload = await response.json();
        detail = payload?.detail?.message || payload?.detail || detail;
      } catch {
        // Keep the HTTP status message if the error body is not JSON.
      }
      throw new Error(detail);
    }

    const payload = await response.json();
    const records = Array.isArray(payload?.result?.data)
      ? payload.result.data
      : [];

    terms.value = records
      .filter((term) => term && typeof term === "object")
      .map((term) => ({
        ontologyTermDbId:
          term.ontologyTermDbId || term.ontologyTermIRI || term.ontologyCurie,
        ontologyTermIRI: term.ontologyTermIRI || term.ontologyTermDbId || "",
        ontologyTermName:
          term.ontologyTermName || term.ontologyCurie || "Unnamed term",
        ontologyName: friendlyOntology(term.ontologyName, term.ontologyCurie),
        ontologyCurie: term.ontologyCurie || term.ontologyTermDbId || "Unknown",
        bioPortalUrl: term.bioPortalUrl || null,
      }));

    const pagination = payload?.metadata?.pagination || {};
    totalCount.value = Number(pagination.totalCount || 0);
    totalPages.value = Number(pagination.totalPages || 0);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    terms.value = [];
    totalCount.value = 0;
    totalPages.value = 0;
    errorMessage.value =
      error instanceof Error ? error.message : "An unexpected error occurred.";
  } finally {
    if (activeController === controller) {
      loading.value = false;
      activeController = null;
    }
  }
}

function applySearch() {
  appliedSearch.value = searchInput.value;
  appliedOntology.value = ontologyInput.value;
  appliedExact.value = exactInput.value;
  page.value = 0;
  loadTerms();
}

function clearSearch() {
  searchInput.value = "";
  ontologyInput.value = "";
  exactInput.value = false;
  appliedSearch.value = "";
  appliedOntology.value = "";
  appliedExact.value = false;
  page.value = 0;
  loadTerms();
}

function refresh() {
  loadTerms();
}

function changePageSize() {
  page.value = 0;
  loadTerms();
}

function termLink(term) {
  if (term.bioPortalUrl) return term.bioPortalUrl;
  if (
    term.ontologyTermIRI &&
    !term.ontologyTermIRI.includes("mydata.example.org")
  ) {
    return term.ontologyTermIRI;
  }
  return null;
}

function ontologySourceUrl(term) {
  const iri = String(term.ontologyTermIRI || "");
  if (iri.startsWith("http://purl.obolibrary.org/obo/")) return iri;
  if (iri.startsWith("https://purl.obolibrary.org/obo/")) return iri;
  if (iri.includes("bioontology.org/ontology/")) return iri;
  return null;
}

function friendlyOntology(name, curie) {
  const code = String(curie || "").split(":", 1)[0].toUpperCase();
  const names = {
    TO: "Plant Trait Ontology",
    PO: "Plant Ontology",
    CO: "Crop Ontology",
    UO: "Units of Measurement Ontology",
    PECO: "Plant Experimental Conditions Ontology",
    PATO: "Phenotype and Trait Ontology",
    ENVO: "Environment Ontology",
    CDNO: "Compositional Dietary Nutrition Ontology",
    NCBITAXON: "NCBI Taxonomy",
    AGRO: "Agronomy Ontology",
  };
  return names[code] || name || "Ontology not identified";
}

async function copyIri(term) {
  if (!term.ontologyTermIRI) return;
  try {
    await navigator.clipboard.writeText(term.ontologyTermIRI);
    copiedIri.value = term.ontologyTermIRI;
    window.setTimeout(function () {
      if (copiedIri.value === term.ontologyTermIRI) copiedIri.value = "";
    }, 1600);
  } catch {
    errorMessage.value = "The browser could not copy the ontology IRI.";
  }
}

function previousPage() {
  if (page.value === 0 || loading.value) return;
  page.value -= 1;
  loadTerms();
}

function nextPage() {
  if (page.value + 1 >= totalPages.value || loading.value) return;
  page.value += 1;
  loadTerms();
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

onMounted(loadTerms);
</script>

<style scoped>
.ontology-search {
  --ink: #183b2d;
  --muted: #66786f;
  --primary: #246b4b;
  --primary-dark: #18573b;
  --border: #d8e2dc;
  min-height: 100vh;
  padding: 32px;
  color: var(--ink);
  background: #f3f6f4;
}

.page-header,
.results-heading {
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
}

h2 {
  margin-bottom: 6px;
}

.eyebrow {
  margin-bottom: 5px;
  color: #287a55;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.subtitle,
.results-heading p {
  margin-bottom: 0;
  color: var(--muted);
}

.panel {
  margin-top: 24px;
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: 15px;
  background: #fff;
}

.search-form {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(220px, 0.45fr) auto auto;
  align-items: end;
  gap: 15px;
}

.field {
  display: grid;
  gap: 7px;
  font-weight: 750;
}

input[type="search"],
select {
  min-height: 46px;
  padding: 0 13px;
  border: 1px solid #c7d5cd;
  border-radius: 9px;
  color: var(--ink);
  background: #fff;
  font: inherit;
}

input:focus,
select:focus {
  border-color: #287a55;
  outline: 3px solid rgb(40 122 85 / 13%);
}

.exact-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 46px;
  font-weight: 700;
  white-space: nowrap;
}

input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--primary);
}

.form-actions {
  display: flex;
  gap: 8px;
}

button,
.view-button {
  min-height: 44px;
  padding: 0 17px;
  border-radius: 9px;
  font: inherit;
  font-weight: 750;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.primary-button {
  border: 1px solid var(--primary);
  color: #fff;
  background: var(--primary);
}

.primary-button:hover:not(:disabled) {
  background: var(--primary-dark);
}

.secondary-button {
  border: 1px solid #c8d5ce;
  color: #265d45;
  background: #fff;
}

.secondary-button:hover:not(:disabled) {
  background: #f0f6f3;
}

.alert {
  display: grid;
  gap: 4px;
  margin-top: 20px;
  padding: 15px 17px;
  border: 1px solid #eab8b8;
  border-radius: 11px;
  color: #842f2f;
  background: #fff0f0;
}

.result-count {
  padding: 7px 11px;
  border-radius: 999px;
  color: #226243;
  background: #e2f2e9;
  font-size: 0.8rem;
  font-weight: 800;
  white-space: nowrap;
}

.results-tools,
.page-size-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-size-control {
  color: var(--muted);
  font-size: 0.84rem;
  font-weight: 700;
}

.page-size-control select {
  min-height: 36px;
  padding: 0 28px 0 9px;
}

.state-message {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 65px 20px;
  color: var(--muted);
  text-align: center;
}

.spinner {
  width: 26px;
  height: 26px;
  border: 3px solid #d9e9e0;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.table-container {
  margin-top: 20px;
  overflow: hidden;
  border: 1px solid #dbe4df;
  border-radius: 12px;
}

table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}

th:first-child,
td:first-child {
  width: 38%;
}

th:nth-child(2),
td:nth-child(2) {
  width: 25%;
}

th:last-child,
td:last-child {
  width: 37%;
}

th {
  padding: 14px 16px;
  border-bottom: 2px solid #d6e0da;
  color: #365a49;
  background: #edf4f0;
  font-size: 0.78rem;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.035em;
}

td {
  padding: 17px 16px;
  border-bottom: 1px solid #e1e9e4;
  vertical-align: top;
}

tbody tr:last-child td {
  border-bottom: 0;
}

tbody tr:hover {
  background: #f5faf7;
}

.term-name {
  display: block;
  max-width: 100%;
  color: var(--ink);
  font-size: 1rem;
  overflow-wrap: anywhere;
}

.term-link {
  color: #196946;
  font-weight: 750;
  text-decoration: none;
}

.term-link:hover {
  text-decoration: underline;
}

.ontology-badge {
  display: inline-block;
  padding: 5px 9px;
  border-radius: 999px;
  color: #17563a;
  background: #e2f2e9;
  font-size: 0.78rem;
  font-weight: 800;
}

.ontology-source-link {
  text-decoration: none;
}

.ontology-source-link:hover {
  color: #10452e;
  background: #d3eadf;
  text-decoration: underline;
}

.action-cell {
  text-align: right;
  white-space: nowrap;
}

.copy-button {
  min-height: 38px;
  margin-right: 7px;
  padding: 0 12px;
  border: 1px solid #c8d5ce;
  color: #265d45;
  background: #fff;
}

.copy-button:hover {
  background: #f0f6f3;
}

.view-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  color: #fff;
  background: var(--primary);
  text-decoration: none;
  white-space: nowrap;
}

.view-button:hover {
  background: var(--primary-dark);
}


.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-top: 22px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1050px) {
  .search-form {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 700px) {
  .ontology-search {
    padding: 18px;
  }

  .page-header,
  .results-heading,
  .search-form {
    display: grid;
    grid-template-columns: 1fr;
  }

  .form-actions {
    flex-wrap: wrap;
  }

  .results-tools {
    justify-content: space-between;
  }

  .panel {
    padding: 17px;
  }
}
</style>





