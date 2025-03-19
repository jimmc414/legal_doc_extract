# Legal Document Extraction Pipeline (Pydantic + Google Gemini 2.0 Flash) - Proof of Concept

This project provides a proof-of-concept (PoC) implementation of a legal document extraction pipeline using Python, Pydantic, Instructor, and the Google Gemini 2.0 Flash API.  It demonstrates how to:

1.  **Upload** legal documents (currently PDFs) to the Google Gemini File API.
2.  **Classify** the type of document (Judgment, Dismissal, Affidavit, or Other).
3.  **Extract** key data points specific to the identified document type, leveraging Gemini's ability to return structured data.
4.  **Validate** the extracted data using Pydantic models.
5.  **Structure** the results into a unified `LegalDocument` Pydantic model.

This PoC *completely* relies on the Google Gemini 2.0 Flash model (via the `google-genai` SDK) for content understanding, including OCR of PDF files.  It does *not* use any local file processing libraries (like `PyPDF2`).

**Important:** This is a *proof-of-concept*. It is *not* production-ready.  It demonstrates the core workflow but lacks robust error handling, file type flexibility, and other features necessary for a real-world application.  See "Limitations and Next Steps" below.

## Key Technologies

*   **Python 3.10+:** The programming language used.
*   **`google-genai`:** The Google Gemini API Python SDK. This handles file uploads, document classification, and data extraction.
*   **Pydantic (v2):**  Used for data modeling, validation, and defining the structure of the extracted data. Pydantic's models are used directly in prompts to guide Gemini's output.
*   **Instructor:** A library that patches the `google-genai` client, adding a `response_model` parameter to enforce structured output conforming to Pydantic models, including automatic retries.
*   **`asyncio` and `httpx`:** Used for asynchronous operations, enabling potential scalability if expanded to a full application.

## Project Structure

The code (`legal_doc_extraction.py`) is organized into the following main sections:

*   **Pydantic Models:** Defines the data structures for representing:
    *   `DocumentTypeEnum`: An enumeration of possible document types.
    *   `DocumentType`:  The result of document classification (type and confidence).
    *   `Party`:  Information about a person or entity involved in the document.
    *   `JudgmentData`:  Data specific to Judgment documents.
    *   `DismissalData`: Data specific to Dismissal documents.
    *   `AffidavitData`: Data specific to Affidavit documents.
    *   `LegalDocument`:  The top-level model that combines the document type and extracted data using a discriminated union.  This is the final output of the pipeline.
*   **`classify_document(file_uri, client)`:**  A function that uses the Gemini API to classify the document type.  It sends the file URI and a prompt to Gemini, expecting a `DocumentType` object in return.
*   **`extract_data(file_uri, document_type, client)`:**  A function that takes the file URI and the classified document type.  It then uses a conditional structure (if/elif/else) to select the appropriate Pydantic model (`JudgmentData`, `DismissalData`, or `AffidavitData`) and calls the Gemini API to extract data into that model.
*   **`process_document(file_uri, client)`:**  The main pipeline function for a single document. It calls `classify_document` and `extract_data`, handles potential low confidence in classification, and combines the results into a `LegalDocument` instance.
*   **`upload_document(file_path, display_name)`:** Uploads a file to the Gemini File API and returns the URI.
*   **`main()`:**  A simple `async` main function that:
    *   Configures the `google-genai` client (with Instructor patching).
    *   **Calls `upload_document` to upload a file and get the URI.**
    *   Calls `process_document` to process the document.
    *   Prints the resulting `LegalDocument` as JSON.

## Setup and Running

1.  **Install Dependencies:**

    ```bash
    pip install google-genai pydantic instructor httpx
    ```

2.  **Set up Google Gemini API Key:**

    *   Obtain an API key for the Google Gemini API. See the [Google Gemini API documentation](https://ai.google.dev/gemini-api/docs) for instructions.
    *   Set the `GOOGLE_API_KEY` environment variable:
        ```bash
        export GOOGLE_API_KEY=your_gemini_api_key
        ```
        (Or use a `.env` file with `python-dotenv`.)

3.  **Copy the Code:** Copy the provided Python code into a file named `legal_doc_extraction.py`.

4.  **Modify the Python Script:**

    *   Open the `legal_doc_extraction.py` file.
    *   **Replace the placeholder `file_path`** in the `main()` function with the *actual* path to your PDF file:
        ```python
        async def main():
            # ...
            # Replace this with the actual path to your PDF file
            file_path = "path/to/your/document.pdf"  # &lt;--- REPLACE THIS
            display_name = "My Legal Document"
            # ...
        ```

5.  **Run the Script:**

    ```bash
    python legal_doc_extraction.py
    ```

    The script will:

    *   Upload the document to the Gemini File API.
    *   Classify the document type.
    *   Extract data based on the classified type.
    *   Print the extracted data as a JSON object to the console.

## Expected Output

The output will be a JSON object representing the `LegalDocument` Pydantic model.  For example, if you upload a "Judgment" document, the output might look like this (the specific content will depend on your document):

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

*   **`document_id`**:  A unique identifier for the document (derived from the file URI in this PoC).
*   **`file_uri`**: The URI of the document in the Gemini File API.
*   **`document_type`**: The classification (e.g., "Judgment") and confidence.
*   **`extracted_data`**: The data extracted, conforming to one of the specific Pydantic models (`JudgmentData`, `DismissalData`, or `AffidavitData`).  The `"__class__"` field is used by Pydantic's discriminated union to determine which model was used.
*   **`raw_text`**:  This field is `null` in this PoC because we're relying on Gemini for all text extraction.
*   **`processing_errors`**:  A list of any errors encountered during processing (empty in this simplified example).

If the document classification confidence is below 0.8, the script will raise an exception.  You can adjust this threshold.

## Limitations and Next Steps

This is a *proof-of-concept* and has several limitations:

*   **Limited File Type Support:**  This PoC only works with PDF files.  Expanding to other formats (DOCX, etc.) would require additional logic.
*   **No Local Text Extraction:**  The code relies *entirely* on the Gemini model for OCR and text extraction.  This simplifies the code but gives you less control over the extraction process.
*   **No Chunking:**  Large documents might exceed the Gemini model's input token limit.  A production system would need to implement chunking (splitting the document into smaller parts).
*   **Simplified Error Handling:**  The error handling is basic.  A production system would need more robust error handling and reporting.
*   **No Contract Support:** The code doesn't yet include the multi-stage extraction logic for contract documents.
*   **No Database:**  The extracted data is only printed to the console. A real application would store the data in a database.
*   **No Asynchronous Task Queue:** The code runs synchronously.  A production system would likely use a task queue like Celery for asynchronous processing.
*   **No Streaming:** There is no support for streaming results.

To build a production-ready system, you would need to address these limitations and add features like user authentication, a web interface, and more.