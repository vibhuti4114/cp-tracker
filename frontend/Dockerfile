# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files from frontend folder
COPY frontend/package*.json ./
RUN npm install

# Copy full frontend source
COPY frontend/ .

# Build-time API URL
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# Serve stage
FROM nginx:alpine

# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]