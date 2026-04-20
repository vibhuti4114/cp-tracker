# ----------------------
# Build stage
# ----------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./
RUN npm install

# Copy full frontend source
COPY frontend/ .

# Build-time API URL
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# ----------------------
# Serve stage
# ----------------------
FROM nginx:alpine

# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx template (IMPORTANT)
COPY frontend/nginx.conf /etc/nginx/templates/default.conf.template

# Expose port (Railway ignores but fine)
EXPOSE 80

# Start nginx with Railway PORT
CMD ["sh", "-c", "envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]