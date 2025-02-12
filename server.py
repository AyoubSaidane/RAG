import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

# Import your PPTProcessor class from your rag file.
# If your code is in a file called `ppt_processor.py`, adjust the import accordingly.
from rag import PPTProcessor

app = FastAPI(title="PPT Query API", description="Query processed PowerPoint presentations", version="1.0")

# Instantiate the processor.
processor = PPTProcessor()

# On startup, load an existing knowledge base (if available).
@app.on_event("startup")
async def startup_event():
    kb_path = "knowledge_base"
    if os.path.exists(kb_path):
        try:
            processor.load_knowledge_base(kb_path)
            print("Knowledge base loaded successfully.")
        except Exception as e:
            print(f"Failed to load knowledge base: {str(e)}")
    else:
        print("Knowledge base not found. Please process PPT files to create one.")


# Define Pydantic models for request and response payloads.
class QueryRequest(BaseModel):
    query: str
    k: int = 5 


class SlideInfo(BaseModel):
    ppt_name: str
    slide_number: int
    image_path: str
    summary: str


class QueryResponse(BaseModel):
    response: str
    slides: List[SlideInfo]


@app.get("/")
async def root():
    return {"message": "Welcome to the PPT Query API. Use the /query endpoint to submit your queries."}



@app.post("/query", response_model=QueryResponse)
async def query_endpoint(query_request: QueryRequest):
    try:
        # Generate a response from the processor.
        print(f"Processing query: {query_request.query}")  # Debug log
        result, slides = processor.query(query_request.query, query_request.k)
        
        if not slides:  # Check if slides is empty
            return QueryResponse(
                response="No relevant slides found for your query.",
                slides=[]
            )

        # Prepare slide information in the response.
        slide_details = [
            SlideInfo(
                ppt_name=slide["ppt_name"],
                slide_number=slide["slide_number"],
                image_path=slide["image_path"],
                summary=slide["summary"]
            )
            for slide in slides
        ]
        return QueryResponse(response=result, slides=slide_details)
    except Exception as e:
        print(f"Server error details: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred while processing your query: {str(e)}"
        )



if __name__ == "__main__":
    # Run the FastAPI app using uvicorn.
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
