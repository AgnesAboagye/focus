import requests
import os
from dotenv import load_dotenv

load_dotenv()

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT")

def run_sparql(query):

    response = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )

    response.raise_for_status()

    return response.json()