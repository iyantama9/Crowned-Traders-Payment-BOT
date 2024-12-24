   # Use the official Python image from the Docker Hub
   FROM python:3.9-slim

   # Set the working directory
   WORKDIR /app

   # Copy the requirements file
   COPY requirements.txt .

   # Install dependencies
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy the rest of the application code
   COPY . .

   # Set environment variables
   ENV PORT=8080

   # Command to run the application
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
