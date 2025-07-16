from fastapi import FastAPI, HTTPException, Depends
import httpx
import os
import uuid
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import UploadFile, File

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="MD Integrations API Client", version="1.0.0")

class TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scope: str = "*"
    
    @field_validator('client_id')
    @classmethod
    def validate_client_id(cls, v):
        if v is not None:
            try:
                uuid.UUID(v)
                return v
            except ValueError:
                raise ValueError('client_id must be a valid UUID')
        return v

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: Optional[str] = None

class VoucherRequest(BaseModel):
    hold_status: bool = False
    patient_id: Optional[str] = None
    questionnaire_id: str
    case_services: list = []
    case_prescriptions: list = []
    disease: list = []

class VoucherResponse(BaseModel):
    onboarding_url: Optional[str] = None
    # You can add more fields as needed based on the actual API response

# Patient creation models
class Country(BaseModel):
    country_id: Optional[str] = None
    name: Optional[str] = None
    abbreviation: Optional[str] = None

class State(BaseModel):
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    state_id: Optional[str] = None
    country: Optional[Country] = None
    is_av_flow: Optional[bool] = None

class Address(BaseModel):
    address: Optional[str] = None
    address2: Optional[str] = None
    zip_code: Optional[str] = None
    city_name: Optional[str] = None
    address_id: Optional[str] = None
    state: Optional[State] = None

class FileInfo(BaseModel):
    file_id: Optional[str] = None
    path: Optional[str] = None
    name: Optional[str] = None
    mime_type: Optional[str] = None
    url: Optional[str] = None
    url_thumbnail: Optional[str] = None
    created_at: Optional[str] = None

class DosespotInfo(BaseModel):
    patient_dosespot_id: Optional[str] = None
    sync_status: Optional[str] = None

class PartnerInfo(BaseModel):
    name: Optional[str] = None
    partner_id: Optional[str] = None
    support_messaging_capability: Optional[str] = None
    support_message_capability: Optional[str] = None
    operations_support_email: Optional[str] = None
    customer_support_email: Optional[str] = None
    partner_notes: Optional[str] = None
    patient_message_capability: Optional[str] = None
    vouched_integration_type: Optional[str] = None
    enable_av_flow: Optional[bool] = None
    enable_icd_bmi: Optional[bool] = None
    is_auto_dl_flow: Optional[bool] = None
    business_model: Optional[str] = None
    slack_channel_id: Optional[str] = None
    operation_country: Optional[Country] = None
    provides_medications: Optional[bool] = None
    thank_you_note_header: Optional[str] = None
    thank_you_note_footer: Optional[str] = None
    customization: Optional[dict] = None
    address: Optional[dict] = None

class Metafield(BaseModel):
    id: Optional[str] = None
    model_type: Optional[str] = None
    model_id: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    scope: Optional[str] = None
    type: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[str] = None
    emailed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None

class PatientAddress(BaseModel):
    address: Optional[str] = None
    address2: Optional[str] = None
    zip_code: Optional[str] = None
    city_name: Optional[str] = None
    state_name: Optional[str] = None

class PatientRequest(BaseModel):
    # Basic patient information
    partner_id: Optional[str] = None
    prefix: Optional[str] = None
    ssn: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    metadata: Optional[str] = None
    gender: Optional[int] = None
    phone_number: Optional[str] = None
    phone_type: Optional[int] = None
    date_of_birth: Optional[str] = None
    active: Optional[bool] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    blood_pressure: Optional[str] = None
    special_necessities: Optional[str] = None
    is_live: Optional[bool] = None
    
    # Medical information
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    pregnancy: Optional[bool] = None
    gender_label: Optional[str] = None
    
    # External integrations
    dosespot: Optional[DosespotInfo] = None
    
    # Files
    driver_license: Optional[FileInfo] = None
    intro_video: Optional[FileInfo] = None
    
    # Address and partner info
    address: Optional[Address] = None
    partner: Optional[PartnerInfo] = None
    
    # Custom metadata
    metafields: Optional[List[Metafield]] = None

class PatientResponse(BaseModel):
    # This will be flexible to handle the complex response structure
    pass

# Case creation models
class CaseStatus(BaseModel):
    name: Optional[str] = None
    reason: Optional[str] = None
    updated_at: Optional[str] = None

class ClinicianPhoto(BaseModel):
    path: Optional[str] = None
    name: Optional[str] = None
    mime_type: Optional[str] = None
    url: Optional[str] = None
    url_thumbnail: Optional[str] = None
    file_id: Optional[str] = None

class Clinician(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    is_online: Optional[bool] = None
    npi: Optional[str] = None
    clinician_id: Optional[str] = None
    full_name: Optional[str] = None
    specialty: Optional[str] = None
    dea: Optional[str] = None
    photo: Optional[ClinicianPhoto] = None

class CaseAssignment(BaseModel):
    reason: Optional[str] = None
    created_at: Optional[str] = None
    case_assignment_id: Optional[str] = None
    clinician: Optional[Clinician] = None

class PartnerCustomization(BaseModel):
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    background_color: Optional[str] = None

class PartnerAddress(BaseModel):
    address_id: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    city_name: Optional[str] = None
    state: Optional[State] = None

class Tag(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    key: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    removable_role: Optional[str] = None
    auto_detach_status: Optional[List[str]] = None

class CasePrescription(BaseModel):
    partner_medication_id: Optional[str] = None

class CaseQuestion(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    type: Optional[str] = None

class CaseRequest(BaseModel):
    patient_id: Optional[str] = None
    case_files: Optional[List[str]] = None
    case_prescriptions: Optional[List[CasePrescription]] = None
    case_services: Optional[List[str]] = None
    case_questions: Optional[List[CaseQuestion]] = None
    diseases: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    hold_status: Optional[bool] = None

class CaseResponse(BaseModel):
    # This will be flexible to handle the complex response structure
    pass

class QuestionnaireMatchRequest(BaseModel):
    query: str

class QuestionnaireMatchResponse(BaseModel):
    partner_questionnaire_id: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None

async def match_questionnaire_to_query(query: str) -> Optional[str]:
    """
    Use GPT-4o-mini to match a query to the most appropriate questionnaire.
    Returns the partner_questionnaire_id if a match is found, None otherwise.
    """
    try:
        # Get the list of questionnaires
        access_token = await get_access_token()
        url = "https://api.mdintegrations.com/v1/partner/questionnaires"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            questionnaires = response.json()
        
        # Prepare the questionnaire data for GPT
        questionnaire_data = []
        for q in questionnaires:
            questionnaire_data.append({
                "id": q.get("partner_questionnaire_id"),
                "name": q.get("name"),
                "intro_title": q.get("intro_title"),
                "intro_description": q.get("intro_description")
            })
        
        # Create the prompt for GPT
        prompt = f"""
You are a medical questionnaire matching system. Given a user query, determine which questionnaire best matches their needs.

Available questionnaires:
{chr(10).join([f"- {q['name']} (ID: {q['id']}): {q['intro_title']} - {q['intro_description']}" for q in questionnaire_data])}

User query: "{query}"

Instructions:
1. Analyze the user's query and match it to the most appropriate questionnaire
2. Consider the medical condition, symptoms, or treatment they're seeking
3. If there's a clear match, return ONLY the questionnaire ID
4. If there's no good match, return "NO_MATCH"
5. Be conservative - only return a match if you're reasonably confident

Response format: Return only the questionnaire ID or "NO_MATCH"
"""
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Call GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical questionnaire matching assistant. Return only the questionnaire ID or 'NO_MATCH'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse the result
        if result == "NO_MATCH":
            return None
        
        # Validate that the result is a valid UUID
        try:
            uuid.UUID(result)
            return result
        except ValueError:
            # If the result isn't a valid UUID, return None
            return None
            
    except Exception as e:
        print(f"Error in questionnaire matching: {str(e)}")
        return None

@app.get("/")
async def root():
    return {"message": "MD Integrations API Client is running"}

@app.post("/auth/token", response_model=TokenResponse)
async def get_auth_token(request: TokenRequest):
    """
    Get authentication token from MD Integrations API
    """
    url = "https://api.mdintegrations.com/v1/partner/auth/token"
    
    # Get client credentials from environment variables or request
    client_id = request.client_id or os.getenv("MD_CLIENT_ID")
    client_secret = request.client_secret or os.getenv("MD_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400, 
            detail="Client ID and Client Secret are required. Set them in .env file or provide in request body."
        )
    
    # Validate that client_id is a valid UUID
    try:
        uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Client ID must be a valid UUID format"
        )
    
    payload = {
        "grant_type": request.grant_type,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": request.scope
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            print(f"API Response: {token_data}")  # Debug log
            return TokenResponse(**token_data)
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

async def get_access_token():
    """Helper to get access token from /auth/token endpoint."""
    from fastapi import Request
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

@app.get("/questionnaires")
async def get_questionnaires():
    """
    Fetch the list of questionnaires from MD Integrations API
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/questionnaires"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/patients")
async def create_patient(patient: PatientRequest):
    """
    Create a new patient via MD Integrations API
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/patients"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Convert the patient model to dict, excluding None values
    payload = {k: v for k, v in patient.dict().items() if v is not None}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.patch("/patients/{patient_id}")
async def update_patient(patient_id: str, patient_update: PatientRequest):
    """
    Update an existing patient via MD Integrations API
    """
    access_token = await get_access_token()
    url = f"https://api.mdintegrations.com/v1/partner/patients/{patient_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Convert the patient model to dict, excluding None values
    payload = {k: v for k, v in patient_update.dict().items() if v is not None}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/metadata/states")
async def get_states_metadata():
    """
    Fetch states metadata from MD Integrations API
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/metadata/states"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/cases")
async def create_case(case: CaseRequest):
    """
    Create a new case via MD Integrations API
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/cases"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Convert the case model to dict, excluding None values
    payload = {k: v for k, v in case.dict().items() if v is not None}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/files")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file via MD Integrations API using multipart/form-data
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/files"
    
    # Prepare the multipart form data
    files = {"file": (file.filename, file.file, file.content_type)}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/questionnaires/summary")
async def get_questionnaires_summary():
    """
    Fetch a summary list of questionnaires with just ID and name from MD Integrations API
    """
    access_token = await get_access_token()
    url = "https://api.mdintegrations.com/v1/partner/questionnaires"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            questionnaires = response.json()
            
            # Filter to just ID and name
            summary = []
            for questionnaire in questionnaires:
                summary.append({
                    "partner_questionnaire_id": questionnaire.get("partner_questionnaire_id"),
                    "name": questionnaire.get("name")
                })
            
            return summary
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/questionnaires/{questionnaire_id}")
async def get_questionnaire(questionnaire_id: str):
    """
    Fetch a specific questionnaire by ID from MD Integrations API
    """
    access_token = await get_access_token()
    url = f"https://api.mdintegrations.com/v1/partner/questionnaires/{questionnaire_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/questionnaires/{questionnaire_id}/questions")
async def get_questionnaire_questions(questionnaire_id: str):
    """
    Fetch questions for a specific questionnaire from MD Integrations API
    """
    access_token = await get_access_token()
    url = f"https://api.mdintegrations.com/v1/partner/questionnaires/{questionnaire_id}/questions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/questionnaires-with-questions")
async def get_questionnaires_with_questions():
    """
    Fetch all questionnaires with their questions from MD Integrations API
    """
    access_token = await get_access_token()
    
    # First, get all questionnaires
    questionnaires_url = "https://api.mdintegrations.com/v1/partner/questionnaires"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Get all questionnaires
            questionnaires_response = await client.get(questionnaires_url, headers=headers)
            questionnaires_response.raise_for_status()
            questionnaires = questionnaires_response.json()
            
            # For each questionnaire, get its questions
            questionnaires_with_questions = []
            for questionnaire in questionnaires:
                questionnaire_id = questionnaire.get("partner_questionnaire_id")
                if questionnaire_id:
                    try:
                        questions_url = f"https://api.mdintegrations.com/v1/partner/questionnaires/{questionnaire_id}"
                        questions_response = await client.get(questions_url, headers=headers)
                        questions_response.raise_for_status()
                        questionnaire_with_questions = questions_response.json()
                        questionnaires_with_questions.append(questionnaire_with_questions)
                    except httpx.HTTPStatusError as e:
                        # If we can't get questions for a specific questionnaire, 
                        # add the questionnaire without questions and log the error
                        print(f"Error getting questions for questionnaire {questionnaire_id}: {e.response.text}")
                        questionnaires_with_questions.append(questionnaire)
                    except Exception as e:
                        print(f"Unexpected error getting questions for questionnaire {questionnaire_id}: {str(e)}")
                        questionnaires_with_questions.append(questionnaire)
            
            return questionnaires_with_questions
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/questionnaire-match", response_model=QuestionnaireMatchResponse)
async def match_questionnaire(request: QuestionnaireMatchRequest):
    """
    Use GPT-4o-mini to match a query to the most appropriate questionnaire.
    """
    try:
        partner_questionnaire_id = await match_questionnaire_to_query(request.query)
        
        if partner_questionnaire_id:
            return QuestionnaireMatchResponse(
                partner_questionnaire_id=partner_questionnaire_id,
                confidence=1.0, # Assuming perfect confidence for now
                reasoning=f"Query '{request.query}' matched questionnaire with ID: {partner_questionnaire_id}"
            )
        else:
            return QuestionnaireMatchResponse(
                partner_questionnaire_id=None,
                confidence=0.0,
                reasoning=f"Query '{request.query}' did not match any questionnaire."
            )
    except Exception as e:
        print(f"Error in questionnaire matching endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error during questionnaire matching: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
