from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pickle
from captchaSolver import getCaptchaText
import json
from enum import Enum
import re
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import bcrypt
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from pymongo import MongoClient
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
import atexit


load_dotenv()

app = Flask(__name__)
CORS(app)
jwt = JWTManager(app)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)  # Token expires in 1 hour
SCRAPE_DATETIME = "scrape_datetime"
MONGO_HOST = os.getenv("MONGO_HOST")
MONGO_USERNAME = os.getenv("MONGO_USERNAME")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_PORT = os.getenv("MONGO_PORT")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")
MONGO_USERS_COLLECTIONNAME = "users"
client = MongoClient(
    f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/"
)
job_store = MongoDBJobStore(client=client, database="scheduler_db")
job_store.remove_all_jobs()
db = client[MONGO_DBNAME]
users_collection = db[MONGO_USERS_COLLECTIONNAME]
processed_data_collection = db["processed_data_collection"]
raw_data_collection = db["raw_data_collection"]


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


URL = os.getenv("GOLESTAN_URL")
# URL='https://golestan.iust.ac.ir/forms/authenticateuser/main.htm'

STUDENT_NUMBER = os.getenv("STUDENT_NUMBER")
NATIONAL_ID = os.getenv("NATIONAL_ID")

REPORT_NUMBER = 102


weekday_map = {
    "شنبه": "SATURDAY",
    "يك شنبه": "SUNDAY",
    "دوشنبه": "MONDAY",
    "سه شنبه": "TUESDAY",
    "چهارشنبه": "WEDNESDAY",
    "پنج شنبه": "THURSDAY",
    "جمعه": "FRIDAY",
}
departmenet_names_map = {
    "مهندسي برق": "ELECTRICAL_ENG",
    "مهندسي راه  آهن": "RAILWAY_ENG",
    "مهندسي صنايع": "INDUSTRIAL_ENG",
    "فيزيك": "PHYSICS",
    "مهندسي مواد و متالورژي": "METALOGY_ENG",
    "مهندسي معماري": "ARCHITECTURE_ENG",
    "مهندسي مكانيك": "MECHANICAL_ENG",
    "مهندسي شيمي، نفت و گاز": "CHEMICAL_ENG",
    "مهندسي عمران": "CIVIL_ENG",
    "مهندسي كامپيوتر": "COMPUTER_ENG",
    "تربيت بدني": "PHYSICALEDU",
    "معارف اسلامي و ادبيات فارسي": "ISLAMICEDU",
    "شيمي": "CHEMISTRY",
    "مديريت، اقتصاد و مهندسي پيشرفت": "MANAGEMENT",
    "واحد نور": "NOOR",
    "پرديس دانشگاهي علم و صنعت": "PARDIS",
    "عمومي": "GENERAL",
    "رياضي و علوم كامپيوتر": "MATH",
}


def arabic_to_persian(text: str) -> str:
    # arabic: persian
    characters = {
        "ك": "ک",
        "دِ": "د",
        "بِ": "ب",
        "زِ": "ز",
        "ذِ": "ذ",
        "شِ": "ش",
        "سِ": "س",
        "ى": "ی",
        "ي": "ی",
        "١": "۱",
        "٢": "۲",
        "٣": "۳",
        "٤": "۴",
        "٥": "۵",
        "٦": "۶",
        "٧": "۷",
        "٨": "۸",
        "٩": "۹",
        "٠": "۰",
    }

    for arabic, persian in characters.items():
        text = text.replace(arabic, persian)

    return text


def persian_to_english_number_regex(persian_str):
    persian_digits_map = {
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
    }
    return re.sub(r"[۰-۹]", lambda x: persian_digits_map[x.group()], persian_str)


cols = [
    "course_number_and_group",  # شماره و گروه درس
    "course_name",  # نام درس
    "total_unit",  # کل واحد
    "practical_unit",  # واحد عملی
    "capacity",  # ظرفیت
    "registered",  # ثبت نام شده
    "waiting",  # تعداد لیست انتظار
    "sex",  # جنس
    "professor_name",  # نام استاد,
    "lecture_location_and_time_info",  # زمان و مکان ارائه,
    "exam_location_and_time",  # زمان و مکان امتحان,
    "limitations",  # محدودیت اخذ,
    "specific_to_some_entrace",  # مخصوص ورودی,
    "opposite_course",  # دروس اجبار/متضاد,
    "lecture_method",  # نحوه ارائه درس,
    "course_period",  # دوره درس,
    "can_emergency_delete",  # امکان حذف اظطراری,
    "can_be_taken_by_guests",  # امکان اخذ توسط مهمان,
    "description",  # توضیحات
]


class Sex(Enum):
    COMPLEX = (1,)
    MALE = (2,)
    FEMALE = (3,)
    UNKNOWN = -1


captcha_predictor_model = pickle.load(open("finalized_model.sav", "rb"))


def process_data_ta_schedule(description: str):
    pattern = r"(یکشنبه|دوشنبه|سه شنبه|چهارشنبه|پنج شنبه|جمعه|شنبه).*?(\d{1,2}(:\d{2})?-\d{1,2}(:\d{2})?).*?کلاس شماره (\d+)"
    ta_weekday_map = {
        "شنبه": "SATURDAY",
        "یکشنبه": "SUNDAY",
        "دوشنبه": "MONDAY",
        "سه شنبه": "TUESDAY",
        "چهارشنبه": "WEDNESDAY",
        "پنجشنبه": "THURSDAY",
        "جمعه": "FRIDAY",
    }
    match = re.search(pattern, arabic_to_persian(description))
    if match:
        day = match.group(1)
        class_number = match.group(5)
        time = match.group(2)
        start_str, end_str = time.split("-")
        start_time = ""
        end_time = ""
        if ":" not in start_str:
            start_time = f"{start_str}:00"
        if ":" not in end_str:
            end_time = f"{end_str}:00"
        ta_schedule = {
            "class_number": class_number,
            "start_time": start_time,
            "end_time": end_time,
            "day_of_week": ta_weekday_map.get(arabic_to_persian(day), ""),
        }
        return ta_schedule
    return None

def process_data(x: dict, department: str):
    processed_data_arr = []
    for raw_data in x:
        processed_sex = Sex.UNKNOWN
        if raw_data["sex"] == "مختلط":
            processed_sex = Sex.COMPLEX
        elif raw_data["sex"] == "مرد":
            processed_sex = Sex.MALE
        elif raw_data["sex"] == "زن":
            processed_sex = Sex.FEMALE
        else:
            print("unknown course sex found")
        can_delete_in_addordelete = True
        if (raw_data["description"] == "حذف درس توسط آموزش گروه معارف امکان ندارد. در انتخاب درس و گروه دقت نمایید."):
            can_delete_in_addordelete = False
        can_emergency_delete = True
        if raw_data["can_emergency_delete"] == "خیر":
            can_emergency_delete = False
        elif raw_data["can_emergency_delete"] == "بله":
            can_emergency_delete = True
        else:
            print("unknown can_emergency_delete text found")

        can_be_taken_by_guests = True
        if raw_data["can_be_taken_by_guests"] == "خیر":
            can_emergency_delete = False
        elif raw_data["can_be_taken_by_guests"] == "بله":
            can_emergency_delete = True
        else:
            print("unknown can_be_taken_by_guests text found")

        total_unit = (
            float(
                persian_to_english_number_regex(
                    arabic_to_persian(raw_data["total_unit"].replace("/", "."))
                )
            )
            if len(raw_data["total_unit"]) > 0
            else 0
        )
        practical_unit = (
            float(
                persian_to_english_number_regex(
                    arabic_to_persian(raw_data["practical_unit"].replace("/", "."))
                )
            )
            if len(raw_data["practical_unit"]) > 0
            else 0
        )
        capacity = (
            float(
                persian_to_english_number_regex(arabic_to_persian(raw_data["capacity"]))
            )
            if len(raw_data["capacity"]) > 0
            else 0
        )
        registered = (
            int(
                persian_to_english_number_regex(
                    arabic_to_persian(raw_data["registered"])
                )
            )
            if len(raw_data["registered"]) > 0
            else 0
        )
        waiting = (
            int(persian_to_english_number_regex(arabic_to_persian(raw_data["waiting"])))
            if len(raw_data["waiting"]) > 0
            else 0
        )
        course_number_and_group = persian_to_english_number_regex(
            arabic_to_persian(raw_data["course_number_and_group"])
        )
        description = persian_to_english_number_regex(
            arabic_to_persian(raw_data["description"])
        )
        exam_date = ""
        exam_start_time = ""
        exam_end_time = ""
        match = re.search(
            r"تاريخ:\s*([\d/]+)\s*ساعت:\s*([\d:]+)-([\d:]+)",
            raw_data["exam_location_and_time"],
        )
        if match:
            exam_date = persian_to_english_number_regex(
                arabic_to_persian(match.group(1))
            )
            exam_start_time = persian_to_english_number_regex(
                arabic_to_persian(match.group(2))
            )
            exam_end_time = persian_to_english_number_regex(
                arabic_to_persian(match.group(3))
            )

        pattern = re.compile(
            r"درس\((?P<type>ت|ع)\): (?P<day>.+?) (?P<start>\d{2}:\d{2})-(?P<end>\d{2}:\d{2})"
        )
        schedules = []

        for match in pattern.finditer(raw_data["lecture_location_and_time_info"]):
            is_theory = match.group("type") == "ت"
            start_time = persian_to_english_number_regex(
                arabic_to_persian(match.group("start"))
            )
            end_time = persian_to_english_number_regex(
                arabic_to_persian(match.group("end"))
            )
            schedules.append(
                {
                    "day_of_week": weekday_map.get(match.group("day")),
                    "start_time": start_time,
                    "end_time": end_time,
                    "is_theory": is_theory,
                }
            )
        if len(course_number_and_group) > 0:
            course_name = persian_to_english_number_regex(
                arabic_to_persian(raw_data["course_name"])
            )
            if department == "PHYSICALEDU":
                course_name = (
                    course_name
                    + " ("
                    + arabic_to_persian(raw_data["description"])
                    + ")"
                )

            obj = {
                "sex": processed_sex.name,
                "lecture_schedules": schedules,
                "exam_date": exam_date,
                "exam_start_time": exam_start_time,
                "exam_end_time": exam_end_time,
                "can_emergency_delete": can_emergency_delete,
                "can_be_taken_by_guests": can_be_taken_by_guests,
                "total_unit": total_unit,
                "practical_unit": practical_unit,
                "capacity": capacity,
                "registered": registered,
                "waiting": waiting,
                "description": description,
                "professor_name": arabic_to_persian(raw_data["professor_name"]),
                "course_name": course_name,
                "course_number_and_group": course_number_and_group,
                "can_delete_in_addordelete":can_delete_in_addordelete
            }
            ta_schedule = process_data_ta_schedule(raw_data["description"])
            if ta_schedule:
                obj["ta_schedule"] = ta_schedule
            processed_data_arr.append(obj)
        else:
            print("HERE 2")
    return processed_data_arr


def get_all_courses(departmenets_courses, wait, driver):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Header")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "Form_Body")))
    time.sleep(1)

    term = "".join(
        filter(
            str.isdigit,
            wait.until(
                EC.presence_of_element_located((By.ID, "Table2_1"))
            ).text.strip(),
        )
    )

    departmenet_name = driver.execute_script(
        """
        var td = document.getElementById("Table2_2");
        return td.childNodes[td.childNodes.length - 1].textContent.trim();
    """
    )
    course_learning_group = driver.execute_script(
        """
        var td = document.getElementById("Table2_21");
        return td.childNodes[td.childNodes.length - 1].textContent.trim();
    """
    )

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.CTRData")))
    tr_elements = driver.find_elements(By.CSS_SELECTOR, "tr.CTRData")
    courses = []
    for tr_e in tr_elements:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "td.CTDData")))
        td_elements = tr_e.find_elements(By.CSS_SELECTOR, "td.CTDData")
        n = len(cols)
        course = {}
        td_texts = [td.text for td in td_elements]
        for i in range(0, n):
            course[cols[i]] = td_texts[i]
        if len(course["course_number_and_group"].strip()) > 0:
            courses.append(course)
        else:
            print("HERE")

    if departmenet_name not in departmenets_courses.keys():
        departmenets_courses[departmenet_name] = courses
    else:
        departmenets_courses[departmenet_name].extend(courses)
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Commander")))
    page_input_element = wait.until(EC.presence_of_element_located((By.ID, "TextPage")))
    current_page = page_input_element.get_property("value")
    print("current_page", current_page)
    next_page_btn_element = wait.until(
        EC.presence_of_element_located((By.ID, "MoveLeft"))
    )
    next_page_btn_element.click()
    new_current_page = page_input_element.get_property("value")
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    if current_page != new_current_page:
        get_all_courses(departmenets_courses, wait, driver)


def golestan_login(driver, wait):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci1")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Form_Body")))
    student_number_input_element = wait.until(
        EC.presence_of_element_located((By.ID, "F80351"))
    )
    national_id_input_element = wait.until(
        EC.presence_of_element_located((By.ID, "F80401"))
    )
    captcha_input_element = wait.until(
        EC.presence_of_element_located((By.ID, "F51701"))
    )
    student_number_input_element.clear()
    student_number_input_element.send_keys(STUDENT_NUMBER)
    national_id_input_element.clear()
    national_id_input_element.send_keys(NATIONAL_ID)
    login_btn_element = wait.until(EC.presence_of_element_located((By.ID, "btnLog")))
    captcha_image_element = wait.until(
        EC.presence_of_element_located((By.ID, "imgCaptcha"))
    )
    captcha_image_element.screenshot("captcha.png")
    captcha_text = getCaptchaText("captcha.png")
    print("captcha text is : ", captcha_text)
    captcha_input_element.clear()
    captcha_input_element.send_keys(captcha_text)
    login_btn_element.click()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    # driver.switch_to.parent_frame()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Message")))
    try:
        errortext_td_element = driver.find_element(By.ID, "errtxt")
        errortext = errortext_td_element.text

        driver.switch_to.parent_frame()
        driver.switch_to.parent_frame()
        if errortext == "لطفا كد امنيتي را به صورت صحيح وارد نماييد":
            golestan_login(driver, wait)
    except Exception as e:
        print("error : ", e)
        driver.switch_to.parent_frame()
        driver.switch_to.parent_frame()


# @app.route("/processRawData",methods=["GET"])
# @jwt_required()
def processRawData():
    temp = {}
    data = raw_data_collection.find_one({}, {"_id": 0})
    if data == None:
        print("no data to process")
        return
    for k, v in data.items():
        if k == SCRAPE_DATETIME:
            continue
        temp[departmenet_names_map.get(k, "OTHER")] = process_data(
            v, departmenet_names_map.get(k, "OTHER")
        )
    processed_data_collection.delete_many({})
    processed_data_collection.insert_one(
        {**temp, SCRAPE_DATETIME: data[SCRAPE_DATETIME]}
    )
    return "processing raw data finished successfully"


# @app.route("/scrape",methods=['GET'])
# @jwt_required()
def scrape():
    scrape_start_dt = datetime.now(timezone.utc)
    opts = FirefoxOptions()
    if os.getenv("HEADLESS") == "1":
        opts.add_argument("--headless")
    driver = webdriver.Firefox(options=opts)

    driver.maximize_window()  # For maximizing window
    driver.implicitly_wait(20)  # gives an implicit wait for 20 seconds
    wait = WebDriverWait(driver, 10)

    driver.get(URL)
    time.sleep(5)

    golestan_login(driver, wait)

    time.sleep(3)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci2")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Form_Body")))
    report_number_input_element = wait.until(
        EC.presence_of_element_located((By.ID, "F20851"))
    )
    time.sleep(1)
    report_number_input_element.send_keys(REPORT_NUMBER)
    ok_btn_element = wait.until(EC.presence_of_element_located((By.ID, "OK")))
    ok_btn_element.click()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    time.sleep(3)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "Commander")))
    time.sleep(1)
    view_report_td_btn_element = wait.until(
        EC.presence_of_element_located((By.ID, "IM16_ViewRep"))
    )
    view_report_td_btn_element.click()

    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    time.sleep(3)
    x = {}
    get_all_courses(x, wait, driver)
    driver.close()
    raw_data_collection.delete_many({})
    raw_data_collection.insert_one({**x, SCRAPE_DATETIME: scrape_start_dt})

    processRawData()
    return "Scraped finished successfully"


@app.route("/departments", methods=["GET"])
def get_departments():
    return [
        {"label": arabic_to_persian(key), "value": value}
        for key, value in departmenet_names_map.items()
    ]


@app.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    jwt_payload = get_jwt_identity()
    user = users_collection.find_one({"username": jwt_payload})
    user_courses = user.get("courses", [])
    data = processed_data_collection.find_one({}, {"_id": 0})
    flatten_data = [item for value in data.values() for item in value]

    return {
        "total_unit": sum(
            item["total_unit"]
            for item in flatten_data
            if item["course_number_and_group"] in user_courses
        ),
        "data": [
            {
                "course_number_and_group": item["course_number_and_group"],
                "course_name": item["course_name"],
                "unit": item["total_unit"],
            }
            for item in flatten_data
            if item["course_number_and_group" in user_courses]
        ],
    }


@app.route("/userCourses", methods=["GET"])
@jwt_required()
def getUserCourses():
    jwt_payload = get_jwt_identity()
    user = users_collection.find_one({"username": jwt_payload})
    return jsonify(user.get("courses", []))


@app.route("/data", methods=["GET"])
@jwt_required()
def data():
    data = processed_data_collection.find_one({}, {"_id": 0})
    response = jsonify(data)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@app.route("/userCourses", methods=["POST"])
@jwt_required()
def addCourse():
    if not request.is_json:
        return jsonify({"msg": "invalid format"}), 400
    data = request.get_json()
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        return jsonify({"error": "Request body must be a list of strings"}), 400
    jwt_payload = get_jwt_identity()
    user = users_collection.find_one({"username": jwt_payload})
    existing_courses = user.get("courses", [])
    updated_courses = list(set(existing_courses + data))
    users_collection.update_one(
        {"username": jwt_payload}, {"$set": {"courses": updated_courses}}
    )
    return jsonify(updated_courses), 200


@app.route("/userCourses", methods=["PUT"])
@jwt_required()
def removeCourse():
    if not request.is_json:
        return jsonify({"msg": "invalid format"}), 400
    data = request.get_json()
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        return jsonify({"msg": "Request body must be a list of strings"}), 400
    jwt_payload = get_jwt_identity()
    user = users_collection.find_one({"username": jwt_payload})
    if not user:
        return jsonify({"msg": "user not found!"}), 404
    existing_courses = user.get("courses", [])
    updated_courses = [course for course in existing_courses if course not in data]
    users_collection.update_one(
        {"username": jwt_payload}, {"$set": {"courses": updated_courses}}
    )
    return jsonify(updated_courses), 200


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    department = data.get("department")
    sex = data.get("sex")
    if users_collection.find_one({"username": username}):
        return jsonify({"msg": "user already exists"}), 400

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    users_collection.insert_one(
        {
            "username": username,
            "password_hash": hashed_password,
            "department": department,
            "sex": sex,
        }
    )
    return jsonify({"msg": "user registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    user = users_collection.find_one({"username": username})
    if user and verify_password(password, user["password_hash"]):
        additional_claims = {
            "department": user.get("department", ""),
            "sex": user.get("sex"),
        }
        access_token = create_access_token(
            identity=username, additional_claims=additional_claims
        )
        return jsonify(access_token=access_token)
    return jsonify({"msg": "invalid username or password"}), 400


scheduler = BackgroundScheduler(jobstores={"default": job_store})
scheduler.add_job(scrape, "interval", seconds=60 * 10)
scheduler.add_job(processRawData, "interval", seconds=30)

# scrape()
if __name__ == "__main__":
    app.run(debug=True)

with app.app_context():
    scheduler.start()
    # scrape()

# @app.teardown_appcontext
# def stop_scheduler(exception=None):
#     scheduler.shutdown()
