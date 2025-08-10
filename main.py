from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uuid
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
from MDI import match_questionnaire_to_query, get_questionnaire_questions

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

async def process_user_answer(question, user_answer):
    """
    Process and validate user answer based on question type.
    Returns standardized answer format for database storage.
    """
    question_type = question.get("type", "")
    options = question.get("options", [])
    
    # Clean the user answer
    cleaned_answer = user_answer.strip().lower() if user_answer else ""
    
    try:
        if question_type == "boolean":
            # Convert Yes/No to 1/0
            if cleaned_answer in ["yes", "true", "1", "y", "yeah", "yep", "sure", "ok", "okay"]:
                return "1"
            elif cleaned_answer in ["no", "false", "0", "n", "nope", "nah", "not really"]:
                return "0"
            else:
                # Try to extract yes/no from longer responses
                if any(word in cleaned_answer for word in ["yes", "true", "affirmative", "correct", "right", "that's right", "correct"]):
                    return "1"
                elif any(word in cleaned_answer for word in ["no", "false", "negative", "incorrect", "wrong", "that's wrong", "not"]):
                    return "0"
                else:
                    # For unclear responses, try to be smart about context
                    if "don't" in cleaned_answer or "do not" in cleaned_answer or "never" in cleaned_answer:
                        return "0"
                    elif "do" in cleaned_answer and "not" not in cleaned_answer:
                        return "1"
                    else:
                        raise ValueError(f"Invalid boolean answer: {user_answer}. Expected Yes/No or 1/0.")
        
        elif question_type == "multiple_option":
            # For multiple choice, handle comma-separated or array of selections
            if isinstance(user_answer, list):
                # If it's already a list, validate each option
                selected_options = user_answer
            elif "," in cleaned_answer:
                # Handle comma-separated values
                selected_options = [opt.strip() for opt in cleaned_answer.split(",")]
            else:
                # Single selection
                selected_options = [cleaned_answer]
            
            # Validate all selected options
            option_texts = [opt.get("option", "").lower() for opt in options]
            valid_selections = []
            
            for selection in selected_options:
                if selection in option_texts:
                    valid_selections.append(selection)
                else:
                    # Try to find partial matches
                    for option in option_texts:
                        if option in selection or selection in option:
                            valid_selections.append(option)
                            break
                        # Handle common variations
                        if option.replace(" ", "") == selection.replace(" ", ""):
                            valid_selections.append(option)
                            break
            
            if not valid_selections:
                raise ValueError(f"Invalid options: {user_answer}. Available options: {[opt.get('option') for opt in options]}")
            
            # Return as comma-separated string for database storage
            return ",".join(valid_selections)
        
        elif question_type == "single_option":
            # For single choice, same logic as multiple choice
            option_texts = [opt.get("option", "").lower() for opt in options]
            if cleaned_answer in option_texts:
                return cleaned_answer
            else:
                # Try to find partial matches
                for option in option_texts:
                    if option in cleaned_answer or cleaned_answer in option:
                        return option
                    # Handle common variations
                    if option.replace(" ", "") == cleaned_answer.replace(" ", ""):
                        return option
                raise ValueError(f"Invalid option: {user_answer}. Available options: {[opt.get('option') for opt in options]}")
        
        elif question_type == "integer":
            # Validate and return integer
            try:
                # Extract numbers from text (e.g., "3 days" -> "3")
                import re
                numbers = re.findall(r'\d+', cleaned_answer)
                if numbers:
                    num = int(numbers[0])
                    if num < 0:
                        raise ValueError("Number must be non-negative")
                    if num > 999:  # Reasonable upper limit
                        raise ValueError("Number seems too high")
                    return str(num)
                else:
                    raise ValueError(f"No number found in: {user_answer}")
            except ValueError as e:
                if "No number found" in str(e):
                    raise e
                raise ValueError(f"Invalid integer: {user_answer}. Please enter a valid number.")
        
        elif question_type in ["string", "text"]:
            # For text inputs, return as-is but validate length
            if len(cleaned_answer) < 1:
                raise ValueError("Answer cannot be empty")
            if len(cleaned_answer) > 1000:  # Reasonable limit
                raise ValueError("Answer too long (max 1000 characters)")
            return cleaned_answer
        
        elif question_type == "informational":
            # For informational questions, user typically just continues
            if cleaned_answer in ["continue", "ok", "okay", "yes", "got it", "understood", "next"]:
                return "acknowledged"
            else:
                return "acknowledged"  # Default to acknowledged for any response
        
        else:
            # Unknown type, return as-is
            return cleaned_answer
            
    except Exception as e:
        print(f"Error processing answer for question {question.get('title', 'Unknown')}: {str(e)}")
        # Return original answer if processing fails
        return user_answer

async def ask_question(question, session_id):
    """
    Use GPT-4o-mini to format a question object into a user-friendly string to be asked.
    """
    title = question.get('title', '')
    description = question.get('description', '')
    label = question.get('label', '')
    question_type = question.get('type', '')
    options = question.get('options', [])
    
    # Build the prompt for GPT
    prompt = f"""
You are a medical assistant on an asynchronous healthcare platform. You need to ask this specific question to gather more information:

Question Title: {title}
Description: {description}
Label: {label}
Type: {question_type}

"""
    
    if options:
        prompt += "Options:\n"
        for option in options:
            prompt += f"- {option.get('option', '')}\n"
    
    prompt += f"""
Please format this as a natural, conversational question that a medical assistant would ask a patient in an asynchronous healthcare setting. 

Make it friendly, professional, and easy to understand. Format the response as a single, natural question:"""
    
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("OPENAI_API_KEY not set in environment variables")
            return title  # Fallback to just the title
        
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional medical assistant on an asynchronous healthcare platform. You ask questions to gather information needed for patient treatment. Be conversational, professional, and clear."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        formatted_question = response.choices[0].message.content.strip()
        
        # Return structured data based on question type
        if question_type == "multiple_option" and options:
            return MultipleChoiceQuestion(
                question=formatted_question,
                options=[opt.get('option', '') for opt in options]
            )
        elif question_type == "boolean":
            return BooleanQuestion(
                question=formatted_question,
                options=["Yes", "No"]
            )
        elif question_type == "single_option" and options:
            return SingleChoiceQuestion(
                question=formatted_question,
                options=[opt.get('option', '') for opt in options]
            )
        elif question_type == "integer":
            return IntegerQuestion(
                question=formatted_question,
                placeholder=question.get('placeholder')
            )
        elif question_type == "string":
            return StringQuestion(
                question=formatted_question,
                placeholder=question.get('placeholder')
            )
        elif question_type == "text":
            return TextQuestion(
                question=formatted_question,
                placeholder=question.get('placeholder')
            )
        elif question_type == "informational":
            return InformationalQuestion(
                question=formatted_question,
                description=question.get('description')
            )
        else:
            return formatted_question
        
    except Exception as e:
        print(f"Error formatting question with GPT: {str(e)}")
        # Fallback to basic formatting
        return title

async def get_next_question_with_rules(questions, answers, session_id):
    """
    Get the next question based on questionnaire rules and previous answers.
    """
    # Sort questions by order
    sorted_questions = sorted(questions, key=lambda q: q.get("order", 9999))
    
    for question in sorted_questions:
        question_id = question["partner_questionnaire_question_id"]
        
        # Skip if already answered
        if question_id in answers:
            continue
            
        # Check if question should be visible based on rules
        if not question.get("is_visible", True):
            continue
            
        # Check rules to see if this question should be shown
        rules = question.get("rules", [])
        if not rules:
            # No rules, show the question
            return question
            
        # Check if all rules are satisfied
        should_show = True
        for rule in rules:
            rule_type = rule.get("type", "and")
            requirements = rule.get("requirements", [])
            
            if rule_type == "and":
                # All requirements must be met
                for req in requirements:
                    if not await check_requirement(req, answers, session_id):
                        should_show = False
                        break
                if not should_show:
                    break
            elif rule_type == "or":
                # At least one requirement must be met
                req_met = False
                for req in requirements:
                    if await check_requirement(req, answers, session_id):
                        req_met = True
                        break
                if not req_met:
                    should_show = False
                    break
        
        if should_show:
            return question
    
    return None

async def check_requirement(requirement, answers, session_id):
    """
    Check if a specific requirement is met based on previous answers.
    """
    based_on = requirement.get("based_on")
    required_question_id = requirement.get("required_question_id")
    required_answer = requirement.get("required_answer")
    conditional_answer = requirement.get("conditional_answer")
    
    if based_on == "question" and required_question_id:
        # Check if the required question was answered with the required answer
        if required_question_id in answers:
            user_answer = answers[required_question_id].get("answer", "")
            
            # Handle different answer formats
            if required_answer == "0" or required_answer == "1":
                # Boolean questions (0 = No, 1 = Yes)
                if required_answer == "0" and user_answer.lower() in ["no", "false", "0"]:
                    return True
                elif required_answer == "1" and user_answer.lower() in ["yes", "true", "1"]:
                    return True
            else:
                # Text-based answers (exact match)
                if user_answer.lower() == required_answer.lower():
                    return True
    
    return False

async def handle_chat_logic(session: ChatSession, request: ChatRequest, session_created: bool):
    """
    Helper function to handle the chat logic after questionnaire has been assigned.
    """
    # Get the next question
    questions = await get_questionnaire_questions(session.questionnaire_id)
    answers = await get_questionnaire_answers_for_session(session.session_id)
    
    # Find next unanswered question using rules
    next_question = await get_next_question_with_rules(questions, answers, session.session_id)
    
    if next_question:
        # Check if this is an informational question (end of flow)
        if next_question.get("type") == "informational":
            question_content = await ask_question(next_question, session.session_id)
            if isinstance(question_content, InformationalQuestion):
                question_content.is_completed = True
                ai_response_content = question_content
            else:
                ai_response_content = InformationalQuestion(
                    question=question_content,
                    description=next_question.get('description'),
                    is_completed=True
                )
        else:
            # If there's a user message, process it as an answer
            if request.message and request.message.strip():
                # Add user message to database
                await add_chat_message(session.session_id, "user", request.message)
                
                try:
                    # Process and validate the user's answer to the current question
                    processed_answer = await process_user_answer(next_question, request.message)
                    
                    # Save the user's answer
                    await save_questionnaire_answer(
                        session.session_id,
                        next_question.get("title", ""),
                        processed_answer,
                        next_question["partner_questionnaire_question_id"],
                        next_question.get("type", "")
                    )
                    
                    # Now get the NEXT question after this one
                    updated_answers = await get_questionnaire_answers_for_session(session.session_id)
                    next_question_after_answer = await get_next_question_with_rules(questions, updated_answers, session.session_id)
                    
                    if next_question_after_answer:
                        ai_response_content = await ask_question(next_question_after_answer, session.session_id)
                    else:
                        ai_response_content = "Great! You've completed all the questions in the questionnaire."
                    
                except ValueError as e:
                    # Handle validation errors
                    error_message = f"I didn't understand your answer. {str(e)} Please try again."
                    ai_response_content = error_message
                    
                    return ChatResponse(
                        message=ai_response_content,
                        session_id=session.session_id,
                        session_created=session_created
                    )
            else:
                # No user message provided - this is the initial call
                # Just ask the first question without saving anything
                ai_response_content = await ask_question(next_question, session.session_id)
    else:
        ai_response_content = "Great! You've completed all the questions in the questionnaire."

    # Add AI response to database
    if isinstance(ai_response_content, (MultipleChoiceQuestion, BooleanQuestion, SingleChoiceQuestion, IntegerQuestion, StringQuestion, TextQuestion, InformationalQuestion)):
        await add_chat_message(session.session_id, "assistant", ai_response_content.question)
    else:
        await add_chat_message(session.session_id, "assistant", ai_response_content)
    
    return ChatResponse(
        message=ai_response_content,
        session_id=session.session_id,
        session_created=session_created
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that handles both initial questions and user responses.
    """
    try:
        # Get or create session
        session = await get_or_create_session(request.session_id)
        session_created = request.session_id is None

        # If no questionnaire yet, the user must provide their issue first
        if session.questionnaire_id is None:
            # User provided their issue - try to match to a questionnaire
            try:
                match_result = await match_questionnaire_to_query(request.message)
                
                if match_result and match_result.questionnaire_id:
                    # Found a matching questionnaire
                    session.questionnaire_id = match_result.questionnaire_id
                    await update_session_questionnaire(session.session_id, session.questionnaire_id)
                    
                    # Add the user's issue description to chat history
                    await add_chat_message(session.session_id, "user", request.message)
                    
                    # Now proceed with the chat logic, but with an empty message so it asks the first question
                    # Create a new request object with empty message to avoid processing the issue description as an answer
                    empty_request = ChatRequest(message="", session_id=request.session_id)
                    return await handle_chat_logic(session, empty_request, session_created)
                else:
                    # No match found - ask for more details
                    return ChatResponse(
                        message="I couldn't find a specific questionnaire for your issue. Could you please provide more details about your symptoms or condition?",
                        session_id=session.session_id,
                        session_created=session_created
                    )
                    
            except Exception as e:
                print(f"Error matching questionnaire: {str(e)}")
                return ChatResponse(
                    message="I'm having trouble understanding your issue. Could you please try describing it differently?",
                    session_id=session.session_id,
                    session_created=session_created
                )

        # Handle the chat logic using the helper function
        return await handle_chat_logic(session, request, session_created)

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)