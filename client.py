import requests

def query_api(query, k=5):
    # URL for the FastAPI endpoint
    url = "http://localhost:8000/query"
    
    # Payload to send in the POST request
    payload = {
        "query": query,
        "k": k
    }
    
    try:
        # Send the POST request with a JSON payload
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Error Status Code: {response.status_code}")
            print("Error Details:", response.text)
            return

        # Parse the JSON response
        data = response.json()
        
        # Print the concise response from the API
        print("### Concise Response ###")
        print(data.get("response", "No response provided"))
        print("\n### Relevant Slides ###")
        
        # Print details of each relevant slide
        slides = data.get("slides", [])
        for slide in slides:
            print(f"PPT: {slide['ppt_name']} | Slide: {slide['slide_number']}")
            print(f"Summary Excerpt: {slide['summary']}\n")
    
    except requests.RequestException as e:
        print("An error occurred while querying the API:", e)

if __name__ == "__main__":
    # Define your query (you can change this to whatever you need)
    query = "Find slides about Planets"
    
    # Call the function to query the API and print the response
    query_api(query)
