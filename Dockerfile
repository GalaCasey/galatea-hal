FROM python:3.5-slim
ADD . /src
WORKDIR /src
RUN pip install -r requirements.txt
CMD python ./bot/app.py
