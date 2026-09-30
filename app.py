"""
Web Dashboard Application for Crypto Twitter & DexScreener Outreach
Powered by FastAPI, Uvicorn, and HTML/Tailwind CSS
"""

import os
import sys
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules.similarity_engine import SimilarityEngine
from modules.outreach_manager import OutreachManager
from modules.outreach_generator import OutreachGenerator

# Reconfigure stdout for Windows console UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = FastAPI(title="Crypto X & DexScreener Outreach Studio", version="1.0.0")

# Initialize engine & manager
engine = SimilarityEngine()
outreach = OutreachManager("outreach_leads.json")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


class AnalyzeRequest(BaseModel):
    target: str
    auth_token: Optional[str] = None
    ct0: Optional[str] = None


class FindSimilarRequest(BaseModel):
    chain: Optional[str] = "all"
    min_fdv: float = 50_000
    max_fdv: float = 25_000_000
    min_liquidity: float = 20_000
    min_volume: float = 50_000
    require_socials: bool = True
    source_influencer: Optional[str] = ""
    limit: int = 40


class UpdateStatusRequest(BaseModel):
    token_address: str
    status: str
    notes: Optional[str] = ""


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join("static", "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Static index.html not found. Please create static/index.html</h1>"


@app.post("/api/analyze-influencer")
async def analyze_influencer_endpoint(req: AnalyzeRequest):
    if not req.target.strip():
        raise HTTPException(status_code=400, detail="Target username or URL is required.")

    # Re-initialize collector with cookies if provided
    if req.auth_token and req.ct0:
        engine.collector.auth_token = req.auth_token
        engine.collector.ct0 = req.ct0

    try:
        data = engine.analyze_influencer(req.target)
        return {"success": True, "data": data}
    except Exception as e:
        print(f"[!] Error analyzing influencer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/find-similar")
async def find_similar_endpoint(req: FindSimilarRequest):
    try:
        data = engine.find_matching_projects(
            chain=req.chain,
            min_fdv=req.min_fdv,
            max_fdv=req.max_fdv,
            min_liquidity=req.min_liquidity,
            min_volume=req.min_volume,
            require_socials=req.require_socials,
            source_influencer=req.source_influencer or "",
            limit=req.limit,
        )
        return {"success": True, "data": data}
    except Exception as e:
        print(f"[!] Error finding similar projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SimilarInfluencerRequest(BaseModel):
    target: str
    limit: Optional[int] = 8


@app.post("/api/find-similar-influencers")
async def find_similar_influencers_endpoint(req: SimilarInfluencerRequest):
    try:
        data = engine.analyze_influencer(req.target)
        similar = engine.find_similar_influencers(
            target_profile=data["profile"],
            promoted_coins=data["promoted_coins"],
            limit=req.limit,
        )
        return {"success": True, "target": data["profile"], "influencers": similar}
    except Exception as e:
        print(f"[!] Error finding similar influencers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SearchAccountsRequest(BaseModel):
    keyword: str
    limit: Optional[int] = 8
    min_followers: Optional[int] = 500


@app.post("/api/search-accounts")
async def search_accounts_endpoint(req: SearchAccountsRequest):
    if not req.keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is required")
    try:
        from modules.account_searcher import AccountSearcher
        searcher = AccountSearcher(collector=engine.collector)
        accounts = searcher.search_accounts(
            keyword=req.keyword,
            limit=req.limit or 8,
            min_followers=req.min_followers or 500
        )
        return {"success": True, "keyword": req.keyword, "accounts": accounts}
    except Exception as e:
        print(f"[!] Error searching accounts by keyword: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GeneratePitchRequest(BaseModel):
    target_type: str  # "influencer" or "dev"
    target_influencer: Optional[str] = None
    coin_symbol: Optional[str] = None
    custom_tweet_text: Optional[str] = None
    candidate_project: Optional[Dict[str, Any]] = None
    my_project_name: Optional[str] = "[Your Project Name]"
    my_chain: Optional[str] = "Solana"


@app.post("/api/generate-pitch")
async def generate_pitch_endpoint(req: GeneratePitchRequest):
    try:
        if req.target_type == "influencer":
            if not req.target_influencer:
                raise HTTPException(status_code=400, detail="target_influencer is required")
            data = engine.analyze_influencer(req.target_influencer)
            prof = data["profile"]
            # Find coin data if symbol provided
            target_coin = None
            if req.coin_symbol:
                for c in data.get("promoted_coins", []):
                    if c.get("symbol", "").lower() == req.coin_symbol.lower():
                        target_coin = c
                        break

            pitches = OutreachGenerator.generate_pitches_for_influencer(
                influencer_profile=prof,
                coin_data=target_coin,
                custom_tweet_text=req.custom_tweet_text,
                my_project_name=req.my_project_name or "[Your Project Name]",
                my_chain=req.my_chain or "Solana",
            )
            return {"success": True, "type": "influencer", "target": prof, "coin": target_coin, "pitches": pitches}

        elif req.target_type == "dev":
            if not req.candidate_project:
                raise HTTPException(status_code=400, detail="candidate_project data is required")
            inf_profile = None
            if req.target_influencer:
                try:
                    data = engine.analyze_influencer(req.target_influencer)
                    inf_profile = data["profile"]
                except Exception:
                    pass

            pitches = OutreachGenerator.generate_pitches_for_dev(
                candidate_project=req.candidate_project,
                influencer_profile=inf_profile,
            )
            return {"success": True, "type": "dev", "project": req.candidate_project, "pitches": pitches}

        else:
            raise HTTPException(status_code=400, detail="Invalid target_type")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[!] Error generating pitch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads")
async def get_leads_endpoint():
    leads = outreach.load_leads()
    return {"success": True, "leads": leads}


@app.post("/api/leads/update-status")
async def update_lead_status_endpoint(req: UpdateStatusRequest):
    for lead in outreach.leads:
        if lead["token_address"] == req.token_address:
            lead["status"] = req.status
            if req.notes is not None:
                lead["notes"] = req.notes
            outreach.save_leads()
            return {"success": True, "lead": lead}
    raise HTTPException(status_code=404, detail="Lead not found")


@app.get("/api/export/excel")
async def export_excel_endpoint():
    file_path = outreach.export_excel("outreach_leads.xlsx")
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            filename="crypto_dev_outreach_leads.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    raise HTTPException(status_code=404, detail="Excel file generation failed")


@app.get("/api/export/csv")
async def export_csv_endpoint():
    file_path = outreach.export_csv("outreach_leads.csv")
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            filename="crypto_dev_outreach_leads.csv",
            media_type="text/csv",
        )
    raise HTTPException(status_code=404, detail="CSV file generation failed")


if __name__ == "__main__":
    import uvicorn
    print("\n=======================================================")
    print("   CRYPTO X & DEXSCREENER OUTREACH STUDIO")
    print("   Web Dashboard starting at: http://127.0.0.1:8000")
    print("=======================================================\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
