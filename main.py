from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Streaming chat endpoint that provides real-time responses.
    """
    print(f"Starting streaming chat for session: {request.session_id}")
    
    async def generate_stream():
        try:
            # Get or create session
            session = await get_or_create_session(request.session_id)
            session_created = request.session_id is None
            print(f"Session created/retrieved: {session.session_id}")

            # Send session ID immediately
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': str(session.session_id)})}\n\n"

            # Add user message to chat history
            if request.message:
                await add_chat_message(session.session_id, "user", request.message)
                print(f"User message added: {request.message[:50]}...")

            # Build conversation context
            chat_history = await get_chat_messages_from_db(session.session_id)
            print(f"Chat history loaded: {len(chat_history)} messages")

            messages = [
                {
                    "role": "system",
                    "content": """You are a medical intake assistant that helps patients through natural conversation. Your job is to:

1. Greet patients warmly and understand their complaint
2. Ask medical questions one at a time in a friendly, professional tone
3. Normalize answers (yes/no → true/false, "2 days" → 2, dates → ISO)
4. Spot red flags and stop/escalate when needed
5. Complete the intake when all necessary information is gathered

You have access to these tools:
- update_session_questionnaire(questionnaire_id): Set the chosen form
- get_simplified_questionnaires: Get available forms
- get_simplified_questionnaire(questionnaire_id): Get full form schema
- save_questionnaire_answer(question_text, answer, question_id, answer_type): Save each answer
- mark_questionnaire_complete(): Submit the completed form

CRITICAL: NEVER mention questionnaires, forms, tools, or any backend processes. Talk like a real medical professional having a conversation with a patient.

Your responses should be:
- Direct and focused on the patient's symptoms
- Professional but warm and caring
- One question at a time
- Free of any technical jargon or process explanations
- Natural questions without instructing patients on how to answer

For example:
❌ WRONG: "I'll check what questionnaires are available so I can choose the right one for UTI symptoms. Now I'll load that questionnaire and start with the first question. I'll save your answers as we go."

❌ WRONG: "Are you having any of the following right now: fever over 100.4°F (38°C), severe back or side pain, nausea/vomiting, confusion, or feeling very ill? Please answer yes or no."

✅ CORRECT: "I'm sorry you're dealing with that—I'll help get the right info to your clinician. Before we start, I need to make sure you're safe. Are you having any of the following right now: fever over 100.4°F (38°C), severe back or side pain, nausea/vomiting, confusion, or feeling very ill?"

Always prioritize patient safety and be direct with your questions. Let patients answer naturally without telling them how to format their responses."""
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

            # Use streaming for the initial response
            print("Starting OpenAI streaming request...")
            stream = client.chat.completions.create(
                model="gpt-5",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True
            )

            full_response = ""
            tool_calls = []
            chunk_count = 0
            
            # Handle the streaming response properly
            try:
                for chunk in stream:
                    chunk_count += 1
                    if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            # Filter out any tool-related content or internal processing
                            if not any(keyword in content.lower() for keyword in [
                                'questionnaire_id', 'status', 'tool_id', 'question_text', 
                                'answer_type', 'executed', 'call_', 'uti_screen'
                            ]):
                                full_response += content
                                # Send the chunk as a data event with proper SSE formatting
                                chunk_data = f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                                print(f"Sending chunk: {repr(content)} -> {repr(chunk_data)}")
                                yield chunk_data
                        
                        if hasattr(chunk.choices[0].delta, 'tool_calls') and chunk.choices[0].delta.tool_calls:
                            for tool_call in chunk.choices[0].delta.tool_calls:
                                if tool_call.function:
                                    if tool_call.function.name:
                                        # Start of a new tool call
                                        tool_calls.append({
                                            'id': tool_call.id,
                                            'function': {'name': tool_call.function.name, 'arguments': ''},
                                            'type': 'function'
                                        })
                                        print(f"Tool call started: {tool_call.function.name}")
                                    if tool_call.function.arguments:
                                        # Append arguments to the current tool call
                                        current_tool = tool_calls[-1]
                                        current_tool['function']['arguments'] += tool_call.function.arguments
            except Exception as e:
                print(f"Error during streaming: {str(e)}")
                # Send error event and continue
                yield f"data: {json.dumps({'type': 'error', 'error': 'Streaming error occurred'})}\n\n"

            print(f"Initial streaming complete. Chunks: {chunk_count}, Tool calls: {len(tool_calls)}")

            # If we have tool calls, execute them and continue the conversation
            if tool_calls:
                # Send tool execution start
                yield f"data: {json.dumps({'type': 'tool_execution_start'})}\n\n"
                
                # Execute tools and continue conversation
                for tool_call in tool_calls:
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'] or "{}")

                    try:
                        if function_name == "update_session_questionnaire":
                            await update_session_questionnaire(session.session_id, function_args["questionnaire_id"])
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

                    # Send tool result
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': function_name, 'result': tool_result})}\n\n"

                # Continue conversation with tool results
                # Convert our tool_calls format to OpenAI's expected format
                openai_tool_calls = []
                for tool_call in tool_calls:
                    openai_tool_calls.append({
                        "id": tool_call['id'],
                        "type": "function",
                        "function": {
                            "name": tool_call['function']['name'],
                            "arguments": tool_call['function']['arguments']
                        }
                    })
                
                print(f"Converting tool calls to OpenAI format: {len(openai_tool_calls)} tools")
                for tool_call in openai_tool_calls:
                    print(f"  - {tool_call['function']['name']}: {tool_call['function']['arguments'][:100]}...")
                
                messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "tool_calls": openai_tool_calls
                })

                for tool_call in tool_calls:
                    # Find the corresponding tool result for this tool call
                    tool_result_for_call = None
                    for executed_tool in tool_calls:
                        if executed_tool['id'] == tool_call['id']:
                            # We need to reconstruct the tool result since it's not stored per tool call
                            tool_result_for_call = {"status": "executed", "tool_id": tool_call['id']}
                            break
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(tool_result_for_call or {"status": "unknown"})
                    })

                # Get final response after tool execution
                final_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    stream=True
                )

                try:
                    for chunk in final_response:
                        if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            # Filter out any tool-related content or internal processing
                            if not any(keyword in content.lower() for keyword in [
                                'questionnaire_id', 'status', 'tool_id', 'question_text', 
                                'answer_type', 'executed', 'call_', 'uti_screen'
                            ]):
                                full_response += content
                                chunk_data = f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                                print(f"Sending final chunk: {repr(content)} -> {repr(chunk_data)}")
                                yield chunk_data
                except Exception as e:
                    print(f"Error during final response streaming: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Final response streaming error'})}\n\n"

            # Save the final response to database
            if full_response:
                await add_chat_message(session.session_id, "assistant", full_response)
                print(f"Final response saved to database: {len(full_response)} characters")

            # Send completion signal
            print("Sending completion signal")
            yield f"data: {json.dumps({'type': 'complete', 'session_created': session_created})}\n\n"

        except Exception as e:
            print(f"Error in streaming chat: {str(e)}")
            error_msg = "I'm having trouble processing your request right now. Please try again or contact support."
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if present
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)