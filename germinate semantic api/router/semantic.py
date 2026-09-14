from math import ceil
from typing import Any

from fastapi import APIRouter, Query

from database import run_query


router = APIRouter(
    prefix="/brapi/v2",
    tags=["BrAPI"],
)



ONTOLOGY_NAMES = {
    "TO": "Plant Trait Ontology",
    "PO": "Plant Ontology",
    "CDNO": "Compositional Dietary Nutrition Ontology",
    "PECO": "Plant Experimental Conditions Ontology",
    "PATO": "Phenotype and Trait Ontology",
    "UO": "Units of Measurement Ontology",
    "NCBITaxon": "NCBI Taxonomy",
    "ENVO": "Environment Ontology",
    "AGRO": "Agronomy Ontology",
    "CO": "Crop Ontology",
}


def get_ontology_reference(iri: str | None) -> dict[str, Any]:
    """Convert an OBO IRI into a BrAPI ontology reference."""

    if not iri:
        return {
            "ontologyDbId": None,
            "ontologyName": None,
        }

    term = iri.rstrip("/").split("/")[-1]

    if "_" in term:
        prefix, accession = term.split("_", 1)
        ontology_db_id = f"{prefix}:{accession}"
    else:
        prefix = term
        ontology_db_id = term

    return {
        "ontologyDbId": ontology_db_id,
        "ontologyName": ONTOLOGY_NAMES.get(prefix, prefix),
    }


def brapi_response(
    data: list[dict[str, Any]],
    total_count: int,
    page_size: int,
    current_page: int,
) -> dict[str, Any]:
    """Create a BrAPI-style response with correct pagination."""

    total_pages = (
        ceil(total_count / page_size)
        if total_count > 0 and page_size > 0
        else 0
    )

    return {
        "metadata": {
            "pagination": {
                "pageSize": page_size,
                "currentPage": current_page,
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


def get_total_count(
    sql: str,
    params: list[Any],
) -> int:
    """Execute a count query and return its integer result."""

    rows = run_query(sql, params)

    if not rows:
        return 0

    return int(rows[0].get("total_count", 0))


@router.get("/traits")
def brapi_traits(
    search: str | None = Query(default=None),
    pageSize: int = Query(default=100, ge=1, le=1000),
    page: int = Query(default=0, ge=0),
):
    where_clauses = ["1 = 1"]
    params: list[Any] = []

    if search:
        search_value = f"%{search.strip()}%"

        where_clauses.append(
            """
            (
                phenotype_name LIKE %s
                OR trait_ontology_label LIKE %s
                OR trait_iri LIKE %s
                OR trait_curie LIKE %s
            )
            """
        )

        params.extend(
            [
                search_value,
                search_value,
                search_value,
                search_value,
            ]
        )

    where_sql = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(*) AS total_count
        FROM semantic_phenotype
        WHERE {where_sql}
    """

    total_count = get_total_count(count_sql, params.copy())

    data_sql = f"""
        SELECT
            phenotype_id,
            phenotype_name,
            phenotype_short_name,
            phenotype_description,
            phenotype_datatype,
            unit_id,

            trait_term_id,
            trait_iri,
            trait_curie,
            trait_ontology_label,
            trait_match_method,
            trait_mapping_confidence,
            trait_mapping_status

        FROM semantic_phenotype

        WHERE {where_sql}

        ORDER BY phenotype_name

        LIMIT %s OFFSET %s
    """

    offset = page * pageSize
    data_params = params.copy()
    data_params.extend([pageSize, offset])

    rows = run_query(data_sql, data_params)

    data = []

    for row in rows:
        ontology_iri = row.get("trait_iri")

        data.append(
            {
                "traitDbId": str(row.get("phenotype_id")),
                "traitName": row.get("phenotype_name"),
                "description": row.get("phenotype_description"),
                "observationVariableName": row.get(
                    "phenotype_short_name"
                ),
                "dataType": row.get("phenotype_datatype"),
                "ontologyReference": get_ontology_reference(
                    ontology_iri
                ),
                "additionalInfo": {
                    "ontologyIRI": ontology_iri,
                    "ontologyCURIE": row.get("trait_curie"),
                    "ontologyLabel": row.get(
                        "trait_ontology_label"
                    ),
                    "mappingMethod": row.get(
                        "trait_match_method"
                    ),
                    "mappingConfidence": row.get(
                        "trait_mapping_confidence"
                    ),
                    "mappingStatus": row.get(
                        "trait_mapping_status"
                    ),
                    "unitDbId": row.get("unit_id"),
                },
            }
        )

    return brapi_response(
        data=data,
        total_count=total_count,
        page_size=pageSize,
        current_page=page,
    )


def split_aggregated_value(
    value: str | None,
) -> list[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).split("|||")
        if item.strip()
    ]


@router.get("/datasets")
def get_datasets(
    search: str | None = Query(default=None),
    pageSize: int = Query(default=20, ge=1, le=200),
    page: int = Query(default=0, ge=0),
):
    where_clauses = ["1 = 1"]
    params: list[Any] = []

    if search:
        search_value = f"%{search.strip()}%"

        where_clauses.append(
            """
            (
                name LIKE %s
                OR species LIKE %s
                OR ncbi_taxon LIKE %s
                OR ncbi_taxon_iri LIKE %s
            )
            """
        )

        params.extend(
            [
                search_value,
                search_value,
                search_value,
                search_value,
            ]
        )

    where_sql = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(*) AS total_count
        FROM semantic_dataset_explorer
        WHERE {where_sql}
    """

    total_count = get_total_count(
        count_sql,
        params.copy(),
    )

    data_sql = f"""
        SELECT
            dataset_id,
            name,
            number_of_traits,
            number_of_germplasm,
            species,
            ncbi_taxon,
            ncbi_taxon_iri,
            dataset_description,
            dataset_start_date,
            dataset_end_date

        FROM semantic_dataset_explorer

        WHERE {where_sql}

        ORDER BY name

        LIMIT %s OFFSET %s
    """

    offset = page * pageSize

    data_params = params.copy()
    data_params.extend(
        [
            pageSize,
            offset,
        ]
    )

    rows = run_query(
        data_sql,
        data_params,
    )

    data = []

    for row in rows:
        species_values = split_aggregated_value(
            row.get("species")
        )

        taxon_values = split_aggregated_value(
            row.get("ncbi_taxon")
        )

        taxon_iris = split_aggregated_value(
            row.get("ncbi_taxon_iri")
        )

        taxonomy_references = []

        taxonomy_count = max(
            len(taxon_values),
            len(taxon_iris),
        )

        for index in range(taxonomy_count):
            taxonomy_references.append(
                {
                    "curie": (
                        taxon_values[index]
                        if index < len(taxon_values)
                        else None
                    ),
                    "iri": (
                        taxon_iris[index]
                        if index < len(taxon_iris)
                        else None
                    ),
                }
            )

        data.append(
            {
                "datasetDbId": str(
                    row.get("dataset_id")
                ),
                "datasetName": row.get("name"),
                "numberOfTraits": int(
                    row.get("number_of_traits")
                    or 0
                ),
                "numberOfGermplasm": int(
                    row.get(
                        "number_of_germplasm"
                    )
                    or 0
                ),
                "species": species_values,
                "taxonomyReferences":
                    taxonomy_references,
                "description": row.get(
                    "dataset_description"
                ),
                "startDate": row.get(
                    "dataset_start_date"
                ),
                "endDate": row.get(
                    "dataset_end_date"
                ),
            }
        )

    return brapi_response(
        data=data,
        total_count=total_count,
        page_size=pageSize,
        current_page=page,
    )

