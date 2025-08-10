import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import UUID4
import asyncpg
from models import ChatMessage, ChatSession

# Database connection
async def get_db_connection():
    """Get a database connection"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL not found in environment variables")
    return await asyncpg.connect(database_url)

# Database helper functions
async def create_session_in_db(session_id: UUID4) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            "INSERT INTO sessions (session_id) VALUES ($1)",
            session_id
        )
    finally:
        await conn.close()

async def update_session_questionnaire(session_id: UUID4, questionnaire_id: str) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE sessions SET questionnaire_id = $1, last_updated = now() WHERE session_id = $2",
            questionnaire_id, session_id
        )
    finally:
        await conn.close()

async def mark_questionnaire_complete(session_id: UUID4) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE sessions SET is_questionnaire_complete = true, last_updated = now() WHERE session_id = $1",
            session_id
        )
    finally:
        await conn.close()

async def save_questionnaire_answer(session_id: UUID4, question_text: str, answer: Optional[str], question_id: str, answer_type: str) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            "INSERT INTO questionnaire_answers (session_id, question_id, question_text, answer, type) VALUES ($1, $2, $3, $4, $5)",
            session_id, question_id, question_text, answer, answer_type
        )
    finally:
        await conn.close()

async def get_questionnaire_answers(session_id: UUID4) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            "SELECT question_id, answer FROM questionnaire_answers WHERE session_id = $1",
            session_id
        )
        return [{"question_id": row["question_id"], "answer": row["answer"]} for row in rows]
    finally:
        await conn.close()

async def add_chat_message(session_id: UUID4, role: str, content: str) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES ($1, $2, $3)",
            session_id, role, content
        )
    finally:
        await conn.close()

async def get_session_from_db(session_id: UUID4) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT session_id, questionnaire_id, created_at, last_updated, is_questionnaire_complete FROM sessions WHERE session_id = $1",
            session_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_chat_messages_from_db(session_id: UUID4) -> List[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            "SELECT role, content, timestamp FROM chat_messages WHERE session_id = $1 ORDER BY timestamp",
            session_id
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_unanswered_questions(session_id: UUID4) -> List[str]:
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT question_id
            FROM questionnaire_answers
            WHERE session_id = $1 AND answer IS NULL
            """,
            session_id
        )
        return [row['question_id'] for row in rows]
    finally:
        await conn.close()

async def update_questionnaire_answer(session_id: UUID4, question_id: str, answer: Optional[str]) -> None:
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE questionnaire_answers
            SET answer = $1
            WHERE session_id = $2 AND question_id = $3
            """,
            answer, session_id, question_id
        )
    finally:
        await conn.close()

async def get_questionnaire_answers_for_session(session_id: UUID4) -> Dict[str, Any]:
    """Get all questionnaire answers for a session as a dict mapping question_id to answer with timestamp"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            "SELECT question_id, answer, created_at FROM questionnaire_answers WHERE session_id = $1 ORDER BY created_at",
            session_id
        )
        return {row["question_id"]: {"answer": row["answer"], "created_at": row["created_at"]} for row in rows}
    finally:
        await conn.close()

def generate_session_id() -> UUID4:
    """Generate a unique session ID"""
    return uuid.uuid4()

async def get_or_create_session(session_id: Optional[str] = None) -> ChatSession:
    if session_id:
        db_session = await get_session_from_db(session_id)
        if db_session:
            messages_data = await get_chat_messages_from_db(session_id)
            messages = [
                ChatMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg["timestamp"].isoformat()
                ) for msg in messages_data
            ]
            return ChatSession(
                session_id=db_session["session_id"],
                messages=messages,
                created_at=db_session["created_at"].isoformat(),
                last_updated=db_session["last_updated"].isoformat(),
                questionnaire_id=db_session["questionnaire_id"]
            )
    new_session_id = generate_session_id()
    await create_session_in_db(new_session_id)
    return ChatSession(
        session_id=new_session_id,
        messages=[],
        created_at=datetime.utcnow().isoformat(),
        last_updated=datetime.utcnow().isoformat(),
        questionnaire_id=None
    ) 