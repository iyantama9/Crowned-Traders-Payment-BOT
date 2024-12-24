# Discord Payment Bot 

This project is a Discord bot built using the `discord.py` library, integrated with a FastAPI application for handling payment notifications and managing user roles. The bot allows users to purchase roles through a payment gateway (Midtrans) and manages role assignments based on payment status.

*I'll create a raw version that you can easily customize to suit your needs soon

## Features

- **Role Management**: Users can purchase roles that grant them access to specific features within the Discord server.
- **Payment Integration**: Utilizes Midtrans for processing payments and handling payment notifications.
- **Google Sheets Integration**: Records user information and payment status in Google Sheets for tracking purposes.
- **Scheduled Role Removal**: Automatically removes roles after a specified duration.

## Requirements

- Python 3.9 or higher
- Discord Bot Token
- Midtrans API Keys
- Google Service Account JSON file for Google Sheets access
- FastAPI and Uvicorn for the web server

## Installation
1. **Clone the repository**:
bash git clone https://github.com/yourusername/your-repo-name.git cd your-repo-name

2. **Create a virtual environment** (optional but recommended):
bash python -m venv venv source venv/bin/activate # On Windows use venv\Scripts\activate

3. **Install the required packages**:
Create a `requirements.txt` file with the following content:
discord.py fastapi uvicorn requests python-dotenv google-auth google-api-python-client
Then run:
bash pip install -r requirements.txt

4. **Set up environment variables**:
Create a `.env` file in the root directory of your project and add the following variables:

DISCORD_TOKEN=your_discord_bot_token 
JSON_FILE_URL=your_google_service_account_json_url 
MIDTRANS_SERVER_KEY=your_midtrans_server_key 
MIDTRANS_CLIENT_KEY=your_midtrans_client_key 
MIDTRANS_ENDPOINT=https://api.midtrans.com/v2/charge 
GUILD_ID=your_discord_guild_id 
PROJECT_ID=your_google_project_id BUCKET_NAME=your_google_bucket_name 
SPREADSHEET_ID=your_google_spreadsheet_id

## Usage
1. **Run the bot**:
bash python main.py

2. **Interact with the bot**:

   - Use the command `!beli` to start the role purchase process.
   - Use the command `!check_payment` to check the status of your payment.
   - Use the command `!hello` to receive a welcome message.
   - Use the command `!info` to get information about the bot's functionality.

## Deployment
1. **Create a Dockerfile** in the root directory:

dockerfile
Use the official Python image from the Docker Hub

FROM python:3.9-slim
Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1 ENV PYTHONUNBUFFERED 1
Set the working directory
WORKDIR /app
Copy the requirements file
COPY requirements.txt .
Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
Copy the entire application code
COPY . .
Expose the port that FastAPI will run on
EXPOSE 8080
Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

2. **Build the Docker image**:
bash docker build -t your-image-name .

3. **Deploy to Google Cloud Run**:
bash gcloud run deploy your-service-name --image gcr.io/your-project-id/your-image-name --platform managed --region your-region --allow-unauthenticated

## Acknowledgments

- [discord.py](https://discordpy.readthedocs.io/en/stable/) for the Discord bot framework.
- [FastAPI](https://fastapi.tiangolo.com/) for building the web application.
- [Midtrans](https://midtrans.com/) for payment processing.
- [Google Sheets API](https://developers.google.com/sheets/api) for managing user data.
