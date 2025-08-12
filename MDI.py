from fastapi import APIRouter, HTTPException, UploadFile, File
import httpx
import os
from typing import Optional, List, Dict, Any
from models import PatientRequest, CaseRequest, TokenRequest, TokenResponse, QuestionnaireMatchRequest, QuestionnaireMatchResponse, QuestionnaireMatchResult
import uuid
import openai

MDI_BASE_URL = "https://api.mdintegrations.com/v1/partner/"

async def mdi_request(method: str, endpoint: str, access_token: str = None, headers: dict = None, params: dict = None, json: dict = None, data: dict = None, files: dict = None):
    url = f"{MDI_BASE_URL}{endpoint}"
    req_headers = headers.copy() if headers else {}
    if access_token:
        req_headers["Authorization"] = f"Bearer {access_token}"
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=req_headers, params=params, json=json, data=data, files=files)
        response.raise_for_status()
        return response.json()

router = APIRouter(prefix="/mdi", tags=["MD Integrations"])

async def get_access_token():
    url = "https://api.mdintegrations.com/v1/partner/auth/token"
    client_id = os.getenv("MD_CLIENT_ID")
    client_secret = os.getenv("MD_CLIENT_SECRET")
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "*"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        return token_data["access_token"]

async def match_questionnaire_to_query(query: str, context: str = "") -> QuestionnaireMatchResult:
    """Use GPT-4o-mini to intelligently match a query to the most appropriate questionnaire."""
    try:
        # Get the list of questionnaires
        questionnaires = await get_questionnaires()
        
        # Combine query with context for better matching
        full_query = f"{context} {query}".strip()
        
        # Prepare questionnaire data for GPT
        questionnaire_data = []
        for q in questionnaires:
            questionnaire_data.append({
                "id": q.get("partner_questionnaire_id"),
                "name": q.get("name", ""),
                "intro_title": q.get("intro_title", ""),
                "intro_description": q.get("intro_description", "")
            })
        
        # Create prompt for GPT
        prompt = f"""
You are a medical assistant helping to match patients to the most appropriate health questionnaire.

Patient query: "{full_query}"

Available questionnaires:
"""      
        for i, q in enumerate(questionnaire_data, 1):
            prompt += f"{i}. ID: {q['id']}\n"
            prompt += f"   Name: {q['name']}  Title: {q['intro_title']}\n"
            prompt += f"   Description: {q['intro_description']}\n"
        
        prompt += f"""
Based on the patient's query, which questionnaire is most appropriate? 

Respond with ONLY the questionnaire ID if there's a clear match, or NO_MATCH if none are appropriate.

Consider:
- Medical conditions mentioned
- Symptoms described
- Patient's stated needs
- Gender-specific questionnaires if relevant

Response (just the ID or NO_MATCH):"""        # Call GPT-4o-mini for matching
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise Exception("OPENAI_API_KEY not set in environment variables")
        
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical assistant that matches patients to appropriate health questionnaires. Only respond with the questionnaire ID or 'NO_MATCH'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        gpt_response = response.choices[0].message.content.strip()
        print(f"GPT matching response: {gpt_response}")
        
        # Check if GPT found a match
        if gpt_response != "NO_MATCH" and gpt_response in [q['id'] for q in questionnaire_data]:
            return QuestionnaireMatchResult(questionnaire_id=gpt_response)
        
        # If no match found, generate clarifying questions
        if not context:  # First attempt
            clarifying_question = "I can help you with various health concerns. Could you tell me more specifically what symptoms or conditions you're experiencing? For example, are you looking for help with weight loss, anxiety, skin issues, pain, or something else?"
        else:  # Follow-up attempt
            clarifying_question = "I'm still not sure which questionnaire would be best for you. Could you describe your symptoms in more detail or tell me what specific health concern you're looking to address?"        
        # Get available questionnaire names for context
        available_options = [q['name'] for q in questionnaire_data]
        
        return QuestionnaireMatchResult(
            clarifying_question=clarifying_question,
            available_options=available_options
        )
            
    except Exception as e:
        print(f"Error in questionnaire matching: {str(e)}")
        return QuestionnaireMatchResult(
            clarifying_question="I'm having trouble accessing the questionnaire database. Could you try again in a moment?"
        )

@router.post("/patients")
async def create_patient(patient: PatientRequest):
    """
    Create a new patient via MD Integrations API
    """
    access_token = await get_access_token()
    payload = {k: v for k, v in patient.dict().items() if v is not None}
    try:
        return await mdi_request("POST", "patients", access_token=access_token, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.patch("/patients/{patient_id}")
async def update_patient(patient_id: str, patient_update: PatientRequest):
    access_token = await get_access_token()
    payload = {k: v for k, v in patient_update.dict().items() if v is not None}
    try:
        return await mdi_request("PATCH", f"patients/{patient_id}", access_token=access_token, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/metadata/states")
async def get_states_metadata():
    access_token = await get_access_token()
    try:
        return await mdi_request("GET", "metadata/states", access_token=access_token, headers={"Accept": "application/json", "Content-Type": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/cases")
async def create_case(case: CaseRequest):
    access_token = await get_access_token()
    payload = {k: v for k, v in case.dict().items() if v is not None}
    try:
        return await mdi_request("POST", "cases", access_token=access_token, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/files")
async def upload_file(file: UploadFile = File(...)):
    access_token = await get_access_token()
    files = {"file": (file.filename, file.file, file.content_type)}
    try:
        return await mdi_request("POST", "files", access_token=access_token, files=files, headers={"Accept": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/auth/token", response_model=TokenResponse)
async def get_auth_token(request: TokenRequest):
    payload = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("MD_CLIENT_ID"),
        "client_secret": os.getenv("MD_CLIENT_SECRET"),
        "scope": "*"
    }
    try:
        return await mdi_request("POST", "auth/token", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/questionnaires")
async def get_questionnaires():
    access_token = await get_access_token()
    try:
        return await mdi_request("GET", "questionnaires", access_token=access_token, headers={"Accept": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/questionnaires/simplified")
async def get_simplified_questionnaires():
    """Get only active questionnaires with just their IDs and names."""
    access_token = await get_access_token()
    try:
        questionnaires = await mdi_request("GET", "questionnaires", access_token=access_token, headers={"Accept": "application/json"})
        
        # Filter for active questionnaires and extract only ID and name
        simplified = []
        for q in questionnaires:
            if q.get("active", False):
                simplified.append({
                    "id": q.get("partner_questionnaire_id"),
                    "name": q.get("name", "")
                })
        
        return simplified
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/questionnaires/{questionnaire_id}/simplified")
async def get_simplified_questionnaire(questionnaire_id: str):
    """Get a simplified version of a specific questionnaire with only essential fields."""
    access_token = await get_access_token()
    try:
        questionnaire = await mdi_request("GET", f"questionnaires/{questionnaire_id}", access_token=access_token, headers={"Accept": "application/json"})
        
        # Extract only the essential fields
        simplified = {
            "id": questionnaire.get("partner_questionnaire_id"),
            "name": questionnaire.get("name", ""),
            "questions": []
        }
        
        # Process questions with rules
        if "questions" in questionnaire:
            for q in questionnaire["questions"]:
                question_simplified = {
                    "id": q.get("partner_questionnaire_question_id"),
                    "title": q.get("title", ""),
                    "desc": q.get("description", ""),
                    "order": q.get("order", 0),
                    "type": q.get("type", ""),
                    "options": [],
                    "rules": []
                }
                
                # Process options if they exist
                if "options" in q:
                    for opt in q["options"]:
                        option_simplified = {
                            "id": opt.get("partner_questionnaire_question_option_id"),
                            "option": opt.get("option", ""),
                            "order": opt.get("order", 0)
                        }
                        question_simplified["options"].append(option_simplified)
                
                # Process rules for this specific question
                if "rules" in q and q["rules"]:
                    for rule in q["rules"]:
                        rule_simplified = {
                            "rule_id": rule.get("id"),
                            "rule_type": rule.get("type"),
                            "requirements": []
                        }
                        
                        # Process rule requirements
                        if "requirements" in rule:
                            for req in rule["requirements"]:
                                requirement_simplified = {
                                    "based_on": req.get("based_on"),
                                    "required_question_id": req.get("required_question_id"),
                                    "required_answer": req.get("required_answer")
                                }
                                rule_simplified["requirements"].append(requirement_simplified)
                        
                        question_simplified["rules"].append(rule_simplified)
                
                simplified["questions"].append(question_simplified)
        
        # Add standard medical safety questions to the end
        standard_questions = [
            {
                "id": "standard_allergies",
                "title": questionnaire.get("allergies_title", "Do you have any drug allergies or intolerances?"),
                "desc": questionnaire.get("allergies_description"),
                "order": 1000,
                "type": "text",
                "options": [],
                "rules": []
            },
            {
                "id": "standard_pregnancy",
                "title": questionnaire.get("pregnancy_title", "Are you pregnant or expecting to be?"),
                "desc": questionnaire.get("pregnancy_description", "Medications on your treatment plan might not be recommended for pregnant woman."),
                "order": 1001,
                "type": "boolean",
                "options": [],
                "rules": []
            },
            {
                "id": "standard_medications",
                "title": questionnaire.get("current_medications_title", "Are you taking any medications?"),
                "desc": questionnaire.get("current_medications_description", "Many medications have interactions. Your doctor needs to know every medication that you take to help avoid any harmful interactions."),
                "order": 1002,
                "type": "text",
                "options": [],
                "rules": []
            },
            {
                "id": "standard_conditions",
                "title": questionnaire.get("medical_conditions_title", "Any medical conditions your doctor should know about?"),
                "desc": questionnaire.get("medical_conditions_description"),
                "order": 1003,
                "type": "text",
                "options": [],
                "rules": []
            }
        ]
        
        # Add the standard questions to the end
        simplified["questions"].extend(standard_questions)
        
        return simplified
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/questionnaires/{questionnaire_id}")
async def get_questionnaire(questionnaire_id: str):
    access_token = await get_access_token()
    try:
        return await mdi_request("GET", f"questionnaires/{questionnaire_id}", access_token=access_token, headers={"Accept": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/questionnaires/{questionnaire_id}/questions")
async def get_questionnaire_questions(questionnaire_id: str):
    access_token = await get_access_token()
    try:
        return await mdi_request("GET", f"questionnaires/{questionnaire_id}/questions", access_token=access_token, headers={"Accept": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/questionnaire-match", response_model=QuestionnaireMatchResponse)
async def match_questionnaire(request: QuestionnaireMatchRequest):
    access_token = await get_access_token()
    try:
        return await mdi_request("POST", "questionnaire-match", access_token=access_token, json=request.dict(), headers={"Accept": "application/json", "Content-Type": "application/json"})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 