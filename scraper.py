import os
import re
import time
import socket
import logging
import base64
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("mlrit_scraper")

BASE_URL = os.getenv("PORTAL_BASE_URL", "https://exams.mlrinstitutions.ac.in").rstrip("/")
PORTAL_PROXY = os.getenv("PORTAL_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
PORTAL_TIMEOUT = float(os.getenv("PORTAL_TIMEOUT", "15.0"))

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def get_async_client(timeout_sec: Optional[float] = None) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient with proxy and timeout support."""
    effective_timeout = timeout_sec if timeout_sec is not None else PORTAL_TIMEOUT
    client_kwargs = {
        "follow_redirects": True,
        "timeout": effective_timeout,
        "verify": False,
        "http2": False,
    }
    if PORTAL_PROXY:
        client_kwargs["proxy"] = PORTAL_PROXY
    return httpx.AsyncClient(**client_kwargs)


def _extract_aspnet_tokens(html: str) -> Dict[str, str]:
    """Extract __VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION tokens."""
    soup = BeautifulSoup(html, "html.parser")
    tokens = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag and tag.get("value") is not None:
            tokens[name] = tag["value"]
    return tokens


async def check_portal_connectivity(timeout_sec: float = 6.0) -> Dict[str, Any]:
    """Test DNS resolution, latency, and HTTP reachability to the MLRIT portal."""
    parsed = urlparse(BASE_URL)
    host = parsed.hostname or "exams.mlrinstitutions.ac.in"
    result: Dict[str, Any] = {
        "portal_url": BASE_URL,
        "portal_host": host,
        "proxy_configured": bool(PORTAL_PROXY),
        "proxy": PORTAL_PROXY if PORTAL_PROXY else None,
        "server_outbound_ip": None,
        "dns_resolved": False,
        "portal_ip": None,
        "http_reachable": False,
        "http_status": None,
        "latency_ms": None,
        "error": None,
    }

    # Fetch server's public outbound IP
    try:
        async with httpx.AsyncClient(timeout=3.0) as ip_client:
            r_ip = await ip_client.get("https://api.ipify.org?format=json")
            if r_ip.status_code == 200:
                result["server_outbound_ip"] = r_ip.json().get("ip")
    except Exception:
        pass

    t0 = time.time()
    try:
        result["portal_ip"] = socket.gethostbyname(host)
        result["dns_resolved"] = True
    except Exception as e:
        result["error"] = f"DNS resolution failed for {host}: {str(e)}"
        return result

    try:
        async with get_async_client(timeout_sec=timeout_sec) as client:
            headers = {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            res = await client.get(f"{BASE_URL}/", headers=headers)
            result["http_status"] = res.status_code
            result["http_reachable"] = (res.status_code == 200)
            result["latency_ms"] = round((time.time() - t0) * 1000, 2)
    except httpx.TimeoutException:
        result["error"] = (
            "Connection timed out. The MLRIT Portal firewall is blocking/dropping requests from this server's IP. "
            "Because MLRIT is hosted on an Indian on-premise network, cloud servers outside India need an Indian proxy "
            "(set PORTAL_PROXY env var) or to be hosted within India."
        )
    except httpx.ConnectError as e:
        result["error"] = f"Connection refused or dropped by firewall: {str(e)}"
    except Exception as e:
        result["error"] = f"Connection check failed: {type(e).__name__} ({str(e)})"

    return result


async def fetch_student_details(
    roll_no: str,
    password: Optional[str] = None,
    include_photo_base64: bool = False,
    timeout_sec: Optional[float] = None
) -> Dict[str, Any]:
    """
    Asynchronously scrape student basic information from MLRIT portal.
    Password defaults to roll_no if not specified.
    """
    clean_roll = roll_no.strip().upper()
    login_pwd = (password or clean_roll).strip()

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with get_async_client(timeout_sec=timeout_sec) as client:
        # Step 1: GET Home page to retrieve initial ASP.NET tokens & session cookie
        res_home = await client.get(f"{BASE_URL}/", headers=headers)
        if res_home.status_code != 200:
            raise RuntimeError(f"MLRIT portal returned status {res_home.status_code} on home page.")

        tokens_home = _extract_aspnet_tokens(res_home.text)
        if not tokens_home.get("__VIEWSTATE"):
            raise RuntimeError("Failed to extract initial ASP.NET session tokens from home page.")

        # Step 2: Post back 'lnkStudent' to reveal student login inputs
        post_lnk_student = {
            "__EVENTTARGET": "lnkStudent",
            "__EVENTARGUMENT": "",
            **tokens_home
        }
        res_login_page = await client.post(f"{BASE_URL}/", data=post_lnk_student, headers=headers)
        tokens_login = _extract_aspnet_tokens(res_login_page.text)

        # Step 3: Submit Roll Number & Password
        post_credentials = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "txtUserId": clean_roll,
            "txtPwd": login_pwd,
            "btnLogin": "Login",
            **tokens_login
        }
        res_login = await client.post(f"{BASE_URL}/", data=post_credentials, headers=headers)

        # Verify successful login: portal redirects to MainStud.aspx
        if "MainStud.aspx" not in str(res_login.url):
            raise ValueError("Invalid Roll Number or Password, or login failed.")

        # Step 4: Request Student Information page directly
        stud_info_url = f"{BASE_URL}/StudentLogin/Student/StudentInformation.aspx"
        info_headers = {
            **headers,
            "Referer": str(res_login.url)
        }
        res_info = await client.get(stud_info_url, headers=info_headers)
        if res_info.status_code != 200:
            raise RuntimeError(f"Could not load Student Information page. Status: {res_info.status_code}")

        # Step 5: Parse Student details
        soup = BeautifulSoup(res_info.text, "html.parser")

        def get_input_val(suffix: str) -> Optional[str]:
            elem = soup.find("input", id=lambda x: x and x.endswith(suffix))
            if elem and elem.get("value"):
                return elem["value"].strip()
            return None

        def get_span_text(suffix: str) -> Optional[str]:
            elem = soup.find("span", id=lambda x: x and x.endswith(suffix))
            if elem and elem.text:
                return elem.text.strip()
            return None

        # Extract Header attributes
        ht_no = get_span_text("lblHTNo") or get_input_val("txtHTNo") or clean_roll
        name = get_span_text("lblStudName") or get_input_val("txtName")
        branch = get_span_text("lblBranch")
        sem = get_span_text("lblSem")

        # Extract Detailed Form fields
        admin_date = get_input_val("txtAdminDate")
        batch = get_input_val("txtBatch")
        dob = get_input_val("txtDOB")
        caste_category = get_input_val("txtCasteCategory")
        father_name = get_input_val("txtParentName")
        mother_name = get_input_val("txtMotherName")
        student_email = get_input_val("txtStuEmail")
        parent_mobile = get_input_val("txtParentMblNo")
        aadhar_no = get_input_val("txtAadharNo")
        apaar_id = get_input_val("txtaaparid")

        # Extract Photo URL if available
        photo_url = None
        photo_match = re.search(r'src=[\"\']([^\"\']*StudentPhoto[^\"\']*)[\"\']', res_info.text, re.IGNORECASE)
        if photo_match:
            rel_photo = photo_match.group(1).replace("&amp;", "&")
            photo_url = f"{BASE_URL}/StudentLogin/Student/{rel_photo}"

        # Fetch Photo Base64 if requested
        photo_base64 = None
        if include_photo_base64 and photo_url:
            try:
                res_photo = await client.get(photo_url, headers=info_headers)
                if res_photo.status_code == 200:
                    content_type = res_photo.headers.get("content-type", "image/jpeg")
                    encoded = base64.b64encode(res_photo.content).decode("utf-8")
                    photo_base64 = f"data:{content_type};base64,{encoded}"
            except Exception as e:
                logger.warning(f"Failed to fetch photo base64: {e}")
                photo_base64 = None

        return {
            "success": True,
            "roll_no": ht_no,
            "name": name,
            "branch": branch,
            "semester": sem,
            "batch": batch,
            "admission_date": admin_date,
            "dob": dob,
            "caste_category": caste_category,
            "father_name": father_name,
            "mother_name": mother_name,
            "student_email": student_email,
            "parent_mobile": parent_mobile,
            "aadhar_no": aadhar_no,
            "apaar_id": apaar_id,
            "photo_url": photo_url,
            "photo_base64": photo_base64
        }


async def fetch_student_photo_bytes(
    roll_no: str,
    password: Optional[str] = None,
    timeout_sec: Optional[float] = None
) -> bytes:
    """Fetch raw photo bytes for streaming."""
    clean_roll = roll_no.strip().upper()
    login_pwd = (password or clean_roll).strip()

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
    }

    async with get_async_client(timeout_sec=timeout_sec) as client:
        res_home = await client.get(f"{BASE_URL}/", headers=headers)
        tokens_home = _extract_aspnet_tokens(res_home.text)

        res_login_page = await client.post(
            f"{BASE_URL}/",
            data={"__EVENTTARGET": "lnkStudent", "__EVENTARGUMENT": "", **tokens_home},
            headers=headers
        )
        tokens_login = _extract_aspnet_tokens(res_login_page.text)

        res_login = await client.post(
            f"{BASE_URL}/",
            data={
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "txtUserId": clean_roll,
                "txtPwd": login_pwd,
                "btnLogin": "Login",
                **tokens_login
            },
            headers=headers
        )
        if "MainStud.aspx" not in str(res_login.url):
            raise ValueError("Invalid Roll Number or Password.")

        stud_info_url = f"{BASE_URL}/StudentLogin/Student/StudentInformation.aspx"
        info_headers = {**headers, "Referer": str(res_login.url)}
        res_info = await client.get(stud_info_url, headers=info_headers)

        photo_match = re.search(r'src=[\"\']([^\"\']*StudentPhoto[^\"\']*)[\"\']', res_info.text, re.IGNORECASE)
        if not photo_match:
            raise FileNotFoundError("Photo not found for this student.")

        rel_photo = photo_match.group(1).replace("&amp;", "&")
        photo_url = f"{BASE_URL}/StudentLogin/Student/{rel_photo}"
        res_photo = await client.get(photo_url, headers=info_headers)
        if res_photo.status_code != 200:
            raise FileNotFoundError("Could not download student photo.")

        return res_photo.content
