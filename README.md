python server/server.py --add-user ivan 1234
python server/server.py --run

python client/client_cli.py
python client/client_gui.py
python client/main.py

lsof -i :8888
kill -9 45123