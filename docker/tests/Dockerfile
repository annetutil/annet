FROM python:3.12-slim-bookworm
WORKDIR /test
COPY requirements.in .
RUN pip install --no-cache-dir -r requirements.in
COPY ssh_device.py .
ENTRYPOINT ["python", "ssh_device.py"]
CMD ["--host", "0.0.0.0", "--port", "2222", "--password-file", "/secrets/password", "--public-key", "/secrets/key.pub", "--ready", "/tmp/ready"]
