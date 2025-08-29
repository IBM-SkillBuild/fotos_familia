FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure static/ exists (if using WhiteNoise)
RUN mkdir -p /app/static
RUN echo "body { background: #fff; }" > /app/static/style.css

# Environment variables
ENV PORT=8000
ENV FLASK_ENV=production
ENV DEBUG=False
ENV SECRET_KEY=6edcfbe4afa8dfcaf5675d3bf32b54b7815c6f389b5b83f7258e7bd2fcb71b6b
ENV SMTP_SERVER=smtp.gmail.com
ENV SMTP_PORT=587
ENV SMTP_EMAIL=ecabrerablazquez@gmail.com
ENV SMTP_PASSWORD="lups stlp jaid rzol"
ENV SMTP_FROM_NAME="SMS Auth App"
ENV CLOUDINARY_CLOUD_NAME=dquxfl0fe
ENV CLOUDINARY_API_KEY=415562488892677
ENV CLOUDINARY_API_SECRET=ZDRNfSczRreAzKXTFhQgFsGOZ0M
ENV FACEPP_API_KEY=zWeIYXZKrSdZeFMdv1OszlLc1ahQZDSr
ENV FACEPP_API_SECRET=2P-w4XH5Dvjmmp6DJr-4BCd9DSMqW4QI

CMD ["gunicorn", "--timeout", "120", "--keep-alive", "20", "--workers", "2", "-b", "0.0.0.0:8000", "app:app"]