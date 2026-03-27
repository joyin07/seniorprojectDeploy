"""
DATABASE SETUP - MongoDB
- Uses MongoDB Atlas
- pymongo is the library that talks to MongoDB
- Users collection stores:
    - _id: auto-generated MongoDB ObjectId
    - clerk_id: the ID from Clerk (links to their auth system)
    - university_id: university identifier (e.g., "ufl")
    - canvas_user_id: user's Canvas ID
    - first_name: user's first name from Clerk
    - last_name: user's last name from Clerk
    - email: user's email from Clerk
    - canvas_token: user's Canvas API token
    - gemini_token: user's Gemini API key
    - created_at: when user first logged in
    - updated_at: when user was last updated
- Course Quizzes collection stores:
    - _id: auto-generated MongoDB ObjectId
    - university_id: university identifier (e.g., "ufl")
    - course_id: Canvas course ID (int)
    - canvas_quiz_id: Canvas quiz ID after publishing (null until published)
    - title: quiz title
    - description: quiz description
    - quiz_type: "practice_quiz" | "assignment" | "graded_survey" | "survey"
    - points_per_question: points per question (default 1)
    - question_count: number of questions
    - questions: list of question dicts (Gemini format)
    - status: "generated_pending_review" | "approved_pending_publish" | "published" | "publish_failed"
    - created_at: when quiz was generated
    - updated_at: when quiz was last updated
    - generation_metadata: source files, question types, difficulty, model used
- get_db(): returns the database instance
- user_has_tokens(): checks if user completed onboarding
"""

from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "quiz_generator")

client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000
)

db = client[DB_NAME]

# collections
users_collection = db["users"]
course_quizzes_collection = db["course_quizzes"]


def init_db():
    """Create indexes - call this after server starts"""
    try:
        users_collection.create_index("clerk_id", unique=True)
        course_quizzes_collection.create_index("course_id")
    except Exception as e:
        print(f"Index creation error (may already exist): {e}")


def get_db():
    return db


def get_or_create_user(clerk_id: str, user_data: dict = None) -> dict:
    """Find user by clerk_id, or create if doesn't exist"""
    user = users_collection.find_one({"clerk_id": clerk_id})
    
    if not user:
        user = {
            "clerk_id": clerk_id,
            "university_id": None,
            "canvas_user_id": None,
            "first_name": user_data.get("first_name") if user_data else None,
            "last_name": user_data.get("last_name") if user_data else None,
            "email": user_data.get("email") if user_data else None,
            "canvas_token": None,
            "gemini_token": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = users_collection.insert_one(user)
        user["_id"] = result.inserted_id
    elif user_data:
        # Update existing user with latest info from Clerk
        users_collection.update_one(
            {"clerk_id": clerk_id},
            {"$set": {
                "email": user_data.get("email"),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
                "updated_at": datetime.utcnow()
            }}
        )
        user = users_collection.find_one({"clerk_id": clerk_id})
    
    return user


def update_user(clerk_id: str, update_data: dict):
    """Update user document"""
    update_data["updated_at"] = datetime.utcnow()
    users_collection.update_one(
        {"clerk_id": clerk_id},
        {"$set": update_data}
    )


def user_has_tokens(user: dict) -> bool:
    """Check if user has both required tokens (completed onboarding)"""
    return (
        user.get("canvas_token") is not None and
        user.get("gemini_token") is not None
    )


def save_course_quiz(quiz_doc: dict) -> str:
    """Insert a new course_quizzes document. Returns the inserted _id as a string."""
    result = course_quizzes_collection.insert_one(quiz_doc)
    return str(result.inserted_id)


def get_course_quiz(doc_id: str) -> dict | None:
    """Fetch a course_quizzes document by its MongoDB _id string."""
    return course_quizzes_collection.find_one({"_id": ObjectId(doc_id)})


def update_course_quiz(doc_id: str, update_data: dict):
    """Update a course_quizzes document by its MongoDB _id string."""
    update_data["updated_at"] = datetime.utcnow()
    course_quizzes_collection.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": update_data}
    )