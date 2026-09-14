<template>
  <main class="dataset-explorer">
    <header class="page-header">
      <div>
        <p class="eyebrow">Semantic data</p>

        <h1>Dataset Explorer</h1>

        <p class="subtitle">
          Explore datasets and their associated traits,
          germplasm, species and NCBI Taxon terms.
        </p>
      </div>

      <button
        type="button"
        class="primary-button"
        :disabled="loading"
        @click="loadDatasets"
      >
        {{ loading ? "Loading..." : "Refresh" }}
      </button>
    </header>

    <section class="search-panel">
      <label for="dataset-search">
        Search datasets
      </label>

      <div class="search-controls">
        <input
          id="dataset-search"
          v-model.trim="search"
          type="search"
          placeholder="Search by dataset, species or NCBI Taxon"
          @keyup.enter="applySearch"
        />

        <button
          type="button"
          class="primary-button"
          :disabled="loading"
          @click="applySearch"
        >
          Search
        </button>

        <button
          v-if="search || appliedSearch"
          type="button"
          class="secondary-button"
          :disabled="loading"
          @click="clearSearch"
        >
          Clear
        </button>
      </div>
    </section>

    <section
      v-if="errorMessage"
      class="error-message"
    >
      <strong>Unable to load datasets.</strong>
      <span>{{ errorMessage }}</span>
    </section>

    <section class="table-panel">
      <div class="table-heading">
        <div>
          <h2>Available datasets</h2>

          <p>
            Select a dataset to view its observations.
          </p>
        </div>

        <span class="result-count">
          {{ formatNumber(totalCount) }}
          {{ totalCount === 1 ? "dataset" : "datasets" }}
        </span>
      </div>

      <div
        v-if="loading"
        class="state-message"
      >
        Loading dataset information...
      </div>

      <div
        v-else-if="datasets.length === 0"
        class="state-message"
      >
        No datasets matched your search.
      </div>

      <div
        v-else
        class="table-container"
      >
        <table class="dataset-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Number of traits</th>
              <th>Number of germplasm</th>
              <th>Species</th>
              <th>NCBI Taxon</th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="dataset in datasets"
              :key="dataset.datasetDbId"
              tabindex="0"
              @click="openDataset(dataset)"
              @keyup.enter="openDataset(dataset)"
            >
              <!-- Dataset name -->
              <td>
                <div class="dataset-name">
                  {{ dataset.datasetName }}
                </div>

                
              </td>

              <!-- Number of traits -->
              <td class="number-cell">
                {{
                  formatNumber(
                    dataset.numberOfTraits
                  )
                }}
              </td>

              <!-- Number of germplasm -->
              <td class="number-cell">
                {{
                  formatNumber(
                    dataset.numberOfGermplasm
                  )
                }}
              </td>

              <!-- Species -->
              <td>
                <div
                  v-if="dataset.species.length"
                  class="value-list"
                >
                  <em
                    v-for="speciesName in
                      dataset.species"
                    :key="speciesName"
                    class="species-name"
                  >
                    {{ speciesName }}
                  </em>
                </div>

                <span
                  v-else
                  class="missing-value"
                >
                  Not recorded
                </span>
              </td>

              <!-- NCBI Taxon BioPortal link -->
              <td>
                <div
                  v-if="
                    dataset.taxonomyReferences.length
                  "
                  class="value-list"
                >
                  <template
                    v-for="taxonomy in
                      dataset.taxonomyReferences"
                    :key="
                      taxonomy.curie ||
                      taxonomy.iri
                    "
                  >
                    <a
                      v-if="taxonomy.bioPortalUrl"
                      :href="taxonomy.bioPortalUrl"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="taxon-link"
                      :title="
                        `Open ${
                          taxonomy.curie ||
                          'NCBI Taxon'
                        } in BioPortal`
                      "
                      @click.stop
                    >
                      {{
                        taxonomy.curie ||
                        taxonomy.iri
                      }}

                      <span
                        class="external-link"
                        aria-hidden="true"
                      >
                        ↗
                      </span>
                    </a>

                    <span
                      v-else-if="
                        taxonomy.curie ||
                        taxonomy.iri
                      "
                      class="taxon-value"
                    >
                      {{
                        taxonomy.curie ||
                        taxonomy.iri
                      }}
                    </span>
                  </template>
                </div>

                <span
                  v-else
                  class="missing-value"
                >
                  Not mapped
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer
        v-if="totalPages > 1"
        class="pagination"
      >
        <button
          type="button"
          class="secondary-button"
          :disabled="page === 0 || loading"
          @click="previousPage"
        >
          Previous
        </button>

        <span>
          Page {{ page + 1 }} of {{ totalPages }}
        </span>

        <button
          type="button"
          class="secondary-button"
          :disabled="
            page + 1 >= totalPages ||
            loading
          "
          @click="nextPage"
        >
          Next
        </button>
      </footer>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

/*
 * The environment variable is preferred for deployment.
 * During local development, FastAPI runs on port 8001.
 */
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8001"
).replace(/\/$/, "");

const datasets = ref([]);
const loading = ref(false);
const errorMessage = ref("");

const search = ref("");
const appliedSearch = ref("");

const page = ref(0);
const pageSize = ref(20);
const totalCount = ref(0);
const totalPages = ref(0);

/*
 * Convert database values separated by |||
 * into JavaScript arrays.
 */
function splitValues(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item).trim())
      .filter(Boolean);
  }

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return [];
  }

  return String(value)
    .split("|||")
    .map((item) => item.trim())
    .filter(Boolean);
}

/*
 * Extract the numeric NCBI Taxon ID.
 *
 * Supported formats:
 * NCBITaxon:4555
 * NCBITAXON:4555
 * NCBITaxon_4555
 * http://purl.obolibrary.org/obo/NCBITaxon_4555
 * http://purl.bioontology.org/ontology/NCBITAXON/4555
 */
function extractTaxonomyId(curie, iri) {
  const values = [curie, iri];

  for (const value of values) {
    if (!value) {
      continue;
    }

    const text = String(value).trim();

    const patterns = [
      /NCBITaxon:(\d+)$/i,
      /NCBITaxon_(\d+)$/i,
      /NCBITAXON\/(\d+)$/i,
      /\/(\d+)$/
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);

      if (match) {
        return match[1];
      }
    }
  }

  return null;
}

/*
 * Construct the link to the NCBI Taxon
 * class page in BioPortal.
 */
function createBioPortalUrl(curie, iri) {
  const taxonomyId =
    extractTaxonomyId(curie, iri);

  if (!taxonomyId) {
    return null;
  }

  return (
    "https://bioportal.bioontology.org/" +
    "ontologies/NCBITAXON" +
    `?conceptid=${encodeURIComponent(
      taxonomyId
    )}` +
    "&p=classes"
  );
}

/*
 * Convert a taxonomy record into one
 * consistent format.
 */
function createTaxonomyReference(
  curie,
  iri
) {
  const cleanedCurie =
    curie !== null &&
    curie !== undefined &&
    curie !== ""
      ? String(curie).trim()
      : null;

  const cleanedIRI =
    iri !== null &&
    iri !== undefined &&
    iri !== ""
      ? String(iri).trim()
      : null;

  return {
    curie: cleanedCurie,
    iri: cleanedIRI,
    bioPortalUrl: createBioPortalUrl(
      cleanedCurie,
      cleanedIRI
    )
  };
}

/*
 * Normalise records returned by either:
 *
 * 1. The BrAPI endpoint;
 * 2. An earlier API format;
 * 3. Raw semantic_dataset_explorer fields.
 */
function normaliseDataset(record) {
  const species = splitValues(
    record.species ??
    record.speciesName ??
    record.species_names
  );

  let taxonomyReferences = [];

  /*
   * API already returned taxonomyReferences.
   */
  if (
    Array.isArray(
      record.taxonomyReferences
    )
  ) {
    taxonomyReferences =
      record.taxonomyReferences
        .map((taxonomy) => {
          const curie =
            taxonomy.curie ??
            taxonomy.ncbiTaxon ??
            taxonomy.ncbi_taxon ??
            null;

          const iri =
            taxonomy.iri ??
            taxonomy.ncbiTaxonIRI ??
            taxonomy.ncbi_taxon_iri ??
            null;

          return createTaxonomyReference(
            curie,
            iri
          );
        })
        .filter(
          (taxonomy) =>
            taxonomy.curie ||
            taxonomy.iri
        );
  }

  /*
   * API returned NCBI Taxon fields separately.
   */
  if (
    taxonomyReferences.length === 0
  ) {
    const taxonomyCuries =
      splitValues(
        record.ncbiTaxon ??
        record.ncbi_taxon ??
        record.ncbiTaxonCURIE ??
        record.ncbi_taxon_curie ??
        record.ncbi_taxon_curies
      );

    const taxonomyIRIs =
      splitValues(
        record.ncbiTaxonIRI ??
        record.ncbi_taxon_iri ??
        record.ncbi_taxon_iris
      );

    const taxonomyCount = Math.max(
      taxonomyCuries.length,
      taxonomyIRIs.length
    );

    for (
      let index = 0;
      index < taxonomyCount;
      index += 1
    ) {
      const curie =
        taxonomyCuries[index] || null;

      const iri =
        taxonomyIRIs[index] || null;

      taxonomyReferences.push(
        createTaxonomyReference(
          curie,
          iri
        )
      );
    }
  }

  return {
    datasetDbId: String(
      record.datasetDbId ??
      record.dataset_id ??
      ""
    ),

    datasetName:
      record.datasetName ??
      record.name ??
      record.dataset_name ??
      "Unnamed dataset",

    numberOfTraits: Number(
      record.numberOfTraits ??
      record.traitCount ??
      record.number_of_traits ??
      0
    ),

    numberOfGermplasm: Number(
      record.numberOfGermplasm ??
      record.germplasmCount ??
      record.number_of_germplasm ??
      0
    ),

    species,

    taxonomyReferences
  };
}

/*
 * Load datasets from the FastAPI endpoint.
 */
async function loadDatasets() {
  loading.value = true;
  errorMessage.value = "";

  const query = new URLSearchParams({
    pageSize: String(pageSize.value),
    page: String(page.value)
  });

  if (appliedSearch.value) {
    query.set(
      "search",
      appliedSearch.value
    );
  }

  try {
    const url =
      `${API_BASE_URL}/brapi/v2/datasets?` +
      query.toString();

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json"
      }
    });

    if (!response.ok) {
      let detail =
        `API request failed with status ${response.status}`;

      try {
        const errorPayload = await response.json();
        detail =
          errorPayload?.detail?.message ||
          errorPayload?.detail ||
          detail;
      } catch {
        // Keep the HTTP status message when the body is not JSON.
      }

      throw new Error(detail);
    }

    const payload =
      await response.json();

    let records = [];

    /*
     * BrAPI response:
     * result.data
     */
    if (
      Array.isArray(
        payload?.result?.data
      )
    ) {
      records =
        payload.result.data;
    }

    /*
     * Direct API array response.
     */
    else if (Array.isArray(payload)) {
      records = payload;
    }

    /*
     * Alternative API response:
     * data
     */
    else if (
      Array.isArray(payload?.data)
    ) {
      records = payload.data;
    }

    datasets.value = records.map(
      normaliseDataset
    );

    const pagination =
      payload?.metadata?.pagination;

    totalCount.value = Number(
      pagination?.totalCount ??
      datasets.value.length
    );

    totalPages.value = Number(
      pagination?.totalPages ??
      (totalCount.value > 0 ? 1 : 0)
    );
  } catch (error) {
    datasets.value = [];
    totalCount.value = 0;
    totalPages.value = 0;

    errorMessage.value =
      error instanceof Error
        ? error.message
        : "An unexpected error occurred.";
  } finally {
    loading.value = false;
  }
}

function applySearch() {
  appliedSearch.value =
    search.value;

  page.value = 0;

  loadDatasets();
}

function clearSearch() {
  search.value = "";
  appliedSearch.value = "";
  page.value = 0;

  loadDatasets();
}

function previousPage() {
  if (page.value === 0) {
    return;
  }

  page.value -= 1;

  loadDatasets();
}

function nextPage() {
  if (
    page.value + 1 >=
    totalPages.value
  ) {
    return;
  }

  page.value += 1;

  loadDatasets();
}

/*
 * Open observations for the selected dataset.
 *
 * The router must contain a route named:
 * observations
 */
function openDataset(dataset) {
  router.push({
    name: "observations",
    query: {
      dataset_id:
        dataset.datasetDbId
    }
  });
}

function formatNumber(value) {
  const number = Number(value || 0);

  return new Intl.NumberFormat(
    "en-GB"
  ).format(number);
}

onMounted(() => {
  loadDatasets();
});
</script>

<style scoped>
.dataset-explorer {
  min-height: 100vh;
  padding: 32px;
  color: #183b2d;
  background: #f3f6f4;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 5px;
  color: #287a55;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 8px;
  font-size: clamp(
    2rem,
    4vw,
    3rem
  );
}

h2 {
  margin: 0 0 5px;
}

.subtitle,
.table-heading p {
  margin: 0;
  color: #66786f;
}

.primary-button,
.secondary-button {
  padding: 11px 18px;
  border-radius: 9px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  border: 0;
  color: white;
  background: #246b4b;
}

.primary-button:hover {
  background: #18573b;
}

.secondary-button {
  border: 1px solid #c8d5ce;
  color: #265d45;
  background: white;
}

.secondary-button:hover {
  background: #f0f6f3;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.search-panel {
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #d8e2dc;
  border-radius: 14px;
  background: white;
}

.search-panel label {
  display: block;
  margin-bottom: 8px;
  font-weight: 750;
}

.search-controls {
  display: flex;
  gap: 10px;
}

.search-controls input {
  flex: 1;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid #c7d5cd;
  border-radius: 9px;
  color: inherit;
  font: inherit;
}

.search-controls input:focus {
  border-color: #287a55;
  outline: 3px solid
    rgb(40 122 85 / 13%);
}

.error-message {
  display: flex;
  gap: 8px;
  padding: 14px 17px;
  margin-bottom: 20px;
  border: 1px solid #eab8b8;
  border-radius: 11px;
  color: #842f2f;
  background: #fff0f0;
}

.table-panel {
  padding: 22px;
  border: 1px solid #d8e2dc;
  border-radius: 15px;
  background: white;
}

.table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 19px;
}

.result-count {
  padding: 7px 11px;
  border-radius: 999px;
  color: #226243;
  background: #e2f2e9;
  font-size: 0.8rem;
  font-weight: 800;
}

.table-container {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #dbe4df;
  border-radius: 12px;
}

.dataset-table {
  width: 100%;
  min-width: 950px;
  border-collapse: collapse;
}

.dataset-table th {
  padding: 14px 17px;
  border-bottom: 2px solid #d6e0da;
  color: #365a49;
  background: #edf4f0;
  font-size: 0.78rem;
  font-weight: 800;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.035em;
}

.dataset-table td {
  padding: 18px 17px;
  border-bottom: 1px solid #e1e9e4;
  vertical-align: top;
}

.dataset-table tbody tr {
  cursor: pointer;
  transition:
    background-color
    0.15s ease;
}

.dataset-table tbody tr:hover,
.dataset-table tbody tr:focus {
  background: #f0f7f3;
  outline: none;
}

.dataset-table
tbody
tr:last-child
td {
  border-bottom: 0;
}

.dataset-name {
  max-width: 350px;
  color: #173d2e;
  font-weight: 800;
}

.dataset-id {
  margin-top: 5px;
  color: #788980;
  font-size: 0.74rem;
}

.number-cell {
  font-size: 1rem;
  font-weight: 800;
  text-align: center;
}

.value-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}

.species-name {
  color: #294d3d;
}

.taxon-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #196946;
  font-weight: 750;
  text-decoration: none;
}

.taxon-link:hover {
  color: #104b32;
  text-decoration: underline;
}

.taxon-value {
  color: #196946;
  font-weight: 750;
}

.external-link {
  font-size: 0.8rem;
}

.missing-value {
  color: #8a9891;
  font-style: italic;
}

.state-message {
  padding: 65px 20px;
  color: #6c7c74;
  text-align: center;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-top: 20px;
}

@media (max-width: 750px) {
  .dataset-explorer {
    padding: 18px;
  }

  .page-header,
  .search-controls {
    align-items: stretch;
    flex-direction: column;
  }

  .table-panel {
    padding: 14px;
  }
}
</style>
