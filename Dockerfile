FROM python:3.12.0-slim
COPY main.py upload_event.py requirements.txt ./
RUN pip install -r requirements.txt
ENTRYPOINT python3 main.py $channelId $token