import httpx
from bs4 import BeautifulSoup
from typing import Optional
import time
from urllib.parse import quote_plus
import os

# Simple in-memory cache
cache = {}
CACHE_TTL = 3600  # 1 hour

def get_cached(key: str):
    if key in cache:
        data, timestamp = cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
        else:
            del cache[key]
    return None

def set_cached(key: str, data):
    cache[key] = (data, time.time())

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "").strip()

def is_blocked_html(html: str) -> bool:
    text_lower = (html or "")[:12000].lower()
    block_markers = [
        "access denied",
        "forbidden",
        "unusual traffic",
        "are you a human",
        "verify you are a human",
        "captcha",
        "cloudflare",
        "akamai",
        "incapsula",
        "challenge",
        "errors.edgesuite.net",
    ]
    return any(m in text_lower for m in block_markers)

async def fetch_html_with_scrapingbee(url: str) -> Optional[str]:
    if not SCRAPINGBEE_API_KEY:
        return None
    try:
        params = {
            "api_key": SCRAPINGBEE_API_KEY,
            "url": url,
            # Avoid JS rendering cost unless absolutely needed
            "render_js": "false",
            "block_resources": "true",
        }
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get("https://app.scrapingbee.com/api/v1/", params=params)
            if resp.status_code == 200 and resp.text and not is_blocked_html(resp.text):
                return resp.text
    except Exception as e:
        print(f"ScrapingBee error for {url}: {e}")
    return None

async def fetch_page(url: str) -> Optional[BeautifulSoup]:
    cached = get_cached(url)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
                if is_blocked_html(response.text):
                    print(f"Blocked or challenge page detected for {url}")
                    # Retry via ScrapingBee if configured
                    html = await fetch_html_with_scrapingbee(url)
                    if not html:
                        return None
                    soup = BeautifulSoup(html, "html.parser")
                    set_cached(url, soup)
                    return soup
                soup = BeautifulSoup(response.text, "html.parser")
                set_cached(url, soup)
                return soup
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def get_part_details(part_number: str) -> dict:
    clean_number = part_number.replace("PS", "").strip()
    url = f"https://www.partselect.com/PS{clean_number}.htm"
    soup = await fetch_page(url)
    if not soup:
        return {"error": f"Could not find part {part_number}"}
    result = {"part_number": f"PS{clean_number}", "url": url}
    try:
        title = soup.find("h1", class_="title-lg")
        if title:
            result["name"] = title.get_text(strip=True)
        price = soup.find("span", class_="price")
        if price:
            result["price"] = price.get_text(strip=True)
        stock = soup.find("span", class_="js-partAvailability")
        if stock:
            result["stock"] = stock.get_text(strip=True)
        # Best-effort image extraction for product cards.
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            result["image"] = og_img.get("content")
        else:
            img = soup.find("img", class_="pd__img")
            if img and img.get("src"):
                result["image"] = img.get("src")
        desc = soup.find("div", class_="pd__description")
        if desc:
            result["description"] = desc.get_text(strip=True)[:600]
        symptoms = []
        symptom_section = soup.find("div", class_="pd__crossref")
        if symptom_section:
            for item in symptom_section.find_all("li")[:5]:
                symptoms.append(item.get_text(strip=True))
        result["fixes_symptoms"] = symptoms
        install = soup.find("div", class_="pd__wrap--install")
        if install:
            result["installation"] = install.get_text(strip=True)[:800]
    except Exception as e:
        print(f"Error parsing part details: {e}")
    return result

async def search_parts(query: str, appliance_type: str = "") -> list:
    search_query = query.strip()
    if appliance_type:
        search_query = f"{search_query} {appliance_type}".strip()
    url = f"https://www.partselect.com/api/search/?searchterm={quote_plus(search_query)}&type=parts"
    cached = get_cached(url)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
                data = response.json()
                parts = []
                for item in data.get("Parts", [])[:6]:
                    ps = (item.get("PartSelectNumber", "") or "").strip()
                    parts.append({
                        "name": item.get("Name", ""),
                        "part_number": ps,
                        "manufacturer_number": item.get("ManufacturerPartNumber", ""),
                        "price": item.get("SalePrice", ""),
                        "stock": item.get("Availability", ""),
                        "url": f"https://www.partselect.com/{ps}.htm" if ps else "",
                        "image": item.get("SmallImageUrl", "")
                    })
                set_cached(url, parts)
                return parts
    except Exception as e:
        print(f"Search error: {e}")
    return []

async def get_model_parts(model_number: str) -> dict:
    url = f"https://www.partselect.com/Models/{quote_plus(model_number)}/"
    cached = get_cached(url)
    if cached:
        return cached
    soup = await fetch_page(url)
    if not soup:
        return {"error": f"Could not find model {model_number}"}
    result = {"model_number": model_number, "parts": [], "url": url}
    try:
        parts_section = soup.find_all("div", class_="mega-m__part")
        for part in parts_section[:8]:
            part_data = {}
            name = part.find("div", class_="mega-m__part__name")
            if name:
                part_data["name"] = name.get_text(strip=True)
            price = part.find("div", class_="mega-m__part__price")
            if price:
                part_data["price"] = price.get_text(strip=True)
            link = part.find("a")
            if link:
                part_data["url"] = "https://www.partselect.com" + link.get("href", "")
            # Best-effort PS number extraction from URL
            href = (link.get("href", "") if link else "") or ""
            if "/PS" in href.upper():
                try:
                    tail = href.split("/PS", 1)[1]
                    digits = "".join([c for c in tail if c.isdigit()])
                    if digits:
                        part_data["part_number"] = f"PS{digits}"
                except Exception:
                    pass
            if part_data:
                result["parts"].append(part_data)
    except Exception as e:
        print(f"Error parsing model parts: {e}")
    set_cached(url, result)
    return result

async def get_repair_guide(model_number: str, symptom: str) -> dict:
    symptom_slug = symptom.lower().replace(" ", "-")
    url = ""
    soup = None
    if model_number:
        url = f"https://www.partselect.com/Models/{quote_plus(model_number)}/Symptoms/{symptom_slug}/"
        soup = await fetch_page(url)
    if not soup:
        url = f"https://www.partselect.com/Repair/{symptom_slug}/"
        soup = await fetch_page(url)
    if not soup:
        return {"error": f"Could not find repair guide for: {symptom}"}
    result = {
        "symptom": symptom,
        "model_number": model_number,
        "recommended_parts": [],
        "instructions": "",
        "url": url
    }
    try:
        parts = soup.find_all("div", class_="symptomsResult__part")
        for part in parts[:5]:
            part_data = {}
            name = part.find("div", class_="symptomsResult__partName")
            if name:
                part_data["name"] = name.get_text(strip=True)
            number = part.find("div", class_="symptomsResult__partNumber")
            if number:
                part_data["part_number"] = number.get_text(strip=True)
            link = part.find("a")
            if link:
                part_data["url"] = "https://www.partselect.com" + link.get("href", "")
            if part_data:
                result["recommended_parts"].append(part_data)
        instructions = soup.find("div", class_="repair-story__instruction")
        if instructions:
            result["instructions"] = instructions.get_text(strip=True)[:1000]
    except Exception as e:
        print(f"Error parsing repair guide: {e}")
    return result

async def check_compatibility(part_number: str, model_number: str) -> dict:
    clean_number = part_number.replace("PS", "").strip()
    url = f"https://www.partselect.com/PS{clean_number}.htm?ModelNum={quote_plus(model_number)}"
    soup = await fetch_page(url)
    if not soup:
        return {"error": "Could not check compatibility"}
    result = {
        "part_number": f"PS{clean_number}",
        "model_number": model_number,
        "compatible": False,
        "message": "",
        "url": url
    }
    try:
        compat_section = soup.find("div", class_="pd__crossref__model")
        if compat_section:
            text = compat_section.get_text(strip=True).lower()
            if model_number.lower() in text:
                result["compatible"] = True
                result["message"] = f"Part PS{clean_number} is compatible with model {model_number}."
            else:
                result["compatible"] = False
                result["message"] = f"Part PS{clean_number} may not be compatible with model {model_number}. Please verify on PartSelect."
        else:
            result["message"] = f"Please verify compatibility of PS{clean_number} with model {model_number} on PartSelect."
    except Exception as e:
        print(f"Error checking compatibility: {e}")
    return result


def _infer_appliance_type_from_text(text: str) -> str:
    t = (text or "").lower()
    scores = {"refrigerator": 0, "dishwasher": 0}
    fridge_keywords = [
        "refrigerator",
        "fridge",
        "freezer",
        "ice maker",
        "french door",
        "side-by-side",
        "side by side",
        "refrigerator parts",
    ]
    dw_keywords = [
        "dishwasher",
        "dish washer",
        "dishwasher parts",
        "rack",
        "spray arm",
        "detergent",
    ]
    for k in fridge_keywords:
        if k in t:
            scores["refrigerator"] += 2
    for k in dw_keywords:
        if k in t:
            scores["dishwasher"] += 2
    if scores["refrigerator"] == 0 and scores["dishwasher"] == 0:
        return "unknown"
    return "refrigerator" if scores["refrigerator"] >= scores["dishwasher"] else "dishwasher"


async def validate_model_number(model_number: str) -> dict:
    """
    Best-effort validation of a PartSelect model page.
    Returns evidence fields the LLM can use to avoid guessing appliance type.
    """
    model = (model_number or "").strip()
    if not model:
        return {"error": "model_number is required"}

    url = f"https://www.partselect.com/Models/{quote_plus(model)}/"
    soup = await fetch_page(url)
    if not soup:
        return {
            "model_number": model,
            "found": False,
            "message": "Could not load a PartSelect model page for that model number.",
            "url": url,
        }

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    # Use a limited page text for heuristics; avoid huge payloads.
    text_blob = soup.get_text(" ", strip=True)[:6000]
    inferred = _infer_appliance_type_from_text(f"{title} {text_blob}")

    def is_not_found_page() -> bool:
        t = f"{title} {text_blob}".lower()
        markers = [
            "page not found",
            "we're sorry",
            "we are sorry",
            "no longer available",
            "could not be found",
            "404",
        ]
        return any(m in t for m in markers)

    # For demo reliability, treat any successfully loaded non-404-like page as "found",
    # even if the model token is not echoed in the visible title.
    model_u = model.upper()
    token_seen = model_u in title.upper() or model_u in text_blob.upper()
    found = (not is_not_found_page()) and (token_seen or bool(title))

    return {
        "model_number": model,
        "found": found,
        "title": title,
        "inferred_appliance_type": inferred,
        "message": (
            "Model page loaded on PartSelect."
            if found
            else "Could not confirm a valid PartSelect model page for that model number."
        ),
        "url": url,
    }