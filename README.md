```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install libreoffice
sudo snap install ollama
ollama pull nomic-embed-text

# download ngrok and setup an ngrok account
sudo apt-get update && sudo apt-get install unzip -y
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip
unzip ngrok-v3-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin/
ngrok config add-authtoken $YOUR_AUTHTOKEN
ngrok http 5000
```