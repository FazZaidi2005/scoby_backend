from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, field_validator, UUID4
from dotenv import load_dotenv

from fastapi import UploadFile, File
import asyncpg
import openai

from MDI import router as mdi_router
from models import TokenRequest, TokenResponse, Country, State, Address, FileInfo, DosespotInfo, PartnerInfo, Metafield, PatientAddress, PatientRequest, PatientResponse, CaseStatus, ClinicianPhoto, Clinician, CaseAssignment, PartnerCustomization, PartnerAddress, Tag, CasePrescription, CaseQuestion, CaseRequest, CaseResponse, QuestionnaireMatchRequest, QuestionnaireMatchResponse, ChatMessage, QuestionnaireMatchResult, ChatSession, ChatRequest, ChatResponse, MultipleChoiceQuestion, BooleanQuestion, SingleChoiceQuestion, IntegerQuestion, StringQuestion, TextQuestion, InformationalQuestion

from database import get_db_connection, create_session_in_db, update_session_questionnaire, mark_questionnaire_complete, save_questionnaire_answer, get_questionnaire_answers, add_chat_message, get_session_from_db, get_chat_messages_from_db, generate_session_id, get_or_create_session, get_unanswered_questions, update_questionnaire_answer, get_questionnaire_answers_for_session
from MDI import match_questionnaire_to_query, get_questionnaire_questions, get_simplified_questionnaires, get_simplified_questionnaire

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="scoby_backend", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now; I'll restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mdi_router)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that handles both initial questions and user responses.
    """
    try:
        # Get or create session
        session = await get_or_create_session(request.session_id)
        session_created = request.session_id is None

        # Add user message to chat history
        if request.message:
            await add_chat_message(session.session_id, "user", request.message)

        # Use GPT-5 to handle the conversation flow
        try:
            # Build conversation context
            chat_history = await get_chat_messages_from_db(session.session_id)

            messages = [
                {
                    "role": "system",
                    "content": """You are a medical intake assistant that helps patients complete medical forms through natural conversation. Your job is to:

1. Greet patients warmly and understand their complaint
2. Identify the right medical form/questionnaire for their issue
3. Ask only the next required question (one at a time, friendly tone)
4. Normalize answers (yes/no → true/false, "2 days" → 2, dates → ISO)
5. Spot red flags and stop/escalate when needed
6. Know when the form is complete and trigger submission
7. Write a short patient message and concise doctor summary

You have access to these tools:
- update_session_questionnaire(questionnaire_id): Set the chosen form
- get_simplified_questionnaires: Get available forms
- get_simplified_questionnaire(questionnaire_id): Get full form schema
- save_questionnaire_answer(question_text, answer, question_id, answer_type): Save each answer
- mark_questionnaire_complete(): Submit the completed form

IMPORTANT: After assigning a questionnaire with update_session_questionnaire(), you should:
1. Get the questionnaire schema using get_simplified_questionnaire()
2. Start asking the first question from the questionnaire
3. Do NOT call update_session_questionnaire() again for the same session

Always be friendly, professional, and prioritize patient safety. If you spot red flags/severe symptoms, pause intake and provide safe next steps."""
                }
            ]

            # Add prior chat (user/assistant) to messages
            for msg in chat_history:
                messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })

            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise Exception("OPENAI_API_KEY not set")

            client = openai.OpenAI(api_key=openai_api_key)

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "update_session_questionnaire",
                        "description": "Set the chosen questionnaire/form for the conversation",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "questionnaire_id": {"type": "string"}
                            },
                            "required": ["questionnaire_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_simplified_questionnaires",
                        "description": "Get a quick catalog of available questionnaires/forms",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_simplified_questionnaire",
                        "description": "Get the full schema for a specific questionnaire",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "questionnaire_id": {"type": "string"}
                            },
                            "required": ["questionnaire_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "save_questionnaire_answer",
                        "description": "Save a patient's answer to a specific question",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question_text": {"type": "string"},
                                "answer": {"type": "string"},
                                "question_id": {"type": "string"},
                                "answer_type": {"type": "string"}
                            },
                            "required": ["question_text", "question_id", "answer_type"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mark_questionnaire_complete",
                        "description": "Mark the questionnaire as complete and submit for doctor review",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
            ]

            # ===== Core tool-calling loop =====
            while True:
                response = client.chat.completions.create(
                    model="gpt-5",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                message = response.choices[0].message

                # Append the assistant message (may contain tool_calls)
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    **({"tool_calls": message.tool_calls} if getattr(message, "tool_calls", None) else {})
                })

                tool_calls = getattr(message, "tool_calls", None)

                # If no tool calls, we have the final assistant reply
                if not tool_calls:
                    ai_response = message.content or "I'm here to help with your medical intake. How can I assist you today?"
                    # Persist the final assistant reply to DB
                    await add_chat_message(session.session_id, "assistant", ai_response)
                    return ChatResponse(
                        message=ai_response,
                        session_id=session.session_id,
                        session_created=session_created
                    )

                # Execute each requested tool and append role="tool" results
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments or "{}")

                    try:
                        if function_name == "update_session_questionnaire":
                            await update_session_questionnaire(session.session_id, function_args["questionnaire_id"])
                            # keep session updated in memory if your Session model has this attribute
                            if hasattr(session, "questionnaire_id"):
                                session.questionnaire_id = function_args["questionnaire_id"]
                            tool_result = {
                                "status": "success",
                                "message": "Questionnaire assigned successfully",
                                "questionnaire_id": function_args["questionnaire_id"],
                                "session_id": str(session.session_id)
                            }

                        elif function_name == "get_simplified_questionnaires":
                            tool_result = await get_simplified_questionnaires()

                        elif function_name == "get_simplified_questionnaire":
                            # NOTE: uses questionnaire_id (not question_id)
                            tool_result = await get_simplified_questionnaire(function_args["questionnaire_id"])

                        elif function_name == "save_questionnaire_answer":
                            await save_questionnaire_answer(
                                session.session_id,
                                function_args["question_text"],
                                function_args.get("answer"),
                                function_args["question_id"],
                                function_args["answer_type"]
                            )
                            tool_result = {
                                "status": "success",
                                "message": "Answer saved successfully",
                                "question_id": function_args["question_id"]
                            }

                        elif function_name == "mark_questionnaire_complete":
                            await mark_questionnaire_complete(session.session_id)
                            tool_result = {
                                "status": "success",
                                "message": "Questionnaire completed and submitted for doctor review",
                                "session_id": str(session.session_id),
                                "completed_at": datetime.utcnow().isoformat()
                            }

                        else:
                            tool_result = {"error": f"Unknown tool: {function_name}"}

                    except Exception as e:
                        tool_result = {"error": f"{function_name} failed: {str(e)}"}

                    # Append the tool result with the matching tool_call_id
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })
            # ===== End loop =====

        except Exception as e:
            print(f"Error in GPT-5 chat: {str(e)}")
            fallback_response = "I'm having trouble processing your request right now. Please try again or contact support."
            await add_chat_message(session.session_id, "assistant", fallback_response)
            return ChatResponse(
                message=fallback_response,
                session_id=session.session_id,
                session_created=session_created
            )

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)