FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY server.js telemetry.js ./
COPY public ./public
ENV PORT=3000 DB_PATH=/data/data.db
EXPOSE 3000
CMD ["node", "server.js"]
