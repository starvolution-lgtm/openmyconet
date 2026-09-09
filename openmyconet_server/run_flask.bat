@echo off
REM Lokaler Dev-Server. Einstieg ist wsgi.py (App-Factory) -- ein app.py gibt es
REM seit dem omn/-Package-Umbau nicht mehr. SECRET_KEY etc. kommen aus .env.
cd /d "C:\Users\wechs\Desktop\openmyconet\openmyconet_server"
"C:\Users\wechs\Desktop\openmyconet\openmyconet_server\venv\Scripts\python.exe" wsgi.py
