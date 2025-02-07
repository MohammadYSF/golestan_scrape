# Golestan Scraper

## Overview
This project is a web scraper and API that extracts course data from the Golestan system of Iran University of Science and Technology (IUST). It uses Selenium to navigate and scrape the data, processes the extracted data, and provides an API to store and retrieve course-related information using MongoDB.

Visit https://github.com/MohammadYSF/elmostime for the frontend application

## Features
- Automated login to the Golestan system using Selenium.
- Captcha solving with a pre-trained model.
- Scraping of course schedules, professor names, and exam times.
- Conversion of Persian characters and numbers to standard formats.
- API for managing users and authentication with JWT.
- Task scheduling with APScheduler, storing jobs in MongoDB.

## Technologies Used
- Python
- Flask (for the API)
- Selenium (for web scraping)
- MongoDB (for storing user and course data)
- APScheduler (for task scheduling)
- JWT Authentication
- bcrypt (for password hashing)

## Prerequisites
Before running the project, ensure you have:
- Python installed
- MongoDB instance running
- Necessary environment variables configured in a `.env` file
- Firefox and Geckodriver installed for Selenium
- use this repo https://github.com/AmirH-Moosavi/Golestan to train the captcha solver model . a .sav file is all you need from this repo  

## Installation

you can run this code from the source , or use docker compose 
1. Clone the repository:
   ```bash
   git clone https://github.com/MohammadYSF/golestan_scrape
   cd golestan_scrape
   ```

2. Configure your `.env` file with the following variables:
   ```plaintext
   JWT_SECRET_KEY=your_secret_key
   MONGO_HOST=localhost
   MONGO_USERNAME=your_username
   MONGO_PASSWORD=your_password
   MONGO_PORT=27017
   MONGO_DBNAME=your_database
   GOLESTAN_URL=https://golestan.iust.ac.ir/forms/authenticateuser/main.htm
   STUDENT_NUMBER=your_student_number
   NATIONAL_ID=your_national_id
   ```

## Running the Application

if using docker compose :
```bash
docker compose up --build
```
else : 

```bash
python app.py
```

The API will be available at `http://localhost:5000`.


## Notes
- The scraper interacts with Golestan's web portal and requires valid credentials.
- Ensure you comply with any university regulations regarding automated access.
- Captcha solving is based on a pre-trained model stored as `finalized_model.sav`.

## License
This project is licensed under the MIT License.

## Author
Mohammad Yousefiyan

