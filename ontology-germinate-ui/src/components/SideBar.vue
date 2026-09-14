<template>
  <aside class="sidebar">
    <div class="menu-section">
      <h6>Data</h6>

      <RouterLink to="/germplasm">
        Germplasm
      </RouterLink>

      <RouterLink to="/genotypic-data">
        Genotypic data
      </RouterLink>

      <RouterLink to="/trials-data">
        Trials data
      </RouterLink>

      <RouterLink to="/climate-data">
        Climate data
      </RouterLink>
    </div>

    <div class="menu-section">
      <h6>Semantic data</h6>

      <RouterLink to="/brapi/v2/traits">
        Trait Browser
      </RouterLink>

      <RouterLink to="/brapi/v2/datasets">
        Dataset Explorer
      </RouterLink>

      <RouterLink to="/brapi/v2/semantic-comparison">
        Semantic Comparison
      </RouterLink>

      <RouterLink to="/brapi/v2/species-comparison">
        Species Comparison
      </RouterLink>

      <RouterLink to="/brapi/v2/ontology-search">
        Ontology Term Search
      </RouterLink>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  flex-shrink: 0;
  min-height: calc(100vh - 72px);
  padding: 20px;
  color: white;
  background-color: #1f2937;
}

.menu-section {
  margin-bottom: 25px;
}

.menu-section h6 {
  margin-bottom: 10px;
  color: #9ca3af;
  font-size: 12px;
  text-transform: uppercase;
}

.sidebar a {
  display: block;
  margin-bottom: 4px;
  padding: 10px 12px;
  color: white;
  text-decoration: none;
  border-radius: 5px;
}

.sidebar a:hover {
  background-color: #374151;
}

.sidebar a.router-link-active {
  background-color: #2563eb;
}
</style>