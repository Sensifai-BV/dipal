# ===== Stage 1: Build dependencies =====
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./

ARG VITE_BASE_URL
ENV VITE_BASE_URL=$VITE_BASE_URL

RUN npm install

COPY . .

# COPY .env .env

RUN npm run build



# ===== Stage 2: Final runtime =====
FROM node:22-alpine

ARG VITE_BASE_URL
ENV VITE_BASE_URL=$VITE_BASE_URL

WORKDIR /app

RUN  npm i -g vite@latest

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["npx" , "vite" , "preview" , "--host" , "0.0.0.0" , "--port" , "3000"]
