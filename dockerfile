# Gunakan image Python 3.12 sebagai base
FROM python:3.12

# Setel direktori kerja ke root
WORKDIR /

# Salin file requirements dan install dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file ke dalam kontainer
COPY . .

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
