FROM python:3.10
ENV VENV_PATH="/venv"
ENV PATH="$VENV_PATH/bin:$PATH"
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils && \
    apt-get upgrade -y && \
    apt-get install ffmpeg tesseract-ocr -y && \
    apt-get autoclean
RUN pip install --upgrade poetry
RUN python -m venv /venv
COPY . .
# 注意下面这一段，在最后加上了 pysocks 和 python-socks 的安装
RUN poetry build && \
    /venv/bin/pip install --upgrade pip wheel setuptools &&\
    /venv/bin/pip install dist/*.whl && \
    /venv/bin/pip install pysocks python-socks
EXPOSE 8501
CMD tgcf-web
