from fastapi import APIRouter, Query
from sparql_client import run_sparql

router = APIRouter(
    prefix="/api/rdf",
    tags=["RDF / SPARQL"]
)

@router.get("/predicates")
def rdf_predicates():
    query = """
    SELECT DISTINCT ?p
    WHERE {
      ?s ?p ?o .
    }
    LIMIT 100
    """
    return run_sparql(query)

@router.get("/health")
def rdf_health():
    query = """
    ASK {
      ?s ?p ?o
    }
    """
    return run_sparql(query)

@router.get("/sample")
def rdf_sample():
    query = """
    SELECT ?s ?p ?o
    WHERE {
      ?s ?p ?o .
    }
    LIMIT 50
    """
    return run_sparql(query)


@router.get("/traits")
def rdf_traits():
    query = """
    PREFIX germinate: <http://germinate.org/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?phenotype ?label ?trait
    WHERE {
        ?phenotype germinate:hasTrait ?trait .
        OPTIONAL {
            ?phenotype rdfs:label ?label .
        }
    }
    LIMIT 100
    """
    return run_sparql(query)



@router.get("/observations")
def rdf_observations(
    trait: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    filters = ""

    if trait:
        filters += f"""
        FILTER(STR(?trait) = "{trait}")
        """

    if search:
        filters += f"""
        FILTER(
            CONTAINS(LCASE(STR(?label)), LCASE("{search}")) ||
            CONTAINS(LCASE(STR(?value)), LCASE("{search}"))
        )
        """

    query = f"""
    PREFIX germinate: <http://germinate.org/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?observation ?phenotype ?label ?trait ?value
    WHERE {{
        ?observation germinate:hasPhenotype ?phenotype ;
                     germinate:phenotypeValue ?value .

        ?phenotype germinate:hasTrait ?trait .

        OPTIONAL {{
            ?phenotype rdfs:label ?label .
        }}

        {filters}
    }}
    LIMIT {limit}
    """

    return run_sparql(query)


@router.get("/compare")
def rdf_compare(
    ontology_iri: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    filters = []

    if ontology_iri:
        filters.append(f'FILTER(STR(?trait) = "{ontology_iri}")')

    if search:
        safe_search = search.replace('"', '\\"')
        filters.append(
            f'FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{safe_search}")))'
        )

    filter_block = "\n".join(filters)

    query = f"""
    PREFIX germinate: <http://germinate.org/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?observation ?phenotype ?label ?trait ?value
    WHERE {{
        ?observation germinate:hasPhenotype ?phenotype ;
                     germinate:hasValue ?value .

        ?phenotype germinate:hasTrait ?trait ;
                   rdfs:label ?label .

        {filter_block}
    }}
    LIMIT {limit}
    """

    return run_sparql(query)