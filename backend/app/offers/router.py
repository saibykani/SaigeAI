"""In-hand salary and offer calculator (/api/offers). Calculation is pure (engine.py); only saved offers touch the database."""

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.offers import constants as k
from app.offers.engine import auto_split, calculate, compare
from app.offers.models import CompareRequest, OfferInput, ParseRequest, SavedOffer, SplitRequest
from app.offers.parse import parse_breakup
from app.services.audit import log_action
from app.utils import new_id, utcnow

router = APIRouter(prefix="/offers", tags=["offers"])
MAX_SAVED = 20


@router.get("/rules")
async def rules(user: dict = Depends(get_current_user)):
    return {"fy": k.FY_LABEL, "states": k.STATE_NAMES, "professional_tax": k.PROFESSIONAL_TAX, "assumptions": k.ASSUMPTIONS}


@router.post("/calculate")
async def calc(body: OfferInput, user: dict = Depends(get_current_user)):
    return calculate(body)


@router.post("/compare")
async def comp(body: CompareRequest, user: dict = Depends(get_current_user)):
    return compare(body)


@router.post("/split")
async def split(body: SplitRequest, user: dict = Depends(get_current_user)):
    return auto_split(body)


@router.post("/parse")
async def parse(body: ParseRequest, user: dict = Depends(get_current_user)):
    return parse_breakup(body.text)


@router.get("/saved")
async def saved(db: AsyncIOMotorDatabase = Depends(db_dep), user: dict = Depends(get_current_user)):
    rows = await db[c.SAVED_OFFERS].find({"user_id": user["_id"]}).sort("updated_at", -1).to_list(MAX_SAVED)
    return [{"id": r["_id"], "input": r["input"], "ctc": r.get("ctc"), "monthly_in_hand": r.get("monthly_in_hand"), "updated_at": r["updated_at"]}
            for r in rows]


@router.post("/saved", status_code=201)
async def save(body: SavedOffer, db: AsyncIOMotorDatabase = Depends(db_dep), user: dict = Depends(get_current_user)):
    uid = user["_id"]
    if await db[c.SAVED_OFFERS].count_documents({"user_id": uid}) >= MAX_SAVED:
        raise HTTPException(400, f"You can keep up to {MAX_SAVED} saved offers. Delete one first.")
    res = calculate(body.input)
    doc = {"_id": new_id(), "user_id": uid, "input": body.input.model_dump(), "ctc": res["ctc"], "monthly_in_hand": res["monthly_in_hand"],
           "created_at": utcnow(), "updated_at": utcnow()}
    await db[c.SAVED_OFFERS].insert_one(doc)
    await log_action(db, user_id=uid, action="offer.saved", entity="offer", entity_id=doc["_id"],
                     details={"name": body.input.name, "ctc": res["ctc"]})
    return {"id": doc["_id"], "ctc": doc["ctc"], "monthly_in_hand": doc["monthly_in_hand"]}


@router.put("/saved/{offer_id}")
async def update(offer_id: str, body: SavedOffer, db: AsyncIOMotorDatabase = Depends(db_dep), user: dict = Depends(get_current_user)):
    res = calculate(body.input)
    r = await db[c.SAVED_OFFERS].update_one({"_id": offer_id, "user_id": user["_id"]}, {"$set": {
        "input": body.input.model_dump(), "ctc": res["ctc"], "monthly_in_hand": res["monthly_in_hand"], "updated_at": utcnow()}})
    if not r.matched_count:
        raise HTTPException(404, "Offer not found")
    await log_action(db, user_id=user["_id"], action="offer.updated", entity="offer", entity_id=offer_id, details={"name": body.input.name})
    return {"id": offer_id, "ctc": res["ctc"], "monthly_in_hand": res["monthly_in_hand"]}


@router.delete("/saved/{offer_id}")
async def delete(offer_id: str, db: AsyncIOMotorDatabase = Depends(db_dep), user: dict = Depends(get_current_user)):
    r = await db[c.SAVED_OFFERS].delete_one({"_id": offer_id, "user_id": user["_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Offer not found")
    await log_action(db, user_id=user["_id"], action="offer.deleted", entity="offer", entity_id=offer_id)
    return {"deleted": True}
