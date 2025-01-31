from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pickle
from captchaSolver import getCaptchaText
import json
from enum import Enum
import re
from flask import Flask, jsonify
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)

URL=os.getenv("GOLESTAN_URL")
# URL='https://golestan.iust.ac.ir/forms/authenticateuser/main.htm'

STUDENT_NUMBER = os.getenv("STUDENT_NUMBER")
NATIONAL_ID = os.getenv("NATIONAL_ID")

REPORT_NUMBER=102



weekday_map = {
    "شنبه": "SATURDAY",
    "یک شنبه": "SUNDAY",
    "دوشنبه": "MONDAY",
    "سه شنبه": "TUESDAY",
    "چهارشنبه": "WEDNESDAY",
    "پنج شنبه": "THURSDAY",
    "جمعه": "FRIDAY"
}
departmenet_names_map = {
    "مهندسي برق":"ELECTRICAL_ENG",
    "مهندسي راه  آهن":"RAILWAY_ENG",
    "مهندسي صنايع":"INDUSTRIAL_ENG",
    "فيزيك":"PHYSICS",
    "مهندسي مواد و متالورژي":"METALOGY_ENG",
    "مهندسي معماري":"ARCHITECTURE_ENG",
    "مهندسي مكانيك":"MECHANICAL_ENG",
    "مهندسي شيمي، نفت و گاز":"CHEMICAL_ENG",
    "مهندسي عمران":"CIVIL_ENG",
    "مهندسي كامپيوتر":"COMPUTER_ENG",
    "تربيت بدني":"PHYSICALEDU",
    "معارف اسلامي و ادبيات فارسي":"ISLAMICEDU",
    "شيمي":"CHEMISTRY",
    "مديريت، اقتصاد و مهندسي پيشرفت":"MANAGEMENT",
    "واحد نور":"NOOR",
    "پرديس دانشگاهي علم و صنعت":"PARDIS",
    "عمومي":"GENERAL"
    
}

def persian_to_english_number_regex(persian_str):
    persian_digits_map = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', 
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    return re.sub(r'[۰-۹]', lambda x: persian_digits_map[x.group()], persian_str)

cols = [
            "course_number_and_group",   #شماره و گروه درس
            "course_name",  # نام درس
            "total_unit",   # کل واحد
            "practical_unit",   # واحد عملی
            "capacity",     # ظرفیت
            "registered",   #ثبت نام شده
            "waiting",  # تعداد لیست انتظار
            "sex",   #جنس
            "professor_name",   # نام استاد,
            "lecture_location_and_time_info",   # زمان و مکان ارائه,
            "exam_location_and_time",   # زمان و مکان امتحان,
            "limitations",   # محدودیت اخذ,
            "specific_to_some_entrace",     # مخصوص ورودی,
            "opposite_course", # دروس اجبار/متضاد,
            "lecture_method",   # نحوه ارائه درس,
            "course_period",    # دوره درس,
            "can_emergency_delete",     # امکان حذف اظطراری,
            "can_be_taken_by_guests",   # امکان اخذ توسط مهمان,
            "description"    # توضیحات
]

class Sex(Enum):
    COMPLEX=1,
    MALE=2,
    FEMALE=3,
    UNKNOWN=-1
    
captcha_predictor_model = pickle.load(open("finalized_model.sav", "rb"))

def process_data(x:dict):
    processed_data_arr=[]
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

        can_emergency_delete = True
        if  raw_data["can_emergency_delete"] == "خیر":
            can_emergency_delete=False
        elif raw_data["can_emergency_delete"] == "بله":
            can_emergency_delete = True
        else:
            print("unknown can_emergency_delete text found")


        can_be_taken_by_guests = True
        if  raw_data["can_be_taken_by_guests"] == "خیر":
            can_emergency_delete=False
        elif raw_data["can_be_taken_by_guests"] == "بله":
            can_emergency_delete = True
        else:
            print("unknown can_be_taken_by_guests text found")

        total_unit = int(persian_to_english_number_regex(raw_data["total_unit"])) if len(raw_data["total_unit"])>0 else 0
        practical_unit = int(persian_to_english_number_regex(raw_data["practical_unit"])) if len(raw_data["practical_unit"])>0 else 0
        capacity = int(persian_to_english_number_regex(raw_data["capacity"])) if len(raw_data["capacity"])>0 else 0
        registered = int(persian_to_english_number_regex(raw_data["registered"])) if len(raw_data["registered"])>0 else 0
        waiting = int(persian_to_english_number_regex(raw_data["waiting"])) if len(raw_data["waiting"])>0 else 0
        course_number_and_group = persian_to_english_number_regex(raw_data["course_number_and_group"]) 
        description =persian_to_english_number_regex(raw_data["description"]) 
        exam_date=""
        exam_start_time=""
        exam_end_time=""
        match = re.search(r'تاريخ:\s*([\d/]+)\s*ساعت:\s*([\d:]+)-([\d:]+)', raw_data["exam_location_and_time"])
        if match:
            exam_date = persian_to_english_number_regex(match.group(1))
            exam_start_time = persian_to_english_number_regex(match.group(2))
            exam_end_time = persian_to_english_number_regex(match.group(3))



        pattern = r"(\w+)\s(\d{2}:\d{2})-(\d{2}:\d{2})"
        matches = re.findall(pattern, raw_data["lecture_location_and_time_info"])
        schedules = []

        for match in matches:
            day, start_time, end_time = match
            start_time = persian_to_english_number_regex(start_time)
            end_time = persian_to_english_number_regex(end_time)

            schedules.append({
                "day_of_week": weekday_map.get(day),
                "start_time": start_time,
                "end_time": end_time
            })
        if len(course_number_and_group)>0:
            processed_data_arr.append({
                "sex":processed_sex.name,
                "lecture_schedules":schedules,
                "exam_date":exam_date,
                "exam_start_time":exam_start_time,
                "exam_end_time":exam_end_time,
                "can_emergency_delete":can_emergency_delete,
                "can_be_taken_by_guests":can_be_taken_by_guests,
                "total_unit":total_unit,
                "practical_unit":practical_unit,
                "capacity":capacity,
                "registered":registered,
                "waiting":waiting,
                "description":description,
                "professor_name":raw_data["professor_name"],
                "course_name":persian_to_english_number_regex(raw_data["course_name"]),
                "course_number_and_group":course_number_and_group
            })
        else:
            print("HERE 2")
    return processed_data_arr

def get_all_courses(departmenets_courses,wait,driver):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Header")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID,"Form_Body")))
    time.sleep(0.15)

    term =''.join(filter(str.isdigit,wait.until(EC.presence_of_element_located((By.ID, "Table2_1"))).text.strip()))

    departmenet_name = driver.execute_script("""
        var td = document.getElementById("Table2_2");
        return td.childNodes[td.childNodes.length - 1].textContent.trim();
    """)
    course_learning_group = driver.execute_script("""
        var td = document.getElementById("Table2_21");
        return td.childNodes[td.childNodes.length - 1].textContent.trim();
    """)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.CTRData")))
    tr_elements = driver.find_elements(By.CSS_SELECTOR,"tr.CTRData")
    courses=[]
    for tr_e in tr_elements:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "td.CTDData")))    
        td_elements = tr_e.find_elements(By.CSS_SELECTOR,"td.CTDData")
        n=len(cols)
        course={}
        td_texts = [td.text for td in td_elements]
        for i in range(0,n):
            course[cols[i]] = td_texts[i]            
        if (len(course["course_number_and_group"].strip()) > 0):
            courses.append(course)
        else:
            print("HERE")
            
                    
    if (departmenet_name not in  departmenets_courses.keys()):
        departmenets_courses[departmenet_name] = courses
    else:
        departmenets_courses[departmenet_name].append(course)
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Commander")))
    page_input_element = wait.until(EC.presence_of_element_located((By.ID, "TextPage")))
    current_page = page_input_element.get_property("value")
    print("current_page",current_page)
    next_page_btn_element = wait.until(EC.presence_of_element_located((By.ID, "MoveLeft")))
    next_page_btn_element.click()
    new_current_page = page_input_element.get_property("value")
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    if (current_page != new_current_page):            
        get_all_courses(departmenets_courses,wait,driver)

def login(driver,wait):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Faci1")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Form_Body")))
    student_number_input_element = wait.until(EC.presence_of_element_located((By.ID, "F80351")))
    national_id_input_element = wait.until(EC.presence_of_element_located((By.ID, "F80401")))
    captcha_input_element = wait.until(EC.presence_of_element_located((By.ID, "F51701")))
    student_number_input_element.send_keys(STUDENT_NUMBER)
    national_id_input_element.send_keys(NATIONAL_ID)
    login_btn_element = wait.until(EC.presence_of_element_located((By.ID, "btnLog")))
    captcha_image_element = wait.until(EC.presence_of_element_located((By.ID, "imgCaptcha")))
    captcha_image_element.screenshot("captcha.png")
    captcha_text = getCaptchaText("captcha.png")
    captcha_input_element.send_keys(captcha_text)
    login_btn_element.click()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    # driver.switch_to.parent_frame()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Message")))
    try:
        errortext_td_element = driver.find_element(By.ID, "errtxt")
        driver.switch_to.parent_frame() 
        driver.switch_to.parent_frame() 
        if errortext_td_element.text == "لطفا كد امنيتي را به صورت صحيح وارد نماييد":
            login(driver,wait)
    except:
        driver.switch_to.parent_frame() 
        driver.switch_to.parent_frame() 






@app.route("/scrape",methods=['GET'])
def scrape():
    
    driver = webdriver.Firefox()

    driver.maximize_window() # For maximizing window
    driver.implicitly_wait(20) # gives an implicit wait for 20 seconds
    wait = WebDriverWait(driver, 10)

    driver.get(URL)

    time.sleep(5)

    login(driver,wait)

    time.sleep(1)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Faci2")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Master")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Form_Body")))
    report_number_input_element = wait.until(EC.presence_of_element_located((By.ID, "F20851")))
    report_number_input_element.send_keys(REPORT_NUMBER)
    ok_btn_element = wait.until(EC.presence_of_element_located((By.ID, "OK")))
    ok_btn_element.click()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    time.sleep(1)
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Faci3")))
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME,"Commander")))
    view_report_td_btn_element = wait.until(EC.presence_of_element_located((By.ID, "IM16_ViewRep")))
    view_report_td_btn_element.click()

    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    driver.switch_to.parent_frame()
    time.sleep(1)
    x = {}
    get_all_courses(x,wait,driver)
    driver.close()
    
    with open("department_courses.json", "w", encoding="utf-8") as json_file:
        json.dump(x, json_file, indent=4, ensure_ascii=False)  # indent=4 makes it readable

    # temp = {}
    # with open('department_courses.json', 'r', encoding='utf-8') as file:
    #     data=json.load(file)
    #     for k,v in data.items():
    #         temp[departmenet_names_map.get(k,"OTHER")] = process_data(v)
    #     with open("processed_data.json", "w", encoding="utf-8") as json_file:
    #         json.dump(temp, json_file, indent=4, ensure_ascii=False)  # indent=4 makes it readable
    return "Scraped finished successfully"

@app.route("/processRawData",methods=["GET"])
def processRawData():
    temp = {}
    with open('department_courses.json', 'r', encoding='utf-8') as file:
        data=json.load(file)
        for k,v in data.items():
            temp[departmenet_names_map.get(k,"OTHER")] = process_data(v)
        with open("processed_data.json", "w", encoding="utf-8") as json_file:
            json.dump(temp, json_file, indent=4, ensure_ascii=False)  # indent=4 makes it readable
    print(temp)
    return "processing raw data finished successfully"

@app.route('/data',methods=['GET'])
def data():
    with open("processed_data.json", "r", encoding="utf-8") as file:
        data=json.load(file)        
        response = jsonify(data)
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        return response


if __name__ == '__main__':
    app.run(debug=True)