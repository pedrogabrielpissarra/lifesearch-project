# Use official Python runtime as a parent image
FROM python:3.11-slim


# Working directory
WORKDIR /app

# Copy both requirements files first (to leverage Docker cache)
COPY requirements.txt requirements.txt
COPY requirements-dev.txt requirements-dev.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dev.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose the port the app runs on Flask or Gunicorn
# development server default port is 5000
EXPOSE 5000

# Define environment variables
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
# To production, you might want to set FLASK_ENV=production

# Command to run the application
# To develop with Flask's built-in server (not for production):
CMD ["flask", "run"]

# To production, consider using Gunicorn:
# CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "run:app"] # Uncomment this line for production
