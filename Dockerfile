FROM python:latest

ENV CONGIFILE=/zap2itconfig.ini
ENV LANGUAGE=en

# Wait 12 Hours after run
ENV SLEEPTIME=43200

ADD zap2it-main.py .
# ADD zap2itconfig.ini .

RUN pip install requests configparser

CMD ["python","./zap2it-main.py"]
