import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from bson.objectid import ObjectId

app = FastAPI(title="Localprint API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def to_str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Convert datetime to isoformat where possible
    for k, v in list(d.items()):
        try:
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        except Exception:
            pass
    return d


@app.get("/")
def read_root():
    return {"message": "Localprint backend running"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Schemas endpoint for transparency (optional)
@app.get("/schema")
def get_schema():
    try:
        import schemas as s
        return {
            "collections": [
                {"name": "user", "schema": s.User.model_json_schema()},
                {"name": "provider", "schema": s.Provider.model_json_schema()},
                {"name": "review", "schema": s.Review.model_json_schema()},
                {"name": "printrequest", "schema": s.PrintRequest.model_json_schema()},
            ]
        }
    except Exception as e:
        return {"error": str(e)}


# API: Providers, Reviews, and Print Requests
class ProviderCreate(BaseModel):
    display_name: str
    city: str
    description: Optional[str] = None
    price_per_page: float
    color_supported: bool = True
    duplex: bool = True


class ProviderPublic(BaseModel):
    id: str
    display_name: str
    city: str
    description: Optional[str] = None
    price_per_page: float
    color_supported: bool
    duplex: bool
    rating: float
    reviews_count: int


class ReviewCreate(BaseModel):
    provider_id: str
    reviewer_name: str
    rating: int
    comment: Optional[str] = None


class PrintRequestCreate(BaseModel):
    provider_id: str
    requester_name: str
    requester_email: str
    pages: int
    color: str = "bw"
    notes: Optional[str] = None


@app.post("/api/providers", response_model=dict)
def create_provider(provider: ProviderCreate):
    from database import create_document
    data = provider.model_dump()
    # Defaults for rating info
    data.update({"rating": 0.0, "reviews_count": 0})
    inserted_id = create_document("provider", data)
    return {"id": inserted_id}


@app.get("/api/providers", response_model=List[ProviderPublic])
def list_providers(city: Optional[str] = Query(None, description="City filter, case-insensitive contains")):
    from database import get_documents
    flt = {}
    if city:
        # Simple case-insensitive contains search
        flt = {"city": {"$regex": city, "$options": "i"}}
    docs = get_documents("provider", filter_dict=flt, limit=50)
    results: List[ProviderPublic] = []
    for d in docs:
        d = to_str_id(d)
        results.append(ProviderPublic(**{
            "id": d.get("id"),
            "display_name": d.get("display_name"),
            "city": d.get("city"),
            "description": d.get("description"),
            "price_per_page": float(d.get("price_per_page", 0)),
            "color_supported": bool(d.get("color_supported", True)),
            "duplex": bool(d.get("duplex", True)),
            "rating": float(d.get("rating", 0.0)),
            "reviews_count": int(d.get("reviews_count", 0)),
        }))
    return results


@app.post("/api/reviews", response_model=dict)
def create_review(review: ReviewCreate):
    from database import db, create_document
    # Validate provider exists
    try:
        provider_obj_id = ObjectId(review.provider_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid provider_id")

    provider = db["provider"].find_one({"_id": provider_obj_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    review_id = create_document("review", review.model_dump())

    # Update aggregate rating
    reviews = list(db["review"].find({"provider_id": review.provider_id}))
    if reviews:
        avg = sum(int(r.get("rating", 0)) for r in reviews) / len(reviews)
        db["provider"].update_one(
            {"_id": provider_obj_id},
            {"$set": {"rating": round(avg, 2), "reviews_count": len(reviews)}}
        )

    return {"id": review_id}


@app.get("/api/reviews", response_model=List[dict])
def list_reviews(provider_id: str = Query(...)):
    from database import get_documents
    reviews = get_documents("review", {"provider_id": provider_id}, limit=50)
    return [to_str_id(r) for r in reviews]


@app.post("/api/print-requests", response_model=dict)
def create_print_request(payload: PrintRequestCreate):
    from database import create_document, db
    # Basic provider validation
    try:
        provider_obj_id = ObjectId(payload.provider_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid provider_id")

    if not db["provider"].find_one({"_id": provider_obj_id}):
        raise HTTPException(status_code=404, detail="Provider not found")

    inserted_id = create_document("printrequest", payload.model_dump())
    return {"id": inserted_id}


# Legacy hello endpoint kept for sanity checks
@app.get("/api/hello")
def hello():
    return {"message": "Hello from Localprint backend API!"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
