from sqlalchemy import text
from sqlalchemy.orm import Session


def search_investors(db: Session, stage=None, sector=None, geography=None, cheque_max=None, q=None, limit=50, offset=0):
    sql = """
        SELECT id, canonical_name, website, domain, investor_type, status,
               hq_city, hq_country, stages, sectors, geographies,
               first_cheque_min, first_cheque_max, first_cheque_currency,
               description, investment_thesis, source_count, dedupe_confidence, needs_review
        FROM investors
        WHERE 1 = 1
    """
    params = {"limit": limit, "offset": offset}
    if stage:
        sql += " AND :stage = ANY(stages)"
        params["stage"] = stage
    if sector:
        sql += " AND :sector = ANY(sectors)"
        params["sector"] = sector
    if geography:
        sql += " AND :geography = ANY(geographies)"
        params["geography"] = geography
    if cheque_max is not None:
        sql += " AND (first_cheque_min IS NULL OR first_cheque_min <= :cheque_max)"
        params["cheque_max"] = cheque_max
    if q:
        sql += """
            AND (
                canonical_name ILIKE :q
                OR investment_thesis ILIKE :q
                OR description ILIKE :q
            )
        """
        params["q"] = f"%{q}%"
    sql += " ORDER BY canonical_name LIMIT :limit OFFSET :offset"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]
