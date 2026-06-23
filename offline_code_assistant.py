
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import threading

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:3b"   # change this to match the model you pulled

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

# --- Content filter settings ---
# Blocks: Korean script text, political keywords, and country names in the input.
# Edit these lists to adjust what gets blocked.

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

# Non-programming subject areas that should be rejected even if no political/
# country/Korean terms are present. Edit freely to expand coverage.
OFF_TOPIC_KEYWORDS = [
    # medical / healthcare
    "diagnosis", "symptom", "treatment", "disease", "patient", "surgery",
    "medication", "dosage", "prescription", "therapy", "healthcare",
    "hospital", "clinic", "nurse", "physician", "mental health", "cancer",
    "vaccine", "anatomy", "pharmacology",
    # martial / military
    "martial arts", "karate", "judo", "taekwondo", "military", "army",
    "navy", "air force", "weapon", "combat training", "self-defense",
    # legal
    "lawsuit", "court", "lawyer", "attorney", "legal advice", "contract law",
    "litigation", "criminal law",
    # finance/industry unrelated to coding
    "stock market", "investment portfolio", "real estate", "insurance policy",
    "manufacturing plant", "supply chain logistics", "agriculture", "farming",
    "construction industry", "oil and gas",
    # general off-topic
    "recipe", "cooking", "diet plan", "workout routine", "relationship advice",
    "astrology", "horoscope", "religion", "theology","sex", "trangender",
    "clothes", "ware", "underware", "girl", "women","man","boy"
]

PROGRAMMING_HINTS = [
    "code", "function", "bug", "error", "class", "variable", "script",
    "algorithm", "api", "compile", "syntax", "debug", "refactor", "loop",
    "array", "library", "framework", "database", "query", "endpoint",
    "component", "module", "import", "method", "exception", "test case",
]


def contains_korean(text: str) -> bool:
    """Detects Hangul (Korean script) characters in the text."""
    for ch in text:
        if "\uac00" <= ch <= "\ud7a3" or "\u1100" <= ch <= "\u11ff" or "\u3130" <= ch <= "\u318f":
            return True
    return False


def find_blocked_terms(text: str):
    """Returns a list of blocked terms/categories found in the text, or [] if clean."""
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


def extract_code_only(text: str) -> str:
    """Strips everything except fenced code blocks from the model's response.
    Returns only the code, concatenated with separators if multiple blocks exist.
    If no fenced code block is found, returns a fallback message."""
    import re
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return "No code block was returned by the model. Try rephrasing your instructions."
    return "\n\n# ---\n\n".join(block.strip() for block in blocks)


class CodeAssistantApp:
    def __init__(self, root):
        self.root = root
        root.title("Offline AI Code Assistant")
        root.geometry("900x700")
        root.configure(bg="#1e1e1e")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox", padding=5)

        tk.Label(root, text="Offline AI Code Generator & Fixer", bg="#1e1e1e",
                 fg="white", font=("Segoe UI", 16, "bold")).pack(pady=(15, 0))
        tk.Label(root, text=f"Model: {MODEL_NAME}  |  Running locally via Ollama",
                 bg="#1e1e1e", fg="#888", font=("Segoe UI", 9)).pack(pady=(0, 10))

        frame_top = tk.Frame(root, bg="#1e1e1e")
        frame_top.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_top, text="Level:", bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 11)).pack(side="left")
        self.level_var = tk.StringVar(value="Beginner")
        level_dropdown = ttk.Combobox(frame_top, textvariable=self.level_var,
                                       values=list(LEVEL_PROMPTS.keys()),
                                       state="readonly", width=15)
        level_dropdown.pack(side="left", padx=10)

        tk.Label(frame_top, text="Language:", bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(20, 0))
        self.language_var = tk.StringVar(value="Python")
        language_dropdown = ttk.Combobox(frame_top, textvariable=self.language_var,
                                          values=LANGUAGES, state="readonly", width=15)
        language_dropdown.pack(side="left", padx=10)
        language_dropdown.bind("<<ComboboxSelected>>", self.on_language_change)

        tk.Label(frame_top, text="Framework:", bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(20, 0))
        self.framework_var = tk.StringVar(value=FRAMEWORKS["Python"][0])
        self.framework_dropdown = ttk.Combobox(frame_top, textvariable=self.framework_var,
                                                values=FRAMEWORKS["Python"], state="readonly", width=18)
        self.framework_dropdown.pack(side="left", padx=10)

        tk.Label(root, text="Instructions (describe what to generate, or paste code + describe the bug):",
                 bg="#1e1e1e", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(15, 5))
        self.instructions_box = scrolledtext.ScrolledText(root, height=8, bg="#2d2d2d", fg="white",
                                                            insertbackground="white", font=("Consolas", 10))
        self.instructions_box.pack(fill="x", padx=20)

        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(fill="x", padx=20, pady=10)
        self.run_btn = tk.Button(btn_frame, text="▲ Run", command=self.run_clicked,
                                  bg="white", fg="#1e1e1e", font=("Segoe UI", 11, "bold"),
                                  padx=20, pady=6, relief="flat", cursor="hand2")
        self.run_btn.pack(side="right")

        tk.Label(root, text="Result:", bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(10, 5))
        self.result_box = scrolledtext.ScrolledText(root, height=16, bg="#111111", fg="#9cdcfe",
                                                      insertbackground="white", font=("Consolas", 10))
        self.result_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.result_box.insert("1.0", "Output will appear here...")
        self.result_box.config(state="disabled")

    def on_language_change(self, event=None):
        lang = self.language_var.get()
        options = FRAMEWORKS.get(lang, ["None"])
        self.framework_dropdown.config(values=options)
        self.framework_var.set(options[0])

    def set_result(self, text):
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")

    def run_clicked(self):
        instructions = self.instructions_box.get("1.0", "end").strip()
        if not instructions:
            messagebox.showwarning("Missing input", "Please enter instructions first.")
            return

        blocked = find_blocked_terms(instructions)
        if blocked:
            messagebox.showwarning(
                "Blocked Content",
                "Your input contains restricted content:\n\n- " + "\n- ".join(blocked)
                + "\n\nPlease remove these and try again."
            )
            return

        self.run_btn.config(state="disabled", text="Running...")
        self.set_result("Generating... (first run may be slower while the model loads into VRAM)")

        thread = threading.Thread(target=self.call_ollama, args=(instructions,))
        thread.start()

    def call_ollama(self, instructions):
        level = self.level_var.get()
        language = self.language_var.get()
        framework = self.framework_var.get()
        framework_line = (
            f"Use the {framework} framework/library conventions and idioms where applicable.\n\n"
            if framework and framework != "None"
            else ""
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
            response = requests.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "prompt": full_prompt, "stream": False},
                timeout=300,
                proxies={"http": None, "https": None},  # bypass system proxy for localhost calls
            )
            response.raise_for_status()
            data = response.json()
            output = data.get("response", "No response received.")
        except requests.exceptions.ConnectionError as e:
            output = (
                "ERROR: Could not connect to Ollama at localhost:11434.\n\n"
                f"Raw error detail:\n{e}\n\n"
                "Make sure Ollama is running. Open a terminal and run:\n"
                "    ollama serve\n"
                "(or just open the Ollama app, which starts the server automatically)\n\n"
                f"Then make sure the model is pulled:\n    ollama pull {MODEL_NAME}"
            )
        except requests.exceptions.HTTPError as e:
            output = (
                f"ERROR: Ollama responded but returned an error.\n\n"
                f"Status code: {response.status_code}\n"
                f"Response body: {response.text}\n\n"
                f"This usually means the model name '{MODEL_NAME}' is not pulled.\n"
                f"Run: ollama pull {MODEL_NAME}"
            )
        except Exception as e:
            output = f"ERROR ({type(e).__name__}): {e}"

        self.root.after(0, lambda: self.finish(output))

    def finish(self, output):
        self.set_result(output)
        self.run_btn.config(state="normal", text="▲ Run")


if __name__ == "__main__":
    root = tk.Tk()
    app = CodeAssistantApp(root)
    root.mainloop()