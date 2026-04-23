import httpx
from bs4 import BeautifulSoup
from typing import Optional
import time

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

async def fetch_page(url: str) -> Optional[BeautifulSoup]:
    cached = get_cached(url)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
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
    search_query = query.replace(" ", "+")
    if appliance_type:
        search_query += f"+{appliance_type.replace(' ', '+')}"
    url = f"https://www.partselect.com/api/search/?searchterm={search_query}&type=parts"
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
                    parts.append({
                        "name": item.get("Name", ""),
                        "part_number": item.get("PartSelectNumber", ""),
                        "manufacturer_number": item.get("ManufacturerPartNumber", ""),
                        "price": item.get("SalePrice", ""),
                        "stock": item.get("Availability", ""),
                        "url": f"https://www.partselect.com/{item.get('PartSelectNumber', '')}.htm",
                        "image": item.get("SmallImageUrl", "")
                    })
                set_cached(url, parts)
                return parts
    except Exception as e:
        print(f"Search error: {e}")
    return []

async def get_model_parts(model_number: str) -> dict:
    url = f"https://www.partselect.com/Models/{model_number}/"
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
            if part_data:
                result["parts"].append(part_data)
    except Exception as e:
        print(f"Error parsing model parts: {e}")
    set_cached(url, result)
    return result

async def get_repair_guide(model_number: str, symptom: str) -> dict:
    symptom_slug = symptom.lower().replace(" ", "-")
    url = f"https://www.partselect.com/Models/{model_number}/Symptoms/{symptom_slug}/"
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
    url = f"https://www.partselect.com/PS{clean_number}.htm?ModelNum={model_number}"
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