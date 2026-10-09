# MLRIT Student Information API 🎓

A fast, lightweight, headless REST API that retrieves student details from the MLRIT Exam Portal (`https://exams.mlrinstitutions.ac.in/`).

- ⚡ **Ultra Fast**: Direct HTTP session emulation (~1.5 seconds response time).
- 🪶 **Low Resource Usage**: Consumes < 30MB RAM (no heavy browser binaries needed).
- 🌐 **Free Hosting Ready**: Can be deployed on Render, Fly.io, Cloudflare Tunnel, or locally.

---

## 🚀 API Endpoints

### 1. `GET /student/{roll_no}`
Fetch student profile details. Supports both `GET` and `HEAD` requests. By default, the roll number is used as the password.

- **Parameters**:
  - `roll_no` (path, required): Student roll number (e.g., `25R21A05LL`)
  - `password` (query, optional): Custom password if different from roll number
  - `include_photo_base64` (query, optional, default: `false`): Include base64 data URI for direct image embedding

**Example Request:**
```bash
curl -X GET "http://localhost:8000/student/25R21A05LL"
```

**Example Response:**
```json
{
  "success": true,
  "roll_no": "25R21A05LL",
  "name": "SIVANENI VENKATAVEERASRIGANGADHAR",
  "branch": "CSE",
  "semester": "II/IV I SEM",
  "batch": "2025 - 2026",
  "admission_date": "18/08/2025",
  "dob": "01/01/2007",
  "caste_category": "OC",
  "father_name": "SIVANENI SATYANARAYANA",
  "mother_name": "SIVANENI VARALAKSHMI",
  "student_email": "25r21a05ll@mlrit.ac.in",
  "parent_mobile": "9440426952",
  "aadhar_no": null,
  "apaar_id": "220871389708",
  "photo_url": "https://exams.mlrinstitutions.ac.in/StudentLogin/Student/StudentPhoto.aspx?StudId=19499&ColCode=PSS",
  "photo_base64": null
}
```

---

### 2. `POST /student`
Same as GET, but accepts JSON body.

**Example Request:**
```bash
curl -X POST "http://localhost:8000/student" \
     -H "Content-Type: application/json" \
     -d '{"roll_no": "25R21A05LL"}'
```

---

### 3. `GET /student/{roll_no}/photo`
Directly streams the student's profile photo as raw `image/jpeg` binary.

**Example:**
```html
<img src="https://your-api-domain/student/25R21A05LL/photo" alt="Student Photo" />
```

---

### 4. `GET /health`
Connectivity and diagnostic check. Tests whether your hosting environment can reach `exams.mlrinstitutions.ac.in` and reports latency, IP, and firewall status.

**Example Response:**
```json
{
  "portal_url": "https://exams.mlrinstitutions.ac.in",
  "portal_host": "exams.mlrinstitutions.ac.in",
  "proxy_configured": false,
  "proxy": null,
  "dns_resolved": true,
  "portal_ip": "202.53.15.72",
  "http_reachable": true,
  "http_status": 200,
  "latency_ms": 78.4,
  "error": null
}
```

---

### 5. Interactive Swagger Documentation
Open your browser and visit:
```
http://localhost:8000/docs
```

---

## 💻 Local Setup & Development

1. **Clone & Navigate into directory:**
   ```bash
   cd mlrit-api
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

---

## ⚠️ Important Note on Cloud Hosting & MLRIT Firewall

The MLRIT Exam Portal (`exams.mlrinstitutions.ac.in` / `202.53.15.72`) is hosted on an **on-premises network in Hyderabad, India**. Its firewall:
1. **Blocks incoming connections from overseas IP addresses (geo-blocked to India only)**.
2. **Drops connections from cloud datacenter IP ranges** (e.g., Render US/EU servers, AWS US, GCP US).

If you deploy on **Render.com** without an Indian proxy, requests to `/student/...` will hang for 15 seconds and return `504 Gateway Timeout` or `502 Bad Gateway` because Render's servers cannot reach the college portal.

### Solutions to Host the API Successfully:

#### Option 1: Expose Local Machine via Cloudflare Tunnel (Free & Instant)
Since you are in India, running the API on your local machine connects to the MLRIT portal in < 100ms. You can expose it with a free, secure public HTTPS URL:

```bash
# In terminal 1: start the API
uvicorn main:app --port 8000

# In terminal 2: create a free public Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```
Cloudflare will give you a public `https://<random-subdomain>.trycloudflare.com` URL that works anywhere in the world!

---

#### Option 2: Use Render with an Indian Proxy (`PORTAL_PROXY`)
If you want to keep hosting on Render, configure an Indian HTTP/HTTPS/SOCKS5 proxy:
1. In Render Dashboard → Your Web Service → **Environment Variables**.
2. Add:
   ```env
   PORTAL_PROXY=http://username:password@indian-proxy-host:port
   ```
3. The API will route all portal requests through India!

---

#### Option 3: Host on an India-Region Cloud Provider
Deploy on a platform with servers physically located in India:
- **Fly.io** (`region: bom` - Mumbai)
- **AWS EC2 / App Runner** (`ap-south-1` - Mumbai)
- **Google Cloud Run** (`asia-south1` - Mumbai)
- **Oracle Cloud Free Tier** (Mumbai / Hyderabad region)
