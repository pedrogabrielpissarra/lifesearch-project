# Use uma imagem oficial do Python como base
FROM python:3.9-slim

# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copie o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt requirements.txt

# Instale as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copie o restante do código da aplicação para o diretório de trabalho
COPY . .

# Exponha a porta em que o Flask (ou Gunicorn) estará rodando
# O servidor de desenvolvimento do Flask geralmente roda na porta 5000
EXPOSE 5000

# Defina variáveis de ambiente (opcional, mas bom para Flask)
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
# Para produção, você pode querer definir FLASK_ENV=production

# Comando para rodar a aplicação
# Para desenvolvimento/simplicidade, você pode usar o servidor do Flask:
CMD ["flask", "run"]

# Para um ambiente de produção, é altamente recomendável usar um servidor WSGI como Gunicorn:
# CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]
# Se for usar Gunicorn, adicione 'gunicorn' ao seu requirements.txt
