import re
import base64
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

BASE_URL = "https://exams.mlrinstitutions.ac.in"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

def _extract_aspnet_tokens(html: str) -> Dict[str, str]:
    """Extract __VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION tokens."""
    soup = BeautifulSoup(html, "html.parser")
    tokens = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag and tag.get("value") is not None:
            tokens[name] = tag["value"]
    return tokens


async def fetch_student_details(
    roll_no: str,
    password: Optional[str] = None,
    include_photo_base64: bool = False,
    timeout_sec: float = 20.0
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

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_sec,
        verify=False,
        http2=False
    ) as client:
        # Step 1: GET Home page to retrieve initial ASP.NET tokens & session cookie
        res_home = await client.get(f"{BASE_URL}/", headers=headers)
        if res_home.status_code != 200:
            raise RuntimeError(f"MLRIT portal is unreachable. Status: {res_home.status_code}")

        tokens_home = _extract_aspnet_tokens(res_home.text)
        if not tokens_home.get("__VIEWSTATE"):
            raise RuntimeError("Failed to extract initial ASP.NET session tokens.")

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
            except Exception:
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
    timeout_sec: float = 20.0
) -> bytes:
    """Fetch raw photo bytes for streaming."""
    clean_roll = roll_no.strip().upper()
    login_pwd = (password or clean_roll).strip()

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_sec, verify=False) as client:
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
