from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.semantic import router as semantic_router
from router.rdf import router as rdf_router
from router.rdf_comparison import router as rdf_comparison_router
from router.species_comparison import router as species_comparison_router
from router.ontology_search import router as ontology_search_router


app = FastAPI(
    title="Germinate Semantic API",
    description=(
        "BrAPI and SPARQL services for semantically "
        "annotated Germinate data."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register every API router
app.include_router(semantic_router)
app.include_router(rdf_router)
app.include_router(rdf_comparison_router)
app.include_router(species_comparison_router)
app.include_router(ontology_search_router)


@app.get("/")
def home():
    return {
        "name": "Germinate Semantic API",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }