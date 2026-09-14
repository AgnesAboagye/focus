import { createRouter, createWebHistory } from "vue-router";

import HomePage from "../views/HomePage.vue";

// Standard Germinate Data pages
import Germplasm from "../views/GermplasmData.vue";
import GenotypicData from "../views/GenotypesData.vue";
import TrialsData from "../views/TrialsData.vue";
import ClimateData from "../views/ClimateData.vue";


// New Semantic Data pages
import TraitBrowser from "../views/semantics/TraitBrowser.vue";
import DatasetExplorer from "../views/semantics/DatasetExplorer.vue";
import SemanticComparison from "../views/semantics/SemanticComparison.vue";
import SpeciesComparison from "../views/semantics/SpeciesComparison.vue";
import OntologyTermSearch from "../views/semantics/OntologyTermSearch.vue";


const routes = [
  {
    path: "/",
    component: HomePage,
  },

  // Standard Germinate Data routes
  {
    path: "/germplasm",
    component: Germplasm,
  },
  {
    path: "/genotypic-data",
    component: GenotypicData,
  },
  {
    path: "/trials-data",
    component: TrialsData,
  },
  
  {
    path: "/climate-data",
    component: ClimateData,
  },
  

  // Semantic Data routes
  {
    path: "/brapi/v2/traits",
    component: TraitBrowser,
  },

  {
  path: "/brapi/v2/datasets",
  component: DatasetExplorer
 }, 
  
  {
    path: "/brapi/v2/semantic-comparison",
    component: SemanticComparison,
  },

  {
    path: "/brapi/v2/species-comparison",
    component: SpeciesComparison,
  },


   {
    path: "/brapi/v2/ontology-search",
    component: OntologyTermSearch,
  },

];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;