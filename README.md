# MLRIT Student Information API 🎓

A fast, lightweight, headless REST API that retrieves student details from the MLRIT Exam Portal (`https://exams.mlrinstitutions.ac.in/`).

- ⚡ **Ultra Fast**: Direct HTTP session emulation (~1.5 seconds response time).
- 🪶 **Low Resource Usage**: Consumes < 30MB RAM (no heavy browser binaries needed).
- 🌐 **100% Free Hosting Ready**: Easily hostable on Render, Koyeb, Hugging Face Spaces, or Railway.

---

## 🚀 API Endpoints

### 1. `GET /student/{roll_no}`
Fetch student profile details. By default, the roll number is used as the password.

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
Can be used directly inside HTML:
```html
<img src="https://your-api.onrender.com/student/25R21A05LL/photo" alt="Student Photo" />
```

---

### 4. Interactive Swagger Documentation
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

## ☁️ How to Host Online for FREE

### Option 1: Render.com (Recommended - Easiest & Free)

1. Push your repository to GitHub.
2. Sign in to [Render.com](https://render.com/) (free account).
3. Click **New +** → **Web Service**.
4. Connect your GitHub repository.
5. Set:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Click **Deploy Web Service**. You will get a free public `https://<your-service>.onrender.com` URL!

---

### Option 2: Koyeb (Free Docker or Git)

1. Sign up at [Koyeb.com](https://www.koyeb.com/).
2. Create App → Choose GitHub repo.
3. Koyeb will automatically detect the `Dockerfile` or `requirements.txt` and launch the API for free.

---

### Option 3: Hugging Face Spaces (Docker - Free 16GB RAM)

1. Create a new Space on [Hugging Face](https://huggingface.co/spaces).
2. Choose **Docker** as the SDK.
3. Push these repository files. It will build and serve your API with no cost!
# mlrit-api
