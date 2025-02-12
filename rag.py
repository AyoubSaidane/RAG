import os
import base64
import subprocess
import numpy as np
import faiss
from dotenv import load_dotenv
from groq import Groq
from ollama import Client
from pdf2image import convert_from_path
import pickle
from typing import List, Dict, Tuple
import pdb

# Load environment variables
load_dotenv()

class PPTProcessor:
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.ollama_client = Client(host='http://127.0.0.1:11434')
        self.vision_model = "llama-3.2-11b-vision-preview"
        self.embedding_model = "nomic-embed-text"
        self.index = None
        self.metadata = []
        self.index_initialized = False

    def convert_pptx_to_images(self, pptx_path: str, output_dir: str) -> List[str]:
        """Convert PPTX file to individual slide images using LibreOffice"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert PPTX to PDF
        subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf',
            '--outdir', output_dir, pptx_path
        ], check=True)
        
        # Convert PDF to images
        pdf_path = os.path.join(
            output_dir, 
            os.path.basename(pptx_path).replace('.pptx', '.pdf')
        )
        images = convert_from_path(pdf_path)
        image_paths = []
        for i, image in enumerate(images):
            img_path = os.path.join(output_dir, f'slide_{i+1}.jpg')
            image.save(img_path, 'JPEG')
            image_paths.append(img_path)
        
        return image_paths

    def generate_slide_summary(self, image_path: str) -> str:
        """Generate detailed slide description using Groq's vision model"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = self.groq_client.chat.completions.create(
            model=self.vision_model, 
            messages=[{
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": (
                        "You are an AI-powered presentation analyzer. Your task is to generate a comprehensive and insightful summary of the slide. "
                        "Provide a detailed description of all visible content, including but not limited to: text, charts, diagrams, images, and other visual elements. "
                        "Focus on the following areas: "
                        "- **Text**: Describe the text, including titles, bullet points, and any other textual content. Pay attention to the tone, wording, and business relevance. "
                        "- **Visuals**: Analyze and describe any charts, graphs, tables, or diagrams. Mention the types of charts (bar, pie, line, etc.), the key trends or data points, and their business relevance. "
                        "- **Layout**: Comment on the slide's layout and design choices, such as color schemes, font styles, and alignment. Note any elements that stand out or help with the presentation's visual appeal. "
                        "- **Contextual Understanding**: If there are any visual cues suggesting a business or industry context (e.g., financials, projections, product details), provide insights into what the slide conveys in that context. "
                        "- **Annotations and Key Data**: Identify any annotations, numerical data, or labels present on the slide, and provide their significance."
                    )
                }, {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                }]
            }],
            max_tokens=1200
        )
        return response.choices[0].message.content
   
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings using Ollama's Nomic model"""
        response = self.ollama_client.embeddings(model=self.embedding_model, prompt=text)
        return response['embedding']
    
    def save_knowledge_base(self, path: str = "knowledge_base"):
        """Save FAISS index and metadata"""
        os.makedirs(path, exist_ok=True)
        faiss.write_index(self.index, os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.pkl"), "wb") as f:
            pickle.dump(self.metadata, f)

    def load_knowledge_base(self, path: str = "knowledge_base"):
        """Load existing knowledge base"""
        self.index = faiss.read_index(os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.pkl"), "rb") as f:
            self.metadata = pickle.load(f)
        self.index_initialized = True

    def process_pptx(self, pptx_path: str, output_base_dir: str = "data"):
        """Process a PPTX file and add to knowledge base"""
        ppt_name = os.path.basename(pptx_path).split('.')[0]
        output_dir = os.path.join(output_base_dir, ppt_name)
        
        # Convert PPTX to images
        image_paths = self.convert_pptx_to_images(pptx_path, output_dir)
        
        # Process each slide
        for idx, img_path in enumerate(image_paths):
            summary = self.generate_slide_summary(img_path)
            embedding = self.generate_embedding(summary)
            
            # Add to metadata and index
            self.metadata.append({
                "ppt_name": ppt_name,
                "slide_number": idx + 1,
                "image_path": img_path,
                "summary": summary
            })

            
            if not self.index_initialized:
                # Initialize FAISS index
                dim = len(embedding)
                self.index = faiss.IndexFlatL2(dim)
                self.index_initialized = True
            
            self.index.add(np.array([embedding], dtype=np.float32))
   
    def process_pptx_directory(self, pptx_dir: str, output_base_dir: str = "data"):
        """Process all PPTX files in a directory and its subdirectories"""
        processed_files = 0
        
        for root, _, files in os.walk(pptx_dir):
            for file in files:
                if file.endswith(".pptx"):
                    pptx_path = os.path.join(root, file)
                    try:
                        print(f"Processing: {pptx_path}")
                        self.process_pptx(pptx_path, output_base_dir)
                        processed_files += 1
                    except Exception as e:
                        print(f"Error processing {pptx_path}: {str(e)}")
                        continue
        
        print(f"Processed {processed_files} PowerPoint files. Saving knowledge base...")
        self.save_knowledge_base()

    def query(self, question: str, k: int = 5) -> Tuple[str, List[Dict]]:
        """Handle user query and return results"""
        # Generate query embedding
        query_embed = np.array([self.generate_embedding(question)], dtype=np.float32)
        
        # Search index
        distances, indices = self.index.search(query_embed, k)
        
        # Get relevant results
        results = [self.metadata[i] for i in indices[0]]
        
        # Generate concise response
        context = "\n".join([f"Slide {res['slide_number']}: {res['summary']}" 
                           for res in results])
        
        response = self.groq_client.chat.completions.create(
            model=self.vision_model,
            messages=[{
                "role": "system",
                "content": ("You are a consulting knowledge manager. Provide a concise answer "
                            "followed by slide references. Focus on business implications, "
                            "chart types, and industry relevance.")
            }, {
                "role": "user",
                "content": f"Query: {question}\n\nContext:\n{context}"
            }],
            max_tokens=800
        )
        
        return response.choices[0].message.content, results
 
if __name__ == "__main__":
    processor = PPTProcessor()
    
    # Process all PPTs in a directory (run once)
    powerpoint_dir = "./presentations"  # Update this path
    if os.path.exists(powerpoint_dir):
        # Either load existing or create new knowledge base
        if os.path.exists("knowledge_base"):
            processor.load_knowledge_base()
            processor.process_pptx_directory(powerpoint_dir)  # Add new files
        else:
            processor.process_pptx_directory(powerpoint_dir)  # Initial creation
    else:
        print(f"PowerPoint directory not found: {powerpoint_dir}")
    
    # Example query (keep previous query logic)
    query = "Find slides about Planets"
    response, slides = processor.query(query)
    
    print("### Concise Response ###")
    print(response)
    print("\n### Relevant Slides ###")
    for slide in slides:
        print(f"PPT: {slide['ppt_name']} | Slide: {slide['slide_number']}")
        print(f"Summary Excerpt: {slide['summary']}\n")