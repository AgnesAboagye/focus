<template>
  <main class="trait-browser">
    <header class="page-header">
      <div>
        <p class="eyebrow">Semantic data</p>
        <h1>Trait Browser</h1>
        <p class="subtitle">
          Browse Germinate traits annotated with ontology terms.
        </p>
      </div>

      <button
        type="button"
        class="secondary-button"
        :disabled="loading"
        @click="loadTraits"
      >
        {{ loading ? "Loading…" : "Refresh traits" }}
      </button>
    </header>

    <section class="search-panel" aria-labelledby="trait-search-heading">
      <label for="trait-search" id="trait-search-heading">
        Search traits
      </label>

      <div class="search-row">
        <input
          id="trait-search"
          v-model.trim="searchTerm"
          type="search"
          maxlength="200"
          autocomplete="off"
          placeholder="Search by trait name, description, ontology, label or IRI"
          @keydown.esc="searchTerm = ''"
        />

        <button
          v-if="searchTerm"
          type="button"
          class="secondary-button"
          @click="searchTerm = ''"
        >
          Clear
        </button>
      </div>
    </section>

    <div v-if="error" class="alert" role="alert">
      <strong>Unable to load traits.</strong>
      <span>{{ error }}</span>
      <button type="button" class="retry-button" @click="loadTraits">
        Try again
      </button>
    </div>

    <section class="results-panel" aria-labelledby="trait-results-heading">
      <header class="results-header">
        <div>
          <h2 id="trait-results-heading">Available traits</h2>
          <p>{{ resultDescription }}</p>
        </div>

        <span class="result-count">
          {{ formatInteger(filteredTraits.length) }}
          {{ filteredTraits.length === 1 ? "trait" : "traits" }}
        </span>
      </header>

      <div v-if="loading" class="state-message" aria-live="polite">
        <span class="spinner" aria-hidden="true"></span>
        <span>Loading traits…</span>
      </div>

      <div v-else-if="filteredTraits.length === 0" class="state-message">
        <strong>No traits found.</strong>
        <span v-if="searchTerm">Try a different search term.</span>
        <span v-else>No ontology-annotated traits were returned by the API.</span>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Trait name</th>
              <th>Description</th>
              <th>Ontology</th>
              <th>Ontology ID</th>
              <th>Ontology label</th>
              <th>Ontology IRI</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="trait in filteredTraits" :key="trait.traitDbId">
              <td>
                <strong class="trait-name">
                  {{ trait.traitName || "Unnamed trait" }}
                </strong>
              </td>

              <td class="description-cell">
                {{ trait.description || "No description recorded" }}
              </td>

              <td>
                <span
                  v-if="ontologyName(trait)"
                  class="ontology-badge"
                >
                  {{ ontologyName(trait) }}
                </span>
                <span v-else class="missing-value">Not mapped</span>
              </td>

              <td>
                <a
                  v-if="ontologyIri(trait) && ontologyId(trait)"
                  :href="ontologyIri(trait)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ontology-id"
                >
                  {{ ontologyId(trait) }} <span aria-hidden="true">↗</span>
                </a>
                <span v-else class="missing-value">Not mapped</span>
              </td>

              <td>
                {{ ontologyLabel(trait) || "Not recorded" }}
              </td>

              <td>
                <a
                  v-if="ontologyIri(trait)"
                  :href="ontologyIri(trait)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="iri-link"
                >
                  {{ ontologyIri(trait) }}
                </a>
                <span v-else class="missing-value">Not mapped</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<script>
import api from "../../services/api";

export default {
  name: "TraitBrowser",

  data() {
    return {
      traits: [],
      searchTerm: "",
      loading: false,
      error: "",
    };
  },

  computed: {
    filteredTraits() {
      const term = this.searchTerm.toLowerCase().trim();
      if (!term) return this.traits;

      return this.traits.filter((trait) =>
        [
          trait.traitName,
          trait.description,
          this.ontologyName(trait),
          this.ontologyId(trait),
          this.ontologyLabel(trait),
          this.ontologyIri(trait),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(term),
      );
    },

    resultDescription() {
      if (this.searchTerm) {
        return `Results matching “${this.searchTerm}”.`;
      }
      return "Traits and their mapped ontology terms.";
    },
  },

  methods: {
    ontologyName(trait) {
      return trait.ontologyReference?.ontologyName || "";
    },

    ontologyId(trait) {
      return (
        trait.ontologyReference?.ontologyDbId ||
        trait.additionalInfo?.ontologyCURIE ||
        ""
      );
    },

    ontologyLabel(trait) {
      return trait.additionalInfo?.ontologyLabel || "";
    },

    ontologyIri(trait) {
      return trait.additionalInfo?.ontologyIRI || "";
    },

    async loadTraits() {
      this.loading = true;
      this.error = "";

      try {
        const response = await api.get("/brapi/v2/traits", {
          params: {
            page: 0,
            pageSize: 1000,
          },
        });

        const records = response.data?.result?.data;
        this.traits = Array.isArray(records) ? records : [];
      } catch (error) {
        this.traits = [];

        if (error.response) {
          const detail = error.response.data?.detail;
          this.error =
            (typeof detail === "string" && detail) ||
            `API returned status ${error.response.status}.`;
        } else if (error.request) {
          this.error =
            "Vue cannot reach FastAPI. Confirm that FastAPI is running on " +
            "port 8001 and that the Vue API base URL is correct.";
        } else {
          this.error = error.message || "An unexpected error occurred.";
        }
      } finally {
        this.loading = false;
      }
    },

    formatInteger(value) {
      return new Intl.NumberFormat("en-GB").format(Number(value || 0));
    },
  },

  mounted() {
    this.loadTraits();
  },
};
</script>

<style scoped>
.trait-browser {
  --ink: #153d30;
  --muted: #66786f;
  --primary: #23754f;
  --primary-dark: #175c3c;
  --border: #d6e1db;
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  padding: 32px;
  color: var(--ink);
  background: #f4f7f5;
}

.page-header,
.results-header,
.search-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 8px;
  font-size: clamp(2.2rem, 4vw, 3.15rem);
}

h2 {
  margin-bottom: 5px;
}

.eyebrow {
  margin-bottom: 6px;
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.subtitle,
.results-header p {
  margin-bottom: 0;
  color: var(--muted);
}

.search-panel,
.results-panel {
  margin-top: 24px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

.search-panel label {
  display: block;
  margin-bottom: 9px;
  font-weight: 800;
}

.search-row input {
  width: 100%;
  min-height: 48px;
  padding: 10px 14px;
  border: 1px solid #c4d3cb;
  border-radius: 9px;
  color: var(--ink);
  background: #fff;
  font: inherit;
}

.search-row input:focus {
  border-color: var(--primary);
  outline: 3px solid rgb(35 117 79 / 14%);
}

button {
  min-height: 43px;
  padding: 0 16px;
  border-radius: 9px;
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.secondary-button,
.retry-button {
  border: 1px solid #c4d3cb;
  color: var(--primary-dark);
  background: #fff;
}

.secondary-button:hover:not(:disabled),
.retry-button:hover {
  background: #edf5f1;
}

.alert {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid #e6b8b8;
  border-radius: 11px;
  color: #862e2e;
  background: #fff0f0;
}

.retry-button {
  margin-left: auto;
}

.result-count {
  flex: none;
  padding: 7px 11px;
  border-radius: 999px;
  color: #1d6242;
  background: #e1f2e9;
  font-size: 0.8rem;
  font-weight: 800;
}

.state-message {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 64px 20px;
  color: var(--muted);
  text-align: center;
}

.spinner {
  width: 27px;
  height: 27px;
  border: 3px solid #d8e8df;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.table-wrapper {
  margin-top: 20px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 11px;
}

table {
  width: 100%;
  min-width: 1080px;
  border-collapse: collapse;
  background: #fff;
}

th {
  padding: 13px 14px;
  border-bottom: 2px solid #d3dfd8;
  color: #365c4a;
  background: #edf4f0;
  font-size: 0.75rem;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.035em;
}

td {
  padding: 16px 14px;
  border-bottom: 1px solid #e0e8e3;
  vertical-align: top;
  overflow-wrap: anywhere;
}

tbody tr:last-child td {
  border-bottom: 0;
}

tbody tr:hover {
  background: #f4faf7;
}

.trait-name {
  font-size: 1rem;
}

.description-cell {
  max-width: 300px;
  color: #405d4f;
  line-height: 1.55;
}

.ontology-badge {
  display: inline-block;
  padding: 5px 9px;
  border-radius: 999px;
  color: #195d3d;
  background: #e1f2e9;
  font-size: 0.76rem;
  font-weight: 800;
}

.ontology-id,
.iri-link {
  color: var(--primary-dark);
  font-weight: 750;
  text-decoration: none;
}

.ontology-id:hover,
.iri-link:hover {
  text-decoration: underline;
}

.iri-link {
  display: inline-block;
  color: #0d6efd;
  font-family: inherit;
  font-size: inherit;
  font-weight: 400;
  text-decoration: underline;
  overflow-wrap: anywhere;
}

.missing-value {
  color: #87968e;
  font-style: italic;
}

@media (max-width: 760px) {
  .trait-browser {
    padding: 20px 14px 40px;
  }

  .page-header,
  .results-header,
  .search-row,
  .alert {
    align-items: stretch;
    flex-direction: column;
  }

  .search-panel,
  .results-panel {
    padding: 17px;
  }

  .retry-button {
    margin-left: 0;
  }
}
</style>
