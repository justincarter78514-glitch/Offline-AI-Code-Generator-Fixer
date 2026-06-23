"""
Offline AI Code Generator & Fixer — Web App version
Runs 100% locally. Open your browser to http://localhost:5000

SETUP:
1. Install Ollama: https://ollama.com/download
2. ollama pull qwen2.5-coder:3b   (or whichever model you're using)
3. pip install flask requests
4. python app.py
5. Open a browser to http://localhost:5000

Leave the terminal running while you use the app in the browser.
"""

from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import re
import os
import uuid
import zipfile
import tempfile

app = Flask(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:3b"   # change to match the model you pulled

GENERATED_DIR = os.path.join(tempfile.gettempdir(), "ai_code_assistant_projects")
os.makedirs(GENERATED_DIR, exist_ok=True)

LEVEL_PROMPTS = {
    "Beginner": "Explain everything in very simple terms. Use basic syntax, avoid advanced patterns, and add lots of comments explaining each line so a beginner programmer can learn from it.",
    "Junior": "Write clean, working code with reasonable comments. Use standard best practices but keep solutions straightforward, similar to what a junior developer would produce with guidance.",
    "Senior": "Write production-quality code following best practices, proper error handling, and efficient patterns. Briefly explain key design decisions like a senior engineer reviewing a PR.",
    "Staff": "Write highly optimized, scalable, and maintainable code as a staff engineer would. Consider edge cases, performance, architecture implications, and provide a concise rationale for trade-offs made.",
}

LANGUAGES = [
    "Python", "JavaScript", "TypeScript", "Java", "C", "C++", "C#",
    "Go", "Rust", "PHP", "Ruby", "Swift", "Kotlin", "SQL", "HTML/CSS", "Bash",
]

FRAMEWORKS = {
    "Python": ["None", "Django", "Flask", "FastAPI", "PyTorch", "TensorFlow", "Pandas/NumPy"],
    "JavaScript": ["None", "React", "Vue", "Node.js/Express", "Next.js", "Angular"],
    "TypeScript": ["None", "React", "Next.js", "Angular", "NestJS", "Vue"],
    "Java": ["None", "Spring Boot", "Hibernate", "Android (SDK)", "Maven/Gradle project"],
    "C": ["None"],
    "C++": ["None", "Qt", "Boost", "Unreal Engine"],
    "C#": ["None", ".NET / ASP.NET Core", "Unity", "WPF"],
    "Go": ["None", "Gin", "Echo", "Fiber"],
    "Rust": ["None", "Actix", "Axum", "Rocket"],
    "PHP": ["None", "Laravel", "Symfony", "WordPress"],
    "Ruby": ["None", "Ruby on Rails", "Sinatra"],
    "Swift": ["None", "SwiftUI", "UIKit"],
    "Kotlin": ["None", "Android (Jetpack)", "Ktor", "Spring Boot"],
    "SQL": ["None", "PostgreSQL", "MySQL", "SQLite", "SQL Server"],
    "HTML/CSS": ["None", "Tailwind CSS", "Bootstrap"],
    "Bash": ["None"],
}

POLITICAL_KEYWORDS = [
    "president", "election", "government", "democrat", "republican",
    "political party", "parliament", "communism", "socialism", "capitalism",
    "dictator", "regime", "prime minister", "senate", "congress", "vote",
    "campaign", "policy", "geopolitics", "diplomacy", "sanctions",
]

COUNTRY_NAMES = [
    "korea", "south korea", "north korea", "united states", "usa", "america",
    "china", "japan", "russia", "germany", "france", "united kingdom", "uk",
    "india", "canada", "australia", "brazil", "mexico", "italy", "spain",
    "netherlands", "sweden", "norway", "vietnam", "thailand", "philippines",
    "indonesia", "pakistan", "iran", "iraq", "israel", "saudi arabia",
    "turkey", "egypt", "nigeria", "south africa", "argentina", "ukraine",
    "poland", "switzerland", "belgium", "austria", "greece", "portugal",
    "denmark", "finland", "ireland", "new zealand", "singapore", "malaysia",
    "taiwan", "hong kong", "cuba", "venezuela", "colombia", "chile", "peru",
]

OFF_TOPIC_KEYWORDS = [
    "diagnosis", "symptom", "treatment", "disease", "patient", "surgery",
    "medication", "dosage", "prescription", "therapy", "healthcare",
    "hospital", "clinic", "nurse", "physician", "mental health", "cancer",
    "vaccine", "anatomy", "pharmacology",
    "martial arts", "karate", "judo", "taekwondo", "military", "army",
    "navy", "air force", "weapon", "combat training", "self-defense",
    "lawsuit", "court", "lawyer", "attorney", "legal advice", "contract law",
    "litigation", "criminal law",
    "stock market", "investment portfolio", "real estate", "insurance policy",
    "manufacturing plant", "supply chain logistics", "agriculture", "farming",
    "construction industry", "oil and gas",
    "recipe", "cooking", "diet plan", "workout routine", "relationship advice",
    "astrology", "horoscope", "religion", "theology",
]


def contains_korean(text):
    return any("\uac00" <= ch <= "\ud7a3" or "\u1100" <= ch <= "\u11ff" or "\u3130" <= ch <= "\u318f" for ch in text)


def find_blocked_terms(text):
    found = []
    lower = text.lower()
    if contains_korean(text):
        found.append("Korean language text")
    for kw in POLITICAL_KEYWORDS:
        if kw in lower:
            found.append(f"political term '{kw}'")
    for country in COUNTRY_NAMES:
        if country in lower:
            found.append(f"country name '{country}'")
    for term in OFF_TOPIC_KEYWORDS:
        if term in lower:
            found.append(f"unrelated topic '{term}'")
    return found


FILE_MARKER_RE = re.compile(
    r"###\s*FILE:\s*(?P<path>[^\n]+)\n```[a-zA-Z0-9]*\n(?P<content>.*?)```",
    re.DOTALL,
)


def parse_project_files(text):
    """Parses model output for blocks like:
    ### FILE: backend/server.js
    ```js
    ...code...
    ```
    Returns a dict {relative_path: content}. Empty dict if no markers found."""
    files = {}
    for match in FILE_MARKER_RE.finditer(text):
        path = match.group("path").strip().strip("`").replace("\\", "/")
        content = match.group("content").strip("\n")
        if path:
            files[path] = content
    return files


def build_project_zip(files: dict) -> str:
    """Writes files to a temp project folder and zips it. Returns the zip file path."""
    project_id = uuid.uuid4().hex[:10]
    project_root = os.path.join(GENERATED_DIR, project_id)
    os.makedirs(project_root, exist_ok=True)

    for rel_path, content in files.items():
        # prevent path traversal outside the project root
        safe_path = os.path.normpath(rel_path).lstrip(os.sep)
        if safe_path.startswith(".."):
            continue
        full_path = os.path.join(project_root, safe_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    zip_path = os.path.join(GENERATED_DIR, f"{project_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, filenames in os.walk(project_root):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, project_root)
                zf.write(fpath, arcname)

    return zip_path, project_id


PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Offline AI Code Assistant</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#1e1e1e; color:white; margin:0; padding:30px; }
  .wrap { max-width: 900px; margin: 0 auto; }
  h2 { margin-bottom: 2px; }
  .sub { color:#888; font-size:13px; margin-top:0; }
  .row { display:flex; gap:16px; align-items:center; margin:16px 0; flex-wrap:wrap; }
  label { font-size:14px; }
  select { padding:7px 10px; border-radius:6px; border:1px solid #444; background:#2d2d2d; color:white; }
  textarea { width:100%; height:140px; padding:12px; border-radius:8px; border:1px solid #444; background:#2d2d2d; color:white; font-family:Consolas, monospace; font-size:13px; box-sizing:border-box; resize:vertical; }
  .actions { display:flex; justify-content:flex-end; margin-top:10px; }
  button { background:white; color:#1e1e1e; border:none; padding:10px 24px; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; }
  button:disabled { opacity:0.6; cursor:default; }
  h3 { margin-top:24px; margin-bottom:8px; }
  #result { min-height:200px; border:1px solid #444; border-radius:8px; padding:16px; background:#111; white-space:pre-wrap; font-family:Consolas, monospace; font-size:13px; line-height:1.5; overflow-x:auto; }
  .warn { background:#3a2a00; border:1px solid #d99a00; color:#ffce5c; padding:12px 16px; border-radius:8px; margin-top:10px; display:none; white-space:pre-wrap; }
</style>
</head>
<body>
<div class="wrap">
  <h2>Offline AI Code Generator & Fixer</h2>
  <p class="sub">Model: {{ model }} | Running locally via Ollama</p>

  <div class="row">
    <label>Level:
      <select id="level">
        {% for l in levels %}<option>{{ l }}</option>{% endfor %}
      </select>
    </label>
    <label>Language:
      <select id="language" onchange="updateFrameworks()">
        {% for l in languages %}<option>{{ l }}</option>{% endfor %}
      </select>
    </label>
    <label>Framework:
      <select id="framework"></select>
    </label>
  </div>

  <div class="row">
    <label><input type="checkbox" id="fullstack" onchange="toggleFullstack()"> Full-stack project (separate backend + frontend)</label>
  </div>

  <div class="row" id="frontendRow" style="display:none;">
    <span style="color:#888; font-size:13px;">Frontend &rarr;</span>
    <label>Language:
      <select id="feLanguage" onchange="updateFeFrameworks()">
        {% for l in languages %}<option>{{ l }}</option>{% endfor %}
      </select>
    </label>
    <label>Framework:
      <select id="feFramework"></select>
    </label>
  </div>

  <textarea id="instructions" placeholder="Describe what code to generate, or paste code + describe the bug to fix..."></textarea>

  <div class="actions">
    <button id="runBtn" onclick="runCode()">▲ Run</button>
  </div>

  <div class="warn" id="warnBox"></div>

  <h3>Result</h3>
  <div id="result">Output will appear here...</div>
</div>

<script>
const frameworks = {{ frameworks | tojson }};

function updateFrameworks() {
  const lang = document.getElementById('language').value;
  const sel = document.getElementById('framework');
  sel.innerHTML = '';
  (frameworks[lang] || ['None']).forEach(f => {
    const opt = document.createElement('option');
    opt.value = f; opt.textContent = f;
    sel.appendChild(opt);
  });
}
updateFrameworks();

function updateFeFrameworks() {
  const lang = document.getElementById('feLanguage').value;
  const sel = document.getElementById('feFramework');
  sel.innerHTML = '';
  (frameworks[lang] || ['None']).forEach(f => {
    const opt = document.createElement('option');
    opt.value = f; opt.textContent = f;
    sel.appendChild(opt);
  });
}

function toggleFullstack() {
  const checked = document.getElementById('fullstack').checked;
  document.getElementById('frontendRow').style.display = checked ? 'flex' : 'none';
  if (checked) {
    document.getElementById('feLanguage').value = 'JavaScript';
    updateFeFrameworks();
    document.getElementById('feFramework').value = 'React';
  }
}

async function runCode() {
  const level = document.getElementById('level').value;
  const language = document.getElementById('language').value;
  const framework = document.getElementById('framework').value;
  const instructions = document.getElementById('instructions').value.trim();
  const fullstack = document.getElementById('fullstack').checked;
  const feLanguage = fullstack ? document.getElementById('feLanguage').value : null;
  const feFramework = fullstack ? document.getElementById('feFramework').value : null;
  const resultBox = document.getElementById('result');
  const warnBox = document.getElementById('warnBox');
  const btn = document.getElementById('runBtn');

  warnBox.style.display = 'none';

  if (!instructions) {
    warnBox.textContent = "Please enter instructions first.";
    warnBox.style.display = 'block';
    return;
  }

  btn.disabled = true;
  btn.textContent = "Running...";
  resultBox.textContent = "Generating...";

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({level, language, framework, instructions, fullstack, feLanguage, feFramework})
    });
    const data = await res.json();

    if (data.blocked) {
      warnBox.textContent = "Blocked content:\\n- " + data.blocked.join("\\n- ");
      warnBox.style.display = 'block';
      resultBox.textContent = "Output will appear here...";
    } else if (data.download_url) {
      resultBox.innerHTML = "Project generated with " + data.file_count + " files.\\n\\n" +
        "<a href='" + data.download_url + "' style='color:#7fd3ff; text-decoration:underline;'>Download project (.zip)</a>\\n\\n" +
        "Files:\\n- " + data.files.join("\\n- ");
    } else {
      resultBox.textContent = data.output;
    }
  } catch (e) {
    resultBox.textContent = "Error: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "▲ Run";
  }
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        PAGE, model=MODEL_NAME, levels=list(LEVEL_PROMPTS.keys()),
        languages=LANGUAGES, frameworks=FRAMEWORKS
    )


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    instructions = data.get("instructions", "").strip()
    level = data.get("level", "Beginner")
    language = data.get("language", "Python")
    framework = data.get("framework", "None")
    fullstack = data.get("fullstack", False)
    fe_language = data.get("feLanguage", "JavaScript")
    fe_framework = data.get("feFramework", "None")

    blocked = find_blocked_terms(instructions)
    if blocked:
        return jsonify({"blocked": blocked})

    if fullstack:
        fe_fw_line = f" using {fe_framework}" if fe_framework and fe_framework != "None" else ""
        be_fw_line = f" using {framework}" if framework and framework != "None" else ""
        system_prompt = (
            f"You are an AI coding assistant. Skill level context: {LEVEL_PROMPTS[level]}\n\n"
            f"Generate a complete full-stack project with two parts:\n"
            f"1. Backend: {language}{be_fw_line}, placed under a 'backend/' folder.\n"
            f"2. Frontend: {fe_language}{fe_fw_line}, placed under a 'frontend/' folder.\n\n"
            "Output EVERY file using exactly this format, with no extra commentary outside it:\n\n"
            "### FILE: backend/relative/path.ext\n"
            "```\n"
            "<file content>\n"
            "```\n\n"
            "Repeat this block for every file needed (e.g. package.json, server entry point, "
            "routes, React components, App.js, index.html, etc.) so the project is complete and runnable. "
            "Include a backend/package.json and frontend/package.json with correct dependencies. "
            "Do not write any explanation outside the FILE blocks."
        )
    else:
        framework_line = (
            f"Use the {framework} framework/library conventions and idioms where applicable.\n\n"
            if framework and framework != "None" else ""
        )
        system_prompt = (
            f"You are an AI coding assistant. Skill level context: {LEVEL_PROMPTS[level]}\n\n"
            f"Target programming language: {language}. Write all code in {language} unless the "
            "user's instructions explicitly paste code in a different language to be fixed — "
            "in that case, fix it in its original language.\n\n"
            f"{framework_line}"
            "When given instructions, either generate new code or fix issues in provided code. "
            "Always return clear, well-formatted code blocks. You may include a brief intro, "
            "explanation, or summary about the code, but stay strictly focused on the code itself — "
            "do not discuss unrelated topics."
        )

    full_prompt = f"{system_prompt}\n\nUser request:\n{instructions}"

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": full_prompt, "stream": False},
            timeout=600,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        output = resp.json().get("response", "No response received.")
    except requests.exceptions.ConnectionError:
        output = (
            "ERROR: Could not connect to Ollama at 127.0.0.1:11434.\n"
            "Make sure Ollama is running (ollama serve) and the model is pulled:\n"
            f"    ollama pull {MODEL_NAME}"
        )
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"output": f"ERROR: {e}"})

    if fullstack:
        files = parse_project_files(output)
        if not files:
            return jsonify({
                "output": "The model did not return files in the expected format. "
                          "Raw response below:\n\n" + output
            })
        zip_path, project_id = build_project_zip(files)
        return jsonify({
            "download_url": f"/download/{project_id}",
            "file_count": len(files),
            "files": sorted(files.keys()),
        })

    return jsonify({"output": output})


@app.route("/download/<project_id>")
def download(project_id):
    zip_path = os.path.join(GENERATED_DIR, f"{project_id}.zip")
    if not os.path.isfile(zip_path):
        return "Project not found or expired.", 404
    return send_file(zip_path, as_attachment=True, download_name=f"project_{project_id}.zip")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
