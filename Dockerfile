FROM python:3.8-slim

WORKDIR /app

# both files are explicitly required!
COPY Pipfile Pipfile.lock ./

RUN pip install pipenv && \
	apt-get update && \
	apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
	pipenv install --deploy --system && \
	apt-get remove -y gcc python3-dev libssl-dev && \
	apt-get autoremove -y && \
	pip uninstall pipenv -y

COPY app ./

CMD ["python", "main.py", "/config/config.yaml"]
