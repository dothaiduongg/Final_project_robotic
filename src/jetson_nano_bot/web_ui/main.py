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
import aiosqlite
from contextlib import asynccontextmanager
import webbrowser

app = FastAPI()
DATABASE = os.path.join(os.getcwd(), "static", "database.db")
app.mount("/static", StaticFiles(directory="./static"), name="static")
templates = Jinja2Templates(directory="templates")
ros_process = None

async def get_db():
    db = await aiosqlite.connect(DATABASE)  # Replace with your DB path
    try:
        yield db
    finally:
        await db.close()
@asynccontextmanager
async def lifespan(app: FastAPI):


    # Khởi động ROS khi ứng dụng chạy
    # global ros_process
    # ros_process = subprocess.Popen(
    # ["bash", "-c", "source ~/catkin_ws/devel/setup.bash && roslaunch mobile_manipulator_body ohmni_empty_world.launch"],
    #  preexec_fn=os.setsid)
    process = subprocess.Popen(["roslaunch", "navstack_pub", "navigation.launch"])
    # print("ROS launched started")


    async with aiosqlite.connect(DATABASE) as conn:    
        try:
            c= await conn.cursor()
            await c.execute("CREATE TABLE IF NOT EXISTS maps (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            await conn.commit()
            print("Table 'maps' checked/created successfully")
            # c.close()
        except aiosqlite.Error as e:
            print(f"Database error: {e}")
        finally:
            await conn.close()
    yield  
    # Đóng ROS khi ứng dụng dừng

    if ros_process:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        print("ROS launched stopped")
    process.terminate()


app.lifespan=lifespan
# app = FastAPI()

# def get_db():
#     db = sqlite3.connect(DATABASE)
#     return db


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
async def index(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    try:
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM maps")
        data = await cursor.fetchall()
        await cursor.close()
    except aiosqlite.Error as e:
        print(f"Database error: {e}")
        data = []
    return templates.TemplateResponse("navigation.html", {"request": request, "map": data})  


@app.api_route("/index/{variable}", methods=["GET", "POST"])
async def themainroute(variable: str, request: Request):
    if variable == "navigation-precheck":
        async for conn in get_db():
            try:
                c = await conn.cursor()
                await c.execute("SELECT count(*) FROM maps")
                map_count = (await c.fetchone())[0]
                await c.close()
                return JSONResponse(content={"mapcount": map_count})
            except sqlite3.Error as e:
                print(e)
                return JSONResponse(content={"error": str(e)}, status_code=500)

    elif variable == "gotonavigation":
        mapname = (await request.body()).decode("utf-8")
        ROSLaunchProcess.start_navigation(mapname)
        return JSONResponse(content={"status": "success"})

    return JSONResponse(content={"error": "Invalid endpoint"}, status_code=400)


@app.post("/navigation")
async def navigation(request: Request, db: sqlite3.Connection = Depends(get_db)):
    try:
        c = await db.cursor()
        await c.execute("SELECT * FROM maps")
        data =  await c.fetchall()
        await c.close()
    except sqlite3.Error as e:
        print(e)
        data = []
    
    return templates.TemplateResponse("navigation.html", {"request": request, "map": data})


@app.post("/navigation/deletemap")
async def deletemap(mapname: str,  conn: aiosqlite.Connection = Depends(get_db)):
    os.system("rm -rf"+" "+os.getcwd()+"/static/"+mapname+".yaml "+os.getcwd()+"/static/"+mapname+".png "+os.getcwd()+"/static/"+mapname+".pgm")

    # conn = get_db()
    try:
        c = await conn.cursor()
        await c.execute("DELETE FROM maps WHERE name=?", (mapname,))
        await conn.commit()
        c.close()
    except sqlite3.Error as e:
        print(e)
    finally:
        await conn.close()

    return "successfully deleted map"

@app.get("/navigation/{variable}")
@app.post("/navigation/{variable}")
async def gotomapping(variable: str):
	if variable == "index":
		ROSLaunchProcess.start_mapping()
	elif variable == "gotomapping":
		ROSLaunchProcess.stop_navigation()
		time.sleep(2)
		ROSLaunchProcess.start_mapping()
	return {"status": "success"}


@app.post("/navigation/loadmap")
async def navigation_properties(mapname: str):
    ROSLaunchProcess.stop_navigation()
    time.sleep(5)
    ROSLaunchProcess.start_navigation(mapname)
    return "success"


@app.post("/navigation/stop")
async def stop():
    subprocess.run("rostopic pub /move_base/cancel actionlib_msgs/GoalID -- {}")
    return "stopped the robot"




@app.get("/mapping")
async def mapping(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    try:
        async with db.cursor() as c:
            await c.execute("SELECT * FROM maps")
            data = await c.fetchall()
    except sqlite3.Error as e:
        print(e)
        data = []
    finally:
        await c.close()
    return templates.TemplateResponse("mapping.html", {"request": request, "title": "Mapping", "map": data})

@app.post("/mapping/cutmapping")
async def killnode():
    ROSLaunchProcess.stop_mapping()
    return {"status": "killed the mapping node"}


@app.post("/mapping/savemap")
async def savemap(mapname: str):
    subprocess.run("rosrun map_server map_saver -f"+" "+os.path.join(os.getcwd(),"static",mapname))
    subprocess.run("convert"+" "+os.getcwd()+"/static/"+mapname+".pgm"+" "+os.getcwd()+"/static/"+mapname+".png")

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
    # if not os.path.exists("static"):
    #     os.makedirs("static")
        
    uvicorn.run('main:app', host='127.0.0.0', port=8090, reload=True)

    # for port in ports:
    #     p = Process(target=run_uvicorn, args=(port,))
    #     p.start()
    #     processes.append(p)

    # Optionally, wait for all processes to finish
    # for p in processes:
    #     p.join()