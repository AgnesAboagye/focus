import json
import os
import re
from typing import Any
from urllib.parse import quote, urlsplit

import requests
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(prefix="/brapi/v2", tags=["Ontology terms"])

SPARQL_ENDPOINT = os.getenv(
    "SPARQL_ENDPOINT",
    "http://127.0.0.1:8090/sparql",
)
SPARQL_TIMEOUT = float(os.getenv("SPARQL_TIMEOUT", "60"))

PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX IAO: <http://purl.obolibrary.org/obo/IAO_>
"""

_ONTOLOGY_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,30}$")

ONTOLOGY_NAMES = {
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
    "GERMINATE": "Germinate Semantic Vocabulary",
}

BIOPORTAL_ONTOLOGIES = {
    "TO", "PO", "CDNO", "PECO", "PATO",
    "UO", "NCBITAXON", "ENVO", "AGRO",
}
_FORBIDDEN_IRI_CHARACTERS = re.compile(r'[\x00-\x20<>"{}|^`\\]')


def _sparql_string(value: str) -> str:
    """Encode user text as a safe SPARQL string literal."""
    return json.dumps(value, ensure_ascii=False)


def _binding_value(binding: dict[str, Any], name: str) -> str | None:
    item = binding.get(name)
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    return str(value) if value is not None else None


def _run_sparql(query: str) -> list[dict[str, Any]]:
    """Run a SPARQL SELECT query and return its JSON bindings."""
    try:
        response = requests.post(
            SPARQL_ENDPOINT,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=SPARQL_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="The ontology search timed out",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to query the semantic database",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="The semantic database returned invalid JSON",
        ) from exc

    try:
        return payload["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="The semantic database returned an unexpected response",
        ) from exc


def _local_name(iri: str) -> str:
    return iri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _curie(iri: str, accession: str | None = None) -> str:
    """Create a CURIE from common OBO and BioPortal IRI formats."""
    if accession:
        cleaned = accession.strip()
        if ":" in cleaned:
            return cleaned
        if match := re.fullmatch(r"([A-Za-z][A-Za-z0-9]+)[_:](.+)", cleaned):
            return f"{match.group(1)}:{match.group(2)}"

    parsed = urlsplit(iri)
    local = _local_name(iri)

    if "germinate-semantic_" in iri:
        namespace_match = re.search(
            r"germinate-semantic_([^/#]+)/([^/#]+)$",
            parsed.path,
            re.IGNORECASE,
        )
        if namespace_match:
            entity_type = namespace_match.group(1).upper()
            entity_id = namespace_match.group(2)
            return f"GERMINATE:{entity_type}_{entity_id}"

    if match := re.fullmatch(r"([A-Za-z][A-Za-z0-9]+)_(.+)", local):
        return f"{match.group(1)}:{match.group(2)}"

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 2 and segments[-2].upper() == segments[-2]:
        return f"{segments[-2]}:{segments[-1]}"
    return local


def _ontology_name(iri: str, curie: str) -> str:
    if "germinate-semantic_" in iri:
        return ONTOLOGY_NAMES["GERMINATE"]

    if ":" in curie:
        code = curie.split(":", 1)[0].upper()
        return ONTOLOGY_NAMES.get(code, code)
    local = _local_name(iri)
    if "_" in local:
        code = local.split("_", 1)[0].upper()
        return ONTOLOGY_NAMES.get(code, code)
    return "Ontology not identified"


def _ontology_code(iri: str, curie: str) -> str | None:
    if "germinate-semantic_" in iri:
        return "GERMINATE"
    if ":" in curie:
        return curie.split(":", 1)[0].upper()
    local = _local_name(iri)
    if "_" in local:
        return local.split("_", 1)[0].upper()
    return None


def _bioportal_url(iri: str, ontology_code: str | None) -> str | None:
    if ontology_code not in BIOPORTAL_ONTOLOGIES:
        return None
    return (
        f"https://bioportal.bioontology.org/ontologies/{quote(ontology_code)}"
        f"?p=classes&conceptid={quote(iri, safe='')}"
    )


def _pagination(page: int, page_size: int, total_count: int) -> dict[str, int]:
    total_pages = (total_count + page_size - 1) // page_size if total_count else 0
    return {
        "currentPage": page,
        "pageSize": page_size,
        "totalCount": total_count,
        "totalPages": total_pages,
    }


def _ontology_filter(ontology: str | None) -> str:
    if not ontology:
        return ""
    code = ontology.strip().upper()
    if not _ONTOLOGY_CODE.fullmatch(code):
        raise HTTPException(
            status_code=422,
            detail="ontology must be a short code such as TO, PO, UO or NCBITAXON",
        )
    encoded = _sparql_string(code)
    return f"""
    FILTER(
        CONTAINS(UCASE(STR(?oboTerm)), CONCAT("/", {encoded}, "_")) ||
        CONTAINS(UCASE(STR(?oboTerm)), CONCAT("/", {encoded}, "/"))
    )
"""


@router.get("/ontology-terms")
def search_ontology_terms(
    search: str | None = Query(
        None,
        min_length=1,
        max_length=200,
        description="Text found in a label, synonym, definition, accession or IRI",
    ),
    ontology: str | None = Query(
        None,
        min_length=1,
        max_length=31,
        description="Optional ontology code, for example TO, PO or UO",
    ),
    exact: bool = Query(False, description="Require an exact literal match"),
    page: int = Query(0, ge=0),
    pageSize: int = Query(20, ge=1, le=200),
) -> dict[str, Any]:
    """Search local traits and return their mapped external ontology terms."""
    search_value = (search or "").strip()
    search_literal = _sparql_string(search_value)
    ontology_clause = _ontology_filter(ontology)

    if exact and search_value:
        text_filter = f"LCASE(STR(?localLabel)) = LCASE({search_literal})"
    elif search_value:
        text_filter = f"""
        (
            CONTAINS(LCASE(STR(?localLabel)), LCASE({search_literal})) ||
            CONTAINS(LCASE(STR(?oboTerm)), LCASE({search_literal}))
        )
"""
    else:
        text_filter = "true"

    match_body = f"""
    ?localResource ?mappingPredicate ?oboTerm .
    ?localResource ?labelPredicate ?localLabel .

    FILTER(ISIRI(?localResource))
    FILTER(ISLITERAL(?localLabel))
    FILTER(STRSTARTS(
        STR(?localResource),
        "http://mydata.example.org/germinate-semantic_"
    ))
    FILTER(
        STRSTARTS(STR(?oboTerm), "http://purl.obolibrary.org/obo/") ||
        STRSTARTS(STR(?oboTerm), "https://purl.obolibrary.org/obo/") ||
        CONTAINS(STR(?oboTerm), "bioontology.org/ontology/")
    )
    FILTER(
        ?labelPredicate = rdfs:label ||
        ?labelPredicate = skos:prefLabel ||
        CONTAINS(LCASE(STR(?labelPredicate)), "label") ||
        CONTAINS(LCASE(STR(?labelPredicate)), "name")
    )
    FILTER({text_filter})
    {ontology_clause}
"""

    count_query = f"""
{PREFIXES}
SELECT (COUNT(*) AS ?totalCount)
WHERE {{
    SELECT DISTINCT ?localResource ?oboTerm
    WHERE {{
{match_body}
    }}
}}
"""
    count_bindings = _run_sparql(count_query)
    total_count = int(
        _binding_value(count_bindings[0], "totalCount")
        if count_bindings
        else 0
    )

    offset = page * pageSize
    candidate_query = f"""
{PREFIXES}
SELECT
    ?localResource
    ?oboTerm
    (SAMPLE(STR(?localLabel)) AS ?localLabel)
    (SAMPLE(STR(?mappingPredicate)) AS ?mappingPredicate)
WHERE {{
{match_body}
}}
GROUP BY ?localResource ?oboTerm
ORDER BY LCASE(?localLabel) STR(?oboTerm)
LIMIT {pageSize}
OFFSET {offset}
"""
    candidate_bindings = _run_sparql(candidate_query)
    data: list[dict[str, Any]] = []
    for binding in candidate_bindings:
        local_resource = _binding_value(binding, "localResource")
        iri = _binding_value(binding, "oboTerm")
        label = _binding_value(binding, "localLabel")
        mapping_predicate = _binding_value(binding, "mappingPredicate")
        if (
            not local_resource
            or not iri
            or _FORBIDDEN_IRI_CHARACTERS.search(iri)
        ):
            continue

        curie = _curie(iri)
        ontology_name = _ontology_name(iri, curie)
        ontology_code = _ontology_code(iri, curie)
        data.append(
            {
                "ontologyTermDbId": f"{local_resource}|{iri}",
                "ontologyTermIRI": iri,
                "ontologyTermName": label or curie,
                "ontologyName": ontology_name,
                "ontologyCurie": curie,
                "description": None,
                "synonyms": [],
                "bioPortalUrl": _bioportal_url(iri, ontology_code),
                "additionalInfo": {
                    "localResourceIRI": local_resource,
                    "mappingPredicate": mapping_predicate,
                },
            }
        )

    data.sort(key=lambda item: (item["ontologyTermName"].casefold(), item["ontologyCurie"]))
    return {
        "metadata": {"pagination": _pagination(page, pageSize, total_count)},
        "result": {"data": data},
    }

