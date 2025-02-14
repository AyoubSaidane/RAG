from groq import Groq
from typing import List, Dict
import json
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv()
from query import Query

class Chat:
    def __init__(self):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = config["chat_model"]
        self.system_prompt = config["chat_system_prompt"]
        self.processor = Query()
        self.tools = config["tools"]
        self.conversation_history = [{
            "role": "system",
            "content": self.system_prompt
        }]

    def process_message(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # First API call to determine tool usage
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.conversation_history,
            tools=self.tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        # Append assistant's message to history
        assistant_msg = {
            "role": "assistant",
            "content": response_message.content
        }
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in tool_calls
            ]
        self.conversation_history.append(assistant_msg)
        
        if tool_calls:
            # Process tool call
            tool_call = tool_calls[0]
            if tool_call.function.name == "query":
                args = json.loads(tool_call.function.arguments)
                results = self.processor.query(
                    question=args["question"],
                    k=args.get("k", 5)
                )
                
                references = "\n".join(
                    f"<result>\n<ppt_name>{res['ppt_name']}</ppt_name>\n<slide_number>{res['slide_number']}</slide_number>\n<summary>{res['summary']}</summary>\n<distance>{res['distance']}</distance>\n</result>"
                    for res in results
                )
                
                # Append tool response
                self.conversation_history.append({
                    "role": "tool",
                    "content": f"References:\n{references}",
                    "tool_call_id": tool_call.id
                })
                
                # Get final response from assistant
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.conversation_history,
                    max_tokens=800
                )
                final_msg = final_response.choices[0].message
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_msg.content
                })
                return final_msg.content
                
        # Return direct response if no tools used
        return response_message.content

# Usage example remains the same
if __name__ == "__main__":
    chat_system = Chat()
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        response = chat_system.process_message(user_input)
        print(f"Assistant: {response}")
    print(chat_system.conversation_history)