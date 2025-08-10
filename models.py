from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, field_validator, UUID4, Field
import uuid
from datetime import datetime

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
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    pregnancy: Optional[bool] = None
    gender_label: Optional[str] = None
    dosespot: Optional[DosespotInfo] = None
    driver_license: Optional[FileInfo] = None
    intro_video: Optional[FileInfo] = None
    address: Optional[Address] = None
    partner: Optional[PartnerInfo] = None
    metafields: Optional[List[Metafield]] = None

class PatientResponse(BaseModel):
    pass

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
    pass

class QuestionnaireMatchRequest(BaseModel):
    query: str

class QuestionnaireMatchResponse(BaseModel):
    partner_questionnaire_id: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class QuestionnaireMatchResult(BaseModel):
    questionnaire_id: Optional[str] = None
    clarifying_question: Optional[str] = None
    available_options: Optional[List[str]] = None

class ChatSession(BaseModel):
    session_id: UUID4
    messages: List[ChatMessage] = []
    created_at: str
    last_updated: str
    questionnaire_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # None for new sessions

class MultipleChoiceQuestion(BaseModel):
    type: str = "multiple_choice"
    question: str
    options: List[str]

class BooleanQuestion(BaseModel):
    type: str = "boolean"
    question: str
    options: List[str] = ["Yes", "No"]

class SingleChoiceQuestion(BaseModel):
    type: str = "single_choice"
    question: str
    options: List[str]

class IntegerQuestion(BaseModel):
    type: str = "integer"
    question: str
    placeholder: Optional[str] = None

class StringQuestion(BaseModel):
    type: str = "string"
    question: str
    placeholder: Optional[str] = None

class TextQuestion(BaseModel):
    type: str = "text"
    question: str
    placeholder: Optional[str] = None

class InformationalQuestion(BaseModel):
    type: str = "informational"
    question: str
    description: Optional[str] = None
    is_completed: Optional[bool] = False

# Union type for all question types
QuestionContent = Union[
    str, 
    MultipleChoiceQuestion, 
    BooleanQuestion, 
    SingleChoiceQuestion, 
    IntegerQuestion, 
    StringQuestion, 
    TextQuestion, 
    InformationalQuestion
]

class ChatResponse(BaseModel):
    message: QuestionContent  # Can be string or any structured question type
    session_id: Union[str, UUID4]  # Can be string or UUID4
    session_created: bool = False 