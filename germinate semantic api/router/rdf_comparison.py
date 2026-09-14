import os
import re
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import quote, urlparse


load_dotenv()

SPARQL_ENDPOINT = os.getenv(
    "SPARQL_ENDPOINT",
    "http://127.0.0.1:8090/sparql",
)


try:
    SPARQL_TIMEOUT = int(
        os.getenv(
            "SPARQL_TIMEOUT",
            "60",
        )
    )
except ValueError:
    SPARQL_TIMEOUT = 60


router = APIRouter(
    prefix="/brapi/v2",
    tags=["BrAPI Semantic Comparison"],
)


def run_sparql(
    query: str,
) -> dict[str, Any]:
    """
    Send a complete SPARQL query to Ontopic
    using the SPARQL HTTP GET protocol.
    """

    headers = {
        "Accept": (
            "application/sparql-results+json"
        ),
    }

    try:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={
                "query": query,
            },
            headers=headers,
            timeout=SPARQL_TIMEOUT,
        )

        response.raise_for_status()

    except requests.exceptions.Timeout as error:
        raise HTTPException(
            status_code=504,
            detail={
                "message": (
                    "The Ontopic SPARQL endpoint "
                    "did not respond before the timeout."
                ),
                "endpoint": SPARQL_ENDPOINT,
            },
        ) from error

    except requests.exceptions.ConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "message": (
                    "FastAPI could not connect to "
                    "the Ontopic SPARQL endpoint."
                ),
                "endpoint": SPARQL_ENDPOINT,
            },
        ) from error

    except requests.exceptions.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "The Ontopic SPARQL endpoint "
                    "returned an HTTP error."
                ),
                "endpoint": SPARQL_ENDPOINT,
                "statusCode": response.status_code,
                "response": response.text[:3000],
                "sentQuery": query,
            },
        ) from error

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "The SPARQL request failed."
                ),
                "endpoint": SPARQL_ENDPOINT,
                "error": str(error),
            },
        ) from error

    try:
        result = response.json()

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "Ontopic did not return valid "
                    "SPARQL Results JSON."
                ),
                "endpoint": SPARQL_ENDPOINT,
                "response": response.text[:3000],
            },
        ) from error

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                "Ontopic returned an unexpected "
                "response structure."
            ),
        )

    return result


def get_bindings(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract bindings from a SPARQL Results
    JSON response.
    """

    bindings = (
        result
        .get("results", {})
        .get("bindings", [])
    )

    if not isinstance(bindings, list):
        return []

    return bindings


def binding_value(
    binding: dict[str, Any],
    variable: str,
) -> str | None:
    """
    Extract one value from a SPARQL binding.
    """

    value_object = binding.get(variable)

    if not isinstance(
        value_object,
        dict,
    ):
        return None

    value = value_object.get("value")

    if value is None:
        return None

    return str(value)


def binding_integer(
    binding: dict[str, Any],
    variable: str,
) -> int:
    """
    Convert a SPARQL numeric value to
    a Python integer.
    """

    value = binding_value(
        binding,
        variable,
    )

    if value is None:
        return 0

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return 0


def iri_to_curie(
    iri: str | None,
) -> str | None:
    """
    Convert an OBO ontology IRI into a CURIE.

    Example:
    http://purl.obolibrary.org/obo/TO_0000207
    becomes TO:0000207.
    """

    if not iri:
        return None

    term = iri.rstrip("/").split("/")[-1]

    obo_match = re.match(
        r"^([A-Za-z][A-Za-z0-9]*)_(.+)$",
        term,
    )

    if obo_match:
        prefix = obo_match.group(1)
        accession = obo_match.group(2)

        return f"{prefix}:{accession}"

    bioportal_match = re.search(
        r"/ontology/([^/]+)/([^/]+)$",
        iri,
        flags=re.IGNORECASE,
    )

    if bioportal_match:
        prefix = bioportal_match.group(1)
        accession = bioportal_match.group(2)

        return f"{prefix}:{accession}"

    return term


def ontology_acronym(
    iri: str | None,
) -> str | None:
    """
    Extract the ontology acronym.
    """

    curie = iri_to_curie(iri)

    if not curie:
        return None

    if ":" not in curie:
        return None

    return curie.split(
        ":",
        1,
    )[0].upper()


def ontology_name(
    acronym: str | None,
) -> str | None:
    """
    Return a readable ontology name.
    """

    ontology_names = {
        "TO": "Plant Trait Ontology",
        "PO": "Plant Ontology",
        "PATO": (
            "Phenotype and Trait Ontology"
        ),
        "CDNO": (
            "Compositional Dietary "
            "Nutrition Ontology"
        ),
        "PECO": (
            "Plant Experimental "
            "Conditions Ontology"
        ),
        "UO": (
            "Units of Measurement Ontology"
        ),
        "ENVO": "Environment Ontology",
        "AGRO": "Agronomy Ontology",
        "NCBITAXON": "NCBI Taxonomy",
    }

    if not acronym:
        return None

    return ontology_names.get(
        acronym.upper(),
        acronym,
    )


def create_bioportal_url(
    iri: str | None,
) -> str | None:
    """
    Create a link to the ontology class
    in BioPortal.
    """

    if not iri:
        return None

    acronym = ontology_acronym(iri)

    if not acronym:
        return None

    encoded_iri = quote(
        iri,
        safe="",
    )

    return (
        "https://bioportal.bioontology.org/"
        f"ontologies/{acronym}"
        f"?p=classes&conceptid={encoded_iri}"
    )


# =========================================================
# BrAPI response helper
# =========================================================

def brapi_response(
    data: list[dict[str, Any]],
    page_size: int,
) -> dict[str, Any]:
    """
    Create a BrAPI-compatible response.
    """

    total_count = len(data)

    total_pages = (
        1 if total_count > 0 else 0
    )

    return {
        "metadata": {
            "pagination": {
                "pageSize": page_size,
                "currentPage": 0,
                "totalCount": total_count,
                "totalPages": total_pages,
            },
            "status": [],
            "datafiles": [],
        },
        "result": {
            "data": data,
        },
    }



@router.get(
    "/rdf-health",
    summary="Check the Ontopic RDF service",
)
def rdf_health():
    """
    Check the Ontopic SPARQL endpoint and
    count the available RDF triples.
    """

    query = """
SELECT
    (COUNT(*) AS ?tripleCount)
WHERE {
    ?subject ?predicate ?object .
}
"""

    result = run_sparql(query)

    bindings = get_bindings(
        result
    )

    triple_count = (
        binding_integer(
            bindings[0],
            "tripleCount",
        )
        if bindings
        else 0
    )

    return {
        "status": (
            "healthy"
            if triple_count > 0
            else "connected-no-data"
        ),
        "endpoint": SPARQL_ENDPOINT,
        "tripleCount": triple_count,
        "apiVersion": (
            "rdf-comparison-v4"
        ),
    }


# =========================================================
# Comparable ontology traits
# =========================================================

@router.get(
    "/comparable-traits",
    summary="Get traits available for semantic comparison",
)
def get_comparable_traits(
    search: str | None = Query(
        default=None,
        max_length=200,
        description=(
            "Optional search by phenotype name, ontology CURIE, "
            "ontology IRI or ontology source."
        ),
    ),
    comparable_only: bool = Query(
        default=False,
        description="Return only traits found in more than one dataset.",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Return ontology-mapped Germinate traits grouped by ontology term."""

    search_filter = ""
    cleaned_search = (search or "").strip()

    if cleaned_search:
        escaped_search = (
            cleaned_search
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", " ")
            .replace("\r", " ")
        )

        source_names = {
            "TO": "Plant Trait Ontology",
            "PO": "Plant Ontology",
            "CDNO": "Compositional Dietary Nutrition Ontology",
            "PECO": "Plant Experimental Conditions Ontology",
            "PATO": "Phenotype and Trait Ontology",
            "UO": "Units of Measurement Ontology",
            "NCBITAXON": "NCBI Taxonomy",
            "ENVO": "Environment Ontology",
            "AGRO": "Agronomy Ontology",
            "CO": "Crop Ontology",
        }
        search_lower = cleaned_search.casefold()
        matching_codes = [
            code
            for code, name in source_names.items()
            if search_lower in code.casefold() or search_lower in name.casefold()
        ]
        source_conditions = "".join(
            f' || CONTAINS(UCASE(STR(?ontologyTrait)), "/{code}_")'
            f' || CONTAINS(UCASE(STR(?ontologyTrait)), "/{code}/")'
            for code in matching_codes
        )

        # This filter must be inside WHERE, before GROUP BY.
        search_filter = f"""
    FILTER(
        CONTAINS(
            LCASE(
                CONCAT(
                    STR(?phenotypeLabel),
                    " ",
                    STR(?ontologyTrait)
                )
            ),
            LCASE("{escaped_search}")
        ){source_conditions}
    )
"""

    having_clause = ""
    if comparable_only:
        having_clause = """
HAVING(COUNT(DISTINCT ?dataset) > 1)
"""

    query = f"""
PREFIX voc:  <http://vocabulary.example.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT
    ?ontologyTrait
    (GROUP_CONCAT(
        DISTINCT STR(?phenotypeLabel);
        SEPARATOR="|||"
    ) AS ?phenotypeNames)
    (COUNT(DISTINCT ?dataset) AS ?datasetCount)
    (COUNT(DISTINCT ?observation) AS ?observationCount)

WHERE {{
    ?observation
        voc:hasTrait ?ontologyTrait ;
        voc:hasPhenotype ?phenotype ;
        voc:belongsTo ?dataset ;
        voc:hasValue ?value .

    ?phenotype rdfs:label ?phenotypeLabel .

{search_filter}
}}

GROUP BY ?ontologyTrait
{having_clause}
ORDER BY LCASE(MIN(STR(?phenotypeLabel))) STR(?ontologyTrait)
LIMIT {limit}
"""

    result = run_sparql(query)
    bindings = get_bindings(result)
    data: list[dict[str, Any]] = []

    for binding in bindings:
        ontology_iri = binding_value(binding, "ontologyTrait")
        if not ontology_iri:
            continue

        aggregated_names = binding_value(binding, "phenotypeNames") or ""
        trait_names = sorted(
            {
                name.strip()
                for name in aggregated_names.split("|||")
                if name.strip()
            },
            key=str.casefold,
        )

        ontology_curie = iri_to_curie(ontology_iri)
        acronym = ontology_acronym(ontology_iri)
        readable_ontology_name = ontology_name(acronym)
        dataset_count = binding_integer(binding, "datasetCount")
        observation_count = binding_integer(binding, "observationCount")

        # Display only the first alphabetically sorted Germinate trait.
        # Dataset and observation counts still represent the ontology group.
        trait_name = trait_names[0] if trait_names else "Trait name not provided"
        displayed_trait_names = trait_names[:1]

        data.append(
            {
                "observationVariableDbId": ontology_curie or ontology_iri,
                "observationVariableName": trait_name,
                "phenotypeName": trait_name,
                "traitName": trait_name,
                "traitNames": displayed_trait_names,
                "ontologyReference": {
                    "ontologyDbId": ontology_curie or ontology_iri,
                    "ontologyName": readable_ontology_name,
                },
                "additionalInfo": {
                    "phenotypeNames": displayed_trait_names,
                    "ontologyIRI": ontology_iri,
                    "ontologyCURIE": ontology_curie,
                    "ontologyAcronym": acronym,
                    "ontologyName": readable_ontology_name,
                    "bioPortalUrl": create_bioportal_url(ontology_iri),
                    "datasetCount": dataset_count,
                    "observationCount": observation_count,
                    "comparable": dataset_count > 1,
                },
            }
        )

    response = brapi_response(data=data, page_size=limit)
    response["metadata"].update(
        {
            "comparableOnly": comparable_only,
            "search": search,
            "sparqlEndpoint": SPARQL_ENDPOINT,
            "apiVersion": "rdf-comparison-v7",
        }
    )
    return response



