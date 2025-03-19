```markdown
# Pydantic + Gemini Legal Document Extraction: Quickstart

This guide provides a quickstart for a proof-of-concept (PoC) legal document extraction pipeline built with Python, Pydantic, Instructor, and the Google Gemini 2.0 Flash API. This PoC demonstrates how to classify legal documents (PDFs) and extract key data points.

**Important:** This is a *proof-of-concept*. It is *not* production-ready. It demonstrates the core workflow but lacks robust error handling, file type flexibility, and other features necessary for a real-world application. See "Limitations and Next Steps" below.

## What This PoC Does

This script performs the following steps:

1.  **Document Upload:** You'll upload a PDF legal document to the Google Gemini File API (this step is done *outside* the provided Python script).
2.  **Document Classification:** It uses the Gemini model to classify the document as one of the following types:
    *   Judgment
    *   Dismissal
    *   Affidavit
    *   Other (extraction not implemented in this PoC)
3.  **Data Extraction:** Based on the classified document type, it uses the Gemini model to extract relevant data points. The extracted data conforms to Pydantic models defined in the code (`JudgmentData`, `DismissalData`, or `AffidavitData`).
4.  **Output:** The script prints the extracted data (and document metadata) as a JSON object, structured according to the `LegalDocument` Pydantic model.

## Prerequisites

*   **Python 3.10+:** This code requires Python 3.10 or later.
*   **Google Cloud Account and Project:** You'll need a Google Cloud project with billing enabled.
*   **Gemini API Key:** You need an API key for the Google Gemini API. You can obtain one from [Google AI Studio](https://ai.google.dev/).
*   **Gemini File API Access:** Ensure the Gemini File API is enabled for your project and that you can upload files to it.
*   **A PDF Legal Document:** Prepare a sample PDF document (e.g., a court judgment, dismissal order, or affidavit) to test the pipeline.

## Installation

1.  **Create and Activate a Virtual Environment (Recommended):**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Linux/macOS
    .venv\Scripts\activate  # On Windows
    ```

2.  **Install Dependencies:**

    ```bash
    pip install google-genai pydantic instructor httpx
    ```

## Setup

1.  **Set the `GOOGLE_API_KEY` Environment Variable:**

    ```bash
    export GOOGLE_API_KEY=your_gemini_api_key
    ```

    Alternatively, you can use a `.env` file and the `python-dotenv` library (not included in this simplified PoC for brevity).

2.  **Copy the Code:** Copy the provided Python code into a file named `legal_doc_extraction.py`.

3. **Upload your file:**
    * You'll need to use the `google-genai` library to upload your file to the Gemini File API.
    * Add the following import to the top of your file:
      ```python
      import google.auth
      ```
    * Uncomment the following lines in the `main()` function, and fill in the correct values:
    ```python
        # --- Example usage (replace with your actual file path and desired display name) ---
        file_path = "path/to/your/document.pdf"  # &lt;--- REPLACE THIS
        display_name = "My Legal Document"

        try:
            file_uri = upload_document(file_path, display_name)
            legal_doc: LegalDocument = await process_document(file_uri, client)
            print(legal_doc.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error processing document: {e}")
    ```
    * Run the code, and copy the `file_uri` that is printed to the console.
    * Comment out the lines you uncommented, and replace the placeholder value for `file_uri` with the value you copied. The code should now look like this:

    ```python
        # --- Example usage (replace with your actual file path and desired display name) ---
        # file_path = "path/to/your/document.pdf"  # &lt;--- REPLACE THIS
        # display_name = "My Legal Document"

        # try:
        #     file_uri = upload_document(file_path, display_name)
        #     legal_doc: LegalDocument = await process_document(file_uri, client)
        #     print(legal_doc.model_dump_json(indent=2))
        # except Exception as e:
        #     print(f"Error processing document: {e}")
            file_uri = "gs://generativeai-downloads/files/..." #Replace with your file_uri
    ```

## Running the Script

1.  **Activate your virtual environment** (if you created one):

    ```bash
    source .venv/bin/activate  # On Linux/macOS
    .venv\Scripts\activate  # On Windows
    ```

2.  **Execute the script:**

    ```bash
    python legal_doc_extraction.py
    ```

    The script will print the JSON representation of the extracted `LegalDocument`.

## Expected Output

The output will be a JSON object representing the `LegalDocument` Pydantic model. For example, if you upload a "Judgment" document, the output might look similar to this (the specific content will depend on your document):

```json
{
  "document_id": "files/...",
  "file_uri": "gs://generativeai-downloads/files/...",
  "document_type": {
    "classification": "Judgment",
    "confidence": 0.98
  },
  "extracted_data": {
    "__class__": "JudgmentData",
    "case_number": "ABC-123-2023",
    "filed_date": "2023-10-27",
    "county": "Some County",
    "court": "Superior Court",
    "plaintiff_creditor": {
      "name": "Plaintiff Corp",
      "role": "Plaintiff",
      "address": "123 Main St",
      "attorney": "John Smith"
    },
    "defendants_debtors": [
      {
        "name": "Defendant Ltd",
        "role": "Defendant",
        "address": "456 Oak Ave"
      }
    ],
    "judgment_amount": "12345.67",
    "interest_rate": "0.05",
    "judge": "Judge Judy",
    "satisfaction_status": false,
    "attorney_fees": "1000.00"
  },
  "raw_text": null,
  "processing_errors": []
}
```

*   **`document_id`**: A unique identifier for the document (derived from the file URI in this PoC).
*   **`file_uri`**: The URI of the document in the Gemini File API.
*   **`document_type`**: The classification (e.g., "Judgment") and confidence.
*   **`extracted_data`**: The data extracted, conforming to one of the specific Pydantic models (`JudgmentData`, `DismissalData`, or `AffidavitData`). The `"__class__"` field is used by Pydantic's discriminated union to determine which model was used.
*   **`raw_text`**: This field is `null` in this PoC because we're relying on Gemini for all text extraction.
*   **`processing_errors`**: A list of any errors encountered during processing (empty in this simplified example).

If the document classification confidence is below 0.8, the script will raise an exception. You can adjust this threshold.

## Limitations and Next Steps

This is a *proof-of-concept* and has several limitations:

*   **Limited File Type Support:** This PoC only works with PDF files. Expanding to other formats (DOCX, etc.) would require additional logic.
*   **No Local Text Extraction:** The code relies *entirely* on the Gemini model for OCR and text extraction. This simplifies the code but gives you less control over the extraction process.
*   **No Chunking:** Large documents might exceed the Gemini model's input token limit. A production system would need to implement chunking (splitting the document into smaller parts).
*   **Simplified Error Handling:** The error handling is basic. A production system would need more robust error handling and reporting.
*   **No Contract Support:** The code doesn't yet include the multi-stage extraction logic for contract documents.
*   **No Database:** The extracted data is only printed to the console. A real application would store the data in a database.
*   **No Asynchronous Task Queue:** The code runs synchronously. A production system would likely use a task queue like Celery for asynchronous processing.
* **No Streaming:** There is no support for streaming results.

To build a production-ready system, you would need to address these limitations and add features like user authentication, a web interface, and more. The provided code demonstrates the core concepts and provides a good starting point.

```

