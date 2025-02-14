import os
import numpy as np
import faiss
from dotenv import load_dotenv
from groq import Groq
from ollama import Client
import pickle
from typing import List, Dict, Tuple
from pathlib import Path
import json

# Load environment variables
load_dotenv()

class Query:
    def __init__(self):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        self.ollama_client = Client(host='http://127.0.0.1:11434')
        self.embedding_model = config["embedding_model"]
        self.index = None
        self.metadata = []
        self.index_initialized = False

    def load_knowledge_base(self, path: str = "knowledge_base"):
        """Load existing knowledge base"""
        self.index = faiss.read_index(os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.pkl"), "rb") as f:
            self.metadata = pickle.load(f)
        self.index_initialized = True

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings using Ollama's Nomic model"""
        response = self.ollama_client.embeddings(model=self.embedding_model, prompt=text)
        return response['embedding']
    
    def query(self, question: str, k: int = 5) -> Tuple[str, List[Dict]]:
        """Handle user query and return results"""
        # Generate query embedding
        self.load_knowledge_base()
        query_embed = np.array([self.generate_embedding(question)], dtype=np.float32)
        
        # Search index
        distances, indices = self.index.search(query_embed, k)
        
        # Get relevant results
        results = [self.metadata[indices[0][i]] | {"distance":distances[0][i]} for i in range(len(indices[0]))]
        
        return results


if __name__ == "__main__":
    processor = Query()
    if not os.path.exists("knowledge_base"):
        print("Knowledge base not available")
        exit()
        
    while True:
        try:
            question = input("\nEnter your question (or 'quit' to exit): ")
            if question.lower() == 'quit':
                break
                
            context = processor.query(question)
            print(f"\nQuery: {question}")
            print(f"Response: {context}")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
    

