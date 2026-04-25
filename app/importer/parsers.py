from app.importer.normalise import (
    clean_text,
    normalize_name,
    clean_website,
    extract_domain,
    split_stages,
    split_sectors,
    split_geographies,
    parse_money,
    split_portfolio_companies,
    json_or_none,
)


def parse_source_1_row(row):
    name = clean_text(row.get("name"))
    website = clean_text(row.get("website"))
    return {
        "source_name": "source_1",
        "source_row_id": clean_text(row.get("id")),
        "name": name,
        "normalized_name": normalize_name(name),
        "website": clean_website(website),
        "domain": extract_domain(website),
        "investor_type": None,
        "status": clean_text(row.get("status")),
        "hq_city": None,
        "hq_country": clean_text(row.get("location")),
        "hq_address": None,
        "stages": split_stages(row.get("round")),
        "sectors": split_sectors(row.get("sector")),
        "geographies": split_geographies(row.get("location")),
        "first_cheque_min": None,
        "first_cheque_max": None,
        "first_cheque_currency": None,
        "capital_under_management": None,
        "fund_size_raw": None,
        "deal_count_raw": None,
        "funds_raw_json": None,
        "description": None,
        "investment_thesis": None,
        "portfolio_companies": [],
        "raw_data": row.to_dict(),
    }


def parse_source_2_row(row):
    name = clean_text(row.get("name"))
    website = clean_text(row.get("websiteUrl"))
    return {
        "source_name": "source_2",
        "source_row_id": clean_text(row.get("accountId")),
        "name": name,
        "normalized_name": normalize_name(name),
        "website": clean_website(website),
        "domain": extract_domain(website),
        "investor_type": clean_text(row.get("typeOfCompany")),
        "status": clean_text(row.get("memberType")),
        "hq_city": clean_text(row.get("city")),
        "hq_country": clean_text(row.get("country")),
        "hq_address": clean_text(row.get("address")),
        "stages": split_stages(row.get("financingStages")),
        "sectors": split_sectors(row.get("industrySector")),
        "geographies": split_geographies(row.get("geoPreferences")),
        "first_cheque_min": None,
        "first_cheque_max": None,
        "first_cheque_currency": None,
        "capital_under_management": parse_money(row.get("capitalUnderManagement")),
        "fund_size_raw": None,
        "deal_count_raw": None,
        "funds_raw_json": json_or_none(row.get("funds_json")),
        "description": clean_text(row.get("profile")),
        "investment_thesis": None,
        "portfolio_companies": [],
        "raw_data": row.to_dict(),
    }


def parse_source_3_row(row):
    name = clean_text(row.get("name"))
    website = clean_text(row.get("website"))
    return {
        "source_name": "source_3",
        "source_row_id": None,
        "name": name,
        "normalized_name": normalize_name(name),
        "website": clean_website(website),
        "domain": extract_domain(website),
        "investor_type": None,
        "status": None,
        "hq_city": None,
        "hq_country": None,
        "hq_address": None,
        "stages": [],
        "sectors": [],
        "geographies": [],
        "first_cheque_min": None,
        "first_cheque_max": None,
        "first_cheque_currency": None,
        "capital_under_management": None,
        "fund_size_raw": clean_text(row.get("fundSize")),
        "deal_count_raw": clean_text(row.get("dealCount")),
        "funds_raw_json": None,
        "description": None,
        "investment_thesis": None,
        "portfolio_companies": split_portfolio_companies(row.get("portfolio")),
        "raw_data": row.to_dict(),
    }


def parse_source_4_row(row):
    name = clean_text(row.get("Investor name"))
    website = clean_text(row.get("Website"))
    thesis = clean_text(row.get("Ivestment thesis")) or clean_text(row.get("Investment thesis"))
    return {
        "source_name": "source_4",
        "source_row_id": None,
        "name": name,
        "normalized_name": normalize_name(name),
        "website": clean_website(website),
        "domain": extract_domain(website),
        "investor_type": clean_text(row.get("Investor type")),
        "status": None,
        "hq_city": None,
        "hq_country": None,
        "hq_address": clean_text(row.get("Global HQ")),
        "stages": split_stages(row.get("Stage of investment")),
        "sectors": split_sectors(thesis),
        "geographies": split_geographies(row.get("Countries of investment")),
        "first_cheque_min": parse_money(row.get("First cheque minimum")),
        "first_cheque_max": parse_money(row.get("First cheque maximum")),
        "first_cheque_currency": "USD",
        "capital_under_management": None,
        "fund_size_raw": None,
        "deal_count_raw": None,
        "funds_raw_json": None,
        "description": None,
        "investment_thesis": thesis,
        "portfolio_companies": [],
        "raw_data": row.to_dict(),
    }
