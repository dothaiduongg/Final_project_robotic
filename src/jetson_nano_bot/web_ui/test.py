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
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database path
DATABASE = os.path.join(os.getcwd(), "static", "database.db")

# Async database dependency
async def get_db():
    async with aiosqlite.connect(DATABASE) as db:
        yield db

# Lifespan event for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch ROS
    process = subprocess.Popen(["roslaunch", "mobile_manipulator_body", "ohmni_empty_world.launch"])
    
    # Create table if it doesn’t exist
    async with aiosqlite.connect(DATABASE) as conn:  # Direct connection for lifespan
        try:
            cursor = await conn.cursor()
            await cursor.execute("CREATE TABLE IF NOT EXISTS maps (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            await conn.commit()
            print("Table 'maps' checked/created successfully")
        except aiosqlite.Error as e:
            print(f"Database error: {e}")
        finally:
            await cursor.close()  # Close cursor explicitly

    yield  # Application runs here

    # Shutdown: Terminate ROS
    process.terminate()
    try:
        process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
    except subprocess.TimeoutExpired:
        process.kill()  # Force kill if it doesn’t terminate

# Assign lifespan to the app
app.lifespan = lifespan

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    try:
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM maps")
        data = await cursor.fetchall()
        await cursor.close()
    except aiosqlite.Error as e:
        print(f"Error fetching maps: {e}")
        data = []

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Index", "map": data}
    )

if __name__ == "__main__":
    uvicorn.run("test:app", host="0.0.0.0", port=8000, reload=True)