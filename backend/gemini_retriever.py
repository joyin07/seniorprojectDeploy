import os
import json
import re
from datetime import datetime
from google import genai
from dotenv import load_dotenv
import httpx
import io
from database import save_course_quiz

load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"
client = genai.Client(api_key=os.getenv("GEMINI_KEY"))

QUIZ_PROMPT = """You are an expert educator and quiz creator. From all of the provided course materials combined, create exactly 5 challenging multiple-choice practice quiz questions that test deep understanding of the most important concepts.

Return ONLY a valid JSON object with no extra text, markdown code fences, or explanation. Use this exact format:

{
  "questions": [
    {
      "question": "The full question text here?",
      "options": {
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      },
      "answer": "A",
      "rationale": "Brief explanation of why this answer is correct."
    }
  ]
}

Rules:
- Exactly 5 questions total across all provided materials
- Each question must have exactly 4 options (A, B, C, D)
- The answer field must be a single letter matching one of the option keys
- Questions should be substantive and require understanding, not just recall
- No markdown, no code fences, no text outside the JSON object"""

"""
    Generate a multiple-choice quiz from a list of Canvas file URLs and save it to MongoDB.

    Args:
        files: List of dicts with keys: 'url', 'display_name', 'content_type', optionally 'id'
        canvas_token: Canvas API token used to authenticate file downloads
        course_id: Canvas course ID the quiz belongs to
        university_id: University identifier (e.g. "ufl")
        title: Quiz title stored in MongoDB
        description: Quiz description stored in MongoDB
        quiz_type: Canvas quiz type (default "practice_quiz")
        points_per_question: Points per question (default 1.0)
        generation_metadata: Dict with optional fields:
            source_prev_quiz_ids, question_types_requested, difficulty

    Returns:
        Dict with 'quiz_doc_id' (MongoDB _id string), 'question_count', and 'questions' list

    Raises:
        ValueError: If files list is empty or a file entry is missing a URL
        RuntimeError: If any download, Gemini upload, or generation step fails
    """
def generate_quiz_from_files(
    files: list,
    canvas_token: str,
    course_id: int = None,
    university_id: str = None,
    title: str = "Generated Quiz",
    description: str = "",
    quiz_type: str = "practice_quiz",
    points_per_question: float = 1.0,
    generation_metadata: dict = None,
) -> dict:
    if not files:
        raise ValueError("At least one file is required to generate a quiz.")

    headers = {"Authorization": f"Bearer {canvas_token}"}
    uploaded_files = []

    try:
        # Download each file from Canvas and upload to Gemini
        for i, file_info in enumerate(files):
            url = file_info.get("url")
            display_name = file_info.get("display_name", f"file_{i}")
            content_type = file_info.get("content_type", "application/pdf")

            if not url:
                raise ValueError(f"File at index {i} is missing a 'url'.")

            print(f"Downloading file {i + 1}/{len(files)}: {display_name}")
            try:
                with httpx.Client(follow_redirects=True, timeout=30.0) as h_client:
                    dl_response = h_client.get(url, headers=headers)
            except httpx.TimeoutException:
                raise RuntimeError(f"Timed out downloading '{display_name}' from Canvas.")
            except httpx.RequestError as e:
                raise RuntimeError(f"Network error downloading '{display_name}': {str(e)}")

            if dl_response.status_code != 200:
                raise RuntimeError(
                    f"Failed to download '{display_name}' from Canvas "
                    f"(HTTP {dl_response.status_code})."
                )

            print(f"Uploading '{display_name}' to Gemini...")
            file_io = io.BytesIO(dl_response.content)
            file_io.seek(0)

            try:
                file_upload = client.files.upload(
                    file=file_io,
                    config={"mime_type": content_type, "display_name": display_name}
                )
                uploaded_files.append(file_upload)
            except Exception as e:
                raise RuntimeError(f"Failed to upload '{display_name}' to Gemini: {str(e)}")

        # Generate quiz: pass all uploaded files + the structured prompt
        print(f"Generating quiz from {len(uploaded_files)} file(s)...")
        contents = uploaded_files + [QUIZ_PROMPT]

        try:
            gemini_response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config={"response_mime_type": "application/json"}
            )
        except Exception as e:
            raise RuntimeError(f"Gemini content generation failed: {str(e)}")

        # Parse the JSON response
        raw_text = gemini_response.text.strip()

        # Strip markdown code fences in case Gemini wraps the output anyway
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        raw_text = raw_text.strip()

        try:
            quiz_data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Gemini returned invalid JSON: {str(e)}. "
                f"Raw response preview: {raw_text[:300]}"
            )

        if "questions" not in quiz_data or not isinstance(quiz_data["questions"], list):
            raise RuntimeError(
                "Gemini response is missing the 'questions' field or it is not a list."
            )

        # Build and save the course_quizzes document
        meta = generation_metadata or {}
        now = datetime.utcnow()
        quiz_doc = {
            "university_id": university_id,
            "course_id": course_id,
            "canvas_quiz_id": None,
            "title": title,
            "description": description,
            "quiz_type": quiz_type,
            "points_per_question": points_per_question,
            "question_count": len(quiz_data["questions"]),
            "questions": quiz_data["questions"],
            "status": "generated_pending_review",
            "created_at": now,
            "updated_at": now,
            "generation_metadata": {
                "source_file_ids": [f["id"] for f in files if "id" in f],
                "source_prev_quiz_ids": meta.get("source_prev_quiz_ids", []),
                "question_types_requested": meta.get("question_types_requested", {}),
                "difficulty": meta.get("difficulty", "medium"),
                "model": GEMINI_MODEL,
            },
        }

        quiz_doc_id = save_course_quiz(quiz_doc)

        return {
            "quiz_doc_id": quiz_doc_id,
            "question_count": len(quiz_data["questions"]),
            "questions": quiz_data["questions"],
        }

    finally:
        # Best-effort cleanup: delete uploaded files from Gemini's servers
        for uploaded in uploaded_files:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass


if __name__ == "__main__":
    import os
    test_files = [
        {
            "url": "https://ufl.instructure.com/files/105079458/download?download_frd=1&verifier=fLAcntrkIOwpDeBbldHFSg8D8lcnWTz2zWt0Ffns",
            "display_name": "1 - Algorithmic Analysis.pdf",
            "content_type": "application/pdf"
        }
        # {
        #     "url": "https://ufl.instructure.com/files/103763467/download?download_frd=1&verifier=OnPPgAaoTvQDyr0GUP7Vhm0CsxuCFK34koEHkg1w",
        #     "display_name": "c_review.pdf",
        #     "content_type": "application/pdf"
        # }
    ]
    result = generate_quiz_from_files(test_files, os.getenv("CANVAS_TOKEN"))
    print("\n--- GENERATED QUIZ ---")
    print(json.dumps(result, indent=2))
