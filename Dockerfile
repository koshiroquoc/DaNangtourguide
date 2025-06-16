FROM python:3.12-slim

WORKDIR /app

# Cài các thư viện hệ thống tối thiểu
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy toàn bộ code và data vào container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir httpserver

# Download spaCy model nếu code có dùng (xem lại Indexing.py có import spacy không)
RUN python -m spacy download en_core_web_md

# Expose port cho Streamlit UI
EXPOSE 8501
EXPOSE 8888

# Lệnh mặc định (chỉnh lại nếu muốn chạy file python trực tiếp)
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
