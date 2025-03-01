from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
import subprocess
import signal
import time
from multiprocessing import Process
import uvicorn

from contextlib import asynccontextmanager
import webbrowser
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động ROS khi ứng dụng chạy
    process = subprocess.Popen(["roslaunch", "navstack_pub", "bringup.launch"])
    
    # Tạo bảng nếu chưa có
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS maps (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.commit()
        c.close()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

    yield  

    # Đóng ROS khi ứng dụng dừng
    process.terminate()

app = FastAPI(lifespan=lifespan)
# app = FastAPI()
app.mount("/static", StaticFiles(directory="./static"), name="static")
DATABASE = os.path.join(os.getcwd(), "static", "database.db")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = sqlite3.connect(DATABASE)



    return db

class ROSLaunchProcess:
    process_navigation = None
    process_mapping = None

    @classmethod
    def start_navigation(cls, mapname):
        cls.process_navigation = subprocess.Popen(
            ["roslaunch", "--wait", "navstack_pub", "navigation.launch", "map_file:=" + os.getcwd() + "/static/" + mapname + ".yaml"]
        )

    @classmethod
    def stop_navigation(cls):
        if cls.process_navigation:
            cls.process_navigation.send_signal(signal.SIGINT)

    @classmethod
    def start_mapping(cls):
        cls.process_mapping = subprocess.Popen(
            ["roslaunch", "--wait", "navstack_pub", "hectorslam.launch"]
        )

    @classmethod
    def stop_mapping(cls):
        if cls.process_mapping:
            cls.process_mapping.send_signal(signal.SIGINT)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM maps")
        data = c.fetchall()
        c.close()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

    return templates.TemplateResponse("index.html", {"request": request, "map": data})


@app.api_route("/index/{variable}", methods=["GET", "POST"])
async def themainroute(variable: str, request: Request):
    if variable == "navigation-precheck":
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute("SELECT count(*) FROM maps")
            map_count = c.fetchone()[0]
            c.close()
            return JSONResponse(content={"mapcount": map_count})
        except sqlite3.Error as e:
            print(e)
            return JSONResponse(content={"error": str(e)}, status_code=500)
        finally:
            conn.close()

    elif variable == "gotonavigation":
        mapname = await request.body()  # Bắt buộc phải await
        mapname = mapname.decode("utf-8")
        ROSLaunchProcess.start_navigation(mapname)
        return JSONResponse(content={"status": "success"})

    return JSONResponse(content={"error": "Invalid endpoint"}, status_code=400)


@app.post("/navigation/deletemap")
def deletemap(mapname: str):
    os.system(f"rm -rf {os.getcwd()}/static/{mapname}.yaml {os.getcwd()}/static/{mapname}.png {os.getcwd()}/static/{mapname}.pgm")

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM maps WHERE name=?", (mapname,))
        conn.commit()
        c.close()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

    return "successfully deleted map"


@app.post("/navigation/loadmap")
def navigation_properties(mapname: str):
    ROSLaunchProcess.stop_navigation()
    time.sleep(5)
    ROSLaunchProcess.start_navigation(mapname)
    return "success"


@app.post("/navigation/stop")
def stop():
    os.system("rostopic pub /move_base/cancel actionlib_msgs/GoalID -- {}")
    return "stopped the robot"


@app.post("/mapping/savemap")
def savemap(mapname: str):
    os.system(f"rosrun map_server map_saver -f {os.path.join(os.getcwd(), 'static', mapname)}")
    os.system(f"convert {os.getcwd()}/static/{mapname}.pgm {os.getcwd()}/static/{mapname}.png")

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO maps (name) VALUES (?)", (mapname,))
        conn.commit()
        c.close()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

    return "success"


@app.post("/shutdown")
def shutdown():
    os.system("shutdown now")
    return "shutting down the robot"


@app.post("/restart")
def restart():
    os.system("restart now")
    return "restarting the robot"

# def run_uvicorn(port):
    # uvicorn.run('main:app', host='0.0.0.0', port=port, reload=True)


if __name__ == "__main__":
    # ports = [8088]  # List of ports to run the app on
    # processes = []
    if not os.path.exists("static"):
        os.makedirs("static")
        
    uvicorn.run('main:app', host='0.0.0.0', port=8088, reload=True)

    # for port in ports:
    #     p = Process(target=run_uvicorn, args=(port,))
    #     p.start()
    #     processes.append(p)

    # Optionally, wait for all processes to finish
    # for p in processes:
    #     p.join()