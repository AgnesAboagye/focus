"""Map Germinate database records to BioPortal ontology terms.

Required packages:
    pip install mysql-connector-python python-dotenv requests

Required .env variables:
    DB_HOST=127.0.0.1
    DB_PORT=3306
    DB_USER=root
    DB_PASSWORD=your_password
    DB_NAME=germinate_test
    BIOPORTAL_API_KEY=your_api_key
"""

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import mysql.connector
import requests
from dotenv import load_dotenv
from mysql.connector import Error


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Create and close a MySQL database connection."""

    def __init__(self, **config: Any):
        self.config = config
        self.conn = None

    def connect(self):
        try:
            self.conn = mysql.connector.connect(**self.config)
            if self.conn.is_connected():
                logger.info(
                    "Connected to database '%s' at %s:%s",
                    self.config.get("database"),
                    self.config.get("host"),
                    self.config.get("port", 3306),
                )
            return self.conn
        except Error as error:
            logger.error("Failed to connect to database: %s", error)
            raise

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()
            logger.info("Database connection closed")


class BioPortalClient:
    """Small client for the NCBO BioPortal search API."""

    BASE_URL = "https://data.bioontology.org"
    SEARCH_URL = f"{BASE_URL}/search"

    def __init__(self, api_key: Optional[str]):
        if not api_key:
            raise ValueError("BIOPORTAL_API_KEY is missing from the .env file")
        self.api_key = api_key.strip().strip('"').strip("'")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"apikey token={self.api_key}",
            "Accept": "application/json",
            "User-Agent": "Germinate-Ontology-Mapper/1.0",
        })

    def test_connection(self):
        """Verify authentication and availability using BioPortal's PTO record."""
        response = self.session.get(
            f"{self.BASE_URL}/ontologies/PTO",
            timeout=30,
        )
        if not response.ok:
            logger.error(
                "BioPortal connection test failed. Status=%s Response=%s",
                response.status_code,
                response.text[:500],
            )
            response.raise_for_status()
        data = response.json()
        logger.info(
            "BioPortal connection successful: %s",
            data.get("name", "Plant Trait Ontology"),
        )
        return data

    def search(self, query: str, ontologies: List[str]) -> Dict[str, Any]:
        response = self.session.get(
            self.SEARCH_URL,
            params={
                "q": query,
                "ontologies": ",".join(ontologies),
                "require_exact_match": "false",
                "include": "prefLabel,synonym,definition",
                "pagesize": 20,
            },
            timeout=30,
            allow_redirects=True,
        )
        if not response.ok:
            logger.error(
                "BioPortal search failed. Status=%s Response=%s",
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        return response.json()


class OntologyMapper:
    def __init__(self, db_config: Dict[str, Any], api_key: Optional[str] = None):
        self.db = DatabaseManager(**db_config)
        self.bp = BioPortalClient(api_key or os.getenv("BIOPORTAL_API_KEY"))
        self.conn = self.db.connect()
        self._source_cache: Dict[str, int] = {}

    @staticmethod
    def normalize(text: Any) -> str:
        if text is None:
            return ""
        return re.sub(r"\s+", " ", str(text).strip())

    def get_source_id(self, acronym: str) -> int:
        if acronym not in self._source_cache:
            cursor = self.conn.cursor(buffered=True)
            try:
                cursor.execute(
                    "SELECT id FROM ontology_source WHERE acronym = %s",
                    (acronym,),
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError(
                        f"Ontology source '{acronym}' was not found in ontology_source"
                    )
                self._source_cache[acronym] = int(row[0])
            finally:
                cursor.close()
        return self._source_cache[acronym]

    def extract_curie_from_iri(
        self, iri: str, ontology_acronym: str
    ) -> Optional[str]:
        if not iri:
            return None

        patterns = [
            r"http://purl\.obolibrary\.org/obo/([A-Za-z]+)_(\d+)",
            r"http://purl\.bioontology\.org/ontology/([A-Za-z]+)/([A-Za-z_]+_\d+)",
            r"http://purl\.bioontology\.org/ontology/([A-Za-z]+)/([^/]+)$",
            r"/([A-Za-z]+)[:_](\d+)$",
            r"/(\d+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, iri)
            if not match:
                continue
            groups = match.groups()
            if len(groups) == 2:
                prefix, identifier = groups
                identifier = identifier.replace(f"{prefix}_", "")
                return f"{prefix}:{identifier}"
            return f"{ontology_acronym}:{groups[0]}"

        last_segment = urlparse(iri).path.rstrip("/").split("/")[-1]
        match = re.match(r"^([A-Za-z]+)_(\d+)$", last_segment)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
        return None

    def extract_hit_fields(self, hit: Dict[str, Any]):
        iri = hit.get("@id") or hit.get("iri")
        label = self.normalize(hit.get("prefLabel") or hit.get("label"))

        raw_synonyms = hit.get("synonym") or []
        if isinstance(raw_synonyms, str):
            raw_synonyms = [raw_synonyms]

        synonyms: List[str] = []
        seen = set()
        for item in raw_synonyms:
            if isinstance(item, dict):
                value = item.get("label") or item.get("prefLabel") or item.get("@value")
            else:
                value = item
            synonym = self.normalize(value)
            key = synonym.lower()
            if synonym and key != label.lower() and key not in seen:
                synonyms.append(synonym)
                seen.add(key)

        ontology = None
        links = hit.get("links") or {}
        ontology_link = links.get("ontology")
        if isinstance(ontology_link, str):
            ontology = ontology_link.rstrip("/").split("/")[-1]

        curie = (
            self.extract_curie_from_iri(iri, ontology)
            if iri and ontology
            else None
        )
        return iri, label, ontology, synonyms, curie

    def pick_best_match(self, raw_term: str, search_results: Dict[str, Any]):
        raw_lower = self.normalize(raw_term).lower()
        hits = search_results.get("collection", [])
        if not hits:
            return None

        for hit in hits:
            label = self.normalize(hit.get("prefLabel") or hit.get("label"))
            if label.lower() == raw_lower:
                return hit, "exact", 1.0

        for hit in hits:
            _, _, _, synonyms, _ = self.extract_hit_fields(hit)
            if any(synonym.lower() == raw_lower for synonym in synonyms):
                return hit, "synonym", 0.95

        return hits[0], "fuzzy", 0.70

    def upsert_term(
        self,
        source_id: int,
        iri: str,
        label: str,
        synonyms: List[str],
        curie: Optional[str],
    ) -> int:
        """Insert a term, or update it when source_id + iri already exists."""
        cursor = self.conn.cursor(buffered=True)
        try:
            synonyms_text = (
                json.dumps(synonyms, ensure_ascii=False) if synonyms else None
            )
            cursor.execute(
                "SELECT id FROM ontology_term WHERE source_id = %s AND iri = %s",
                (source_id, iri),
            )
            existing = cursor.fetchone()

            if existing:
                term_id = int(existing[0])
                cursor.execute(
                    """
                    UPDATE ontology_term
                    SET curie = COALESCE(%s, curie),
                        label = COALESCE(NULLIF(%s, ''), label),
                        synonyms = COALESCE(%s, synonyms)
                    WHERE id = %s
                    """,
                    (curie, label, synonyms_text, term_id),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO ontology_term
                        (source_id, iri, curie, label, synonyms)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (source_id, iri, curie, label, synonyms_text),
                )
                term_id = int(cursor.lastrowid)

            return term_id
        finally:
            cursor.close()

    def upsert_mapping(
        self,
        table: str,
        id_column: str,
        row_id: int,
        term_id: int,
        method: str,
        confidence: float,
    ):
        """Insert or update a record in an approved mapping table."""
        allowed = {
            ("unit_term_map", "unit_id"),
            ("taxonomy_term_map", "taxonomy_id"),
            ("phenotype_term_map", "phenotype_id"),
            ("environment_term_map", "environment_id"),
            ("crop_part_term_map", "crop_part_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError(f"Unsupported mapping table: {table}.{id_column}")

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                INSERT INTO {table}
                    ({id_column}, term_id, match_method, confidence)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    term_id = VALUES(term_id),
                    match_method = VALUES(match_method),
                    confidence = VALUES(confidence)
                """,
                (row_id, term_id, method, confidence),
            )
        finally:
            cursor.close()

    def _search_and_save(
        self,
        raw_term: str,
        ontology: str,
        source_id: int,
        mapping_table: str,
        id_column: str,
        row_id: int,
    ) -> bool:
        results = self.bp.search(raw_term, [ontology])
        match = self.pick_best_match(raw_term, results)
        if not match:
            return False

        hit, method, confidence = match
        iri, label, _, synonyms, curie = self.extract_hit_fields(hit)
        if not iri:
            return False

        term_id = self.upsert_term(source_id, iri, label, synonyms, curie)
        self.upsert_mapping(
            mapping_table,
            id_column,
            row_id,
            term_id,
            method,
            confidence,
        )
        self.conn.commit()
        return True

    def map_units(self, limit: Optional[int] = None):
        logger.info("Starting unit mapping")
        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = "SELECT id, unit_name, unit_abbreviation FROM units"
            if limit:
                query += " LIMIT %s"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            records = cursor.fetchall()
        finally:
            cursor.close()

        source_id = self.get_source_id("UO")
        mapped = 0
        for record in records:
            unit_id = record["id"]
            queries = [record.get("unit_abbreviation"), record.get("unit_name")]
            try:
                saved = False
                for value in queries:
                    term = self.normalize(value)
                    if not term:
                        continue
                    if self._search_and_save(
                        term, "UO", source_id, "unit_term_map", "unit_id", unit_id
                    ):
                        saved = True
                        break
                mapped += int(saved)
            except Exception as error:
                self.conn.rollback()
                logger.error("Could not map unit %s: %s", unit_id, error)
            time.sleep(0.2)
        logger.info("Unit mapping completed: %s/%s", mapped, len(records))

    def map_taxonomies(self, limit: Optional[int] = None):
        logger.info("Starting taxonomy mapping")
        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = "SELECT id, genus, species, subtaxa FROM taxonomies"
            if limit:
                query += " LIMIT %s"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            records = cursor.fetchall()
        finally:
            cursor.close()

        source_id = self.get_source_id("NCBITAXON")
        mapped = 0
        for record in records:
            taxonomy_id = record["id"]
            scientific_name = " ".join(
                self.normalize(record.get(field))
                for field in ("genus", "species", "subtaxa")
                if self.normalize(record.get(field))
            )
            if not scientific_name:
                continue
            try:
                mapped += int(
                    self._search_and_save(
                        scientific_name,
                        "NCBITAXON",
                        source_id,
                        "taxonomy_term_map",
                        "taxonomy_id",
                        taxonomy_id,
                    )
                )
            except Exception as error:
                self.conn.rollback()
                logger.error("Could not map taxonomy %s: %s", taxonomy_id, error)
            time.sleep(0.2)
        logger.info("Taxonomy mapping completed: %s/%s", mapped, len(records))

    def map_phenotypes(self, limit: Optional[int] = None):
        logger.info("Starting phenotype mapping")
        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = """
                SELECT id, name, short_name, description
                FROM phenotypes
                WHERE (name IS NULL OR LOWER(name) NOT LIKE '%concentration%')
                  AND (short_name IS NULL OR LOWER(short_name) NOT LIKE '%concentration%')
                  AND (description IS NULL OR LOWER(description) NOT LIKE '%concentration%')
                ORDER BY id
            """
            if limit:
                query += " LIMIT %s"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            records = cursor.fetchall()
        finally:
            cursor.close()

        source_id = self.get_source_id("TO")
        mapped = 0
        for record in records:
            phenotype_id = record["id"]
            name = self.normalize(record.get("name"))
            if not name:
                continue
            try:
                mapped += int(
                    self._search_and_save(
                        name,
                        "PTO",
                        source_id,
                        "phenotype_term_map",
                        "phenotype_id",
                        phenotype_id,
                    )
                )
            except Exception as error:
                self.conn.rollback()
                logger.error("Could not map phenotype %s: %s", phenotype_id, error)
            time.sleep(0.2)
        logger.info("Phenotype mapping completed: %s/%s", mapped, len(records))

    def map_concentrations(self, limit: Optional[int] = None):
        """Map concentration-related phenotype records to CDNO."""
        logger.info("Starting concentration mapping to CDNO")
        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = """
                SELECT id, name, short_name, description
                FROM phenotypes
                WHERE LOWER(COALESCE(name, '')) LIKE %s
                   OR LOWER(COALESCE(short_name, '')) LIKE %s
                   OR LOWER(COALESCE(description, '')) LIKE %s
                ORDER BY id
            """
            parameters: List[Any] = [
                "%concentration%",
                "%concentration%",
                "%concentration%",
            ]
            if limit:
                query += " LIMIT %s"
                parameters.append(limit)
            cursor.execute(query, tuple(parameters))
            records = cursor.fetchall()
        finally:
            cursor.close()

        if not records:
            logger.warning("No concentration records found in phenotypes")
            return

        source_id = self.get_source_id("CDNO")
        mapped = 0
        for record in records:
            phenotype_id = record["id"]
            name = self.normalize(record.get("name"))
            if not name:
                continue
            try:
                mapped += int(
                    self._search_and_save(
                        name,
                        "CDNO",
                        source_id,
                        "phenotype_term_map",
                        "phenotype_id",
                        phenotype_id,
                    )
                )
            except Exception as error:
                self.conn.rollback()
                logger.error(
                    "Could not map concentration phenotype %s '%s': %s",
                    phenotype_id,
                    name,
                    error,
                )
            time.sleep(0.2)

        logger.info(
            "CDNO concentration mapping completed: %s/%s",
            mapped,
            len(records),
        )

    def map_environments(self, limit: Optional[int] = None):
        """Map records from environment to the Environment Ontology (ENVO)."""
        logger.info("Starting environment mapping to ENVO")
        aliases = {
            "field drought environment": "agricultural field",
            "field environment": "agricultural field",
            "field": "agricultural field",
            "glasshouse drought environment": "greenhouse",
            "glasshouse environment": "greenhouse",
            "glasshouse": "greenhouse",
            "greenhouse environment": "greenhouse",
            "greenhouse": "greenhouse",
        }

        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = "SELECT id, name, description FROM environment ORDER BY id"
            if limit:
                query += " LIMIT %s"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            records = cursor.fetchall()
        finally:
            cursor.close()

        if not records:
            logger.warning("No records found in environment")
            return

        source_id = self.get_source_id("ENVO")
        mapped = 0
        for record in records:
            row_id = record["id"]
            name = self.normalize(record.get("name"))
            if not name:
                logger.warning("Skipping environment %s: missing name", row_id)
                continue
            search_term = aliases.get(name.lower(), name)
            try:
                success = self._search_and_save(
                    search_term,
                    "ENVO",
                    source_id,
                    "environment_term_map",
                    "environment_id",
                    row_id,
                )
                mapped += int(success)
                if success:
                    logger.info("Mapped environment %s '%s' to ENVO", row_id, name)
                else:
                    logger.warning("No ENVO match for environment %s '%s'", row_id, name)
            except Exception as error:
                self.conn.rollback()
                logger.error("Could not map environment %s '%s': %s", row_id, name, error)
            time.sleep(0.2)

        logger.info("Environment mapping completed: %s/%s", mapped, len(records))

    def map_crop_parts(self, limit: Optional[int] = None):
        """Map records from crop_part to the Plant Ontology (PO)."""
        logger.info("Starting crop-part mapping to PO")
        aliases = {
            "seed": "seed",
            "grain": "seed",
            "leaf": "vascular leaf",
            "root": "root",
            "panicle": "panicle inflorescence",
            "whole plant": "whole plant",
            "stem": "stem",
            "shoot": "shoot system",
            "flower": "flower",
            "fruit": "fruit",
        }

        cursor = self.conn.cursor(buffered=True, dictionary=True)
        try:
            query = """
                SELECT id, name, description
                FROM crop_part
                ORDER BY id
            """
            if limit:
                query += " LIMIT %s"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            records = cursor.fetchall()
        finally:
            cursor.close()

        if not records:
            logger.warning("No records found in crop_part")
            return

        source_id = self.get_source_id("PO")
        mapped = 0
        for record in records:
            row_id = record["id"]
            name = self.normalize(record.get("name"))
            if not name:
                logger.warning("Skipping crop part %s: missing name", row_id)
                continue
            search_term = aliases.get(name.lower(), name)
            try:
                success = self._search_and_save(
                    search_term,
                    "PO",
                    source_id,
                    "crop_part_term_map",
                    "crop_part_id",
                    row_id,
                )
                mapped += int(success)
                if success:
                    logger.info("Mapped crop part %s '%s' to PO", row_id, name)
                else:
                    logger.warning("No PO match for crop part %s '%s'", row_id, name)
            except Exception as error:
                self.conn.rollback()
                logger.error("Could not map crop part %s '%s': %s", row_id, name, error)
            time.sleep(0.2)

        logger.info("Crop-part mapping completed: %s/%s", mapped, len(records))

    def show_summary(self):
        cursor = self.conn.cursor()
        try:
            queries = {
                "Ontology terms": "SELECT COUNT(*) FROM ontology_term",
                "Unit mappings": "SELECT COUNT(*) FROM unit_term_map",
                "Taxonomy mappings": "SELECT COUNT(*) FROM taxonomy_term_map",
                "Phenotype mappings": "SELECT COUNT(*) FROM phenotype_term_map",
                "Environment mappings": "SELECT COUNT(*) FROM environment_term_map",
                "Crop-part mappings": "SELECT COUNT(*) FROM crop_part_term_map",
            }
            logger.info("Mapping summary")
            for label, query in queries.items():
                cursor.execute(query)
                logger.info("%s: %s", label, cursor.fetchone()[0])
        finally:
            cursor.close()


def load_database_config() -> Dict[str, Any]:
    env_file = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_file, override=True)

    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }
    missing = [
        name
        for name, value in {
            "DB_USER": config["user"],
            "DB_PASSWORD": config["password"],
            "DB_NAME": config["database"],
            "BIOPORTAL_API_KEY": os.getenv("BIOPORTAL_API_KEY"),
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing .env variables: " + ", ".join(missing))
    return config


def main():
    parser = argparse.ArgumentParser(description="Map Germinate data to ontologies")
    parser.add_argument("--skip-units", action="store_true")
    parser.add_argument("--skip-taxonomies", action="store_true")
    parser.add_argument("--skip-phenotypes", action="store_true")
    parser.add_argument("--skip-concentrations", action="store_true")
    parser.add_argument("--skip-environments", action="store_true")
    parser.add_argument("--skip-crop-parts", action="store_true")
    parser.add_argument("--test", action="store_true", help="Map five records per table")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    mapper = None
    try:
        mapper = OntologyMapper(load_database_config())
        mapper.bp.test_connection()
        limit = 5 if args.test else None

        if not args.skip_units:
            mapper.map_units(limit)
        if not args.skip_taxonomies:
            mapper.map_taxonomies(limit)
        if not args.skip_phenotypes:
            mapper.map_phenotypes(limit)
        if not args.skip_concentrations:
            mapper.map_concentrations(limit)
        if not args.skip_environments:
            mapper.map_environments(limit)
        if not args.skip_crop_parts:
            mapper.map_crop_parts(limit)

        mapper.show_summary()
        logger.info("All requested mappings completed successfully")
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as error:
        logger.error("Process failed: %s", error, exc_info=True)
        raise
    finally:
        if mapper:
            mapper.db.close()


if __name__ == "__main__":
    main()