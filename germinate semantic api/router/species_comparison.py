import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(prefix="/brapi/v2", tags=["Species comparison"])

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://127.0.0.1:8090/sparql")
SPARQL_TIMEOUT = float(os.getenv("SPARQL_TIMEOUT", "60"))

VOCABULARY = "http://vocabulary.example.org/"
PREFIXES = f"""
PREFIX voc: <{VOCABULARY}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

_FORBIDDEN_IRI_CHARACTERS = re.compile(r'[\x00-\x20<>"{}|^`\\]')


def _validated_iri(value: str, parameter: str) -> str:
    """Validate an external IRI before interpolating it into SPARQL."""
    value = value.strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or _FORBIDDEN_IRI_CHARACTERS.search(value)
    ):
        raise HTTPException(
            status_code=422,
            detail=f"{parameter} must be a valid HTTP(S) IRI",
        )
    return value


def _binding_value(binding: dict[str, Any], name: str) -> str | None:
    item = binding.get(name)
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    return str(value) if value is not None else None


def _run_sparql(query: str) -> list[dict[str, Any]]:
    """Execute a SELECT query and return its SPARQL JSON bindings."""
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
            detail="The semantic database query timed out",
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


def _number(value: str | None) -> int | float | None:
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _curie(iri: str) -> str:
    for prefix in (
        "http://purl.obolibrary.org/obo/",
        "http://purl.bioontology.org/ontology/",
    ):
        if iri.startswith(prefix):
            local = iri[len(prefix) :]
            if "_" in local:
                ontology, accession = local.split("_", 1)
                return f"{ontology}:{accession}"
            return local.replace("/", ":", 1)
    return iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _pagination(page: int, page_size: int, total_count: int) -> dict[str, int]:
    total_pages = (total_count + page_size - 1) // page_size if total_count else 0
    return {
        "currentPage": page,
        "pageSize": page_size,
        "totalCount": total_count,
        "totalPages": total_pages,
    }


def _normalize_unit(value: str | None) -> str | None:
    """Normalize equivalent unit names and symbols to one comparison key."""
    if not value:
        return None

    cleaned = re.sub(r"\s+", " ", value.strip().casefold())
    aliases = {
        "centimeter": "cm",
        "centimeters": "cm",
        "centimetre": "cm",
        "centimetres": "cm",
        "cm": "cm",
        "millimeter": "mm",
        "millimeters": "mm",
        "millimetre": "mm",
        "millimetres": "mm",
        "mm": "mm",
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "m": "m",
        "day": "day",
        "days": "day",
        "d": "day",
    }
    return aliases.get(cleaned, cleaned)


def _species_name_lookup() -> dict[str, str]:
    query = """
SELECT DISTINCT ?species ?scientificName
WHERE {
    ?species ?namePredicate ?scientificName .
    FILTER(CONTAINS(LCASE(STR(?namePredicate)), "scientificname"))
}
"""
    return {
        species: name
        for binding in _run_sparql(query)
        if (species := _binding_value(binding, "species"))
        and (name := _binding_value(binding, "scientificName"))
    }


def _unit_lookup() -> dict[str, dict[str, str | None]]:
    """Return metadata for units that have an abbreviation or label mapping."""
    query = f"""
{PREFIXES}
SELECT DISTINCT ?unit ?unitName ?unitAbbreviation
WHERE {{
    {{ ?unit voc:unitAbbreviation ?unitAbbreviation . }}
    UNION
    {{
        ?unit rdfs:label ?unitName .
        FILTER(CONTAINS(STR(?unit), "germinate-semantic_unit/"))
    }}
    OPTIONAL {{ ?unit rdfs:label ?unitName . }}
    OPTIONAL {{ ?unit voc:unitAbbreviation ?unitAbbreviation . }}
}}
"""
    units: dict[str, dict[str, str | None]] = {}
    for binding in _run_sparql(query):
        unit_iri = _binding_value(binding, "unit")
        if not unit_iri:
            continue
        name = _binding_value(binding, "unitName")
        abbreviation = _binding_value(binding, "unitAbbreviation")
        units[unit_iri] = {
            "unitIri": unit_iri,
            "unitName": name,
            "unitAbbreviation": abbreviation,
            "normalizedUnit": _normalize_unit(abbreviation or name),
        }
    return units


def _unit_summary(
    unit_iris: set[str],
    unit_metadata: dict[str, dict[str, str | None]],
) -> tuple[list[dict[str, str | None]], bool, str | None]:
    details = [
        unit_metadata.get(
            iri,
            {
                "unitIri": iri,
                "unitName": None,
                "unitAbbreviation": None,
                "normalizedUnit": None,
            },
        )
        for iri in sorted(unit_iris)
    ]
    normalized = {row["normalizedUnit"] for row in details if row["normalizedUnit"]}
    all_resolved = bool(details) and all(row["normalizedUnit"] for row in details)
    compatible = all_resolved and len(normalized) == 1
    canonical = next(iter(normalized)) if compatible else None
    return details, compatible, canonical


@router.get("/comparable-traits-by-species")
def comparable_traits_by_species(
    search: str | None = Query(None, min_length=1, max_length=200),
    page: int = Query(0, ge=0),
    pageSize: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Return ontology traits having numeric observations in two or more species."""
    query = f"""
{PREFIXES}
SELECT ?trait ?species ?unit
       (GROUP_CONCAT(DISTINCT STR(?phenotypeLabel); SEPARATOR="|||")
           AS ?phenotypeNames)
       (COUNT(DISTINCT ?observation) AS ?observationCount)
WHERE {{
    ?observation voc:hasSpecies ?species ;
                 voc:hasTrait ?trait ;
                 voc:hasValue ?value .
    OPTIONAL {{ ?observation voc:hasUnit ?unit . }}
    OPTIONAL {{
        ?observation voc:hasPhenotype ?phenotype .
        ?phenotype rdfs:label ?phenotypeLabel .
    }}
    FILTER(ISIRI(?trait))
}}
GROUP BY ?trait ?species ?unit
ORDER BY ?trait ?species ?unit
"""

    species_names = _species_name_lookup()
    unit_metadata = _unit_lookup()
    grouped: dict[str, dict[str, Any]] = {}

    for binding in _run_sparql(query):
        trait = _binding_value(binding, "trait")
        species_iri = _binding_value(binding, "species")
        if not trait or not species_iri:
            continue

        item = grouped.setdefault(
            trait,
            {
                "ontologyIri": trait,
                "traitCurie": _curie(trait),
                "species": {},
                "units": set(),
                "traitNames": set(),
                "observationCount": 0,
            },
        )
        species = item["species"].setdefault(
            species_iri,
            {
                "speciesIri": species_iri,
                "scientificName": species_names.get(species_iri) or species_iri,
                "observationCount": 0,
            },
        )
        count = int(_binding_value(binding, "observationCount") or 0)
        species["observationCount"] += count
        item["observationCount"] += count
        if unit := _binding_value(binding, "unit"):
            item["units"].add(unit)
        phenotype_names = _binding_value(binding, "phenotypeNames") or ""
        item["traitNames"].update(
            name.strip()
            for name in phenotype_names.split("|||")
            if name.strip()
        )

    data: list[dict[str, Any]] = []
    search_text = search.casefold() if search else None
    for item in grouped.values():
        if len(item["species"]) < 2:
            continue
        trait_name = (
            sorted(item["traitNames"], key=str.casefold)[0]
            if item["traitNames"]
            else "Trait name not provided"
        )
        if search_text and search_text not in (
            item["ontologyIri"] + " " + item["traitCurie"] + " " + trait_name
        ).casefold():
            continue

        species_list = sorted(
            item["species"].values(),
            key=lambda row: row["scientificName"].casefold(),
        )
        unit_details, compatible, canonical_unit = _unit_summary(
            item["units"], unit_metadata
        )
        data.append(
            {
                "ontologyIri": item["ontologyIri"],
                "traitName": trait_name,
                "traitCurie": item["traitCurie"],
                "speciesCount": len(species_list),
                "species": species_list,
                "units": unit_details,
                "canonicalUnit": canonical_unit,
                "unitsCompatible": compatible,
                "observationCount": item["observationCount"],
            }
        )

    data.sort(key=lambda row: (-row["speciesCount"], row["traitCurie"]))
    total_count = len(data)
    start = page * pageSize
    return {
        "metadata": {"pagination": _pagination(page, pageSize, total_count)},
        "result": {"data": data[start : start + pageSize]},
    }


@router.get("/compare-species")
def compare_species(
    ontology_iri: str = Query(..., description="Shared ontology trait IRI"),
    species_iri: list[str] | None = Query(
        None,
        description="Optional species IRI; repeat to select multiple species",
    ),
    exclude_zero: bool = Query(False),
    page: int = Query(0, ge=0),
    pageSize: int = Query(1000, ge=1, le=10000),
) -> dict[str, Any]:
    """Return observation-level values grouped by species for box plots."""
    trait_iri = _validated_iri(ontology_iri, "ontology_iri")
    selected_species = [
        _validated_iri(value, "species_iri") for value in (species_iri or [])
    ]
    values_clause = ""
    if selected_species:
        values_clause = "VALUES ?species { " + " ".join(
            f"<{value}>" for value in selected_species
        ) + " }"
    zero_filter = "FILTER(?value != 0)" if exclude_zero else ""

    where_body = f"""
    {values_clause}
    ?observation voc:hasSpecies ?species ;
                 voc:hasTrait <{trait_iri}> ;
                 voc:hasValue ?value .
    OPTIONAL {{ ?observation voc:hasUnit ?unit . }}
    OPTIONAL {{ ?observation voc:observedOn ?germplasm . }}
    OPTIONAL {{ ?observation voc:belongsTo ?dataset . }}
    OPTIONAL {{ ?observation voc:hasPhenotype ?phenotype . }}
    {zero_filter}
"""

    count_query = f"""
{PREFIXES}
SELECT (COUNT(DISTINCT ?observation) AS ?totalCount)
WHERE {{
{where_body}
}}
"""
    count_bindings = _run_sparql(count_query)
    total_count = int(
        _binding_value(count_bindings[0], "totalCount")
        if count_bindings
        else 0
    )

    offset = page * pageSize
    data_query = f"""
{PREFIXES}
SELECT DISTINCT ?observation ?species ?value ?unit
                ?germplasm ?dataset ?phenotype
WHERE {{
{where_body}
}}
ORDER BY ?species ?observation
LIMIT {pageSize}
OFFSET {offset}
"""

    species_names = _species_name_lookup()
    unit_metadata = _unit_lookup()
    data: list[dict[str, Any]] = []
    returned_unit_iris: set[str] = set()

    for binding in _run_sparql(data_query):
        value = _number(_binding_value(binding, "value"))
        if value is None:
            continue
        species_value = _binding_value(binding, "species")
        unit_iri = _binding_value(binding, "unit")
        if unit_iri:
            returned_unit_iris.add(unit_iri)
        unit = unit_metadata.get(unit_iri or "", {})
        data.append(
            {
                "observationDbId": _binding_value(binding, "observation"),
                "ontologyIri": trait_iri,
                "traitCurie": _curie(trait_iri),
                "speciesIri": species_value,
                "scientificName": species_names.get(species_value or "")
                or species_value,
                "value": value,
                "unitIri": unit_iri,
                "unitName": unit.get("unitName"),
                "unitAbbreviation": unit.get("unitAbbreviation"),
                "normalizedUnit": unit.get("normalizedUnit"),
                "germplasmDbId": _binding_value(binding, "germplasm"),
                "datasetDbId": _binding_value(binding, "dataset"),
                "phenotypeDbId": _binding_value(binding, "phenotype"),
            }
        )

    unit_details, compatible, canonical_unit = _unit_summary(
        returned_unit_iris, unit_metadata
    )
    return {
        "metadata": {"pagination": _pagination(page, pageSize, total_count)},
        "result": {
            "ontologyIri": trait_iri,
            "traitCurie": _curie(trait_iri),
            "units": unit_details,
            "canonicalUnit": canonical_unit,
            "unitsCompatible": compatible,
            "data": data,
        },
    }
