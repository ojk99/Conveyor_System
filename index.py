import cv2
from numpy import True_
from ultralytics import YOLO
import random
from pyzbar.pyzbar import decode
import time

from google.cloud import vision
import threading

from flask import Flask, Response, render_template, request, jsonify
import cv2
import numpy as np
import AWServer as AS
import cProfile


app = Flask(__name__)
AWS = AS.AWS_Server()
lock = False
super_user = False
user = ""
resQR = False
qrinfo = ""
WaitNext = False
BoxCheck = False
DamageCheck = False

bestTxt = 0

lstnum = []
numdict = {}

LastProductNum = 0


my_file = open("C:\\python\\project\\coco.txt", "r")
data = my_file.read()
class_list = data.split("\n")
my_file.close()

detection_colors = []
for i in range(len(class_list)):
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    detection_colors.append((b, g, r))

model6 = YOLO("C:\\python\\project\\model6.pt", "v8")
model7 = YOLO("C:\\python\\project\\model7.pt", "v8")
damagemodel = YOLO("C:\\python\\project\\damaged_detect.pt", "v8")
frame_wid = 640
frame_hyt = 480

key_path = r"C:\python\project\teamproject-416403-41cdf314768a.json"
client = vision.ImageAnnotatorClient.from_service_account_file(key_path)

lstnum_lock = threading.Lock()
AWS_check = [True, True]


def process_image(image):
    image = vision.Image(content=image)
    text_response = client.text_detection(image=image)
    texts = text_response.text_annotations
    if texts:
        strres = ""
        for i in texts[0].description:
            if str(i).isdigit() == True:
                strres += i

        if strres != "":
            res = int(strres)
            with lstnum_lock:
                lstnum.append(res)  # 임계 영역 안에서 리스트에 접근


def capture_and_process(roi):
    _, roi_image_buffer = cv2.imencode(".jpg", roi)
    roi_image_bytes = roi_image_buffer.tobytes()
    threading.Thread(target=process_image, args=(roi_image_bytes,)).start()


def decode_and_display(frame):
    decoded_objects = decode(frame)
    global resQR
    global qrinfo
    if len(decoded_objects) == 0:
        resQR = False
        return

    current_time = time.time()
    for obj in decoded_objects:
        x, y, w, h = obj.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        print("QR : " + obj.data.decode("utf-8"))
        resQR = True
        qrinfo = str(obj.data.decode("utf-8"))


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/join")
def join():
    return render_template("join.html")


@app.route("/user")
def user():
    global super_user
    if super_user == True:
        users = AWS.RPS_Select("users", "(id, user_name, user_password, usesuper)")
        return render_template("user.html", user=users)
    else:
        return "관리자가 아닙니다."


@app.route("/edit/user", methods=["POST"])
def edit_user():
    if request.method == "POST":
        userid = request.form["userid"]
        password = request.form["password"]
        admin = request.form["admin"]
        if admin == "true":
            admin == True
        else:
            admin == False

        AWS.Update_data("user_name", userid, "user_password", password)
        AWS.Update_data("user_name", userid, "usesuper", admin)

        return "유저 정보가 성공적으로 수정되었습니다."
    else:
        return "에러"


@app.route("/user/delete", methods=["POST"])
def user_delete():
    if request.method == "POST":
        userid = request.json.get("userid")
        print(userid)
        if AWS.SuperUser_Delete_User(userid):
            return jsonify({"message": "사용자 {}를 삭제했습니다.".format(userid)})
        else:
            return jsonify({"error": "사용자 삭제에 실패했습니다."}), 500


errr = {
    "normal": "OK",
    1: "hole",
    2: "NonChar",
    3: "crumpling",
}


@app.route("/boxinfo", methods=["GET"])
def boxinfo():
    boxs = AWS.Join_Tables()
    boxsinfo = []
    for row in boxs:
        id, boxnum, boxaddress, boxproduct, receiver, sender, faulty1, s3image = row
        faulty = None
        if faulty1 != None:
            faulty = []
            for i in range(3):
                arr = 1 << i
                if int(faulty1) & arr == 0:
                    faulty.append(errr[i + 1])
                else:
                    faulty.append(errr["normal"])
        if faulty == None:
            faulty = ["None", "None", "None"]
        if faulty1 == "11111111":
            fault = ["정상"]
        else:
            fault = ["불량"]
        boxsinfo.append(
            fault
            + [id, boxnum, boxaddress, boxproduct, receiver, sender]
            + faulty
            + [s3image]
        )
    return render_template("boxinfo.html", box=boxsinfo)


# 로그인 창
@app.route("/login", methods=["POST"])
def login():
    global lock
    global user
    global super_user
    if request.method == "POST":
        inputID = request.form.get("username")
        inputPassword = request.form.get("pass")
        lock, super_user = AWS.Login_User(inputID, inputPassword)
        if lock:
            print("로그인 성공")
            user = inputID
            # 성공 폼
            return render_template("menu.html", result="로그인 성공", use=user)
        else:
            print("로그인 실패")
            return render_template("login.html", result="아이디가 존재하지 않습니다.")


# 회원가입 창
@app.route("/join/member", methods=["POST", "GET"])
def join_member():
    if request.method == "POST":
        inputID = request.form.get("username")
        inputPassword = request.form.get("pass")
        inputPassword_chk = request.form.get("pass_chk")
        if AWS.RPS_Join_Member(inputID, inputPassword, inputPassword_chk):
            print("회원가입 완료")
            # 성공 폼
            return render_template("login.html", result="회원가입 완료")
        else:
            print("회원가입 실패")
            return render_template("join.html", result="회원가입 실패")


# 메뉴
@app.route("/menu")
def menu():
    global lock
    global user
    if lock == True:
        return render_template("menu.html", use=user)
    else:
        return render_template("login.html")


@app.route("/video_feed")
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/boxcv")
def boxcv():
    return render_template("boxcv.html")


@app.route("/user_info")
def user_info():
    return render_template("user_info.html")


@app.route("/user_info/chk", methods=["POST"])
def user_chk():
    if request.method == "POST":
        inputID = request.form.get("pass")
        inputPassword = request.form.get("pass_n")
        inputPassword_chk = request.form.get("pass_chk")
        if AWS.RPS_User_Info(user, inputID, inputPassword, inputPassword_chk):
            return "비밀번호 변경 완료"
        else:
            return "비밀변호 변경 실패"


@app.route("/boxcv/start")
def boxcvstart():
    try:
        AWS.socket_server(1)
        # 컨베이어 벨트 시작 코드
        return "OK"
    except:
        return "fail"


@app.route("/boxcv/stop")
def boxcvstop():
    try:
        # 컨베이어 벨트 종료 코드
        AWS.socket_server(2)
        return "OK"
    except:
        return "fail"


def gen():
    roi = np.identity(3)
    cap = cv2.VideoCapture(0)
    cv2.namedWindow("YOLOv8")
    global resQR
    global WaitNext
    global DamageCheck
    global LastProductNum
    global AWS_check
    while cap.isOpened():
        success, frame = cap.read()
        if success:
            detect_params = model6.predict(source=[frame], conf=0.8, save=False)
            DP = detect_params[0].numpy()
            if len(DP) != 0:
                for i in range(len(detect_params[0])):
                    boxes = detect_params[0].boxes
                    box = boxes[i]
                    clsID = box.cls.numpy()[0]
                    bb = box.xyxy.numpy()[0]
                    if class_list[int(clsID)] == "PERSON":
                        continue
                    cv2.rectangle(
                        frame,
                        (int(bb[0]), int(bb[1])),
                        (int(bb[2]), int(bb[3])),
                        detection_colors[int(clsID)],
                        3,
                    )
                    if int(bb[0]) < 70:
                        BoxCheck = False
                        continue
                    else:
                        BoxCheck = True
                    x1, y1, x2, y2 = int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])
                    roi = frame[y1:y2, x1:x2]
                    detect_damage = damagemodel.predict(
                        source=[roi], conf=0.64, save=False
                    )
                    DPdam = detect_damage[0].numpy()
                    if len(DPdam) != 0:
                        DamageCheck = True
                        for i in range(len(detect_damage[0])):
                            dboxes = detect_damage[0].boxes
                            dbox = dboxes[i]
                            dclsID = dbox.cls.numpy()[0]
                            dbb = dbox.xyxy.numpy()[0]
                            cv2.rectangle(
                                roi,
                                (int(dbb[0]), int(dbb[1])),
                                (int(dbb[2]), int(dbb[3])),
                                detection_colors[int(dclsID)],
                                3,
                            )
                    capture_and_process(roi)
                    decode_and_display(roi)

                    if resQR == True:
                        qr = qrinfo.split("/")
                        if LastProductNum == qr[3]:
                            resQR = False
                            BoxCheck = False
                            continue

            cv2.imshow("YOLOv8", frame)

            if resQR == True and BoxCheck == True:
                lstqr = qrinfo.split("/")
                productinfo = lstqr[0]
                recieverinfo = lstqr[1]
                senderinfo = lstqr[2]
                LastProductNum = lstqr[3]

                if AWS_check == [True, True]:

                    cv2.imwrite("pic.jpg", frame)

                    try:
                        with open("pic.jpg", "rb") as image_file:
                            image_data = image_file.read()
                    except Exception as e:
                        print("Failed to read image file:", e)
                        image_data = None

                    if image_data is not None:
                        for i in range(2):
                            yield (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n\r\n"
                                + image_data
                                + b"\r\n"
                            )

                    maxcnt = 0
                    maxval = 0
                    for i in lstnum:
                        cnt = 0
                        for k in lstnum:
                            if i == k:
                                cnt += 1
                        if cnt >= maxcnt:
                            maxcnt = cnt
                            maxval = i

                    maxvallen = len(str(maxval))
                    valerror = False
                    if maxvallen != 8:
                        valerror == True

                    if DamageCheck == False and maxval != 0 and valerror == False:
                        AWS_th = threading.Thread(
                            target=AWS_SAVE,
                            args=(
                                "pic",
                                maxval,
                                productinfo,
                                11111111,
                                recieverinfo,
                                senderinfo,
                            ),
                        )
                        AWS_th.start()
                    elif (maxval == 0 or valerror == True) and DamageCheck == True:
                        AWS_th = threading.Thread(
                            target=AWS_SAVE,
                            args=(
                                "pic",
                                maxval,
                                productinfo,
                                11111100,
                                recieverinfo,
                                senderinfo,
                            ),
                        )
                        SOCKET_th = threading.Thread(target=Faluty_BOX)
                        AWS_th.start()
                        SOCKET_th.start()
                    elif DamageCheck == True:
                        AWS_th = threading.Thread(
                            target=AWS_SAVE,
                            args=(
                                "pic",
                                maxval,
                                productinfo,
                                11111110,
                                recieverinfo,
                                senderinfo,
                            ),
                        )
                        SOCKET_th = threading.Thread(target=Faluty_BOX)
                        AWS_th.start()
                        SOCKET_th.start()
                    elif maxval == 0 or valerror == True:
                        AWS_th = threading.Thread(
                            target=AWS_SAVE,
                            args=(
                                "pic",
                                maxval,
                                productinfo,
                                11111101,
                                recieverinfo,
                                senderinfo,
                            ),
                        )
                        SOCKET_th = threading.Thread(target=Faluty_BOX)
                        AWS_th.start()
                        SOCKET_th.start()

                print("lstnum:")
                for i in range(len(lstnum)):
                    print(lstnum[i])

                lstnum.clear()

            BoxCheck = False
            DamageCheck = False

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyWindow("YOLOv8")


def AWS_SAVE(filnamestr, maxval, productinfo, faultybit, recieverinfo, senderinfo):
    global AWS_check
    AWS_check[0] = False
    AWS.RPS_BoxSave(
        filename=filnamestr,
        num=maxval,
        product=productinfo,
        faulty=faultybit,
        receiver=recieverinfo,
        sender=senderinfo,
    )
    AWS_check[0] = True


# 소켓 스레드
def Faluty_BOX():
    global AWS_check
    AWS_check[1] = False
    AWS.socket_server(3)
    AWS_check[1] = True


def run_flask_app():
    app.run("0.0.0.0", port=5000)


if __name__ == "__main__":
    cProfile.run("run_flask_app()", filename="profile_data.txt")
