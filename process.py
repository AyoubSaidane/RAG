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
from pathlib import Path
import json

# Load environment variables
load_dotenv()

class PPTProcessor:
    def __init__(self):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.vision_model = config["vision_model"]
        self.VLM_system_prompt = config["VLM_system_prompt"]        
        self.ollama_client = Client(host='http://127.0.0.1:11434')
        self.embedding_model = config["embedding_model"]
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
                    "text": (self.VLM_system_prompt)
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

    def process_pptx(self, pptx_path: str, output_base_dir: str = "images"):
        """Process a PPTX file and add to knowledge base"""
        ppt_name = os.path.basename(pptx_path).split('.')[0]
        output_dir = os.path.join(output_base_dir, ppt_name)

        # Convert PPTX to images
        try:
            print(f"Processing: {pptx_path}")
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
            
        except Exception as e:
            print(f"Error processing {ppt_name}: {str(e)}")
            # Cleanup partial processing
            if os.path.exists(output_dir):
                import shutil
                shutil.rmtree(output_dir)
            raise

    def process_pptx_directory(self, pptx_dir: str, output_base_dir: str = "images"):
        """Process all PPTX files in a directory and its subdirectories"""
        processed_files = 0
        
        for root, _, files in os.walk(pptx_dir):
            for file in files:
                if file.endswith(".pptx"):
                    pptx_path = os.path.join(root, file)
                    try:
                        self.process_pptx(pptx_path, output_base_dir)
                        processed_files += 1
                    except Exception as e:
                        print(f"Error processing {pptx_path}: {str(e)}")
                        continue
        
        if processed_files > 0:
            print(f"Processed {processed_files} new PowerPoint files. Saving knowledge base...")
            self.save_knowledge_base()
        else:
            print("No new files were processed.")


if __name__ == "__main__":

    processor = PPTProcessor()

    # Process all PPTs in a directory (run once)
    powerpoint_dir = "./Presentations"  # Update this path
    if os.path.exists(powerpoint_dir):
        processor.process_pptx_directory(powerpoint_dir)  # Initial creation
    else:
        print(f"PowerPoint directory not found: {powerpoint_dir}")