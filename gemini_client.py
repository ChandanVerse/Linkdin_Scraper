from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

_client = None
_chat = None  # reused within one job application

SYSTEM_INSTRUCTION = """You are an AI assistant helping Chandan Tavane auto-fill job application forms on LinkedIn.
You must answer each form question accurately based on his resume and profile below.

=== RESUME ===
CHANDAN TAVANE
Phone: +91 9845105667 | Email: chandantavane99@gmail.com
Location: Bengaluru, India

PROFESSIONAL SUMMARY:
AI/ML Engineer and Data Scientist specializing in Computer Vision and NLP. Built production ML
systems achieving 94% accuracy with PyTorch, vector databases, and AWS. Expertise in RAG
architectures, semantic search, and scalable ML pipelines using FastAPI, Docker, and distributed systems.

EDUCATION:
Bachelor of Engineering in Computer Science (2021-2025)
Visvesvaraya Technological University (VTU), CGPA: 8.0

WORK EXPERIENCE:
Data Science Intern at Vosmos (Kestone) — Sep 2025 to Dec 2025 (4 months)
- Developed face recognition systems using InsightFace, PyTorch, and GPU inference (CUDA, ONNX),
  improving accuracy from 78% to 94% with 150-200ms search times.
- Built vector-search pipelines with Pinecone for face embeddings and cosine-similarity matching.
- Designed async ML pipelines using Celery + Redis for scalable batch processing.
- Architected hybrid storage with MongoDB (metadata) and Pinecone (embeddings).
- Integrated ML components into FastAPI microservices with RESTful APIs.

PROJECTS:
1. Legal Judgement Retrieval & Research System (Nov 2025 - Jan 2026)
   - RAG-based semantic search across Indian judgments using Pinecone + AWS DynamoDB/S3
   - Chat interface with Google Gemini and function calling, deployed on AWS EC2
   - Tech: Python, FastAPI, Sentence Transformers, Pinecone, DynamoDB, S3, Next.js, Docker

2. Workout Planner (Aug 2025 - Oct 2025)
   - Recommendation engine using Sentence-BERT embeddings and cosine-similarity
   - Containerized FastAPI microservices with JWT auth, PostgreSQL, Streamlit UI
   - Tech: Python, FastAPI, Sentence-BERT, PostgreSQL, Docker, AWS ECS, RDS

3. Twitter Sentiment Analysis using NLP (May 2025 - Jul 2025)
   - Bi-directional LSTM, BERT, and DistilBERT models achieving 90% accuracy
   - Tech: Python, PyTorch, TensorFlow, Hugging Face Transformers, BERT, Scikit-learn

TECHNICAL SKILLS:
- Languages: Python, C++, C, JavaScript, SQL
- ML/DL: PyTorch, TensorFlow, Scikit-learn, Keras, NumPy, Pandas
- NLP/LLM: Transformers, BERT, LangChain, LlamaIndex, Sentence-BERT, Hugging Face
- Computer Vision: InsightFace, OpenCV, CUDA, ONNX Runtime
- Vector DBs: Pinecone, Qdrant, FAISS, ChromaDB
- Cloud & DevOps: AWS (EC2, S3, Lambda, ECS, RDS, DynamoDB), Docker, Git
- Backend: FastAPI, Node.js, REST APIs, Celery, Redis
- Databases: PostgreSQL, MongoDB, MySQL

CERTIFICATIONS:
- Machine Learning A-Z: AI, Python (Udemy, 2024)
- NLP with Classification (Coursera/DeepLearning.AI, 2025)
- Agentic AI (DeepLearning.AI, 2025)
- AWS Cloud Technical Essentials (Coursera/AWS, 2025)

=== KEY FACTS FOR FORM FILLING ===
- Date of birth: 10/01/2003 (dd/mm/yyyy)
- Fresher (0 years full-time experience, 4-month internship)
- Immediately available (0 days notice period)
- Current CTC: 0 (fresher)
- Expected CTC: 4,00,000 (4 LPA) — if a numeric field, use 400000
- Authorized to work in India, does NOT need visa sponsorship
- Willing to relocate and commute
- Gender: Male
- Preferred roles: Data Scientist, ML Engineer, AI Engineer, Python Developer, NLP Engineer
- LinkedIn: https://www.linkedin.com/in/chandantavane
- GitHub: https://github.com/ChandanVerse

=== RULES ===
1. Answer ONLY with the value to fill in — no explanation, no quotes, no extra text.
2. If options are provided, reply with the EXACT text of the best matching option.
3. For yes/no questions about willingness, authorization, relocation, commute → answer "Yes".
4. For sponsorship or visa requirement questions → answer "No".
5. For experience questions → answer "0" or pick the lowest/entry-level option.
6. For current salary/CTC → "0". For expected salary/CTC → "400000" (numeric) or "4,00,000" (text).
7. For skills/cover-letter fields → write a brief, relevant answer using resume details.
8. Keep all answers professional, concise, and truthful based on the resume above.
"""


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            return None
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def start_chat(job_context=None):
    """Start a new chat session for one job application.

    Call this once before filling a job's form. All subsequent ask_gemini()
    calls reuse this session, so the resume context is sent only once.
    """
    global _chat
    client = _get_client()
    if client is None:
        _chat = None
        return

    _chat = client.chats.create(
        model=GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    # Send job context as the first message so it's in history
    if job_context:
        title = job_context.get("title", "N/A")
        company = job_context.get("company", "N/A")
        try:
            _chat.send_message(
                f"I am now applying for: {title} at {company}. "
                "I will ask you form questions one by one. Reply with only the answer each time."
            )
        except Exception:
            pass


def end_chat():
    """End the current chat session (between job applications)."""
    global _chat
    _chat = None


def ask_gemini(question, options=None, job_context=None):
    """Ask Gemini to answer a form question.

    If a chat session is active (via start_chat), uses it — the resume
    context was already sent once and is reused across all questions for
    the same job. Falls back to a one-shot call if no session exists.

    Args:
        question: The form field label / question text.
        options: List of option strings (for dropdowns/radio buttons).
        job_context: Dict with 'title' and 'company' for context.

    Returns:
        Answer string, or None on error.
    """
    prompt = f"Form question: {question}\n"
    if options:
        prompt += f"Available options: {', '.join(options)}\n"
        prompt += "Reply with ONLY the exact text of the best matching option."
    else:
        prompt += "Reply with ONLY the answer to fill in the field."

    # ── Chat session path (token-efficient) ──
    if _chat is not None:
        try:
            response = _chat.send_message(prompt)
            answer = response.text.strip().strip('"').strip("'")
            return answer if answer else None
        except Exception as e:
            print(f"    [WARN] Gemini chat error: {e}")
            return None

    # ── Fallback: one-shot call (if no session) ──
    client = _get_client()
    if client is None:
        return None

    full_prompt = SYSTEM_INSTRUCTION + "\n"
    if job_context:
        full_prompt += (
            f"Currently applying for: {job_context.get('title', 'N/A')} "
            f"at {job_context.get('company', 'N/A')}\n\n"
        )
    full_prompt += prompt

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt,
        )
        answer = response.text.strip().strip('"').strip("'")
        return answer if answer else None
    except Exception as e:
        print(f"    [WARN] Gemini API error: {e}")
        return None
