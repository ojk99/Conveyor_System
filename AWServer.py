import psycopg2 as pg2
import boto3
import getpass
import socket


class AWS_Server:
    def __init__(self):
        self.ID = 0
        # S3 접속 정보
        self.__BUCKET_NAME = "box-s3-buket"  # S3 버킷 서버 이름
        __SERVER_NAME = "s3"  # 서버 이름
        __ACCESS_KEY_ID = "AKIAW3MEDPLYXFKU3W4F"  # S3 관련 권한을 가진 IAM계정 정보
        __ACCESS_SECRET_KEY = "npafqD1Wtg+kaTmtyaWqSuQl/gN2jdanz9ER372X"  # IAM 비밀번호
        __REGION_NAME = "ap-northeast-2"  # 서버 국가 정보
        # AWS RPS 데이터 베이스 접속 정보
        __DATABASE = "boxdb"  # 데이터베이스 모듈 이름
        __HOST = "boxdatabase.czoc6ci6mkxq.us-east-1.rds.amazonaws.com"  # 데이터베이스 엔드 포인트
        __PORT = "5432"  # 포트 PostgreSQL서버 기본
        __USER = "boxadmin"  # 아이디 (관리자)
        __PASSWORD = "admin1234"  # 비밀번호 (관리자)

        # AWS RPS 데이터 베이스 연결
        try:
            self.__conn = pg2.connect(
                database=__DATABASE,
                host=__HOST,
                port=__PORT,
                user=__USER,
                password=__PASSWORD,
            )
        except pg2.Error as e:
            print("AWS RPS 서버 접속 실패")
            return None
        self.__cur = self.__conn.cursor()  # self.cur 에 데이터 베이스 연결

        # AWS S3 서버 연결
        self.__s3_client = boto3.client(
            service_name=__SERVER_NAME,  # 서버 정보
            aws_access_key_id=__ACCESS_KEY_ID,  # IAM 아이디
            aws_secret_access_key=__ACCESS_SECRET_KEY,  # IAM 비밀번호
            region_name=__REGION_NAME,  # 버킷의 리전(국가) 이름
        )
        if self.__s3_client == None:
            print("AWS S3 서버 접속 실패")
            return None

    #############################################################
    ########################### AWS RPS #########################
    #############################################################

    # 데이터베이스에 정보 저장
    def RPS_BoxSave(
        self,
        filename: str = "1",
        num: int = 0,
        product: str = "",
        receiver: str = "",
        sender: str = "",
        address: str = "",
        faulty=11111111,
    ):  # 저장할 정보 매개변수 추가

        try:
            self.__cur.execute(
                f"INSERT INTO public.boxinfo (boxnum, boxproduct, faulty, receiver, boxaddress, sender) VALUES ({num}, '{product}', B'{faulty}', '{receiver}', '{address}', '{sender}');"
            )
        except pg2.Error as e:
            print(e)
            return False
        # 서버에 코드 반영
        self.__conn.commit()

        # 데이터베이스 S3 동기화
        if self.RPS_S3_Syn(filename) != True:
            return False

        return True

    # 특정 데이터 삭제
    def RPS_Delete(self, id: int):
        tablename = "boxinfo"
        de = self.__cur.execute(f"DELETE FROM {tablename} WHERE id = {id};")
        if self.__cur.rowcount == 0:
            print("삭제할 데이터가 존재하지 않습니다.")
            return False
        self.__conn.commit()

        tablename = "s3info"
        self.__cur.execute(f"DELETE FROM {tablename} WHERE id = {id};")
        self.__conn.commit()

        self.Handle_Delete_Img(id)
        return True

    # 데이터 베이스 동기화
    def RPS_S3_Syn(self, filename):
        self.__cur.execute("SELECT * FROM boxinfo ORDER BY id DESC LIMIT 1;")
        id_result = self.__cur.fetchone()

        if id_result:
            id_value = id_result[self.ID]
            boxIMG = (
                "https://box-s3-buket.s3.ap-northeast-2.amazonaws.com/BOX/"
                + str(id_value)
                + ".jpg"
            )

            self.__cur.execute(
                "INSERT INTO public.s3info (id, s3image) VALUES (%s, %s);",
                (id_value, boxIMG),
            )
            self.__conn.commit()

            # 이미지 업로드 (업로드할 사진 명, id)
            if self.Handle_Upload_Img(filename, id_value) != True:
                return False
        else:
            return False
            print("No data retrieved from boxinfo table")

        return True

    # 테이블 값 가져오기 (테이블이름, 열 이름 (* 적으면 모든 열 가져옴))
    def RPS_Select(self, table: str, row_: str):
        INFO = "SELECT " + row_ + " FROM " + table
        row_info = []
        try:
            self.__cur.execute(INFO)
        except pg2.Error as e:
            print(e)
            return False

        rows = self.__cur.fetchall()

        for row in rows:
            print(row)
            row_info.append(row)

        return row_info

    def Find(self, where, what):
        try:
            # 이미 해당 내용이 존재하는지 확인
            self.__cur.execute(
                f"SELECT COUNT(*) FROM public.users WHERE {where} = %s;", (what,)
            )
            existing_users_count = self.__cur.fetchone()[0]
            if existing_users_count > 0:
                # print("이미 존재합니다.")
                return False
            else:
                # print("존재하지 않습니다.")
                return True
        except pg2.Error as e:
            print(e)
            return False

    # 데이터베이스에 정보 확인(로그인)
    # 첫 실행시 실행
    def Login_User(self, __id, __password):
        try:
            # 해당 아이디를 가진 사용자가 존재하는지 확인
            if self.Find("user_name", __id):
                print("해당 아이디를 가진 사용자가 존재하지 않습니다.")
                return False, False

            # 해당 아이디를 가진 사용자의 비밀번호가 맞는지 확인
            if self.Find("(user_name,user_password)", (__id, __password)):
                print("비밀번호가 맞지 않습니다.")
                return False, False

        except pg2.Error as e:
            print(e)
            return False, False

        if not self.Find("(user_name,usesuper)", (__id, True)):
            print(f"슈퍼유저 {__id}님이 로그인 하셨습니다.")
            self.superuse = True
            return True, True
        else:
            print(f"{__id}님이 로그인 하셨습니다.")
            self.superuse = False
            return True, False

    # 데이터베이스에 정보 저장(회원가입)
    def RPS_Join_Member(
        self, __id, __password, __Repassword
    ):  # 저장할 정보 매개변수 추가
        useuper = False

        # 이미 해당 아이디가 존재하는지 확인
        if not self.Find("user_name", __id):
            print("이미 존재하는 아이디입니다.")
            return False
        try:
            # 아이디와 비밀번호의 길이 체크
            if len(__id) > 16 or len(__password) > 16:
                print(
                    "아이디 또는 비밀번호의 길이가 최대 길이를 초과했습니다. 다시 입력해주세요."
                )
                return False

            # 설정한 비밀번호와 같은지 확인
            if __Repassword != __password:
                print("설정한 비밀번호와 같지 않습니다")
                return False

            # 존재하지 않을 경우 새로운 사용자 정보 삽입
            self.__cur.execute(
                f"INSERT INTO public.users (user_name, user_password, usesuper) VALUES ('{__id}', '{__password}', {useuper});"
            )
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        print("회원가입이 완료되었습니다.")
        return True

    # 데이터베이스에 정보 삭제(회원 탈퇴)
    def Delete_User(self, id: str, password: str):
        try:
            # 해당 아이디를 가진 사용자가 존재하는지 확인
            if self.Find("user_name", id):
                print("해당 아이디를 가진 사용자가 존재하지 않습니다.")
                return False

            # 해당 아이디를 가진 사용자가 존재하는지 확인
            if self.Find("(user_name,user_password)", (id, password)):
                print("비밀번호가 맞지 않습니다.")
                return False

            # 사용자 삭제
            self.__cur.execute("DELETE FROM public.users WHERE user_name = %s;", (id,))
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        print(f"{id} 사용자 삭제가 완료되었습니다.")
        return True

    # 데이터베이스 수정
    def Update_data(self, where, who, what, how):
        try:
            # 값을 업데이트
            self.__cur.execute(
                f"UPDATE public.users SET {what} = '{how}' WHERE {where} = '{who}';"
            )
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        return True

    # 불량품 검출
    def RPS_faulty(self):
        self.__cur.execute("SELECT faulty FROM boxinfo ORDER BY id DESC LIMIT 1;")
        id_result = self.__cur.fetchone()

        if id_result[0] == "11111111":
            return True
        else:
            return False

        ################## AWS RPS SuperUser ########################

    # 데이터베이스 유저권한 수정
    def Update_Super_User(self, who, how):
        try:
            self.Update_data("user_name", who, "usesuper", how)
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        return True

    # 데이터베이스에 정보 강제 삭제(강제 회원 탈퇴)
    def SuperUser_Delete_User(self, id: str):
        try:
            # 해당 아이디를 가진 사용자가 존재하는지 확인
            if self.Find("user_name", id):
                print("해당 아이디를 가진 사용자가 존재하지 않습니다.")
                return False
            if self.Find("(user_name, usesuper)", (id, True)):
                # 사용자 삭제
                self.__cur.execute(
                    "DELETE FROM public.users WHERE user_name = %s;", (id,)
                )
                print(f"{id} 사용자 삭제가 완료되었습니다.")
                return True

            else:
                print(
                    "해당 아이디를 가진 사용자는 동일한 권한을 가지고 있어 삭제할수 없습니다."
                )
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        return True

        # 테이블 연동

    def Join_Tables(self):
        try:
            # SQL 쿼리 실행
            self.__cur.execute(
                "SELECT a.id, a.boxnum, a.boxaddress, a.boxproduct, a.receiver, a.sender, a.faulty, b.s3image FROM boxinfo AS a LEFT OUTER JOIN s3info AS b ON a.id = b.id"
            )

            # 결과 가져오기
            rows = self.__cur.fetchall()
            # 결과 출력
            # for row in rows:
            #     id, boxnum, boxproduct, faulty, s3image = row
            # print(
            #     f"ID: {id}, Box Number: {boxnum}, Box Product: {boxproduct}, S3 Image: {s3image}"
            # )

            return rows

        except pg2.Error as e:
            print("PostgreSQL error:", e)
            return False

    # 데이터베이스에 정보 저장(비밀번호 변경,일반회원)
    def RPS_User_Info(
        self, __id, __password, __newpassword, __Repassword
    ):  # 저장할 정보 매개변수 추가

        # 이미 해당 아이디가 존재하는지 확인
        if self.Find("user_name", __id):
            print("해당 아이디를 가진 사용자가 존재하지 않습니다.")
            return False
        try:
            # 해당 아이디를 가진 사용자의 비밀번호가 맞는지 확인
            if self.Find("(user_name,user_password)", (__id, __password)):
                print("비밀번호가 맞지 않습니다.")
                return False

            # 새 비밀번호의 길이 체크
            if len(__newpassword) > 16:
                print(
                    "새 비밀번호의 길이가 최대 길이를 초과했습니다. 다시 입력해주세요."
                )
                return False

            # 새로 설정한 비밀번호가 기존과 같은지 확인
            if __password == __newpassword:
                print("설정한 비밀번호와 같지 않습니다")
                return False

            # 설정한 새 비밀번호와 체크와 같은지 확인
            if __Repassword != __newpassword:
                print("설정한 비밀번호와 같지 않습니다")
                return False

            # 새로운 사용자의 비밀번호 정보 삽입
            self.Update_data("user_name", __id, "user_password", __newpassword)
        except pg2.Error as e:
            print(e)
            return False

        # 서버에 코드 반영
        self.__conn.commit()
        print("비밀번호 변경이 완료되었습니다.")
        return True

    #############################################################
    ########################### AWS S3 ##########################
    #############################################################

    # S3서버에 이미지 저장
    def Handle_Upload_Img(self, file_name, id: int):  # f = 파일명
        FilePath = "./" + file_name + ".jpg"  # 저장할 파일 경로 및 이름
        SaveJPG = "BOX/" + str(id) + ".jpg"  # 저장될 파일 경로 및 이름
        try:
            with open(FilePath, "rb") as data:
                # '로컬의 해당파일경로'+ 파일명 + 확장자
                self.__s3_client.upload_fileobj(data, self.__BUCKET_NAME, SaveJPG)
            print(f"File '{file_name}' uploaded successfully.")
        except Exception as e:
            print("Error:", e)
            return False
        return True

    # 이미지 다운로드
    def Handle_Download_Img(self, id: int):
        try:
            # 데이터베이스에서 파일 경로 가져오기
            self.__cur.execute(
                "SELECT s3image FROM public.s3info WHERE id = %s;", (id,)
            )
            s3image_path = self.__cur.fetchone()[0]  # 파일 경로 가져오기
            print("File path:", s3image_path)
            file_path = s3image_path.split("com/")[-1]
            print(file_path)

            # S3에서 파일 다운로드
            with open(f"./{id}.jpg", "wb") as f:
                self.__s3_client.download_fileobj(self.__BUCKET_NAME, file_path, f)
            print("File downloaded successfully.")

        except Exception as e:
            print("Error:", e)
            return False

        return True

    # S3 이미지 사진 삭제
    def Handle_Delete_Img(self, file_name):
        FilePath = "BOX/" + str(file_name) + ".jpg"
        try:
            # S3 버킷에서 파일 삭제
            self.__s3_client.delete_object(Bucket=self.__BUCKET_NAME, Key=FilePath)
            print(f"File '{FilePath}' deleted successfully.")
        except Exception as e:
            print("Error:", e)
            return False

        return True

    # 데이터베이스 모든 정보 삭제 S3는 웹에서 지워줘야 됨
    def all_Delete(self):
        self.__cur.execute(f"DELETE FROM boxinfo;")
        self.__conn.commit()
        self.__cur.execute(f"DELETE FROM s3info;")
        self.__conn.commit()

    #############################################################
    ########################### Socket ##########################
    #############################################################

    def socket_server(self, num: int = 0):
        if num == 1:
            message = "GO"
        elif num == 2:
            message = "STOP"
        elif num == 3:
            message = "OUT"
        else:
            message = "error"

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_address = ("192.168.0.77", 8080)
            client_socket.connect(server_address)
        except:
            return False

        # 서버로 데이터 전송
        client_socket.send(message.encode())

        data = client_socket.recv(1024)
        data1 = data.decode()
        print("받은 데이터:", data1)

        client_socket.close()

        if data1 == "True":
            return True
        else:
            return False
