"""
Outreach Manager Module
Handles developer outreach leads, tracking, and export to Excel (.xlsx) and CSV.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class OutreachManager:
    def __init__(self, db_file: str = "outreach_leads.json"):
        self.db_file = db_file
        self.leads = self.load_leads()

    def load_leads(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Error loading leads db: {e}")
        return []

    def save_leads(self):
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.leads, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] Error saving leads db: {e}")

    def add_or_update_leads(self, candidates: List[Dict[str, Any]], source_influencer: str = "") -> int:
        """Adds new candidates to the leads database, updating existing ones."""
        existing_map = {lead["token_address"]: lead for lead in self.leads}
        added_count = 0

        for cand in candidates:
            addr = cand.get("token_address")
            if not addr:
                continue

            if addr in existing_map:
                # Update stats
                existing_map[addr]["fdv"] = cand.get("fdv", existing_map[addr].get("fdv"))
                existing_map[addr]["liquidity_usd"] = cand.get("liquidity_usd", existing_map[addr].get("liquidity_usd"))
                existing_map[addr]["volume_24h"] = cand.get("volume_24h", existing_map[addr].get("volume_24h"))
                if cand.get("twitter_url"):
                    existing_map[addr]["twitter_url"] = cand["twitter_url"]
                if cand.get("telegram_url"):
                    existing_map[addr]["telegram_url"] = cand["telegram_url"]
            else:
                lead = {
                    "symbol": cand.get("symbol", "UNKNOWN"),
                    "name": cand.get("name", ""),
                    "chain_id": cand.get("chain_id", ""),
                    "token_address": addr,
                    "fdv": cand.get("fdv", 0),
                    "liquidity_usd": cand.get("liquidity_usd", 0),
                    "volume_24h": cand.get("volume_24h", 0),
                    "twitter_url": cand.get("twitter_url"),
                    "twitter_handle": cand.get("twitter_handle"),
                    "telegram_url": cand.get("telegram_url"),
                    "website_url": cand.get("website_url"),
                    "dex_url": cand.get("dex_url"),
                    "source_influencer": source_influencer,
                    "status": "New",
                    "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "notes": "",
                }
                self.leads.append(lead)
                existing_map[addr] = lead
                added_count += 1

        self.save_leads()
        return added_count

    def export_excel(self, file_path: str = "outreach_leads.xlsx") -> str:
        """Exports leads into a beautifully styled Excel workbook."""
        if not self.leads:
            df = pd.DataFrame(
                columns=[
                    "Symbol",
                    "Name",
                    "Chain",
                    "Contract Address",
                    "Market Cap (FDV)",
                    "Liquidity USD",
                    "24h Volume USD",
                    "Twitter (X)",
                    "Telegram",
                    "Website",
                    "DexScreener",
                    "Status",
                    "Added Date",
                    "Notes",
                ]
            )
            df.to_excel(file_path, index=False)
            return file_path

        rows = []
        for lead in self.leads:
            rows.append(
                {
                    "Symbol": lead.get("symbol", ""),
                    "Name": lead.get("name", ""),
                    "Chain": (lead.get("chain_id") or "").upper(),
                    "Contract Address": lead.get("token_address", ""),
                    "Market Cap (FDV)": round(lead.get("fdv") or 0),
                    "Liquidity USD": round(lead.get("liquidity_usd") or 0),
                    "24h Volume USD": round(lead.get("volume_24h") or 0),
                    "Twitter (X)": lead.get("twitter_url") or "",
                    "Telegram": lead.get("telegram_url") or "",
                    "Website": lead.get("website_url") or "",
                    "DexScreener": lead.get("dex_url") or "",
                    "Status": lead.get("status", "New"),
                    "Source Influencer": lead.get("source_influencer", ""),
                    "Added Date": lead.get("added_at", ""),
                    "Notes": lead.get("notes", ""),
                }
            )

        df = pd.DataFrame(rows)
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Leads")
            ws = writer.sheets["Leads"]

            # Styling
            header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            thin_border = Border(
                left=Side(style="thin", color="E2E8F0"),
                right=Side(style="thin", color="E2E8F0"),
                top=Side(style="thin", color="E2E8F0"),
                bottom=Side(style="thin", color="E2E8F0"),
            )

            # Format headers
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Number formatting and borders
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border
                    # Currency format for cols 5, 6, 7
                    if cell.column in [5, 6, 7]:
                        cell.number_format = "$#,##0"

            # Auto-fit column widths
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        return file_path

    def export_csv(self, file_path: str = "outreach_leads.csv") -> str:
        """Exports leads into CSV format."""
        if not self.leads:
            return file_path
        df = pd.DataFrame(self.leads)
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        return file_path
