import re
import os
import asyncio
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Union

import instructor
from google import genai
from pydantic import BaseModel, Field, field_validator, ValidationError, condecimal

# --- Pydantic Models ---
class DocumentTypeEnum(str, Enum):
    JUDGMENT = "Judgment"
    DISMISSAL = "Dismissal"
    AFFIDAVIT = "Affidavit"
    OTHER = "Other"

class DocumentType(BaseModel):
    classification: DocumentTypeEnum = Field(..., description="The identified type of legal document.")
    confidence: float = Field(..., description="Confidence score from the classification process (0.0 to 1.0).")

class Party(BaseModel):
    name: str = Field(..., description="Full name of the party (person or entity).")
    role: Optional[str] = Field(None, description="Role of the party, e.g., 'Plaintiff', 'Defendant', 'Creditor', 'Debtor'.")
    address: Optional[str] = Field(None, description="Address of the party, if available.")
    attorney: Optional[str] = Field(None, description="Name of the attorney representing the party, if available.")

class JudgmentData(BaseModel):
    case_number: str = Field(..., description="The unique case number assigned to the judgment.  Must be in the format ABC-123-2023.")
    filed_date: date = Field(..., description="The date the judgment was filed with the court.")
    county: str = Field(..., description="The county where the judgment was filed.")
    court: Optional[str] = Field(None, description="The specific court (e.g., 'Superior Court', 'District Court') where the judgment was filed.")
    plaintiff_creditor: Party = Field(..., description="The party in whose favor the judgment is entered (plaintiff/creditor).")
    defendants_debtors: List[Party] = Field(..., description="The party or parties against whom the judgment is entered (defendant(s)/debtor(s)).")
    judgment_amount: condecimal(ge=0) = Field(..., description="The monetary amount awarded in the judgment, expressed as a decimal.  Look for phrases like 'the sum of', 'judgment is entered for', etc.  Exclude any commas.")  # type: ignore
    interest_rate: Optional[condecimal(ge=0, le=1)] = Field(None, description="The annual interest rate applied to the judgment, if specified. Express as a decimal (e.g., 0.05 for 5%).")  # type: ignore
    judge: Optional[str] = Field(None, description="The name of the judge who issued the judgment.")
    satisfaction_status: Optional[bool] = Field(None, description="Indicates whether the judgment has been satisfied (paid). True if satisfied, False otherwise. Look for phrases like 'satisfied', 'released', 'paid in full'.")
    attorney_fees: Optional[condecimal(ge=0)] = Field(None, description="Attorney's fees awarded, if any.")  # type: ignore

    @field_validator('case_number')
    def validate_case_number_format(self, v: str) -> str:
        if not re.match(r'^[A-Z]{3}-\d{3}-\d{4}$', v):
            raise ValueError('Invalid case number format. Must be ABC-123-2023.')
        return v

    @field_validator('judgment_amount', 'attorney_fees', mode='before')
    def remove_commas(cls, v: str | None | Decimal) -> str | None | Decimal:
        if isinstance(v, str):
             return v.replace(',', '')
        return v

    @field_validator('satisfaction_status', mode='before')
    def standardize_satisfaction(cls, v: str | bool | None) -> bool | None:
        if isinstance(v, str):
            v_lower = v.lower()
            if 'satisf' in v_lower or 'paid in full' in v_lower or 'release' in v_lower:  #More keywords could be added.
                return True
            elif 'unsatisfied' in v_lower: #Handle explicit negatives
                return False
            else:
                return None #Could not determine
        return v

    @field_validator('interest_rate')
    def check_interest_rate(cls, v: Decimal | None, info) -> Decimal | None: # Using info instead of values
        if v is not None and 'judgment_amount' in info.data and v > 1:
            raise ValueError('Interest rate is too high.')
        return v

class DismissalTypeEnum(str, Enum):
    WITH_PREJUDICE = "with prejudice"
    WITHOUT_PREJUDICE = "without prejudice"
    VOLUNTARY = "voluntary"
    INVOLUNTARY = "involuntary"

class DismissalData(BaseModel):
    case_number: str = Field(..., description="The unique case number assigned to the case being dismissed.")
    filed_date: date = Field(..., description="The date the dismissal was filed with the court.")
    county: str = Field(..., description="The county where the case was filed and dismissed.")
    court: Optional[str] = Field(None, description="The specific court (e.g., 'Superior Court', 'District Court') where the case was filed.")
    plaintiff: Party = Field(..., description="The party who filed the original case (plaintiff).")
    defendants: List[Party] = Field(..., description="The party or parties against whom the case was filed (defendant(s)).")
    dismissal_type: DismissalTypeEnum = Field(..., description="The type of dismissal.")
    judge: Optional[str] = Field(None, description="The name of the judge who issued the dismissal.")
    reason: Optional[str] = Field(None, description="Reason for dismissal, if stated.")


class AffidavitData(BaseModel):
    affiant: Party = Field(..., description="The person making the sworn statement (the affiant).")
    date_of_affidavit: date = Field(..., description="The date the affidavit was signed and sworn.")
    content_summary: str = Field(..., description="A concise summary of the main points or statements made in the affidavit.", max_length=500)
    notary_public: Optional[str] = Field(None, description="The name of the notary public who witnessed the signing of the affidavit.")
    notary_county: Optional[str] = Field(None, description="County where the affidavit was notarized.")
    notary_state: Optional[str] = Field(None, description="State where the affidavit was notarized.")
    commission_expiration: Optional[date] = Field(None, description="Expiration date of the notary public's commission.")


class ExtractionError(BaseModel):
    error_message: str

class LegalDocument(BaseModel):
    document_id: str = Field(..., description="Unique identifier for the document.")
    file_uri: str = Field(..., description="URI from the Gemini File API.")  # No HttpUrl
    document_type: DocumentTypeEnum = Field(..., description="Classification of the document.")
    extracted_data: Union[JudgmentData, DismissalData, AffidavitData, ExtractionError] = Field(..., discriminator='__class__') # type: ignore
    processing_errors: List[str] = Field(default_factory=list, description="List of errors encountered during processing.")


# --- Constants ---
CLASSIFY_PROMPT = """Classify the following legal document (provided as file URI: {file_uri}) into one of the following categories:

- Judgment
- Dismissal
- Affidavit
- Other

Return the classification and a confidence score between 0.0 and 1.0.
"""

# --- Helper Functions ---

async def classify_document(file_uri: str, client: genai.AsyncGenerativeModel) -> DocumentType:
    """Classifies the type of legal document using the Gemini API."""
    prompt = CLASSIFY_PROMPT.format(file_uri=file_uri)
    response = await client.generate_content_async(
        contents=[prompt, {"uri": file_uri, "mime_type": "application/pdf"}], # Assuming PDF, adapt if needed
        generation_config={'response_mime_type': 'application/json'},
        response_model=DocumentType,
        max_retries=3
    )
    return response.parsed # type: ignore


async def extract_data(file_uri: str, document_type: DocumentTypeEnum, client: genai.AsyncGenerativeModel) -> Union[JudgmentData, DismissalData, AffidavitData, ExtractionError]:
    """Extracts data from the legal document based on its type."""
    try:
        if document_type == DocumentTypeEnum.JUDGMENT:
            response = await client.generate_content_async(
                contents=[{'uri': file_uri, 'mime_type': 'application/pdf'}],
                generation_config={'response_mime_type': 'application/json'},
                response_model=JudgmentData,
                max_retries=3
            )
            return response.parsed # type: ignore

        elif document_type == DocumentTypeEnum.DISMISSAL:
            response = await client.generate_content_async(
                contents=[{'uri': file_uri, 'mime_type': 'application/pdf'}],
                generation_config={'response_mime_type': 'application/json'},
                response_model=DismissalData,
                max_retries=3
            )
            return response.parsed # type: ignore

        elif document_type == DocumentTypeEnum.AFFIDAVIT:
            response = await client.generate_content_async(
                contents=[{'uri': file_uri, 'mime_type': 'application/pdf'}],
                generation_config={'response_mime_type': 'application/json'},
                response_model=AffidavitData,
                max_retries=3
            )
            return response.parsed # type: ignore

        elif document_type == DocumentTypeEnum.OTHER:
            return ExtractionError(error_message="Extraction for document type 'Other' not implemented.")
        else:
            raise ValueError(f"Invalid document type: {document_type}")
    except ValidationError as e:
        return ExtractionError(error_message=str(e))
    except Exception as e:
        return ExtractionError(error_message=f"Unexpected error: {type(e).__name__} - {e}")


async def process_document(file_uri: str, client: genai.AsyncGenerativeModel) -> LegalDocument:
    """Processes a single legal document."""
    errors = []
    try:
        document_type = await classify_document(file_uri, client)
        if document_type.confidence < 0.8:
            errors.append("Low confidence in document classification.")
            return LegalDocument(document_id=file_uri, file_uri=file_uri, document_type=DocumentTypeEnum.OTHER, extracted_data=ExtractionError(error_message="Low confidence in document classification."), processing_errors=errors) # type: ignore

        extracted_data = await extract_data(file_uri, document_type.classification, client)

    except Exception as e:
        errors.append(str(e))
        return LegalDocument(
            document_id=file_uri.split(":")[-1],
            file_uri=file_uri,
            document_type=DocumentTypeEnum.OTHER,
            extracted_data=ExtractionError(error_message=str(e)), # type: ignore
            processing_errors=errors
        )

    return LegalDocument(
        document_id=file_uri.split(":")[-1],  # Extract ID from URI.
        file_uri=file_uri,
        document_type=document_type.classification,
        extracted_data=extracted_data, # type: ignore
    )

async def upload_document(file_path: str, display_name: str) -> str:
    """Uploads a file to the Gemini File API and returns the file URI."""
    async with genai.GenerativeModel('gemini-2.0-flash-001') as client:
        # Upload the file.
        file = await client.upload_file(file=file_path, display_name=display_name)

        # Return the file URI.
        print(f"Uploaded file: {file.uri}")
        return file.uri

async def main():
    # Configure Gemini API
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    client = genai.GenerativeModel(model_name="gemini-2.0-flash-001")
    client = instructor.from_google(client, mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS)

    # --- Example usage (replace with your actual file path and desired display name) ---
    # file_path = "path/to/your/document.pdf"  # <--- REPLACE THIS
    # display_name = "My Legal Document"

    # try:
    #     file_uri = await upload_document(file_path, display_name)
    #     legal_doc: LegalDocument = await process_document(file_uri, client)
    #     print(legal_doc.model_dump_json(indent=2))
    # except Exception as e:
    #     print(f"Error processing document: {e}")
    file_uri = "gs://generativeai-downloads/files/..." #Replace with your file_uri
    legal_doc: LegalDocument = await process_document(file_uri, client)
    print(legal_doc.model_dump_json(indent=2))


if __name__ == "__main__":
  asyncio.run(main())